#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Stitch service for X-FAIS.
X-FAIS 多探测器位置图像拼接服务模块。

Stitches multiple 2D detector images taken at different spatial positions
into a single large detector-like image using pixel offsets.
将多张不同空间位置的探测器二维图像，按像素偏移拼接为一张大探测器图像。

Algorithm / 算法:
    Each input image carries its own pixel size (µm/px) and an absolute
    spatial offset (X right, Y down, in µm). Offsets are converted to pixel
    offsets using each image's own pixel size, then placed onto a shared
    canvas. Overlapping regions are merged according to a strategy.
    每张输入图各自带有像素尺寸(µm/px)和绝对空间偏移(X向右、Y向下，µm单位)。
    偏移按各图自身像素尺寸换算为像素偏移，然后放置到公共画布上；
    重叠区域按指定策略合并。

    - "mean"  : average of all contributing pixels (sum / count)
    - "sum"   : plain sum of all contributing pixels
    - "max"   : element-wise maximum
    - "first" : first contributor wins (later overlaps ignored)

Pure numpy, no I/O, no WebSocket code — mirrors image_math.py style.
纯 numpy 实现，不包含文件 I/O 与 WebSocket 代码，风格与 image_math.py 一致。

Usage / 用法::

    from python.services.image_stitch import stitch

    images = [(img1, 172.0, 0.0, 0.0), (img2, 172.0, 1000.0, 0.0)]
    result, meta = stitch(images, strategy="mean")
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# HDF5 dead-pixel sentinel used by ImageLoader / ImageRenderer.
# ImageLoader / ImageRenderer 使用的 HDF5 死像素哨兵阈值。
_DEAD_PIXEL_SENTINEL = 4.29e9

# Guard against accidental huge canvas allocation.
# 防止意外分配过大画布的防护上限。
_MAX_CANVAS_PIXELS = 20000 * 20000  # ~1.6e9 px → ~6 GB float32

_VALID_STRATEGIES = ("mean", "sum", "max", "first")


# ---------------------------------------------------------------------------
# Core stitching / 核心拼接
# ---------------------------------------------------------------------------

def stitch(
    images: list[tuple[np.ndarray, float, float, float]],
    strategy: str = "mean",
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Stitch multiple 2D images onto a shared canvas using pixel offsets.
    使用像素偏移将多张二维图像拼接到公共画布。

    Parameters
    ----------
    images : list of (data, pixel_size_um, offset_x_um, offset_y_um)
        Each tuple is one detector image. Offsets are absolute, in microns,
        with X increasing rightward and Y increasing downward, relative to a
        common canvas origin. Relative offsets should be pre-accumulated into
        absolute form by the caller.
        每个元组为一张探测器图。偏移为绝对值，单位微米，X 向右、Y 向下增加，
        相对公共画布原点。相对偏移应由调用方预先累加为绝对坐标。
    strategy : str
        Overlap merge strategy: "mean", "sum", "max", or "first". Default "mean".
        重叠区合并策略："mean"（平均）、"sum"（求和）、"max"（取最大）、
        "first"（先到先得），默认 "mean"。

    Returns
    -------
    canvas : np.ndarray
        Stitched 2D image, float32. Uncovered pixels and dead-pixel sentinels
        are set to NaN.
        拼接后的二维图像，float32。未覆盖区域与死像素哨兵置为 NaN。
    meta : dict
        Metadata: canvas_width, canvas_height, n_images, strategy,
        coverage_ratio, overlaps.
        元数据：画布宽高、图数、策略、覆盖率、是否存在重叠。

    Raises
    ------
    ValueError
        If inputs are invalid (too few images, bad pixel size, huge canvas,
        unknown strategy).
        输入无效时抛出（图数过少、像素尺寸非法、画布过大、未知策略）。
    """
    if strategy not in _VALID_STRATEGIES:
        raise ValueError(
            f"strategy must be one of {_VALID_STRATEGIES}, got '{strategy}'. "
            f"strategy 必须为 {_VALID_STRATEGIES} 之一，当前值为 '{strategy}'。"
        )

    if not images or len(images) < 2:
        raise ValueError(
            "stitch requires at least 2 images. "
            "拼接至少需要 2 张图像。"
        )

    # --- 1. Compute pixel offsets and canvas bounds (in pixels) ---
    # 计算各图的像素偏移与画布边界（像素单位）
    placements: list[tuple[np.ndarray, int, int, np.ndarray]] = []  # (data, r0, c0, valid_mask)
    min_col = min_row = 0
    max_col_end = max_row_end = 0
    has_overlap = False

    for idx, item in enumerate(images):
        data, pixel_size_um, offset_x_um, offset_y_um = item

        if pixel_size_um is None or float(pixel_size_um) <= 0:
            raise ValueError(
                f"image #{idx + 1}: pixel_size_um must be > 0, got {pixel_size_um}. "
                f"第 {idx + 1} 张图：pixel_size_um 必须 > 0，当前值为 {pixel_size_um}。"
            )
        pixel_size_um = float(pixel_size_um)

        arr = np.asarray(data, dtype=np.float32)
        if arr.ndim != 2:
            # Squeeze trailing dims if higher-D; otherwise error.
            # 若为高维数组则尝试压缩尾部维度，否则报错。
            if arr.ndim >= 2:
                arr = arr.reshape(arr.shape[-2], arr.shape[-1])
            else:
                raise ValueError(
                    f"image #{idx + 1}: expected 2D data, got shape {arr.shape}. "
                    f"第 {idx + 1} 张图：需要二维数据，当前形状为 {arr.shape}。"
                )

        h, w = arr.shape
        col0 = int(round(float(offset_x_um) / pixel_size_um))
        row0 = int(round(float(offset_y_um) / pixel_size_um))

        # Valid mask: finite and not a dead-pixel sentinel.
        # 有效像素掩码：有限值且非死像素哨兵。
        valid = np.isfinite(arr) & (arr < _DEAD_PIXEL_SENTINEL) & (arr >= 0)

        placements.append((arr, row0, col0, valid))

        if idx == 0:
            min_col, min_row = col0, row0
            max_col_end, max_row_end = col0 + w, row0 + h
        else:
            min_col = min(min_col, col0)
            min_row = min(min_row, row0)
            max_col_end = max(max_col_end, col0 + w)
            max_row_end = max(max_row_end, row0 + h)

    # --- 2. Determine canvas size (origin normalized to 0,0) ---
    # 确定画布尺寸（原点归一化到 0,0）
    canvas_w = max_col_end - min_col
    canvas_h = max_row_end - min_row

    if canvas_w <= 0 or canvas_h <= 0:
        raise ValueError(
            f"invalid canvas size ({canvas_w}, {canvas_h}). "
            f"画布尺寸非法 ({canvas_w}, {canvas_h})。"
        )

    total_pixels = canvas_w * canvas_h
    if total_pixels > _MAX_CANVAS_PIXELS:
        raise ValueError(
            f"canvas too large: {canvas_w}x{canvas_h} = {total_pixels} px "
            f"(limit {_MAX_CANVAS_PIXELS}). "
            f"画布过大：{canvas_w}x{canvas_h} = {total_pixels} 像素（上限 {_MAX_CANVAS_PIXELS}）。"
        )

    logger.info(
        "stitch: canvas %dx%d, %d images, strategy=%s. "
        "拼接：画布 %dx%d，%d 张图，策略=%s。",
        canvas_w, canvas_h, len(placements), strategy,
        canvas_w, canvas_h, len(placements), strategy,
    )

    # --- 3. Accumulate onto canvas ---
    # 在画布上累加
    if strategy in ("mean", "sum"):
        sum_canvas = np.zeros((canvas_h, canvas_w), dtype=np.float32)
        count_canvas = np.zeros((canvas_h, canvas_w), dtype=np.uint16)

        for arr, row0, col0, valid in placements:
            r_off = row0 - min_row
            c_off = col0 - min_col
            h, w = arr.shape
            sub = sum_canvas[r_off:r_off + h, c_off:c_off + w]
            sub_count = count_canvas[r_off:r_off + h, c_off:c_off + w]
            contrib = np.where(valid, arr, 0.0).astype(np.float32)
            sub += contrib
            sub_count += valid.astype(np.uint16)

        covered = count_canvas > 0
        if strategy == "mean":
            # Avoid div-by-zero: only divide covered pixels.
            # 避免除零：仅对已覆盖像素做除法。
            canvas = np.full((canvas_h, canvas_w), np.nan, dtype=np.float32)
            canvas[covered] = sum_canvas[covered] / count_canvas[covered]
        else:  # sum
            canvas = np.full((canvas_h, canvas_w), np.nan, dtype=np.float32)
            canvas[covered] = sum_canvas[covered]

    elif strategy == "max":
        canvas = np.full((canvas_h, canvas_w), np.nan, dtype=np.float32)
        for arr, row0, col0, valid in placements:
            r_off = row0 - min_row
            c_off = col0 - min_col
            h, w = arr.shape
            sub = canvas[r_off:r_off + h, c_off:c_off + w]
            # For uncovered sub-pixels, treat as -inf so first valid value wins.
            # 对未覆盖子像素视为 -inf，使首个有效值胜出。
            masked = np.where(valid, arr, -np.inf).astype(np.float32)
            cur = np.where(np.isnan(sub), -np.inf, sub)
            merged = np.maximum(cur, masked)
            # Write back, keeping NaN where still -inf.
            # 写回；仍为 -inf 处保持 NaN。
            sub[:] = np.where(np.isfinite(merged), merged, np.nan)

    else:  # "first"
        canvas = np.full((canvas_h, canvas_w), np.nan, dtype=np.float32)
        filled = np.zeros((canvas_h, canvas_w), dtype=bool)
        for arr, row0, col0, valid in placements:
            r_off = row0 - min_row
            c_off = col0 - min_col
            h, w = arr.shape
            sub = canvas[r_off:r_off + h, c_off:c_off + w]
            sub_filled = filled[r_off:r_off + h, c_off:c_off + w]
            # Write only valid pixels not yet filled.
            # 仅写入有效且尚未填充的像素。
            write_mask = valid & (~sub_filled)
            sub[write_mask] = arr[write_mask]
            sub_filled |= write_mask

    # --- 4. Detect overlaps (count >= 2 anywhere) ---
    # 检测重叠（任意位置 count >= 2）
    if strategy in ("mean", "sum"):
        has_overlap = bool(np.any(count_canvas >= 2))
    else:
        # For max/first, detect overlap by checking placement geometry.
        # 对 max/first，通过几何重叠判断。
        overlap_acc = np.zeros((canvas_h, canvas_w), dtype=np.uint16)
        for _arr, row0, col0, _valid in placements:
            r_off = row0 - min_row
            c_off = col0 - min_col
            h, w = _arr.shape
            overlap_acc[r_off:r_off + h, c_off:c_off + w] += 1
        has_overlap = bool(np.any(overlap_acc >= 2))

    # --- 5. Coverage statistics ---
    # 覆盖率统计
    finite = np.isfinite(canvas)
    coverage_ratio = float(np.count_nonzero(finite)) / float(canvas.size)

    # Non-finite warning (excludes intended NaN background).
    # 非有限值警告（不包含预期的 NaN 背景）。
    n_bad_in_covered = 0
    if strategy in ("mean", "sum"):
        # Bad values within covered region.
        # 已覆盖区域内的坏值。
        bad_in_covered = covered & ~np.isfinite(canvas)
        n_bad_in_covered = int(np.count_nonzero(bad_in_covered))
    if n_bad_in_covered > 0:
        logger.warning(
            "stitch: %d non-finite values within covered region. "
            "已覆盖区域存在 %d 个非有限值。",
            n_bad_in_covered, n_bad_in_covered,
        )

    meta: dict[str, Any] = {
        "canvas_width": int(canvas_w),
        "canvas_height": int(canvas_h),
        "n_images": len(placements),
        "strategy": strategy,
        "coverage_ratio": coverage_ratio,
        "overlaps": has_overlap,
    }

    return canvas, meta
