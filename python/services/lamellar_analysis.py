#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lamellar structure analysis (SAXS) service for X-FAIS.
X-FAIS 聚合物 SAXS 片晶结构分析服务模块。

Extracts lamellar structural parameters from a 1-D SAXS profile I(q) via the
1-D correlation function (Strobl–Schneider) pipeline, exposing every
intermediate curve so users can inspect each step:
从一维 SAXS 曲线 I(q) 出发，按一维相关函数（Strobl–Schneider）流水线提取片晶
结构参数，并暴露每一步的中转曲线供用户逐步检查：

    1. I(q)        — raw profile in the (optionally one-sided) q window
    2. I(q)−B      — flat-background-subtracted profile
    3. Z(q)=q²I(q) — Lorentz-corrected profile ("Iq²–q" curve) with a
                     high-q Porod-law extrapolation appended
                     (reduces transform-truncation ripples)
    4. γ₁(x)       — normalized 1-D correlation function, cosine transform
                     of Z(q), normalized to 1 at x = 0
    5. tangent fit — linear fit on the initial descending flank of γ₁; its
                     slope, R², fit window and intersections are reported
                     explicitly (the slope IS a user-facing result)

Method references (mature implementations this module follows) / 方法参考
（本模块所遵循的成熟实现）:
    - Strobl & Schneider, J. Polym. Sci., Polym. Phys. Ed. 18 (1980) 1343.
    - Ruland, Colloid Polym. Sci. 255 (1977) 417.
    - Koberstein & Stein, J. Polym. Sci. Phys. Ed. 21 (1983) 2181.
    - Goderis, Reynaers, Koch & Mathot, J. Polym. Sci. B: Polym. Phys. 37
      (1999) 1712 ("linear correlation functions", the corfunc lineage).
    - Baltá Calleja & Vonk, "X-ray Scattering of Synthetic Polymers",
      Elsevier (1989); Stribeck, "X-Ray Scattering of Soft Matter",
      Springer (2007).
    - SasView "Corfunc" perspective (sas.sascalc.corfunc, docs under
      src/sas/qtgui/Perspectives/Corfunc/media/) and the Diamond Light
      Source CORFUNC program (G. R. Mitchell) — same construction.

Physics of the tangent construction / 切线构图物理:
    For an ideal two-phase lamellar stack (crystalline thickness l_c,
    amorphous l_a, L = l_c + l_a, φ_c = l_c/L) the correlation function is
    piecewise linear: it leaves γ₁(0)=1 with slope −1/(L·φ_c·φ_a). Hence,
    with the tangent line γ_t(x) fitted on that initial flank:
        x at γ_t = γ_min  →  l_minority  (γ_min = level of the first
                            minimum; equals l_c when the crystalline phase
                            is the minority phase)
        |slope|            = 1/(L·φ_c·φ_a) → specific inner surface
                            O_s = 2·φ_c·φ_a·|slope| (interfaces per nm)
    The long period is the position of the FIRST maximum of γ₁ (2× the first
    minimum is reported as a cross-check, following SasView).

    理想两相片晶堆叠（晶区厚 l_c、非晶厚 l_a、L = l_c+l_a、φ_c = l_c/L）的
    γ₁ 分段线性：自 γ₁(0)=1 以斜率 −1/(L·φ_c·φ_a) 起降。因此对初始下降沿
    拟合切线 γ_t(x) 后：
        γ_t 与首极小水平线 γ_min 的交点 → 少数相厚度（少数相为晶相时即 l_c）
        |斜率| = 1/(L·φ_c·φ_a) → 比内表面积 O_s = 2φ_cφ_a·|斜率|
    长周期取 γ₁ 首极大位置（同时报告 2×首极小作交叉核对，同 SasView）。

    A flat background must be removed BEFORE the transform; a high-q Porod
    tail (I ∝ q^s, s≈−4) is extrapolated past the measured q_max so the
    cosine integral is not truncated (truncation ⇒ Gibbs ripples on γ₁).
    余弦变换前必须扣除平坦背景；并将高 q Porod 尾巴（I ∝ q^s，s≈−4）外推
    到测量 q_max 之外，避免截断引起 γ₁ 的 Gibbs 涟漪。

All q are normalized to nm⁻¹ internally (Å⁻¹ input is converted); all
lengths are reported in nm. 内部所有 q 统一为 nm⁻¹（Å⁻¹ 输入自动换算），
长度一律以 nm 报告。

Pure numpy, no I/O, no WebSocket code.
纯 numpy 实现，不含文件 I/O 与 WebSocket 代码。

Usage / 用法::

    from python.services.lamellar_analysis import analyze_lamellar

    result = analyze_lamellar(
        q_nm, intensity,
        q_unit="nm^-1",
        q_min=0.08,                # optional, one-sided windows allowed
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
# Which phase is the minority (thinner) phase of the stack. / 堆叠中的少数相。
_VALID_MINORITY = ("crystalline", "amorphous")
# Fraction of the high-q tail used for auto background estimation.
# 自动背景估计所用高 q 尾部比例。
_BG_TAIL_FRACTION = 0.15
# Fraction of the high-q tail used to fit the Porod power law.
# 拟合 Porod 幂律尾所用高 q 尾部比例。
_POROD_FIT_FRACTION = 0.15
# Extrapolated tail extends to fit_q_max × this factor.
# 外推尾巴延伸到拟合区间上限的该倍数。
_POROD_EXT_FACTOR = 3.0
# Points on the log-spaced extension grid. / 对数外推网格点数。
_POROD_EXT_NPTS = 384
# Points on the uniform q / r grids for the correlation function.
# 相关函数均匀 q / r 网格的默认点数。
_Q_GRID_NPT = 2048
_R_GRID_NPT = 2048
# Minimum span of q (nm⁻¹) below which the analysis is flagged unreliable.
# q 跨度（nm⁻¹）低于该值时结果被标记为不可信。
_MIN_Q_SPAN_NM = 0.05
# Tangent fit: minimum R² below which the tangent result is flagged.
# 切线拟合：R² 低于该值时切线结果被标记。
_TANGENT_MIN_R2 = 0.985
# Tangent vs first-minimum thickness relative disagreement that triggers a
# warning. / 切线法与首极小法厚度相对偏离超过该比例时给出警告。
_TAN_VS_MIN_WARN = 0.25

# numpy 2.0 renamed trapz → trapezoid; support both.
# numpy 2.0 将 trapz 重命名为 trapezoid；兼容两者。
_trapezoid = getattr(np, "trapezoid", None) or np.trapz


# ---------------------------------------------------------------------------
# Input conditioning / 输入整理
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


def _clip_q_window(
    q: np.ndarray, intensity: np.ndarray, *,
    q_min: float | None, q_max: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply the (each-side-optional) q window. q 上下限各自独立可选。

    Either bound may be None — e.g. with a mask the user often only needs a
    lower limit. / 任一界限可为空——例如配合 mask 时常只需下限。
    """
    keep = np.ones(q.size, dtype=bool)
    clipped: list[str] = []
    if q_min is not None:
        keep &= q >= float(q_min)
        clipped.append(f"q≥{float(q_min):g}")
    if q_max is not None:
        keep &= q <= float(q_max)
        clipped.append(f"q≤{float(q_max):g}")
    q_out, i_out = q[keep], intensity[keep]
    if q_out.size < 8:
        raise ValueError(
            f"q window ({', '.join(clipped) or 'full'}) leaves {q_out.size} points (<8); "
            f"relax q_min/q_max. q 窗口（{', '.join(clipped) or '全范围'}）后仅剩 "
            f"{q_out.size} 点（<8）；请放宽 q 上下限。"
        )
    return q_out, i_out


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


# ---------------------------------------------------------------------------
# Step 2: background / 第二步：背景扣除
# ---------------------------------------------------------------------------

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
# Step 3b: high-q Porod extrapolation / 第三步 b：高 q Porod 外推
# ---------------------------------------------------------------------------

def porod_extrapolation(
    q: np.ndarray,
    intensity: np.ndarray, *,
    fit_fraction: float = _POROD_FIT_FRACTION,
    ext_factor: float = _POROD_EXT_FACTOR,
    ext_npts: int = _POROD_EXT_NPTS,
) -> dict[str, Any] | None:
    """Fit I ≈ C·q^s on the high-q tail and extend it past q_max.

    在高 q 尾部拟合 I ≈ C·q^s 并延伸到测量 q_max 之外。

    The cosine transform of a truncated q²I(q) rings (Gibbs); continuing the
    Porod tail (s ≈ −4 for sharp interfaces) out to `ext_factor`× q_max
    damps those termination ripples — the same trick used by SasView's
    corfunc. Returns None (caller keeps the measured range) when the tail is
    not Porod-like (s > −1, e.g. rising aggregation tail) or unfittable.
    截断的 q²I(q) 余弦变换会产生 Gibbs 振荡；把 Porod 尾巴（清晰界面时
    s ≈ −4）延伸到 `ext_factor`× q_max 可抑制这种截断涟漪——与 SasView
    corfunc 同法。若尾部不符合 Porod（s > −1，如聚集上升尾）或无法拟合，
    返回 None（调用方仅用测量范围）。
    """
    n_fit = max(8, int(round(q.size * fit_fraction)))
    qs, Is = q[-n_fit:], intensity[-n_fit:]
    pos = Is > 0
    if int(pos.sum()) < 8:
        return None
    # Least squares in log-log. / 对数坐标最小二乘。
    slope, intercept = np.polyfit(np.log(qs[pos]), np.log(Is[pos]), 1)
    slope, intercept = float(slope), float(intercept)
    if not np.isfinite(slope) or slope > -1.0:
        return None

    q_hi = float(q[-1])
    q_ext_max = q_hi * float(ext_factor)
    ext_q = np.geomspace(q_hi, q_ext_max, int(ext_npts))
    ext_i = np.exp(intercept) * ext_q ** slope
    return {
        "slope": round(slope, 4),
        "amplitude": round(float(np.exp(intercept)), 8),
        "fit_q_min": round(float(qs[0]), 6),
        "fit_q_max": round(q_hi, 6),
        "n_fit": int(n_fit),
        "ext_q_max": round(q_ext_max, 4),
        "ext_q": ext_q.tolist(),
        "ext_intensity": ext_i.tolist(),
    }


# ---------------------------------------------------------------------------
# Step 4: 1-D correlation function / 第四步：一维相关函数（Strobl）
# ---------------------------------------------------------------------------

def correlation_function(
    q: Any,
    intensity: Any, *,
    q_unit: str = "nm^-1",
    r_max_nm: float | None = None,
    use_intensity: "np.ndarray | None" = None,
    porod: dict[str, Any] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Normalized 1-D correlation function γ₁(x) of the lamellar stack.

    片晶堆叠的归一化一维相关函数 γ₁(x)。

    γ₁(x) = ∫ I(q) q² cos(qx) dq / ∫ I(q) q² dq     (γ₁(0) = 1)

    Computed by direct (trapezoidal) cosine integration on a uniform measured
    grid plus the (log-spaced) Porod extension — no FFT periodicity
    assumption, robust for the short q ranges typical of laboratory SAXS.
    在均匀测量网格 +（对数 spaced）Porod 外推段上直接（梯形）余弦积分——
    不假设周期性的 FFT，对实验室 SAXS 常见的窄 q 范围更稳健。

    Returns (r_nm, gamma, meta).
    """
    qarr, _ = _as_q_i(q, intensity if use_intensity is None else intensity, q_unit)
    I = np.asarray(use_intensity if use_intensity is not None else intensity, dtype=float).ravel()
    if I.size != qarr.size:
        raise ValueError("use_intensity must match the q axis length. / use_intensity 须与 q 轴等长。")

    # Uniform grid over the measured range, plus the Porod extension if any.
    # 测量范围内均匀网格，若有 Porod 外推段则追加之。
    qg = np.linspace(qarr[0], qarr[-1], _Q_GRID_NPT)
    Ig = np.interp(qg, qarr, I)
    if porod is not None and porod.get("ext_q") and porod.get("ext_intensity"):
        ext_q = np.asarray(porod["ext_q"], dtype=float)
        ext_i = np.asarray(porod["ext_intensity"], dtype=float)
        if ext_q.size > 1 and ext_q[0] > qg[-1] * 0.999:
            qg = np.concatenate([qg, ext_q[1:]])
            Ig = np.concatenate([Ig, ext_i[1:]])
    f = Ig * qg * qg  # Lorentz-weighted integrand / 洛伦兹加权被积函数
    dq = np.gradient(qg)  # trapezoid weights, non-uniform-safe / 梯形权重，兼容非均匀

    # Real-space grid: default out to one full period of the lowest q.
    # 实空间网格：默认到最低 q 的一个完整周期。
    r_max = float(r_max_nm) if r_max_nm is not None else float(2.0 * np.pi / qg[0])
    if not (r_max > 0):
        r_max = 10.0
    rg = np.linspace(0.0, r_max, _R_GRID_NPT)

    # Direct cosine transform, vectorized as an outer product (chunked to
    # bound the transient memory of the (n_q × n_r) matrix).
    # 直接余弦变换，外积向量化（分块以限制 (n_q × n_r) 矩阵的瞬时内存）。
    gamma = np.empty_like(rg)
    den = float(np.sum(f * dq))
    if den <= 0:
        raise ValueError(
            "∫ I q² dq ≤ 0 — check background subtraction / intensity sign. "
            "∫ I q² dq ≤ 0 —— 请检查背景扣除或强度符号。"
        )
    chunk = 256
    for i0 in range(0, rg.size, chunk):
        cos_mx = np.cos(np.outer(qg, rg[i0:i0 + chunk]))
        gamma[i0:i0 + chunk] = (f * dq) @ cos_mx / den

    meta = {
        "q_min_nm": round(float(qg[0]), 6),
        "q_max_nm": round(float(qg[-1]), 6),
        "r_max_nm": round(r_max, 4),
        "n_q": int(qg.size),
        "n_r": int(rg.size),
        "porod_extended": bool(porod is not None),
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


# ---------------------------------------------------------------------------
# Step 5: tangent (linear) analysis of γ₁ / 第五步：γ₁ 切线（线性）分析
# ---------------------------------------------------------------------------

def tangent_analysis(
    r: np.ndarray,
    gamma: np.ndarray, *,
    x_first_min: float | None = None,
    fit_min_nm: float | None = None,
    fit_max_nm: float | None = None,
) -> dict[str, Any] | None:
    """Linear fit on the initial descending flank of γ₁ and its intersections.

    对 γ₁ 初始下降沿做线性拟合，并给出斜率与各交点。

    For an ideal two-phase stack the flank between x=0 and the first minimum
    is (mostly) linear with slope −1/(L·φ_c·φ_a). By DEFAULT the fit window
    is chosen automatically: a sliding window inside (0, x_first_min)
    maximising the R² of the least-squares line (SasView fits around the
    inflection point / half-minimum — with real, smoothed data both land on
    the same flank). The USER may override the window side-by-side via
    `fit_min_nm` / `fit_max_nm` (each optional on its own); a manual window
    is fitted directly, no search, and works even when no first minimum was
    detected (`x_first_min=None`).
    理想两相堆叠中 0 到首极小之间的下降沿近似线性，斜率
    −1/(L·φ_c·φ_a)。默认拟合窗口自动选取：(0, x_first_min) 内使最小二乘
    直线 R² 最大的滑动窗口（SasView 取拐点/半极小附近——真实平滑数据上
    两者落在同一沿上）。用户可通过 `fit_min_nm` / `fit_max_nm` 逐边覆盖
    （各自可选）；手动区间直接拟合、不做搜索，且在未检出首极小
    （`x_first_min=None`）时仍可使用。

    Returns None when no usable window (auto without x_first_min, or a manual
    window that is empty / has <8 points).
    """
    manual = fit_min_nm is not None or fit_max_nm is not None
    if not manual and x_first_min is None:
        return None

    if manual:
        # Manual window: missing sides fall back to the auto rules.
        # 手动窗口：缺省的一侧退回自动规则。
        lo = float(fit_min_nm) if fit_min_nm is not None else (
            0.08 * x_first_min if x_first_min is not None else float(r[1])
        )
        hi = float(fit_max_nm) if fit_max_nm is not None else (
            0.92 * x_first_min if x_first_min is not None else 0.5 * float(r[-1])
        )
        if not (hi > lo):
            return None
        sel = np.flatnonzero((r >= lo) & (r <= hi))
        if sel.size < 8:
            return None
        xs, ys = r[sel], gamma[sel]
        slope, intercept = np.polyfit(xs, ys, 1)
        pred = slope * xs + intercept
        ss_res = float(np.sum((ys - pred) ** 2))
        ss_tot = float(np.sum((ys - ys.mean()) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
        coef, window = np.array([slope, intercept]), sel
    else:
        # Auto: sliding windows inside the flank, 40%–80% of the span, step 5%.
        # 自动：下降沿内滑动窗口，宽度为区间的 40%–80%，步长 5%。
        win = (r > 0.08 * x_first_min) & (r < 0.92 * x_first_min)
        idx = np.flatnonzero(win)
        if idx.size < 8:
            return None
        n_span = idx.size
        best: tuple[float, np.ndarray, np.ndarray] | None = None  # (r2, coef, window)
        frac_width = max(0.40, min(0.80, 64.0 / max(n_span, 1)))
        frac = frac_width
        while frac <= 0.801:
            w = max(8, int(round(n_span * frac)))
            step = max(1, w // 8)
            for start in range(0, n_span - w + 1, step):
                selw = idx[start:start + w]
                xs, ys = r[selw], gamma[selw]
                slope, intercept = np.polyfit(xs, ys, 1)
                pred = slope * xs + intercept
                ss_res = float(np.sum((ys - pred) ** 2))
                ss_tot = float(np.sum((ys - ys.mean()) ** 2))
                r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
                if best is None or r2 > best[0]:
                    best = (r2, np.array([slope, intercept]), selw)
            frac += 0.10
        if best is None:
            return None
        r2, coef, window = best[0], best[1], best[2]
        lo = float(r[window][0])

    slope = float(coef[0])
    intercept = float(coef[1])

    # Sample the fitted line for plotting, slightly past the window's upper
    # end (and past the first minimum when known).
    # 采样拟合直线供绘图，略超窗口上端（已知首极小时也略超它）。
    x_line_max = max(lo * 1.0, float(r[window][-1]) * 1.25)
    if x_first_min is not None:
        x_line_max = max(x_line_max, 1.15 * x_first_min)
    line_r = np.linspace(0.0, x_line_max, 80)
    line_gamma = slope * line_r + intercept

    return {
        "window_mode": "manual" if manual else "auto",
        "slope_nm_inv": round(slope, 6),
        "intercept": round(intercept, 6),
        "r2": round(float(r2), 6),
        "fit_min_nm": round(float(r[window][0]), 4),
        "fit_max_nm": round(float(r[window][-1]), 4),
        "n_fit": int(window.size),
        "line_r": line_r.tolist(),
        "line_gamma": line_gamma.tolist(),
        # x where the tangent reaches γ = 0 / 切线与 γ=0 的交点。
        "x_at_gamma_zero": round(-intercept / slope, 4) if slope != 0 else None,
    }


# ---------------------------------------------------------------------------
# Extrema + tangent extraction / 极值 + 切线提取
# ---------------------------------------------------------------------------

def lamellar_from_correlation(
    q: Any, intensity: Any, *,
    q_unit: str = "nm^-1",
    minority_phase: str = "crystalline",
    r_max_nm: float | None = None,
    use_intensity: "np.ndarray | None" = None,
    porod: dict[str, Any] | None = None,
    tangent_opts: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Structural parameters from γ₁: extrema read-outs + tangent fit.

    从 γ₁ 提取结构参数：极值读出 + 切线拟合。

    - L = position of the FIRST maximum of γ₁ (long period; 2× the first
      minimum is reported as `long_period_2min_nm` cross-check, SasView-style).
    - Tangent on the initial flank: its intersection with the first-minimum
      LEVEL γ=γ_min gives the minority-phase thickness (tangent method);
      the slope is reported and feeds the specific inner surface.
    - Extrema method (kept for reference): first minimum of γ₁ read directly
      as the minority-phase thickness.
    - φ_c from the tangent method ("linear crystallinity", l_c/L).

    - L = γ₁ 首极大位置（长周期；同时报告 2×首极小 `long_period_2min_nm`
      作交叉核对，同 SasView）。
    - 初始沿切线：与首极小水平线 γ=γ_min 的交点给出少数相厚度（切线法）；
      斜率单独报告，并用于比内表面积。
    - 极值法（保留作参照）：γ₁ 首极小位置直接读作少数相厚度。
    - 切线法给出 φ_c（“线性结晶度”，l_c/L）。
    """
    if minority_phase not in _VALID_MINORITY:
        raise ValueError(
            f"minority_phase must be one of {_VALID_MINORITY}, got '{minority_phase}'. "
            f"minority_phase 必须为 {_VALID_MINORITY} 之一，当前值为 '{minority_phase}'。"
        )
    rg, gamma, gmeta = correlation_function(
        q, intensity, q_unit=q_unit, r_max_nm=r_max_nm,
        use_intensity=use_intensity, porod=porod,
    )

    # Peak-presence check on the raw profile. Since v0.2.6+ this is a WARNING,
    # not a gate: when γ₁ itself shows a clear min→max sequence the structural
    # read-outs are reported (flagged); only a profile with NO sequence at all
    # leaves them unreported. Features visible on the curve must not vanish
    # from the results.
    # 原始曲线峰存在性检查。现仅作警示、不再一票否决：只要 γ₁ 本身出现清晰的
    # 极小→极大序列即照常报告结构参数（附警告）；仅当完全没有序列时不予报告。
    # 曲线上看得见的特征不应从结果中消失。
    I_raw = np.asarray(use_intensity if use_intensity is not None else intensity, dtype=float).ravel()
    sm = _smooth(I_raw, 7)
    imax = int(np.argmax(sm))
    tail_n = max(3, int(0.1 * sm.size))
    tail_level = float(np.mean(sm[-tail_n:]))
    peak_interior = 2 < imax < sm.size - 3
    above_tail = sm[imax] >= 2.0 * max(tail_level, 1e-12) or (sm[imax] - tail_level) >= 0.2 * (sm.max() - sm.min() + 1e-12)
    has_peak = peak_interior and above_tail

    warnings: list[str] = []
    base_result: dict[str, Any] = {
        "long_period_nm": None,
        "long_period_2min_nm": None,
        "l_crystalline_nm": None,
        "l_amorphous_nm": None,
        "first_min_nm": None,
        "first_max_nm": None,
        "gamma_first_min": None,
        "crystallinity_stack": None,
        "l_minority_tangent_nm": None,
        "l_crystalline_tangent_nm": None,
        "l_amorphous_tangent_nm": None,
        "crystallinity_linear": None,
        "tangent_slope_nm_inv": None,
        "tangent_r2": None,
        "tangent_fit_min_nm": None,
        "tangent_fit_max_nm": None,
        "x_at_gamma_zero": None,
        "specific_surface_nm_inv": None,
        "minority_phase": minority_phase,
    }
    if not has_peak:
        warnings.append(
            "No distinct SAXS peak in the raw profile; γ₁ extrema may be "
            "truncation artifacts — results are still reported, judge with care. "
            "原始曲线无明显 SAXS 峰；γ₁ 极值可能为截断伪影——结果仍报出，请谨慎判断。"
        )

    # Minimum: a real two-phase first minimum dips far below γ(0)=1. Shallow
    # dips (<0.25) used to be discarded outright, hiding features visible on
    # the curve; now only sub-ripple dips (<0.05) are dropped — shallow ones
    # are kept with a warning.
    # 极小：真实两相首极小显著低于 γ(0)=1。过去浅于 0.25 一律弃用，导致曲线
    # 上看得见的极小从结果中消失；现在仅滤掉涟漪级（<0.05）浅谷，其余保留
    # 并附警告。
    _GAMMA_MIN_MAX_DROP = 0.25
    _MIN_ABS_DROP = 0.05
    _EXTREMUM_PROMINENCE = 0.05

    x_min, gamma_min = _first_extremum(rg, gamma, mode="min")
    if x_min is not None and gamma_min is not None and (gamma[0] - gamma_min) < _GAMMA_MIN_MAX_DROP:
        if (gamma[0] - gamma_min) < _MIN_ABS_DROP:
            x_min, gamma_min = None, None
        else:
            warnings.append(
                "γ₁ first minimum is shallow (dips <0.25 below γ(0)); read-outs "
                "kept but may be ripple-affected. / γ₁ 首极小较浅（低于 γ(0) 不足 "
                "0.25）；读数保留但可能受涟漪影响。"
            )
    # Maximum: must rise clearly above the first minimum (ripple filter).
    # 极大：须明显高于首极小（涟漪过滤）。
    x_max, gamma_max = _first_extremum(
        rg, gamma, mode="max",
        prominence=_EXTREMUM_PROMINENCE,
        reference=gamma_min if gamma_min is not None else 1.0,
    )

    # Tangent: auto window from the first minimum, or the user's manual window
    # (which works even when no extremum was detected).
    # 切线：默认按首极小自动开窗；用户手动区间优先，未检出首极小时仍可用。
    tan_opts = tangent_opts or {}
    tangent = tangent_analysis(
        rg, gamma, x_first_min=x_min,
        fit_min_nm=tan_opts.get("fit_min_nm"), fit_max_nm=tan_opts.get("fit_max_nm"),
    )
    if tangent is None and (tan_opts.get("fit_min_nm") is not None or tan_opts.get("fit_max_nm") is not None):
        warnings.append(
            "Manual tangent window is invalid or has <8 points; no tangent fit. "
            "手动切线区间无效或点数不足（<8）；未做切线拟合。"
        )

    if x_min is None or x_max is None or not (x_max > x_min > 0):
        warnings.append(
            "γ₁ did not show a clear min→max sequence in the accessible r range; "
            "widen the q range (lower q_min / higher q_max) or check the background. "
            "γ₁ 在可及的 r 范围内未出现清晰的首极小→首极大序列；请展宽 q 范围"
            "（降低 q_min / 提高 q_max）或检查背景。"
        )
        # A manual tangent is still useful without extrema — keep its fields.
        # 无极值时手动切线仍有价值——保留其字段。
        if tangent is not None:
            base_result.update({
                "tangent_slope_nm_inv": tangent["slope_nm_inv"],
                "tangent_r2": tangent["r2"],
                "tangent_fit_min_nm": tangent["fit_min_nm"],
                "tangent_fit_max_nm": tangent["fit_max_nm"],
                "x_at_gamma_zero": tangent.get("x_at_gamma_zero"),
            })
        return base_result, {**gmeta, "method": "correlation", "warnings": warnings, "tangent": tangent}

    long_period = float(x_max)
    # Extrema method: first minimum = minority thickness (classic read-out).
    # 极值法：首极小 = 少数相厚度（经典读出）。
    l_minority_extrema = float(x_min)
    if minority_phase == "crystalline":
        l_c_ext, l_a_ext = l_minority_extrema, long_period - l_minority_extrema
    else:
        l_a_ext, l_c_ext = l_minority_extrema, long_period - l_minority_extrema

    # Tangent method: the fit ran above (auto or manual window); intersect it
    # with the γ_min level. / 切线法：拟合已在上面完成（自动或手动），与
    # γ_min 水平线相交。
    l_minority_tan: float | None = None
    if tangent is not None:
        if tangent["r2"] < _TANGENT_MIN_R2:
            warnings.append(
                f"Tangent fit R² = {tangent['r2']:.3f} is low; the tangent-based "
                f"thickness/crystallinity may be unreliable. "
                f"切线拟合 R² = {tangent['r2']:.3f} 偏低；切线法厚度/结晶度可能不可靠。"
            )
        level = float(gamma_min)
        slope = tangent["slope_nm_inv"]
        if slope < 0:
            x_at_level = (level - tangent["intercept"]) / slope
            if 0.0 < x_at_level < 1.5 * x_min:
                l_minority_tan = float(x_at_level)
                tangent["x_at_gamma_min"] = round(float(x_at_level), 4)
        if l_minority_tan is None:
            tangent["x_at_gamma_min"] = None
            warnings.append(
                "Tangent does not reach the first-minimum level inside a sensible "
                "range; tangent thickness not reported. "
                "切线在合理范围内未到达首极小水平线；切线法厚度不予报告。"
            )
    else:
        warnings.append(
            "No linear region found on the initial γ₁ flank; tangent analysis "
            "skipped. 初始 γ₁ 沿未找到线性区；跳过切线分析。"
        )

    # Prefer the tangent thickness (Goderis/SasView construction); keep the
    # extrema values as the reference/cross-check.
    # 优先采用切线法厚度（Goderis/SasView 构图）；极值法保留作参照核对。
    if l_minority_tan is not None:
        l_minority = l_minority_tan
    else:
        l_minority = l_minority_extrema
    if minority_phase == "crystalline":
        l_c, l_a = l_minority, long_period - l_minority
    else:
        l_a, l_c = l_minority, long_period - l_minority
    phi_c = l_c / long_period

    # Specific inner surface from the tangent slope (Vonk):
    # O_s = 2φ_cφ_a|slope|; report only when the tangent is trustworthy.
    # 由切线斜率得比内表面积（Vonk）：O_s = 2φ_cφ_a|斜率|；仅当切线可信时报出。
    specific_surface: float | None = None
    if tangent is not None and l_minority_tan is not None:
        phi_a = 1.0 - phi_c
        specific_surface = round(2.0 * phi_c * phi_a * abs(slope), 4)

    if gamma_min is not None and gamma_min < -1.15:
        # Ideal asymmetric stacks dip to −φ_c/φ_a (legitimately below −1 for
        # majority-crystal systems); only clearly deeper minima hint at
        # truncation ringing / over-subtracted background.
        # 理想不对称堆叠的 γ_min = −φ_c/φ_a（晶相占多数时可合法低于 −1）；
        # 仅明显更深时才提示截断振荡/背景过扣。
        warnings.append(
            "γ₁ dips far below the ideal two-phase range — the q range may be "
            "truncated or the background over-subtracted. "
            "γ₁ 远低于理想两相范围——q 范围可能被截断或背景过度扣除。"
        )
    if l_minority_tan is not None:
        rel = abs(l_minority_tan - l_minority_extrema) / max(l_minority_extrema, 1e-9)
        if rel > _TAN_VS_MIN_WARN:
            warnings.append(
                f"Tangent thickness ({l_minority_tan:.2f} nm) and first-minimum "
                f"thickness ({l_minority_extrema:.2f} nm) differ by {rel * 100:.0f}% — "
                f"check the fit window / background. 切线法厚度（{l_minority_tan:.2f} nm）"
                f"与首极小法厚度（{l_minority_extrema:.2f} nm）相差 {rel * 100:.0f}% —— "
                f"请检查拟合窗口/背景。"
            )

    result = {
        **base_result,
        "long_period_nm": round(long_period, 4),
        "long_period_2min_nm": round(2.0 * x_min, 4),
        "l_crystalline_nm": round(l_c, 4),
        "l_amorphous_nm": round(l_a, 4),
        "first_min_nm": round(x_min, 4),
        "first_max_nm": round(x_max, 4),
        "gamma_first_min": round(gamma_min, 6),
        "crystallinity_stack": round(phi_c, 4),
        "l_minority_tangent_nm": round(l_minority_tan, 4) if l_minority_tan is not None else None,
        "l_crystalline_tangent_nm": round(l_c, 4) if l_minority_tan is not None else None,
        "l_amorphous_tangent_nm": round(l_a, 4) if l_minority_tan is not None else None,
        "crystallinity_linear": round(phi_c, 4) if l_minority_tan is not None else None,
        "tangent_slope_nm_inv": tangent["slope_nm_inv"] if tangent is not None else None,
        "tangent_r2": tangent["r2"] if tangent is not None else None,
        "tangent_fit_min_nm": tangent["fit_min_nm"] if tangent is not None else None,
        "tangent_fit_max_nm": tangent["fit_max_nm"] if tangent is not None else None,
        "x_at_gamma_zero": tangent.get("x_at_gamma_zero") if tangent is not None else None,
        "x_at_gamma_min": tangent.get("x_at_gamma_min") if tangent is not None else None,
        "specific_surface_nm_inv": specific_surface,
        "minority_phase": minority_phase,
    }
    meta = {**gmeta, "method": "correlation", "warnings": warnings, "tangent": tangent}
    return result, meta


# ---------------------------------------------------------------------------
# Orchestration / 顶层编排
# ---------------------------------------------------------------------------

def analyze_lamellar(q: Any, intensity: Any, **opts: Any) -> dict[str, Any]:
    """Full lamellar pipeline with per-step curves for the UI.

    完整片晶分析流水线，逐步输出中转曲线供 UI 展示。

    Steps / 步骤:
        1. clip to the q window (each bound optional) / q 窗口筛选（各自可选）
        2. subtract flat background / 扣平坦背景
        3. Lorentz correction Z(q) = q²·I(q) + Porod high-q extrapolation
           / 洛伦兹校正 Z(q) = q²·I(q) + 高 q Porod 外推
        4. cosine transform → γ₁(x) / 余弦变换 → γ₁(x)
        5. extrema + tangent (slope) analysis / 极值 + 切线（斜率）分析

    Parameters
    ----------
    q, intensity : array-like
        1-D SAXS profile (q ascending or any order; NaN/negative-q dropped).
    q_unit : {"nm^-1", "A^-1"}
        Unit of the supplied q. All outputs in nm / nm⁻¹.
    q_min, q_max : float, optional
        Each-side-optional q window, interpreted in the SAME unit as the
        input q (Å⁻¹ input → bounds are Å⁻¹ too; converted internally).
        各自独立可选的 q 上下限，与输入 q 同单位（Å⁻¹ 输入时界限亦为 Å⁻¹，
        内部自动换算）。
    background : dict
        mode ("none"|"constant"|"auto"), constant.
    minority_phase : {"crystalline", "amorphous"}, default "crystalline"
        Which phase is the thinner (minority) layer of the stack.
    correlation : dict
        r_max_nm (optional override).
    tangent : dict
        fit_min_nm / fit_max_nm (each optional) — manual tangent window on
        γ₁'s initial flank; empty → auto window (max-R² sliding search).
    porod : dict
        enabled (default True), fit_fraction, ext_factor.

    Returns
    -------
    dict
        q_nm, intensity (raw in-window), corrected_intensity, background,
        z_q/z_intensity (q²I on the measured grid), porod info +
        z_ext_q/z_ext_intensity (extension only), gamma_r/gamma, tangent,
        results (single correlation entry), warnings, quality.
    """
    q_unit = opts.get("q_unit", "nm^-1")
    bg_opts = opts.get("background") or {}
    bg_mode = bg_opts.get("mode", "auto")
    minority_phase = opts.get("minority_phase", "crystalline")
    c_opts = opts.get("correlation") or {}
    porod_opts = opts.get("porod") or {}

    warnings: list[str] = []

    # Step 1: q window (either bound may be absent). The bounds arrive in the
    # SAME unit as the input q, so they must be scaled together with the data
    # (Å⁻¹ → ×10) BEFORE clipping — otherwise an Å⁻¹ q_min would be applied as
    # an nm⁻¹ threshold, i.e. clip 10× less than intended.
    # 第一步：q 窗口。界限与输入 q 同单位，须与数据同步换算（Å⁻¹ → ×10）后再
    # 裁剪——否则 Å⁻¹ 的 q_min 会被当作 nm⁻¹ 阈值，裁剪量只有预期的 1/10。
    q_all, i_all = _as_q_i(q, intensity, q_unit)
    unit_scale = 10.0 if q_unit == "A^-1" else 1.0

    def _scaled(bound: Any) -> float | None:
        return float(bound) * unit_scale if bound is not None else None

    qarr, iarr = _clip_q_window(
        q_all, i_all, q_min=_scaled(opts.get("q_min")), q_max=_scaled(opts.get("q_max")),
    )

    # Step 2: background. / 第二步：背景。
    qarr, corrected, bg_info = subtract_background(
        qarr, iarr, mode=bg_mode, constant=bg_opts.get("constant"), q_unit="nm^-1",
    )
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

    # Step 3: Lorentz correction + Porod extrapolation. / 第三步：洛伦兹校正。
    z = corrected * qarr * qarr
    porod: dict[str, Any] | None = None
    if porod_opts.get("enabled", True):
        porod = porod_extrapolation(
            qarr, corrected,
            fit_fraction=float(porod_opts.get("fit_fraction", _POROD_FIT_FRACTION)),
            ext_factor=float(porod_opts.get("ext_factor", _POROD_EXT_FACTOR)),
        )
        if porod is None:
            warnings.append(
                "High-q tail is not Porod-like (or unfittable); no extrapolation "
                "was appended — γ₁ may show termination ripples. "
                "高 q 尾部不符合 Porod（或无法拟合）；未追加外推——γ₁ 可能出现"
                "截断涟漪。"
            )
    z_ext_q: list[float] = []
    z_ext: list[float] = []
    if porod is not None:
        z_ext_q = porod["ext_q"]
        z_ext = (np.asarray(porod["ext_intensity"]) * np.asarray(z_ext_q) ** 2).tolist()

    # Steps 4–5: correlation + extraction. / 第四、五步：相关函数与提取。
    result, meta = lamellar_from_correlation(
        qarr, corrected,
        q_unit="nm^-1",
        minority_phase=minority_phase,
        r_max_nm=c_opts.get("r_max_nm"),
        use_intensity=corrected,
        porod=porod,
        tangent_opts=opts.get("tangent") or {},
    )
    for w in meta.pop("warnings", []):
        if w not in warnings:
            warnings.append(w)
    rg, gm, _ = correlation_function(
        qarr, corrected, q_unit="nm^-1",
        r_max_nm=c_opts.get("r_max_nm"), use_intensity=corrected, porod=porod,
    )
    tangent = meta.pop("tangent", None)

    return {
        "q_nm": qarr.tolist(),
        "intensity": iarr.tolist(),
        "corrected_intensity": corrected.tolist(),
        "background": bg_info,
        "z_q": qarr.tolist(),
        "z": z.tolist(),
        "porod": porod,
        "z_ext_q": z_ext_q,
        "z_ext": z_ext,
        "gamma_r": rg.tolist(),
        "gamma": gm.tolist(),
        "tangent": tangent,
        "results": [{**result, "method": "correlation"}],
        "warnings": warnings,
        "quality": {
            "q_min_nm": round(float(qarr[0]), 6),
            "q_max_nm": round(float(qarr[-1]), 6),
            "n_points": int(qarr.size),
        },
    }
