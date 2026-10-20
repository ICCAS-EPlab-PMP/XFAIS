#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Curve fitting service (1-D diffraction peak fitting) for X-FAIS.
X-FAIS 一维衍射曲线拟合服务模块。

Interactive peak fitting on a 1-D diffraction profile, organised after the
classic four-stage workflow (prepare → place peaks → fit → review):
对一维衍射曲线做交互式峰拟合，流程沿经典四段式（预处理 → 放峰 → 拟合 → 复查）：

    1. region     — crop the profile to a fit window (选区)
    2. smoothing  — Savitzky–Golay / moving average / median filter (平滑)
    3. background — polynomial / iterative-polynomial / SNIP baseline (背景)
    4. peaks      — sum of peak shapes refined by Levenberg–Marquardt
                    against the (optionally smoothed, background-modelled)
                    profile, with per-parameter locks (峰拟合)

Peak shapes (6) / 峰形（6 种）:
    gaussian      y = h·exp(−½((x−c)/σ)²),           σ = fwhm/2.3548
    lorentzian    y = h/(1+((x−c)/γ)²),              γ = fwhm/2 (HWHM)
    pseudo_voigt  y = h·[η·L(fwhm) + (1−η)·G(fwhm)]  (Thompson–Cox–Hastings)
    pearson7      y = h·[1+4(2^(1/m)−1)((x−c)/w)²]^(−m),  w = fwhm
    voigt         G⊗L with an FWHM-consistent σ/κ split (w = effective FWHM)
    lognormal     y = h·exp(−½(ln(x/c)/w)²),          peak at x = c (x > 0)

All shapes are parameterised by (center, height, FWHM [, shape]) so the UI
table stays uniform; FWHM/area are reported analytically wherever a closed
form exists (numerical Simpson otherwise).
所有峰形统一以（中心、峰高、FWHM[、形状]）参数化，界面表格保持一致；
FWHM 与面积在存在闭式解处解析计算，其余用 Simpson 数值积分。

Method references (published literature only; every formula below is
re-implemented from its paper — no third-party or decompiled code) /
方法参考（仅公开文献；下列公式均按原文重实现，不含任何第三方或反编译代码）:
    - Savitzky & Golay, Anal. Chem. 36 (1964) 1627 — smoothing.
    - Thompson, Cox & Hastings, J. Appl. Cryst. 20 (1987) 79 — pseudo-Voigt.
    - Olivero & Longbothum, JQSRT 17 (1977) 233 — Voigt FWHM ≈
      0.5346·fL + sqrt(0.2166·fL² + fG²) and its inversion used here.
    - C.G. Ryan et al., Nucl. Instrum. Methods B34 (1988) 396 — SNIP
      baseline (LLS transform + decreasing-window clipping).
    - Lieber & Mahadevan-Jansen, Appl. Spectrosc. 57 (2003) 1363 —
      iterative polynomial baseline (ModPoly lineage, min-clip variant).
    - Pearson type VII distribution (Student-t family) for pearson7.
    - Levenberg–Marquardt / TRF via scipy.optimize.least_squares (MINPACK
      lineage, BSD-3-Clause); special functions via scipy.special.

Interaction-study credit: the workflow (per-parameter locks, joint
background+peak refinement, live model evaluation without fitting, residual
review) follows the interaction study of PeakFit 4.12 (Systat) documented in
the project research notes; only the ideas are used — no PeakFit code,
binaries or assets are involved.
交互研究致谢：工作流（参数锁定、背景与峰联合精修、改参即时求值不拟合、
残差复查）参考了项目调研笔记中关于 PeakFit 4.12（Systat）的交互研究；
仅采用其思路，不涉及其代码、二进制或素材。

Pure numpy/scipy, no I/O, no WebSocket code.
纯 numpy/scipy 实现，不含文件 I/O 与 WebSocket 代码。

Usage / 用法::

    from python.services.curve_fitting import fit_curve

    result = fit_curve(
        q, intensity,
        region={"min": 0.15, "max": 1.2},
        smoothing={"method": "savgol", "window": 11, "poly_order": 3},
        background={"method": "iterative", "order": 2, "iterations": 40,
                    "refine": True},
        peaks=[{"type": "pseudo_voigt", "center": 0.5, "height": 100.0,
                "fwhm": 0.08, "shape": 0.5,
                "locks": {"center": False, "height": False,
                          "fwhm": False, "shape": False}}],
        options={"max_iterations": 500, "loss": "linear"},
    )
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np
from scipy.integrate import simpson
from scipy.ndimage import median_filter, uniform_filter1d
from scipy.optimize import least_squares
from scipy.signal import find_peaks, peak_widths, savgol_filter
from scipy.special import gamma as _gamma_fn
from scipy.special import wofz

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / 常量
# ---------------------------------------------------------------------------

# Peak shape registry / 峰形注册表。
PEAK_TYPES = ("gaussian", "lorentzian", "pseudo_voigt", "pearson7", "voigt", "lognormal")
# Shapes that carry a fourth "shape" parameter / 带第四个「形状」参数的峰形。
SHAPE_TYPES = ("pseudo_voigt", "pearson7", "voigt", "lognormal")
# Default shape value when the caller omits it / 调用方未提供形状时的默认值。
SHAPE_DEFAULTS: dict[str, float] = {
    "pseudo_voigt": 0.5,
    "pearson7": 2.0,
    "voigt": 0.5,
    "lognormal": 0.3,
}
# Shape bounds (identical in scaled and original space) / 形状参数边界。
SHAPE_BOUNDS: dict[str, tuple[float, float]] = {
    "pseudo_voigt": (0.0, 1.0),      # η: 0 = pure Gaussian, 1 = pure Lorentzian
    "pearson7": (0.6, 64.0),         # m: 1 = Lorentzian, larger → Gaussian-like
    "voigt": (0.0, 1.0),             # κ: Lorentz share of the FWHM budget
    "lognormal": (0.01, 8.0),        # w: log-width
}
SMOOTH_METHODS = ("none", "savgol", "moving_average", "median")
BACKGROUND_METHODS = ("none", "polynomial", "iterative", "snip")
LOSS_METHODS = ("linear", "soft_l1", "huber", "cauchy")

# σ ↔ FWHM conversion for Gaussians / 高斯 σ 与 FWHM 的换算。
_FWHM_PER_SIGMA = 2.0 * math.sqrt(2.0 * math.log(2.0))  # ≈ 2.3548
# sqrt(π / (4 ln 2)) — Gaussian area factor in terms of (height, FWHM).
_GAUSS_AREA_FACTOR = math.sqrt(math.pi / (4.0 * math.log(2.0)))
# Olivero–Longbothum Voigt FWHM coefficients / Voigt FWHM 近似系数。
_OL_A = 0.5346
_OL_B = 0.2166
# Minimum points after region crop / 选区裁剪后的最少点数。
_MIN_POINTS = 8
# Hard cap on peaks per fit / 单次拟合的峰数上限。
_MAX_PEAKS = 24
# Default fitting options / 默认拟合选项（PeakFit 时代的经典默认值）。
_DEFAULT_MAX_ITER = 500
# Polynomial background order limits / 多项式背景阶数范围。
_BG_ORDER_RANGE = (0, 5)


# ---------------------------------------------------------------------------
# Small numeric helpers / 数值辅助
# ---------------------------------------------------------------------------

def _as_float_array(values: Any) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError("Expected a 1-D array / 需要一维数组")
    return arr


def _odd_window(window: int, n: int, minimum: int = 3) -> int:
    """Clamp a smoothing window to an odd value inside (minimum, n).
    把平滑窗口钳制为 (minimum, n) 内的奇数。"""
    w = max(minimum, int(window) if window else minimum)
    w = min(w, n if n % 2 == 1 else n - 1)
    if w % 2 == 0:
        w -= 1
    return max(minimum, w)


def _lognormal_w_from_fwhm(center: float, fwhm: float) -> float:
    """Solve the lognormal log-width w for a target FWHM at peak position c
    (the FWHM↔w map is monotonic → Newton converges in a few steps).
    在峰位 c 处按目标 FWHM 反解对数宽度 w（映射单调，Newton 数步收敛）。"""
    if center <= 0.0 or fwhm <= 0.0:
        raise ValueError(
            "LogNormal requires a positive center and FWHM / LogNormal 峰形要求中心与 FWHM 均为正数"
        )
    a = math.sqrt(2.0 * math.log(2.0))
    w = fwhm / (2.0 * center * a)  # small-w expansion start / 小 w 展开初值
    for _ in range(64):
        f = center * (math.exp(a * w) - math.exp(-a * w)) - fwhm
        df = center * a * (math.exp(a * w) + math.exp(-a * w))
        step = f / max(df, 1e-300)
        w = max(w - step, 1e-6)
        if abs(step) < 1e-12 * max(w, 1e-6):
            break
    return w


def _lognormal_fwhm(center: float, w: float) -> float:
    a = math.sqrt(2.0 * math.log(2.0))
    return center * (math.exp(a * w) - math.exp(-a * w))


# ---------------------------------------------------------------------------
# Peak shape profiles (all in SCALED x/y units — shapes are scale-invariant) /
# 峰形曲线（均在缩放后的 x/y 单位下计算——峰形对缩放不变）
# ---------------------------------------------------------------------------

def peak_profile(
    x: np.ndarray,
    peak_type: str,
    center: float,
    height: float,
    fwhm: float,
    shape: float | None = None,
) -> np.ndarray:
    """Evaluate one peak shape. Every shape passes exactly through
    (center, height). 评估单个峰形；所有峰形在中心处的值恰为 height。"""
    if peak_type == "gaussian":
        sigma = fwhm / _FWHM_PER_SIGMA
        z = (x - center) / sigma
        return height * np.exp(-0.5 * z * z)

    if peak_type == "lorentzian":
        gamma = 0.5 * fwhm
        z = (x - center) / gamma
        return height / (1.0 + z * z)

    if peak_type == "pseudo_voigt":
        eta = float(shape if shape is not None else 0.5)
        sigma = fwhm / _FWHM_PER_SIGMA
        gamma = 0.5 * fwhm
        zg = (x - center) / sigma
        zl = (x - center) / gamma
        return height * (eta / (1.0 + zl * zl) + (1.0 - eta) * np.exp(-0.5 * zg * zg))

    if peak_type == "pearson7":
        m = max(float(shape if shape is not None else 2.0), 0.6)
        big_m = 2.0 ** (1.0 / m) - 1.0
        z = (x - center) / fwhm
        return height * (1.0 + 4.0 * big_m * z * z) ** (-m)

    if peak_type == "voigt":
        # FWHM-consistent (σ, γ) split: with fL = κ·w the Olivero–Longbothum
        # inversion makes the profile's effective FWHM exactly w.
        # 与 FWHM 一致的 (σ, γ) 分解：取 fL = κ·w 后按 Olivero–Longbothum 反演，
        # 峰形的有效 FWHM 恰为 w。
        kappa = min(max(float(shape if shape is not None else 0.5), 0.0), 1.0)
        f_l = kappa * fwhm
        inner = (fwhm - _OL_A * f_l) ** 2 - _OL_B * f_l * f_l
        f_g = math.sqrt(inner) if inner > 0.0 else fwhm * 1e-3
        sigma = f_g / _FWHM_PER_SIGMA
        gamma = 0.5 * f_l
        u = ((x - center) + 1j * gamma) / (sigma * math.sqrt(2.0))
        prof = wofz(u).real / (sigma * math.sqrt(2.0 * math.pi))
        vc = wofz(1j * gamma / (sigma * math.sqrt(2.0))).real / (sigma * math.sqrt(2.0 * math.pi))
        return height * prof / max(vc, 1e-300)

    if peak_type == "lognormal":
        w = float(shape if shape is not None else 0.3)
        xr = np.maximum(x, center * math.exp(-30.0 * max(w, 1e-3)))
        z = np.log(xr / center) / w
        y = height * np.exp(-0.5 * z * z)
        return np.where(x > 0.0, y, 0.0)

    raise ValueError(f"Unknown peak type / 未知峰形: {peak_type}")


def _peak_area_scaled(
    peak_type: str,
    height: float,
    fwhm: float,
    shape: float | None = None,
) -> float:
    """Peak area in scaled units — analytic where a closed form exists
    (Gaussian, Lorentzian, pseudo-Voigt, Pearson VII, Voigt via the unit-area
    normalisation), Simpson for the lognormal.
    缩放单位下的峰面积：有闭式解处解析计算（高斯/洛伦兹/伪 Voigt/Pearson VII/
    Voigt 经单位面积归一），lognormal 用 Simpson 数值积分。"""
    if peak_type == "gaussian":
        return height * fwhm * _GAUSS_AREA_FACTOR
    if peak_type == "lorentzian":
        return height * math.pi * fwhm / 2.0
    if peak_type == "pseudo_voigt":
        eta = float(shape if shape is not None else 0.5)
        return height * fwhm * (eta * math.pi / 2.0 + (1.0 - eta) * _GAUSS_AREA_FACTOR)
    if peak_type == "pearson7":
        # ∫(1+4M z²)^(−m)dx over ℝ = w/(2√M)·√π·Γ(m−½)/Γ(m); at m=1 this
        # reduces to the Lorentzian π·h·w/2 (checked in tests).
        # 全线积分在 m=1 时退化为洛伦兹 π·h·w/2（测试中验证）。
        m = max(float(shape if shape is not None else 2.0), 0.6)
        big_m = 2.0 ** (1.0 / m) - 1.0
        return (
            height * fwhm / (2.0 * math.sqrt(big_m)) * math.sqrt(math.pi)
            * _gamma_fn(m - 0.5) / _gamma_fn(m)
        )
    if peak_type == "voigt":
        # The profile normalised to peak 1 has unit-mass Voigt inside →
        # area = height / V(center). 峰值归一后面积 = height / V(中心)。
        unit = float(peak_profile(np.zeros(1), "voigt", 0.0, 1.0, fwhm, shape)[0])
        return height / max(unit, 1e-300)
    if peak_type == "lognormal":
        # Scale-invariant trick: area(c, h, w) = c · area(1, h, w), so the
        # integration runs on a unit-center grid. 面积 = c·面积(1,h,w)，
        # 故在单位中心网格上积分。
        w = float(shape if shape is not None else 0.3)
        lo = math.exp(-40.0 * max(w, 1e-3))
        grid = np.geomspace(lo, 1.0 / lo, 2001)
        vals = peak_profile(grid, "lognormal", 1.0, height, 1.0, w)
        return float(simpson(vals, x=grid))
    raise ValueError(f"Unknown peak type / 未知峰形: {peak_type}")


# ---------------------------------------------------------------------------
# Pipeline stage 1-2: intake + region + smoothing / 数据整理 + 选区 + 平滑
# ---------------------------------------------------------------------------

def _intake_curve(x: Any, y: Any) -> tuple[np.ndarray, np.ndarray, list[str]]:
    """Finite-filter, pair and sort ascending. 有限值过滤、配对并按 x 升序排序。"""
    xa = _as_float_array(x)
    ya = _as_float_array(y)
    if xa.size != ya.size:
        raise ValueError("x and y must have equal length / x 与 y 长度必须一致")
    if xa.size < _MIN_POINTS:
        raise ValueError(
            f"At least {_MIN_POINTS} points required (got {int(xa.size)}) / "
            f"至少需要 {_MIN_POINTS} 个数据点（收到 {int(xa.size)} 个）"
        )
    finite = np.isfinite(xa) & np.isfinite(ya)
    dropped = int((~finite).sum())
    xa, ya = xa[finite], ya[finite]
    if xa.size < _MIN_POINTS:
        raise ValueError(
            f"Fewer than {_MIN_POINTS} finite points / 有效数据点不足 {_MIN_POINTS} 个"
        )
    order = np.argsort(xa, kind="stable")
    xa, ya = xa[order], ya[order]
    warnings: list[str] = []
    if dropped:
        warnings.append(f"Dropped {dropped} non-finite points / 已丢弃 {dropped} 个非有限值点")
    return xa, ya, warnings


def _apply_region(
    xa: np.ndarray, ya: np.ndarray, region: dict[str, Any] | None
) -> tuple[np.ndarray, np.ndarray]:
    rmin = region.get("min") if region else None
    rmax = region.get("max") if region else None
    keep = np.ones(xa.shape, dtype=bool)
    if isinstance(rmin, (int, float)) and math.isfinite(float(rmin)):
        keep &= xa >= float(rmin)
    if isinstance(rmax, (int, float)) and math.isfinite(float(rmax)):
        keep &= xa <= float(rmax)
    return xa[keep], ya[keep]


def smooth_curve(
    y: np.ndarray, method: str, window: int, poly_order: int
) -> tuple[np.ndarray, dict[str, Any]]:
    """Smoothing stage. Returns (smoothed, applied-info). 平滑步骤。"""
    n = int(y.size)
    if method == "none" or n < 5:
        return y.copy(), {"method": "none", "window": 0, "poly_order": 0}
    if method == "savgol":
        order = min(max(int(poly_order or 3), 1), 4)
        w = _odd_window(window or 11, n, minimum=max(order + 2, 3))
        if w <= order:
            return y.copy(), {"method": "none", "window": 0, "poly_order": 0}
        return savgol_filter(y, w, order), {"method": "savgol", "window": w, "poly_order": order}
    if method == "moving_average":
        w = _odd_window(window or 7, n)
        return uniform_filter1d(y, size=w, mode="nearest"), {"method": "moving_average", "window": w, "poly_order": 0}
    if method == "median":
        w = _odd_window(window or 5, n)
        return median_filter(y, size=w, mode="nearest"), {"method": "median", "window": w, "poly_order": 0}
    raise ValueError(f"Unknown smoothing method / 未知平滑方法: {method}")


# ---------------------------------------------------------------------------
# Pipeline stage 3: background / 背景估计
# ---------------------------------------------------------------------------

def _polyfit_scaled(xs: np.ndarray, ys: np.ndarray, order: int) -> np.ndarray:
    """Ascending-order polynomial fit on scaled x (well conditioned).
    在缩放 x 上做升幂多项式拟合（数值条件良好）。"""
    order = min(max(int(order), _BG_ORDER_RANGE[0]), _BG_ORDER_RANGE[1])
    order = min(order, int(xs.size) - 1)
    return np.polynomial.polynomial.polyfit(xs, ys, order)


def estimate_background(
    xs: np.ndarray,
    ys: np.ndarray,
    method: str,
    order: int,
    iterations: int,
) -> tuple[np.ndarray | None, np.ndarray | None]:
    """Standalone baseline estimate on scaled arrays.
    在缩放数组上做独立背景估计；返回 (背景曲线, 多项式系数或 None)。"""
    if method == "none":
        return None, None
    if method == "polynomial":
        coeffs = _polyfit_scaled(xs, ys, order)
        return np.polynomial.polynomial.polyval(xs, coeffs), coeffs
    if method == "iterative":
        # Iterative polynomial with peak clipping (ModPoly lineage): repeat
        # {fit, clip points above the fit} until the baseline settles under
        # the peaks. 迭代多项式（ModPoly 一脉）：反复「拟合、把高于拟合的点
        # 压回拟合」，直至背景沉到峰下。
        z = ys.copy()
        coeffs = _polyfit_scaled(xs, z, order)
        n_iter = max(1, min(int(iterations or 40), 500))
        for _ in range(n_iter):
            p = np.polynomial.polynomial.polyval(xs, coeffs)
            z_new = np.minimum(z, p)
            if np.array_equal(z_new, z):
                break
            z = z_new
            coeffs = _polyfit_scaled(xs, z, order)
        return np.polynomial.polynomial.polyval(xs, coeffs), coeffs
    if method == "snip":
        # SNIP (Ryan et al. 1988): LLS transform, then clip with a
        # decreasing window; requires non-negative y (shift by the minimum).
        # SNIP：LLS 变换 + 递减窗口裁剪；要求 y 非负（按最小值平移）。
        y_shift = float(ys.min())
        base = ys - (y_shift if y_shift < 0.0 else 0.0)
        v = np.log(np.log(np.sqrt(base + 1.0) + 1.0) + 1.0)
        n = int(v.size)
        m = max(1, min(int(iterations or 24), max(1, n // 2)))
        for p in range(m, 0, -1):
            if 2 * p >= n:
                continue
            w = v.copy()
            w[p : n - p] = np.minimum(v[p : n - p], 0.5 * (v[: n - 2 * p] + v[2 * p :]))
            v = w
        out = (np.exp(np.exp(v) - 1.0) - 1.0) ** 2 - 1.0
        out = np.maximum(out, 0.0)
        return out + (y_shift if y_shift < 0.0 else 0.0), None
    raise ValueError(f"Unknown background method / 未知背景方法: {method}")


# ---------------------------------------------------------------------------
# Pipeline stage 4: peaks / 峰参数
# ---------------------------------------------------------------------------

def _normalise_peaks(raw_peaks: list[Any], dx_median: float) -> list[dict[str, Any]]:
    """Validate/fill user peak entries into the internal canonical form.
    校验/补全用户峰参数为内部规范形式。"""
    if not raw_peaks:
        return []
    if len(raw_peaks) > _MAX_PEAKS:
        raise ValueError(
            f"At most {_MAX_PEAKS} peaks per fit / 单次拟合最多 {_MAX_PEAKS} 个峰"
        )
    out: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_peaks):
        entry = raw if isinstance(raw, dict) else {}
        ptype = str(entry.get("type", "pseudo_voigt"))
        if ptype not in PEAK_TYPES:
            raise ValueError(f"Unknown peak type / 未知峰形: {ptype}")
        locks_raw = entry.get("locks") if isinstance(entry.get("locks"), dict) else {}
        locks = {
            "center": bool(locks_raw.get("center", False)),
            "height": bool(locks_raw.get("height", False)),
            "fwhm": bool(locks_raw.get("fwhm", False)),
            "shape": bool(locks_raw.get("shape", False)),
        }

        def _num(key: str) -> float | None:
            v = entry.get(key)
            if isinstance(v, (int, float)) and math.isfinite(float(v)):
                return float(v)
            return None

        center = _num("center")
        height = _num("height")
        fwhm = _num("fwhm")
        shape = _num("shape")
        if center is None or height is None or fwhm is None:
            raise ValueError(
                f"Peak {idx + 1}: center, height and fwhm are required / "
                f"峰 {idx + 1}：中心、峰高与 FWHM 为必填项"
            )
        if ptype == "lognormal":
            if center <= 0.0 or fwhm <= 0.0:
                raise ValueError(
                    f"Peak {idx + 1}: LogNormal requires center > 0 and FWHM > 0 / "
                    f"峰 {idx + 1}：LogNormal 峰形要求中心与 FWHM 均为正数"
                )
            if shape is None:
                shape = _lognormal_w_from_fwhm(center, fwhm)
        if shape is None and ptype in SHAPE_TYPES:
            shape = SHAPE_DEFAULTS[ptype]
        if ptype not in SHAPE_TYPES:
            shape = None
            locks["shape"] = False
        if fwhm <= 0.0:
            fwhm = max(fwhm, 0.5 * dx_median)
        out.append(
            {
                "type": ptype,
                "center": center,
                "height": height,
                "fwhm": fwhm,
                "shape": shape,
                "locks": locks,
            }
        )
    return out


def auto_detect_peaks(
    xs: np.ndarray,
    y_proc: np.ndarray,
    prominence_frac: float,
    max_peaks: int = _MAX_PEAKS,
) -> list[dict[str, Any]]:
    """Prominence-based peak detection on the processed (background-
    subtracted, smoothed) curve; widths from the half-maximum crossings.
    Rank by height, keep the strongest max_peaks. Inputs/outputs are in
    scaled units. 在处理过（扣背景+平滑）的曲线上按显著度寻峰；宽度取半高
    交点；按峰高排序取最强 max_peaks 个。输入输出均为缩放单位。"""
    y = np.asarray(y_proc, dtype=float)
    n = int(y.size)
    span = float(y.max() - y.min()) if n else 0.0
    if span <= 0.0:
        return []
    prom = max(float(prominence_frac), 1e-4) * span
    dx = float(np.median(np.diff(xs))) if n > 1 else 1.0
    distance = max(1, int(round(0.025 / max(dx, 1e-12))))  # ≈ 2.5% of the region
    idx, _props = find_peaks(y, prominence=prom, distance=distance)
    if idx.size == 0:
        return []
    widths_samples, _, _, _ = peak_widths(y, idx, rel_height=0.5)
    order = np.argsort(y[idx])[::-1][:max_peaks]
    peaks: list[dict[str, Any]] = []
    for k in order:
        i = int(idx[k])
        fwhm = float(max(widths_samples[k], 2.0) * dx)
        peaks.append(
            {
                "type": "pseudo_voigt",
                "center": float(xs[i]),
                "height": float(y[i]),
                "fwhm": fwhm,
                "shape": SHAPE_DEFAULTS["pseudo_voigt"],
                "locks": {"center": False, "height": False, "fwhm": False, "shape": False},
            }
        )
    peaks.sort(key=lambda p: p["center"])
    return peaks


# ---------------------------------------------------------------------------
# Shared preparation (region → smoothing → scales) / 共享预处理
# ---------------------------------------------------------------------------

class _Prepared:
    """Scaled-space pipeline state shared by preview / evaluate / fit.
    preview / evaluate / fit 共享的缩放空间流水线状态。"""

    def __init__(
        self,
        x: Any,
        y: Any,
        region: dict[str, Any] | None,
        smoothing: dict[str, Any] | None,
    ) -> None:
        warnings: list[str] = []
        xa, ya, w = _intake_curve(x, y)
        warnings.extend(w)
        xa_r, ya_r = _apply_region(xa, ya, region)
        if int(xa_r.size) < _MIN_POINTS:
            raise ValueError(
                f"Region left fewer than {_MIN_POINTS} points; widen the selection. / "
                f"选区内不足 {_MIN_POINTS} 个数据点；请扩大选区。"
            )
        self.x_orig = xa_r
        self.y_orig = ya_r
        self.warnings = warnings

        sm_cfg = smoothing if isinstance(smoothing, dict) else {}
        sm_method = str(sm_cfg.get("method", "none"))
        ys_smooth, sm_info = smooth_curve(
            ya_r,
            sm_method,
            int(sm_cfg.get("window", 11) or 11),
            int(sm_cfg.get("poly_order", 3) or 3),
        )
        self.smoothed = ys_smooth if sm_info["method"] != "none" else None
        self.smoothing_applied = sm_info

        # Scale x to [0, 1] and y to O(1) for a well-conditioned fit.
        # x 缩放到 [0,1]、y 缩放到 O(1)，保证拟合数值条件良好。
        self.x0 = float(xa_r[0])
        self.sx = float(xa_r[-1] - xa_r[0]) or 1.0
        self.sy = float(np.max(np.abs(ys_smooth))) or 1.0
        self.xs = (xa_r - self.x0) / self.sx
        self.ys = ys_smooth / self.sy
        self.dx_median_s = float(np.median(np.diff(self.xs))) if int(self.xs.size) > 1 else 1e-3


def _model_scaled(
    xs: np.ndarray,
    peaks: list[dict[str, Any]],
    bg_coeffs: np.ndarray | None,
) -> np.ndarray:
    """Sum of peaks (+ polynomial background) in scaled space.
    缩放空间下的峰之和（+ 多项式背景）。"""
    if bg_coeffs is not None:
        total = np.polynomial.polynomial.polyval(xs, bg_coeffs)
    else:
        total = np.zeros_like(xs)
    for p in peaks:
        total = total + peak_profile(xs, p["type"], p["center"], p["height"], p["fwhm"], p["shape"])
    return total


def _background_curves(
    prepared: _Prepared, bg_cfg: dict[str, Any]
) -> tuple[np.ndarray | None, np.ndarray | None, dict[str, Any]]:
    """Standalone background on the smoothed scaled data.

    Background SECTIONS (PeakFit semantics, 2026-10-13): the user may define
    MULTIPLE peak-free windows (``regions``: list of {min,max}, or a single
    legacy ``region``). The baseline is ESTIMATED only on the union of those
    windows — polynomial/iterative coefficients from the combined points are
    extrapolated over the whole fit region; SNIP (point-wise) is computed per
    window and extended with the nearest window edge value outside/between
    windows. Empty/invalid windows are dropped (too-few-points windows warn
    and fall back to the full fit region).
    背景多段选区（PeakFit 语义，2026-10-13）：用户可定义多个无峰窗口
    （``regions`` 列表，或兼容单个 ``region``）。背景仅在所有窗口的并集上
    估计——多项式/迭代多项式用合并点定系数并全区外推；SNIP（逐点算法）按
    窗口分别计算，窗口之间与之外取最近窗口边缘值。无效窗口丢弃（点数过少
    的窗口警告并回退全区）。
    """
    method = str(bg_cfg.get("method", "none"))
    order_raw = bg_cfg.get("order", 2)
    iterations_raw = bg_cfg.get("iterations", 40)
    order = int(order_raw) if isinstance(order_raw, (int, float)) else 2
    iterations = int(iterations_raw) if isinstance(iterations_raw, (int, float)) else 40

    def _norm_window(raw: Any) -> tuple[float, float] | None:
        if not isinstance(raw, dict):
            return None
        lo = raw.get("min")
        hi = raw.get("max")
        lo_f = float(lo) if isinstance(lo, (int, float)) and math.isfinite(float(lo)) else None
        hi_f = float(hi) if isinstance(hi, (int, float)) and math.isfinite(float(hi)) else None
        if lo_f is None and hi_f is None:
            return None
        lo_u = lo_f if lo_f is not None else -np.inf
        hi_u = hi_f if hi_f is not None else np.inf
        if hi_u < lo_u:
            lo_u, hi_u = hi_u, lo_u
        return (lo_u, hi_u)

    windows: list[tuple[float, float]] = []
    regions_raw = bg_cfg.get("regions")
    if isinstance(regions_raw, list):
        for raw in regions_raw:
            w = _norm_window(raw)
            if w is not None:
                windows.append(w)
    if not windows:
        single = _norm_window(bg_cfg.get("region"))
        if single is not None:
            windows.append(single)

    mask: np.ndarray | None = None
    kept_windows: list[tuple[float, float]] = []
    if windows:
        min_pts = max(4, order + 2)
        mask = np.zeros(prepared.xs.shape, dtype=bool)
        for lo_u, hi_u in windows:
            # Windows arrive in ORIGINAL units → convert to the scaled axis
            # before masking. 窗口为原始单位 → 先换算到缩放轴再做掩膜。
            lo_s = (lo_u - prepared.x0) / prepared.sx
            hi_s = (hi_u - prepared.x0) / prepared.sx
            w_mask = (prepared.xs >= lo_s) & (prepared.xs <= hi_s)
            if int(w_mask.sum()) >= min_pts:
                mask |= w_mask
                kept_windows.append((lo_s, hi_s))
            else:
                prepared.warnings.append(
                    f"Background section [{lo_u:.4g}, {hi_u:.4g}] holds too few points; ignored. / "
                    f"背景选区 [{lo_u:.4g}, {hi_u:.4g}] 内点数过少，已忽略。"
                )
        if not kept_windows:
            prepared.warnings.append(
                "No usable background sections remain; estimating on the full fit window. / "
                "没有可用的背景选区；改用整个拟合区间估计背景。"
            )
            mask = None

    xs_fit = prepared.xs if mask is None else prepared.xs[mask]
    ys_fit = prepared.ys if mask is None else prepared.ys[mask]
    bg_s, coeffs = estimate_background(xs_fit, ys_fit, method, order, iterations)

    if bg_s is not None and mask is not None:
        if coeffs is not None:
            # Polynomial family: coefficients from the sections' combined
            # points, curve over the whole fit region (extrapolation).
            # 多项式族：用各选区合并点定系数，全区外推曲线。
            bg_s = np.polynomial.polynomial.polyval(prepared.xs, coeffs)
        else:
            # SNIP is point-wise per section: fill each window with its own
            # SNIP curve, then extend NaN gaps with the nearest window edge
            # value (edge-hold interpolation on the index axis).
            # SNIP 按选区逐段计算：各窗口填各自曲线，空隙用最近窗口边缘值
            # （索引轴上的边缘保持插值）延伸。
            full = np.full(prepared.xs.shape, np.nan)
            for lo_s, hi_s in kept_windows:
                w_mask = (prepared.xs >= lo_s) & (prepared.xs <= hi_s)
                seg, _c = estimate_background(
                    prepared.xs[w_mask], prepared.ys[w_mask], method, order, iterations
                )
                if seg is not None:
                    full[w_mask] = seg
            known = np.flatnonzero(np.isfinite(full))
            if known.size:
                full = np.interp(np.arange(full.size), known, full[known])
            else:
                full = np.zeros_like(prepared.xs)
            bg_s = full

    info: dict[str, Any] = {"method": method, "refined": False}
    if kept_windows:
        info["windows"] = [
            [
                float(prepared.x0 + lo_s * prepared.sx) if np.isfinite(lo_s) else float(prepared.x_orig[0]),
                float(prepared.x0 + hi_s * prepared.sx) if np.isfinite(hi_s) else float(prepared.x_orig[-1]),
            ]
            for lo_s, hi_s in kept_windows
        ]
        # Backward-compatible single-window echo. / 兼容单窗口回显。
        info["window"] = info["windows"][0]
    return bg_s, coeffs, info


def _marshal_preview(
    prepared: _Prepared,
    bg_s: np.ndarray | None,
    y_proc_s: np.ndarray,
    bg_info: dict[str, Any],
    auto_peaks: list[dict[str, Any]],
) -> dict[str, Any]:
    sy, sx, x0 = prepared.sy, prepared.sx, prepared.x0
    return {
        "x": (x0 + prepared.xs * sx).tolist(),
        "raw_y": prepared.y_orig.tolist(),
        "smoothed_y": prepared.smoothed.tolist() if prepared.smoothed is not None else None,
        "processed_y": (y_proc_s * sy).tolist(),
        "background_y": (bg_s * sy).tolist() if bg_s is not None else None,
        "auto_peaks": [
            {
                "type": p["type"],
                "center": float(x0 + p["center"] * sx),
                "height": float(p["height"] * sy),
                "fwhm": float(p["fwhm"] * sx),
                "shape": p["shape"],
            }
            for p in auto_peaks
        ],
        "background_info": bg_info,
        "quality": {
            "n_points": int(prepared.xs.size),
            "x_min": float(prepared.x_orig[0]),
            "x_max": float(prepared.x_orig[-1]),
            "smoothing": prepared.smoothing_applied,
        },
        "warnings": prepared.warnings,
    }


def _peak_to_scaled(p: dict[str, Any], prepared: _Prepared) -> dict[str, Any]:
    """Convert a canonical (original-unit) peak to scaled units.
    把原始单位的峰参数换算到缩放单位（lognormal 的宽度按 (c,w)→FWHM 换算）。"""
    return {
        "type": p["type"],
        "center": (p["center"] - prepared.x0) / prepared.sx,
        "height": p["height"] / prepared.sy,
        "fwhm": _lognormal_fwhm(p["center"], p["shape"]) / prepared.sx
        if p["type"] == "lognormal"
        else p["fwhm"] / prepared.sx,
        "shape": p["shape"],
        "locks": p["locks"],
    }


# ---------------------------------------------------------------------------
# Public entry 1: preview / 预览（选区 + 平滑 + 背景，可选自动寻峰）
# ---------------------------------------------------------------------------

def preview_pipeline(
    x: Any,
    y: Any,
    *,
    region: dict[str, Any] | None = None,
    smoothing: dict[str, Any] | None = None,
    background: dict[str, Any] | None = None,
    detect: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prepared = _Prepared(x, y, region, smoothing)
    bg_cfg = background if isinstance(background, dict) else {}
    bg_s, _coeffs, bg_info = _background_curves(prepared, bg_cfg)

    y_proc_s = prepared.ys - bg_s if bg_s is not None else prepared.ys
    auto_peaks: list[dict[str, Any]] = []
    if isinstance(detect, dict) and detect.get("enabled"):
        prom = detect.get("prominence", 0.05)
        try:
            auto_peaks = auto_detect_peaks(prepared.xs, y_proc_s, float(prom) if prom else 0.05)
        except Exception as exc:  # noqa: BLE001
            logger.warning("auto peak detection failed: %s", exc)
            prepared.warnings.append(f"Auto peak detection failed / 自动寻峰失败: {exc}")

    return _marshal_preview(prepared, bg_s, y_proc_s, bg_info, auto_peaks)


# ---------------------------------------------------------------------------
# Public entry 2: evaluate / 模型求值（改参时的即时曲线，不拟合）
# ---------------------------------------------------------------------------

def evaluate_model(
    x: Any,
    y: Any,
    *,
    region: dict[str, Any] | None = None,
    smoothing: dict[str, Any] | None = None,
    background: dict[str, Any] | None = None,
    peaks: list[Any] | None = None,
) -> dict[str, Any]:
    """Evaluate the current model (fixed parameters) — the interaction-study
    counterpart of "dragging an anchor never triggers a fit".
    以当前（固定）参数求模型曲线——对应交互研究中「拖锚只求值、不触发拟合」。"""
    prepared = _Prepared(x, y, region, smoothing)
    bg_cfg = background if isinstance(background, dict) else {}
    bg_s, coeffs, _info = _background_curves(prepared, bg_cfg)
    peaks_n = _normalise_peaks(peaks or [], prepared.dx_median_s)
    peaks_s = [_peak_to_scaled(p, prepared) for p in peaks_n]
    model = _model_scaled(prepared.xs, peaks_s, coeffs)
    return {
        "x": (prepared.x0 + prepared.xs * prepared.sx).tolist(),
        "curves": {
            "sum": (model * prepared.sy).tolist(),
            "background": (bg_s * prepared.sy).tolist() if bg_s is not None else None,
            "peaks": [
                (
                    peak_profile(
                        prepared.xs, p["type"], p["center"], p["height"], p["fwhm"], p["shape"]
                    )
                    * prepared.sy
                ).tolist()
                for p in peaks_s
            ],
        },
        "warnings": prepared.warnings,
    }


# ---------------------------------------------------------------------------
# Public entry 3: fit / 拟合
# ---------------------------------------------------------------------------

def fit_curve(
    x: Any,
    y: Any,
    *,
    region: dict[str, Any] | None = None,
    smoothing: dict[str, Any] | None = None,
    background: dict[str, Any] | None = None,
    peaks: list[Any] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Full pipeline + Levenberg–Marquardt (TRF implementation) refinement
    with per-parameter locks and optional joint background refinement.
    完整流水线 + Levenberg–Marquardt（TRF 实现）精修，支持参数级锁定与
    背景联合精修。"""
    prepared = _Prepared(x, y, region, smoothing)
    bg_cfg = background if isinstance(background, dict) else {}
    opt_cfg = options if isinstance(options, dict) else {}
    bg_method = str(bg_cfg.get("method", "none"))
    refine_raw = bg_cfg.get("refine", False)
    refine_bg = bool(refine_raw) and bg_method in ("polynomial", "iterative")

    bg_s, coeffs, _bg_info = _background_curves(prepared, bg_cfg)
    peaks_n = _normalise_peaks(peaks or [], prepared.dx_median_s)
    if not peaks_n:
        raise ValueError("At least one peak is required / 至少需要一个峰")
    peaks_s = [_peak_to_scaled(p, prepared) for p in peaks_n]

    # Fit target & model-background wiring / 拟合目标与模型背景接线：
    #   refine   → target = smoothed;        model = poly(coeffs) + peaks
    #   subtract → target = smoothed − bg_s; model = peaks
    if refine_bg and coeffs is not None:
        y_target = prepared.ys
        model_coeffs: np.ndarray | None = np.asarray(coeffs, dtype=float)
    else:
        refine_bg = False
        y_target = prepared.ys - bg_s if bg_s is not None else prepared.ys
        model_coeffs = None

    # ── Pack free parameters / 打包自由参数（锁定的参数不入向量） ──
    names: list[tuple[str, int, str]] = []
    p0: list[float] = []
    lo: list[float] = []
    hi: list[float] = []
    span_s = 1.0
    dx = max(prepared.dx_median_s, 1e-6)
    y_max_s = float(np.max(np.abs(y_target))) or 1.0

    def _add(kind: str, idx: int, name: str, value: float, low: float, high: float) -> None:
        names.append((kind, idx, name))
        p0.append(min(max(float(value), low), high))
        lo.append(float(low))
        hi.append(float(high))

    for i, p in enumerate(peaks_s):
        lk = p["locks"]
        if not lk["center"]:
            c_lo = 1e-3 if p["type"] == "lognormal" else -0.15 * span_s
            _add("peak", i, "center", p["center"], c_lo, 1.15 * span_s)
        if not lk["height"]:
            _add("peak", i, "height", p["height"], 0.0, 3.0 * y_max_s)
        if not lk["fwhm"] and p["type"] != "lognormal":
            _add("peak", i, "fwhm", p["fwhm"], 0.25 * dx, 4.0 * span_s)
        if not lk["shape"] and p["type"] in SHAPE_TYPES:
            s_lo, s_hi = SHAPE_BOUNDS[p["type"]]
            _add(
                "peak",
                i,
                "shape",
                p["shape"] if p["shape"] is not None else SHAPE_DEFAULTS[p["type"]],
                s_lo,
                s_hi,
            )

    if model_coeffs is not None:
        for j, c in enumerate(model_coeffs):
            _add("bg", j, f"c{j}", float(c), -50.0, 50.0)

    warnings = list(prepared.warnings)
    n = int(prepared.xs.size)
    k_free = len(p0)

    def _apply_theta(theta: list[float]) -> tuple[list[dict[str, Any]], np.ndarray | None]:
        work = [dict(p) for p in peaks_s]
        coeff_out = model_coeffs.copy() if model_coeffs is not None else None
        for (kind, idx, name), value in zip(names, theta):
            if kind == "peak":
                work[idx][name] = float(value)
            elif coeff_out is not None:
                coeff_out[idx] = float(value)
        return work, coeff_out

    def _residual(theta: np.ndarray) -> np.ndarray:
        work, coeff_out = _apply_theta(theta.tolist())
        return _model_scaled(prepared.xs, work, coeff_out) - y_target

    success = True
    fit_message = "all parameters locked / 全部参数已锁定"
    n_fev = 0
    active_mask: np.ndarray | None = None
    jac: np.ndarray | None = None

    theta_final = list(p0)
    if k_free > 0:
        loss = str(opt_cfg.get("loss", "linear"))
        if loss not in LOSS_METHODS:
            loss = "linear"
        max_iter_raw = opt_cfg.get("max_iterations", _DEFAULT_MAX_ITER)
        max_iter = min(max(int(max_iter_raw) if max_iter_raw else _DEFAULT_MAX_ITER, 10), 10000)
        kwargs: dict[str, Any] = {
            "method": "trf",
            "bounds": (np.asarray(lo), np.asarray(hi)),
            "max_nfev": max_iter,
            "loss": loss,
        }
        if loss != "linear":
            # y is scaled to O(1) → f_scale 1.0 is a sane robustness radius.
            # y 已缩放到 O(1)，f_scale=1.0 即合理的稳健半径。
            kwargs["f_scale"] = 1.0
        try:
            res = least_squares(_residual, np.asarray(p0), **kwargs)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Optimizer failed / 优化器失败: {exc}") from exc
        theta_final = [float(v) for v in res.x]
        success = bool(res.success)
        fit_message = str(res.message)
        n_fev = int(res.nfev)
        active_mask = getattr(res, "active_mask", None)
        jac = res.jac

    work, coeff_final = _apply_theta(theta_final)
    model = _model_scaled(prepared.xs, work, coeff_final)
    residuals = y_target - model
    sse = float(np.sum(residuals ** 2))

    # ── Statistics / 统计量 ──
    dof = n - k_free
    if dof < 1:
        warnings.append(
            f"Degrees of freedom = {dof} (<1): statistics are unreliable. / "
            f"自由度 = {dof}（<1）：统计量不可靠。"
        )
    dof_safe = max(dof, 1)
    sst = float(np.sum((y_target - float(np.mean(y_target))) ** 2))
    rmse_s = math.sqrt(sse / n) if n else float("nan")
    fit_std_err_s = math.sqrt(sse / dof_safe)
    r2 = 1.0 - sse / sst if sst > 0.0 else float("nan")
    r2_adj = 1.0 - (1.0 - r2) * (n - 1) / dof_safe if (sst > 0.0 and n > 1) else float("nan")
    f_stat = ((sst - sse) / k_free) / (sse / dof_safe) if (k_free > 0 and sse > 0.0) else float("nan")
    if math.isfinite(r2) and r2 < 0.8:
        warnings.append(
            f"R² = {r2:.4f}: the model does not describe the data well; "
            f"check peak placements and background. / R² = {r2:.4f}：模型与数据吻合不佳；"
            f"请检查放峰位置与背景。"
        )

    # ── Parameter standard errors from the covariance / 协方差 → 参数标准误 ──
    perr_map: dict[tuple[str, int, str], float] = {}
    if jac is not None and k_free > 0 and dof >= 1:
        try:
            jtj = jac.T @ jac
            cov = np.linalg.pinv(jtj) * (sse / dof_safe)
            perr = np.sqrt(np.maximum(np.diag(cov), 0.0))
            for slot, key in enumerate(names):
                perr_map[key] = float(perr[slot])
        except np.linalg.LinAlgError:
            warnings.append(
                "Covariance unavailable; parameter errors omitted. / 协方差不可用，参数标准误省略。"
            )

    # Parameters pinned at their bounds / 触及边界的参数。
    if active_mask is not None and bool(np.any(active_mask)):
        hit = [
            (f"peak{idx + 1}.{name}" if kind == "peak" else f"bg.{name}")
            for (kind, idx, name), m in zip(names, active_mask)
            if m
        ]
        warnings.append(
            "Parameters at their bounds: " + ", ".join(hit)
            + " / 参数触及边界：" + ", ".join(hit)
        )

    # ── Marshal back to original units / 换算回原始单位 ──
    sx, sy, x0 = prepared.sx, prepared.sy, prepared.x0
    peak_results: list[dict[str, Any]] = []
    areas: list[float] = []
    for i, p in enumerate(work):
        center_u = x0 + p["center"] * sx
        height_u = p["height"] * sy
        shape_u = p["shape"]
        if p["type"] == "lognormal":
            fwhm_u = _lognormal_fwhm(center_u, shape_u)
            fwhm_s_arg = _lognormal_fwhm(1.0, shape_u)
        else:
            fwhm_u = p["fwhm"] * sx
            fwhm_s_arg = p["fwhm"]
        area_u = _peak_area_scaled(p["type"], p["height"], fwhm_s_arg, shape_u) * sx * sy
        areas.append(area_u)

        errors = {
            "center": perr_map.get(("peak", i, "center")),
            "height": perr_map.get(("peak", i, "height")),
            "fwhm": perr_map.get(("peak", i, "fwhm")),
            "shape": perr_map.get(("peak", i, "shape")),
        }
        if p["type"] == "lognormal" and (errors["shape"] is not None or errors["center"] is not None):
            # FWHM error through the (center, w) → FWHM map (numeric gradient).
            dc = errors["center"] or 0.0
            dw = errors["shape"] or 0.0
            if shape_u and shape_u > 0.0 and center_u > 0.0:
                grad_c = (
                    _lognormal_fwhm(center_u * 1.001, shape_u)
                    - _lognormal_fwhm(center_u * 0.999, shape_u)
                ) / (0.002 * center_u)
                grad_w = (
                    _lognormal_fwhm(center_u, shape_u * 1.001)
                    - _lognormal_fwhm(center_u, shape_u * 0.999)
                ) / (0.002 * shape_u)
                errors["fwhm"] = math.sqrt((grad_c * dc) ** 2 + (grad_w * dw) ** 2)

        # Area error via numeric gradients over the free (height, fwhm, shape).
        area_error_s: float | None = None
        if perr_map:
            h_s = p["height"]
            s_s = p["shape"]
            terms: list[float] = []
            for pname, base in (
                ("height", h_s),
                ("fwhm", fwhm_s_arg),
                ("shape", s_s if p["type"] in SHAPE_TYPES else None),
            ):
                if base is None:
                    continue
                sigma = perr_map.get(("peak", i, pname))
                if sigma is None or sigma == 0.0:
                    continue
                delta = max(abs(base) * 1e-4, 1e-9)
                variants: list[float] = []
                for sign in (1.0, -1.0):
                    args: list[float | None] = [h_s, fwhm_s_arg, s_s]
                    slot = {"height": 0, "fwhm": 1, "shape": 2}[pname]
                    args[slot] = base + sign * delta
                    variants.append(_peak_area_scaled(p["type"], args[0], args[1], args[2]))
                grad = (variants[0] - variants[1]) / (2.0 * delta)
                terms.append((grad * sigma) ** 2)
            if terms:
                area_error_s = math.sqrt(sum(terms))

        peak_results.append(
            {
                "index": i,
                "type": p["type"],
                "params": {
                    "center": float(center_u),
                    "height": float(height_u),
                    "fwhm": float(fwhm_u),
                    "shape": float(shape_u) if shape_u is not None else None,
                },
                "errors": {
                    kk: (float(vv) if vv is not None and math.isfinite(vv) else None)
                    for kk, vv in errors.items()
                },
                "area": float(area_u),
                "area_error": (
                    float(area_error_s * sx * sy)
                    if area_error_s is not None and math.isfinite(area_error_s)
                    else None
                ),
                "locks": p["locks"],
            }
        )

    total_area = sum(areas)
    for entry in peak_results:
        entry["area_fraction"] = (entry["area"] / total_area) if total_area != 0.0 else None

    # Background curve after (possible) joint refinement, in original units.
    # （可能经联合精修后的）背景曲线，原始单位。
    if coeff_final is not None:
        bg_curve_u = np.polynomial.polynomial.polyval(prepared.xs, coeff_final) * sy
    elif bg_s is not None:
        bg_curve_u = bg_s * sy
    else:
        bg_curve_u = None

    y_proc_s = prepared.ys - bg_s if bg_s is not None else prepared.ys
    peak_curves_u = [
        (
            peak_profile(prepared.xs, p["type"], p["center"], p["height"], p["fwhm"], p["shape"])
            * sy
        ).tolist()
        for p in work
    ]

    result = _marshal_preview(
        prepared, bg_s, y_proc_s, {"method": bg_method, "refined": refine_bg}, []
    )
    result["fit"] = {
        "success": bool(success),
        "message": fit_message,
        "n_iterations": n_fev,
        "n_free_params": k_free,
        "stats": {
            "sse": float(sse * sy * sy),
            "dof": int(dof),
            "rmse": float(rmse_s * sy),
            "fit_std_err": float(fit_std_err_s * sy),
            "r2": float(r2) if math.isfinite(r2) else None,
            "r2_adj": float(r2_adj) if math.isfinite(r2_adj) else None,
            "f_stat": float(f_stat) if math.isfinite(f_stat) else None,
        },
        "background_info": {"method": bg_method, "refined": refine_bg},
        "background_coefficients": coeff_final.tolist() if coeff_final is not None else None,
        "peaks": peak_results,
        "curves": {
            "sum": (model * sy).tolist(),
            "background": bg_curve_u.tolist() if bg_curve_u is not None else None,
            "peaks": peak_curves_u,
            "residuals": (residuals * sy).tolist(),
        },
    }
    result["warnings"] = warnings
    return result
