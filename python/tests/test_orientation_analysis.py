#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_orientation_analysis.py — Unit tests for the polymer orientation service.

Covers: symmetry detection & folding, missing-value handling, background
subtraction (amorphous floor + reference), Hermans orientation function
(isotropic limit, perfect-orientation limits, half/full-range equivalence),
FWHM orientation index, Wilchinsky method (orthogonal β=90° degeneracy and
monoclinic forward/inverse self-consistency), end-to-end pipeline, and
input-validation errors.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure python/ is importable / 确保 python/ 在导入路径上
_BETA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BETA_ROOT) not in sys.path:
    sys.path.insert(0, str(_BETA_ROOT))

from python.services.orientation_analysis import (  # noqa: E402
    analyze_orientation,
    detect_symmetry,
    fwhm_orientation_index,
    fold_symmetry,
    handle_missing,
    hermans_orientation,
    subtract_background,
    wilchinsky_chain_axis,
)


# ---------------------------------------------------------------------------
# Fixtures / 测试夹具
# ---------------------------------------------------------------------------

@pytest.fixture
def uniform_grid():
    """1°-spaced [0, 360) grid."""
    return np.arange(0.0, 360.0, 1.0)


@pytest.fixture
def isotropic_profile(uniform_grid):
    """Flat (isotropic) azimuthal profile of intensity 1.0."""
    return np.ones_like(uniform_grid)


def _gaussian_peak(chi, center, sigma, height=1.0, floor=0.0):
    """Gaussian peak on a flat floor (degrees)."""
    # shortest angular distance for the periodic wrap
    d = np.abs((chi - center + 180.0) % 360.0 - 180.0)
    return floor + height * np.exp(-(d ** 2) / (2.0 * sigma * sigma))


# ---------------------------------------------------------------------------
# Symmetry detection & folding / 对称性检测与折叠
# ---------------------------------------------------------------------------

class TestSymmetry:
    def test_friedel_detected(self, uniform_grid):
        """I(χ)=I(χ+180) → friedel_r ≈ 1, recommended = friedel."""
        I = 2.0 + np.sin(2 * np.deg2rad(uniform_grid))  # period 180 → Friedel-symmetric
        info = detect_symmetry(uniform_grid, I)
        assert info["friedel_r"] > 0.99
        assert info["recommended"] == "friedel"

    def test_meridional_mirror_detected(self, uniform_grid):
        """Even-symmetric about χ=0 → meridional_mirror_r ≈ 1."""
        # |sin(χ)| is even about 0 and 180 → both mirror symmetries hold; pick a
        # function even about 0 but NOT 180-periodic to single out meridional.
        I = 1.0 + np.cos(np.deg2rad(uniform_grid))  # cos is even about 0
        info = detect_symmetry(uniform_grid, I)
        assert info["meridional_mirror_r"] > 0.99

    def test_fold_averages_partners(self, uniform_grid):
        """Folding a noisy symmetric profile should reduce variance vs raw."""
        base = 1.0 + np.cos(np.deg2rad(uniform_grid))
        rng = np.random.default_rng(0)
        noisy = base + rng.normal(0.0, 0.2, size=base.shape)
        chi_f, I_f, meta = fold_symmetry(uniform_grid, noisy, symmetry="meridional_mirror")
        # folded profile should be closer to the noiseless base than the raw was
        raw_err = np.mean((noisy - base) ** 2)
        fold_err = np.mean((I_f - base) ** 2)
        assert fold_err < raw_err
        assert meta["applied"] == "meridional_mirror"
        assert meta["folded"] is True

    def test_reflection_geometry_excludes_friedel(self, uniform_grid):
        """In reflection geometry, auto must not pick Friedel even if it scores high."""
        I = 2.0 + np.sin(2 * np.deg2rad(uniform_grid))  # Friedel-symmetric
        _, _, meta = fold_symmetry(uniform_grid, I, symmetry="auto", geometry="reflection")
        assert meta["applied"] != "friedel"


# ---------------------------------------------------------------------------
# Missing-value handling / 缺失值处理
# ---------------------------------------------------------------------------

class TestMissing:
    def test_interp_fills_nan(self):
        chi = np.array([0.0, 90.0, 180.0, 270.0])
        I = np.array([1.0, np.nan, 3.0, 4.0])
        chi_o, I_o, meta = handle_missing(chi, I, strategy="interp")
        assert np.all(np.isfinite(I_o))
        assert meta["strategy"] == "interp"

    def test_drop_keeps_finite(self):
        chi = np.array([0.0, 90.0, 180.0, 270.0])
        I = np.array([1.0, np.nan, 3.0, 4.0])
        chi_o, I_o, meta = handle_missing(chi, I, strategy="drop")
        assert np.all(np.isfinite(I_o))
        assert I_o.size == 3
        assert meta["strategy"] == "drop"

    def test_wide_gap_flagged(self):
        chi = np.array([0.0, 1.0, 2.0, 200.0, 201.0])
        I = np.array([1.0, 1.0, 1.0, 2.0, 2.0])
        _, _, meta = handle_missing(chi, I, strategy="interp")
        assert meta["max_gap_deg"] > 15.0
        assert meta["unreliable"] is True


# ---------------------------------------------------------------------------
# Background subtraction / 背景扣除（非晶基底）
# ---------------------------------------------------------------------------

class TestBackground:
    def test_constant_exact_restoration(self):
        """f_meas = X·f_c for isotropic amorphous; subtracting the constant
        level must restore the crystalline f_c."""
        chi = np.arange(0.0, 360.0, 1.0)
        I_cryst = _gaussian_peak(chi, center=90.0, sigma=15.0, height=10.0, floor=0.0)
        # crystalline-only Hermans f (equatorial peak at χ=90 → highly oriented)
        r_c, _ = hermans_orientation(chi, I_cryst, equatorial_to_chain=True)
        # add a flat amorphous floor
        I_meas = I_cryst + 20.0
        r_meas_raw, _ = hermans_orientation(chi, I_meas, equatorial_to_chain=True)
        assert r_meas_raw["f"] < r_c["f"]  # contaminated f is biased low
        # subtract the constant floor exactly
        _, I_corr, bg, info = subtract_background(chi, I_meas, mode="constant", constant=20.0)
        assert abs(info["constant"] - 20.0) < 1e-9
        r_corr, _ = hermans_orientation(chi, I_corr, equatorial_to_chain=True)
        assert abs(r_corr["f"] - r_c["f"]) < 1e-3  # restored

    def test_auto_estimate(self):
        chi = np.arange(0.0, 360.0, 1.0)
        I = _gaussian_peak(chi, center=0.0, sigma=20.0, height=5.0, floor=3.0)
        _, I_corr, bg, info = subtract_background(chi, I, mode="constant", auto_estimate=True)
        # auto-estimated constant should be near the floor (low percentile of I)
        assert info["constant"] > 0
        assert np.min(I_corr) >= 0.0

    def test_reference_curve_subtraction(self):
        chi = np.arange(0.0, 360.0, 1.0)
        I_ref = _gaussian_peak(chi, center=45.0, sigma=30.0, height=2.0, floor=1.0)
        I_sample = _gaussian_peak(chi, center=90.0, sigma=15.0, height=8.0, floor=0.0)
        I_total = I_sample + 0.5 * I_ref
        _, I_corr, _, info = subtract_background(
            chi, I_total, mode="none",
            reference_curve=(chi, I_ref), reference_scale=0.5,
        )
        assert info["reference_scale"] == 0.5
        # residual should be close to the crystalline profile alone
        assert np.max(np.abs(I_corr - I_sample)) < 0.5


# ---------------------------------------------------------------------------
# Hermans orientation function / Hermans 取向函数
# ---------------------------------------------------------------------------

class TestHermans:
    def test_isotropic_limit(self, uniform_grid, isotropic_profile):
        """Isotropic I(χ) → <cos²χ>=1/3; with equatorial_to_chain=False, f=0."""
        r, _ = hermans_orientation(uniform_grid, isotropic_profile, equatorial_to_chain=False)
        assert abs(r["cos2_normal"] - 1.0 / 3.0) < 1e-2
        assert abs(r["f"]) < 2e-2

    def test_perfect_orientation_chain_parallel(self, uniform_grid):
        """Peak at χ=90° (equator) + equatorial_to_chain → chain ∥ reference, f→1."""
        I = _gaussian_peak(uniform_grid, center=90.0, sigma=5.0, height=10.0)
        I = np.maximum(I, 1e-6)
        r, _ = hermans_orientation(uniform_grid, I, equatorial_to_chain=True)
        assert r["f"] > 0.85

    def test_perfect_orientation_chain_perpendicular(self, uniform_grid):
        """Peak at χ=0° (meridian) + equatorial_to_chain → chain ⊥ reference, f→−0.5."""
        I = _gaussian_peak(uniform_grid, center=0.0, sigma=5.0, height=10.0)
        I = np.maximum(I, 1e-6)
        r, _ = hermans_orientation(uniform_grid, I, equatorial_to_chain=True)
        assert r["f"] < -0.35  # approaches −0.5

    def test_half_range_equals_full_range(self, uniform_grid):
        """For a four-quadrant-symmetric profile, [0,90] == full [0,360)."""
        # cos(2χ) is exactly four-quadrant symmetric (period 180, even).
        # cos(2χ) 严格四象限对称（周期 180，偶函数）。
        I = 1.0 + 0.5 * np.cos(2.0 * np.deg2rad(uniform_grid))
        r_full, _ = hermans_orientation(uniform_grid, I, equatorial_to_chain=False)
        mask = (uniform_grid >= 0) & (uniform_grid <= 90)
        r_half, _ = hermans_orientation(uniform_grid[mask], I[mask], equatorial_to_chain=False)
        assert abs(r_full["cos2_normal"] - r_half["cos2_normal"]) < 5e-2

    def test_reference_chi_deg_matches_chi_zero(self, uniform_grid):
        """reference_chi_deg must agree with the chi_zero shorthand presets."""
        # reference_chi_deg 必须与 chi_zero 快捷预设一致。
        I = _gaussian_peak(uniform_grid, center=90.0, sigma=15.0, height=5.0) + 1.0
        r_merid, _ = hermans_orientation(uniform_grid, I, chi_zero="meridian", equatorial_to_chain=False)
        r_ref0, _ = hermans_orientation(uniform_grid, I, reference_chi_deg=0.0, equatorial_to_chain=False)
        assert abs(r_merid["cos2_normal"] - r_ref0["cos2_normal"]) < 1e-9
        r_equat, _ = hermans_orientation(uniform_grid, I, chi_zero="equator", equatorial_to_chain=False)
        r_ref90, _ = hermans_orientation(uniform_grid, I, reference_chi_deg=90.0, equatorial_to_chain=False)
        assert abs(r_equat["cos2_normal"] - r_ref90["cos2_normal"]) < 1e-9

    def test_reference_chi_deg_rotation_invariance(self, uniform_grid):
        """A peak at χ=θ analyzed with reference=θ ≡ peak at χ=0 with reference=0."""
        # 峰在 χ=θ、reference=θ 等价于峰在 χ=0、reference=0。
        I_at30 = _gaussian_peak(uniform_grid, center=30.0, sigma=8.0, height=10.0)
        I_at30 = np.maximum(I_at30, 1e-6)
        r, _ = hermans_orientation(uniform_grid, I_at30, equatorial_to_chain=False, reference_chi_deg=30.0)
        # rotating the peak onto the reference axis → normal ∥ reference → high <cos²>
        # 把峰旋转到参考轴上 → 法向∥参考轴 → <cos²> 偏高
        assert r["cos2_normal"] > 0.8


# ---------------------------------------------------------------------------
# FWHM orientation index / FWHM 取向指数
# ---------------------------------------------------------------------------

class TestFWHM:
    def test_known_gaussian_fwhm(self):
        """Gaussian σ=10° → FWHM=2√(2ln2)·σ ≈ 23.53° → f≈0.869."""
        # Use a positive-angle window so the peak does not straddle the 0°/360° wrap.
        # 使用正角度窗口，避免峰跨 0°/360° 边界。
        chi = np.linspace(0.0, 120.0, 241)
        sigma = 10.0
        I = np.exp(-((chi - 60.0) ** 2) / (2 * sigma * sigma))
        r, _ = fwhm_orientation_index(chi, I)
        expected_fwhm = 2.0 * np.sqrt(2.0 * np.log(2.0)) * sigma
        assert abs(r["fwhm_deg"] - expected_fwhm) < 1.0
        expected_f = (180.0 - expected_fwhm) / 180.0
        assert abs(r["f"] - expected_f) < 1e-2

    def test_pi_pct_range(self):
        chi = np.linspace(0.0, 60.0, 121)
        I = np.exp(-((chi - 30.0) ** 2) / 50.0)
        r, _ = fwhm_orientation_index(chi, I)
        assert 0.0 <= r["pi_pct"] <= 100.0
        assert abs(r["pi_pct"] - r["f"] * 100.0) < 1e-6


# ---------------------------------------------------------------------------
# Wilchinsky method / Wilchinsky 方法
# ---------------------------------------------------------------------------

class TestWilchinsky:
    def test_orthogonal_degeneracy(self):
        """β=90° (cubic): reflections (100)/(010)/(001) directly give the axes."""
        cell = {"a": 1.0, "b": 1.0, "c": 1.0, "beta": 90.0}
        # measured <cos²χ> for (100),(010),(001) → exactly <cos²φ_a,b,c>
        reflections = [
            {"h": 1, "k": 0, "l": 0, "cos2": 0.2},
            {"h": 0, "k": 1, "l": 0, "cos2": 0.3},
            {"h": 0, "k": 0, "l": 1, "cos2": 0.5},
        ]
        r, _ = wilchinsky_chain_axis(reflections, cell)
        assert abs(r["cos2_axes"]["1"] - 0.2) < 1e-6
        assert abs(r["cos2_axes"]["2"] - 0.3) < 1e-6
        assert abs(r["cos2_axes"]["3"] - 0.5) < 1e-6
        # β=90°: <cos²φ_c> = cos²90·x1 + sin²90·x3 = x3 = 0.5
        assert abs(r["cos2_phi_c"] - 0.5) < 1e-6
        assert abs(r["f"] - (3 * 0.5 - 1) / 2) < 1e-6

    def test_monoclinic_forward_inverse(self):
        """Forward (x → measured <cos²χ>) then inverse must recover x (α-iPP cell)."""
        cell = {"a": 6.65, "b": 20.96, "c": 6.5, "beta": 99.62}
        # choose a closed set of axis second moments
        x_true = np.array([0.20, 0.30, 0.50])
        # several equatorial/general reflections
        hkls = [(1, 1, 0), (0, 4, 0), (1, 3, 0), (1, 0, 1)]
        from python.services.orientation_analysis import _monoclinic_direction_cosines
        reflections = []
        for h, k, l in hkls:
            u1, u2, u3 = _monoclinic_direction_cosines(h, k, l, cell["a"], cell["b"], cell["c"], cell["beta"])
            cos2 = (u1 * u1) * x_true[0] + (u2 * u2) * x_true[1] + (u3 * u3) * x_true[2]
            reflections.append({"h": h, "k": k, "l": l, "cos2": cos2})
        r, _ = wilchinsky_chain_axis(reflections, cell)
        assert abs(r["cos2_axes"]["1"] - x_true[0]) < 1e-4
        assert abs(r["cos2_axes"]["2"] - x_true[1]) < 1e-4
        assert abs(r["cos2_axes"]["3"] - x_true[2]) < 1e-4
        # residual should be ~0 for a consistent synthetic system
        assert r["residual"] < 1e-4

    def test_monoclinic_chain_axis_formula(self):
        """For β≠90°, <cos²φ_c> = cos²β·x1 + sin²β·x3 (verified against direct calc)."""
        cell = {"a": 5.0, "b": 6.0, "c": 7.0, "beta": 100.0}
        x = np.array([0.25, 0.35, 0.40])
        from python.services.orientation_analysis import _monoclinic_direction_cosines
        reflections = []
        for h, k, l in [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1)]:
            u1, u2, u3 = _monoclinic_direction_cosines(h, k, l, cell["a"], cell["b"], cell["c"], cell["beta"])
            cos2 = (u1 * u1) * x[0] + (u2 * u2) * x[1] + (u3 * u3) * x[2]
            reflections.append({"h": h, "k": k, "l": l, "cos2": cos2})
        r, _ = wilchinsky_chain_axis(reflections, cell)
        beta = np.deg2rad(cell["beta"])
        expected_cos2_c = (np.cos(beta) ** 2) * x[0] + (np.sin(beta) ** 2) * x[2]
        assert abs(r["cos2_phi_c"] - expected_cos2_c) < 1e-4


# ---------------------------------------------------------------------------
# End-to-end pipeline / 端到端流水线
# ---------------------------------------------------------------------------

class TestPipeline:
    def test_analyze_full_pipeline(self, uniform_grid):
        I = (_gaussian_peak(uniform_grid, center=90.0, sigma=12.0, height=10.0)
             + _gaussian_peak(uniform_grid, center=270.0, sigma=12.0, height=10.0)
             + 3.0)  # isotropic amorphous floor
        out = analyze_orientation(
            uniform_grid, I,
            methods=["hermans", "fwhm"],
            geometry="transmission", symmetry="auto",
            background={"mode": "constant", "auto_estimate": True},
            hermans={"chi_zero": "meridian", "equatorial_to_chain": True},
        )
        methods_run = [r["method"] for r in out["results"]]
        assert "hermans" in methods_run and "fwhm" in methods_run
        # equatorial peak (χ=90) + equatorial_to_chain → well-oriented chain
        f_hermans = next(r["f"] for r in out["results"] if r["method"] == "hermans")
        assert f_hermans > 0.5
        # background was subtracted (non-zero background curve)
        assert np.max(out["background"]) > 0
        # amorphous-bias caveat is present
        assert any("amorphous" in w.lower() for w in out["warnings"])

    def test_crystallinity_hint(self, uniform_grid):
        I = _gaussian_peak(uniform_grid, center=90.0, sigma=15.0, height=5.0) + 2.0
        out = analyze_orientation(
            uniform_grid, I, methods=["hermans"],
            background={"mode": "constant"}, crystallinity=50.0,
        )
        assert out["crystallinity_hint"] is not None
        assert abs(out["crystallinity_hint"]["xc_percent"] - 50.0) < 1e-9

    def test_wilchinsky_in_pipeline(self):
        cell = {"a": 1.0, "b": 1.0, "c": 1.0, "beta": 90.0}
        reflections = [
            {"h": 1, "k": 0, "l": 0, "cos2": 0.2},
            {"h": 0, "k": 1, "l": 0, "cos2": 0.3},
            {"h": 0, "k": 0, "l": 1, "cos2": 0.5},
        ]
        chi = np.arange(0.0, 360.0, 1.0)
        I = np.ones_like(chi)
        out = analyze_orientation(
            chi, I, methods=["wilchinsky"],
            wilchinsky={"cell": cell, "reflections": reflections},
        )
        w = next(r for r in out["results"] if r["method"] == "wilchinsky")
        assert abs(w["cos2_phi_c"] - 0.5) < 1e-6


# ---------------------------------------------------------------------------
# Validation / 输入校验
# ---------------------------------------------------------------------------

class TestValidation:
    def test_mismatched_lengths(self):
        with pytest.raises(ValueError, match="equal length"):
            hermans_orientation([0, 90, 180], [1, 2])

    def test_too_few_points(self):
        with pytest.raises(ValueError, match="at least 2"):
            hermans_orientation([0], [1])

    def test_bad_symmetry(self):
        with pytest.raises(ValueError, match="symmetry must be"):
            fold_symmetry([0, 90, 180], [1, 2, 3], symmetry="bogus")

    def test_bad_method(self):
        with pytest.raises(ValueError, match="methods must be"):
            analyze_orientation([0, 90, 180, 270], [1, 2, 3, 4], methods=["nope"])

    def test_wilchinsky_bad_cell(self):
        with pytest.raises(ValueError, match="cell parameters invalid"):
            wilchinsky_chain_axis(
                [{"h": 1, "k": 0, "l": 0, "cos2": 0.5}],
                {"a": -1, "b": 1, "c": 1, "beta": 90.0},
            )

    def test_zero_reciprocal_vector(self):
        with pytest.raises(ValueError, match="zero norm"):
            wilchinsky_chain_axis(
                [{"h": 0, "k": 0, "l": 0, "cos2": 0.5}],
                {"a": 1, "b": 1, "c": 1, "beta": 90.0},
            )
