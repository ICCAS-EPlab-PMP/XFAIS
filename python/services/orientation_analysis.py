#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymer orientation analysis service for X-FAIS.
X-FAIS 聚合物（高分子）取向度分析服务模块。

Computes polymer chain-axis orientation from azimuthal intensity profiles
I(χ) extracted from GIWAXS/WAXS 2D detector images (or supplied directly).
Three methods are supported:
    - Hermans orientation function (single-reflection, second moment)
    - FWHM orientation index (empirical, peak-width based)
    - Wilchinsky method (multi-reflection, handles monoclinic unit cells)

从 GIWAXS/WAXS 二维探测器图像提取（或由用户直接提供）的方位角强度分布
I(χ) 出发，计算聚合物链轴取向度。支持三种方法：
    - Hermans 取向函数（单反射、二阶矩）
    - FWHM 取向指数（经验、基于峰宽）
    - Wilchinsky 方法（多反射，支持单斜晶胞）

Pipeline / 处理流水线:
    raw I(χ) [possibly incomplete / with gaps]
      → ① symmetry detection & folding (Friedel / mirror, gap filling)
      → ② background subtraction (constant / linear; optional amorphous reference)
      → ③ orientation calculation (Hermans / FWHM / Wilchinsky, multi-select)
      → ④ reporting (f / FWHM / <cos²> + crystallinity + bias warnings)

    原始 I(χ) [可能不完整 / 有缺失]
      → ① 对称性检测与折叠（Friedel / 镜面，缺失补全）
      → ② 背景扣除（常数 / 线性；可选非晶参考曲线）
      → ③ 取向度计算（Hermans / FWHM / Wilchinsky，可多选）
      → ④ 报告（f / FWHM / <cos²> + 结晶度 + 偏差警示）

Equatorial-only & symmetry notes / 仅赤道面 + 对称性约定:
    - Equatorial reflections (hk0) have normals ⊥ chain axis c; in orthogonal
      cells the chain-axis second moment follows <cos²φ_c> = 1 − <cos²χ>.
    - In monoclinic cells (a–c not orthogonal) the single-reflection shortcut
      is invalid and the Wilchinsky route is required.
    - Friedel's law I(χ)=I(χ+180°) holds for transmission fiber geometry but
      NOT by default for reflection GIWAXS (in-plane powder assumption); the
      caller selects geometry to set the default.
    - The Hermans half-range [0,π/2] integral is exactly equivalent to the
      full-range form under I(φ)=I(π−φ); the sinφ solid-angle weight is
      unaffected by folding.

    - 赤道反射 (hk0) 的法向⊥链轴 c；正交晶系下链轴二阶矩
      <cos²φ_c> = 1 − <cos²χ>。
    - 单斜晶系（a-c 不正交）下单反射捷径失效，须走 Wilchinsky。
    - Friedel 定律 I(χ)=I(χ+180°) 在透射纤维几何成立，反射 GIWAXS 默认不成立
      （in-plane powder 假设）；由调用方选择几何以设定默认值。
    - Hermans 半区间 [0,π/2] 积分在 I(φ)=I(π−φ) 下与全区间严格等价；
      sinφ 立体角权重不受折叠影响。

Pure numpy, no I/O, no WebSocket code — mirrors image_stitch.py style.
纯 numpy 实现，不包含文件 I/O 与 WebSocket 代码，风格与 image_stitch.py 一致。

Usage / 用法::

    from python.services.orientation_analysis import analyze_orientation

    result = analyze_orientation(
        chi_deg, intensity,
        methods=["hermans", "fwhm"],
        geometry="transmission", symmetry="auto",
        background={"mode": "constant", "auto_estimate": True},
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

# Symmetry folding options. / 对称折叠选项。
_VALID_SYMMETRY = ("auto", "friedel", "meridional_mirror", "equatorial_mirror", "none")
# Scattering geometry. / 散射几何。
_VALID_GEOMETRY = ("transmission", "reflection")
# Missing-value handling strategies. / 缺失值处理策略。
_VALID_MISSING = ("interp", "drop", "mirror")
# Background subtraction modes. / 背景扣除模式。
_VALID_BG_MODE = ("none", "constant", "linear")
# Orientation calculation methods. / 取向度计算方法。
_VALID_METHODS = ("hermans", "fwhm", "wilchinsky")
# χ = 0 reference direction. / χ=0 的参考方向约定。
_VALID_CHI_ZERO = ("meridian", "equator")
# Monoclinic unique-axis convention (only b-axis supported, standard setting).
# 单斜唯一轴约定（仅支持标准 b-unique 设置）。
_VALID_UNIQUE_AXIS = ("b",)

# Pearson r above which a symmetry is auto-recommended. / 自动推荐对称性的 r 阈值。
_SYMMETRY_DETECT_THRESHOLD = 0.9
# A gap wider than this (degrees) in the raw χ coverage is flagged unreliable.
# 原始 χ 覆盖中大于此宽度（度）的间隙被标记为不可信。
_WIDE_GAP_DEG = 15.0
# Default angular grid resolution for folding (degrees per sample).
# 折叠默认角度网格分辨率（每采样点度数）。
_GRID_STEP_DEG = 1.0
# Percentile used to auto-estimate the isotropic (amorphous) background level.
# 自动估计各向同性（非晶）背景水平所用的百分位数。
_BG_PERCENTILE = 10.0

# numpy 2.0 renamed trapz → trapezoid; support both.
# numpy 2.0 将 trapz 重命名为 trapezoid；兼容两者。
_trapezoid = getattr(np, "trapezoid", None) or np.trapz


# ---------------------------------------------------------------------------
# Internal helpers / 内部辅助
# ---------------------------------------------------------------------------

def _as_chi_i(chi_deg: Any, intensity: Any) -> tuple[np.ndarray, np.ndarray]:
    """Coerce inputs to 1-D float arrays, keep only finite pairs, sort by χ.

    将输入转为 1-D 浮点数组，仅保留有限值对，按 χ 排序。
    """
    chi = np.asarray(chi_deg, dtype=float).ravel()
    inten = np.asarray(intensity, dtype=float).ravel()
    if chi.shape != inten.shape:
        raise ValueError(
            f"chi and intensity must have equal length, got {chi.shape} vs {inten.shape}. "
            f"chi 与 intensity 长度必须一致，当前为 {chi.shape} 与 {inten.shape}。"
        )
    if chi.size < 2:
        raise ValueError(
            f"need at least 2 (chi, intensity) points, got {chi.size}. "
            f"至少需要 2 个 (chi, intensity) 数据点，当前为 {chi.size}。"
        )
    finite = np.isfinite(chi) & np.isfinite(inten)
    chi = chi[finite]
    inten = inten[finite]
    if chi.size < 2:
        raise ValueError(
            "not enough finite (chi, intensity) points. "
            "有效的 (chi, intensity) 数据点不足。"
        )
    # Wrap to [0, 360) and sort. / 归一化到 [0, 360) 并排序。
    chi = np.mod(chi, 360.0)
    order = np.argsort(chi)
    return chi[order], inten[order]


def _periodic_interp(chi_sorted: np.ndarray, I_sorted: np.ndarray,
                     query_deg: np.ndarray) -> np.ndarray:
    """Periodic (period=360°) linear interpolation over sorted finite samples.

    在已排序的有限样本上做周期（周期 360°）线性插值。
    """
    return np.interp(np.mod(query_deg, 360.0), chi_sorted, I_sorted, period=360.0)


def _pearson_r(a: np.ndarray, b: np.ndarray) -> float:
    """Pearson correlation coefficient; returns 0.0 when degenerate.

    皮尔逊相关系数；退化情形返回 0.0。
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    am = a - a.mean()
    bm = b - b.mean()
    denom = np.sqrt(float((am * am).sum()) * float((bm * bm).sum()))
    if denom == 0.0 or not np.isfinite(denom):
        return 0.0
    return float((am * bm).sum() / denom)


def _detect_gaps(chi_sorted: np.ndarray) -> dict[str, float]:
    """Estimate the largest angular gap in the χ coverage (degrees).

    估计 χ 覆盖范围中最大的角度间隙（度）。
    """
    if chi_sorted.size < 2:
        return {"max": 360.0, "mean": 360.0}
    diffs = np.diff(chi_sorted)
    # Account for the periodic wrap-around gap (last → first + 360).
    # 计入周期环绕间隙（末点 → 首点 + 360）。
    wrap = 360.0 - chi_sorted[-1] + chi_sorted[0]
    all_gaps = np.append(diffs, wrap)
    all_gaps = all_gaps[all_gaps > 0]
    if all_gaps.size == 0:
        return {"max": 0.0, "mean": 0.0}
    return {"max": float(np.max(all_gaps)), "mean": float(np.mean(all_gaps))}


def _uniform_grid() -> np.ndarray:
    """Default [0, 360) uniform grid at 1° resolution.

    默认 [0, 360) 的 1° 分辨率均匀网格。
    """
    return np.arange(0.0, 360.0, _GRID_STEP_DEG)


# ---------------------------------------------------------------------------
# Group A: preprocessing / 预处理组
# ---------------------------------------------------------------------------

def detect_symmetry(chi_deg: Any, intensity: Any) -> dict[str, Any]:
    """Detect azimuthal symmetry by Pearson correlation.

    通过皮尔逊相关系数检测方位角对称性。

    Three symmetries are scored against the measured I(χ):
        - Friedel:          I(χ) vs I(χ + 180°)
        - meridional mirror: I(χ) vs I(−χ)         (mirror plane at χ = 0, the meridian)
        - equatorial mirror: I(χ) vs I(180° − χ)   (mirror plane at χ = 90°, the equator)

    The highest-scoring symmetry with r above the threshold is `recommended`.
    得分最高且 r 超过阈值的对称性记为 `recommended`（自动推荐值）。

    Parameters
    ----------
    chi_deg, intensity : array-like
        Azimuthal angle (degrees) and intensity. / 方位角（度）与强度。

    Returns
    -------
    dict
        friedel_r, meridional_mirror_r, equatorial_mirror_r, recommended.
    """
    chi, I = _as_chi_i(chi_deg, intensity)
    grid = _uniform_grid()
    base = _periodic_interp(chi, I, grid)
    friedel = _periodic_interp(chi, I, grid + 180.0)
    meridional = _periodic_interp(chi, I, -grid)
    equatorial = _periodic_interp(chi, I, 180.0 - grid)
    scores = {
        "friedel": _pearson_r(base, friedel),
        "meridional_mirror": _pearson_r(base, meridional),
        "equatorial_mirror": _pearson_r(base, equatorial),
    }
    best_key, best_r = max(scores.items(), key=lambda kv: kv[1])
    recommended = best_key if best_r >= _SYMMETRY_DETECT_THRESHOLD else "none"
    return {
        "friedel_r": round(scores["friedel"], 4),
        "meridional_mirror_r": round(scores["meridional_mirror"], 4),
        "equatorial_mirror_r": round(scores["equatorial_mirror"], 4),
        "recommended": recommended,
    }


def handle_missing(chi_deg: Any, intensity: Any, *, strategy: str = "interp") -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Fill or drop NaN/gaps in the raw I(χ).

    填充或丢弃原始 I(χ) 中的 NaN/缺失。

    Parameters
    ----------
    strategy : {"interp", "drop", "mirror"}
        - interp: linear-interpolate missing points on a 1° grid (default).
        - drop  : keep only finite samples (no filling).
        - mirror: detect symmetry, then fill gaps from the symmetric partner.

        - interp：在 1° 网格上线性插值缺失点（默认）。
        - drop  ：仅保留有限样本（不填充）。
        - mirror：检测对称性后用对称伴点填充缺失。

    Returns
    -------
    chi, intensity : np.ndarray
        Cleaned arrays on a uniform grid (interp/mirror) or sparse finite points (drop).
        interp/mirror 返回均匀网格上的清洗数组；drop 返回稀疏有限点。
    meta : dict
        max_gap_deg, mean_gap_deg, unreliable, strategy.
    """
    if strategy not in _VALID_MISSING:
        raise ValueError(
            f"strategy must be one of {_VALID_MISSING}, got '{strategy}'. "
            f"strategy 必须为 {_VALID_MISSING} 之一，当前值为 '{strategy}'。"
        )
    chi, I = _as_chi_i(chi_deg, intensity)
    gaps = _detect_gaps(chi)
    unreliable = gaps["max"] > _WIDE_GAP_DEG

    if strategy == "drop":
        return chi, I, {"max_gap_deg": gaps["max"], "mean_gap_deg": gaps["mean"],
                        "unreliable": unreliable, "strategy": strategy}

    grid = _uniform_grid()
    if strategy == "mirror":
        sym = detect_symmetry(chi, I)
        base = _periodic_interp(chi, I, grid)
        partner = _symmetric_partner(grid, sym["recommended"], chi, I)
        # Where the raw data has a wide gap, prefer the symmetric partner.
        # 原始数据存在宽间隙处，优先采用对称伴点。
        filled = np.where(np.isfinite(base) & np.isfinite(partner),
                          (base + partner) / 2.0,
                          np.where(np.isfinite(partner), partner, base))
    else:  # interp
        filled = _periodic_interp(chi, I, grid)

    return grid, filled, {"max_gap_deg": gaps["max"], "mean_gap_deg": gaps["mean"],
                          "unreliable": unreliable, "strategy": strategy}


def _symmetric_partner(grid: np.ndarray, symmetry: str,
                       chi: np.ndarray, I: np.ndarray) -> np.ndarray:
    """Interpolate I(χ) at the symmetry-transformed abscissa of `grid`.

    在 `grid` 的对称变换自变量处插值 I(χ)。
    """
    if symmetry == "friedel":
        q = grid + 180.0
    elif symmetry == "meridional_mirror":
        q = -grid
    elif symmetry == "equatorial_mirror":
        q = 180.0 - grid
    else:  # none / unknown → return NaN so averaging is a no-op
        return np.full_like(grid, np.nan)
    return _periodic_interp(chi, I, q)


def fold_symmetry(chi_deg: Any, intensity: Any, *,
                  symmetry: str = "auto",
                  geometry: str = "transmission") -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Symmetry-fold I(χ) onto a uniform 1° grid, averaging partners to cut noise.

    将 I(χ) 对称折叠到 1° 均匀网格上，平均对称伴点以降噪。

    Parameters
    ----------
    symmetry : {"auto", "friedel", "meridional_mirror", "equatorial_mirror", "none"}
        "auto" picks the best-detected symmetry, excluding Friedel when
        `geometry == "reflection"` (Friedel's law fails for in-plane powder).
        "auto" 选择检测到的最佳对称；当 `geometry=="reflection"` 时排除 Friedel
        （反射几何 in-plane powder 假设下 Friedel 定律失效）。
    geometry : {"transmission", "reflection"}
        Scattering geometry; only affects "auto" selection. / 散射几何；仅影响 auto 选择。

    Returns
    -------
    chi, intensity : np.ndarray
        Folded profile on the uniform [0, 360) grid. / 折叠后位于 [0,360) 均匀网格的分布。
    meta : dict
        applied (symmetry used), detected (full detect_symmetry dict), geometry, folded (bool).
    """
    if symmetry not in _VALID_SYMMETRY:
        raise ValueError(
            f"symmetry must be one of {_VALID_SYMMETRY}, got '{symmetry}'. "
            f"symmetry 必须为 {_VALID_SYMMETRY} 之一，当前值为 '{symmetry}'。"
        )
    if geometry not in _VALID_GEOMETRY:
        raise ValueError(
            f"geometry must be one of {_VALID_GEOMETRY}, got '{geometry}'. "
            f"geometry 必须为 {_VALID_GEOMETRY} 之一，当前值为 '{geometry}'。"
        )
    chi, I = _as_chi_i(chi_deg, intensity)
    detected = detect_symmetry(chi, I)
    grid = _uniform_grid()
    base = _periodic_interp(chi, I, grid)

    applied = symmetry
    if symmetry == "auto":
        scores = {
            "friedel": detected["friedel_r"],
            "meridional_mirror": detected["meridional_mirror_r"],
            "equatorial_mirror": detected["equatorial_mirror_r"],
        }
        # Reflection GIWAXS: Friedel's law does not hold by default.
        # 反射 GIWAXS：Friedel 定律默认不成立。
        if geometry == "reflection":
            scores.pop("friedel", None)
        best_key, best_r = max(scores.items(), key=lambda kv: kv[1])
        applied = best_key if best_r >= _SYMMETRY_DETECT_THRESHOLD else "none"

    if applied == "none":
        folded = base
    else:
        partner = _symmetric_partner(grid, applied, chi, I)
        folded = (base + partner) / 2.0

    return grid, folded, {
        "applied": applied,
        "detected": detected,
        "geometry": geometry,
        "folded": applied != "none",
    }


def subtract_background(chi_deg: Any, intensity: Any, *,
                        mode: str = "constant",
                        auto_estimate: bool = True,
                        constant: float | None = None,
                        reference_curve: tuple[Any, Any] | None = None,
                        reference_scale: float | None = None) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Subtract an isotropic / slowly-varying background (amorphous halo floor).

    扣除各向同性/缓变背景（非晶 halo 基底）。

    Levels / 级别:
        - Level 0 (mode "constant"/"linear"): removes an isotropic amorphous
          floor. A constant background EXACTLY restores f_c for isotropic
          amorphous contributions (f_meas = X·f_c → f_c after subtraction).
        - Level 1 (reference_curve): subtract a scaled pure-amorphous reference
          I_a(χ), for when the caller has a quenched-melt profile.

        - Level 0（mode "constant"/"linear"）：移除各向同性非晶基底。常数背景可
          精确还原各向同性非晶贡献下的 f_c（f_meas = X·f_c → 扣后得 f_c）。
        - Level 1（reference_curve）：扣除按比例缩放的纯非晶参考 I_a(χ)，
          适用于调用方具备淬火熔体曲线的情况。

    Parameters
    ----------
    mode : {"none", "constant", "linear"}
        Background shape. constant = flat floor; linear = first-order χ trend.
        背景形状。constant=平坦基底；linear=一阶 χ 趋势。
    auto_estimate : bool
        Estimate the constant level from a low percentile (default True).
        用低百分位数自动估计常数水平（默认 True）。
    constant : float, optional
        Explicit constant level; overrides auto_estimate when given.
        显式常数水平；提供时覆盖 auto_estimate。
    reference_curve : (chi_ref, I_ref), optional
        Pure-amorphous reference profile for Level 1 difference subtraction.
        纯非晶参考分布，用于 Level 1 差减。
    reference_scale : float, optional
        Scale factor k for I − k·I_ref; auto-chosen when None (low-percentile ratio).
        差减比例 k（I − k·I_ref）；为 None 时自动取低百分位之比。

    Returns
    -------
    chi, corrected : np.ndarray
        Background-subtracted intensity (clipped at 0). / 扣背景后强度（截断至 0）。
    background : np.ndarray
        The subtracted background curve. / 被扣除的背景曲线。
    meta : dict
        mode, constant, reference_scale, note.
    """
    if mode not in _VALID_BG_MODE:
        raise ValueError(
            f"mode must be one of {_VALID_BG_MODE}, got '{mode}'. "
            f"mode 必须为 {_VALID_BG_MODE} 之一，当前值为 '{mode}'。"
        )
    chi, I = _as_chi_i(chi_deg, intensity)
    grid = chi  # operate on the (already uniform, post-fold) grid supplied
    # If the caller passes a uniform grid (typical, post-fold), use it directly;
    # otherwise interpolate onto the input χ nodes (sorted, finite).
    # 调用方通常传入折叠后的均匀网格；否则在输入 χ 节点上插值。
    background = np.zeros_like(I, dtype=float)

    constant_val: float = 0.0
    note = "no background subtracted"
    if mode == "constant":
        if constant is None:
            constant_val = float(np.percentile(I, _BG_PERCENTILE)) if auto_estimate else 0.0
        else:
            constant_val = float(constant)
        background = np.full_like(I, constant_val)
        note = "isotropic amorphous floor removed; anisotropic amorphous NOT corrected"
    elif mode == "linear":
        # Robust first-order trend via least squares on χ (radians).
        # 对 χ（弧度）做最小二乘一阶趋势。
        chi_rad = np.deg2rad(chi)
        coeffs = np.polyfit(chi_rad, I, 1)  # [slope, intercept]
        background = np.polyval(coeffs, chi_rad)
        constant_val = float(np.mean(background))
        note = "isotropic amorphous floor removed; anisotropic amorphous NOT corrected"
    # mode == "none": background stays zeros. / mode=="none" 时背景保持零。

    ref_scale_used: float | None = None

    if reference_curve is not None:
        ref_chi, ref_I = _as_chi_i(reference_curve[0], reference_curve[1])
        ref_on_grid = _periodic_interp(ref_chi, ref_I, chi)
        if reference_scale is None:
            denom = float(np.percentile(ref_on_grid, _BG_PERCENTILE))
            numer = float(np.percentile(I - background, _BG_PERCENTILE))
            ref_scale_used = numer / denom if denom > 0 else 0.0
        else:
            ref_scale_used = float(reference_scale)
        background = background + ref_scale_used * ref_on_grid
        note = ("isotropic floor + amorphous reference subtraction"
                if mode != "none" else "amorphous reference subtraction")

    corrected = np.clip(I - background, 0.0, None)
    return chi, corrected, background, {
        "mode": mode,
        "constant": constant_val,
        "reference_scale": ref_scale_used,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Group B: orientation metrics / 取向度计算组
# ---------------------------------------------------------------------------

def _fold_to_quadrant(chi_deg: np.ndarray, intensity: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Fold any χ coverage onto [0°, 90°] by symmetry averaging (fiber symmetry).

    利用对称平均将任意 χ 覆盖折叠到 [0°, 90°]（纤维对称假设）。

    Assumes I(χ)=I(−χ)=I(180°−χ)=I(χ+180°) (the four quadrants are equivalent),
    which is the fiber-symmetry limit used by the Hermans half-range integral.
    假设 I(χ)=I(−χ)=I(180°−χ)=I(χ+180°)（四象限等价），即 Hermans 半区间积分
    所用的纤维对称极限。
    """
    chi, I = _as_chi_i(chi_deg, intensity)
    grid = np.arange(0.0, 90.0 + _GRID_STEP_DEG, _GRID_STEP_DEG)
    cov_min, cov_max = float(chi.min()), float(chi.max())
    # If the supplied χ spans nearly the full ring, all four mirror partners are
    # real measurements and get averaged. For partial coverage (e.g. an
    # equatorial window), out-of-range partners are masked to NaN so only the
    # genuinely measured quadrant contributes — no bogus edge extrapolation.
    # 若 χ 几乎覆盖整环，四个镜像伴点都是真实测量，取平均。若为部分覆盖
    # （如赤道窗口），超出范围的伴点置 NaN，只让真实测量象限贡献，避免边界外推。
    full_coverage = (cov_max - cov_min) >= 359.0
    queries = [grid, 180.0 - grid, 180.0 + grid, 360.0 - grid]
    columns = []
    for q in queries:
        qm = np.mod(q, 360.0)
        val = _periodic_interp(chi, I, qm)
        if not full_coverage:
            in_range = (qm >= cov_min) & (qm <= cov_max)
            val = np.where(in_range, val, np.nan)
        columns.append(val)
    stack = np.vstack(columns)
    Iq = np.nanmean(stack, axis=0)
    # All-NaN columns (no coverage anywhere) → 0 to keep the integral finite.
    # 全 NaN 列（完全无覆盖）填 0 以保持积分有限。
    Iq = np.where(np.isfinite(Iq), Iq, 0.0)
    return grid, Iq


def hermans_orientation(chi_deg: Any, intensity: Any, *,
                        chi_zero: str = "meridian",
                        equatorial_to_chain: bool = True,
                        reference_chi_deg: float | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Hermans orientation function from I(χ) (single-reflection second moment).

    由 I(χ) 计算 Hermans 取向函数（单反射二阶矩）。

    <cos²φ> = ∫ I(φ) cos²φ sinφ dφ / ∫ I(φ) sinφ dφ     (half-range [0, π/2])
    f       = (3 <cos²φ> − 1) / 2                         ∈ [−0.5, 1]

    For equatorial reflections (normal ⊥ chain axis c), the chain-axis second
    moment is <cos²φ_c> = 1 − <cos²χ> (orthogonal cells; monoclinic needs Wilchinsky).
    赤道反射（法向⊥链轴 c）下，链轴二阶矩 <cos²φ_c> = 1 − <cos²χ>
    （正交晶系；单斜须用 Wilchinsky）。

    Parameters
    ----------
    chi_zero : {"meridian", "equator"}
        Shorthand preset for the reference-axis (meridian / draw direction)
        position in χ: "meridian" → 0°, "equator" → 90°. Ignored when
        `reference_chi_deg` is given.
        参考轴（子午线/拉伸方向）在 χ 中位置的快捷预设：
        "meridian"→0°，"equator"→90°。给定 `reference_chi_deg` 时本参数被忽略。
    equatorial_to_chain : bool
        Convert the measured normal <cos²χ> to chain-axis <cos²φ_c>=1−<cos²χ>.
        将测得的法向 <cos²χ> 换算为链轴 <cos²φ_c>=1−<cos²χ>。
    reference_chi_deg : float, optional
        Explicit reference-axis (meridian) angle in χ space. The meridian is
        not necessarily at χ = 0 — set this when the fiber/draw axis sits at an
        arbitrary azimuth. χ is rotated by −reference_chi_deg before folding.
        显式参考轴（子午线）在 χ 空间的角度。子午线未必在 χ=0——当纤维/拉伸
        轴位于任意方位角时设置此项。折叠前 χ 会减去 reference_chi_deg。

    Returns
    -------
    result : dict
        f, cos2_phi (reported orientation second moment), cos2_normal,
        chi_zero, equatorial_to_chain, reference_chi_deg.
    meta : dict
        method, quadrant_chi, quadrant_intensity, n_points.
    """
    if chi_zero not in _VALID_CHI_ZERO:
        raise ValueError(
            f"chi_zero must be one of {_VALID_CHI_ZERO}, got '{chi_zero}'. "
            f"chi_zero 必须为 {_VALID_CHI_ZERO} 之一，当前值为 '{chi_zero}'。"
        )
    chi_arr = np.asarray(chi_deg, dtype=float)
    if reference_chi_deg is None:
        ref = 0.0 if chi_zero == "meridian" else 90.0
    else:
        ref = float(reference_chi_deg)
    # Rotate χ so the reference axis lands on 0; the folded angle is then the
    # normal-vs-reference angle φ.
    # 旋转 χ 使参考轴落在 0；折叠后的角度即法向与参考轴的夹角 φ。
    phi_raw = np.mod(chi_arr - ref, 360.0)
    q_deg, I_q = _fold_to_quadrant(phi_raw, intensity)
    phi_deg = q_deg
    phi = np.deg2rad(phi_deg)
    w = np.sin(phi)
    num = float(_trapezoid(I_q * np.cos(phi) ** 2 * w, phi))
    den = float(_trapezoid(I_q * w, phi))
    cos2_normal = num / den if den != 0.0 else 1.0 / 3.0
    # Clamp to physical [0, 1]. / 钳制到物理范围 [0, 1]。
    cos2_normal = min(max(cos2_normal, 0.0), 1.0)

    if equatorial_to_chain:
        cos2_phi = 1.0 - cos2_normal
    else:
        cos2_phi = cos2_normal
    f = (3.0 * cos2_phi - 1.0) / 2.0

    result = {
        "f": round(f, 6),
        "cos2_phi": round(cos2_phi, 6),
        "cos2_normal": round(cos2_normal, 6),
        "chi_zero": chi_zero,
        "equatorial_to_chain": equatorial_to_chain,
        "reference_chi_deg": round(ref, 4),
    }
    meta = {
        "method": "hermans",
        "quadrant_chi": q_deg.tolist(),
        "quadrant_intensity": I_q.tolist(),
        "n_points": int(q_deg.size),
    }
    return result, meta


def fwhm_orientation_index(chi_deg: Any, intensity: Any, *,
                           peak_window: float | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """FWHM orientation index f = (180° − H) / 180 from the main azimuthal peak.

    由主方位峰的半高宽 H 计算取向指数 f = (180° − H) / 180。

    Parameters
    ----------
    peak_window : float, optional
        Half-width (degrees) around the global max within which to measure FWHM.
        If None, the full supplied range is used. / 全局极大值附近测量 FWHM 的半宽（度）；
        为 None 时使用全部提供范围。

    Returns
    -------
    result : dict
        f, pi_pct (f×100), fwhm_deg (H), peak_chi, peak_intensity, baseline, snr.
    meta : dict
        method, peak_window.
    """
    chi, I = _as_chi_i(chi_deg, intensity)
    if peak_window is not None and peak_window > 0:
        peak_idx_global = int(np.argmax(I))
        center = chi[peak_idx_global]
        mask = np.abs(((chi - center + 180.0) % 360.0) - 180.0) <= peak_window
        if mask.sum() >= 3:
            chi = chi[mask]
            I = I[mask]
    baseline = float(np.min(I))
    peak_idx = int(np.argmax(I))
    peak_val = float(I[peak_idx])
    peak_chi = float(chi[peak_idx])
    half = baseline + (peak_val - baseline) / 2.0

    # Walk left/right from the peak to the half-maximum crossings (linear interp).
    # 从峰位向左右走到半高点（线性插值）。
    n = chi.size

    def _crossing(start: int, step: int) -> float:
        j = start
        while 0 <= j + step < n:
            if (I[j] - half) * (I[j + step] - half) <= 0 and I[j] != I[j + step]:
                # linear interp on χ / 对 χ 线性插值
                frac = (half - I[j]) / (I[j + step] - I[j])
                return float(chi[j] + frac * (chi[j + step] - chi[j]))
            j += step
        return float(chi[start])

    left_chi = _crossing(peak_idx, -1) if peak_idx > 0 else float(chi[0])
    right_chi = _crossing(peak_idx, 1) if peak_idx < n - 1 else float(chi[-1])
    fwhm = abs(right_chi - left_chi)
    f = (180.0 - fwhm) / 180.0
    # Signal-to-noise: peak height over baseline scatter (std of lower half).
    # 信噪比：峰高除以基线散布（较低半区的标准差）。
    lower_half = I[I <= np.median(I)]
    scatter = float(np.std(lower_half)) if lower_half.size > 1 else 1.0
    snr = (peak_val - baseline) / scatter if scatter > 0 else float("inf")

    result = {
        "f": round(f, 6),
        "pi_pct": round(f * 100.0, 4),
        "fwhm_deg": round(fwhm, 4),
        "peak_chi": round(peak_chi, 4),
        "peak_intensity": round(peak_val, 6),
        "baseline": round(baseline, 6),
        "snr": float(snr) if np.isfinite(snr) else None,
    }
    meta = {"method": "fwhm", "peak_window": peak_window}
    return result, meta


def _monoclinic_direction_cosines(h: float, k: float, l: float,
                                  a: float, b: float, c: float,
                                  beta_deg: float) -> tuple[float, float, float]:
    """Direction cosines (u1, u2, u3) of the (hkl) normal in the orthonormal
    crystal basis {e1∥a, e2∥b, e3 = e1×e2}, for a b-unique monoclinic cell.

    b-unique 单斜晶胞下，(hkl) 法向在正交晶体基 {e1∥a, e2∥b, e3=e1×e2} 中的
    方向余弦 (u1, u2, u3)。

    Cartesian convention (a along x, b along y, c in xz-plane at angle β from a):
    G = h·a* + k·b* + l·c*, with
        Gx = h/a,  Gy = k/b,  Gz = −h·cosβ/(a·sinβ) + l/(c·sinβ)
    so u_i = G_i / |G|. This is numerically stable and reduces to the
    orthogonal formula when β = 90° (verified in tests).

    Cartesian 约定（a 沿 x，b 沿 y，c 在 xz 平面与 a 成 β 角）：
    Gx = h/a，Gy = k/b，Gz = −h·cosβ/(a·sinβ) + l/(c·sinβ)，
    u_i = G_i / |G|。该实现数值稳定，且 β=90° 时退化为正交公式（测试验证）。
    """
    beta = np.deg2rad(beta_deg)
    sb = np.sin(beta)
    cb = np.cos(beta)
    gx = h / a
    gy = k / b
    gz = -h * cb / (a * sb) + l / (c * sb)
    norm = float(np.sqrt(gx * gx + gy * gy + gz * gz))
    if norm == 0.0:
        raise ValueError(
            f"reciprocal vector ({h},{k},{l}) has zero norm for the given cell. "
            f"给定晶胞下倒易矢量 ({h},{k},{l}) 模长为零。"
        )
    return gx / norm, gy / norm, gz / norm


def wilchinsky_chain_axis(reflections: list[dict[str, Any]], cell: dict[str, Any], *,
                          unique_axis: str = "b") -> tuple[dict[str, Any], dict[str, Any]]:
    """Wilchinsky chain-axis orientation from multiple reflections (monoclinic-capable).

    Wilchinsky 多反射链轴取向（支持单斜）。

    Solves the Wilchinsky system, for each reflection (hkl):
        <cos²χ_hkl> = u1²·<cos²φ_1> + u2²·<cos²φ_2> + u3²·<cos²φ_3>
    with closure <cos²φ_1>+<cos²φ_2>+<cos²φ_3> = 1 (least squares), then converts
    to the chain-axis second moment. For a b-unique monoclinic cell with the
    {e1∥a, e2∥b, e3=e1×e2} basis, the c axis reads
    ĉ = cosβ·e1 + sinβ·e3, so <cos²φ_c> = cos²β·<cos²φ_1> + sin²β·<cos²φ_3>
    (fiber-symmetry cross term vanishes), and f_c = (3<cos²φ_c>−1)/2.

    求解 Wilchinsky 方程组，每个反射 (hkl)：
        <cos²χ_hkl> = u1²·<cos²φ_1> + u2²·<cos²φ_2> + u3²·<cos²φ_3>
    附闭合约束 <cos²φ_1>+<cos²φ_2>+<cos²φ_3> = 1（最小二乘），再换算到链轴二阶矩。
    b-unique 单斜、{e1∥a, e2∥b, e3=e1×e2} 基下，c 轴为
    ĉ = cosβ·e1 + sinβ·e3，故 <cos²φ_c> = cos²β·<cos²φ_1> + sin²β·<cos²φ_3>
    （纤维对称交叉项为零），f_c = (3<cos²φ_c>−1)/2。

    Parameters
    ----------
    reflections : list of {"h","k","l","cos2"}
        Each reflection's measured <cos²χ> (normal vs reference axis).
        每个反射实测的 <cos²χ>（法向相对参考轴）。
    cell : {"a","b","c","beta"}
        Unit-cell parameters (Å, degrees); β = ∠(a,c), b-unique.
        晶胞参数（Å，度）；β=∠(a,c)，b-unique。
    unique_axis : {"b"}
        Monoclinic unique axis. Only "b" (standard) is supported.
        单斜唯一轴。仅支持标准 "b"。

    Returns
    -------
    result : dict
        f, cos2_phi_c, cos2_axes {1,2,3}, residual, condition_number,
        per-reflection {hkl, u, predicted, measured, residual}.
    meta : dict
        method, cell, unique_axis, n_reflections.
    """
    if unique_axis not in _VALID_UNIQUE_AXIS:
        raise ValueError(
            f"unique_axis must be one of {_VALID_UNIQUE_AXIS}, got '{unique_axis}'. "
            f"unique_axis 必须为 {_VALID_UNIQUE_AXIS} 之一，当前值为 '{unique_axis}'。"
        )
    if not reflections or len(reflections) < 1:
        raise ValueError(
            "wilchinsky requires at least 1 reflection. "
            "Wilchinsky 至少需要 1 个反射。"
        )
    try:
        a = float(cell["a"]); b = float(cell["b"]); c = float(cell["c"])
        beta = float(cell["beta"])
    except (KeyError, TypeError) as exc:
        raise ValueError(
            f"cell must contain a, b, c, beta. / cell 必须包含 a, b, c, beta。 ({exc})"
        ) from exc
    if min(a, b, c) <= 0 or not (0.0 < beta < 180.0):
        raise ValueError(
            f"cell parameters invalid (a,b,c>0, 0<beta<180). got a={a},b={b},c={c},beta={beta}. "
            f"晶胞参数非法（a,b,c>0，0<beta<180），当前 a={a},b={b},c={c},beta={beta}。"
        )

    # Build the linear system A·x = b with x = [<cos²φ_1>,<cos²φ_2>,<cos²φ_3>].
    # 建立线性方程组 A·x = b，x = [<cos²φ_1>,<cos²φ_2>,<cos²φ_3>]。
    rows: list[np.ndarray] = []
    meas: list[float] = []
    per_refl: list[dict[str, Any]] = []
    for ref in reflections:
        h = float(ref.get("h", ref.get(0, 0)))
        k = float(ref.get("k", ref.get(1, 0)))
        l = float(ref.get("l", ref.get(2, 0)))
        cos2_meas = float(ref.get("cos2", ref.get("cos2_chi", 0.0)))
        u1, u2, u3 = _monoclinic_direction_cosines(h, k, l, a, b, c, beta)
        rows.append(np.array([u1 * u1, u2 * u2, u3 * u3]))
        meas.append(cos2_meas)
        per_refl.append({
            "hkl": [int(h), int(k), int(l)],
            "u": [round(u1, 6), round(u2, 6), round(u3, 6)],
            "measured": round(cos2_meas, 6),
        })

    A = np.array(rows, dtype=float)
    b_vec = np.array(meas, dtype=float)
    # Closure constraint as a high-weight extra row: x1+x2+x3 = 1.
    # 闭合约束作为高权额外行：x1+x2+x3 = 1。
    closure_weight = 10.0
    A_aug = np.vstack([A, np.array([[closure_weight] * 3])])
    b_aug = np.append(b_vec, closure_weight)

    # Least squares. / 最小二乘。
    x, residuals, rank, sv = np.linalg.lstsq(A_aug, b_aug, rcond=None)
    cos2_1, cos2_2, cos2_3 = (min(max(float(v), 0.0), 1.0) for v in x)

    # Condition number of A (without closure) for reliability reporting.
    # A（不含闭合）的条件数，用于可靠性报告。
    cond = float(np.linalg.cond(A)) if A.shape[0] >= 3 else float("nan")

    # Chain-axis second moment: ĉ = cosβ·e1 + sinβ·e3 (b-unique monoclinic).
    # 链轴二阶矩：ĉ = cosβ·e1 + sinβ·e3（b-unique 单斜）。
    cb = np.cos(np.deg2rad(beta))
    sb = np.sin(np.deg2rad(beta))
    cos2_phi_c = (cb * cb) * cos2_1 + (sb * sb) * cos2_3
    cos2_phi_c = min(max(cos2_phi_c, 0.0), 1.0)
    f_c = (3.0 * cos2_phi_c - 1.0) / 2.0

    # Per-reflection predicted vs measured for residual reporting.
    # 逐反射预测 vs 实测，用于残差报告。
    predicted = A @ np.array([cos2_1, cos2_2, cos2_3])
    for entry, pred in zip(per_refl, predicted):
        entry["predicted"] = round(float(pred), 6)
        entry["residual"] = round(float(pred - entry["measured"]), 6)
    residual = float(np.sqrt(np.mean((predicted - b_vec) ** 2))) if b_vec.size else 0.0

    result = {
        "f": round(f_c, 6),
        "cos2_phi_c": round(cos2_phi_c, 6),
        "cos2_axes": {"1": round(cos2_1, 6), "2": round(cos2_2, 6), "3": round(cos2_3, 6)},
        "residual": round(residual, 6),
        "condition_number": None if np.isnan(cond) else round(cond, 4),
        "rank": int(rank),
        "reflections": per_refl,
    }
    meta = {
        "method": "wilchinsky",
        "cell": {"a": a, "b": b, "c": c, "beta": beta},
        "unique_axis": unique_axis,
        "n_reflections": len(reflections),
    }
    return result, meta


# ---------------------------------------------------------------------------
# Group C: orchestration / 顶层编排
# ---------------------------------------------------------------------------

def analyze_orientation(chi_deg: Any, intensity: Any, **opts: Any) -> dict[str, Any]:
    """Run the full preprocessing → metrics → reporting pipeline on one I(χ).

    对一条 I(χ) 执行完整的 预处理 → 指标 → 报告 流水线。

    Parameters
    ----------
    chi_deg, intensity : array-like
        Azimuthal profile (degrees). / 方位角分布（度）。
    methods : list[str], default ["hermans"]
        Subset of {"hermans","fwhm","wilchinsky"}. / 取向方法的子集。
    geometry, symmetry, missing : str
        Forwarded to fold_symmetry / handle_missing. / 透传给 fold_symmetry / handle_missing。
    background : dict
        mode, auto_estimate, constant, reference_curve, reference_scale.
    hermans : dict
        chi_zero, equatorial_to_chain. / chi_zero、equatorial_to_chain。
    fwhm : dict
        peak_window. / peak_window。
    wilchinsky : dict
        cell, reflections, unique_axis. / cell、reflections、unique_axis。
    crystallinity : float, optional
        User-supplied degree of crystallinity Xc (0–100) for bias reporting.
        用户提供的结晶度 Xc（0–100），用于偏差报告。

    Returns
    -------
    dict
        chi, intensity, folded_intensity, corrected_intensity, background,
        fold_info, background_info, results, crystallinity, warnings, quality.
    """
    methods = opts.get("methods") or ["hermans"]
    for m in methods:
        if m not in _VALID_METHODS:
            raise ValueError(
                f"methods must be a subset of {_VALID_METHODS}, got '{m}'. "
                f"methods 必须为 {_VALID_METHODS} 的子集，当前含 '{m}'。"
            )
    geometry = opts.get("geometry", "transmission")
    symmetry = opts.get("symmetry", "auto")
    missing = opts.get("missing", "interp")
    bg_opts = opts.get("background") or {}
    bg_mode = bg_opts.get("mode", "constant")
    crystallinity = opts.get("crystallinity")

    warnings: list[str] = []
    raw_chi, raw_I = _as_chi_i(chi_deg, intensity)
    raw_list = raw_I.tolist()

    # ① Missing-value handling, then symmetry folding on the filled grid.
    # ① 缺失值处理，随后在填充网格上做对称折叠。
    filled_chi, filled_I, miss_meta = handle_missing(raw_chi, raw_I, strategy=missing)
    if miss_meta.get("unreliable"):
        warnings.append(
            f"Large χ gap detected ({miss_meta['max_gap_deg']:.1f}°); "
            f"results may be unreliable. "
            f"检测到大 χ 间隙（{miss_meta['max_gap_deg']:.1f}°），结果可能不可信。"
        )

    fold_chi, fold_I, fold_info = fold_symmetry(
        filled_chi, filled_I, symmetry=symmetry, geometry=geometry,
    )
    # If folding was skipped (none), fall back to the filled grid directly.
    # 若折叠被跳过（none），直接退回填充网格。
    if not fold_info["folded"]:
        fold_chi, fold_I = filled_chi, filled_I

    # Surface the detected symmetry + reflection-geometry Friedel caveat.
    # 上报检测到的对称性 + 反射几何的 Friedel 注意事项。
    detected = fold_info.get("detected", {})
    if geometry == "reflection" and detected.get("friedel_r", 0) >= _SYMMETRY_DETECT_THRESHOLD:
        warnings.append(
            "Friedel symmetry detected but geometry is 'reflection' (GIWAXS); "
            "Friedel folding was NOT auto-applied. Override with symmetry='friedel' if intended. "
            "检测到 Friedel 对称但几何为反射 GIWAXS；未自动应用 Friedel 折叠。"
            "如确需，请显式设置 symmetry='friedel'。"
        )

    # ② Background subtraction. / ② 背景扣除。
    bg_kwargs: dict[str, Any] = {
        "mode": bg_mode,
        "auto_estimate": bg_opts.get("auto_estimate", True),
    }
    if bg_opts.get("constant") is not None:
        bg_kwargs["constant"] = bg_opts["constant"]
    if bg_opts.get("reference_curve") is not None:
        bg_kwargs["reference_curve"] = bg_opts["reference_curve"]
    if bg_opts.get("reference_scale") is not None:
        bg_kwargs["reference_scale"] = bg_opts["reference_scale"]

    corr_chi, corr_I, background, bg_info = subtract_background(fold_chi, fold_I, **bg_kwargs)

    # ③ Orientation metrics. / ③ 取向度计算。
    results: list[dict[str, Any]] = []
    if "hermans" in methods:
        h_opts = opts.get("hermans") or {}
        r, m = hermans_orientation(
            corr_chi, corr_I,
            chi_zero=h_opts.get("chi_zero", "meridian"),
            equatorial_to_chain=h_opts.get("equatorial_to_chain", True),
            reference_chi_deg=h_opts.get("reference_chi_deg"),
        )
        results.append({**r, "method": "hermans"})
    if "fwhm" in methods:
        f_opts = opts.get("fwhm") or {}
        r, m = fwhm_orientation_index(corr_chi, corr_I, peak_window=f_opts.get("peak_window"))
        results.append({**r, "method": "fwhm"})
    if "wilchinsky" in methods:
        w_opts = opts.get("wilchinsky") or {}
        if not w_opts.get("cell") or not w_opts.get("reflections"):
            warnings.append(
                "Wilchinsky selected but cell/reflections not provided; skipped. "
                "已选择 Wilchinsky 但未提供 cell/reflections，已跳过。"
            )
        else:
            r, m = wilchinsky_chain_axis(
                w_opts["reflections"], w_opts["cell"],
                unique_axis=w_opts.get("unique_axis", "b"),
            )
            results.append({**r, "method": "wilchinsky"})
            if r.get("condition_number") is not None and r["condition_number"] > 1e3:
                warnings.append(
                    f"Wilchinsky system is ill-conditioned "
                    f"(cond={r['condition_number']:.1f}); add more reflections. "
                    f"Wilchinsky 方程组病态（cond={r['condition_number']:.1f}），建议增加反射。"
                )

    # ④ Reporting: amorphous-bias caveat + crystallinity bias estimate.
    # ④ 报告：非晶偏差提示 + 结晶度偏差估计。
    if bg_mode in ("constant", "linear"):
        # Isotropic amorphous is corrected, but anisotropic amorphous is not.
        # 各向同性非晶已修正，但各向异性非晶未修正。
        warnings.append(
            "Isotropic amorphous background subtracted; anisotropic (oriented) "
            "amorphous contribution is NOT corrected and may still bias f low. "
            "已扣除各向同性非晶背景；各向异性（取向）非晶贡献未修正，可能仍使 f 偏低。"
        )
    crystallinity_hint: dict[str, Any] | None = None
    if crystallinity is not None:
        try:
            xc = float(crystallinity)
            if 0.0 < xc < 100.0:
                x = xc / 100.0
                crystallinity_hint = {
                    "xc_percent": xc,
                    "note": (
                        "Without amorphous separation, measured f ≈ X·f_c "
                        "(X = crystalline intensity fraction ≈ Xc). "
                        "未经非晶分离时，测得 f ≈ X·f_c（X≈结晶度 Xc）。"
                    ),
                    "correction_factor_guess": round(1.0 / x, 4) if x > 0 else None,
                }
        except (TypeError, ValueError):
            pass

    return {
        "chi": fold_chi.tolist(),
        "intensity": raw_list,
        "folded_intensity": fold_I.tolist(),
        "corrected_intensity": corr_I.tolist(),
        "background": background.tolist(),
        "fold_info": {**fold_info, "missing": miss_meta},
        "background_info": bg_info,
        "results": results,
        "crystallinity_hint": crystallinity_hint,
        "warnings": warnings,
        "quality": {
            "max_gap_deg": miss_meta.get("max_gap_deg"),
            "unreliable": miss_meta.get("unreliable", False),
            "n_raw_points": int(raw_chi.size),
        },
    }
