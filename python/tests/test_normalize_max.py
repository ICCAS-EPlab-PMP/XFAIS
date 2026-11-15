#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_normalize_max.py — Max-intensity normalization tests
test_normalize_max.py — 最大强度归一化测试

Covers:
  A. Core helpers `_normalize_max_1d` / `_normalize_max_2d` (pure NumPy).
  B. Handler wiring: handle_integrate1d (serial + parallel batch) with
     monkeypatched geometry/loader — per-group max → 100 when the option is
     ON, byte-identical behavior when OFF, and skipped groups (non-positive
     max) reported in ``normalize_warnings`` without NaN.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# service_launcher.py runs with the python/ directory on sys.path (it imports
# `services.*` directly), so import the helpers the same way.
# service_launcher.py 运行时 python/ 目录在 sys.path 上（直接 import services.*），
# 因此按同样方式导入辅助函数。
_PYTHON_DIR = str(Path(__file__).resolve().parent.parent)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

import numpy as np
import pytest

import service_launcher
from service_launcher import _normalize_max_1d, _normalize_max_2d


async def _noop_progress(_progress: float, _message: str) -> None:
    """No-op progress callback."""


# ===========================================================================
# A. Core helpers / 核心辅助函数
# ===========================================================================


class TestNormalizeMax1D:
    def test_scales_max_to_100(self):
        values = [1.0, 2.0, 4.0, 10.0]
        out, applied = _normalize_max_1d(values)
        assert applied is True
        assert out == pytest.approx([10.0, 20.0, 40.0, 100.0])

    def test_relative_ratios_preserved(self):
        rng = np.random.default_rng(42)
        arr = rng.uniform(0.5, 1000.0, size=500)
        out, applied = _normalize_max_1d(arr.tolist())
        assert applied is True
        src = np.asarray(arr)
        dst = np.asarray(out)
        np.testing.assert_allclose(dst / dst.max(), src / src.max(), rtol=1e-12)
        assert dst.max() == pytest.approx(100.0)

    def test_all_zero_skipped(self):
        values = [0.0, 0.0, 0.0]
        out, applied = _normalize_max_1d(values)
        assert applied is False
        assert out == values

    def test_negative_only_skipped(self):
        values = [-5.0, -1.0, -3.0]
        out, applied = _normalize_max_1d(values)
        assert applied is False
        assert out == values

    def test_nan_and_inf_do_not_break_max(self):
        values = [float("nan"), 2.0, float("inf"), 8.0]
        out, applied = _normalize_max_1d(values)
        assert applied is True
        # Finite max (8.0) drives the scale; non-finite entries stay non-finite
        # but must not crash or poison the finite part.
        # 有限最大值（8.0）决定缩放；非有限项保持非有限但不崩溃、不污染有限部分。
        assert out[1] == pytest.approx(25.0)
        assert out[3] == pytest.approx(100.0)
        assert np.isnan(out[0]) and np.isinf(out[2])

    def test_all_nan_skipped(self):
        values = [float("nan"), float("nan")]
        out, applied = _normalize_max_1d(values)
        assert applied is False
        assert out == values

    def test_empty_skipped(self):
        out, applied = _normalize_max_1d([])
        assert applied is False
        assert out == []


class TestNormalizeMax2D:
    def test_scales_max_to_100(self):
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        out, applied = _normalize_max_2d(arr)
        assert applied is True
        np.testing.assert_allclose(out, [[25.0, 50.0], [75.0, 100.0]])

    def test_all_zero_skipped(self):
        arr = np.zeros((3, 3))
        out, applied = _normalize_max_2d(arr)
        assert applied is False
        np.testing.assert_array_equal(out, arr)

    def test_nan_only_skipped(self):
        arr = np.full((2, 2), np.nan)
        out, applied = _normalize_max_2d(arr)
        assert applied is False
        np.testing.assert_array_equal(out, arr)

    def test_input_not_mutated(self):
        arr = np.array([[1.0, 2.0], [3.0, 4.0]])
        before = arr.copy()
        _normalize_max_2d(arr)
        np.testing.assert_array_equal(arr, before)


# ===========================================================================
# B. handle_integrate1d wiring / 处理函数接线
# ===========================================================================


class _FakeIntegrateResult:
    """Minimal stand-in for a pyFAI integrate1d_ng result."""

    def __init__(self, intensity: np.ndarray):
        self.radial = np.linspace(0.0, 10.0, len(intensity))
        self.intensity = intensity
        self.count = np.ones(len(intensity))


class _FakeAI:
    """Fake AzimuthalIntegrator: intensity = first n samples of the image."""

    def __init__(self, npt: int = 16):
        self.npt = npt

    def integrate1d_ng(self, **kwargs):
        data = np.asarray(kwargs["data"], dtype=float).ravel()
        vals = np.pad(data, (0, max(0, self.npt - len(data))))[: self.npt]
        return _FakeIntegrateResult(vals)

    def clone(self):  # used by the parallel batch path
        return self


def _install_fakes(monkeypatch: pytest.MonkeyPatch, scale_by_file: dict[str, float]):
    """Patch geometry + image loading so handle_integrate1d runs offline."""
    def fake_from_poni_path(_poni):
        return _FakeAI(), 4.0, 4.0

    def fake_load(fpath, *_args, **_kwargs):
        scale = scale_by_file.get(Path(fpath).name, 1.0)
        data = np.full((8, 8), scale, dtype=np.float32)
        meta = {"filename": Path(fpath).name}
        return data, None, meta

    monkeypatch.setattr(
        service_launcher.IntegratorFactory, "from_poni_path",
        staticmethod(fake_from_poni_path),
    )
    monkeypatch.setattr(service_launcher.ImageLoader, "load", fake_load)


def _payload(files: list[str], normalize: bool, parallel: bool = False):
    return {
        "geometry": {"poni_path": "fake.poni"},
        "files": files,
        "parallel": parallel,
        "options": {"npt": 16, "drop_empty_bins": True, "normalize_max": normalize},
    }


class TestHandleIntegrate1DNormalization:
    def test_off_keeps_raw_intensities(self, monkeypatch: pytest.MonkeyPatch):
        _install_fakes(monkeypatch, {"a.tif": 1000.0, "b.tif": 5.0})
        res = asyncio.run(service_launcher.handle_integrate1d(
            _payload(["a.tif", "b.tif"], normalize=False),
            _noop_progress, asyncio.Event(),
        ))
        assert res["status"] == "ok"
        assert "normalized" not in res
        maxima = [max(r["intensity"]) for r in res["results"]]
        assert maxima == pytest.approx([1000.0, 5.0])

    def test_on_scales_each_group_to_100(self, monkeypatch: pytest.MonkeyPatch):
        _install_fakes(monkeypatch, {"a.tif": 1000.0, "b.tif": 5.0})
        res = asyncio.run(service_launcher.handle_integrate1d(
            _payload(["a.tif", "b.tif"], normalize=True),
            _noop_progress, asyncio.Event(),
        ))
        assert res["status"] == "ok"
        assert res["normalized"] is True
        maxima = [max(r["intensity"]) for r in res["results"]]
        assert maxima == pytest.approx([100.0, 100.0])
        assert res["normalize_warnings"] == []

    def test_zero_group_skipped_with_warning(self, monkeypatch: pytest.MonkeyPatch):
        _install_fakes(monkeypatch, {"a.tif": 1000.0, "zero.tif": 0.0})
        res = asyncio.run(service_launcher.handle_integrate1d(
            _payload(["a.tif", "zero.tif"], normalize=True),
            _noop_progress, asyncio.Event(),
        ))
        assert res["status"] == "ok"
        assert res["normalized"] is True
        by_name = {r["filename"]: r for r in res["results"]}
        assert max(by_name["a.tif"]["intensity"]) == pytest.approx(100.0)
        # The zero group is reported and kept unchanged — no NaN.
        # 全零组被上报并保持原值——不产生 NaN。
        assert max(by_name["zero.tif"]["intensity"]) == pytest.approx(0.0)
        assert res["normalize_warnings"] == ["zero.tif"]

    def test_parallel_batch_normalizes_too(self, monkeypatch: pytest.MonkeyPatch):
        _install_fakes(monkeypatch, {"a.tif": 1000.0, "b.tif": 5.0})
        res = asyncio.run(service_launcher.handle_integrate1d(
            _payload(["a.tif", "b.tif"], normalize=True, parallel=True),
            _noop_progress, asyncio.Event(),
        ))
        assert res["status"] == "ok"
        assert res["normalized"] is True
        maxima = sorted(max(r["intensity"]) for r in res["results"])
        assert maxima == pytest.approx([100.0, 100.0])
