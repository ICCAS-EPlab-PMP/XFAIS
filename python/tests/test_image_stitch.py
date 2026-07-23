#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_image_stitch.py — Unit tests for the image stitching service.

Covers: no-overlap placement, overlap strategies (mean/sum/max/first),
different pixel sizes, negative offsets (origin normalization), Y offsets,
HDF5 dead-pixel sentinel handling, NaN background in gaps, multi-image
triple overlap, and input validation errors.
"""

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure python/ is importable / 确保 python/ 在导入路径上
_BETA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BETA_ROOT) not in sys.path:
    sys.path.insert(0, str(_BETA_ROOT))

from python.services.image_stitch import stitch  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / 测试夹具
# ---------------------------------------------------------------------------

@pytest.fixture
def img_a():
    """10x10 image filled with 1.0."""
    return np.ones((10, 10), dtype=np.float32) * 1.0


@pytest.fixture
def img_b():
    """10x10 image filled with 2.0."""
    return np.ones((10, 10), dtype=np.float32) * 2.0


# ---------------------------------------------------------------------------
# Placement & canvas sizing / 放置与画布尺寸
# ---------------------------------------------------------------------------

class TestPlacement:
    def test_no_overlap_x_direction(self, img_a, img_b):
        """b offset 100µm at 10µm/px = 10px right; no overlap."""
        res, meta = stitch([(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 100.0, 0.0)], "mean")
        assert meta["canvas_width"] == 20
        assert meta["canvas_height"] == 10
        assert meta["overlaps"] is False
        assert res[0, 0] == 1.0       # a region
        assert res[0, 15] == 2.0      # b region

    def test_y_offset(self, img_a, img_b):
        """b offset 100µm down at 10µm/px = 10px down."""
        res, meta = stitch([(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 0.0, 100.0)], "mean")
        assert meta["canvas_height"] == 20
        assert meta["canvas_width"] == 10
        assert res[0, 0] == 1.0
        assert res[15, 0] == 2.0

    def test_negative_offset_normalizes_origin(self, img_a, img_b):
        """b at x=0, a at x=50µm → origin shifts left; canvas = 15px wide."""
        res, meta = stitch([(img_a, 10.0, 50.0, 0.0), (img_b, 10.0, 0.0, 0.0)], "mean")
        assert meta["canvas_width"] == 15

    def test_different_pixel_sizes(self, img_a):
        """Smaller pixel size → image spans fewer µm for same px count."""
        d = np.ones((5, 5), dtype=np.float32) * 3.0  # 5µm/px, 5px wide = 25µm
        # offset 100µm: at 5µm/px = 20px; canvas = max(10, 20+5) = 25
        _res, meta = stitch([(img_a, 10.0, 0.0, 0.0), (d, 5.0, 100.0, 0.0)], "mean")
        assert meta["canvas_width"] == 25


# ---------------------------------------------------------------------------
# Overlap strategies / 重叠策略
# ---------------------------------------------------------------------------

class TestOverlapStrategies:
    @pytest.fixture
    def overlap_pair(self, img_a, img_b):
        """a:[0,10), b:[5,15) → overlap [5,10)."""
        return [(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 50.0, 0.0)]

    def test_mean(self, overlap_pair):
        res, meta = stitch(overlap_pair, "mean")
        assert meta["overlaps"] is True
        # In overlap [5,10): mean(1, 2) = 1.5
        assert abs(res[0, 7] - 1.5) < 1e-5

    def test_sum(self, overlap_pair):
        res, _ = stitch(overlap_pair, "sum")
        assert abs(res[0, 7] - 3.0) < 1e-5

    def test_max(self, overlap_pair):
        res, _ = stitch(overlap_pair, "max")
        assert abs(res[0, 7] - 2.0) < 1e-5

    def test_first_respects_order(self, img_a, img_b):
        full_overlap = [(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 0.0, 0.0)]
        res_a_first = stitch(full_overlap, "first")[0]
        assert abs(res_a_first[0, 0] - 1.0) < 1e-5  # a first → a wins
        res_b_first = stitch(list(reversed(full_overlap)), "first")[0]
        assert abs(res_b_first[0, 0] - 2.0) < 1e-5  # b first → b wins

    def test_triple_overlap_mean(self, img_a, img_b):
        """Three images overlapping at col 7: a[7]=1, b[4]=2, c[2]=1 → 4/3."""
        triple = [
            (img_a, 10.0, 0.0, 0.0),
            (img_b, 10.0, 30.0, 0.0),  # offset 3px
            (img_a, 10.0, 50.0, 0.0),  # offset 5px
        ]
        res, meta = stitch(triple, "mean")
        assert meta["n_images"] == 3
        # col 7: a covers [0,10), b covers [3,13), c covers [5,15) → all three
        assert abs(res[0, 7] - (4.0 / 3.0)) < 1e-5


# ---------------------------------------------------------------------------
# Background & dead pixels / 背景与死像素
# ---------------------------------------------------------------------------

class TestBackgroundAndDeadPixels:
    def test_gap_is_nan(self, img_a, img_b):
        """Gap between a and b should be NaN."""
        # a:[0,10), b:[20,30) → gap [10,20)
        res, meta = stitch([(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 200.0, 0.0)], "mean")
        assert meta["canvas_width"] == 30
        assert np.isnan(res[0, 15])              # gap
        assert np.isfinite(res[0, 5])            # a region
        assert np.isfinite(res[0, 25])           # b region

    def test_dead_pixel_excluded_from_mean(self, img_a):
        """Dead-pixel sentinel (>=4.29e9) should be excluded from averaging."""
        c = np.full((10, 10), 5.0, dtype=np.float32)
        c[5, 0] = 5e9  # dead pixel in overlap region (lands at canvas col 5)
        res, _ = stitch([(img_a, 10.0, 0.0, 0.0), (c, 10.0, 50.0, 0.0)], "mean")
        # canvas (5,5): a[5,5]=1 valid, c[5,0]=dead invalid → only a → 1.0
        assert abs(res[5, 5] - 1.0) < 1e-5
        # canvas (5,7): a[5,7]=1, c[5,2]=5 → mean = 3.0
        assert abs(res[5, 7] - 3.0) < 1e-5

    def test_dead_pixel_excluded_from_max(self, img_a):
        """max should ignore dead pixels."""
        e = np.full((10, 10), 0.5, dtype=np.float32)
        e[3, 3] = 5e9  # dead
        res, _ = stitch([(img_a, 10.0, 0.0, 0.0), (e, 10.0, 0.0, 0.0)], "max")
        # full overlap; at (3,3): a=1 valid, e dead → max=1.0
        assert abs(res[3, 3] - 1.0) < 1e-5

    def test_coverage_ratio(self, img_a, img_b):
        """Coverage ratio reflects fraction of canvas covered."""
        # canvas 30 wide, a covers 10, b covers 10, gap 10 → coverage = 20/30
        _res, meta = stitch([(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 200.0, 0.0)], "mean")
        assert abs(meta["coverage_ratio"] - (20.0 / 30.0)) < 1e-5


# ---------------------------------------------------------------------------
# Validation / 输入校验
# ---------------------------------------------------------------------------

class TestValidation:
    def test_too_few_images(self, img_a):
        with pytest.raises(ValueError, match="at least 2"):
            stitch([(img_a, 10.0, 0.0, 0.0)], "mean")

    def test_empty_list(self):
        with pytest.raises(ValueError):
            stitch([], "mean")

    def test_bad_pixel_size(self, img_a, img_b):
        with pytest.raises(ValueError, match="pixel_size_um"):
            stitch([(img_a, 0.0, 0.0, 0.0), (img_b, 10.0, 0.0, 0.0)], "mean")

    def test_negative_pixel_size(self, img_a, img_b):
        with pytest.raises(ValueError, match="pixel_size_um"):
            stitch([(img_a, -5.0, 0.0, 0.0), (img_b, 10.0, 0.0, 0.0)], "mean")

    def test_unknown_strategy(self, img_a, img_b):
        with pytest.raises(ValueError, match="strategy"):
            stitch([(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 0.0, 0.0)], "bogus")

    def test_canvas_too_large(self, img_a, img_b):
        """Absurd offset triggering canvas-size guard."""
        with pytest.raises(ValueError, match="canvas too large"):
            stitch(
                [(img_a, 0.001, 0.0, 0.0), (img_b, 0.001, 1e9, 0.0)],
                "mean",
            )


# ---------------------------------------------------------------------------
# Meta & dtype / 元数据与数据类型
# ---------------------------------------------------------------------------

class TestMetaAndDtype:
    def test_returns_float32(self, img_a, img_b):
        res, _ = stitch([(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 100.0, 0.0)], "mean")
        assert res.dtype == np.float32

    def test_meta_fields(self, img_a, img_b):
        _res, meta = stitch([(img_a, 10.0, 0.0, 0.0), (img_b, 10.0, 100.0, 0.0)], "sum")
        for key in ("canvas_width", "canvas_height", "n_images", "strategy",
                    "coverage_ratio", "overlaps"):
            assert key in meta
        assert meta["n_images"] == 2
        assert meta["strategy"] == "sum"
        assert isinstance(meta["overlaps"], bool)
