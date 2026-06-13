#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_bg_integration.py — Integration tests for background subtraction service
test_bg_integration.py — 背景扣除服务集成测试

Tests cover:
  A. Handler integration (handle_bg_subtract with monkeypatched deps)
  B. Core module functions (subtract_with_reference, ionchamber, h5 stack)
  C. Memory usage for large datasets
  D. Error recovery and edge cases
"""

from __future__ import annotations

import asyncio
import os
import sys
import tracemalloc
from pathlib import Path

# Ensure BETA/python is on sys.path so service_launcher can import `services.*`
_PYTHON_DIR = str(Path(__file__).resolve().parent.parent)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

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
# Helpers
# ---------------------------------------------------------------------------

async def _noop_progress(_progress: float, _message: str) -> None:
    """No-op progress callback."""


def _write_ionchamber_file(path: str, rows: list[list], header: bool = True) -> None:
    """Write a fake .Ionchamber text file."""
    lines: list[str] = []
    if header:
        lines.append("# Time  Ionchamber0  Ionchamber1  Ionchamber2")
    for row in rows:
        lines.append("  ".join(str(v) for v in row))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ===========================================================================
# Group A: Handler Integration Tests
# ===========================================================================


class TestBgSubtractHandlerIntegration:
    """Test the handle_bg_subtract handler with monkeypatched dependencies."""

    def test_single_subtract_end_to_end(self, monkeypatch) -> None:
        """Full single-file subtraction flow via handler."""
        sample_data = np.ones((100, 100), dtype=np.float32) * 100
        bg_data = np.ones((100, 100), dtype=np.float32) * 10

        def _fake_load(path: str):
            if "sample" in path:
                return sample_data, None, {"filename": "sample.edf"}
            return bg_data, None, {"filename": "bg.edf"}

        def _fake_compute_stats(data):
            return {"autoMin": float(np.nanmin(data)), "autoMax": float(np.nanmax(data))}

        def _fake_render_png(data, settings):
            return b"fake-png-bytes"

        monkeypatch.setattr("python.service_launcher.ImageLoader.load", _fake_load)
        monkeypatch.setattr("python.service_launcher.ImageRenderer.compute_stats", _fake_compute_stats)
        monkeypatch.setattr("python.service_launcher.ImageRenderer.render_png", _fake_render_png)

        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {
                    "action": "subtract",
                    "sample_path": "sample.edf",
                    "bg_path": "bg.edf",
                    "transmission": 0.5,
                },
                _noop_progress,
                asyncio.Event(),
            )
        )

        assert result["status"] == "ok"
        assert result["result"]["shape"] == [100, 100]
        # 100/0.5 - 10 = 190
        assert abs(result["result"]["min"] - 190.0) < 0.01
        assert abs(result["result"]["max"] - 190.0) < 0.01

    def test_single_subtract_missing_sample_path(self) -> None:
        """Handler returns error when sample_path is missing."""
        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {"action": "subtract", "bg_path": "bg.edf"},
                _noop_progress,
                asyncio.Event(),
            )
        )
        assert result["status"] == "error"
        assert "sample_path" in result["message"]

    def test_single_subtract_missing_bg_path(self) -> None:
        """Handler returns error when bg_path is missing."""
        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {"action": "subtract", "sample_path": "sample.edf"},
                _noop_progress,
                asyncio.Event(),
            )
        )
        assert result["status"] == "error"
        assert "bg_path" in result["message"]

    def test_unknown_action_returns_error(self) -> None:
        """Unknown action returns error."""
        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {"action": "nonexistent"},
                _noop_progress,
                asyncio.Event(),
            )
        )
        assert result["status"] == "error"
        assert "Unknown action" in result["message"]

    def test_batch_flow_simulation(self, tmp_path, monkeypatch) -> None:
        """Simulate batch processing flow via handler."""
        # Create fake EDF files in a folder
        folder = tmp_path / "samples"
        folder.mkdir()
        for i in range(3):
            (folder / f"sample_{i:05d}.edf").write_bytes(b"fake-edf-data")

        bg_file = tmp_path / "bg.edf"
        bg_file.write_bytes(b"fake-bg-data")

        output_dir = tmp_path / "output"

        sample_data = np.ones((50, 50), dtype=np.float32) * 200
        bg_data = np.ones((50, 50), dtype=np.float32) * 20

        def _fake_load(path: str):
            if "bg" in path:
                return bg_data, None, {"filename": "bg.edf"}
            return sample_data, None, {"filename": os.path.basename(path)}

        monkeypatch.setattr("python.service_launcher.ImageLoader.load", _fake_load)

        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {
                    "action": "batch",
                    "folder_path": str(folder),
                    "bg_path": str(bg_file),
                    "output_dir": str(output_dir),
                    "transmission": 1.0,
                },
                _noop_progress,
                asyncio.Event(),
            )
        )

        assert result["status"] == "ok"
        assert result["success_count"] == 3
        assert result["failed_count"] == 0
        assert output_dir.exists()

    def test_batch_cancel_midway(self, tmp_path, monkeypatch) -> None:
        """Batch processing respects cancel_event."""
        folder = tmp_path / "samples"
        folder.mkdir()
        for i in range(5):
            (folder / f"sample_{i:05d}.edf").write_bytes(b"fake")

        bg_file = tmp_path / "bg.edf"
        bg_file.write_bytes(b"fake")

        sample_data = np.ones((10, 10), dtype=np.float32)
        bg_data = np.ones((10, 10), dtype=np.float32) * 0.1

        call_count = 0

        def _fake_load(path: str):
            nonlocal call_count
            call_count += 1
            if "bg" in path:
                return bg_data, None, {}
            return sample_data, None, {}

        monkeypatch.setattr("python.service_launcher.ImageLoader.load", _fake_load)

        cancel_event = asyncio.Event()
        cancel_event.set()  # Pre-cancelled

        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {
                    "action": "batch",
                    "folder_path": str(folder),
                    "bg_path": str(bg_file),
                    "output_dir": str(tmp_path / "out"),
                    "transmission": 1.0,
                },
                _noop_progress,
                cancel_event,
            )
        )

        assert result["status"] == "cancelled"

    def test_ionchamber_match_handler(self, tmp_path) -> None:
        """Ionchamber match handler returns matches."""
        # Create ionchamber files
        ion_dir = tmp_path / "ions"
        ion_dir.mkdir()

        sample_ion_path = str(ion_dir / "wkf-G1-Q-30-2-waxs-11.9s_00001.Ionchamber")
        bg_ion_path = str(ion_dir / "wkf-G1-W-30-1-BG-waxs_00001.Ionchamber")

        _write_ionchamber_file(sample_ion_path, [
            ["2026-01-19 12:34:34.130", "2.807135e-7", "2.388761e-8", "9.71103e-10"],
            ["2026-01-19 12:34:35.130", "2.810000e-7", "2.390000e-8", "9.72000e-10"],
        ])
        _write_ionchamber_file(bg_ion_path, [
            ["2026-01-19 12:30:00.000", "3.300000e-7", "2.800000e-8", "1.10000e-9"],
            ["2026-01-19 12:30:01.000", "3.310000e-7", "2.810000e-8", "1.11000e-9"],
        ])

        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {
                    "action": "ionchamber_match",
                    "data_files": ["wkf-G1-Q-30-2-waxs-11.9s_00001.tiff"],
                    "ionchamber_files": [sample_ion_path, bg_ion_path],
                },
                _noop_progress,
                asyncio.Event(),
            )
        )

        assert result["status"] == "ok"
        assert result["count"] == 1


# ===========================================================================
# Group B: Core Module Function Tests
# ===========================================================================


class TestSubtractWithReference:
    """Direct tests for subtract_with_reference core function."""

    def test_basic_subtraction(self) -> None:
        """Basic formula: sample / T - background."""
        sample = np.ones((100, 100), dtype=np.float32) * 100
        bg = np.ones((100, 100), dtype=np.float32) * 10
        result = subtract_with_reference(sample, bg, transmission=0.5)
        # 100/0.5 - 10 = 190
        assert np.allclose(result, 190.0)

    def test_transmission_one(self) -> None:
        """T=1.0 means no scaling."""
        sample = np.ones((50, 50), dtype=np.float32) * 80
        bg = np.ones((50, 50), dtype=np.float32) * 30
        result = subtract_with_reference(sample, bg, transmission=1.0)
        assert np.allclose(result, 50.0)

    def test_mismatched_shapes(self) -> None:
        """Different shapes: uses overlapping region."""
        sample = np.ones((100, 120), dtype=np.float32) * 50
        bg = np.ones((80, 100), dtype=np.float32) * 10
        result = subtract_with_reference(sample, bg, transmission=1.0)
        assert result.shape == (100, 120)
        # Overlapping region: 50 - 10 = 40
        assert np.allclose(result[:80, :100], 40.0)
        # Non-overlapping region: zeros
        assert np.allclose(result[80:, :], 0.0)
        assert np.allclose(result[:80, 100:], 0.0)

    def test_zero_transmission_raises(self) -> None:
        """T=0 should raise ValueError."""
        sample = np.ones((10, 10), dtype=np.float32)
        bg = np.ones((10, 10), dtype=np.float32)
        with pytest.raises(ValueError, match="Transmission must be > 0"):
            subtract_with_reference(sample, bg, transmission=0.0)

    def test_negative_transmission_raises(self) -> None:
        """Negative T should raise ValueError."""
        sample = np.ones((10, 10), dtype=np.float32)
        bg = np.ones((10, 10), dtype=np.float32)
        with pytest.raises(ValueError, match="Transmission must be > 0"):
            subtract_with_reference(sample, bg, transmission=-0.5)

    def test_result_dtype_is_float32(self) -> None:
        """Result is always float32."""
        sample = np.ones((10, 10), dtype=np.uint16) * 100
        bg = np.ones((10, 10), dtype=np.uint16) * 10
        result = subtract_with_reference(sample, bg, transmission=1.0)
        assert result.dtype == np.float32


class TestIonchamberParsing:
    """Tests for ionchamber file parsing and transmission calculation."""

    def test_parse_ionchamber_file(self, tmp_path) -> None:
        """Parse a well-formed ionchamber file."""
        path = str(tmp_path / "test.Ionchamber")
        _write_ionchamber_file(path, [
            ["2026-01-19 12:34:34.130", "2.807135e-7", "2.388761e-8", "9.71103e-10"],
            ["2026-01-19 12:34:35.130", "2.810000e-7", "2.390000e-8", "9.72000e-10"],
            ["2026-01-19 12:34:36.130", "2.805000e-7", "2.385000e-8", "9.70000e-10"],
        ])

        df = parse_ionchamber_file(path)
        assert df is not None
        assert len(df) == 3
        assert "Ionchamber0" in df.columns
        assert "Ionchamber1" in df.columns
        assert "Ionchamber2" in df.columns
        assert abs(df["Ionchamber0"].iloc[0] - 2.807135e-7) < 1e-15

    def test_parse_empty_file_returns_none(self, tmp_path) -> None:
        """Empty file returns None."""
        path = str(tmp_path / "empty.Ionchamber")
        Path(path).write_text("# header only\n", encoding="utf-8")
        df = parse_ionchamber_file(path)
        assert df is None

    def test_parse_nonexistent_file_returns_none(self) -> None:
        """Non-existent file returns None."""
        df = parse_ionchamber_file("/nonexistent/path/file.Ionchamber")
        assert df is None

    def test_calc_transmission_median(self, tmp_path) -> None:
        """Transmission calculation with median method."""
        sample_path = str(tmp_path / "sample.Ionchamber")
        bg_path = str(tmp_path / "bg.Ionchamber")

        _write_ionchamber_file(sample_path, [
            ["2026-01-19 12:34:34.130", "8.5e-8", "1.0e-8", "1.0e-9"],
            ["2026-01-19 12:34:35.130", "8.5e-8", "1.0e-8", "1.0e-9"],
            ["2026-01-19 12:34:36.130", "8.5e-8", "1.0e-8", "1.0e-9"],
        ])
        _write_ionchamber_file(bg_path, [
            ["2026-01-19 12:30:00.000", "1.0e-7", "1.0e-8", "1.0e-9"],
            ["2026-01-19 12:30:01.000", "1.0e-7", "1.0e-8", "1.0e-9"],
            ["2026-01-19 12:30:02.000", "1.0e-7", "1.0e-8", "1.0e-9"],
        ])

        sample_df = parse_ionchamber_file(sample_path)
        bg_df = parse_ionchamber_file(bg_path)
        assert sample_df is not None
        assert bg_df is not None

        t = calc_transmission(sample_df, bg_df, channel="Ionchamber0", method="median")
        # 8.5e-8 / 1.0e-7 = 0.85
        assert abs(t - 0.85) < 0.01

    def test_calc_transmission_zero_bg_raises(self) -> None:
        """Zero background intensity raises ValueError."""
        sample_df = pd.DataFrame({
            "Time": ["t1"], "Ionchamber0": [1.0],
            "Ionchamber1": [1.0], "Ionchamber2": [1.0],
        })
        bg_df = pd.DataFrame({
            "Time": ["t1"], "Ionchamber0": [0.0],
            "Ionchamber1": [1.0], "Ionchamber2": [1.0],
        })
        with pytest.raises(ValueError, match="Background intensity is zero"):
            calc_transmission(sample_df, bg_df, channel="Ionchamber0")


class TestIonchamberMatching:
    """Tests for ionchamber file matching."""

    def test_exact_match(self) -> None:
        """Exact filename match."""
        data_files = ["wkf-G1-Q-30-2-waxs-11.9s_00001.tiff"]
        ion_files = [
            "/data/wkf-G1-Q-30-2-waxs-11.9s_00001.Ionchamber",
            "/data/wkf-G1-W-30-1-BG-waxs_00001.Ionchamber",
        ]
        results = match_ionchamber(data_files, ion_files)
        assert len(results) == 1
        assert results[0]["matched_ion"] == "/data/wkf-G1-Q-30-2-waxs-11.9s_00001.Ionchamber"
        assert results[0]["method"] == "exact"
        assert results[0]["score"] == 1.0

    def test_no_match_returns_none(self) -> None:
        """Completely unrelated names return None match."""
        data_files = ["completely_different_file.tiff"]
        ion_files = ["/data/xyz-abc-123.Ionchamber"]
        results = match_ionchamber(data_files, ion_files)
        assert len(results) == 1
        assert results[0]["matched_ion"] is None
        assert results[0]["method"] == "none"

    def test_multiple_data_files(self) -> None:
        """Multiple data files each get matched."""
        data_files = [
            "wkf-sample_00001.tiff",
            "wkf-sample_00002.tiff",
        ]
        ion_files = [
            "/data/wkf-sample_00001.Ionchamber",
            "/data/wkf-sample_00002.Ionchamber",
        ]
        results = match_ionchamber(data_files, ion_files)
        assert len(results) == 2
        for r in results:
            assert r["matched_ion"] is not None


class TestH5StackSubtraction:
    """Tests for HDF5 multi-frame subtraction."""

    def test_basic_h5_stack(self, tmp_path) -> None:
        """Basic HDF5 stack subtraction with per-frame transmissions."""
        h5_path = str(tmp_path / "test_stack.h5")
        n_frames, h, w = 5, 64, 64

        data = np.ones((n_frames, h, w), dtype=np.float32) * 100
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("data", data=data)

        bg = np.ones((h, w), dtype=np.float32) * 10
        transmissions = np.linspace(0.8, 0.95, n_frames).astype(np.float32)

        result = subtract_h5_stack(h5_path, "data", bg, transmissions=transmissions)

        assert result.shape == (n_frames, h, w)
        assert result.dtype == np.float32

        # Verify first frame: 100/0.8 - 10 = 115
        expected_0 = 100.0 / transmissions[0] - 10.0
        assert np.allclose(result[0], expected_0, atol=0.1)

    def test_h5_stack_no_transmissions(self, tmp_path) -> None:
        """Stack subtraction with T=1.0 for all frames."""
        h5_path = str(tmp_path / "test_stack.h5")
        data = np.ones((3, 32, 32), dtype=np.float32) * 50
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("data", data=data)

        bg = np.ones((32, 32), dtype=np.float32) * 10
        result = subtract_h5_stack(h5_path, "data", bg, transmissions=None)

        assert result.shape == (3, 32, 32)
        assert np.allclose(result, 40.0)

    def test_h5_stack_2d_dataset(self, tmp_path) -> None:
        """2D dataset is treated as single frame."""
        h5_path = str(tmp_path / "test_2d.h5")
        data = np.ones((64, 64), dtype=np.float32) * 80
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("data", data=data)

        bg = np.ones((64, 64), dtype=np.float32) * 20
        result = subtract_h5_stack(h5_path, "data", bg, transmissions=None)

        assert result.shape == (1, 64, 64)
        assert np.allclose(result, 60.0)

    def test_h5_stack_missing_file_raises(self) -> None:
        """Non-existent HDF5 file raises FileNotFoundError."""
        bg = np.ones((10, 10), dtype=np.float32)
        with pytest.raises(FileNotFoundError):
            subtract_h5_stack("/nonexistent/file.h5", "data", bg)

    def test_h5_stack_missing_dataset_raises(self, tmp_path) -> None:
        """Non-existent dataset raises KeyError."""
        h5_path = str(tmp_path / "test.h5")
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("other", data=np.zeros((5, 5)))

        bg = np.ones((5, 5), dtype=np.float32)
        with pytest.raises(KeyError, match="not found"):
            subtract_h5_stack(h5_path, "data", bg)

    def test_h5_stack_transmission_length_mismatch_raises(self, tmp_path) -> None:
        """Mismatched transmissions length raises ValueError."""
        h5_path = str(tmp_path / "test.h5")
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("data", data=np.ones((5, 10, 10), dtype=np.float32))

        bg = np.ones((10, 10), dtype=np.float32)
        wrong_transmissions = np.array([0.9, 0.8], dtype=np.float32)  # length 2, not 5
        with pytest.raises(ValueError, match="transmissions length"):
            subtract_h5_stack(h5_path, "data", bg, transmissions=wrong_transmissions)


class TestFindH5Transmissions:
    """Tests for finding transmissions inside HDF5 files."""

    def test_find_root_dataset(self, tmp_path) -> None:
        """Find transmission as root-level dataset."""
        h5_path = str(tmp_path / "with_trans.h5")
        trans_data = np.array([0.85, 0.90, 0.95], dtype=np.float32)
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("data", data=np.zeros((3, 5, 5)))
            f.create_dataset("transmission", data=trans_data)

        result = find_h5_transmissions(h5_path)
        assert result is not None
        assert np.allclose(result, trans_data)

    def test_find_nested_dataset(self, tmp_path) -> None:
        """Find transmission as nested dataset."""
        h5_path = str(tmp_path / "nested_trans.h5")
        trans_data = np.array([0.80, 0.85], dtype=np.float32)
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("entry/data/data", data=np.zeros((2, 5, 5)))
            f.create_dataset("entry/instrument/transmission", data=trans_data)

        result = find_h5_transmissions(h5_path)
        assert result is not None
        assert np.allclose(result, trans_data)

    def test_find_root_attribute(self, tmp_path) -> None:
        """Find transmission as root attribute."""
        h5_path = str(tmp_path / "attr_trans.h5")
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("data", data=np.zeros((5, 5)))
            f.attrs["transmission"] = 0.88

        result = find_h5_transmissions(h5_path)
        assert result is not None
        assert abs(float(result[0]) - 0.88) < 0.01

    def test_no_transmission_returns_none(self, tmp_path) -> None:
        """File without transmission data returns None."""
        h5_path = str(tmp_path / "no_trans.h5")
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("data", data=np.zeros((5, 5)))

        result = find_h5_transmissions(h5_path)
        assert result is None


# ===========================================================================
# Group C: Memory Usage Tests
# ===========================================================================


class TestMemoryUsage:
    """Verify memory usage stays within bounds for large datasets."""

    def test_large_2d_subtraction(self) -> None:
        """Test subtraction with large 2D arrays (2048x2048)."""
        tracemalloc.start()

        sample = np.random.rand(2048, 2048).astype(np.float32)
        bg = np.random.rand(2048, 2048).astype(np.float32)
        result = subtract_with_reference(sample, bg, transmission=0.85)

        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024
        # 2048x2048 float32 = ~16MB per array, 3 arrays = ~48MB
        # Allow generous headroom for Python overhead
        assert peak_mb < 100, f"Peak memory {peak_mb:.1f}MB exceeds 100MB"
        assert result.shape == (2048, 2048)
        assert result.dtype == np.float32

    def test_h5_stack_memory(self, tmp_path) -> None:
        """Test HDF5 stack subtraction memory (10 frames x 512x512)."""
        h5_path = str(tmp_path / "test_mem.h5")
        n_frames, h, w = 10, 512, 512

        with h5py.File(h5_path, "w") as f:
            f.create_dataset(
                "data",
                data=np.random.rand(n_frames, h, w).astype(np.float32),
            )

        bg = np.random.rand(h, w).astype(np.float32) * 0.1

        tracemalloc.start()
        transmissions = np.linspace(0.8, 0.95, n_frames).astype(np.float32)
        result = subtract_h5_stack(h5_path, "data", bg, transmissions=transmissions)
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024
        # 10x512x512 float32 = ~10MB per copy, should be < 200MB
        assert peak_mb < 200, f"Peak memory {peak_mb:.1f}MB exceeds 200MB"
        assert result.shape == (n_frames, h, w)

    def test_repeated_subtraction_no_leak(self) -> None:
        """Repeated subtractions should not cause memory growth."""
        tracemalloc.start()

        sample = np.random.rand(256, 256).astype(np.float32)
        bg = np.random.rand(256, 256).astype(np.float32)

        # Warm up
        for _ in range(5):
            subtract_with_reference(sample, bg, transmission=0.9)

        snapshot_before = tracemalloc.take_snapshot()
        stats_before = snapshot_before.statistics("lineno")
        size_before = sum(s.size for s in stats_before)

        # Run 50 iterations
        for _ in range(50):
            subtract_with_reference(sample, bg, transmission=0.9)

        snapshot_after = tracemalloc.take_snapshot()
        stats_after = snapshot_after.statistics("lineno")
        size_after = sum(s.size for s in stats_after)
        tracemalloc.stop()

        # Memory growth should be < 5MB (allowing for Python GC noise)
        growth_mb = (size_after - size_before) / 1024 / 1024
        assert growth_mb < 5, f"Memory grew by {growth_mb:.1f}MB over 50 iterations"


# ===========================================================================
# Group D: Error Recovery Tests
# ===========================================================================


class TestErrorRecovery:
    """Test error handling and recovery."""

    def test_corrupt_ionchamber_file(self, tmp_path) -> None:
        """Corrupt ionchamber file returns None gracefully."""
        path = str(tmp_path / "corrupt.Ionchamber")
        Path(path).write_bytes(b"\x00\x01\x02\xff\xfe\xfd\x80\x81")

        result = parse_ionchamber_file(path)
        # Should return None (no valid rows) rather than crash
        assert result is None

    def test_ionchamber_partial_data(self, tmp_path) -> None:
        """Ionchamber file with a bad row among valid rows."""
        path = str(tmp_path / "partial.Ionchamber")
        content = (
            "# Time  Ionchamber0  Ionchamber1  Ionchamber2\n"
            "2026-01-19 12:34:34.130  2.8e-7  2.3e-8  9.7e-10\n"
            "bad line with not enough columns\n"
            "2026-01-19 12:34:36.130  2.9e-7  2.4e-8  9.8e-10\n"
        )
        Path(path).write_text(content, encoding="utf-8")

        df = parse_ionchamber_file(path)
        # Parser catches ValueError at outer level → returns None for whole file
        # because "bad line with not enough columns" has 6 parts but "with" is not float
        assert df is None

    def test_ionchamber_short_rows_skipped(self, tmp_path) -> None:
        """Rows with fewer than 5 columns are silently skipped."""
        path = str(tmp_path / "short.Ionchamber")
        content = (
            "# Time  Ionchamber0  Ionchamber1  Ionchamber2\n"
            "2026-01-19 12:34:34.130  2.8e-7  2.3e-8  9.7e-10\n"
            "short_row\n"
            "2026-01-19 12:34:36.130  2.9e-7  2.4e-8  9.8e-10\n"
        )
        Path(path).write_text(content, encoding="utf-8")

        df = parse_ionchamber_file(path)
        assert df is not None
        assert len(df) == 2

    def test_subtract_with_nan_input(self) -> None:
        """NaN in input produces NaN in output (no crash)."""
        sample = np.ones((10, 10), dtype=np.float32)
        sample[5, 5] = np.nan
        bg = np.ones((10, 10), dtype=np.float32)

        result = subtract_with_reference(sample, bg, transmission=1.0)
        assert np.isnan(result[5, 5])
        assert np.isfinite(result[0, 0])

    def test_subtract_with_inf_input(self) -> None:
        """Inf in input produces Inf in output (no crash)."""
        sample = np.ones((10, 10), dtype=np.float32)
        sample[3, 3] = np.inf
        bg = np.ones((10, 10), dtype=np.float32)

        result = subtract_with_reference(sample, bg, transmission=1.0)
        assert np.isinf(result[3, 3])
        assert np.isfinite(result[0, 0])

    def test_h5_stack_with_zero_transmission_frame(self, tmp_path) -> None:
        """Zero transmission in one frame falls back to T=1.0 (no crash)."""
        h5_path = str(tmp_path / "zero_t.h5")
        data = np.ones((3, 10, 10), dtype=np.float32) * 50
        with h5py.File(h5_path, "w") as f:
            f.create_dataset("data", data=data)

        bg = np.ones((10, 10), dtype=np.float32) * 10
        transmissions = np.array([0.9, 0.0, 0.8], dtype=np.float32)

        # Should not crash; frame 1 uses T=1.0 fallback
        result = subtract_h5_stack(h5_path, "data", bg, transmissions=transmissions)
        assert result.shape == (3, 10, 10)
        # Frame 0: 50/0.9 - 10 ≈ 45.56
        assert abs(result[0, 0, 0] - (50.0 / 0.9 - 10.0)) < 0.1
        # Frame 1: T=0 → fallback to T=1.0: 50/1.0 - 10 = 40
        assert abs(result[1, 0, 0] - 40.0) < 0.1

    def test_mixed_valid_invalid_batch(self, tmp_path, monkeypatch) -> None:
        """Batch with some invalid files still processes valid ones."""
        folder = tmp_path / "mixed"
        folder.mkdir()

        # Create 3 "files" — 2 valid, 1 invalid
        for i in range(3):
            (folder / f"sample_{i:05d}.edf").write_bytes(b"fake")

        bg_file = tmp_path / "bg.edf"
        bg_file.write_bytes(b"fake")

        good_data = np.ones((20, 20), dtype=np.float32) * 100
        bg_data = np.ones((20, 20), dtype=np.float32) * 10

        load_count = 0

        def _fake_load(path: str):
            nonlocal load_count
            load_count += 1
            if "bg" in path:
                return bg_data, None, {}
            # Second sample file fails to load
            if "sample_00001" in path:
                return None, None, {}
            return good_data, None, {}

        monkeypatch.setattr("python.service_launcher.ImageLoader.load", _fake_load)

        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {
                    "action": "batch",
                    "folder_path": str(folder),
                    "bg_path": str(bg_file),
                    "output_dir": str(tmp_path / "out"),
                    "transmission": 1.0,
                },
                _noop_progress,
                asyncio.Event(),
            )
        )

        assert result["status"] == "ok"
        assert result["success_count"] == 2
        assert result["failed_count"] == 1

    def test_batch_empty_folder(self, tmp_path) -> None:
        """Batch on empty folder returns error."""
        folder = tmp_path / "empty_folder"
        folder.mkdir()

        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {
                    "action": "batch",
                    "folder_path": str(folder),
                    "bg_path": str(tmp_path / "bg.edf"),
                    "output_dir": str(tmp_path / "out"),
                    "transmission": 1.0,
                },
                _noop_progress,
                asyncio.Event(),
            )
        )

        assert result["status"] == "error"
        assert "No image files" in result["message"]

    def test_batch_invalid_folder_path(self, tmp_path) -> None:
        """Batch with non-existent folder returns error."""
        from python.service_launcher import handle_bg_subtract

        result = asyncio.run(
            handle_bg_subtract(
                {
                    "action": "batch",
                    "folder_path": str(tmp_path / "nonexistent"),
                    "bg_path": str(tmp_path / "bg.edf"),
                    "output_dir": str(tmp_path / "out"),
                    "transmission": 1.0,
                },
                _noop_progress,
                asyncio.Event(),
            )
        )

        assert result["status"] == "error"
        assert "Invalid folder" in result["message"]
