#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_curve_fitting.py — Tests for the 1-D diffraction curve-fitting service.

Synthetic-data tests (all parameters known exactly, noise seeded):
  - Region cropping and point counts.
  - Smoothing methods run and preserve peak height (Savitzky–Golay).
  - Background estimators: SNIP under a peak+pedestal, iterative polynomial
    under overlapping peaks.
  - Peak-shape math: pseudo-Voigt FWHM exactness, Pearson VII area formula
    (m=1 → Lorentzian area), lognormal FWHM↔w round-trip, Voigt FWHM
    consistency via Olivero–Longbothum.
  - Auto peak detection counts and initial estimates.
  - Full fit recovery: single Gaussian on a linear background, overlapping
    peaks, locked parameters stay fixed, statistics sanity (DOF / R²).
"""

import math

import numpy as np
import pytest

from python.services.curve_fitting import (
    auto_detect_peaks,
    evaluate_model,
    fit_curve,
    peak_profile,
    preview_pipeline,
    smooth_curve,
    _lognormal_fwhm,
    _lognormal_w_from_fwhm,
    _peak_area_scaled,
)

rng = np.random.default_rng(42)


def _gaussian_sum(x, peaks, background_fn=None):
    y = background_fn(x) if background_fn is not None else np.zeros_like(x)
    for c, h, f in peaks:
        sigma = f / 2.3548200450309493
        y = y + h * np.exp(-0.5 * ((x - c) / sigma) ** 2)
    return y


# ── Region & preview / 选区与预览 ────────────────────────────────────────────

def test_preview_region_crop_and_stages():
    x = np.linspace(0.0, 2.0, 400)
    y = 5.0 + 2.0 * x + _gaussian_sum(x, [(0.6, 50.0, 0.1)])
    y = y + rng.normal(0.0, 0.2, x.size)
    result = preview_pipeline(
        x, y,
        region={"min": 0.2, "max": 1.4},
        smoothing={"method": "savgol", "window": 11, "poly_order": 3},
        background={"method": "iterative", "order": 1, "iterations": 40},
    )
    xs = np.asarray(result["x"])
    assert result["quality"]["n_points"] == xs.size
    assert xs.min() >= 0.2 - 1e-12 and xs.max() <= 1.4 + 1e-12
    assert result["smoothed_y"] is not None
    assert result["background_y"] is not None
    assert len(result["processed_y"]) == xs.size
    # Iterative background under a peak should stay near the true linear bg.
    bg = np.asarray(result["background_y"])
    true_bg = 5.0 + 2.0 * xs
    assert np.max(np.abs(bg - true_bg)) < 3.0  # pedestal ~50 → few % accuracy


def test_preview_detect_peaks():
    x = np.linspace(0.1, 3.0, 900)
    y = _gaussian_sum(x, [(0.8, 40.0, 0.08), (1.6, 25.0, 0.12), (2.4, 8.0, 0.1)])
    result = preview_pipeline(
        x, y,
        smoothing={"method": "none"},
        background={"method": "none"},
        detect={"enabled": True, "prominence": 0.05},
    )
    found = result["auto_peaks"]
    assert len(found) == 3
    centers = sorted(p["center"] for p in found)
    assert centers[0] == pytest.approx(0.8, abs=0.03)
    assert centers[1] == pytest.approx(1.6, abs=0.03)
    assert centers[2] == pytest.approx(2.4, abs=0.03)
    by_c = {round(p["center"], 1): p for p in found}
    assert by_c[1.6]["fwhm"] == pytest.approx(0.12, rel=0.35)


# ── Smoothing / 平滑 ────────────────────────────────────────────────────────

def test_savgol_preserves_peak_height():
    x = np.linspace(0.0, 1.0, 501)
    y = 100.0 * np.exp(-0.5 * ((x - 0.5) / 0.05) ** 2)
    ys, info = smooth_curve(y, "savgol", 11, 3)
    assert info["method"] == "savgol" and info["window"] == 11
    assert ys.max() == pytest.approx(100.0, rel=5e-3)


def test_smoothing_window_snapped_to_odd():
    y = rng.normal(0.0, 1.0, 200)
    _, info = smooth_curve(y, "savgol", 10, 2)
    assert info["window"] % 2 == 1
    _, info2 = smooth_curve(y, "median", 4, 0)
    assert info2["window"] % 2 == 1


# ── Shape math / 峰形数学 ───────────────────────────────────────────────────

def test_pseudo_voigt_fwhm_exact():
    x = np.array([0.0])
    for eta in (0.0, 0.3, 0.7, 1.0):
        half = peak_profile(np.array([0.5]), "pseudo_voigt", 0.0, 10.0, 1.0, eta)[0]
        assert half == pytest.approx(5.0, rel=1e-12), f"eta={eta}"


def test_pearson7_area_matches_lorentzian_at_m1():
    fwhm, height = 0.4, 12.0
    lor = _peak_area_scaled("lorentzian", height, fwhm, None)
    p7 = _peak_area_scaled("pearson7", height, fwhm, 1.0)
    assert p7 == pytest.approx(lor, rel=1e-6)


def test_lognormal_fwhm_roundtrip():
    for w in (0.1, 0.3, 0.8):
        c, f = 1.7, _lognormal_fwhm(1.7, w)
        assert _lognormal_w_from_fwhm(c, f) == pytest.approx(w, rel=1e-8, abs=1e-10)
        assert _lognormal_fwhm(c, w) == pytest.approx(f, rel=1e-12)


def test_voigt_profile_height_and_fwhm():
    for kappa in (0.1, 0.5, 0.9):
        w = 0.2
        center = peak_profile(np.zeros(1), "voigt", 0.0, 7.0, w, kappa)[0]
        assert center == pytest.approx(7.0, rel=1e-9)
        # Half-maximum width == w (Olivero–Longbothum inversion).
        grid = np.linspace(-w * 2, w * 2, 20001)
        prof = peak_profile(grid, "voigt", 0.0, 7.0, w, kappa)
        above = grid[prof >= 3.5]
        fwhm = above[-1] - above[0]
        assert fwhm == pytest.approx(w, rel=2e-3), f"kappa={kappa}"


def test_gaussian_area_formula():
    h, f = 5.0, 0.3
    sigma = f / 2.3548200450309493
    assert _peak_area_scaled("gaussian", h, f, None) == pytest.approx(
        h * sigma * math.sqrt(2 * math.pi), rel=1e-12
    )


# ── Evaluate / 模型求值 ─────────────────────────────────────────────────────

def test_evaluate_model_sum_of_components():
    x = np.linspace(0.0, 2.0, 300)
    y = 10.0 + x  # placeholder data; evaluation only needs the grid
    result = evaluate_model(
        x, y,
        smoothing={"method": "none"},
        background={"method": "none"},
        peaks=[
            {"type": "gaussian", "center": 0.8, "height": 20.0, "fwhm": 0.15},
            {"type": "lorentzian", "center": 1.4, "height": 8.0, "fwhm": 0.2},
        ],
    )
    xs = np.asarray(result["x"])
    total = np.asarray(result["curves"]["sum"])
    parts = np.asarray(result["curves"]["peaks"])
    assert parts.shape[0] == 2
    assert total == pytest.approx(parts.sum(axis=0), rel=1e-9, abs=1e-9)
    assert peak_profile(np.array([0.8]), "gaussian", 0.8, 20.0, 0.15)[0] == pytest.approx(20.0)
    # 0.8 is not exactly on the 300-point grid → loose interpolation tolerance.
    assert np.interp(0.8, xs, parts[0]) == pytest.approx(20.0, abs=0.05)


# ── Background region (PeakFit baseline section, 2026-10-13) / 背景选区 ──────

def test_background_region_excludes_peaks_from_fit():
    """Polynomial background estimated inside the window only: a big peak
    OUTSIDE the window must not pull the baseline up (the PeakFit baseline-
    section semantics), while the baseline curve still covers the full range
    by extrapolation. / 多项式背景只在窗口内估计：窗口外的大峰不得拉高基线
    （PeakFit 基线区段语义）；背景曲线仍经外推覆盖全区。"""
    x = np.linspace(0.0, 2.0, 400)
    peak = _gaussian_sum(x, [(1.5, 500.0, 0.1)])  # big peak at 1.5
    y = 5.0 + 2.0 * x + peak  # true baseline = 5 + 2x
    result = preview_pipeline(
        x, y,
        smoothing={"method": "none"},
        background={"method": "polynomial", "order": 1,
                    "region": {"min": 0.1, "max": 0.8}},  # peak-free window
    )
    bg = np.asarray(result["background_y"])
    xs = np.asarray(result["x"])
    true_bg = 5.0 + 2.0 * xs
    # Baseline follows the true line closely EVERYWHERE (window fit +
    # extrapolation), including under the peak at 1.5.
    # 基线在全区（含 1.5 处峰下方）都贴近真值直线。
    assert np.max(np.abs(bg - true_bg)) < 3.0
    assert result["background_info"]["window"] == [pytest.approx(0.1, abs=1e-9), pytest.approx(0.8, abs=1e-9)]
    # Without the region the same polynomial IS pulled up by the peak.
    # 不设选区时，同一阶多项式会被峰拉高。"""
    ref = preview_pipeline(x, y, smoothing={"method": "none"},
                           background={"method": "polynomial", "order": 1})
    bg_ref = np.asarray(ref["background_y"])
    assert np.max(np.abs(bg_ref - true_bg)) > 3.0


def test_background_region_iterative_and_snip_extension():
    """SNIP inside a window extends its edge values outside (flat wings);
    iterative polynomial uses window points and extrapolates smoothly. Both
    keep full-length curves. / SNIP 窗口外用边缘值延伸（平翼）；迭代多项式
    窗口内拟合并外推；两者曲线都保持全区长度。"""
    x = np.linspace(0.0, 3.0, 600)
    y = 10.0 + _gaussian_sum(x, [(2.2, 60.0, 0.1)])
    result = preview_pipeline(
        x, y,
        smoothing={"method": "none"},
        background={"method": "snip", "iterations": 24,
                    "region": {"min": 0.2, "max": 1.2}},
    )
    bg = np.asarray(result["background_y"])
    xs = np.asarray(result["x"])
    assert bg.size == xs.size
    left = xs < 0.2
    right = xs > 1.2
    # Constant wings. / 两翼为常数。
    assert np.allclose(bg[left], bg[left][0])
    assert np.allclose(bg[right], bg[right][0])
    assert bg.mean() == pytest.approx(10.0, abs=2.0)

    result2 = preview_pipeline(
        x, y,
        smoothing={"method": "none"},
        background={"method": "iterative", "order": 0, "iterations": 40,
                    "region": {"min": 0.2, "max": 1.2}},
    )
    bg2 = np.asarray(result2["background_y"])
    assert bg2.size == xs.size
    assert bg2.mean() == pytest.approx(10.0, abs=2.0)


def test_background_region_too_narrow_falls_back_with_warning():
    x = np.linspace(0.0, 1.0, 200)
    y = 5.0 + _gaussian_sum(x, [(0.5, 50.0, 0.08)])
    result = preview_pipeline(
        x, y,
        smoothing={"method": "none"},
        background={"method": "polynomial", "order": 1,
                    "region": {"min": 0.500, "max": 0.505}},  # ~1 point inside
    )
    assert any("too few" in w or "过少" in w for w in result["warnings"])
    assert result["background_info"].get("window") is None
    assert result["background_y"] is not None


def test_fit_curve_honours_background_region():
    """End-to-end: with the peak excluded from the background window, the fit
    recovers the peak height on a linear baseline. / 端到端：峰落在背景窗口
    之外时，拟合在线性基线上正确回收峰高。"""
    x = np.linspace(0.0, 2.0, 500)
    y = 4.0 + 3.0 * x + _gaussian_sum(x, [(1.2, 120.0, 0.1)]) + rng.normal(0, 0.4, x.size)
    result = fit_curve(
        x, y,
        region={"min": 0.1, "max": 1.9},
        smoothing={"method": "savgol", "window": 9, "poly_order": 3},
        background={"method": "polynomial", "order": 1, "refine": True,
                    "region": {"min": 0.15, "max": 0.75}},
        peaks=[{"type": "gaussian", "center": 1.2, "height": 110.0, "fwhm": 0.11}],
    )
    p = result["fit"]["peaks"][0]["params"]
    assert p["height"] == pytest.approx(120.0, rel=0.05)
    assert result["fit"]["stats"]["r2"] > 0.99


def test_background_multiple_sections_union_fit():
    """PeakFit semantics: MULTIPLE peak-free bands feed ONE baseline fit
    (union of active points, single model) — peaks between bands must not
    pull the baseline. / PeakFit 语义：多条无峰点带并入同一次基线拟合；点带
    之间的峰不得拉高基线。"""
    x = np.linspace(0.0, 3.0, 600)
    y = 6.0 - 1.0 * x + _gaussian_sum(x, [(1.0, 80.0, 0.1), (2.0, 60.0, 0.1)])
    result = preview_pipeline(
        x, y,
        smoothing={"method": "none"},
        background={"method": "polynomial", "order": 1, "regions": [
            {"min": 0.1, "max": 0.6},
            {"min": 1.4, "max": 1.7},
            {"min": 2.4, "max": 2.9},
        ]},
    )
    bg = np.asarray(result["background_y"])
    xs = np.asarray(result["x"])
    true_bg = 6.0 - 1.0 * xs
    # One fit across all three bands tracks the true tilted baseline over the
    # whole range, including between the bands (under the peaks).
    # 三段点带一次拟合：全区（含点带之间的峰下方）都贴合真实斜基线。
    assert np.max(np.abs(bg - true_bg)) < 2.5
    info = result["background_info"]
    assert isinstance(info.get("windows"), list) and len(info["windows"]) == 3
    # Legacy single-region field still honoured (compat). 兼容：单 region 仍生效。
    single = preview_pipeline(
        x, y, smoothing={"method": "none"},
        background={"method": "polynomial", "order": 1, "region": {"min": 0.1, "max": 0.6}},
    )
    assert np.max(np.abs(np.asarray(single["background_y"]) - true_bg)) < 2.5


def test_background_sections_invalid_dropped_with_warning():
    x = np.linspace(0.0, 1.0, 200)
    y = 5.0 + _gaussian_sum(x, [(0.5, 50.0, 0.08)])
    result = preview_pipeline(
        x, y,
        smoothing={"method": "none"},
        background={"method": "polynomial", "order": 1, "regions": [
            {"min": 0.500, "max": 0.503},  # too few points → dropped
            {"min": 0.05, "max": 0.25},    # valid
        ]},
    )
    assert any("过少" in w or "too few" in w for w in result["warnings"])
    assert isinstance(result["background_info"].get("windows"), list)
    assert len(result["background_info"]["windows"]) == 1



# ── Full fit recovery / 拟合回收 ────────────────────────────────────────────

def test_fit_single_gaussian_on_linear_background():
    x = np.linspace(0.0, 2.0, 500)
    y = 3.0 + 4.0 * x + _gaussian_sum(x, [(1.0, 100.0, 0.12)])
    y = y + rng.normal(0.0, 0.5, x.size)
    result = fit_curve(
        x, y,
        smoothing={"method": "savgol", "window": 11, "poly_order": 3},
        background={"method": "iterative", "order": 1, "iterations": 60, "refine": True},
        peaks=[
            {"type": "gaussian", "center": 1.02, "height": 90.0, "fwhm": 0.14,
             "locks": {"center": False, "height": False, "fwhm": False, "shape": False}},
        ],
        options={"max_iterations": 500, "loss": "linear"},
    )
    fit = result["fit"]
    assert fit["success"]
    p = fit["peaks"][0]["params"]
    assert p["center"] == pytest.approx(1.0, abs=2e-3)
    assert p["height"] == pytest.approx(100.0, rel=0.02)
    assert p["fwhm"] == pytest.approx(0.12, rel=0.03)
    stats = fit["stats"]
    assert stats["r2"] > 0.995
    # DOF = n_points − free params (3 gaussian params + 2 background coeffs).
    assert stats["dof"] == result["quality"]["n_points"] - 5
    assert fit["peaks"][0]["area"] == pytest.approx(
        100.0 * 0.12 * math.sqrt(math.pi / (4 * math.log(2))), rel=0.03
    )
    # Errors present and positive.
    errs = fit["peaks"][0]["errors"]
    assert errs["center"] is not None and errs["center"] > 0
    assert fit["peaks"][0]["area_error"] is not None


def test_fit_overlapping_pseudo_voigt_peaks():
    x = np.linspace(0.2, 2.2, 800)

    def pv(xv, c, h, f, eta):
        sigma = f / 2.3548200450309493
        return h * (eta / (1 + ((xv - c) / (f / 2)) ** 2)
                    + (1 - eta) * np.exp(-0.5 * ((xv - c) / sigma) ** 2))

    y = 8.0 + pv(x, 0.9, 60.0, 0.10, 0.4) + pv(x, 1.15, 35.0, 0.14, 0.6)
    y = y + rng.normal(0.0, 0.3, x.size)
    result = fit_curve(
        x, y,
        smoothing={"method": "savgol", "window": 9, "poly_order": 3},
        background={"method": "polynomial", "order": 0, "refine": True},
        peaks=[
            {"type": "pseudo_voigt", "center": 0.88, "height": 55.0, "fwhm": 0.11, "shape": 0.5,
             "locks": {"center": False, "height": False, "fwhm": False, "shape": False}},
            {"type": "pseudo_voigt", "center": 1.18, "height": 32.0, "fwhm": 0.13, "shape": 0.5,
             "locks": {"center": False, "height": False, "fwhm": False, "shape": False}},
        ],
    )
    fit = result["fit"]
    assert fit["stats"]["r2"] > 0.99
    peaks = sorted(fit["peaks"], key=lambda p: p["params"]["center"])
    assert peaks[0]["params"]["center"] == pytest.approx(0.9, abs=5e-3)
    assert peaks[1]["params"]["center"] == pytest.approx(1.15, abs=5e-3)
    assert peaks[0]["params"]["shape"] == pytest.approx(0.4, abs=0.08)
    assert peaks[1]["params"]["shape"] == pytest.approx(0.6, abs=0.08)
    # Area fractions sum to 1.
    fracs = [p["area_fraction"] for p in fit["peaks"]]
    assert sum(fracs) == pytest.approx(1.0, rel=1e-9)


def test_fit_locked_center_stays_fixed():
    x = np.linspace(0.0, 2.0, 400)
    y = 2.0 + _gaussian_sum(x, [(1.0, 50.0, 0.1)])
    result = fit_curve(
        x, y,
        smoothing={"method": "none"},
        background={"method": "polynomial", "order": 0, "refine": True},
        peaks=[
            {"type": "gaussian", "center": 0.93, "height": 40.0, "fwhm": 0.12,
             "locks": {"center": True, "height": False, "fwhm": False, "shape": False}},
        ],
    )
    assert result["fit"]["peaks"][0]["params"]["center"] == pytest.approx(0.93, abs=1e-12)
    # Center excluded from the free vector.
    assert result["fit"]["n_free_params"] == 3  # height + fwhm + bg c0


def test_fit_region_limits_target():
    x = np.linspace(0.0, 3.0, 600)
    y = 5.0 + _gaussian_sum(x, [(0.5, 80.0, 0.1), (2.5, 80.0, 0.1)])
    result = fit_curve(
        x, y,
        region={"min": 0.2, "max": 1.2},
        smoothing={"method": "none"},
        background={"method": "none"},
        peaks=[{"type": "gaussian", "center": 0.52, "height": 70.0, "fwhm": 0.12}],
    )
    xs = np.asarray(result["x"])
    assert xs.max() <= 1.2 + 1e-12
    assert result["fit"]["peaks"][0]["params"]["center"] == pytest.approx(0.5, abs=5e-3)
    assert result["fit"]["stats"]["dof"] == xs.size - 3


def test_fit_snip_background_subtracted_target():
    x = np.linspace(0.5, 4.0, 700)
    y = 12.0 + _gaussian_sum(x, [(1.5, 40.0, 0.12)])
    result = fit_curve(
        x, y,
        smoothing={"method": "none"},
        background={"method": "snip", "iterations": 24},
        peaks=[{"type": "gaussian", "center": 1.5, "height": 36.0, "fwhm": 0.13}],
    )
    bg = np.asarray(result["background_y"])
    assert bg.mean() == pytest.approx(12.0, abs=2.0)
    p = result["fit"]["peaks"][0]["params"]
    assert p["height"] == pytest.approx(40.0, rel=0.05)
    assert result["fit"]["stats"]["r2"] > 0.98


def test_fit_requires_peaks_and_points():
    x = np.linspace(0.0, 1.0, 50)
    y = np.ones_like(x)
    with pytest.raises(ValueError):
        fit_curve(x, y, smoothing={"method": "none"}, background={"method": "none"}, peaks=[])
    with pytest.raises(ValueError):
        fit_curve(
            x, y,
            region={"min": 0.4, "max": 0.42},  # leaves 2 points
            smoothing={"method": "none"},
            background={"method": "none"},
            peaks=[{"type": "gaussian", "center": 0.5, "height": 1.0, "fwhm": 0.05}],
        )


def test_lognormal_requires_positive_center():
    x = np.linspace(-1.0, 1.0, 100)
    y = np.abs(rng.normal(1.0, 0.1, x.size))
    with pytest.raises(ValueError):
        fit_curve(
            x, y,
            smoothing={"method": "none"},
            background={"method": "none"},
            peaks=[{"type": "lognormal", "center": -0.5, "height": 1.0, "fwhm": 0.2}],
        )


def test_auto_detect_direct_call():
    xs = np.linspace(0.0, 1.0, 500)
    ys = _gaussian_sum(xs, [(0.3, 10.0, 0.05), (0.7, 6.0, 0.05)])
    peaks = auto_detect_peaks(xs, ys, 0.05)
    assert len(peaks) == 2
    assert peaks[0]["type"] == "pseudo_voigt"
