#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h5convert.py — H5 to TIFF/CSV/DAT conversion (no GUI dependencies)
H5格式转换 — 将HDF5数据转换为TIFF/CSV/DAT（无GUI依赖）
"""

from __future__ import annotations

import csv
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional

import h5py
import numpy as np

# Relative import works under both import routes: `services.*` (launcher,
# python/ on sys.path) and `python.services.*` (tests).
# 相对导入兼容两种导入路由：services.*（launcher）与 python.services.*（测试）。
from .paths import validated_output_path_optional

OVERFLOW_THRESHOLD = 4.25e9
OVERFLOW_VALUE = -1.0

# HDF5 container extensions: Nexus (.nxs) and plain .hdf5 are HDF5 files too.
# HDF5 容器扩展名：Nexus（.nxs）与 .hdf5 本质都是 HDF5 文件。
H5_FILE_EXTENSIONS = (".h5", ".nxs", ".hdf5")

# Output naming modes: which first-level folder under output_dir receives a
# source file's image exports.
# 输出命名模式：源文件的图像导出落到输出目录下哪一层第一级子文件夹。
NAMING_MODES = ("parent_folder", "file_name", "dataset")

log = logging.getLogger(__name__)


def is_h5_file(name: str) -> bool:
    """True if a filename carries a supported HDF5 extension. 文件名是否为受支持的 HDF5 扩展名。"""
    return name.lower().endswith(H5_FILE_EXTENSIONS)


def is_master_file(name: str, suffix: str) -> bool:
    """True if a filename matches '<suffix><ext>' for any supported extension.
    文件名是否匹配 '<后缀><受支持扩展名>'。"""
    sfx = (suffix or "").lower()
    if not sfx:
        return False
    return name.lower().endswith(tuple(f"{sfx}{ext}" for ext in H5_FILE_EXTENSIONS))


def matches_suffix_filter(name: str, suffix_filter: str) -> bool:
    """Suffix filter match for the extract/file-list handlers: '<filter><ext>',
    or the filter itself already ends with a full extension.
    提取/文件列表的后缀过滤匹配：'<过滤词><扩展名>'，或过滤词本身已带完整扩展名。"""
    sfx = (suffix_filter or "").strip().lower()
    if not sfx:
        return True
    if sfx.endswith(H5_FILE_EXTENSIONS):
        return name.lower().endswith(sfx)
    return is_master_file(name, sfx)


def scan_h5_files(root_dir: str, recursive: bool = True) -> list[str]:
    """List supported H5/Nexus files under root_dir (sorted, deduplicated).
    列出 root_dir 下所有受支持的 H5/Nexus 文件（排序、去重）。"""
    root = str(root_dir)
    if not recursive:
        return sorted(
            os.path.join(root, f)
            for f in os.listdir(root)
            if os.path.isfile(os.path.join(root, f)) and is_h5_file(f)
        )
    # Single os.walk pass covers all supported extensions — one directory-tree
    # traversal instead of one recursive glob walk per extension.
    # 单次 os.walk 覆盖全部受支持扩展名——一遍目录树，代替每个扩展名一遍递归 glob。
    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        found.extend(os.path.join(dirpath, f) for f in filenames if is_h5_file(f))
    return sorted(found)


def _is_image_like(shape: tuple) -> bool:
    return len(shape) >= 2 and shape[-2] >= 2 and shape[-1] >= 2


def _dataset_kind(shape: tuple) -> str:
    nd = len(shape)
    if nd == 0:
        return "scalar"
    if nd == 1:
        return "1d"
    if _is_image_like(shape):
        return f"{nd}d_image"
    return f"{nd}d"


def _safe_folder_name(ds_path: str) -> str:
    return re.sub(r"[^\w\-]", "_", ds_path).strip("_") or "dataset"


def _apply_overflow(arr: np.ndarray) -> np.ndarray:
    if not np.issubdtype(arr.dtype, np.floating):
        arr = arr.astype(np.float32)
    else:
        arr = arr.copy()
    arr[arr > OVERFLOW_THRESHOLD] = OVERFLOW_VALUE
    return arr


def _require_vds_sources_present(ds: "h5py.Dataset", h5_path: str) -> None:
    """A virtual dataset whose source files are missing silently reads back
    fill values (blank images). Refuse to export that as data.
    虚拟数据集的源文件缺失时会静默读回填充值（空白图）；拒绝将其当数据导出。"""
    if not getattr(ds, "is_virtual", False):
        return
    sources = ds.virtual_sources
    if callable(sources):
        sources = sources()
    base = os.path.dirname(os.path.abspath(h5_path))
    missing: list[str] = []
    for vs in sources:
        ref = vs.file_name
        path = ref if os.path.isabs(ref) else os.path.join(base, ref)
        if not os.path.isfile(path):
            missing.append(ref)
    if missing:
        raise ValueError(
            f"VDS source file(s) missing for '{ds.name}': {missing[0]}"
            f"{' …' if len(missing) > 1 else ''} (extracted master without its data files?)"
        )


def save_tiff(data: np.ndarray, path: str) -> None:
    """Save 2D array as TIFF via fabio. 通过fabio将2D数组保存为TIFF。"""
    import fabio

    if data.ndim != 2:
        raise ValueError(f"TIFF requires 2D array, got shape: {data.shape}")
    fabio.tifimage.TifImage(data=data).write(path)


def save_edf(data: np.ndarray, path: str) -> None:
    """Save 2D array as EDF via fabio. 通过fabio将2D数组保存为EDF。"""
    import fabio

    if data.ndim != 2:
        raise ValueError(f"EDF requires 2D array, got shape: {data.shape}")
    fabio.edfimage.EdfImage(data=data).write(path)


class H5Converter:
    """Convert HDF5 datasets to TIFF/CSV/DAT. 将HDF5数据集转换为TIFF/CSV/DAT。"""

    def __init__(
        self,
        root_dir: str | Path,
        output_dir: str | Path,
        master_suffix: str = "_master",
        table_format: str = "csv",
        image_format: str = "tiff",
        naming_mode: str = "parent_folder",
        flat_output: bool = False,
    ):
        self.root_dir = str(root_dir)
        # v0.3.0 hardening: all converted outputs are written under this
        # directory (joins use sanitized relative names), so validating it
        # here confines every _write_csv/_write_dat target.
        self.output_dir = validated_output_path_optional(str(output_dir or ""), field="output_dir")
        self.master_suffix = master_suffix
        self.table_format = table_format
        self.image_format = image_format
        self.naming_mode = naming_mode if naming_mode in NAMING_MODES else "parent_folder"
        # Flat export: image files go straight into output_dir with the
        # folder components folded into the file name (no subfolders).
        # 扁平导出：图像文件直接落在输出目录，文件夹组并入文件名（不建子文件夹）。
        self.flat_output = bool(flat_output)
        self._all_h5: list[str] = []
        self._master_h5: Optional[str] = None
        self._ds_cfg: dict[str, dict] = {}

    def scan(self) -> list[str]:
        """Scan root_dir for all supported H5/Nexus files. 扫描根目录所有受支持的 H5/Nexus 文件。"""
        self._all_h5 = scan_h5_files(self.root_dir, recursive=True)
        self._master_h5 = next(
            (f for f in self._all_h5 if is_master_file(os.path.basename(f), self.master_suffix)),
            None,
        )
        return self._all_h5

    def inspect_datasets(self) -> dict[str, dict]:
        """Inspect datasets from the reference H5 (master if any, else the
        first scanned file — mirrors the scan handler's fallback).
        从参考 H5 检查数据集（有 master 用 master，否则取第一个扫描文件，
        与扫描端回退语义一致）。"""
        ref = self._master_h5 or (self._all_h5[0] if self._all_h5 else None)
        if not ref:
            raise FileNotFoundError("No H5 file found. Call scan() first.")
        self._ds_cfg.clear()
        with h5py.File(ref, "r") as f:
            def _visit(name: str, obj: Any) -> None:
                if not isinstance(obj, h5py.Dataset):
                    return
                shape = obj.shape
                channels = list(range(shape[1])) if len(shape) == 4 else None
                self._ds_cfg[name] = {
                    "export": True,
                    "shape": shape,
                    "dtype": str(obj.dtype),
                    "kind": _dataset_kind(shape),
                    "channels": channels,
                }
            f.visititems(_visit)
        return self._ds_cfg

    def set_dataset_config(self, ds_path: str, export: bool = True,
                           channels: Optional[list[int]] = None) -> None:
        if ds_path in self._ds_cfg:
            self._ds_cfg[ds_path]["export"] = export
            if channels is not None:
                self._ds_cfg[ds_path]["channels"] = channels

    def set_all_export(self, export: bool = True) -> None:
        """Set the export flag on every inspected dataset. The convert handler
        passes False before applying the UI selection: the UI's dataset list
        is the COMPLETE selection, so anything unlisted (e.g. Nexus instrument
        flatfields / pixel masks) must not keep inspect()'s default True.
        设置所有已检查数据集的导出标记。转换 handler 在套用 UI 选择前先全置
        False：UI 的数据集列表是完整选择，未列出的（如 Nexus 仪器平场/像素
        掩码）不得保留 inspect() 的默认 True。"""
        for cfg in self._ds_cfg.values():
            cfg["export"] = export

    def convert(
        self,
        log_fn: Optional[Callable[[str], None]] = None,
        progress_fn: Optional[Callable[[float], None]] = None,
        stop_event: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Execute the conversion. 执行转换。

        Returns dict with summary stats. 返回含汇总统计的字典。
        """
        def _log(msg: str) -> None:
            log.info(msg)
            if log_fn:
                log_fn(msg)

        def _stopped() -> bool:
            return stop_event is not None and stop_event.is_set()

        os.makedirs(self.output_dir, exist_ok=True)
        selected = {k: v for k, v in self._ds_cfg.items() if v["export"]}
        if not selected:
            raise ValueError("No datasets selected for export")

        sfx = self.master_suffix
        data_h5 = [f for f in self._all_h5
                   if is_master_file(os.path.basename(f), sfx)]
        if not data_h5:
            # No '<suffix><ext>' files: convert everything found, matching the
            # scan handler's fallback (reference file = first file).
            # 没有 '<后缀><扩展名>' 文件时转换全部扫描到的文件——与扫描端
            # （参考文件取第一个）的回退语义一致。
            data_h5 = list(self._all_h5)

        def _image_folders(h5_path: str, ds_path: str) -> list[str]:
            """Folder components for one (file, dataset) image export; the
            naming mode decides the first-level folder (flat_output folds
            them into the file name instead — see _export_image).
            命名模式决定第一层子文件夹；扁平导出时这些组件并入文件名。"""
            if self.naming_mode == "parent_folder":
                top = _safe_folder_name(Path(h5_path).parent.name)
            elif self.naming_mode == "file_name":
                top = _safe_folder_name(Path(h5_path).stem)
            else:  # dataset: legacy layout, dataset folder at output root / 旧版布局
                top = ""
            return [p for p in (top, _safe_folder_name(ds_path)) if p]

        scalar_acc: dict = {}
        stats = {"files_processed": 0, "images_exported": 0, "errors": 0}
        total = len(data_h5)

        for h5_idx, h5_path in enumerate(data_h5):
            if _stopped():
                break
            file_stem = Path(h5_path).stem
            _log(f"Processing: {file_stem}")
            try:
                with h5py.File(h5_path, "r") as f:
                    for ds_path, cfg in selected.items():
                        if ds_path not in f:
                            continue
                        ds = f[ds_path]
                        _require_vds_sources_present(ds, h5_path)
                        if "image" in cfg["kind"]:
                            n = self._export_image(
                                ds, ds_path, cfg, _image_folders(h5_path, ds_path), file_stem
                            )
                            stats["images_exported"] += n
                        else:
                            self._accumulate_scalar(ds, ds_path, file_stem, scalar_acc)
            except Exception as exc:
                _log(f"Error ({file_stem}): {exc}")
                stats["errors"] += 1
            stats["files_processed"] += 1
            if progress_fn:
                progress_fn((h5_idx + 1) / max(total, 1))

        if scalar_acc:
            ext = "csv" if self.table_format == "csv" else "dat"
            out_path = os.path.join(self.output_dir, f"non_image_data.{ext}")
            if self.table_format == "csv":
                self._write_csv(scalar_acc, out_path)
            else:
                self._write_dat(scalar_acc, out_path)
            _log(f"Non-image data → {out_path}")

        _log("Conversion complete.")
        return stats

    def _export_image(self, ds: h5py.Dataset, ds_path: str, cfg: dict,
                      folders: list[str], file_stem: str) -> int:
        shape = ds.shape
        nd = len(shape)
        count = 0
        ext = ".edf" if self.image_format == "edf" else ".tif"
        _save = save_edf if self.image_format == "edf" else save_tiff

        def _out(more_folders: list[str], name: str) -> str:
            # flat_output: no subfolders — the folder components fold into the
            # file name (user option 2026-09-30). 扁平导出：不建子文件夹，
            # 文件夹组并入文件名。
            if self.flat_output:
                return os.path.join(self.output_dir, "_".join([*more_folders, name]))
            out_dir = os.path.join(self.output_dir, *more_folders)
            os.makedirs(out_dir, exist_ok=True)
            return os.path.join(out_dir, name)

        if nd == 2:
            data = _apply_overflow(ds[()])
            _save(data, _out(folders, f"{file_stem}{ext}"))
            count = 1
        elif nd == 3:
            n_frames = shape[0]
            data = ds[()]
            for fi in range(n_frames):
                frame = _apply_overflow(data[fi])
                _save(frame, _out(folders, f"{file_stem}_frame{fi:04d}{ext}"))
            count = n_frames
        elif nd == 4:
            # channels=[] is a deliberate "none selected", not "all" — only
            # a missing key falls back to every channel.
            # channels=[] 是用户明确全不选；仅缺省时才回退为全部通道。
            channels = cfg.get("channels")
            if channels is None:
                channels = list(range(shape[1]))
            n_frames = shape[0]
            data = ds[()]
            for ci in channels:
                if ci >= shape[1]:
                    continue
                for fi in range(n_frames):
                    slice2d = _apply_overflow(data[fi, ci, :, :])
                    frame_tag = f"_frame{fi:04d}" if n_frames > 1 else ""
                    _save(slice2d, _out([*folders, f"CH{ci}"], f"{file_stem}{frame_tag}{ext}"))
            count = n_frames * len(channels)
        return count

    def _accumulate_scalar(self, ds: h5py.Dataset, ds_path: str,
                           file_stem: str, acc: dict) -> None:
        try:
            flat = np.ravel(ds[()])
        except Exception:
            return
        if ds_path not in acc:
            acc[ds_path] = {"files": [], "values": []}
        acc[ds_path]["files"].append(file_stem)
        acc[ds_path]["values"].append(flat)

    def _build_table(self, acc: dict) -> tuple[list[str], list[list]]:
        header = ["source_file"]
        col_widths: dict[str, int] = {}
        for ds_path, info in acc.items():
            mx = max((len(v) for v in info["values"]), default=1)
            col_widths[ds_path] = mx
            if mx == 1:
                header.append(ds_path)
            else:
                header.extend(f"{ds_path}[{i}]" for i in range(mx))

        all_files: list[str] = []
        seen: set[str] = set()
        for info in acc.values():
            for fn in info["files"]:
                if fn not in seen:
                    all_files.append(fn)
                    seen.add(fn)

        rows = []
        for fn in all_files:
            row = [fn]
            for ds_path, info in acc.items():
                w = col_widths[ds_path]
                if fn in info["files"]:
                    idx = info["files"].index(fn)
                    vals = info["values"][idx].tolist()
                    vals += [""] * max(0, w - len(vals))
                    row.extend(vals[:w])
                else:
                    row.extend([""] * w)
            rows.append(row)
        return header, rows

    def _write_csv(self, acc: dict, path: str) -> None:
        header, rows = self._build_table(acc)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)

    def _write_dat(self, acc: dict, path: str) -> None:
        header, rows = self._build_table(acc)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\t".join(str(h) for h in header) + "\n")
            for row in rows:
                fh.write("\t".join(str(v) for v in row) + "\n")
