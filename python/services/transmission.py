#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""transmission.py — Direct-beam transmission measurement (2026-10-25).

The user shoots a direct-beam image (no sample), draws a RECTANGLE or a
multi-point POLYGON over the beam stop-free spot — exactly like the mask
editor's region semantics — and this module integrates EVERY pixel inside
that region (full integration, no threshold tail cut, no centre-of-mass
weighting). One file, usually the direct beam, is designated as the
reference; every other file then gets T = I / I_ref.

Exports are two flavours shared with the background-subtraction module:
``transmission.csv`` (file, intensity, transmission — for humans/Excel) and
``transmission.json`` (file + transmission only). The reader below accepts
both, and matches entries back to data files by basename so the background
subtractor can consume imported transmissions.

transmission.py — 直通光透过率测量（2026-10-25）。

用户拍摄直通光图（不放样品），像掩膜编辑器那样在光斑上圈一个**方形框**或
**多折框**，本模块对该区域内的**每一个像素**做完全积分（不设阈值尾部截断、
不做质心加权）。指定一个文件（通常就是直通光图）为「参考」，其余文件即得
T = I / I_ref。

导出两种格式供背景扣除模块共享：``transmission.csv``（file, intensity,
transmission，便于人工核对/Excel）与 ``transmission.json``（仅 file +
transmission）。下方读取函数两种都接受，并按 basename 把条目匹配回数据
文件，供背景扣除消费。

Pure library — no fabio / no GUI / no I/O beyond the explicit export and
parse helpers (the handler layer loads images and writes through the
validated-output-path choke point).
纯函数库——不依赖 fabio/GUI；除显式的导出与解析函数外不做 I/O（图像加载与
写盘校验都在 service_launcher 处理层完成）。
"""

from __future__ import annotations

import csv
import io
import json
import math
import os
import re
from typing import Any, Dict, List, Optional

import numpy as np

#: Border width (pixels) of a rectangular ROI used for the background estimate
#: when ``subtract_border=True`` — same ring as calibration's COM background.
#: subtract_border=True 时矩形 ROI 的背景估计边缘宽度（像素）——与标定质心的
#: 背景边框同宽。
_BORDER_PX: int = 3


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Coerce to a finite float, falling back to ``default``. / 安全转有限 float。

    Non-finite inputs (nan/inf) are treated as unavailable, exactly like the
    calibration helper this module mirrors.
    非有限值（nan/inf）视为不可用，与所镜像的标定工具函数一致。
    """
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _bad(message_en: str, message_zh: str) -> ValueError:
    """Build a bilingual ValueError. / 构造双语 ValueError。"""
    return ValueError(f"{message_en} / {message_zh}")


def _polygon_mask(verts: np.ndarray, y0: int, y1: int, x0: int, x1: int) -> np.ndarray:
    """Even-odd point-in-polygon over the integer grid [y0,y1)×[x0,x1).

    Vectorized ray casting: for every pixel centre (row, col) a ray is cast
    toward +x and the polygon edge crossings are counted XOR-wise (vertices on
    the ray are handled by the standard half-open edge rule y_min ≤ y < y_max).
    / 在整数网格 [y0,y1)×[x0,x1) 上做奇偶规则多边形内判定（向量化射线法，
    半开边规则 y_min ≤ y < y_max 处理顶点在射线上的退化情形）。

    Copied verbatim from ``services.calibration._polygon_mask`` (the region
    semantics must stay identical) but kept local so this module stays
    independent of the calibration engine.
    逐字复制自 ``services.calibration._polygon_mask``（区域语义必须一致），
    但保留在本模块内，使透过率库不依赖标定引擎。
    """
    rows = np.arange(y0, y1, dtype=np.float64)[:, None]
    cols = np.arange(x0, x1, dtype=np.float64)[None, :]
    inside = np.zeros((y1 - y0, x1 - x0), dtype=bool)
    n = len(verts)
    for i in range(n):
        ay, ax = verts[i]
        by, bx = verts[(i + 1) % n]
        # Half-open edge rule: an edge [a,b] counts crossings only when the
        # ray's y lies in [min, max). / 半开边规则：仅当射线 y 落在 [min, max)
        # 时该边计入穿越。
        ylo, yhi = (ay, by) if ay < by else (by, ay)
        cond = (rows >= ylo) & (rows < yhi)
        if not cond.any():
            continue
        # x intersection of the edge at each row. / 各行上边的交点 x。
        with np.errstate(invalid="ignore", divide="ignore"):
            t = (rows - ay) / (by - ay)
        xint = ax + t * (bx - ax)
        inside ^= cond & (cols < xint)
    return inside


def validate_region(region: Any) -> Dict[str, Any]:
    """Structural validation of a rect / polygon region (no image needed).

    Accepts exactly the region shape the calibration canvas produces:
    ``{"kind": "rect", "y0", "y1", "x0", "x1"}`` (floats, pixel coordinates)
    or ``{"kind": "poly", "points": [{"y", "x"} ...] | [[y, x] ...]}`` with at
    least 3 vertices. Returns a normalized shallow copy; raises ValueError
    (bilingual) on unusable input.
    方形框/多折框区域的结构校验（不需要图像尺寸）：接受标定画布产出的区域
    形状——``{"kind":"rect", y0,y1,x0,x1}``（浮点像素坐标）或
    ``{"kind":"poly", "points":[{y,x}...] | [[y,x]...]}``（至少 3 个顶点）。
    返回规范化副本；输入不可用时抛双语 ValueError。
    """
    if not isinstance(region, dict):
        raise _bad(
            "region must be a dict with kind 'rect' or 'poly'",
            "region 必须是含 kind='rect' 或 'poly' 的字典",
        )
    kind = str(region.get("kind") or "").strip().lower()
    if kind == "rect":
        y0 = _as_float(region.get("y0"))
        y1 = _as_float(region.get("y1"))
        x0 = _as_float(region.get("x0"))
        x1 = _as_float(region.get("x1"))
        if None in (y0, y1, x0, x1):
            raise _bad(
                "rect region needs finite y0/y1/x0/x1",
                "方形框区域需要有限的 y0/y1/x0/x1",
            )
        # Sorted + floor/ceil exactly like calibration's COM region, so a
        # drag in any direction yields the same pixel block.
        # 与标定质心一致：排序后 floor/ceil，任意方向拖框得到同一像素块。
        ya, yb = sorted((int(math.floor(y0)), int(math.ceil(y1))))
        xa, xb = sorted((int(math.floor(x0)), int(math.ceil(x1))))
        if (yb - ya) < 1 or (xb - xa) < 1:
            raise _bad(
                "rect region is empty (needs ≥1 pixel)",
                "方形框区域为空（至少需要 1 个像素）",
            )
        return {"kind": "rect", "y0": y0, "y1": y1, "x0": x0, "x1": x1, "ya": ya, "yb": yb, "xa": xa, "xb": xb}
    if kind == "poly":
        raw_pts = region.get("points") or []
        verts: List[List[float]] = []
        for p in raw_pts:
            if isinstance(p, dict):
                py, px = _as_float(p.get("y")), _as_float(p.get("x"))
            elif isinstance(p, (list, tuple)) and len(p) >= 2:
                py, px = _as_float(p[0]), _as_float(p[1])
            else:
                continue
            if py is not None and px is not None:
                verts.append([py, px])
        if len(verts) < 3:
            raise _bad(
                "polygon region needs at least 3 vertices",
                "多折框区域需要至少 3 个顶点",
            )
        vy = np.array([v[0] for v in verts], dtype=np.float64)
        vx = np.array([v[1] for v in verts], dtype=np.float64)
        ya = int(math.floor(vy.min()))
        yb = int(math.ceil(vy.max()))
        xa = int(math.floor(vx.min()))
        xb = int(math.ceil(vx.max()))
        if (yb - ya) < 1 or (xb - xa) < 1:
            raise _bad(
                "polygon region is empty (needs ≥1 pixel)",
                "多折框区域为空（至少需要 1 个像素）",
            )
        return {"kind": "poly", "points": verts, "ya": ya, "yb": yb, "xa": xa, "xb": xb}
    raise _bad(
        f"Unknown region kind {kind!r}: expected 'rect' or 'poly'",
        f"未知区域类型 {kind!r}：应为 'rect' 或 'poly'",
    )


def _region_border(mask: np.ndarray, kind: str) -> np.ndarray:
    """Boundary pixels of a region mask (rect ring / polygon edge).

    Rectangles use the outermost ``_BORDER_PX`` rows/columns of the box (the
    dimmest, spot-free population, same as calibration); polygons use
    ``mask & ~binary_erosion(mask, 1)``. scipy is imported lazily so the
    module stays importable in a bare numpy environment.
    区域掩膜的边界像素（矩形取边框环 / 多折框取掩膜边缘）。矩形取框最外
    ``_BORDER_PX`` 行/列（最暗、无光斑，与标定一致）；多折框取
    ``mask & ~binary_erosion(mask,1)``。scipy 惰性导入，无 scipy 环境下本模块
    仍可导入。
    """
    if kind == "rect":
        border = np.zeros_like(mask)
        b = min(_BORDER_PX, (mask.shape[0] - 1) // 2, (mask.shape[1] - 1) // 2)
        b = max(1, b)
        border[:b, :] = True
        border[-b:, :] = True
        border[:, :b] = True
        border[:, -b:] = True
        return border
    from scipy import ndimage  # lazy: keeps the module import light / 惰性导入

    eroded = ndimage.binary_erosion(mask, iterations=1)
    return mask & ~eroded


def region_pixel_sum(
    data: np.ndarray, region: Dict[str, Any], subtract_border: bool = False,
) -> Dict[str, Any]:
    """Full integration of every pixel inside a rect / polygon region.

    Region semantics are identical to ``calibration._region_center_of_mass``:
    rect corners are floats, floor/ceil-expanded and clipped into the image;
    poly points are ``[{y,x}]`` or ``[[y,x]]`` with ≥3 vertices, and the
    even-odd rasterization is clipped to the image. The ROI is NOT filtered,
    NOT thresholded and NOT centre-of-mass weighted — this is a plain sum, so
    the transmission ratio is unbiased by any tail cut.

    With ``subtract_border=True`` the background is the median of the region's
    boundary pixels (rect: 3 px ring; poly: mask edge) and every pixel
    contributes ``clip(roi − bg, 0, ∞)`` — negative contributions are clipped
    to 0 because a negative transmission has no physical meaning. Without it
    nothing is subtracted (the default, "completely integrate the region").

    Raises ValueError (bilingual) for an empty / fully out-of-image region or
    a non-finite / negative total.
    方形框/多折框区域内每个像素的完全积分。区域语义与标定质心完全一致（矩形
    浮点角点 floor/ceil 后裁进图像；多折框顶点 ≥3，奇偶规则光栅化后裁进
    图像）。ROI 不做滤波、不做阈值截断、不做质心加权——就是求和，因此透过率
    比值不受任何尾部截断影响。

    ``subtract_border=True`` 时以区域边界像素中位数为背景（矩形 3px 边框环；
    多折框掩膜边缘），每像素贡献 ``clip(roi − bg, 0, ∞)``——负贡献截 0，
    物理上透过率不应为负。默认不扣任何背景（「完全积分」）。

    区域为空/完全落在图像外，或总和非有限/为负时抛双语 ValueError。
    """
    arr = np.asarray(data)
    # Reduce a stack to its first frame, matching how the image handlers pick
    # the displayed frame. / 与图像处理层一致：多层数据取第一帧。
    while arr.ndim > 2:
        arr = arr[0]
    if arr.ndim != 2 or arr.shape[0] < 1 or arr.shape[1] < 1:
        raise _bad(
            f"Expected a 2-D image array, got shape {arr.shape}",
            f"需要二维图像数组，实际形状为 {arr.shape}",
        )
    arr = arr.astype(np.float64, copy=False)
    h, w = arr.shape

    norm = validate_region(region)
    kind = norm["kind"]
    ya = max(0, int(norm["ya"]))
    xa = max(0, int(norm["xa"]))
    yb = min(h, int(norm["yb"]))
    xb = min(w, int(norm["xb"]))
    if yb <= ya or xb <= xa:
        raise _bad(
            "Region lies entirely outside the image",
            "区域完全落在图像之外",
        )

    if kind == "rect":
        mask = np.ones((yb - ya, xb - xa), dtype=bool)
    else:
        verts = np.asarray(norm["points"], dtype=np.float64)
        mask = _polygon_mask(verts, ya, yb, xa, xb)
        if not mask.any():
            raise _bad(
                "Polygon region contains no pixel inside the image",
                "多折框区域内没有任何像素（图像范围外）",
            )

    pixel_count = int(np.count_nonzero(mask))
    if pixel_count < 1:
        raise _bad(
            "Region contains no pixel inside the image",
            "区域内没有任何像素（图像范围外）",
        )

    roi = arr[ya:yb, xa:xb]
    # Non-finite pixels contribute nothing to an integral. / 非有限像素不计入积分。
    roi = np.nan_to_num(roi, nan=0.0, posinf=0.0, neginf=0.0)

    if subtract_border:
        border = _region_border(mask, kind)
        border_vals = roi[border]
        bg_level = float(np.median(border_vals)) if border_vals.size else 0.0
        values = np.clip(roi - bg_level, 0.0, None)
        values[~mask] = 0.0
        total = float(values.sum())
    else:
        bg_level = None
        total = float(roi[mask].sum())

    if not math.isfinite(total) or total < 0.0:
        raise _bad(
            f"Region integral is not a valid intensity ({total!r})",
            f"区域积分不是有效强度（{total!r}）",
        )
    return {
        "total": total,
        "pixel_count": pixel_count,
        "mean": total / float(pixel_count),
        "bg_level": bg_level,
    }


def compute_transmission_rows(rows: List[Dict[str, Any]], reference: str) -> List[Dict[str, Any]]:
    """Attach ``transmission = I / I_ref`` to every row (reference → 1.0).

    ``rows`` items need ``file`` and ``intensity``; the reference file is
    matched by exact path first, then by ``normcase(normpath(...))`` so a
    differently-cased Windows path still hits. The input list is never
    mutated — a new list of shallow copies is returned.

    Raises ValueError (bilingual) when the reference is not among the rows,
    when its intensity is missing / non-finite / ≤ 0, or when any row's
    intensity is not a finite number.
    给每一行附加 ``transmission = I / I_ref``（参考行为 1.0）。行需含 ``file``
    与 ``intensity``；参考文件先按原样路径匹配，再按
    ``normcase(normpath(...))`` 匹配（Windows 大小写不同也能命中）。不修改
    入参，返回浅拷贝组成的新列表。

    参考文件不在 rows、其强度缺失/非有限/≤0，或某行强度非有限时，抛双语
    ValueError。
    """
    if not reference:
        raise _bad("reference file is required", "需要参考文件")
    ref = str(reference)
    ref_index: Optional[int] = None
    for i, row in enumerate(rows or []):
        if str(row.get("file")) == ref:
            ref_index = i
            break
    if ref_index is None:
        ref_key = os.path.normcase(os.path.normpath(ref))
        for i, row in enumerate(rows or []):
            if os.path.normcase(os.path.normpath(str(row.get("file", "")))) == ref_key:
                ref_index = i
                break
    if ref_index is None:
        raise _bad(
            f"Reference file is not among the integrated rows: {ref}",
            f"参考文件不在已积分的文件列表中：{ref}",
        )

    ref_intensity = _as_float((rows[ref_index] or {}).get("intensity"))
    if ref_intensity is None or ref_intensity <= 0.0:
        raise _bad(
            "Reference intensity must be a finite positive number "
            f"(got {ref_intensity!r} for {ref})",
            f"参考强度必须是有限正数（{ref} 当前为 {ref_intensity!r}）",
        )

    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows or []):
        intensity = _as_float((row or {}).get("intensity"))
        if intensity is None:
            raise _bad(
                f"Row {i} has no finite intensity (file={row.get('file')!r})",
                f"第 {i} 行缺少有限强度（file={row.get('file')!r}）",
            )
        item = dict(row)
        item["transmission"] = 1.0 if i == ref_index else intensity / ref_intensity
        out.append(item)
    return out


def _fmt_number(value: Optional[float]) -> str:
    """Format a float for CSV with shortest round-trip precision. / CSV 数值格式。"""
    if value is None:
        return ""
    return repr(float(value))


def _export_name(file_value: str) -> str:
    """Basename for the exported ``file`` column.

    Rows may carry full server-side paths (web uploads land in a session
    directory whose path is meaningless on any other machine — or even in the
    next session of the same deployment). The portable identity of a row is
    its file NAME, which is also what ``match_transmission_entries`` keys on.
    导出 ``file`` 列用纯文件名。行内可能是完整服务器路径（web 上传落在会话
    目录，该路径换台机器、甚至换个会话就失效），行的可移植标识是文件名，
    与 ``match_transmission_entries`` 的匹配键一致。
    """
    return os.path.basename(file_value) or file_value


def export_transmission_csv(rows: List[Dict[str, Any]], path: str) -> str:
    """Write ``file,intensity,transmission`` as CSV (UTF-8 with BOM).

    Row order is preserved. The BOM (``utf-8-sig``) keeps Excel from
    mangling non-ASCII file names; ``None`` intensities become empty cells.
    The ``file`` column carries the BASENAME (see ``_export_name``) so the
    table stays portable across machines and sessions. Returns the written
    absolute path.
    写 ``file,intensity,transmission`` 三列 CSV（带 BOM 的 UTF-8，Excel 打开
    中文文件名不乱码）。行序保持；intensity 为 None 时写空单元格；file 列
    写纯文件名（见 ``_export_name``），跨机器/跨会话可移植。返回写出的
    绝对路径。
    """
    path = str(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["file", "intensity", "transmission"])
        for i, row in enumerate(rows or []):
            file_value = row.get("file")
            if not isinstance(file_value, str) or not file_value.strip():
                raise _bad(
                    f"Row {i} has no file name", f"第 {i} 行缺少文件名",
                )
            transmission = _as_float(row.get("transmission"))
            if transmission is None:
                raise _bad(
                    f"Row {i} ({file_value}) has no finite transmission",
                    f"第 {i} 行（{file_value}）缺少有限透过率",
                )
            intensity = row.get("intensity")
            intensity_value: Optional[float] = None
            if not (intensity is None or (isinstance(intensity, str) and not intensity.strip())):
                intensity_value = _as_float(intensity)
                if intensity_value is None:
                    raise _bad(
                        f"Row {i} ({file_value}) has an invalid intensity",
                        f"第 {i} 行（{file_value}）强度无效",
                    )
            writer.writerow([
                _export_name(file_value),
                _fmt_number(intensity_value),
                _fmt_number(transmission),
            ])
    return os.path.abspath(path)


def export_transmission_json(rows: List[Dict[str, Any]], path: str) -> str:
    """Write ``[{"file": ..., "transmission": ...}]`` JSON (indent 2).

    Intensity is deliberately omitted — the JSON flavour is the compact
    "transmission table" the background subtractor consumes. The ``file``
    values are BASENAMES (see ``_export_name``). Returns the written
    absolute path.
    写 ``[{"file":..., "transmission":...}]`` JSON（缩进 2）。刻意不含
    intensity——JSON 是背景扣除消费的紧凑「透过率表」；file 为纯文件名
    （见 ``_export_name``）。返回写出的绝对路径。
    """
    path = str(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    payload: List[Dict[str, Any]] = []
    for i, row in enumerate(rows or []):
        file_value = row.get("file")
        if not isinstance(file_value, str) or not file_value.strip():
            raise _bad(f"Row {i} has no file name", f"第 {i} 行缺少文件名")
        transmission = _as_float(row.get("transmission"))
        if transmission is None:
            raise _bad(
                f"Row {i} ({file_value}) has no finite transmission",
                f"第 {i} 行（{file_value}）缺少有限透过率",
            )
        payload.append({"file": _export_name(file_value), "transmission": transmission})
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return os.path.abspath(path)


def _read_text(path: str) -> str:
    """Read a text file as UTF-8 (BOM tolerant) with a GBK fallback.

    Returns the decoded text; raises OSError when the file is unreadable.
    以 UTF-8（容忍 BOM）读取文本文件，失败时回退 GBK；不可读时抛 OSError。
    """
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            return fh.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="gbk", newline="") as fh:
            return fh.read()


def _entry_from_json(item: Any, index: int) -> Dict[str, Any]:
    """Validate one JSON transmission item. / 校验单个 JSON 透过率条目。"""
    if not isinstance(item, dict):
        raise _bad(
            f"Transmission entry {index} is not an object",
            f"第 {index} 个透过率条目不是对象",
        )
    file_value = item.get("file")
    if not isinstance(file_value, str) or not file_value.strip():
        raise _bad(
            f"Transmission entry {index} has no file name",
            f"第 {index} 个透过率条目缺少文件名",
        )
    transmission = _as_float(item.get("transmission"))
    if transmission is None:
        raise _bad(
            f"Transmission entry for {file_value} has no finite transmission",
            f"{file_value} 的透过率条目缺少有限数值",
        )
    intensity: Optional[float] = None
    raw_intensity = item.get("intensity")
    if not (raw_intensity is None or (isinstance(raw_intensity, str) and not raw_intensity.strip())):
        intensity = _as_float(raw_intensity)
        if intensity is None:
            raise _bad(
                f"Transmission entry for {file_value} has an invalid intensity",
                f"{file_value} 的透过率条目强度无效",
            )
    return {"file": file_value, "intensity": intensity, "transmission": transmission}


def parse_transmission_file(path: str) -> List[Dict[str, Any]]:
    """Parse a transmission CSV / JSON export back into entries.

    ``.json`` files (or content starting with ``[`` / ``{``) are read as JSON:
    a bare array or ``{"files": [...]}``; every item needs ``file`` and a
    numeric ``transmission`` (``intensity`` optional). Everything else is read
    as CSV with a UTF-8-BOM (GBK fallback) decode; the header must contain
    ``file`` and ``transmission`` (case-insensitive, surrounding whitespace
    ignored) and ``intensity`` is optional. Returns
    ``[{"file", "intensity"|None, "transmission"}]``.

    Raises ValueError (bilingual) for a missing/empty file, unparseable
    content, or a row without a usable transmission value.
    把导出的透过率 CSV/JSON 解析回条目。``.json``（或内容以 ``[``/``{`` 开头）
    按 JSON 读：裸数组或 ``{"files":[...]}`；每项需 ``file`` 与数值
    ``transmission``（``intensity`` 可选）。其余按 CSV 读（UTF-8-BOM，回退
    GBK）；表头必须含 ``file`` 与 ``transmission``（大小写不敏感、忽略首尾
    空白），``intensity`` 可选。返回
    ``[{"file", "intensity"|None, "transmission"}]``。

    文件缺失/为空、内容无法解析、或某行没有可用透过率时抛双语 ValueError。
    """
    path = str(path)
    if not os.path.isfile(path):
        raise _bad(f"Transmission file not found: {path}", f"透过率文件不存在：{path}")
    text = _read_text(path)
    if not text.strip():
        raise _bad(
            f"Transmission file is empty: {path}", f"透过率文件为空：{path}",
        )

    stripped = text.lstrip()
    is_json = path.lower().endswith(".json") or stripped.startswith(("[", "{"))
    if is_json:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise _bad(
                f"Invalid JSON in transmission file {path}: {exc}",
                f"透过率文件 JSON 无效（{path}）：{exc}",
            ) from exc
        if isinstance(data, dict):
            items = data.get("files")
            if not isinstance(items, list):
                raise _bad(
                    "JSON transmission file must be an array or a "
                    "{'files': [...]} object",
                    "JSON 透过率文件必须是数组或 {'files': [...]} 对象",
                )
        elif isinstance(data, list):
            items = data
        else:
            raise _bad(
                "JSON transmission file must be an array or a "
                "{'files': [...]} object",
                "JSON 透过率文件必须是数组或 {'files': [...]} 对象",
            )
        if not items:
            raise _bad(
                f"Transmission file has no entries: {path}",
                f"透过率文件中没有任何条目：{path}",
            )
        return [_entry_from_json(item, i) for i, item in enumerate(items)]

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise _bad(
            f"Transmission CSV has no header: {path}",
            f"透过率 CSV 缺少表头：{path}",
        )
    columns = {
        str(name).strip().lower(): name
        for name in reader.fieldnames
        if name is not None
    }
    missing = [key for key in ("file", "transmission") if key not in columns]
    if missing:
        raise _bad(
            f"Transmission CSV needs columns {missing} (found "
            f"{list(columns)!r}): {path}",
            f"透过率 CSV 缺少列 {missing}（实际表头 {list(columns)!r}）：{path}",
        )

    entries: List[Dict[str, Any]] = []
    for line_no, raw_row in enumerate(reader, start=2):
        file_raw = raw_row.get(columns["file"])
        transmission_raw = raw_row.get(columns["transmission"])
        file_value = str(file_raw).strip() if file_raw is not None else ""
        transmission_text = (
            str(transmission_raw).strip() if transmission_raw is not None else ""
        )
        if not file_value and not transmission_text:
            continue  # blank line / 空行
        if not file_value:
            raise _bad(
                f"Transmission CSV line {line_no} has no file name",
                f"透过率 CSV 第 {line_no} 行缺少文件名",
            )
        transmission = _as_float(transmission_text)
        if transmission is None:
            raise _bad(
                f"Transmission CSV line {line_no} ({file_value}) has no valid "
                f"transmission value: {transmission_text!r}",
                f"透过率 CSV 第 {line_no} 行（{file_value}）没有有效透过率："
                f"{transmission_text!r}",
            )
        intensity: Optional[float] = None
        if "intensity" in columns:
            intensity_raw = raw_row.get(columns["intensity"])
            intensity_text = (
                str(intensity_raw).strip() if intensity_raw is not None else ""
            )
            if intensity_text:
                intensity = _as_float(intensity_text)
                if intensity is None:
                    raise _bad(
                        f"Transmission CSV line {line_no} ({file_value}) has an "
                        f"invalid intensity: {intensity_text!r}",
                        f"透过率 CSV 第 {line_no} 行（{file_value}）强度无效："
                        f"{intensity_text!r}",
                    )
        entries.append({
            "file": file_value,
            "intensity": intensity,
            "transmission": transmission,
        })

    if not entries:
        raise _bad(
            f"Transmission file has no data rows: {path}",
            f"透过率文件没有数据行：{path}",
        )
    return entries


#: Longest digit run treated as an upload-conflict suffix when de-suffixing
#: names for the loose match (see ``_strip_conflict_suffix``). Real counters
#: are short (`_1`, `_12`); long digit runs (timestamps `_20261025`) are
#: genuine name parts.
#: 宽松匹配时视为上传冲突后缀的最大数字位数（见 ``_strip_conflict_suffix``）。
#: 冲突计数都很短（`_1`、`_12`）；长数字串（时间戳 `_20261025`）是文件名
#: 本身的一部分，不动。
_CONFLICT_SUFFIX_MAX_DIGITS = 4

_CONFLICT_SUFFIX_RE = re.compile(r"^(?P<stem>.+?)_(?P<n>\d{1,4})$")


def _strip_conflict_suffix(basename: str) -> str:
    """Drop one trailing ``_<small counter>`` from a basename's stem.

    The web upload store de-duplicates same-name uploads as ``name_1.ext``,
    ``name_2.ext``… WITHIN one session — the recommended flow (measure
    transmission, then import the same images into background subtraction)
    re-uploads and therefore hits exactly this rename. The loose match strips
    that counter so ``direct_1.edf`` still finds the ``direct.edf`` entry.
    ``sample60.edf`` also strips (``sample.edf``); that is harmless because
    the stripped key must still exist on the other side AND the row's note
    discloses the fuzzy hit for the user to veto.
    从 basename 主干去掉一个尾部「_<短计数>」。web 上传目录在**同一会话内**
    把同名重传改名为 ``name_1.ext``、``name_2.ext``…——推荐流程（先测透过率、
    再把同一批图导入背景扣除）必然重传并触发该改名。宽松匹配剥掉这个计数，
    ``direct_1.edf`` 仍能找到 ``direct.edf`` 条目。``sample60.edf`` 也会被剥
    成 ``sample.edf``——无害：剥后的键必须在另一侧真实存在才命中，且行内
    note 会披露该模糊匹配，用户可否决。
    """
    stem, dot, ext = basename.rpartition(".")
    if not dot:
        stem, ext = basename, ""
    match = _CONFLICT_SUFFIX_RE.match(stem)
    if not match:
        return basename
    new_stem = match.group("stem")
    if not new_stem:
        return basename
    return f"{new_stem}.{ext}" if ext else new_stem


def match_transmission_entries(
    data_files: List[str], entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Match imported transmission entries to data files by basename.

    ``os.path.normcase`` is applied to both sides' basenames, so Windows
    paths differing only in case still match (on POSIX normcase is identity —
    the comparison then stays case-sensitive, which is the correct POSIX
    semantic). The first entry wins when several share a basename; that
    collision is reported in the row's ``note``. Unmatched files get
    ``transmission=None`` plus a bilingual note, so the UI can list them
    instead of silently defaulting to 1.0.

    When the exact basename misses, a LOOSE pass strips one upload-conflict
    counter suffix (``direct_1.edf`` → ``direct.edf``) from either side
    (see ``_strip_conflict_suffix``); loose hits are flagged in ``note`` so
    the user can veto a wrong fuzzy pairing in the match table.

    按 basename 把导入的透过率条目匹配回数据文件。两侧 basename 都过
    ``os.path.normcase``，Windows 下仅大小写不同的路径也能命中（POSIX 下
    normcase 为恒等，比较保持大小写敏感，符合 POSIX 语义）。多个条目同名时
    取第一个，并在该行 ``note`` 中注明；未命中文件 transmission=None 并附
    双语说明，供前端列出，而不是静默按 1.0 处理。精确未命中时再做一轮宽松
    匹配：剥掉任一侧的上传冲突计数后缀（``direct_1.edf`` → ``direct.edf``，
    见 ``_strip_conflict_suffix``）；宽松命中在 ``note`` 中标注，用户可在匹配
    表里否决错误的模糊配对。
    """
    index: Dict[str, Dict[str, Any]] = {}
    duplicated: set = set()
    loose_index: Dict[str, Dict[str, Any]] = {}
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        file_value = entry.get("file")
        if not isinstance(file_value, str) or not file_value:
            continue
        key = os.path.normcase(os.path.basename(file_value))
        if key in index:
            duplicated.add(key)
        else:
            index[key] = entry
        loose_key = os.path.normcase(_strip_conflict_suffix(os.path.basename(file_value)))
        if loose_key != key:
            loose_index.setdefault(loose_key, entry)

    _FUZZY_NOTE = (
        "Matched after ignoring an upload conflict suffix (_N) / "
        "忽略上传冲突后缀(_N)后匹配"
    )

    results: List[Dict[str, Any]] = []
    for data_file in data_files or []:
        path_value = str(data_file)
        base = os.path.basename(path_value)
        key = os.path.normcase(base)
        stripped_key = os.path.normcase(_strip_conflict_suffix(base))
        entry = index.get(key)
        fuzzy = False
        if entry is None:
            # Everything past the exact hit went through conflict-suffix
            # de-suffixing on at least one side — flag it for the user.
            # 精确未命中后的所有路径都至少对一侧做过冲突后缀剥离——标注给用户。
            fuzzy = True
            if stripped_key != key:
                entry = index.get(stripped_key)
            if entry is None:
                entry = loose_index.get(key) or loose_index.get(stripped_key)
        if entry is None:
            results.append({
                "data_file": path_value,
                "matched_file": "",
                "transmission": None,
                "note": (
                    "Not found in the transmission file / "
                    "未在透过率文件中找到匹配"
                ),
            })
            continue
        transmission = _as_float(entry.get("transmission"))
        if transmission is None:
            raise _bad(
                f"Transmission entry for {entry.get('file')!r} is not a finite "
                "number",
                f"条目 {entry.get('file')!r} 的透过率不是有限数值",
            )
        notes: List[str] = []
        if fuzzy:
            notes.append(_FUZZY_NOTE)
        if key in duplicated:
            notes.append(
                "Multiple entries share this basename — the first one is used / "
                "多个透过率条目同名，已取第一个"
            )
        results.append({
            "data_file": path_value,
            "matched_file": entry.get("file", ""),
            "transmission": transmission,
            "note": "；".join(notes),
        })
    return results
