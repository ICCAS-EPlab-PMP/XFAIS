#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_bg_subtractor.py — Comprehensive tests for bg_subtractor service.

Covers:
    Group A: subtract_with_reference (formula correctness, edge cases)
    Group B: parse_ionchamber_file (utf-8, GBK fallback, invalid path)
    Group C: calc_transmission (median/mean/trimmed_mean, error paths)
    Group D: match_ionchamber (5 priority levels, fuzzy matching)
    Group E: subtract_h5_stack (2D/3D, transmission validation)
    Group F: find_h5_transmissions (root / nested / attribute)
    Group G: Golden-file comparison against BGsub reference formula
"""

import logging

import h5py
import numpy as np
import pandas as pd
import pytest

from python.services.bg_subtractor import (
    calc_transmission,
    find_h5_transmissions,
    match_ionchamber,
    parse_ionchamber_file,
    subtract_h5_stack,
    subtract_with_reference,
)


# ---------------------------------------------------------------------------
# Group A: subtract_with_reference
# ---------------------------------------------------------------------------


class TestSubtractWithReference:
    def test_subtract_basic(self):
        """result = sample / T - background with known values."""
        sample = np.array(
            [[100.0, 200.0], [300.0, 400.0]], dtype=np.float32
        )
        bg = np.array(
            [[10.0, 20.0], [30.0, 40.0]], dtype=np.float32
        )
        result = subtract_with_reference(sample, bg, transmission=0.5)
        expected = np.array(
            [[190.0, 380.0], [570.0, 760.0]], dtype=np.float32
        )
        assert np.allclose(result, expected)

    def test_subtract_transmission_one(self):
        """T=1.0 should give sample - background."""
        sample = np.array(
            [[50.0, 60.0], [70.0, 80.0]], dtype=np.float32
        )
        bg = np.array(
            [[5.0, 6.0], [7.0, 8.0]], dtype=np.float32
        )
        result = subtract_with_reference(sample, bg, transmission=1.0)
        expected = sample - bg
        assert np.allclose(result, expected)

    def test_subtract_default_transmission(self):
        """Default transmission should be 1.0 → sample - background."""
        sample = np.array([[10.0, 20.0]], dtype=np.float32)
        bg = np.array([[1.0, 2.0]], dtype=np.float32)
        result = subtract_with_reference(sample, bg)
        assert np.allclose(result, [[9.0, 18.0]])

    def test_subtract_shape_mismatch(self):
        """Different shapes should crop to intersection (sample shape wins)."""
        sample = np.ones((4, 5), dtype=np.float32) * 100
        bg = np.ones((3, 6), dtype=np.float32) * 10
        result = subtract_with_reference(sample, bg, transmission=1.0)
        # Output shape follows sample.
        assert result.shape == (4, 5)
        # Cropped area (3x5 intersection) computed correctly.
        assert np.allclose(result[:3, :5], 90.0)
        # Extra area in sample (last row) stays at fill value of 0.
        assert np.allclose(result[3:, :], 0.0)

    def test_subtract_3d_batch(self):
        """3D input (batch) — last two dims treated as image."""
        sample = np.ones((2, 4, 4), dtype=np.float32) * 200
        bg = np.ones((3, 3), dtype=np.float32) * 20
        result = subtract_with_reference(sample, bg, transmission=0.5)
        assert result.shape == (2, 4, 4)
        # Each frame: 200/0.5 - 20 = 380
        assert np.allclose(result[:, :3, :3], 380.0)
        # Right column and bottom row untouched
        assert np.allclose(result[:, :, 3:], 0.0)
        assert np.allclose(result[:, 3:, :], 0.0)

    def test_zero_transmission_raises(self):
        """T=0 should raise ValueError."""
        sample = np.ones((2, 2), dtype=np.float32)
        bg = np.ones((2, 2), dtype=np.float32)
        with pytest.raises(ValueError, match="Transmission must be > 0"):
            subtract_with_reference(sample, bg, transmission=0.0)

    def test_negative_transmission_raises(self):
        """T<0 should raise ValueError."""
        sample = np.ones((2, 2), dtype=np.float32)
        bg = np.ones((2, 2), dtype=np.float32)
        with pytest.raises(ValueError, match="Transmission must be > 0"):
            subtract_with_reference(sample, bg, transmission=-0.1)

    def test_nan_propagation(self):
        """NaN in input should propagate to output (warning logged)."""
        sample = np.array([[10.0, np.nan], [30.0, 40.0]], dtype=np.float32)
        bg = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        result = subtract_with_reference(sample, bg, transmission=1.0)
        assert np.isnan(result[0, 1])
        # Other cells remain finite
        assert np.isfinite(result[0, 0])
        assert np.isfinite(result[1, :]).all()

    def test_inf_propagation(self):
        """Inf in input should propagate to output (warning logged)."""
        sample = np.array([[np.inf, 20.0], [30.0, 40.0]], dtype=np.float32)
        bg = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
        result = subtract_with_reference(sample, bg, transmission=1.0)
        assert np.isinf(result[0, 0])
        assert result[0, 0] > 0  # positive infinity preserved

    def test_output_dtype_float32(self):
        """Output should always be float32, regardless of input dtype."""
        sample_f32 = np.ones((3, 3), dtype=np.float32) * 100
        bg_f32 = np.ones((3, 3), dtype=np.float32) * 10
        result = subtract_with_reference(sample_f32, bg_f32, transmission=0.5)
        assert result.dtype == np.float32

        sample_f64 = np.ones((3, 3), dtype=np.float64) * 100
        bg_f64 = np.ones((3, 3), dtype=np.float64) * 10
        result = subtract_with_reference(sample_f64, bg_f64, transmission=0.5)
        assert result.dtype == np.float32

    def test_warning_on_nan(self, caplog):
        """Non-finite values should trigger a warning."""
        sample = np.array([[np.nan, 20.0]], dtype=np.float32)
        bg = np.array([[1.0, 2.0]], dtype=np.float32)
        with caplog.at_level(logging.WARNING):
            subtract_with_reference(sample, bg, transmission=1.0)
        assert any(
            "non-finite values" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# Group B: parse_ionchamber_file
# ---------------------------------------------------------------------------


class TestParseIonchamberFile:
    def test_parse_ionchamber_basic(self, tmp_path):
        """Parse a valid .Ionchamber file."""
        ion_file = tmp_path / "test.Ionchamber"
        ion_file.write_text(
            "# Time  Ionchamber0  Ionchamber1  Ionchamber2\n"
            "2026-01-19 12:34:34.130671238  2.807135e-7  2.388761e-8  9.71103e-10\n"
            "2026-01-19 12:34:35.130671238  2.907135e-7  2.488761e-8  1.071103e-9\n",
            encoding="utf-8",
        )
        df = parse_ionchamber_file(str(ion_file))
        assert df is not None
        assert len(df) == 2
        # Expected column names
        assert "Ionchamber0" in df.columns
        assert "Ionchamber1" in df.columns
        assert "Ionchamber2" in df.columns
        assert "Time" in df.columns
        # First row intensity values
        assert df["Ionchamber0"].iloc[0] == pytest.approx(2.807135e-7)
        assert df["Ionchamber2"].iloc[1] == pytest.approx(1.071103e-9)
        # Time column should be the joined date+time string
        assert df["Time"].iloc[0].startswith("2026-01-19 12:34:34")

    def test_parse_ionchamber_gbk_encoding(self, tmp_path):
        """GBK encoded file should parse via fallback encoding."""
        ion_file = tmp_path / "test_gbk.Ionchamber"
        content = (
            "# Time  Ionchamber0  Ionchamber1  Ionchamber2\n"
            "2026-01-19 12:34:34.130671238  2.807135e-7  2.388761e-8  9.71103e-10\n"
        )
        # Write raw GBK bytes so utf-8 decode fails.
        ion_file.write_bytes(content.encode("gbk"))
        df = parse_ionchamber_file(str(ion_file))
        assert df is not None
        assert len(df) == 1
        assert df["Ionchamber0"].iloc[0] == pytest.approx(2.807135e-7)

    def test_parse_ionchamber_invalid_path(self):
        """Non-existent file should return None."""
        result = parse_ionchamber_file("/nonexistent/path/to/file.Ionchamber")
        assert result is None

    def test_parse_ionchamber_empty_file(self, tmp_path):
        """Empty file should return None (no data rows)."""
        ion_file = tmp_path / "empty.Ionchamber"
        ion_file.write_text("", encoding="utf-8")
        result = parse_ionchamber_file(str(ion_file))
        assert result is None

    def test_parse_ionchamber_skips_comments_and_blanks(self, tmp_path):
        """Lines starting with # and blank lines should be ignored."""
        ion_file = tmp_path / "commented.Ionchamber"
        ion_file.write_text(
            "# Header comment\n"
            "\n"
            "# Another comment\n"
            "2026-01-19 12:34:34.000000000  1.0e-7  2.0e-8  3.0e-10\n",
            encoding="utf-8",
        )
        df = parse_ionchamber_file(str(ion_file))
        assert df is not None
        assert len(df) == 1
        assert df["Ionchamber0"].iloc[0] == pytest.approx(1.0e-7)


# ---------------------------------------------------------------------------
# Group C: calc_transmission
# ---------------------------------------------------------------------------


def _make_ion_df(values):
    """Helper: build a DataFrame matching the parse_ionchamber_file schema."""
    return pd.DataFrame({
        "Time": ["2026-01-19 12:34:34"] * len(values),
        "Ionchamber0": values,
        "Ionchamber1": [v * 0.1 for v in values],
        "Ionchamber2": [v * 0.01 for v in values],
    })


class TestCalcTransmission:
    def test_calc_transmission_basic(self):
        """Basic transmission = sample / background ratio."""
        sample_df = _make_ion_df([2.0, 4.0, 6.0])
        bg_df = _make_ion_df([10.0, 10.0, 10.0])
        # median sample = 4.0, median bg = 10.0, T = 0.4
        t = calc_transmission(sample_df, bg_df, channel="Ionchamber0")
        assert t == pytest.approx(0.4)

    def test_calc_transmission_zero_bg_raises(self):
        """Zero background intensity should raise ValueError."""
        sample_df = _make_ion_df([1.0, 2.0, 3.0])
        bg_df = _make_ion_df([0.0, 0.0, 0.0])
        with pytest.raises(ValueError, match="zero or unavailable"):
            calc_transmission(sample_df, bg_df, channel="Ionchamber0")

    def test_calc_transmission_methods(self):
        """median, mean, trimmed_mean should all work."""
        sample_df = _make_ion_df([1.0, 2.0, 3.0, 4.0, 5.0])
        bg_df = _make_ion_df([10.0, 10.0, 10.0, 10.0, 10.0])

        t_median = calc_transmission(
            sample_df, bg_df, channel="Ionchamber0", method="median"
        )
        assert t_median == pytest.approx(0.3)  # median(1..5) / 10

        t_mean = calc_transmission(
            sample_df, bg_df, channel="Ionchamber0", method="mean"
        )
        assert t_mean == pytest.approx(0.3)  # mean(1..5) / 10

        # trimmed_mean: sort [1,2,3,4,5], drop first and last → [2,3,4] mean = 3
        t_trimmed = calc_transmission(
            sample_df, bg_df, channel="Ionchamber0", method="trimmed_mean"
        )
        assert t_trimmed == pytest.approx(0.3)

    def test_calc_transmission_invalid_channel(self):
        """Missing channel should raise ValueError."""
        sample_df = _make_ion_df([1.0, 2.0])
        bg_df = _make_ion_df([10.0, 10.0])
        with pytest.raises(ValueError, match="Cannot compute sample intensity"):
            calc_transmission(
                sample_df, bg_df, channel="NonexistentChannel"
            )

    def test_calc_transmission_trimmed_short_fallback(self):
        """trimmed_mean with <=2 values should fall back to plain mean."""
        sample_df = _make_ion_df([2.0, 4.0])
        bg_df = _make_ion_df([10.0, 10.0])
        # mean(2,4) / 10 = 0.3
        t = calc_transmission(
            sample_df, bg_df, channel="Ionchamber0", method="trimmed_mean"
        )
        assert t == pytest.approx(0.3)


# ---------------------------------------------------------------------------
# Group D: match_ionchamber
# ---------------------------------------------------------------------------


class TestMatchIonchamber:
    def test_match_exact(self):
        """Exact filename match (base + state + number all equal)."""
        tiffs = ["sample_001.tif", "bg_001.tif"]
        ions = ["sample_001.Ionchamber", "bg_001.Ionchamber"]
        matches = match_ionchamber(tiffs, ions)
        assert len(matches) == 2
        # Both should have high scores
        assert all(m["score"] >= 0.9 for m in matches)
        # Method should be 'exact' or 'base_state'
        assert all(
            m["method"] in ("exact", "base_state") for m in matches
        )

    def test_match_fuzzy(self):
        """Fuzzy matching for similar names."""
        tiffs = ["data_Q_001.tif"]
        ions = ["data-Q-001.Ionchamber"]  # underscores → dashes
        matches = match_ionchamber(tiffs, ions)
        assert len(matches) == 1
        # High score from priority 1/2
        assert matches[0]["score"] >= 0.9

    def test_match_no_match(self):
        """Completely different names should have low scores / no match."""
        tiffs = ["alpha_sample_001.tif"]
        ions = ["zzz_completely_different.Ionchamber"]
        matches = match_ionchamber(tiffs, ions)
        assert len(matches) == 1
        # No match or very low score
        assert (
            matches[0]["matched_ion"] is None
            or matches[0]["score"] < 0.5
        )
        assert matches[0]["method"] in ("none", "fuzzy")

    def test_match_empty_lists(self):
        """Empty input should return empty output."""
        assert match_ionchamber([], []) == []
        # Empty tiffs with non-empty ions
        assert match_ionchamber([], ["x.Ionchamber"]) == []
        # Non-empty tiffs with empty ions
        result = match_ionchamber(["a.tif"], [])
        assert len(result) == 1
        assert result[0]["matched_ion"] is None
        assert result[0]["method"] == "none"

    def test_match_priority_base_only(self):
        """Same base, different state — should still match via base_only."""
        tiffs = ["wkf-G1-Q-30-2-waxs-11.9s_00001.tif"]
        ions = ["wkf-G1-W-30-1-BG-waxs_00099.Ionchamber"]
        matches = match_ionchamber(tiffs, ions)
        assert len(matches) == 1
        # Method should not be 'none'
        assert matches[0]["method"] != "none"
        # Same base 'wkf' → matches
        assert matches[0]["matched_ion"] is not None

    def test_match_result_keys(self):
        """Each result dict should contain the documented keys."""
        tiffs = ["a_001.tif"]
        ions = ["a_001.Ionchamber"]
        result = match_ionchamber(tiffs, ions)
        assert len(result) == 1
        m = result[0]
        assert set(m.keys()) == {
            "data_file", "matched_ion", "score", "method"
        }
        assert m["data_file"] == "a_001.tif"


# ---------------------------------------------------------------------------
# Group E: subtract_h5_stack
# ---------------------------------------------------------------------------


class TestSubtractH5Stack:
    def test_h5_stack_3d(self, tmp_path):
        """3D HDF5 stack subtraction with per-frame transmissions."""
        h5_file = tmp_path / "sample.h5"
        bg_file = tmp_path / "bg.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset(
                "data",
                data=np.ones((3, 10, 10), dtype=np.float32) * 100,
            )
        with h5py.File(str(bg_file), "w") as f:
            f.create_dataset(
                "data",
                data=np.ones((3, 10, 10), dtype=np.float32) * 10,
            )
        # Read the bg as 2D and pass it in (broadcastable).
        with h5py.File(str(bg_file), "r") as f:
            bg_2d = np.asarray(f["data"][0], dtype=np.float32)
        transmissions = np.array([0.9, 0.95, 0.85], dtype=np.float32)
        result = subtract_h5_stack(
            str(h5_file), "data", bg_2d, transmissions=transmissions
        )
        assert result.shape == (3, 10, 10)
        # Verify formula: 100/0.9 - 10 ≈ 101.111
        assert np.allclose(result[0], 100 / 0.9 - 10, atol=0.1)
        assert np.allclose(result[1], 100 / 0.95 - 10, atol=0.1)
        assert np.allclose(result[2], 100 / 0.85 - 10, atol=0.1)

    def test_h5_stack_2d(self, tmp_path):
        """2D HDF5 should be treated as a single frame (N=1)."""
        h5_file = tmp_path / "sample_2d.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset(
                "data", data=np.ones((8, 8), dtype=np.float32) * 50
            )
        bg_2d = np.ones((8, 8), dtype=np.float32) * 5
        result = subtract_h5_stack(
            str(h5_file), "data", bg_2d, transmissions=None
        )
        # 2D input is wrapped to (1, H, W) — output is 3D.
        assert result.ndim == 3
        assert result.shape[0] == 1
        assert np.allclose(result[0], 45.0)  # 50 - 5 with T=1.0

    def test_h5_stack_transmission_mismatch(self, tmp_path):
        """Transmission length != frame count should raise ValueError."""
        h5_file = tmp_path / "mismatch.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset(
                "data", data=np.ones((3, 5, 5), dtype=np.float32)
            )
        bg = np.ones((5, 5), dtype=np.float32)
        # 2 transmissions for 3 frames
        with pytest.raises(ValueError, match="transmissions length"):
            subtract_h5_stack(
                str(h5_file),
                "data",
                bg,
                transmissions=np.array([0.9, 0.8], dtype=np.float32),
            )

    def test_h5_stack_no_transmission(self, tmp_path):
        """No transmission should use default T=1.0 (simple subtraction)."""
        h5_file = tmp_path / "no_trans.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset(
                "data",
                data=np.full((2, 4, 4), 100.0, dtype=np.float32),
            )
        bg = np.full((4, 4), 20.0, dtype=np.float32)
        result = subtract_h5_stack(str(h5_file), "data", bg, transmissions=None)
        assert result.shape == (2, 4, 4)
        # T=1.0 → 100 - 20 = 80
        assert np.allclose(result, 80.0)

    def test_h5_stack_missing_file(self):
        """Missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            subtract_h5_stack(
                "/nonexistent/file.h5", "data", np.zeros((2, 2))
            )

    def test_h5_stack_missing_dataset(self, tmp_path):
        """Missing dataset path should raise KeyError."""
        h5_file = tmp_path / "no_ds.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset("other", data=np.ones((3, 3), dtype=np.float32))
        with pytest.raises(KeyError, match="not found"):
            subtract_h5_stack(
                str(h5_file), "data", np.zeros((3, 3))
            )

    def test_h5_stack_dtype_float32(self, tmp_path):
        """Output should always be float32."""
        h5_file = tmp_path / "dtype_test.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset(
                "data",
                data=np.ones((2, 4, 4), dtype=np.float64) * 50,
            )
        bg = np.ones((4, 4), dtype=np.float64) * 5
        result = subtract_h5_stack(str(h5_file), "data", bg, transmissions=None)
        assert result.dtype == np.float32

    def test_h5_stack_4d(self, tmp_path):
        """4D HDF5 (N, C, H, W) subtraction across all channels."""
        h5_file = tmp_path / "stack_4d.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset(
                "data",
                data=np.ones((2, 2, 4, 4), dtype=np.float32) * 100,
            )
        bg = np.ones((4, 4), dtype=np.float32) * 10
        result = subtract_h5_stack(
            str(h5_file),
            "data",
            bg,
            transmissions=np.array([0.5, 0.5], dtype=np.float32),
        )
        # 4D shape preserved: 100/0.5 - 10 = 190
        assert result.shape == (2, 2, 4, 4)
        assert np.allclose(result, 190.0)


# ---------------------------------------------------------------------------
# Group F: find_h5_transmissions
# ---------------------------------------------------------------------------


class TestFindH5Transmissions:
    def test_find_transmissions_found(self, tmp_path):
        """Should find a transmission dataset at root level."""
        h5_file = tmp_path / "with_trans.h5"
        trans_values = np.array([0.9, 0.85, 0.95], dtype=np.float32)
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset("data", data=np.ones((3, 4, 4), dtype=np.float32))
            f.create_dataset("transmission", data=trans_values)
        result = find_h5_transmissions(str(h5_file))
        assert result is not None
        assert np.allclose(result, trans_values)

    def test_find_transmissions_not_found(self, tmp_path):
        """Should return None when no transmission dataset exists."""
        h5_file = tmp_path / "no_trans.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset("data", data=np.ones((3, 4, 4), dtype=np.float32))
            f.create_dataset("intensity", data=np.ones((3,), dtype=np.float32))
        result = find_h5_transmissions(str(h5_file))
        assert result is None

    def test_find_transmissions_missing_file(self):
        """Should return None for a non-existent file."""
        result = find_h5_transmissions("/nonexistent/file.h5")
        assert result is None

    def test_find_transmissions_nested(self, tmp_path):
        """Should find transmission dataset nested inside a group."""
        h5_file = tmp_path / "nested_trans.h5"
        trans_values = np.array([0.7, 0.8], dtype=np.float32)
        with h5py.File(str(h5_file), "w") as f:
            entry = f.create_group("entry")
            entry.create_dataset("data", data=np.ones((2, 4, 4)))
            entry.create_dataset("transmission", data=trans_values)
        result = find_h5_transmissions(str(h5_file))
        assert result is not None
        assert np.allclose(result, trans_values)

    def test_find_transmissions_root_attr(self, tmp_path):
        """Should find transmission stored as a root attribute."""
        h5_file = tmp_path / "attr_trans.h5"
        with h5py.File(str(h5_file), "w") as f:
            f.create_dataset("data", data=np.ones((2, 4, 4)))
            f.attrs["transmission"] = np.array([0.6, 0.5], dtype=np.float32)
        result = find_h5_transmissions(str(h5_file))
        assert result is not None
        assert np.allclose(result, [0.6, 0.5])


# ---------------------------------------------------------------------------
# Group G: Golden-file comparison against BGsub reference
# ---------------------------------------------------------------------------


class TestGoldenFileFormula:
    def test_golden_file_formula(self):
        """Verify X-FAIS formula matches BGsub reference exactly.

        The reference (ref/BGsub/WORKSPACE/BGsub/core/bg_fitter.py
        fit_with_reference) computes:
            result = sample / T - reference   (overlap region, float64)

        Our subtract_with_reference does the same in float32.
        This test confirms bit-for-bit equivalence (modulo dtype precision).
        """
        np.random.seed(42)
        sample = np.random.rand(100, 100).astype(np.float32) * 1000
        bg = np.random.rand(100, 100).astype(np.float32) * 50
        T = 0.85

        # X-FAIS result (float32)
        xfais_result = subtract_with_reference(sample, bg, transmission=T)

        # Reference implementation (replicated inline from bg_fitter.py)
        sr, sc = sample.shape
        rr, rc = bg.shape
        cr, cc = min(sr, rr), min(sc, rc)
        ref_result = np.zeros_like(sample, dtype=np.float64)
        ref_result[:cr, :cc] = (
            sample[:cr, :cc] / T - bg[:cr, :cc]
        )

        # Compare: reference is float64; X-FAIS is float32.
        max_diff = np.max(np.abs(xfais_result - ref_result.astype(np.float32)))
        assert max_diff < 1e-3, (
            f"Max diff: {max_diff} exceeds float32 precision tolerance"
        )
        # Tighter assertion: ratio of values should be near 1.0
        assert np.allclose(
            xfais_result, ref_result.astype(np.float32), rtol=1e-5
        ), f"Max diff: {np.max(np.abs(xfais_result - ref_result.astype(np.float32)))}"

    def test_golden_file_formula_mismatched_shapes(self):
        """Formula equivalence with mismatched sample/bg shapes."""
        np.random.seed(7)
        sample = np.random.rand(50, 80).astype(np.float32) * 500
        bg = np.random.rand(40, 100).astype(np.float32) * 25
        T = 0.92

        xfais_result = subtract_with_reference(sample, bg, transmission=T)

        # Reference: crop to intersection, output shape = sample.shape
        sr, sc = sample.shape
        rr, rc = bg.shape
        cr, cc = min(sr, rr), min(sc, rc)
        ref_result = np.zeros_like(sample, dtype=np.float64)
        ref_result[:cr, :cc] = sample[:cr, :cc] / T - bg[:cr, :cc]

        assert xfais_result.shape == ref_result.shape
        # Float32 precision: a few counts at most
        diff = np.abs(xfais_result - ref_result.astype(np.float32))
        assert np.max(diff) < 0.5, f"Max diff: {np.max(diff)}"

    def test_golden_file_formula_various_transmissions(self):
        """Formula holds for a range of transmission values."""
        np.random.seed(123)
        sample = np.random.rand(20, 20).astype(np.float32) * 100
        bg = np.random.rand(20, 20).astype(np.float32) * 5

        for T in [0.1, 0.5, 0.85, 0.99, 1.0]:
            xfais = subtract_with_reference(sample, bg, transmission=T)
            ref = sample / T - bg
            # Allow float32 vs implicit float64 round-off
            assert np.allclose(xfais, ref.astype(np.float32), rtol=1e-4), (
                f"T={T}: max diff = {np.max(np.abs(xfais - ref.astype(np.float32)))}"
            )
