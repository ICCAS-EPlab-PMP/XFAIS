#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
colormaps.py — Shared colormap definitions for viewer and PNG tool
共享色图定义 — 供查看器和PNG批量导出工具使用
"""

from __future__ import annotations

from typing import Any

import numpy as np
from matplotlib.colors import LinearSegmentedColormap

CMAP_FOXTROT: LinearSegmentedColormap = LinearSegmentedColormap.from_list(
    "smooth_WAXS_foxtrot",
    [(0.00, "black"), (0.25, "blue"), (0.50, (51 / 255, 1.0, 51 / 255)),
     (0.75, "yellow"), (1.00, "red")],
)

CMAP_FIT2D: LinearSegmentedColormap = LinearSegmentedColormap.from_list(
    "smooth_WAXS_fit2D",
    [(0.00, "black"), (0.20, "blue"), (0.40, (51 / 255, 1.0, 51 / 255)),
     (0.60, "yellow"), (0.80, "red"), (1.00, "white")],
)

_CUSTOM_CMAPS: dict[str, LinearSegmentedColormap] = {
    "smooth_WAXS_foxtrot": CMAP_FOXTROT,
    "smooth_WAXS_fit2D": CMAP_FIT2D,
}

CMAP_CHOICES: list[str] = [
    "smooth_WAXS_foxtrot", "smooth_WAXS_fit2D",
    "viridis", "plasma", "inferno", "magma",
    "hot", "gray", "seismic", "rainbow", "cool",
]


def build_cmap(name: str) -> Any:
    """Resolve a colourmap name to a Matplotlib colourmap object.
    将色图名称解析为Matplotlib色图对象。"""
    if name in _CUSTOM_CMAPS:
        return _CUSTOM_CMAPS[name]
    import matplotlib
    try:
        return matplotlib.colormaps[name]
    except KeyError:
        # Unknown colormap name → fallback to viridis / 未知色图名 → 回退到 viridis
        return matplotlib.colormaps["viridis"]


def get_cmap(name: str) -> Any:
    """Alias for build_cmap. 色图解析别名。"""
    return build_cmap(name)


def apply_colormap_pil(
    data_2d: np.ndarray,
    cmap_name: str,
    vmin: float,
    vmax: float,
    use_log: bool = False,
) -> np.ndarray:
    """Normalize data and apply matplotlib colormap, returning uint8 RGB array.
    归一化数据并应用 matplotlib 色图，返回 uint8 RGB 数组。

    Parameters / 参数
    ----------
    data_2d : ndarray
        2-D float array / 二维浮点数组。
    cmap_name : str
        Colormap name / 色图名称。
    vmin, vmax : float
        Contrast limits / 对比度范围。
    use_log : bool
        Apply log10 scaling before normalization / 归一化前应用 log10 缩放。

    Returns / 返回
    -------
    ndarray
        uint8 RGB array of shape (H, W, 3) / uint8 RGB 数组 (H, W, 3)。
    """
    d = np.asarray(data_2d, dtype=np.float64)
    cmap = build_cmap(cmap_name)

    if use_log:
        with np.errstate(divide="ignore", invalid="ignore"):
            dl = np.log10(np.where(d > 0, d, np.nan))
        lo = np.log10(max(vmin, 1e-6))
        hi = np.log10(max(vmax, 1e-5))
        span = hi - lo
        if span <= 0:
            span = 1e-15
        norm = np.clip((dl - lo) / span, 0, 1)
    else:
        span = vmax - vmin
        if span <= 0:
            span = 1.0
        norm = np.clip((d - vmin) / span, 0, 1)

    norm = np.nan_to_num(norm, nan=0.0)
    rgba = cmap(norm)
    return (rgba[:, :, :3] * 255).astype(np.uint8)


# Export alias for use in other modules / 导出别名供其他模块使用
CMAP_CHOICES_FOR_UI: list[str] = list(CMAP_CHOICES)
