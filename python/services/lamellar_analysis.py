#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lamellar structure analysis (SAXS) service for X-FAIS.
X-FAIS 聚合物 SAXS 片晶结构分析服务模块。

Extracts lamellar structural parameters from 1-D SAXS profiles I(q):
    - Bragg / Lorentz-corrected peak method: q* → long period L = 2π/q*,
      plus peak FWHM and a coherent-stack repeat-count estimate.
    - 1-D correlation function (Strobl): γ₁(x) from the cosine transform of
      q²·I(q); long period from the first maximum, lamellar thickness from
      the first minimum, and a stack crystallinity estimate l_c/L.

从一维 SAXS 曲线 I(q) 提取片晶结构参数：
    - Bragg /洛伦兹校正峰法：q* → 长周期 L = 2π/q*，以及峰宽与相干堆叠
      周期数估计。
    - 一维相关函数法（Strobl）：由 q²·I(q) 的余弦变换得 γ₁(x)；首极大取长
      周期，首极小取片晶厚度，并给出堆叠内结晶度估计 l_c/L。

Physics notes / 物理约定:
    - All q are normalized to nm⁻¹ internally (Å⁻¹ input is converted), and
      all lengths are reported in nm.
    - γ₁(x) = ∫₀^∞ I(q) q² cos(qx) dq / ∫₀^∞ I(q) q² dq, normalized to 1 at
      x = 0. For an ideal two-phase lamellar stack the first maximum gives the
      long period and the first minimum gives the MINORITY phase thickness;
      the caller states which phase (crystalline/amorphous) is minority.
    - A flat background (constant, estimated from the high-q tail when auto)
      should be removed BEFORE the cosine transform, otherwise γ₁ develops a
      spurious low-frequency component.
    - The interface distribution function (Ruland/Vonk, second derivative of
      γ₁) is intentionally NOT included here; it can be added later on top of
      the same γ₁ pipeline.

    - 内部所有 q 统一为 nm⁻¹（Å⁻¹ 输入自动换算），长度一律以 nm 报告。
    - γ₁(x) = ∫₀^∞ I(q) q² cos(qx) dq / ∫₀^∞ I(q) q² dq，在 x=0 处归一为 1。
      理想两相片晶堆叠中：首极大 = 长周期；首极小 = 少数相厚度；由调用方
      指明少数相是晶相还是非晶相。
    - 余弦变换前应扣除平坦背景（auto 模式用高 q 尾部估计常数背景），否则
      γ₁ 会叠加虚假低频分量。
    - 界面分布函数（Ruland/Vonk，γ₁ 的二阶导数）暂不包含，可日后在同一
      γ₁ 流水线上扩展。

Pure numpy, no I/O, no WebSocket code — mirrors orientation_analysis.py style.
纯 numpy 实现，不包含文件 I/O 与 WebSocket 代码，风格与 orientation_analysis.py 一致。

Usage / 用法::

    from python.services.lamellar_analysis import analyze_lamellar

    result = analyze_lamellar(
        q_nm, intensity,
        q_unit="nm^-1",
        methods=["bragg", "correlation"],
        background={"mode": "auto"},
        minority_phase="crystalline",
    )
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants / 常量
# ---------------------------------------------------------------------------

# q input units. / q 输入单位。
_VALID_Q_UNIT = ("nm^-1", "A^-1")
# Background subtraction modes. / 背景扣除模式。
_VALID_BG_MODE = ("none", "constant", "auto")
# Analysis methods. / 分析方法。
_VALID_METHODS = ("bragg", "correlation")
# Which phase is the minority (thinner) phase of the stack. / 堆叠中的少数相。
_VALID_MINORITY = ("crystalline", "amorphous")
# Fraction of the high-q tail used for auto background estimation.
# 自动背景估计所用高 q 尾部比例。
_BG_TAIL_FRACTION = 0.15
# Default smoothing window (points) for peak finding. / 峰搜索默认平滑窗口（点）。
_DEFAULT_SMOOTH_WINDOW = 7
# Number of points on the uniform q / r grids for the correlation function.
# 相关函数均匀 q / r 网格的默认点数。
_Q_GRID_NPT = 1024
_R_GRID_NPT = 1024
# Minimum span of q (nm⁻¹) below which the analysis is flagged unreliable.
# q 跨度（nm⁻¹）低于该值时结果被标记为不可信。
_MIN_Q_SPAN_NM = 0.05

# numpy 2.0 renamed trapz → trapezoid; support both.
# numpy 2.0 将 trapz 重命名为 trapezoid；兼容两者。
_trapezoid = getattr(np, "trapezoid", None) or np.trapz


# ---------------------------------------------------------------------------
# Internal helpers / 内部辅助
# ---------------------------------------------------------------------------

def _as_q_i(q: Any, intensity: Any, q_unit: str = "nm^-1") -> tuple[np.ndarray, np.ndarray]:
    """Coerce inputs to sorted ascending positive-q arrays (q normalized to nm⁻¹).

    将输入整理为 q 升序、为正的数组（q 统一换算到 nm⁻¹）。
    """
    if q_unit not in _VALID_Q_UNIT:
        raise ValueError(
            f"q_unit must be one of {_VALID_Q_UNIT}, got '{q_unit}'. "
            f"q_unit 必须为 {_VALID_Q_UNIT} 之一，当前值为 '{q_unit}'。"
        )
    qarr = np.asarray(q, dtype=float).ravel()
    iarr = np.asarray(intensity, dtype=float).ravel()
    if qarr.shape != iarr.shape:
        raise ValueError(
            f"q and intensity must have equal length, got {qarr.shape} vs {iarr.shape}. "
            f"q 与 intensity 长度必须一致，当前为 {qarr.shape} 与 {iarr.shape}。"
        )
    finite = np.isfinite(qarr) & np.isfinite(iarr) & (qarr > 0)
    qarr, iarr = qarr[finite], iarr[finite]
    if qarr.size < 8:
        raise ValueError(
            "need at least 8 valid (q>0, finite) points for lamellar analysis. "
            "片晶分析至少需要 8 个有效（q>0 且有限）数据点。"
        )
    if q_unit == "A^-1":
        qarr = qarr * 10.0  # Å⁻¹ → nm⁻¹ / Å⁻¹ → nm⁻¹
    order = np.argsort(qarr)
    qarr, iarr = qarr[order], iarr[order]
    # Collapse duplicated q nodes (mean) so interpolation stays well-defined.
    # 合并重复 q 节点（取均值），保证插值良定义。
    uniq_q, index = np.unique(qarr, return_inverse=True)
    if uniq_q.size != qarr.size:
        uniq_i = np.zeros_like(uniq_q)
        counts = np.zeros_like(uniq_q)
        np.add.at(uniq_i, index, iarr)
        np.add.at(counts, index, 1.0)
        iarr = uniq_i / counts
        qarr = uniq_q
    return qarr, iarr


def _smooth(y: np.ndarray, window: int) -> np.ndarray:
    """Simple moving-average smoothing (even window → window+1).

    简单滑动平均平滑（偶数窗口自动 +1）。
    """
    w = int(window)
    if w < 3:
        return y.copy()
    if w % 2 == 0:
        w += 1
    if w >= y.size:
        w = y.size if y.size % 2 == 1 else y.size - 1
    if w < 3:
        return y.copy()
    kernel = np.ones(w) / w
    padded = np.pad(y, (w // 2, w // 2), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def estimate_background(intensity: np.ndarray) -> float:
    """Flat-background level from the high-q tail (mean of the last 15%).

    用高 q 尾部（最后 15% 点的均值）估计平坦背景水平。
    """
    n = max(1, int(round(intensity.size * _BG_TAIL_FRACTION)))
    return float(np.mean(intensity[-n:]))


def subtract_background(
    q: Any, intensity: Any, *,
    mode: str = "auto",
    constant: float | None = None,
    q_unit: str = "nm^-1",
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Subtract a flat background from I(q).

    从 I(q) 中扣除平坦背景。

    Parameters
    ----------
    mode : {"none", "constant", "auto"}
        auto → estimate from the high-q tail; constant → use `constant`.
        auto → 用高 q 尾部估计；constant → 使用给定值。
    """
    if mode not in _VALID_BG_MODE:
        raise ValueError(
            f"mode must be one of {_VALID_BG_MODE}, got '{mode}'. "
            f"mode 必须为 {_VALID_BG_MODE} 之一，当前值为 '{mode}'。"
        )
    qarr, iarr = _as_q_i(q, intensity, q_unit)
    level = 0.0
    if mode == "auto":
        level = estimate_background(iarr)
    elif mode == "constant":
        if constant is None:
            raise ValueError(
                "mode='constant' requires a constant level. "
                "mode='constant' 需要提供 constant 水平值。"
            )
        level = float(constant)
    corrected = np.clip(iarr - level, 0.0, None)
    return qarr, corrected, {"mode": mode, "level": round(level, 6)}


# ---------------------------------------------------------------------------
# Method 1: Bragg / Lorentz-corrected peak / 方法一：Bragg（洛伦兹校正）峰
# ---------------------------------------------------------------------------

def bragg_long_period(
    q: Any, intensity: Any, *,
    q_unit: str = "nm^-1",
    smooth_window: int = _DEFAULT_SMOOTH_WINDOW,
    q_min: float | None = None,
    q_max: float | None = None,
    use_intensity: "np.ndarray | None" = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Long period from the Lorentz-corrected SAXS peak: L = 2π/q*.

    由洛伦兹校正 (I·q²) 后的 SAXS 峰求长周期：L = 2π/q*。

    When `use_intensity` is given (already background-subtracted), it is used
    directly and (q, intensity) are only consulted for the q axis.
    给定 use_intensity（已扣背景）时直接使用，(q, intensity) 仅提供 q 轴。

    Returns (result, meta): result carries q_star_nm, long_period_nm, peak
    intensity, FWHM, relative width and repeat-count estimate.
    """
    qarr, _ = _as_q_i(q, intensity if use_intensity is None else intensity, q_unit)
    I = np.asarray(use_intensity if use_intensity is not None else intensity, dtype=float).ravel()
    if I.size != qarr.size:
        raise ValueError("use_intensity must match the q axis length. / use_intensity 须与 q 轴等长。")

    # Optional peak-search window (excludes e.g. beamstop artifacts at low q).
    # 可选峰搜索窗口（如排除低 q 直射束伪影）。
    lo = qarr[0] if q_min is None else float(q_min)
    hi = qarr[-1] if q_max is None else float(q_max)
    win = (qarr >= lo) & (qarr <= hi)
    if int(win.sum()) < 5:
        raise ValueError(
            "peak search window contains <5 points; widen q_min/q_max. "
            "峰搜索窗口内不足 5 个点；请放宽 q_min/q_max。"
        )
    qw = qarr[win]
    # Lorentz correction for lamellar (1-D) systems: I·q².
    # 层状（一维）体系的洛伦兹校正：I·q²。
    lorenz = _smooth(I[win] * qw * qw, smooth_window)

    idx = int(np.argmax(lorenz))
    q_star = float(qw[idx])
    peak_val = float(lorenz[idx])
    baseline = float(np.min(lorenz))
    half = baseline + (peak_val - baseline) / 2.0

    # Half-maximum crossings around the peak (linear interp), within window.
    # 峰位两侧半高交点（窗口内线性插值）。
    def _cross(start: int, step: int) -> float | None:
        j = start
        while 0 <= j + step < lorenz.size:
            a, b = lorenz[j], lorenz[j + step]
            if (a - half) * (b - half) <= 0 and a != b:
                frac = (half - a) / (b - a)
                return float(qw[j] + frac * (qw[j + step] - qw[j]))
            j += step
        return None

    left = _cross(idx, -1)
    right = _cross(idx, 1)
    fwhm = (right - left) if (left is not None and right is not None) else None

    long_period = 2.0 * np.pi / q_star
    result: dict[str, Any] = {
        "q_star_nm": round(q_star, 6),
        "long_period_nm": round(long_period, 6),
        "peak_lorenz_intensity": round(peak_val, 6),
        "fwhm_nm_inv": round(fwhm, 6) if fwhm is not None else None,
        "relative_width": round(fwhm / q_star, 6) if fwhm is not None else None,
        # Scherrer-like coherent repeat count N ≈ q*/Δq (first order).
        # 类 Scherrer 相干周期数 N ≈ q*/Δq（一级）。
        "n_repeats_estimate": round(q_star / fwhm, 2) if fwhm is not None and fwhm > 0 else None,
    }
    meta = {"method": "bragg", "window": [float(lo), float(hi)], "smooth_window": int(smooth_window)}
    return result, meta


# ---------------------------------------------------------------------------
# Method 2: 1-D correlation function / 方法二：一维相关函数（Strobl）
# ---------------------------------------------------------------------------

def correlation_function(
    q: Any, intensity: Any, *,
    q_unit: str = "nm^-1",
    r_max_nm: float | None = None,
    use_intensity: "np.ndarray | None" = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Normalized 1-D correlation function γ₁(x) of the lamellar stack.

    片晶堆叠的归一化一维相关函数 γ₁(x)。

    γ₁(x) = ∫ I(q) q² cos(qx) dq / ∫ I(q) q² dq     (γ₁(0) = 1)

    Computed by direct (trapezoidal) cosine integration on uniform q/r grids —
    no FFT assumption about periodicity, robust for the short q ranges typical
    of laboratory SAXS.
    在均匀 q/r 网格上直接（梯形）余弦积分——不假设周期性的 FFT，对实验室
    SAXS 常见的窄 q 范围更稳健。

    Returns (r_nm, gamma, meta).
    """
    qarr, _ = _as_q_i(q, intensity if use_intensity is None else intensity, q_unit)
    I = np.asarray(use_intensity if use_intensity is not None else intensity, dtype=float).ravel()
    if I.size != qarr.size:
        raise ValueError("use_intensity must match the q axis length. / use_intensity 须与 q 轴等长。")

    # Uniform q grid over the measured range.
    # 在测量范围内建立均匀 q 网格。
    qg = np.linspace(qarr[0], qarr[-1], _Q_GRID_NPT)
    Ig = np.interp(qg, qarr, I)
    f = Ig * qg * qg  # Lorentz-weighted integrand / 洛伦兹加权被积函数
    dq = np.gradient(qg)

    # Real-space grid: default out to one full period of the lowest q.
    # 实空间网格：默认到最低 q 的一个完整周期。
    r_max = float(r_max_nm) if r_max_nm is not None else float(2.0 * np.pi / qg[0])
    if not (r_max > 0):
        r_max = 10.0
    rg = np.linspace(0.0, r_max, _R_GRID_NPT)

    # Direct cosine transform, vectorized as an outer product.
    # 直接余弦变换，外积向量化。
    cos_mx = np.cos(np.outer(qg, rg))
    num = (f * dq) @ cos_mx
    den = float(np.sum(f * dq))
    if den <= 0:
        raise ValueError(
            "∫ I q² dq ≤ 0 — check background subtraction / intensity sign. "
            "∫ I q² dq ≤ 0 —— 请检查背景扣除或强度符号。"
        )
    gamma = num / den

    meta = {
        "q_min_nm": round(float(qg[0]), 6),
        "q_max_nm": round(float(qg[-1]), 6),
        "r_max_nm": round(r_max, 4),
        "n_q": int(qg.size),
        "n_r": int(rg.size),
    }
    return rg, gamma, meta


def _first_extremum(x: np.ndarray, y: np.ndarray, *, mode: "str" = "max",
                    prominence: float = 0.0,
                    reference: float | None = None) -> tuple[float | None, float | None]:
    """First local extremum of y(x) after the initial decay from y[0].

    y(x) 自 y[0] 初始衰减后的第一个局部极值（max 或 min）。

    `prominence` filters out numerical ripple (truncated-transform Gibbs
    oscillations): a candidate max must rise at least `prominence` above
    `reference` (the preceding qualifying minimum), and vice versa for minima
    relative to `reference` treated as a peak level.
    `prominence` 过滤数值涟漪（截断变换的 Gibbs 振荡）：候选极大须比
    `reference`（前一个合格极小）高出至少 `prominence`；极小同理。
    """
    for i in range(1, y.size - 1):
        if mode == "min" and y[i] < y[i - 1] and y[i] <= y[i + 1]:
            if reference is not None and (reference - y[i]) < prominence:
                continue
            return float(x[i]), float(y[i])
        if mode == "max" and y[i] > y[i - 1] and y[i] >= y[i + 1]:
            if reference is not None and (y[i] - reference) < prominence:
                continue
            return float(x[i]), float(y[i])
    return None, None


def lamellar_from_correlation(
    q: Any, intensity: Any, *,
    q_unit: str = "nm^-1",
    minority_phase: str = "crystalline",
    r_max_nm: float | None = None,
    use_intensity: "np.ndarray | None" = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Long period & lamellar thickness from the 1-D correlation function.

    由一维相关函数提取长周期与片晶厚度。

    - L = position of the FIRST maximum of γ₁ (after the initial decay).
    - first minimum of γ₁ = thickness of the MINORITY phase (thinner layers);
      `minority_phase` states whether that is the crystalline or amorphous
      phase, which fixes l_c and l_a.
    - φ_c,stack = l_c / L (ideal two-phase stack crystallinity).

    - L = γ₁ 首极大（初始衰减后）的位置。
    - γ₁ 首极小 = 少数相（较薄层）的厚度；`minority_phase` 指明少数相是晶相
      还是非晶相，从而确定 l_c 与 l_a。
    - φ_c,stack = l_c / L（理想两相堆叠的结晶度）。
    """
    if minority_phase not in _VALID_MINORITY:
        raise ValueError(
            f"minority_phase must be one of {_VALID_MINORITY}, got '{minority_phase}'. "
            f"minority_phase 必须为 {_VALID_MINORITY} 之一，当前值为 '{minority_phase}'。"
        )
    rg, gamma, gmeta = correlation_function(
        q, intensity, q_unit=q_unit, r_max_nm=r_max_nm, use_intensity=use_intensity,
    )

    # Peak-presence gate: without a distinct SAXS peak in the raw profile the
    # γ₁ first maximum is dominated by finite-window truncation ringing (a
    # plain monotonic decay still rings after the q² weighting), so the long
    # period would be an artifact. Gate = interior argmax of the smoothed raw
    # profile that also stands above the high-q tail.
    # 峰存在性门控：原始曲线若无明显 SAXS 峰，γ₁ 首极大主要由有限窗口截断
    # 振荡决定（纯单调衰减经 q² 加权后同样会振荡），此时的长周期是伪影。
    # 判据 = 平滑后原始曲线的 argmax 位于内部且明显高于高 q 尾部。
    I_raw = np.asarray(use_intensity if use_intensity is not None else intensity, dtype=float).ravel()
    sm = _smooth(I_raw, 7)
    imax = int(np.argmax(sm))
    tail_n = max(3, int(0.1 * sm.size))
    tail_level = float(np.mean(sm[-tail_n:]))
    peak_interior = 2 < imax < sm.size - 3
    above_tail = sm[imax] >= 2.0 * max(tail_level, 1e-12) or (sm[imax] - tail_level) >= 0.2 * (sm.max() - sm.min() + 1e-12)
    has_peak = peak_interior and above_tail

    warnings: list[str] = []
    if not has_peak:
        warnings.append(
            "No distinct SAXS peak in the raw profile; the γ₁ long period would "
            "be a truncation artifact — not reported. / 原始曲线无明显 SAXS 峰；"
            "γ₁ 长周期将属截断伪影，不予报告。"
        )
        result: dict[str, Any] = {
            "long_period_nm": None,
            "l_crystalline_nm": None,
            "l_amorphous_nm": None,
            "first_min_nm": None,
            "first_max_nm": None,
            "gamma_first_min": None,
            "crystallinity_stack": None,
            "minority_phase": minority_phase,
        }
        return result, {**gmeta, "method": "correlation", "warnings": warnings}

    # Minimum: must dip meaningfully below γ(0)=1 (real two-phase γ₁ first
    # minima are near 0 or negative); drops pure numerical ripples.
    # 极小：须显著低于 γ(0)=1（真实两相 γ₁ 首极小接近 0 或为负）；
    # 过滤纯数值涟漪。
    _GAMMA_MIN_MAX_DROP = 0.25
    _EXTREMUM_PROMINENCE = 0.05

    x_min, gamma_min = _first_extremum(rg, gamma, mode="min")
    if x_min is not None and gamma_min is not None and (gamma[0] - gamma_min) < _GAMMA_MIN_MAX_DROP:
        x_min, gamma_min = None, None
    # Maximum: must rise clearly above the first minimum (ripple filter).
    # 极大：须明显高于首极小（涟漪过滤）。
    x_max, gamma_max = _first_extremum(
        rg, gamma, mode="max",
        prominence=_EXTREMUM_PROMINENCE,
        reference=gamma_min if gamma_min is not None else 1.0,
    )

    if x_min is None or x_max is None or not (x_max > x_min > 0):
        warnings.append(
            "γ₁ did not show a clear min→max sequence in the accessible r range; "
            "widen the q range (lower q_min / higher q_max) or check the background. "
            "γ₁ 在可及的 r 范围内未出现清晰的首极小→首极大序列；请展宽 q 范围"
            "（降低 q_min / 提高 q_max）或检查背景。"
        )
        result: dict[str, Any] = {
            "long_period_nm": None,
            "l_crystalline_nm": None,
            "l_amorphous_nm": None,
            "first_min_nm": None if x_min is None else round(x_min, 4),
            "first_max_nm": None if x_max is None else round(x_max, 4),
            "gamma_first_min": None if gamma_min is None else round(gamma_min, 6),
            "crystallinity_stack": None,
            "minority_phase": minority_phase,
        }
        return result, {**gmeta, "method": "correlation", "warnings": warnings}

    long_period = x_max
    l_minority = x_min
    if minority_phase == "crystalline":
        l_c, l_a = l_minority, long_period - l_minority
    else:
        l_a, l_c = l_minority, long_period - l_minority
    phi_c = l_c / long_period

    if gamma_min is not None and gamma_min < -0.05:
        warnings.append(
            "γ₁ dips well below zero (strong oscillation) — the q range may be "
            "truncated or the background over-subtracted. "
            "γ₁ 显著低于零（强振荡）——q 范围可能被截断或背景过度扣除。"
        )

    result = {
        "long_period_nm": round(long_period, 4),
        "l_crystalline_nm": round(l_c, 4),
        "l_amorphous_nm": round(l_a, 4),
        "first_min_nm": round(x_min, 4),
        "first_max_nm": round(x_max, 4),
        "gamma_first_min": round(gamma_min, 6),
        "crystallinity_stack": round(phi_c, 4),
        "minority_phase": minority_phase,
    }
    meta = {**gmeta, "method": "correlation", "warnings": warnings}
    return result, meta


# ---------------------------------------------------------------------------
# Orchestration / 顶层编排
# ---------------------------------------------------------------------------

def analyze_lamellar(q: Any, intensity: Any, **opts: Any) -> dict[str, Any]:
    """Full lamellar pipeline: background → methods → reporting.

    完整片晶分析流水线：背景扣除 → 方法计算 → 报告。

    Parameters
    ----------
    q, intensity : array-like
        1-D SAXS profile (q ascending or any order; NaN/negative-q dropped).
    q_unit : {"nm^-1", "A^-1"}
        Unit of the supplied q. All outputs in nm / nm⁻¹.
    methods : list[str], default ["bragg", "correlation"]
    background : dict
        mode ("none"|"constant"|"auto"), constant.
    minority_phase : {"crystalline", "amorphous"}, default "crystalline"
        Which phase is the thinner (minority) layer of the stack.
    bragg : dict
        smooth_window, q_min, q_max (peak-search window).
    correlation : dict
        r_max_nm (optional override).

    Returns
    -------
    dict
        q_nm, intensity (raw), corrected_intensity, background info, gamma_r,
        gamma, results (list per method), warnings.
    """
    q_unit = opts.get("q_unit", "nm^-1")
    methods = list(opts.get("methods") or ["bragg", "correlation"])
    for m in methods:
        if m not in _VALID_METHODS:
            raise ValueError(
                f"methods must be a subset of {_VALID_METHODS}, got '{m}'. "
                f"methods 必须为 {_VALID_METHODS} 的子集，当前含 '{m}'。"
            )
    bg_opts = opts.get("background") or {}
    bg_mode = bg_opts.get("mode", "auto")
    minority_phase = opts.get("minority_phase", "crystalline")

    warnings: list[str] = []
    qarr, corrected, bg_info = subtract_background(
        q, intensity,
        mode=bg_mode, constant=bg_opts.get("constant"), q_unit=q_unit,
    )
    raw_q, raw_i = _as_q_i(q, intensity, q_unit)
    if (qarr[-1] - qarr[0]) < _MIN_Q_SPAN_NM:
        warnings.append(
            f"q span {(qarr[-1] - qarr[0]):.3f} nm⁻¹ is very narrow; results may be unreliable. "
            f"q 跨度 {(qarr[-1] - qarr[0]):.3f} nm⁻¹ 过窄，结果可能不可信。"
        )
    if bg_mode == "none":
        warnings.append(
            "No background subtracted; γ₁ may ride on a spurious low-frequency "
            "component — prefer auto/constant background. "
            "未扣除背景；γ₁ 可能叠加虚假低频分量——建议使用 auto/constant 背景。"
        )

    results: list[dict[str, Any]] = []
    gamma_r: list[float] = []
    gamma: list[float] = []

    if "bragg" in methods:
        b_opts = opts.get("bragg") or {}
        r, m = bragg_long_period(
            qarr, corrected,
            q_unit="nm^-1",
            smooth_window=int(b_opts.get("smooth_window", _DEFAULT_SMOOTH_WINDOW)),
            q_min=b_opts.get("q_min"),
            q_max=b_opts.get("q_max"),
            use_intensity=corrected,
        )
        results.append({**r, "method": "bragg"})

    if "correlation" in methods:
        c_opts = opts.get("correlation") or {}
        r, m = lamellar_from_correlation(
            qarr, corrected,
            q_unit="nm^-1",
            minority_phase=minority_phase,
            r_max_nm=c_opts.get("r_max_nm"),
            use_intensity=corrected,
        )
        results.append({**r, "method": "correlation"})
        for w in m.pop("warnings", []):
            if w not in warnings:
                warnings.append(w)
        # Expose γ₁ for plotting (same grid regardless of extraction success).
        # 暴露 γ₁ 供绘图（无论提取是否成功，网格一致）。
        rg, gm, _ = correlation_function(
            qarr, corrected, q_unit="nm^-1",
            r_max_nm=c_opts.get("r_max_nm"), use_intensity=corrected,
        )
        gamma_r = rg.tolist()
        gamma = gm.tolist()

    # Cross-method consistency note. / 方法间一致性提示。
    l_bragg = next((x["long_period_nm"] for x in results if x.get("method") == "bragg"), None)
    l_corr = next((x["long_period_nm"] for x in results if x.get("method") == "correlation"), None)
    if l_bragg is not None and l_corr is not None and l_bragg > 0:
        rel = abs(l_bragg - l_corr) / l_bragg
        if rel > 0.15:
            warnings.append(
                f"Bragg L ({l_bragg:.2f} nm) and correlation-function L ({l_corr:.2f} nm) "
                f"differ by {rel * 100:.0f}% — peak assignment or background may need review. "
                f"Bragg 长周期（{l_bragg:.2f} nm）与相关函数长周期（{l_corr:.2f} nm）相差 "
                f"{rel * 100:.0f}% —— 请复查峰归属或背景。"
            )

    return {
        "q_nm": raw_q.tolist(),
        "intensity": raw_i.tolist(),
        "corrected_intensity": corrected.tolist(),
        "background": bg_info,
        "gamma_r": gamma_r,
        "gamma": gamma,
        "results": results,
        "warnings": warnings,
        "quality": {
            "q_min_nm": round(float(qarr[0]), 6),
            "q_max_nm": round(float(qarr[-1]), 6),
            "n_points": int(qarr.size),
        },
    }
