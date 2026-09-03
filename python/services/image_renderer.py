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

# Matplotlib mathtext axis labels for fiber units (mirrors frontend UNIT_LABELS).
# Keyed by the raw pyFAI unit string sent from the frontend.
# 纤维单位的 matplotlib mathtext 坐标轴标签（与前端 UNIT_LABELS 对应）。
_FIBER_UNIT_MPL_LABELS: dict[str, str] = {
    "qip_nm^-1":                r"$q_{ip}$ ($nm^{-1}$)",
    "qoop_nm^-1":               r"$q_{oop}$ ($nm^{-1}$)",
    "qip_A^-1":                 r"$q_{ip}$ ($\AA^{-1}$)",
    "qoop_A^-1":                r"$q_{oop}$ ($\AA^{-1}$)",
    "qxgi_nm^-1":               r"$q_{xgi}$ ($nm^{-1}$)",
    "qygi_nm^-1":               r"$q_{ygi}$ ($nm^{-1}$)",
    "qzgi_nm^-1":               r"$q_{zgi}$ ($nm^{-1}$)",
    "qtot_nm^-1":               r"$q_{tot}$ ($nm^{-1}$)",
    "qxgi_A^-1":                r"$q_{xgi}$ ($\AA^{-1}$)",
    "qygi_A^-1":                r"$q_{ygi}$ ($\AA^{-1}$)",
    "qzgi_A^-1":                r"$q_{zgi}$ ($\AA^{-1}$)",
    "qtot_A^-1":                r"$q_{tot}$ ($\AA^{-1}$)",
    "scattering_angle_horz_rad": r"$2\theta_{horz}$ ($rad$)",
    "scattering_angle_vert_rad": r"$2\theta_{vert}$ ($rad$)",
    "exit_angle_horz_rad":      r"$\alpha_{horz}$ ($rad$)",
    "exit_angle_vert_rad":      r"$\alpha_{vert}$ ($rad$)",
    "exit_angle_horz_deg":      r"$\alpha_{horz}$ ($\degree$)",
    "exit_angle_vert_deg":      r"$\alpha_{vert}$ ($\degree$)",
    "chigi_rad":                r"$\chi_{gi}$ ($rad$)",
    "chigi_deg":                r"$\chi_{gi}$ ($\degree$)",
}


def _fiber_unit_label(unit: str | None) -> str:
    """Resolve a fiber unit key to a matplotlib mathtext axis label.
    将纤维单位键解析为 matplotlib mathtext 坐标轴标签。"""
    if not unit:
        return ""
    return _FIBER_UNIT_MPL_LABELS.get(str(unit), str(unit).replace("_", " "))


def _bold_mathtext(text: str) -> str:
    """Make a mathtext-containing label bold.

    matplotlib ignores ``fontweight='bold'`` for ``$...$`` mathtext segments,
    so we wrap the inner content of every ``$...$`` block in ``\\boldsymbol{}``
    (works for Latin letters, Greek symbols like ``\\theta``, and units like
    ``\\AA`` under the default mathtext fontset). Non-mathtext fragments are
    left untouched — they already respond to ``fontweight``.

    matplotlib 对 ``$...$`` mathtext 段会忽略 ``fontweight='bold'``，故将每个
    ``$...$`` 块的内部内容包裹进 ``\\boldsymbol{}``（在默认 mathtext fontset 下
    兼容拉丁字母、``\\theta`` 等希腊符号与 ``\\AA`` 等单位）。
    """
    import re

    def _wrap(match: re.Match) -> str:
        inner = match.group(1)
        return r"$\boldsymbol{" + inner + r"}$"

    return re.sub(r"\$(.*?)\$", _wrap, text)


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
    def render_mask_png(
        mask: np.ndarray,
        fill_rgba: tuple[int, int, int, int] = (128, 128, 128, 90),
        edge_rgba: tuple[int, int, int, int] = (30, 30, 30, 217),
        edge_width: int = 1,
    ) -> bytes:
        """Render a boolean mask as a transparent PNG with fill + dark edge.

        将布尔遮罩渲染为透明 PNG（半透明填充 + 深色边界线）。

        Used to overlay the selected azimuthal-range wedge on a detector image.
        The mask pixels are filled with a semi-transparent gray, and the outer
        boundary band (``edge_width`` px wide, computed by morphological
        dilation) is overdrawn with a dark edge color for clarity.

        用于在探测器图上叠加用户选择的方位角范围。遮罩区域填充半透明灰色，
        外缘 ``edge_width`` 像素宽的边界带（由形态学膨胀求得）用深色描边以增强可见性。

        Parameters / 参数
        ----------
        mask : ndarray
            2-D boolean array (True = inside the selection).
            二维布尔数组（True = 选中区域内）。
        fill_rgba : tuple
            Fill color (R, G, B, A) for inside-mask pixels.
            遮罩内部填充色 (R, G, B, A)。
        edge_rgba : tuple
            Edge color (R, G, B, A) for the boundary band.
            边界带颜色 (R, G, B, A)。
        edge_width : int
            Boundary band thickness in pixels.
            边界带厚度（像素）。

        Returns / 返回
        -------
        bytes
            PNG image data (RGBA, same H×W as ``mask``; fully transparent where
            the mask is False).
            PNG 图像数据（RGBA，与 ``mask`` 同 H×W；遮罩为 False 处全透明）。
        """
        m = np.asarray(mask, dtype=bool)
        if m.ndim != 2:
            raise ValueError(f"mask must be 2-D, got shape {m.shape}")

        h, w = m.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)

        if m.any():
            # Boundary band: pixels just outside the mask (morphological gradient).
            # Use scipy if available for robust dilation; fall back to a numpy
            # max-filter approximation (slower but dependency-free).
            # 边界带：遮罩外缘的像素（形态学梯度）。优先 scipy，回退 numpy 最大滤波。
            eroded = ImageRenderer._erode_mask(m, iterations=edge_width)
            edge = m & ~eroded  # inner ring of `edge_width` px → crisp outline / 内缘环

            rgba[m] = fill_rgba
            rgba[edge] = edge_rgba

        img = Image.fromarray(rgba, mode="RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return buf.getvalue()

    @staticmethod
    def _erode_mask(mask: np.ndarray, iterations: int = 1) -> np.ndarray:
        """Erode a boolean mask by ``iterations`` pixels.

        将布尔遮罩腐蚀 ``iterations`` 个像素。

        Uses scipy.ndimage when available (fast C implementation); otherwise
        falls back to a numpy-based repeated minimum-filter that needs no extra
        dependency.
        优先使用 scipy.ndimage（C 实现，快）；否则回退到基于 numpy 的重复最小滤波，
        无需额外依赖。
        """
        if iterations <= 0:
            return mask.copy()
        try:
            from scipy.ndimage import binary_erosion

            return binary_erosion(mask, iterations=iterations)
        except Exception:
            # Dependency-free fallback / 无依赖回退
            out = mask.copy()
            for _ in range(iterations):
                up = np.zeros_like(out)
                up[1:, :] = out[:-1, :]
                down = np.zeros_like(out)
                down[:-1, :] = out[1:, :]
                left = np.zeros_like(out)
                left[:, 1:] = out[:, :-1]
                right = np.zeros_like(out)
                right[:, :-1] = out[:, 1:]
                out = out & up & down & left & right
            return out

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
        log_floor = settings.get("log_floor")

        # Resolve colormap / 解析色图
        if isinstance(cmap_name, str):
            lut = _get_cached_lut(cmap_name)
            cmap = None
        else:
            cmap = cmap_name
            lut = (cmap(np.linspace(0, 1, 256))[:, :3] * 255).astype(np.uint8)

        # Normalize to [0, 1] / 归一化到 [0, 1]
        if use_log:
            # When log_floor is set, clamp finite sub-floor values (including 0)
            # to the floor so they map to a real low color instead of being
            # collapsed to NaN (darkest). True NaN stays NaN -> nan_to_num -> 0.
            # log_floor 设置时，将有限的小于阈值的值（含 0）clamp 到阈值，
            # 映射到真实低色而非被压缩为 NaN（最暗色）。
            # 真 NaN 保持 NaN -> nan_to_num -> 0，与 clamp 值区分。
            if log_floor is not None and float(log_floor) > 0:
                floor = float(log_floor)
                d_clamped = d.copy()
                finite = np.isfinite(d_clamped)
                d_clamped[finite & (d_clamped < floor)] = floor
            else:
                d_clamped = d
            with np.errstate(divide="ignore", invalid="ignore"):
                dl = np.log10(np.where(d_clamped > 0, d_clamped, np.nan))
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
        axis_ip: np.ndarray | None = None,
        axis_oop: np.ndarray | None = None,
        unit_ip: str = "qip_nm^-1",
        unit_oop: str = "qoop_nm^-1",
        show_labels: bool = True,
        font_size: int = 12,
        title: str | None = None,
        no_data_bg: str = "white",
        show_colorbar: bool = True,
        border_width: float = 1.0,
        edge_color: str = "black",
        x_label: str | None = None,
        y_label: str | None = None,
        font_family: str | None = None,
        show_axis_title: bool = True,
        show_ticks: bool = True,
        title_bold: bool = False,
        axis_title_bold: bool = False,
        tick_bold: bool = False,
        flip_x: bool = True,
        flip_y: bool = True,
        log_floor: float | None = None,
        x_tick_step: float | None = None,
        y_tick_step: float | None = None,
    ) -> bytes:
        """Render PNG with matplotlib colorbar + optional axis labels.
        使用 matplotlib 渲染带色条和可选坐标轴标注的 PNG（出版质量）。

        Parameters / 参数
        ----------
        axis_ip, axis_oop : ndarray | None
            1-D coordinate arrays for axis tick labels. When provided
            together with ``show_labels=True``, the plot includes labelled
            x (qip) and y (qoop) axes instead of ``ax.axis("off")``.
            一维坐标数组，用于坐标轴刻度标签。
        unit_ip, unit_oop : str
            Axis unit strings shown in axis labels.
            坐标轴单位字符串。
        show_labels : bool
            Whether to draw axis labels and ticks.
            是否绘制坐标轴标签和刻度。
        font_size : int
            Base font size for labels and ticks.
            标签和刻度的基础字号。
        title : str | None
            Optional plot title.
            可选图表标题。
        no_data_bg : str
            Fill for no-data (NaN / non-finite) pixels and the figure
            background. One of ``"transparent"``, ``"white"``, ``"black"``.

            - ``"white"`` (default): NaN pixels filled white, white figure
              background. Keeps readable axes/colorbar on white.
              NaN 像素填充白色，图底白色。
            - ``"black"``: NaN pixels filled black, white figure background
              (Origin-style).
              NaN 像素填充黑色，图底仍为白色（Origin 风格）。
            - ``"transparent"``: NaN pixels transparent AND the whole figure
              background transparent (so axes/labels/colorbar float with no
              fill, ideal for overlaying on slides/Origin). Saved with
              ``transparent=True``.
              NaN 像素透明且整图背景透明，方便叠加到 PPT/Origin 等图层。

            无数据（NaN/非有限）像素及图背景的填充方式，取值为
            ``"transparent"``、``"white"``、``"black"``。
        show_colorbar : bool
            Whether to append the colorbar. Default ``True``.
            是否绘制色条，默认绘制。
        border_width : float
            Thickness of the spine/axes border drawn around the image, in
            points. ``0`` hides the border. Default ``1.0``.
            图像四周坐标轴边框粗细（磅），``0`` 为无边框，默认 ``1.0``。
        edge_color : str
            Color of the border spines and tick labels, e.g. ``"black"``,
            ``"white"``, ``"#1f2937"``. Default ``"black"``.
            边框与刻度颜色，如 ``"black"``、``"white"``、``"#1f2937"``，默认黑色。
        x_label, y_label : str | None
            Custom axis title text. When provided, overrides the unit-derived
            label (``_fiber_unit_label``). Empty string ``""`` hides the title.
            自定义 x/y 轴标题文字；提供时覆盖单位推导的标签，空串则隐藏标题。
        font_family : str | None
            Matplotlib font family for all text, e.g. ``"Arial"``,
            ``"Times New Roman"``. ``None`` keeps the matplotlib default.
            全局字体族，如 ``"Arial"``、``"Times New Roman"``。
        show_axis_title : bool
            Whether to draw the x/y axis title text (kept separate from ticks).
            Default ``True``. Ignored when ``show_labels`` is False.
            是否绘制 x/y 轴标题文字（与刻度独立），默认绘制。
        show_ticks : bool
            Whether to draw axis tick marks and numbers. Default ``True``.
            Ignored when ``show_labels`` is False.
            是否绘制刻度线与数值，默认绘制。
        title_bold, axis_title_bold, tick_bold : bool
            Independent bold toggles for the plot title, the x/y axis titles,
            and the tick numbers respectively. Default all ``False``.
            标题、x/y 轴标题、刻度数字的独立加粗开关，默认均不加粗。
        flip_x, flip_y : bool
            Reverse the x / y axis direction (both the array and the extent),
            default ``True``. Matches the orientation convention where the
            raw integration array needs to be flipped to match the physical
            sample frame (e.g. sample orientation 0 vs 4).
            反转 x / y 轴方向（数组与 extent 同时翻转），默认均翻转。
        """
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import LogNorm, Normalize
        from matplotlib.ticker import MaxNLocator, MultipleLocator, ScalarFormatter

        d = np.asarray(data, dtype=np.float64)
        if d.ndim != 2:
            d = d.squeeze()
            if d.ndim != 2:
                d = d[0] if d.ndim > 2 else d

        # Apply font family globally for this figure / 设置全局字体
        if font_family:
            matplotlib.rcParams["font.family"] = font_family

        if clim is None:
            stats_ = ImageRenderer.compute_stats(data)
            clim = (float(stats_["min"]), float(stats_["adjustedMax"] or stats_["max"]))

        vmin, vmax = clim
        cmap = build_cmap(cmap_name) if isinstance(cmap_name, str) else cmap_name

        # Normalize no_data_bg option (tolerate variants) / 归一化无数据填充选项（容错）
        bg = str(no_data_bg).strip().lower()
        if bg not in ("transparent", "white", "black"):
            bg = "white"

        # Mark non-finite / negative-for-log pixels as NaN so set_bad controls
        # their appearance. Copy the colormap so we never mutate a cached shared
        # object (build_cmap returns shared LinearSegmentedColormap instances).
        # 将非有限（及对数模式下的非正）像素标记为 NaN，由 set_bad 控制其外观。
        # 拷贝色图以免修改共享缓存对象。
        d = d.copy()
        d[~np.isfinite(d)] = np.nan
        if use_log:
            if log_floor is not None and float(log_floor) > 0:
                # Clamp finite sub-floor values (including 0) to the floor so
                # they render as a real low color. True NaN stays NaN -> set_bad.
                # This lets users distinguish "low signal clamped" from
                # "integration gap (NaN)" by color.
                # 将有限的小于阈值的值（含 0）clamp 到阈值，渲染为真实低色。
                # 真 NaN 保持 NaN -> set_bad，使用户能通过颜色区分
                # "低信号被 clamp"与"积分空洞 (NaN)"。
                floor = float(log_floor)
                finite = np.isfinite(d)
                d[finite & (d < floor)] = floor
            else:
                d[d <= 0] = np.nan
        cmap = cmap.copy()
        if bg == "transparent":
            cmap.set_bad(alpha=0)  # transparent NaN pixels / NaN 像素透明
        elif bg == "black":
            cmap.set_bad(color="black")
        else:
            cmap.set_bad(color="white")

        h, w = d.shape
        figsize_w = max(4, w / 100)
        figsize_h = max(3, h / 100)

        fig, ax = plt.subplots(figsize=(figsize_w, figsize_h))

        if bg == "transparent":
            fig.patch.set_alpha(0)
            ax.set_facecolor("none")

        # Set up axis extent if labels are requested / 如需要则设置坐标轴范围
        has_axes = (
            show_labels
            and axis_ip is not None
            and axis_oop is not None
            and len(axis_ip) > 0
            and len(axis_oop) > 0
        )
        if has_axes:
            # Apply axis flips: reverse array rows/cols AND swap extent endpoints
            # so tick numbers run in the flipped direction. extent = [left, right, bottom, top].
            # 应用轴反转：同时翻转数组行列与 extent 端点，使刻度数值方向随之反转。extent=[左,右,下,上]。
            if flip_x:
                d = d[:, ::-1]
            if flip_y:
                d = d[::-1, :]
            x0, x1 = float(axis_ip[0]), float(axis_ip[-1])
            y0, y1 = float(axis_oop[0]), float(axis_oop[-1])
            left, right = (x1, x0) if flip_x else (x0, x1)
            bottom, top = (y1, y0) if flip_y else (y0, y1)
            extent = [left, right, bottom, top]
        else:
            extent = None
            ax.axis("off")

        if use_log:
            norm = LogNorm(vmin=max(vmin, 1e-6), vmax=max(vmax, vmin * 10))
            im = ax.imshow(d, cmap=cmap, norm=norm, interpolation="nearest",
                           origin="lower", extent=extent, aspect="auto")
            cbar_label = "Log Intensity"
        else:
            im = ax.imshow(d, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest",
                           origin="lower", extent=extent, aspect="auto")
            cbar_label = "Intensity"

        # Resolve bold weight strings once / 一次性解析加粗字重
        title_fw = "bold" if title_bold else "normal"
        axis_fw = "bold" if axis_title_bold else "normal"

        if has_axes:
            # Resolve axis titles: custom override wins, else unit-derived label.
            # Bold mathtext labels by wrapping in \boldsymbol{} (fontweight is
            # ignored for $...$ mathtext).
            # 解析轴标题：自定义优先，否则按单位推导。
            # mathtext 标签加粗需包裹 \boldsymbol{}（fontweight 对 $...$ 无效）。
            xtext = x_label if x_label is not None else _fiber_unit_label(unit_ip)
            ytext = y_label if y_label is not None else _fiber_unit_label(unit_oop)
            if axis_title_bold:
                xtext = _bold_mathtext(xtext)
                ytext = _bold_mathtext(ytext)
            # X axis (qip) / X 轴 (qip)
            if show_axis_title and xtext:
                ax.set_xlabel(xtext, fontsize=font_size, color=edge_color, fontweight=axis_fw)
            if x_tick_step is not None and float(x_tick_step) > 0:
                ax.xaxis.set_major_locator(MultipleLocator(float(x_tick_step)))
            else:
                ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
            ax.xaxis.set_major_formatter(ScalarFormatter(useMathText=True))
            ax.tick_params(axis="x", labelsize=font_size - 2, colors=edge_color)
            # Y axis (qoop) / Y 轴 (qoop)
            if show_axis_title and ytext:
                ax.set_ylabel(ytext, fontsize=font_size, color=edge_color, fontweight=axis_fw)
            if y_tick_step is not None and float(y_tick_step) > 0:
                ax.yaxis.set_major_locator(MultipleLocator(float(y_tick_step)))
            else:
                ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
            ax.yaxis.set_major_formatter(ScalarFormatter(useMathText=True))
            ax.tick_params(axis="y", labelsize=font_size - 2, colors=edge_color)
            # Optionally hide tick marks + numbers while keeping the title / 可隐藏刻度仅留标题
            if not show_ticks:
                ax.tick_params(axis="both", which="both", length=0, labelbottom=False, labelleft=False)
            elif tick_bold:
                for lbl in list(ax.get_xticklabels()) + list(ax.get_yticklabels()):
                    lbl.set_fontweight("bold")
            if title:
                ax.set_title(title, fontsize=font_size + 2, color=edge_color, fontweight=title_fw)
        elif title:
            fig.suptitle(title, fontsize=font_size + 2, color=edge_color, fontweight=title_fw)

        # Border spines around the image / 图像四周边框
        if border_width > 0:
            for spine in ax.spines.values():
                spine.set_linewidth(border_width)
                spine.set_edgecolor(edge_color)
            # Ensure spines are visible even when has_axes is False / 无坐标轴时也显示边框
            if not has_axes:
                for spine in ax.spines.values():
                    spine.set_visible(True)

        # Optional colorbar / 可选色条
        if show_colorbar:
            cbar = fig.colorbar(im, ax=ax, label=cbar_label, shrink=0.85)
            cbar.ax.tick_params(labelsize=font_size - 2, colors=edge_color)
            cbar.set_label(cbar_label, fontsize=font_size, color=edge_color)
            # Colorbar border to match / 色条边框同色
            for spine in cbar.ax.spines.values():
                spine.set_edgecolor(edge_color)
                spine.set_linewidth(border_width)

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.1,
            transparent=(bg == "transparent"),
        )
        plt.close(fig)
        return buf.getvalue()
