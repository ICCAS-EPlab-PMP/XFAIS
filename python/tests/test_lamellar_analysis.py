#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_lamellar_analysis.py — Tests for the SAXS lamellar analysis service.

Synthetic-data tests (v0.2.6, correlation-function pipeline only — the Bragg
peak method was removed):
  - One-sided q windows (q_min only / q_max only) clip correctly.
  - Background estimation from the high-q tail.
  - Porod extrapolation extends a q⁻⁴ tail and refuses a non-Porod tail.
  - Correlation-function machinery on a TRUE piecewise-linear γ₁ (ideal
    two-phase stack, asymmetric l_c ≠ l_a): long period, tangent slope,
    tangent/γ_min-intersection thickness, linear crystallinity and the
    specific inner surface are all recovered.
  - Full pipeline exposes every intermediate curve (I, I−B, q²I, γ₁, tangent).
"""

import numpy as np
import pytest

from python.services.lamellar_analysis import (
    analyze_lamellar,
    correlation_function,
    lamellar_from_correlation,
    porod_extrapolation,
    subtract_background,
    tangent_analysis,
)

_trap = getattr(np, "trapezoid", None) or np.trapz


def _gaussian_peak_profile(q_star=0.5, background=10.0, n=400):
    """Gaussian SAXS peak on a flat background over a dense q grid (nm⁻¹)."""
    q = np.linspace(0.05, 2.0, n)
    intensity = background + 100.0 * np.exp(-((q - q_star) ** 2) / (2 * 0.02 ** 2))
    return q, intensity


def _harmonic_stack_profile(L=12.0, m_harmonics=8, sigma=0.02, background=50.0, n=800):
    """I(q) whose q²·I is a 1/m² cosine-harmonic series at q_m = 2πm/L.

    Smooth (band-limited) γ₁ with first minimum at L/2 — the machinery
    target for the extrema read-outs.
    """
    q1 = 2.0 * np.pi / L
    q = np.linspace(0.15, 2.2, n)
    f = np.zeros_like(q)
    for m in range(1, m_harmonics + 1):
        f += (1.0 / m ** 2) * np.exp(-((q - m * q1) ** 2) / (2 * sigma ** 2))
    intensity = background + f / (q * q)
    return q, intensity


def _ideal_stack_profile(l_c=10.0, l_a=15.0, background=50.0, sigma=0.03, n=1200):
    """I(q) synthesized from the IDEAL piecewise-linear γ₁ of a two-phase stack.

    The 1-D correlation function of an ideal lamellar stack (thicknesses
    l_c, l_a) is piecewise linear; its cosine-series coefficients a_m are
    computed numerically and placed as harmonics at q_m = 2πm/L. The result
    is the exact machinery target for the tangent construction.
    理想两相片晶堆叠的 γ₁ 分段线性；数值求其余弦级数系数，并作为谐波放在
    q_m = 2πm/L 处——切线构图的精确基准。
    """
    L = l_c + l_a
    q1 = 2.0 * np.pi / L
    phi_c = l_c / L
    lv = -phi_c / (1.0 - phi_c)

    def gamma_ideal(x):
        x = np.mod(x, L)
        return np.where(
            x <= l_c,
            1.0 - (1.0 - lv) * x / l_c,
            np.where(x < l_a, lv, lv + (1.0 - lv) * (x - l_a) / l_c),
        )

    xs = np.linspace(0.0, L, 8192, endpoint=False)
    g0 = gamma_ideal(xs)
    q = np.linspace(0.08, 2.2, n)
    f = np.zeros_like(q)
    for m in range(1, 25):
        a_m = 2.0 / L * _trap((g0 - g0.mean()) * np.cos(m * q1 * xs), xs)
        f += a_m * np.exp(-((q - m * q1) ** 2) / (2 * sigma ** 2))
    intensity = background + np.clip(f, 0.0, None) / (q * q)
    return q, intensity


# ── q window (one-sided) / q 窗口（单边） ─────────────────────────────────────

def test_q_min_only_window():
    """A lone q_min clips the low-q beamstop artifact; q_max stays open."""
    q, I = _gaussian_peak_profile()
    result = analyze_lamellar(q, I, q_min=0.3)
    assert result["quality"]["q_min_nm"] >= 0.3
    assert result["quality"]["q_max_nm"] == pytest.approx(q[-1], rel=1e-6)


def test_q_max_only_window():
    q, I = _gaussian_peak_profile()
    result = analyze_lamellar(q, I, q_max=1.0)
    assert result["quality"]["q_max_nm"] <= 1.0
    assert result["quality"]["q_min_nm"] == pytest.approx(q[0], rel=1e-6)


def test_q_window_bounds_follow_input_unit():
    """Å⁻¹ input: q_min/q_max are Å⁻¹ too — clipped at ×10 the typed number.

    Å⁻¹ 输入时 q 上下限同为 Å⁻¹——裁剪位置是输入数值的 ×10（nm⁻¹ 内部值）。
    Regression: the bounds used to be applied as nm⁻¹ thresholds AFTER the
    data was scaled, silently clipping 10× less than intended.
    回归：界限曾被当作 nm⁻¹ 阈值作用在已换算的数据上，裁剪量只有预期 1/10。
    """
    q, I = _gaussian_peak_profile()  # nm⁻¹ grid 0.05–2.0
    result = analyze_lamellar(q * 0.1, I, q_unit="A^-1", q_min=0.05)
    # 0.05 Å⁻¹ = 0.5 nm⁻¹: clip lands just above 0.5, not at ≈0.005 (pre-fix).
    assert result["quality"]["q_min_nm"] >= 0.5
    assert result["quality"]["q_min_nm"] < 0.6


def test_q_window_too_narrow_raises():
    q, I = _gaussian_peak_profile()
    with pytest.raises(ValueError):
        analyze_lamellar(q, I, q_min=0.9, q_max=0.91)


# ── Background / 背景 ──────────────────────────────────────────────────────────

def test_background_auto_uses_high_q_tail():
    q = np.linspace(0.1, 2.0, 200)
    I = 25.0 + 100.0 * np.exp(-((q - 0.5) ** 2) / 0.02)
    _, corrected, info = subtract_background(q, I, mode="auto")
    assert info["level"] == pytest.approx(25.0, abs=1.0)
    assert corrected.min() >= 0.0


def test_background_constant_requires_level():
    q = np.linspace(0.1, 2.0, 50)
    with pytest.raises(ValueError):
        subtract_background(q, np.ones_like(q), mode="constant", constant=None)


def test_unit_conversion_A_to_nm():
    """q in Å⁻¹ is converted to nm⁻¹ (×10) internally."""
    q_nm = np.linspace(0.2, 2.0, 100)
    I = 10.0 + 50.0 * np.exp(-((q_nm - 0.6) ** 2) / 0.01)
    q_out, _, _ = subtract_background(q_nm * 0.1, I, mode="auto", q_unit="A^-1")
    assert q_out[0] == pytest.approx(q_nm[0], rel=1e-6)


def test_rejects_too_few_points():
    with pytest.raises(ValueError):
        subtract_background([0.1, 0.2, 0.3], [1.0, 2.0, 3.0], mode="auto")


# ── Porod extrapolation / Porod 外推 ───────────────────────────────────────────

def test_porod_extrapolation_extends_power_law_tail():
    q = np.geomspace(0.1, 2.0, 300)
    I = 1e-3 * q ** -4.0  # pure Porod tail / 纯 Porod 尾
    porod = porod_extrapolation(q, I)
    assert porod is not None
    assert porod["slope"] == pytest.approx(-4.0, abs=0.05)
    assert porod["ext_q_max"] > q[-1]
    ext_i = np.asarray(porod["ext_intensity"])
    ext_q = np.asarray(porod["ext_q"])
    # Continuation follows the same power law. / 延伸段遵循同一幂律。
    assert np.allclose(ext_i / (1e-3 * ext_q ** -4.0), 1.0, rtol=1e-3)


def test_porod_refuses_rising_tail():
    q = np.geomspace(0.1, 2.0, 200)
    I = q ** 2  # aggregation-like rising tail / 聚集式上升尾
    assert porod_extrapolation(q, I) is None


# ── Correlation function + tangent / 相关函数 + 切线 ──────────────────────────

def test_gamma_normalized_to_one_at_origin():
    q, I = _harmonic_stack_profile()
    r, gamma, _ = correlation_function(q, I)
    assert gamma[0] == pytest.approx(1.0, abs=1e-6)
    assert r[0] == 0.0


def test_correlation_recovers_period_and_min():
    L = 12.0
    q, I = _harmonic_stack_profile(L=L)
    q_corr, I_corr, _ = subtract_background(q, I, mode="auto")
    result, _ = lamellar_from_correlation(
        q_corr, I_corr, q_unit="nm^-1", minority_phase="crystalline",
        use_intensity=I_corr,
    )
    assert result["long_period_nm"] == pytest.approx(L, rel=0.05)
    # Smoothed triangular γ₁ → first minimum near L/2. / 平滑三角 γ₁ → 首极小近 L/2。
    assert result["first_min_nm"] == pytest.approx(L / 2.0, rel=0.08)


def test_ideal_stack_recovers_tangent_parameters():
    """Piecewise-linear γ₁: tangent slope/intersection recover l_c and φ_c."""
    l_c, l_a = 10.0, 15.0
    L = l_c + l_a
    phi_c = l_c / L
    q, I = _ideal_stack_profile(l_c=l_c, l_a=l_a)
    q_corr, I_corr, _ = subtract_background(q, I, mode="auto")
    result, meta = lamellar_from_correlation(
        q_corr, I_corr, minority_phase="crystalline", use_intensity=I_corr,
    )
    assert result["long_period_nm"] == pytest.approx(L, rel=0.02)
    assert result["x_at_gamma_min"] == pytest.approx(l_c, rel=0.03)
    assert result["l_crystalline_nm"] == pytest.approx(l_c, rel=0.03)
    assert result["l_amorphous_nm"] == pytest.approx(l_a, rel=0.03)
    assert result["crystallinity_linear"] == pytest.approx(phi_c, abs=0.02)
    ideal_slope = -1.0 / (L * phi_c * (1.0 - phi_c))
    assert result["tangent_slope_nm_inv"] == pytest.approx(ideal_slope, rel=0.08)
    assert result["tangent_r2"] > 0.99
    assert result["specific_surface_nm_inv"] == pytest.approx(2.0 / L, rel=0.08)


def test_ideal_stack_minority_phase_swap():
    """amorphous minority swaps l_c/l_a while keeping L and the slope."""
    q, I = _ideal_stack_profile(l_c=10.0, l_a=15.0)
    q_corr, I_corr, _ = subtract_background(q, I, mode="auto")
    r_c, _ = lamellar_from_correlation(q_corr, I_corr, minority_phase="crystalline", use_intensity=I_corr)
    r_a, _ = lamellar_from_correlation(q_corr, I_corr, minority_phase="amorphous", use_intensity=I_corr)
    assert r_a["long_period_nm"] == pytest.approx(r_c["long_period_nm"], rel=1e-6)
    # l_c=10 is the minority here, so both assignments report the same split
    # flipped. / 此处 l_c=10 为少数相，两种指派给出同一拆分的翻转。
    assert r_a["l_crystalline_nm"] == pytest.approx(r_a["long_period_nm"] - r_c["l_crystalline_nm"], rel=1e-3)


def test_tangent_analysis_reports_slope_and_windows():
    """Direct unit test of the sliding-window linear fit."""
    x = np.linspace(0.0, 20.0, 400)
    gamma = np.where(x <= 10.0, 1.0 - 0.1 * x, -1.0 + 0.1 * (x - 10.0) / 1.0)
    tan = tangent_analysis(x, gamma, x_first_min=10.0)
    assert tan is not None
    assert tan["slope_nm_inv"] == pytest.approx(-0.1, rel=1e-3)
    assert tan["r2"] > 0.999
    assert 0.0 < tan["fit_min_nm"] < tan["fit_max_nm"] < 10.0
    assert tan["window_mode"] == "auto"


def test_tangent_manual_window_fits_exactly_that_span():
    """Manual window (user-picked): fitted verbatim, no search; works without
    a detected first minimum. 手动区间（用户点选）：按原区间直接拟合、不做
    搜索；未检出首极小也可用。"""
    x = np.linspace(0.0, 20.0, 400)
    gamma = np.where(x <= 10.0, 1.0 - 0.1 * x, -1.0 + 0.1 * (x - 10.0) / 1.0)
    tan = tangent_analysis(x, gamma, fit_min_nm=2.0, fit_max_nm=8.0)
    assert tan is not None
    assert tan["window_mode"] == "manual"
    assert tan["slope_nm_inv"] == pytest.approx(-0.1, rel=1e-6)
    assert tan["fit_min_nm"] == pytest.approx(2.0, abs=0.05)
    assert tan["fit_max_nm"] == pytest.approx(8.0, abs=0.05)
    assert tan["r2"] > 0.999
    # No first minimum + no manual window → nothing to fit. / 无首极小且无手动
    # 区间 → 不拟合。
    assert tangent_analysis(x, gamma) is None


def test_pipeline_manual_tangent_reaches_results():
    """Full pipeline with a manual window overrides the auto estimate."""
    """带手动区间的完整流水线覆盖自动预估。"""
    q, I = _ideal_stack_profile(l_c=10.0, l_a=15.0)
    result = analyze_lamellar(
        q, I, background={"mode": "auto"},
        tangent={"fit_min_nm": 1.0, "fit_max_nm": 5.0},
    )
    tan = result["tangent"]
    assert tan["window_mode"] == "manual"
    assert tan["fit_min_nm"] == pytest.approx(1.0, abs=0.05)
    assert tan["fit_max_nm"] == pytest.approx(5.0, abs=0.05)
    assert result["results"][0]["tangent_fit_min_nm"] == tan["fit_min_nm"]


def test_correlation_flags_missing_extrema():
    """Monotonic decay: the no-peak warning is always raised; γ₁ ringing
    extrema may still be reported (flagged), but never silently without the
    warning. 曲线无峰时必附警告；γ₁ 振荡极值可以报出（带警示），但不会在
    无警告的情况下静默给出。"""
    q = np.linspace(0.2, 2.0, 300)
    I = 100.0 * np.exp(-3.0 * q)  # pure exponential decay / 纯指数衰减
    result, meta = lamellar_from_correlation(q, I, use_intensity=I)
    assert any("No distinct SAXS peak" in w for w in meta["warnings"])
    # Visible-on-γ₁ features must not vanish: either reported values or the
    # explicit no-sequence warning. / γ₁ 上看得见的特征不许消失：要么报出
    # 数值，要么给出明确的“无序列”警告。
    if result["long_period_nm"] is None:
        assert any("γ₁" in w or "γ1" in w for w in meta["warnings"])


# ── Pipeline / 流水线 ─────────────────────────────────────────────────────────

def test_analyze_lamellar_full_pipeline_exposes_step_curves():
    q, I = _ideal_stack_profile(l_c=10.0, l_a=15.0)
    result = analyze_lamellar(
        q, I,
        q_unit="nm^-1",
        background={"mode": "auto"},
        minority_phase="crystalline",
    )
    res = result["results"][0]
    assert res["method"] == "correlation"
    assert len(result["results"]) == 1
    assert res["long_period_nm"] == pytest.approx(25.0, rel=0.02)
    # Step curves present: raw/corrected I(q), q²I(q), γ₁, tangent overlay.
    # 各步曲线齐备：原始/扣背景 I(q)、q²I(q)、γ₁、切线叠加线。
    for key in ("q_nm", "intensity", "corrected_intensity", "z_q", "z", "gamma_r", "gamma"):
        assert isinstance(result[key], list) and len(result[key]) > 50, key
    assert len(result["z_q"]) == len(result["z"])
    assert result["gamma"][0] == pytest.approx(1.0, abs=1e-6)
    tan = result["tangent"]
    assert tan is not None and len(tan["line_r"]) == len(tan["line_gamma"])
    assert tan["slope_nm_inv"] < 0


def test_analyze_lamellar_no_bragg_method():
    """v0.2.6 removed the Bragg method entirely from the pipeline."""
    q, I = _gaussian_peak_profile()
    result = analyze_lamellar(q, I)
    assert all(r["method"] != "bragg" for r in result["results"])
