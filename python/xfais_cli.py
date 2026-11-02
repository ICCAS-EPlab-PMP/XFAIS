#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xfais_cli.py — pyFAI-style command line interface for X-FAIS analysis services.

xfais_cli.py — 供外部 AI agent 直接调用的 X-FAIS 命令行层（pyFAI 风格子命令）。

The CLI is a thin, dependency-free wrapper around the same ``services.*``
modules the desktop/web application uses, so a script or an external agent can
reach X-FAIS analysis capabilities without the UI:

    xfais-cli info *.edf
    xfais-cli poni calib.poni
    xfais-cli average -o dark.edf -m median *.edf
    xfais-cli integrate -p calib.poni -n 2048 --unit q_nm^-1 *.edf
    xfais-cli bgsubtract -b bg.edf --ion-folder ion/ -o out/ *.edf
    xfais-cli transmission *.edf --region rect:100,100,300,300 --csv T.csv
    xfais-cli lamellar curve.txt
    xfais-cli orientation chi.txt --method both

本命令行层只是 ``services.*`` 的薄封装——与桌面/Web 应用走同一套 Python
业务代码，因此结果口径一致。设计约定：

* 子命令沿用 pyFAI 官方 CLI（pyFAI-average / pyFAI-integrate /
  pyFAI-waxs）的语义与命名习惯，降低迁移成本；
* 浮点输出统一 ``%.6g``（6 位有效数字），紧凑且足够定位问题；
* 路径含 ``*`` / ``?`` 时由 CLI 自行 glob 展开（Windows shell 不展开通配符）；
* 错误一律写入 stderr 并以非 0 退出码结束，stdout 只放结果；
* 支持 ``--json`` 的子命令输出机器可解析的 JSON；
* 只依赖已随 X-FAIS 附带的 numpy / fabio / h5py / pyFAI，不引入新第三方库。

Usage / 用法::

    python xfais_cli.py <command> [options] [files...]
    python xfais_cli.py --help
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Make ``services`` importable no matter which directory the process started
# in — xfais_cli.py sits next to the services package, exactly like
# service_launcher.py. / 无论从哪个工作目录启动，都能 import services（与本文件同级）。
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import numpy as np

from services.bg_subtractor import (
    calc_transmission,
    match_ionchamber,
    parse_ionchamber_file,
    subtract_with_reference,
)
from services.image_loader import ImageLoader
from services.integrator import UNIT_LABELS, IntegratorFactory
from services.lamellar_analysis import analyze_lamellar
from services.orientation_analysis import (
    fwhm_orientation_index,
    hermans_orientation,
)
from services.transmission import (
    compute_transmission_rows,
    export_transmission_csv,
    region_pixel_sum,
    validate_region,
)

#: CLI layer version (independent of the X-FAIS application version).
#: CLI 层自身版本号（与应用版本号相互独立，后者由 version 子命令读取 package.json）。
__version__ = "1.0.0"

#: hc in keV·Å — used to derive the photon energy from the wavelength.
#: hc（keV·Å）——由波长换算光子能量。
HC_KEV_ANGSTROM = 12.398419843320026

#: One-dimensional integration units understood by pyFAI.
#: pyFAI 支持的一维积分单位。
INTEGRATION_UNITS: Tuple[str, ...] = (
    "q_nm^-1",
    "q_A^-1",
    "2th_deg",
    "2th_rad",
    "r_mm",
)

#: Stacking modes accepted by ``average`` (pyFAI-average semantics).
#: ``average`` 子命令接受的叠加模式（对齐 pyFAI-average）。
AVERAGE_MODES: Tuple[str, ...] = ("mean", "median", "min", "max", "sum")

#: Canonical file suffixes per output format. / 各输出格式的规范后缀。
_FORMAT_SUFFIX: Dict[str, Tuple[str, ...]] = {
    "edf": (".edf",),
    "tif": (".tif", ".tiff"),
    "npy": (".npy",),
    "h5": (".h5", ".hdf5"),
}

#: Extensions scanned inside ``--ion-folder``. / ``--ion-folder`` 内扫描的扩展名。
_ION_EXTENSIONS: Tuple[str, ...] = (".ionchamber", ".ion", ".txt", ".dat")


# ---------------------------------------------------------------------------
# Errors / 错误类型
# ---------------------------------------------------------------------------


class CliError(Exception):
    """Recoverable command error → stderr + non-zero exit status.

    可恢复的命令错误 → 写 stderr 并返回非 0 退出码。
    """


class _ParseExit(Exception):
    """argparse exit request (--help / -V / usage error), never raised outside.

    argparse 的退出请求（--help / -V / 用法错误），不会逃出 main()。
    """

    def __init__(self, status: int = 0, message: Optional[str] = None) -> None:
        super().__init__(message or "")
        self.status = int(status)
        self.message = message


class _Parser(argparse.ArgumentParser):
    """ArgumentParser that reports usage errors instead of calling sys.exit.

    不直接 sys.exit 的 ArgumentParser：用法错误统一交给 main() 处理，
    便于进程内调用（测试 / agent 内嵌）拿到真实退出码。
    """

    def error(self, message: str) -> None:  # type: ignore[override]
        raise _ParseExit(2, "{}{}: error: {}\n".format(self.format_usage(), self.prog, message))

    def exit(self, status: int = 0, message: Optional[str] = None) -> None:  # type: ignore[override]
        raise _ParseExit(status, message)


# ---------------------------------------------------------------------------
# Small helpers / 小工具
# ---------------------------------------------------------------------------


def _p(text: str = "") -> None:
    """print() that degrades gracefully on a non-UTF-8 Windows console.

    在非 UTF-8 Windows 控制台上优雅降级的 print()。
    """
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        sys.stdout.write(text.encode(encoding, "replace").decode(encoding) + "\n")


def _eprint(text: str) -> None:
    """Write a line to stderr (encoding-safe). / 写一行到 stderr（编码安全）。"""
    try:
        print(text, file=sys.stderr)
    except UnicodeEncodeError:
        encoding = getattr(sys.stderr, "encoding", None) or "ascii"
        sys.stderr.write(text.encode(encoding, "replace").decode(encoding) + "\n")


def _fmt(value: Any, template: str = "%.6g") -> str:
    """Format a number with the CLI's compact ``%.6g`` convention.

    按 CLI 约定的紧凑格式（``%.6g``）格式化数值；非数值原样转字符串。
    """
    if value is None:
        return "-"
    try:
        return template % float(value)
    except (TypeError, ValueError):
        return str(value)


def _json_default(value: Any) -> Any:
    """JSON encoder fallback for numpy scalars / arrays. / numpy 标量与数组的 JSON 兜底。"""
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    return str(value)


def _dump_json(payload: Any) -> str:
    """Serialize ``payload`` as readable, non-ASCII-preserving JSON.

    以可读、保留非 ASCII 的方式序列化 JSON。
    """
    return json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default)


def _write_json(path: str, payload: Any, overwrite: bool) -> str:
    """Write ``payload`` as JSON to ``path``; returns the absolute path."""
    target = os.path.abspath(path)
    _check_output(target, overwrite)
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(_dump_json(payload) + "\n")
    return target


def _check_output(path: str, overwrite: bool) -> None:
    """Refuse to clobber an existing file unless ``--overwrite`` was given.

    除非显式 ``--overwrite``，否则拒绝覆盖已存在的文件；同时创建父目录。
    """
    if os.path.exists(path) and not overwrite:
        raise CliError("output already exists (use --overwrite): {}".format(path))
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _ensure_suffix(path: str, fmt: str) -> str:
    """Append the format's canonical suffix when ``path`` does not already carry one.

    当 ``path`` 不带该格式的规范后缀时补上（如 ``out`` + edf → ``out.edf``）。
    """
    allowed = _FORMAT_SUFFIX.get(fmt.lower(), ())
    suffix = os.path.splitext(path)[1].lower()
    if allowed and suffix not in allowed:
        return path + allowed[0]
    return path


def _normalize_ext(ext: str) -> str:
    """Normalize an output extension to a leading-dot form. / 规范输出扩展名（补前导点）。"""
    text = str(ext or "").strip()
    if not text:
        return ".xy"
    return text if text.startswith(".") else "." + text


def _expand_files(patterns: Sequence[str], must_exist: bool = True) -> List[str]:
    """Expand shell-style patterns (``*`` / ``?``) the way a POSIX shell would.

    按 POSIX shell 语义展开 ``*`` / ``?`` 通配符（Windows shell 不会展开），
    去重并保持输入顺序。
    """
    result: List[str] = []
    for raw in patterns or []:
        text = str(raw)
        if "*" in text or "?" in text:
            matches = sorted(glob.glob(text))
            if not matches:
                raise CliError("no file matches pattern: {}".format(text))
            result.extend(matches)
        else:
            result.append(text)

    unique: List[str] = []
    seen = set()
    for path in result:
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        if must_exist and not os.path.exists(path):
            raise CliError("file not found: {}".format(path))
        unique.append(path)
    if not unique:
        raise CliError("no input files given")
    return unique


def _load_image(path: str) -> Tuple[np.ndarray, Optional[np.ndarray], Dict[str, Any]]:
    """Load one detector image through ``ImageLoader``.

    通过 ``ImageLoader.load`` 读取单帧图像（HDF5 自动挑选默认图像数据集），
    解不出数据时抛出 CliError。
    """
    data, dead_mask, meta = ImageLoader.load(path)
    if data is None:
        raise CliError("no image data decoded from: {}".format(path))
    return np.asarray(data), (None if dead_mask is None else np.asarray(dead_mask)), dict(meta or {})


def _load_optional_image(path: Optional[str], label: str) -> Optional[np.ndarray]:
    """Load an optional auxiliary image (dark / flat / mask). / 读取可选的辅助图。"""
    if not path:
        return None
    try:
        data, _, _ = _load_image(path)
    except Exception as exc:  # noqa: BLE001 - re-raised as a CLI error
        raise CliError("cannot load {} image {}: {}".format(label, path, exc)) from exc
    return data


def _require_same_shape(reference: np.ndarray, other: np.ndarray, label: str) -> None:
    """Fail early with a clear message when two images cannot be combined.

    两图尺寸不一致时提前失败并给出清晰提示（避免下游 numpy 广播错误）。
    """
    if tuple(reference.shape) != tuple(other.shape):
        raise CliError(
            "{} shape {} does not match the sample shape {}".format(
                label, tuple(other.shape), tuple(reference.shape)
            )
        )


def _write_image(path: str, array: np.ndarray, fmt: str, attrs: Optional[Dict[str, Any]] = None) -> str:
    """Write a 2-D array as EDF / TIFF / HDF5 / NPY. / 把二维数组写成 EDF/TIFF/HDF5/NPY。

    EDF and TIFF go through fabio (the same reader ``ImageLoader`` uses), HDF5
    stores the frame as a ``data`` dataset with optional attributes, and NPY is
    plain numpy — so every produced file is readable by the X-FAIS stack again.
    EDF/TIFF 走 fabio（与 ``ImageLoader`` 同源读取器），HDF5 写成 ``data``
    数据集并附属性，NPY 为原生 numpy。
    """
    key = str(fmt or "").strip().lower()
    payload = np.asarray(array, dtype=np.float32)
    target = os.path.abspath(path)
    if key in ("h5", "hdf5"):
        import h5py

        with h5py.File(target, "w") as handle:
            handle.create_dataset("data", data=payload)
            for name, value in (attrs or {}).items():
                if value is None:
                    continue
                handle.attrs[str(name)] = value
    elif key == "edf":
        from fabio.edfimage import EdfImage

        EdfImage(data=payload).write(target)
    elif key in ("tif", "tiff"):
        from fabio.tifimage import TifImage

        TifImage(data=payload).write(target)
    elif key == "npy":
        np.save(target, payload)
    else:
        raise CliError("unsupported output format: {}".format(fmt))
    return target


def _read_curve(path: str) -> Tuple[np.ndarray, np.ndarray]:
    """Read a two-column (x, y) text curve.

    读取两列（x, y）文本曲线：空白或逗号分隔，``#``/``;`` 开头的注释行与
    无法解析为数字的行会被跳过。
    """
    rows: List[Tuple[float, float]] = []
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            for line in handle:
                text = line.strip()
                if not text or text.startswith("#") or text.startswith(";"):
                    continue
                fields = text.replace("\t", " ").replace(",", " ").replace(";", " ").split()
                if len(fields) < 2:
                    continue
                try:
                    x = float(fields[0])
                    y = float(fields[1])
                except ValueError:
                    continue
                rows.append((x, y))
    except OSError as exc:
        raise CliError("cannot read curve {}: {}".format(path, exc)) from exc
    if len(rows) < 3:
        raise CliError(
            "curve needs at least 3 numeric two-column rows: {}".format(path)
        )
    array = np.asarray(rows, dtype=np.float64)
    return array[:, 0], array[:, 1]


def _parse_region(text: str) -> Dict[str, Any]:
    """Parse ``rect:x0,y0,x1,y1`` (also accepts ``poly:x0,y0;x1,y1;...``).

    解析 ``--region``：主用法 ``rect:x0,y0,x1,y1``；另外支持
    ``poly:x0,y0;x1,y1;...``（x 为列、y 为行，与图像坐标一致）。
    """
    if not isinstance(text, str) or not text.strip():
        raise CliError("--region is required, e.g. rect:x0,y0,x1,y1")
    raw = text.strip()
    head, _, body = raw.partition(":")
    kind = head.strip().lower()
    if kind == "rect":
        fields = [item for item in re.split(r"[,\s]+", body.strip()) if item]
        if len(fields) != 4:
            raise CliError("rect region needs 4 numbers: rect:x0,y0,x1,y1")
        try:
            x0, y0, x1, y1 = (float(item) for item in fields)
        except ValueError as exc:
            raise CliError("rect region contains a non-numeric value: {}".format(raw)) from exc
        return {"kind": "rect", "x0": x0, "y0": y0, "x1": x1, "y1": y1}
    if kind == "poly":
        points: List[List[float]] = []
        for chunk in [item for item in re.split(r"[;]+", body.strip()) if item.strip()]:
            pair = [item for item in re.split(r"[,\s]+", chunk.strip()) if item]
            if len(pair) != 2:
                raise CliError("polygon vertex must be x,y: {}".format(chunk))
            try:
                px, py = float(pair[0]), float(pair[1])
            except ValueError as exc:
                raise CliError("polygon vertex contains a non-numeric value: {}".format(chunk)) from exc
            points.append([py, px])
        return {"kind": "poly", "points": points}
    raise CliError("--region must be rect:x0,y0,x1,y1 (or poly:x0,y0;x1,y1;...)")


def _resolve_reference(reference: Optional[str], rows: Sequence[Dict[str, Any]]) -> str:
    """Resolve ``--reference first|last|<file>`` to one row's ``file`` value.

    把 ``--reference first|last|<文件名>`` 解析为某一行的 ``file`` 值。
    """
    if not rows:
        raise CliError("no rows to reference")
    token = (reference or "first").strip()
    lowered = token.lower()
    if lowered == "first":
        return str(rows[0]["file"])
    if lowered == "last":
        return str(rows[-1]["file"])
    wanted_full = os.path.normcase(os.path.abspath(token))
    for row in rows:
        candidate = str(row.get("file", ""))
        if candidate == token:
            return candidate
        if os.path.basename(candidate) == token:
            return candidate
        if os.path.normcase(os.path.abspath(candidate)) == wanted_full:
            return candidate
    raise CliError("reference file is not among the inputs: {}".format(token))


def _find_ion_files(folder: str) -> List[str]:
    """Collect ionchamber files inside ``--ion-folder``. / 收集 ``--ion-folder`` 内的电离室文件。"""
    if not os.path.isdir(folder):
        raise CliError("ion folder does not exist: {}".format(folder))
    found: List[str] = []
    for entry in sorted(os.listdir(folder)):
        full = os.path.join(folder, entry)
        if not os.path.isfile(full):
            continue
        if os.path.splitext(entry)[1].lower() in _ION_EXTENSIONS:
            found.append(full)
    if not found:
        raise CliError(
            "no ionchamber files (*{}) found in: {}".format(
                ", *".join(_ION_EXTENSIONS), folder
            )
        )
    return found


def _package_version() -> str:
    """Read the X-FAIS version from ``BETA/package.json`` (best effort).

    从 ``BETA/package.json`` 读取应用版本号（读不到时返回 ``unknown``）。
    """
    path = os.path.join(os.path.dirname(_HERE), "package.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return str(payload.get("version") or "unknown")
    except Exception:  # noqa: BLE001 - version reporting must never fail
        return "unknown"


def _module_version(name: str) -> Optional[str]:
    """Return an installed module's version string, or None. / 返回模块版本号。"""
    try:
        module = __import__(name)
    except Exception:  # noqa: BLE001 - optional dependency
        return None
    for attribute in ("version", "__version__", "VERSION"):
        value = getattr(module, attribute, None)
        if isinstance(value, str) and value:
            return value
    return None


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------


def cmd_info(ns: argparse.Namespace) -> int:
    """Probe image files: format, shape, dtype, min/max/mean.

    逐文件探测：格式、形状、dtype、最小值/最大值/均值（以及帧数与死像素数）。
    """
    files = _expand_files(ns.files, must_exist=False)
    rows: List[Dict[str, Any]] = []
    failures = 0

    for path in files:
        try:
            data, dead_mask, meta = _load_image(path)
            values = np.asarray(data, dtype=np.float64)
            with np.errstate(invalid="ignore"):
                row: Dict[str, Any] = {
                    "file": path,
                    "name": os.path.basename(path),
                    "format": str(meta.get("ext") or os.path.splitext(path)[1]).lstrip(".").upper(),
                    "shape": [int(dim) for dim in np.shape(data)],
                    "dtype": str(np.asarray(data).dtype),
                    "min": float(np.nanmin(values)) if values.size else None,
                    "max": float(np.nanmax(values)) if values.size else None,
                    "mean": float(np.nanmean(values)) if values.size else None,
                }
            if dead_mask is not None:
                row["dead_pixels"] = int(np.count_nonzero(dead_mask))
            if meta.get("n_frames") is not None:
                row["n_frames"] = int(meta["n_frames"])
            if meta.get("h5_dataset"):
                row["h5_dataset"] = str(meta["h5_dataset"])
            rows.append(row)
        except Exception as exc:  # noqa: BLE001 - one bad file must not hide the rest
            failures += 1
            _eprint("xfais-cli: error: {}: {}".format(path, exc))

    if ns.json:
        _p(_dump_json(rows))
        return 1 if failures else 0

    for row in rows:
        shape = "x".join(str(dim) for dim in row["shape"])
        line = "{:<32} {:<6} {:<14} {:<9} min={} max={} mean={}".format(
            row["name"],
            row["format"],
            shape,
            row["dtype"],
            _fmt(row.get("min")),
            _fmt(row.get("max")),
            _fmt(row.get("mean")),
        )
        extras = []
        if "n_frames" in row:
            extras.append("frames={}".format(row["n_frames"]))
        if "dead_pixels" in row:
            extras.append("dead={}".format(row["dead_pixels"]))
        if row.get("h5_dataset"):
            extras.append("dataset={}".format(row["h5_dataset"]))
        if extras:
            line += "  " + "  ".join(extras)
        _p(line)
    return 1 if failures else 0


# ---------------------------------------------------------------------------
# poni
# ---------------------------------------------------------------------------


def cmd_poni(ns: argparse.Namespace) -> int:
    """Print a PONI geometry summary (dist, center, rotations, wavelength, detector).

    打印 PONI 几何摘要：距离、中心、三个旋转角、波长/能量、探测器与像素尺寸。
    """
    poni_path = str(ns.ponifile)
    if not os.path.exists(poni_path):
        raise CliError("PONI file not found: {}".format(poni_path))
    ai, center_x, center_y = IntegratorFactory.from_poni_path(poni_path)
    if ai is None:
        raise CliError("failed to build an integrator from: {}".format(poni_path))

    wavelength_m = ai.wavelength
    pixel1_m = ai.pixel1
    pixel2_m = ai.pixel2
    detector = getattr(ai, "detector", None)
    detector_name = getattr(detector, "name", None) if detector is not None else None
    detector_pixel1 = getattr(detector, "pixel1", None) if detector is not None else None
    detector_pixel2 = getattr(detector, "pixel2", None) if detector is not None else None

    wavelength_a = float(wavelength_m) * 1.0e10 if wavelength_m else None
    energy_kev = HC_KEV_ANGSTROM / wavelength_a if wavelength_a else None

    info: Dict[str, Any] = {
        "file": os.path.abspath(poni_path),
        "dist_mm": float(ai.dist) * 1.0e3,
        "poni1_mm": float(ai.poni1) * 1.0e3,
        "poni2_mm": float(ai.poni2) * 1.0e3,
        "rot1_deg": float(np.degrees(ai.rot1)),
        "rot2_deg": float(np.degrees(ai.rot2)),
        "rot3_deg": float(np.degrees(ai.rot3)),
        "wavelength_A": wavelength_a,
        "energy_keV": energy_kev,
        "detector": detector_name,
        "pixel1_um": (float(pixel1_m) * 1.0e6) if pixel1_m else None,
        "pixel2_um": (float(pixel2_m) * 1.0e6) if pixel2_m else None,
        "center_x_px": None if center_x is None else float(center_x),
        "center_y_px": None if center_y is None else float(center_y),
    }
    if detector_pixel1 is not None and detector_pixel2 is not None:
        info["detector_pixel_um"] = [
            float(detector_pixel1) * 1.0e6,
            float(detector_pixel2) * 1.0e6,
        ]

    if ns.json:
        _p(_dump_json(info))
        return 0

    _p("PONI: {}".format(info["file"]))
    _p("  detector   : {}".format(info["detector"] or "unknown"))
    _p("  dist       : {} mm".format(_fmt(info["dist_mm"])))
    _p("  poni1      : {} mm".format(_fmt(info["poni1_mm"])))
    _p("  poni2      : {} mm".format(_fmt(info["poni2_mm"])))
    _p(
        "  rot1/2/3   : {} / {} / {} deg".format(
            _fmt(info["rot1_deg"]), _fmt(info["rot2_deg"]), _fmt(info["rot3_deg"])
        )
    )
    _p("  wavelength : {} A".format(_fmt(info["wavelength_A"])))
    _p("  energy     : {} keV".format(_fmt(info["energy_keV"])))
    _p("  pixel      : {} x {} um".format(_fmt(info["pixel1_um"]), _fmt(info["pixel2_um"])))
    _p(
        "  center     : {} x {} px".format(
            _fmt(info["center_x_px"]), _fmt(info["center_y_px"])
        )
    )
    return 0


# ---------------------------------------------------------------------------
# average
# ---------------------------------------------------------------------------


def cmd_average(ns: argparse.Namespace) -> int:
    """Average / stack detector images with optional dark and flat correction.

    多图平均/求和：可先逐一扣暗场（--dark）、再逐个除以平场（--flat），
    与 pyFAI-average 的 ``(image - dark) / flat`` 语义一致。
    """
    files = _expand_files(ns.files)

    frames: List[np.ndarray] = []
    for path in files:
        try:
            data, _, _ = _load_image(path)
        except CliError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CliError("cannot load {}: {}".format(path, exc)) from exc
        frames.append(np.asarray(data, dtype=np.float32))

    shapes = {tuple(frame.shape) for frame in frames}
    if len(shapes) > 1:
        listed = ", ".join("{}:{}".format(os.path.basename(f), "x".join(map(str, s))) for f, s in zip(files, (f.shape for f in frames)))
        raise CliError("input image shapes differ — cannot stack ({})".format(listed))

    stack = np.stack(frames, axis=0)

    dark = _load_optional_image(ns.dark, "dark")
    if dark is not None:
        _require_same_shape(stack[0], dark, "dark")
        stack = stack - np.asarray(dark, dtype=np.float32)

    flat = _load_optional_image(ns.flat, "flat")
    if flat is not None:
        _require_same_shape(stack[0], flat, "flat")
        # pyFAI-average guards non-positive flat pixels by using 1.0 there.
        # 与 pyFAI-average 一致：非正平场像素以 1.0 处理，避免除零/负值翻转。
        flat_values = np.asarray(flat, dtype=np.float32)
        flat_values = np.where(flat_values <= 0, np.float32(1.0), flat_values)
        stack = stack / flat_values

    mode = str(ns.mode).lower()
    if mode == "mean":
        result = np.mean(stack, axis=0, dtype=np.float64)
    elif mode == "median":
        result = np.median(stack, axis=0)
    elif mode == "min":
        result = np.min(stack, axis=0)
    elif mode == "max":
        result = np.max(stack, axis=0)
    elif mode == "sum":
        result = np.sum(stack, axis=0, dtype=np.float64)
    else:  # pragma: no cover - argparse choices already restrict this
        raise CliError("unsupported mode: {}".format(ns.mode))

    output = _ensure_suffix(str(ns.output), ns.fmt)
    _check_output(os.path.abspath(output), ns.overwrite)
    written = _write_image(output, result.astype(np.float32), ns.fmt)

    _p(
        "{} files -> {}  mode={}  shape={}x{}".format(
            len(files), written, mode, result.shape[0], result.shape[1]
        )
    )
    return 0


# ---------------------------------------------------------------------------
# integrate
# ---------------------------------------------------------------------------


def cmd_integrate(ns: argparse.Namespace) -> int:
    """Azimuthal 1-D integration of every input image through its PONI geometry.

    逐文件一维积分：读取 PONI 几何 → ``ai.integrate1d`` → 输出
    ``<stem><ext>`` 纯文本列文件（径向轴 + 强度 + 可选 sigma）。
    """
    files = _expand_files(ns.files)

    poni_path = str(ns.poni)
    if not os.path.exists(poni_path):
        raise CliError("PONI file not found: {}".format(poni_path))
    ai, _, _ = IntegratorFactory.from_poni_path(poni_path)
    if ai is None:
        raise CliError("failed to build an integrator from: {}".format(poni_path))

    npt = int(ns.npt)
    if npt < 2:
        raise CliError("--npt must be >= 2 (got {})".format(npt))

    unit = str(ns.unit)
    if unit not in INTEGRATION_UNITS:
        raise CliError(
            "unsupported --unit {} (choose from {})".format(unit, ", ".join(INTEGRATION_UNITS))
        )

    extension = _normalize_ext(ns.ext)

    mask_values = _load_optional_image(ns.mask, "mask")
    mask = None if mask_values is None else np.asarray(mask_values) != 0
    dark = _load_optional_image(ns.dark, "dark")
    flat = _load_optional_image(ns.flat, "flat")

    error_model = str(ns.error_model).lower()
    if error_model not in ("poisson", "none"):
        raise CliError("unsupported --error-model {} (poisson|none)".format(ns.error_model))

    written_targets: Dict[str, str] = {}
    axis_label = UNIT_LABELS.get(unit, unit)

    for path in files:
        data, _, _ = _load_image(path)
        if data.ndim > 2:
            data = data[0]
        if data.ndim != 2:
            raise CliError("expected a 2-D image, got shape {} in {}".format(tuple(data.shape), path))

        kwargs: Dict[str, Any] = {"unit": unit}
        if mask is not None:
            kwargs["mask"] = mask
        if dark is not None:
            kwargs["dark"] = np.asarray(dark, dtype=np.float32)
        if flat is not None:
            kwargs["flat"] = np.asarray(flat, dtype=np.float32)
        if error_model == "poisson":
            kwargs["error_model"] = "poisson"

        try:
            result = ai.integrate1d(np.asarray(data, dtype=np.float32), npt, **kwargs)
        except Exception as exc:  # noqa: BLE001 - surface pyFAI wording to the user
            raise CliError("integration failed for {}: {}".format(path, exc)) from exc

        radial = np.asarray(result[0], dtype=np.float64)
        intensity = np.asarray(result[1], dtype=np.float64)
        sigma = np.asarray(result[2], dtype=np.float64) if len(result) > 2 else None
        if radial.size != npt or intensity.size != npt:
            raise CliError(
                "integration returned {} points, expected {} for {}".format(
                    radial.size, npt, path
                )
            )

        out_dir = str(ns.outdir) if ns.outdir else (os.path.dirname(os.path.abspath(path)) or os.getcwd())
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0]
        target = os.path.abspath(os.path.join(out_dir, stem + extension))
        if target in written_targets:
            raise CliError(
                "two inputs map to the same output {}: {} and {}".format(
                    target, written_targets[target], path
                )
            )
        written_targets[target] = path
        _check_output(target, ns.overwrite)

        header = [
            "# xfais-cli integrate (pyFAI-style)",
            "# poni: {}".format(os.path.abspath(poni_path)),
            "# source: {}".format(os.path.abspath(path)),
            "# unit: {} ({})".format(unit, axis_label),
            "# npt: {}".format(npt),
            "# columns: {}".format(
                "radial intensity sigma" if sigma is not None else "radial intensity"
            ),
        ]
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(header) + "\n")
            for index in range(npt):
                fields = [_fmt(radial[index]), _fmt(intensity[index])]
                if sigma is not None:
                    fields.append(_fmt(sigma[index]))
                handle.write(" ".join(fields) + "\n")

        _p("{} -> {}  ({} points, unit={})".format(path, target, npt, unit))

    return 0


# ---------------------------------------------------------------------------
# bgsubtract
# ---------------------------------------------------------------------------


def cmd_bgsubtract(ns: argparse.Namespace) -> int:
    """Batch reference-background subtraction with optional ionchamber transmission.

    批量扣除参考背景：``result = sample / T - background``。T 的来源按优先级：
    电离室匹配（--ion-folder，必要时用 --bg-ion 指定背景电离室）→ 手动百分比
    （-T）→ 1.0。
    """
    files = _expand_files(ns.files)

    if not ns.bg:
        raise CliError("-b/--bg is required: a reference background image")
    if not os.path.exists(str(ns.bg)):
        raise CliError("background image not found: {}".format(ns.bg))
    background, _, _ = _load_image(str(ns.bg))

    if ns.bg_ion and not ns.ion_folder:
        raise CliError("--bg-ion requires --ion-folder (per-file ionchamber matching)")

    ion_files: List[str] = []
    background_ion = None
    matches: List[Dict[str, Any]] = []

    if ns.ion_folder:
        ion_files = _find_ion_files(str(ns.ion_folder))
        if ns.bg_ion:
            if not os.path.exists(str(ns.bg_ion)):
                raise CliError("background ionchamber file not found: {}".format(ns.bg_ion))
            background_ion = parse_ionchamber_file(str(ns.bg_ion))
            if background_ion is None:
                raise CliError("cannot parse background ionchamber file: {}".format(ns.bg_ion))
        else:
            background_match = match_ionchamber([str(ns.bg)], ion_files)[0]
            matched = background_match.get("matched_ion")
            if matched:
                background_ion = parse_ionchamber_file(str(matched))
                if background_ion is not None:
                    _p(
                        "# background ionchamber: {} ({}, score {})".format(
                            os.path.basename(str(matched)),
                            background_match.get("method"),
                            _fmt(background_match.get("score")),
                        )
                    )
            if background_ion is None:
                _eprint(
                    "xfais-cli: warning: no ionchamber matched the background image; "
                    "transmission falls back to -T / 1.0"
                )
        matches = match_ionchamber(files, ion_files)

    manual = None
    if ns.transmission is not None:
        manual = float(ns.transmission) / 100.0
        if manual <= 0:
            raise CliError("-T/--transmission percent must be > 0")

    fmt = str(ns.fmt).lower()
    out_suffix = _FORMAT_SUFFIX.get(fmt, (".h5",))[0]

    for index, path in enumerate(files):
        sample, _, _ = _load_image(path)

        transmission: Optional[float] = None
        source = "none"
        note = ""

        if background_ion is not None and matches:
            matched = matches[index].get("matched_ion") if index < len(matches) else None
            if matched:
                sample_ion = parse_ionchamber_file(str(matched))
                if sample_ion is not None:
                    try:
                        transmission = float(
                            calc_transmission(
                                sample_ion,
                                background_ion,
                                channel=str(ns.ion_channel),
                                method=str(ns.ion_method),
                            )
                        )
                        source = "ionchamber"
                        note = os.path.basename(str(matched))
                    except ValueError as exc:
                        _eprint(
                            "xfais-cli: warning: {}: {}".format(path, exc)
                        )
            if transmission is None:
                note = "no ionchamber match"

        if transmission is None and manual is not None:
            transmission = manual
            source = "manual"

        if transmission is None:
            transmission = 1.0
            source = "default"

        if transmission <= 0:
            raise CliError(
                "transmission must be > 0 for {} (got {})".format(path, transmission)
            )

        corrected = subtract_with_reference(sample, background, transmission)

        out_dir = str(ns.outdir) if ns.outdir else (os.path.dirname(os.path.abspath(path)) or os.getcwd())
        os.makedirs(out_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(path))[0]
        target = os.path.abspath(os.path.join(out_dir, stem + "_bgsub" + out_suffix))
        _check_output(target, ns.overwrite)

        attrs = {
            "source": os.path.abspath(path),
            "background": os.path.abspath(str(ns.bg)),
            "transmission": float(transmission),
            "transmission_source": source,
            "ionchamber": note or None,
        }
        _write_image(target, corrected, fmt, attrs=attrs)

        _p(
            "{}  T={} ({}{})  -> {}".format(
                os.path.basename(path),
                _fmt(transmission),
                source,
                ", " + note if note else "",
                target,
            )
        )

    return 0


# ---------------------------------------------------------------------------
# transmission
# ---------------------------------------------------------------------------


def cmd_transmission(ns: argparse.Namespace) -> int:
    """Direct-beam transmission from a fixed region: I / I_reference per file.

    直通光透过率：对每张图在固定区域（矩形/多折框）内求和，再除以参考图的
    积分强度得到逐文件透过率。
    """
    files = _expand_files(ns.files)
    region = _parse_region(str(ns.region))

    # Fail fast with the service's own bilingual validation message.
    # 先用服务自身的校验做一次结构检查，错误信息与应用内完全一致。
    validate_region(region)

    rows: List[Dict[str, Any]] = []
    for path in files:
        data, _, _ = _load_image(path)
        try:
            stats = region_pixel_sum(data, region)
        except Exception as exc:  # noqa: BLE001
            raise CliError("region integral failed for {}: {}".format(path, exc)) from exc
        rows.append(
            {
                "file": path,
                "name": os.path.basename(path),
                "intensity": float(stats["total"]),
                "pixel_count": int(stats["pixel_count"]),
                "mean": float(stats["mean"]),
            }
        )

    reference = _resolve_reference(ns.reference, rows)
    try:
        rows = compute_transmission_rows(rows, reference)
    except ValueError as exc:
        raise CliError(str(exc)) from exc

    if ns.csv:
        written = export_transmission_csv(rows, str(ns.csv))
        _eprint("xfais-cli: wrote CSV {}".format(written))

    if ns.json:
        payload = [
            {
                "file": row.get("file"),
                "name": row.get("name"),
                "intensity": row.get("intensity"),
                "transmission": row.get("transmission"),
                "pixel_count": row.get("pixel_count"),
            }
            for row in rows
        ]
        _p(_dump_json(payload))
        return 0

    _p(
        "{:<32} {:>16} {:>14} {:>8}".format("file", "intensity", "transmission", "pixels")
    )
    for row in rows:
        _p(
            "{:<32} {:>16} {:>14} {:>8}".format(
                str(row.get("name") or row.get("file")),
                _fmt(row.get("intensity")),
                _fmt(row.get("transmission")),
                int(row.get("pixel_count") or 0),
            )
        )
    _p("# reference: {}".format(os.path.basename(reference)))
    return 0


# ---------------------------------------------------------------------------
# lamellar
# ---------------------------------------------------------------------------


def _strip_array_values(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Drop long list/tuple values so a summary stays compact. / 去掉长数组让摘要保持紧凑。"""
    return {key: value for key, value in payload.items() if not isinstance(value, (list, tuple))}


def cmd_lamellar(ns: argparse.Namespace) -> int:
    """Lamellar (Strobl–Schneider) analysis of a 1-D SAXS profile → JSON.

    片晶一维相关函数分析：读两列 q/I 曲线 → ``analyze_lamellar`` → JSON。
    默认输出紧凑摘要（结果 + 质量 + 警告），``--json`` 输出含全部中间曲线的
    完整报告，``--out`` 落盘完整报告。
    """
    q, intensity = _read_curve(str(ns.curve))

    # No-`-porod` options are omitted rather than passed as None: the service
    # reads them with dict.get(...) + float(), and an explicit None would raise.
    # 未给出的 porod 选项必须省略而不是传 None：服务端用 dict.get(...)+float() 读取，
    # 显式 None 会抛 TypeError。
    porod_options: Dict[str, Any] = {"enabled": not bool(ns.no_porod)}
    if ns.porod_fraction is not None:
        porod_options["fit_fraction"] = float(ns.porod_fraction)
    if ns.porod_ext is not None:
        porod_options["ext_factor"] = float(ns.porod_ext)

    options: Dict[str, Any] = {
        "q_unit": str(ns.q_unit),
        "q_min": ns.qmin,
        "q_max": ns.qmax,
        "background": {"mode": str(ns.background), "constant": ns.bg_constant},
        "minority_phase": str(ns.minority_phase),
        "correlation": {"r_max_nm": ns.r_max},
        "porod": porod_options,
        "tangent": {"fit_min_nm": ns.tangent_min, "fit_max_nm": ns.tangent_max},
    }

    try:
        report = analyze_lamellar(q, intensity, **options)
    except ValueError as exc:
        raise CliError(str(exc)) from exc
    if not isinstance(report, dict):
        raise CliError("lamellar analysis returned no report")

    payload: Dict[str, Any] = {"file": os.path.abspath(str(ns.curve))}
    payload.update(report)

    if ns.out:
        written = _write_json(str(ns.out), payload, ns.overwrite)
        _eprint("xfais-cli: wrote report {}".format(written))

    if ns.json:
        _p(_dump_json(payload))
        return 0

    summary: Dict[str, Any] = {"file": payload["file"]}
    for key in ("quality", "results", "warnings"):
        if key in payload:
            summary[key] = payload[key]
    for key in ("background", "porod", "tangent"):
        value = payload.get(key)
        if isinstance(value, dict):
            summary[key] = _strip_array_values(value)
        elif value is not None:
            summary[key] = value
    _p(_dump_json(summary))
    return 0


# ---------------------------------------------------------------------------
# orientation
# ---------------------------------------------------------------------------


def cmd_orientation(ns: argparse.Namespace) -> int:
    """Azimuthal orientation analysis of an I(χ) curve → JSON.

    方位角取向分析：读 χ/I 两列曲线 → Hermans 取向函数和/或 FWHM 取向指数 → JSON。
    """
    chi, intensity = _read_curve(str(ns.curve))
    method = str(ns.method).lower()
    if method not in ("hermans", "fwhm", "both"):
        raise CliError("unsupported --method {} (hermans|fwhm|both)".format(ns.method))

    payload: Dict[str, Any] = {
        "file": os.path.abspath(str(ns.curve)),
        "method": method,
        "n_points": int(chi.size),
        "chi_min": float(np.min(chi)),
        "chi_max": float(np.max(chi)),
    }

    if method in ("hermans", "both"):
        try:
            result, meta = hermans_orientation(
                chi,
                intensity,
                chi_zero=str(ns.chi_zero),
                equatorial_to_chain=not bool(ns.no_equatorial_to_chain),
                reference_chi_deg=ns.reference_chi,
            )
        except ValueError as exc:
            raise CliError(str(exc)) from exc
        entry = dict(result)
        entry["meta"] = meta if ns.json else _strip_array_values(meta)
        payload["hermans"] = entry

    if method in ("fwhm", "both"):
        result, meta = fwhm_orientation_index(
            chi, intensity, peak_window=ns.peak_window
        )
        entry = dict(result)
        entry["meta"] = meta if ns.json else _strip_array_values(meta)
        payload["fwhm"] = entry

    _p(_dump_json(payload))
    return 0


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


def cmd_version(ns: argparse.Namespace) -> int:
    """Print xfais-cli / X-FAIS / python / numpy / pyFAI versions.

    打印 xfais-cli、X-FAIS 应用、python、numpy、pyFAI（以及 fabio/h5py）版本。
    """
    info: Dict[str, Any] = {
        "cli": __version__,
        "xfais": _package_version(),
        "python": "{}.{}.{}".format(*sys.version_info[:3]),
        "numpy": np.__version__,
        "pyFAI": _module_version("pyFAI"),
        "fabio": _module_version("fabio"),
        "h5py": _module_version("h5py"),
    }

    if ns.json:
        _p(_dump_json(info))
        return 0

    _p("{:<10} {}".format("xfais-cli", info["cli"]))
    _p("{:<10} {}".format("X-FAIS", info["xfais"]))
    _p("{:<10} {}".format("python", info["python"]))
    _p("{:<10} {}".format("numpy", info["numpy"]))
    _p("{:<10} {}".format("pyFAI", info["pyFAI"] or "not installed"))
    _p("{:<10} {}".format("fabio", info["fabio"] or "not installed"))
    _p("{:<10} {}".format("h5py", info["h5py"] or "not installed"))
    return 0


# ---------------------------------------------------------------------------
# Argument parser / 参数解析
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the full argparse tree (bilingual help). / 构建完整参数树（双语帮助）。"""
    parser = _Parser(
        prog="xfais-cli",
        description=(
            "X-FAIS analysis command line interface, pyFAI-style subcommands.\n"
            "X-FAIS 分析命令行接口，采用 pyFAI 风格子命令。\n\n"
            "All results go to stdout; errors go to stderr with a non-zero exit code.\n"
            "结果写 stdout；错误写 stderr 并返回非 0 退出码。"
        ),
        epilog=(
            "examples / 示例:\n"
            "  xfais-cli info *.edf --json\n"
            "  xfais-cli poni calib.poni\n"
            "  xfais-cli average -o dark.edf -m median dark_*.edf\n"
            "  xfais-cli integrate -p calib.poni -n 2048 --unit q_nm^-1 -o out *.edf\n"
            "  xfais-cli bgsubtract -b bg.edf -T 50 -o out/ *.edf\n"
            "  xfais-cli transmission *.edf --region rect:900,900,1100,1100 --csv T.csv\n"
            "  xfais-cli lamellar curve.txt --json\n"
            "  xfais-cli orientation chi.txt --method both\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version="xfais-cli {}".format(__version__),
        help="打印 CLI 版本并退出 / print the CLI version and exit",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # -- info ---------------------------------------------------------------
    info = subparsers.add_parser(
        "info",
        help="逐文件探测格式/形状/最值 / probe format, shape, min/max/mean per file",
        description=(
            "Probe image files: format, shape, dtype, min/max/mean.\n"
            "逐文件探测：格式、形状、dtype、最小值/最大值/均值。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    info.add_argument("files", nargs="+", metavar="FILES", help="图像文件，支持 * 与 ? / image files, * and ? are expanded")
    info.add_argument("--json", action="store_true", help="输出 JSON / emit JSON")
    info.set_defaults(func=cmd_info)

    # -- poni ---------------------------------------------------------------
    poni = subparsers.add_parser(
        "poni",
        help="打印 PONI 几何摘要 / print a PONI geometry summary",
        description=(
            "Print the geometry stored in a PONI file: distance, center, rotations,\n"
            "wavelength/energy, detector and pixel size.\n"
            "打印 PONI 文件中的几何：距离、中心、旋转角、波长/能量、探测器与像素尺寸。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    poni.add_argument("ponifile", metavar="PONIFILE", help="PONI 标定文件 / PONI calibration file")
    poni.add_argument("--json", action="store_true", help="输出 JSON / emit JSON")
    poni.set_defaults(func=cmd_poni)

    # -- average ------------------------------------------------------------
    average = subparsers.add_parser(
        "average",
        help="多图平均/求和（可扣暗场/平场）/ average or stack images (dark/flat aware)",
        description=(
            "Average or stack detector images, pyFAI-average semantics:\n"
            "(image - dark) / flat, then mean/median/min/max/sum over the stack.\n"
            "多图平均/求和（对齐 pyFAI-average）：先 (图 - 暗场) / 平场，再按模式叠加。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    average.add_argument("files", nargs="+", metavar="FILES", help="输入图像，支持 * 与 ? / input images, * and ? are expanded")
    average.add_argument("-o", "--output", required=True, metavar="OUT", help="输出文件 / output file")
    average.add_argument(
        "-m",
        "--mode",
        default="mean",
        choices=list(AVERAGE_MODES),
        help="叠加模式（默认 mean）/ stacking mode (default: mean)",
    )
    average.add_argument(
        "-F",
        "--format",
        dest="fmt",
        default="edf",
        choices=["edf", "tif", "npy"],
        help="输出格式（默认 edf）/ output format (default: edf)",
    )
    average.add_argument("--dark", metavar="F", default=None, help="暗场图（先扣）/ dark image (subtracted first)")
    average.add_argument("--flat", metavar="F", default=None, help="平场图（后除）/ flat image (divided after)")
    average.add_argument("--overwrite", action="store_true", help="允许覆盖已有输出 / overwrite existing output")
    average.set_defaults(func=cmd_average)

    # -- integrate ----------------------------------------------------------
    integrate = subparsers.add_parser(
        "integrate",
        help="逐文件一维积分输出 xy / azimuthal 1-D integration to text columns",
        description=(
            "Azimuthal 1-D integration per file; writes <stem><ext> text columns with\n"
            "a commented header (poni/unit/npt/source), pyFAI-waxs naming convention.\n"
            "逐文件一维积分；按 pyFAI-waxs 约定输出 <stem><ext> 文本列文件，\n"
            "表头以 # 注明 poni/单位/点数/源文件。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    integrate.add_argument("files", nargs="+", metavar="FILES", help="输入图像，支持 * 与 ? / input images, * and ? are expanded")
    integrate.add_argument("-p", "--poni", required=True, metavar="PONI", help="PONI 标定文件 / PONI calibration file")
    integrate.add_argument("-n", "--npt", type=int, default=2048, metavar="NPT", help="径向点数（默认 2048）/ radial bins (default: 2048)")
    integrate.add_argument(
        "--unit",
        default="q_nm^-1",
        choices=list(INTEGRATION_UNITS),
        help="径向单位（默认 q_nm^-1）/ radial unit (default: q_nm^-1)",
    )
    integrate.add_argument("--ext", default=".xy", metavar="EXT", help="输出扩展名（默认 .xy）/ output extension (default: .xy)")
    integrate.add_argument("--mask", metavar="F", default=None, help="掩膜图（非零=屏蔽）/ mask image (non-zero = masked)")
    integrate.add_argument("--dark", metavar="F", default=None, help="暗场图 / dark image")
    integrate.add_argument("--flat", metavar="F", default=None, help="平场图 / flat image")
    integrate.add_argument(
        "--error-model",
        default="none",
        choices=["poisson", "none"],
        help="误差模型（默认 none）/ error model (default: none)",
    )
    integrate.add_argument("-o", "--outdir", metavar="OUTDIR", default=None, help="输出目录（默认输入文件所在目录）/ output directory (default: input directory)")
    integrate.add_argument("--overwrite", action="store_true", help="允许覆盖已有输出 / overwrite existing output")
    integrate.set_defaults(func=cmd_integrate)

    # -- bgsubtract ---------------------------------------------------------
    bgsubtract = subparsers.add_parser(
        "bgsubtract",
        help="批量扣参考背景 / batch reference background subtraction",
        description=(
            "Batch reference-background subtraction: result = sample / T - background.\n"
            "T comes from ionchamber matching (--ion-folder) > manual -T percent > 1.0.\n"
            "批量扣参考背景：result = sample / T - background。\n"
            "T 的优先级：电离室匹配（--ion-folder）> 手动 -T 百分比 > 1.0。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    bgsubtract.add_argument("files", nargs="+", metavar="FILES", help="样品图像，支持 * 与 ? / sample images, * and ? are expanded")
    bgsubtract.add_argument("-b", "--bg", required=True, metavar="BG", help="参考背景图 / reference background image")
    bgsubtract.add_argument("-T", "--transmission", type=float, default=None, metavar="PERCENT", help="手动透过率百分比，如 50 / manual transmission percent, e.g. 50")
    bgsubtract.add_argument("--ion-folder", default=None, metavar="DIR", help="电离室文件目录 / directory with ionchamber files")
    bgsubtract.add_argument("--bg-ion", default=None, metavar="F", help="背景图对应电离室文件 / ionchamber file of the background")
    bgsubtract.add_argument("--ion-channel", default="Ionchamber0", choices=["Ionchamber0", "Ionchamber1", "Ionchamber2"], help="电离室通道（默认 Ionchamber0）/ ionchamber channel")
    bgsubtract.add_argument("--ion-method", default="median", choices=["median", "mean", "trimmed_mean"], help="强度统计方式（默认 median）/ intensity statistic")
    bgsubtract.add_argument("-o", "--outdir", default=None, metavar="OUTDIR", help="输出目录（默认输入文件所在目录）/ output directory")
    bgsubtract.add_argument("--format", dest="fmt", default="h5", choices=["h5", "edf", "tif"], help="输出格式（默认 h5）/ output format (default: h5)")
    bgsubtract.add_argument("--overwrite", action="store_true", help="允许覆盖已有输出 / overwrite existing output")
    bgsubtract.set_defaults(func=cmd_bgsubtract)

    # -- transmission -------------------------------------------------------
    transmission = subparsers.add_parser(
        "transmission",
        help="直通光区域求和算透过率 / direct-beam transmission from a region",
        description=(
            "Sum a fixed region on every image and divide by the reference image:\n"
            "transmission = I / I_reference. Region syntax: rect:x0,y0,x1,y1\n"
            "(or poly:x0,y0;x1,y1;...).\n"
            "对每张图在固定区域求和后除以参考图：transmission = I / I_reference。\n"
            "区域写法：rect:x0,y0,x1,y1（或 poly:x0,y0;x1,y1;...）。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    transmission.add_argument("files", nargs="+", metavar="FILES", help="图像文件，支持 * 与 ? / image files, * and ? are expanded")
    transmission.add_argument("--region", required=True, metavar="REGION", help="矩形区域 rect:x0,y0,x1,y1 / rect region")
    transmission.add_argument("--reference", default="first", metavar="REF", help="参考图 first|last|<文件名>（默认 first）/ reference first|last|<file>")
    transmission.add_argument("--csv", default=None, metavar="OUT", help="导出 CSV 路径 / export CSV path")
    transmission.add_argument("--json", action="store_true", help="输出 JSON / emit JSON")
    transmission.set_defaults(func=cmd_transmission)

    # -- lamellar -----------------------------------------------------------
    lamellar = subparsers.add_parser(
        "lamellar",
        help="片晶相关函数分析 / lamellar correlation analysis",
        description=(
            "Lamellar (Strobl-Schneider) analysis of a two-column q/I curve.\n"
            "Two-column q/I text curve (whitespace or comma separated, # comments).\n"
            "片晶（Strobl-Schneider）一维相关函数分析，输入两列 q/I 文本曲线\n"
            "（空白或逗号分隔，# 为注释）。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    lamellar.add_argument("curve", metavar="CURVE", help="两列 q/I 曲线文件 / two-column q/I curve file")
    lamellar.add_argument("--json", action="store_true", help="输出含全部曲线的完整 JSON / full JSON with all curves")
    lamellar.add_argument("--out", default=None, metavar="REPORT", help="完整报告 JSON 落盘路径 / write the full report here")
    lamellar.add_argument("--q-unit", dest="q_unit", default="nm^-1", choices=["nm^-1", "A^-1"], help="输入 q 单位（默认 nm^-1）/ input q unit")
    lamellar.add_argument("--qmin", type=float, default=None, help="q 下限（与输入同单位）/ q lower bound")
    lamellar.add_argument("--qmax", type=float, default=None, help="q 上限（与输入同单位）/ q upper bound")
    lamellar.add_argument("--background", default="auto", choices=["none", "constant", "auto"], help="背景模式（默认 auto）/ background mode")
    lamellar.add_argument("--bg-constant", dest="bg_constant", type=float, default=None, help="constant 背景值 / constant background value")
    lamellar.add_argument("--minority-phase", dest="minority_phase", default="crystalline", choices=["crystalline", "amorphous"], help="薄层相（默认 crystalline）/ minority phase")
    lamellar.add_argument("--r-max", dest="r_max", type=float, default=None, help="相关函数 r 上限（nm）/ correlation r_max in nm")
    lamellar.add_argument("--tangent-min", dest="tangent_min", type=float, default=None, help="切线拟合窗口下限（nm）/ tangent window min")
    lamellar.add_argument("--tangent-max", dest="tangent_max", type=float, default=None, help="切线拟合窗口上限（nm）/ tangent window max")
    lamellar.add_argument("--no-porod", action="store_true", help="关闭 Porod 高 q 外推 / disable Porod extrapolation")
    lamellar.add_argument("--porod-fraction", dest="porod_fraction", type=float, default=None, help="Porod 拟合尾部比例 / Porod fit fraction")
    lamellar.add_argument("--porod-ext", dest="porod_ext", type=float, default=None, help="Porod 外推长度系数 / Porod extension factor")
    lamellar.add_argument("--overwrite", action="store_true", help="允许覆盖 --out 文件 / overwrite the --out file")
    lamellar.set_defaults(func=cmd_lamellar)

    # -- orientation --------------------------------------------------------
    orientation = subparsers.add_parser(
        "orientation",
        help="方位角取向分析 / azimuthal orientation analysis",
        description=(
            "Azimuthal orientation analysis of a two-column chi/I curve:\n"
            "Hermans orientation function and/or FWHM orientation index.\n"
            "方位角取向分析：两列 χ/I 曲线 → Hermans 取向函数和/或 FWHM 取向指数。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    orientation.add_argument("curve", metavar="CURVE", help="两列 χ/I 曲线文件 / two-column chi/I curve file")
    orientation.add_argument("--method", default="both", choices=["hermans", "fwhm", "both"], help="方法（默认 both）/ method (default: both)")
    orientation.add_argument("--json", action="store_true", help="输出含折叠曲线的完整 JSON / full JSON with folded curves")
    orientation.add_argument("--chi-zero", dest="chi_zero", default="meridian", choices=["meridian", "equator"], help="参考轴预设（默认 meridian）/ reference axis preset")
    orientation.add_argument("--reference-chi", dest="reference_chi", type=float, default=None, help="参考轴在 χ 中的角度（度）/ reference axis angle in chi")
    orientation.add_argument("--no-equatorial-to-chain", dest="no_equatorial_to_chain", action="store_true", help="不换算到链轴 <cos²φc> / skip chain-axis conversion")
    orientation.add_argument("--peak-window", dest="peak_window", type=float, default=None, help="FWHM 峰邻域半宽（度）/ FWHM peak window half width")
    orientation.set_defaults(func=cmd_orientation)

    # -- version ------------------------------------------------------------
    version = subparsers.add_parser(
        "version",
        help="打印版本信息 / print version information",
        description=(
            "Print xfais-cli, X-FAIS, python, numpy, pyFAI (and fabio/h5py) versions.\n"
            "打印 xfais-cli、X-FAIS 应用、python、numpy、pyFAI 等版本。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    version.add_argument("--json", action="store_true", help="输出 JSON / emit JSON")
    version.set_defaults(func=cmd_version)

    return parser


# ---------------------------------------------------------------------------
# Entry point / 入口
# ---------------------------------------------------------------------------


def _configure_stdio() -> None:
    """Best-effort UTF-8 stdio so Chinese/bilingual messages never crash.

    尽力把 stdio 切到 UTF-8，避免中文/特殊符号在 cp936 控制台触发
    UnicodeEncodeError（pytest 等替换过 sys.stdout 时静默跳过）。
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - never fail because of stdio setup
            continue


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the CLI; returns the process exit status (never raises SystemExit).

    执行 CLI，返回进程退出码（不会抛出 SystemExit，便于进程内调用）。
    """
    _configure_stdio()
    parser = build_parser()
    arguments: List[str] = list(sys.argv[1:] if argv is None else argv)

    try:
        ns = parser.parse_args(arguments)
    except _ParseExit as exc:
        if exc.message:
            _eprint(exc.message.rstrip("\n"))
        return int(exc.status)

    handler = getattr(ns, "func", None)
    if handler is None:
        parser.print_help()
        return 2

    try:
        return int(handler(ns) or 0)
    except _ParseExit as exc:  # pragma: no cover - sub-parsers never exit post-parse
        if exc.message:
            _eprint(exc.message.rstrip("\n"))
        return int(exc.status)
    except BrokenPipeError:  # pragma: no cover - shell piping
        return 1
    except CliError as exc:
        _eprint("xfais-cli: error: {}".format(exc))
        return 1
    except (ValueError, IOError, OSError, KeyError) as exc:
        _eprint("xfais-cli: error: {}".format(exc))
        return 1
    except KeyboardInterrupt:  # pragma: no cover - interactive
        _eprint("xfais-cli: interrupted")
        return 130


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
