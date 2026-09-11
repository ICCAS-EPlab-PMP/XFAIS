#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_line_profile.py — Tests for the line-profile core sampler
test_line_profile.py — 沿线剖面核心采样器测试

Covers _sample_line_profile (pure NumPy/SciPy core used by the
viewer_config 'line_profile' action). pyFAI itself has no native
"integrate along an arbitrary line segment" capability, so we sample the
2D array directly and optionally project q/2θ/χ onto the same grid.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

# service_launcher.py uses `from services.xxx import ...` (it runs with the
# python/ directory on sys.path), so we import the core sampler directly rather
# than via the `python.service_launcher` package path.
# service_launcher.py 内部用 `from services.xxx import ...`（运行时 python/
# 目录在 sys.path 上），因此直接导入核心采样器，而非走 python.service_launcher 包路径。
from service_launcher import _sample_line_profile


# ── 1. Geometry: distance axis & sample count ───────────────────────────

def test_horizontal_line_distance_axis():
    """A 10-px horizontal line yields distance 0..9 and 10 samples."""
    data = np.zeros((20, 20), dtype=np.float32)
    res = _sample_line_profile(data, 5, 0, 5, 9, width=1)
    assert res["n_samples"] == 10
    assert math.isclose(res["length_px"], 9.0)
    assert math.isclose(res["distance_px"][0], 0.0)
    assert math.isclose(res["distance_px"][-1], 9.0)
    assert len(res["intensity"]) == 10


def test_diagonal_line_length():
    """A diagonal (0,0)->(3,4) has length 5 and 6 samples (one per pixel)."""
    data = np.zeros((10, 10), dtype=np.float32)
    res = _sample_line_profile(data, 0, 0, 3, 4, width=1)
    assert math.isclose(res["length_px"], 5.0)
    # Default sampler yields ceil(L)+1 = 6 samples (one per pixel center).
    assert res["n_samples"] == 6


def test_explicit_n_samples_overrides_default():
    """User-supplied n_samples is respected when >= 2."""
    data = np.zeros((20, 20), dtype=np.float32)
    res = _sample_line_profile(data, 0, 0, 0, 9, width=1, n_samples=50)
    assert res["n_samples"] == 50


def test_degenerate_single_point():
    """Coincident endpoints collapse to a single sample."""
    data = np.full((10, 10), 7.0, dtype=np.float32)
    res = _sample_line_profile(data, 5, 5, 5, 5, width=1)
    assert res["n_samples"] == 1
    assert math.isclose(float(res["intensity"][0]), 7.0)


# ── 2. Intensity correctness ────────────────────────────────────────────

def test_constant_image_returns_constant_profile():
    """On a constant image the profile is flat at that value."""
    data = np.full((30, 30), 3.5, dtype=np.float32)
    res = _sample_line_profile(data, 0, 0, 29, 29, width=1)
    assert np.allclose(res["intensity"], 3.5)


def test_horizontal_gradient_linear():
    """On a column-ramp image, a horizontal line yields a linear ramp."""
    cols = np.arange(20, dtype=np.float32)
    data = np.tile(cols, (20, 1))  # data[r, c] = c
    res = _sample_line_profile(data, 10, 0, 10, 19, width=1)
    # Endpoints should hit exact pixel values; interior is interpolated.
    assert math.isclose(float(res["intensity"][0]), 0.0, abs_tol=1e-5)
    assert math.isclose(float(res["intensity"][-1]), 19.0, abs_tol=1e-5)
    # Monotonic non-decreasing along the ramp.
    diffs = np.diff(res["intensity"])
    assert np.all(diffs >= -1e-6)


def test_endpoints_match_pixel_values():
    """With default n_samples = length, endpoints land on exact pixels."""
    data = np.arange(100, dtype=np.float32).reshape(10, 10)
    # Vertical line down column 3: data[i, 3] = 10*i + 3
    res = _sample_line_profile(data, 0, 3, 9, 3, width=1)
    assert math.isclose(float(res["intensity"][0]), 3.0, abs_tol=1e-5)
    assert math.isclose(float(res["intensity"][-1]), 93.0, abs_tol=1e-5)


# ── 3. Width band & aggregation ─────────────────────────────────────────

def test_width_band_mean():
    """A width>1 band averages rows perpendicular to the line."""
    # Column index + row index, so cross-line values vary.
    rows = np.arange(5, dtype=np.float32)[:, None]
    cols = np.arange(5, dtype=np.float32)[None, :]
    data = (rows + cols).astype(np.float32)  # data[r,c] = r + c
    # Horizontal line along row 2, columns 0..4, width=3 → rows 1,2,3.
    # Mean over rows 1,2,3 at column c = (1+2+3)/3 + c = 2 + c
    res = _sample_line_profile(data, 2, 0, 2, 4, width=3, aggregate="mean")
    expected = 2.0 + np.arange(5)
    assert np.allclose(res["intensity"], expected, atol=1e-5)


def test_aggregate_sum():
    """aggregate='sum' totals the band instead of averaging."""
    data = np.full((10, 10), 2.0, dtype=np.float32)
    res = _sample_line_profile(data, 5, 0, 5, 9, width=4, aggregate="sum")
    # 4 rows × value 2 → sum = 8 at every sample
    assert np.allclose(res["intensity"], 8.0)


def test_width_centering_symmetric():
    """Odd width centers the band on the line; endpoints stay symmetric."""
    # Row-only image: data[r, c] = r, shape (7, 7).
    # 仅依赖行的图像：data[r, c] = r，形状 (7, 7)。
    data = np.tile(np.arange(7, dtype=np.float32)[:, None], (1, 7))
    # Horizontal line along row 3, width=3 → rows 2,3,4; mean = 3
    res = _sample_line_profile(data, 3, 0, 3, 6, width=3, aggregate="mean")
    assert np.allclose(res["intensity"], 3.0, atol=1e-5)


# ── 4. Boundary clamping ────────────────────────────────────────────────

def test_out_of_bounds_clamps_via_nearest():
    """Endpoints slightly outside the frame are clamped, not NaN."""
    data = np.full((10, 10), 5.0, dtype=np.float32)
    # (-2, -2) -> (12, 12): endpoints clamp to (0,0) and (9,9).
    res = _sample_line_profile(data, -2, -2, 12, 12, width=1)
    assert not np.any(np.isnan(res["intensity"]))
    assert np.allclose(res["intensity"], 5.0)


def test_clamp_preserves_endpoint_values():
    """When an endpoint is out of bounds, it snaps to the edge pixel."""
    data = np.arange(100, dtype=np.float32).reshape(10, 10)
    # Overshoot row -5 → clamps to row 0. Line (0,3)→(5,3): data[r,3] = 10*r+3.
    # 起点 row=-5 被钳制到 row 0。线 (0,3)→(5,3)：data[r,3] = 10*r+3。
    res = _sample_line_profile(data, -5, 3, 5, 3, width=1)
    assert math.isclose(float(res["intensity"][0]), 3.0, abs_tol=1e-5)
    assert math.isclose(float(res["intensity"][-1]), 53.0, abs_tol=1e-5)


# ── 5. Grid exposure (for physics-map projection by caller) ─────────────

def test_grid_shapes_for_width_one():
    """width=1 grids have shape (1, n_samples)."""
    data = np.zeros((20, 20), dtype=np.float32)
    res = _sample_line_profile(data, 0, 0, 0, 9, width=1)
    assert res["grid_rows"].shape == (1, 10)
    assert res["grid_cols"].shape == (1, 10)


def test_grid_shapes_for_band():
    """Band grids have shape (width, n_samples)."""
    data = np.zeros((20, 20), dtype=np.float32)
    res = _sample_line_profile(data, 10, 0, 10, 9, width=5)
    assert res["grid_rows"].shape == (5, 10)
    assert res["grid_cols"].shape == (5, 10)


# ── 6. Return-contract sanity ───────────────────────────────────────────

def test_return_keys_present():
    """All documented keys are present in the result dict."""
    data = np.zeros((10, 10), dtype=np.float32)
    res = _sample_line_profile(data, 0, 0, 0, 5)
    for key in ("distance_px", "intensity", "grid_rows", "grid_cols",
                "length_px", "n_samples", "width", "aggregate"):
        assert key in res, f"missing key: {key}"
    assert res["aggregate"] == "mean"
    assert res["width"] == 1


@pytest.mark.parametrize("w", [1, 2, 3, 5])
def test_widths_run_without_error(w):
    """Various widths execute cleanly on a small image."""
    data = np.random.rand(15, 15).astype(np.float32)
    res = _sample_line_profile(data, 2, 3, 12, 8, width=w)
    assert len(res["intensity"]) == res["n_samples"]
