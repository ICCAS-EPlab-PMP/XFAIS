#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_renderer.py — PIL-based image rendering with smart auto-contrast and XRD colormaps
PIL图像渲染器 — 智能自适应对比度与XRD色图支持

Provides fast server-side rendering of detector images to PNG bytes or base64
strings, bypassing the slow JSON pixel-array → Plotly pipeline.
提供快速的服务端探测器图像渲染，输出PNG字节或base64字符串，
绕过缓慢的 JSON 像素数组→Plotly 管道。
"""

from __future__ import annotations

import base64
from functools import lru_cache
import io
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .colormaps import build_cmap, get_cmap

# Sentinel value for H5 dead pixels / H5死像素哨兵值
_H5_DEAD_SENTINEL: float = 4.29e9


@lru_cache(maxsize=32)
def _get_cached_lut(cmap_name: str) -> np.ndarray:
    """Return a cached 256-color LUT for a named colormap.
    返回命名色图对应的缓存 256 色 LUT。"""
    cmap = build_cmap(cmap_name)
    return (cmap(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)


class ImageRenderer:
    """Pure-utility class for rendering detector images via PIL + NumPy.
    基于 PIL + NumPy 的探测器图像渲染纯工具类。

    All methods are ``@staticmethod`` / ``@classmethod`` — no instantiation.
    所有方法均为静态/类方法，无需实例化。
    """

    # ------------------------------------------------------------------
    # Public rendering API / 公共渲染接口
    # ------------------------------------------------------------------

    @staticmethod
    def render_png(data: np.ndarray, settings: dict) -> bytes:
        """Apply colormap + contrast to a 2D array and return PNG bytes.
        对二维数组应用色图和对比度，返回 PNG 字节。

        Parameters / 参数
        ----------
        data : ndarray
            2-D float array (raw detector frame).
            二维浮点数组（原始探测器帧）。
        settings : dict
            Keys: ``cmap`` (str or colormap object), ``use_log`` (bool),
            ``clim`` (tuple of vmin, vmax).
            键：``cmap``（字符串或色图对象）、``use_log``（布尔值）、
            ``clim``（vmin, vmax 元组）。

        Returns / 返回
        -------
        bytes
            PNG image data / PNG图像数据。
        """
        rgb = ImageRenderer._apply_colormap(data, settings)
        img = Image.fromarray(rgb)
        if settings.get("show_colorbar"):
            img = ImageRenderer._append_colorbar(img, settings)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    @staticmethod
    def render_thumbnail(
        data: np.ndarray,
        settings: dict,
        size: tuple[int, int] = (130, 130),
    ) -> str:
        """Render a small thumbnail and return base64-encoded PNG string.
        渲染小缩略图，返回 base64 编码的 PNG 字符串。

        Suitable for inline HTML ``<img src="data:image/png;base64,...">``.
        适合内联 HTML ``<img src="data:image/png;base64,...">``。

        Parameters / 参数
        ----------
        data : ndarray
            2-D float array / 二维浮点数组。
        settings : dict
            Same keys as :meth:`render_png` / 与 render_png 相同的键。
        size : tuple
            Maximum thumbnail dimensions (width, height).
            缩略图最大尺寸（宽，高）。

        Returns / 返回
        -------
        str
            Base64-encoded PNG string / base64 编码的 PNG 字符串。
        """
        rgb = ImageRenderer._apply_colormap(data, settings)
        img = Image.fromarray(rgb)
        img.thumbnail(size, Image.Resampling.NEAREST)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode()

    # ------------------------------------------------------------------
    # Contrast / statistics helpers / 对比度/统计辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def adjusted_max(data: np.ndarray) -> float:
        """Return the median of top-50 valid pixel values as a robust max.
        返回前50个有效像素值的中位数作为鲁棒最大值。

        Valid pixels: finite, >= 0, not H5 dead-pixel sentinel (4.29e9).
        有效像素：有限值、>=0、非H5死像素哨兵值(4.29e9)。
        """
        arr = np.asarray(data, dtype=np.float64).ravel()
        mask = np.isfinite(arr) & (arr >= 0) & (arr < _H5_DEAD_SENTINEL)
        valid = arr[mask]
        if valid.size == 0:
            return float("nan")
        n = min(50, valid.size)
        top = np.partition(valid, -n)[-n:]
        return float(np.median(np.sort(top)))

    @staticmethod
    def global_range(
        all_data: list[np.ndarray],
        use_log: bool,
    ) -> tuple[float, float]:
        """Compute sensible global contrast range across all frames.
        计算所有帧的合理全局对比度范围。

        Per-frame max is capped at 1_000_000 to suppress hot pixels.
        每帧最大值限制在 1_000_000 以压制热像素。

        Parameters / 参数
        ----------
        all_data : list[ndarray]
            List of 2-D frames / 二维帧列表。
        use_log : bool
            Whether log scaling will be used / 是否使用对数缩放。

        Returns / 返回
        -------
        tuple[float, float]
            (gmin, gmax) contrast range / 对比度范围。
        """
        gmin: float = float("inf")
        gmax: float = float("-inf")

        for frame in all_data:
            d = np.asarray(frame)
            adj = ImageRenderer.adjusted_max(d)
            # Cap hot pixels / 压制热像素
            cap = min(adj, 1_000_000) if not np.isnan(adj) and adj > 1_000_000 else adj

            if use_log:
                pos = d[d > 0]
                if pos.size > 0:
                    gmin = min(gmin, float(pos.min()))
            else:
                finite_min = float(np.nanmin(d))
                gmin = min(gmin, finite_min)

            if not np.isnan(cap):
                gmax = max(gmax, float(cap))

        # Fallbacks / 后备值
        if gmin == float("inf"):
            gmin = 1e-6 if use_log else 0.0
        if gmax == float("-inf"):
            gmax = 1.0
        # Ensure log mode gmin > 0 / 确保对数模式 gmin > 0
        if use_log and gmin <= 0:
            gmin = 1e-6
        if gmin >= gmax:
            gmax = gmin * 10 if use_log else gmin + 1.0

        return float(gmin), float(gmax)

    @staticmethod
    def compute_stats(data: np.ndarray) -> dict[str, float]:
        """Compute per-frame statistics using float32-safe operations.
        使用 float32 安全操作计算每帧统计信息。

        Returns / 返回
        -------
        dict
            Keys: ``min``, ``max``, ``adjustedMax``, ``std``.
        """
        arr = np.asarray(data, dtype=np.float32)
        finite = arr[np.isfinite(arr)]
        if finite.size == 0:
            return {
                "min": 0.0,
                "max": 0.0,
                "adjustedMax": 0.0,
                "std": 0.0,
            }
        return {
            "min": float(np.min(finite)),
            "max": float(np.max(finite)),
            "adjustedMax": float(ImageRenderer.adjusted_max(arr)),
            "std": float(np.std(finite)),
        }

    @staticmethod
    def get_default_settings() -> dict[str, Any]:
        """Return default rendering settings.
        返回默认渲染设置。"""
        return {
            "cmap": "viridis",
            "use_log": False,
            "clim": (0.0, 1.0),
        }

    # ------------------------------------------------------------------
    # Internal helpers / 内部辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_colormap(data: np.ndarray, settings: dict) -> np.ndarray:
        """Normalize + apply colormap → uint8 RGB array (H, W, 3).
        归一化 + 应用色图 → uint8 RGB 数组 (H, W, 3)。

        Delegates to the fast LUT path by default.
        默认委托给快速 LUT 路径。
        """
        return ImageRenderer._apply_colormap_lut(data, settings)

    @staticmethod
    def _apply_colormap_lut(data: np.ndarray, settings: dict) -> np.ndarray:
        """Normalize + apply colormap via numpy LUT indexing (15-25× faster than cmap()).
        通过 numpy LUT 索引归一化并应用色图（比 cmap() 快 15-25 倍）。

        Pre-computes a 256-color LUT from the matplotlib colormap, then maps
        normalized pixel values to indices 0-255 and applies C-speed vectorized
        indexing — no per-pixel Python overhead.
        预计算色图的 256 色 LUT，然后将归一化像素值映射到 0-255 索引，
        通过 C 速度向量化索引应用，无逐像素 Python 开销。
        """
        d = np.asarray(data, dtype=np.float64)
        if d.ndim != 2:
            d = d.squeeze()
            if d.ndim != 2:
                d = d[0] if d.ndim > 2 else d

        cmap_name = settings.get("cmap", "viridis")
        use_log = settings.get("use_log", False)
        vmin, vmax = settings.get("clim", (0.0, 1.0))

        # Resolve colormap / 解析色图
        if isinstance(cmap_name, str):
            lut = _get_cached_lut(cmap_name)
            cmap = None
        else:
            cmap = cmap_name
            lut = (cmap(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)

        # Normalize to [0, 1] / 归一化到 [0, 1]
        if use_log:
            with np.errstate(divide="ignore", invalid="ignore"):
                dl = np.log10(np.where(d > 0, d, np.nan))
            lo = np.log10(max(vmin, 1e-6))
            hi = np.log10(max(vmax, 1e-5))
            norm = np.clip((dl - lo) / (hi - lo + 1e-15), 0, 1)
        else:
            span = vmax - vmin
            if span <= 0:
                span = 1.0
            norm = np.clip((d - vmin) / span, 0, 1)

        # Handle NaN → 0 / 处理 NaN → 0
        norm = np.nan_to_num(norm, nan=0.0)

        # Map normalized [0,1] → indices [0,255] → C-speed LUT lookup
        # 将归一化 [0,1] 映射到索引 [0,255] → C 速度 LUT 查找
        indices = np.clip(norm * 255, 0, 255).astype(np.uint8)
        rgb = lut[indices]
        return rgb

    @staticmethod
    def _append_colorbar(image: Image.Image, settings: dict) -> Image.Image:
        """Append a readable colorbar panel to the rendered image.
        为渲染结果追加清晰可读的色条面板。"""
        width, height = image.size
        panel_width = max(72, min(110, width // 5))
        padding = 10
        bar_width = 22
        bar_height = max(64, height - padding * 2)
        bar_x = padding + 8
        bar_y = padding

        canvas = Image.new("RGB", (width + panel_width, height), (15, 23, 42))
        canvas.paste(image, (0, 0))

        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()

        lut = _get_cached_lut(str(settings.get("cmap", "viridis")))
        gradient = np.zeros((bar_height, bar_width, 3), dtype=np.uint8)
        for row in range(bar_height):
            idx = int(round((1 - row / max(bar_height - 1, 1)) * 255))
            gradient[row, :, :] = lut[idx]
        gradient_image = Image.fromarray(gradient)
        canvas.paste(gradient_image, (width + bar_x, bar_y))

        outline_box = [width + bar_x, bar_y, width + bar_x + bar_width, bar_y + bar_height]
        draw.rounded_rectangle(outline_box, radius=4, outline=(148, 163, 184), width=1)

        tick_positions = [0.25, 0.5, 0.75]
        for ratio in tick_positions:
            y = bar_y + int(bar_height * ratio)
            draw.line(
                [(width + bar_x - 6, y), (width + bar_x + bar_width + 6, y)],
                fill=(226, 232, 240),
                width=1,
            )

        use_log = bool(settings.get("use_log", False))
        vmin, vmax = settings.get("clim", (0.0, 1.0))
        if use_log:
            top_label = f"{float(vmax):.2e}"
            bottom_label = f"{float(vmin):.2e}"
        else:
            top_label = f"{float(vmax):.3g}"
            bottom_label = f"{float(vmin):.3g}"

        draw.text((width + panel_width - 8, bar_y - 2), top_label, fill=(226, 232, 240), font=font, anchor="ra")
        draw.text((width + panel_width - 8, bar_y + bar_height - 8), bottom_label, fill=(226, 232, 240), font=font, anchor="ra")
        return canvas

    @staticmethod
    def render_png_mpl(
        data: np.ndarray,
        cmap_name: str = "viridis",
        use_log: bool = False,
        clim: tuple[float, float] | None = None,
        dpi: int = 100,
    ) -> bytes:
        """Render PNG with matplotlib colorbar (publication-quality).
        使用 matplotlib 渲染带色条的 PNG（出版质量）。"""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import LogNorm, Normalize

        d = np.asarray(data, dtype=np.float64)
        if d.ndim != 2:
            d = d.squeeze()
            if d.ndim != 2:
                d = d[0] if d.ndim > 2 else d

        if clim is None:
            stats = ImageRenderer.compute_stats(data)
            clim = (float(stats["min"]), float(stats["adjustedMax"] or stats["max"]))

        vmin, vmax = clim
        cmap = build_cmap(cmap_name) if isinstance(cmap_name, str) else cmap_name

        h, w = d.shape
        figsize_w = max(4, w / 100)
        figsize_h = max(3, h / 100)

        fig, ax = plt.subplots(figsize=(figsize_w, figsize_h))
        ax.axis("off")

        if use_log:
            norm = LogNorm(vmin=max(vmin, 1e-6), vmax=max(vmax, vmin * 10))
            im = ax.imshow(d, cmap=cmap, norm=norm, interpolation="nearest", origin="lower")
            label = "Log Intensity"
        else:
            im = ax.imshow(d, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest", origin="lower")
            label = "Intensity"

        fig.colorbar(im, ax=ax, label=label, shrink=0.85)

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", pad_inches=0.05)
        plt.close(fig)
        return buf.getvalue()
