#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_drop_empty_bins.py — Tests for _drop_empty_bins (pyFAI empty-bin removal)
test_drop_empty_bins.py — _drop_empty_bins（剔除 pyFAI 空 bin）测试
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from python.service_launcher import _drop_empty_bins


@dataclass
class _StubResult:
    """Minimal stand-in for pyFAI's Integrate1dResult (radial/intensity/count)."""

    radial: np.ndarray
    intensity: np.ndarray
    count: Optional[np.ndarray]


def test_drops_only_zero_count_bins_keeps_real_zeros() -> None:
    """仅剔除 count==0 的 bin；真实零信号（count>0）必须保留。

    Only fully-masked bins (count==0) are removed; a real zero-signal bin
    (count>0) is preserved — this is the correctness crux vs. filtering on intensity==0.
    """
    res = _StubResult(
        radial=np.array([0.0, 1.0, 2.0, 3.0]),
        intensity=np.array([10.0, 0.0, 30.0, 0.0]),  # bin 1 masked→0; bin 3 real→0
        count=np.array([5, 0, 7, 3]),  # bin 1 empty; bin 3 has 3 valid pixels
    )
    radial, intensity = _drop_empty_bins(res, drop=True)

    # bin 1 dropped; bin 3 (real zero, count>0) kept
    assert radial == [0.0, 2.0, 3.0]
    assert intensity == [10.0, 30.0, 0.0]
    # returned as plain Python lists
    assert isinstance(radial, list) and isinstance(intensity, list)


def test_disabled_returns_all_points() -> None:
    """drop=False 时原样返回全部点 / disabled returns all points unchanged."""
    res = _StubResult(
        radial=np.array([0.0, 1.0, 2.0]),
        intensity=np.array([10.0, 0.0, 30.0]),
        count=np.array([5, 0, 7]),
    )
    radial, intensity = _drop_empty_bins(res, drop=False)

    assert radial == [0.0, 1.0, 2.0]
    assert intensity == [10.0, 0.0, 30.0]


def test_count_none_falls_back_to_all() -> None:
    """count 不可用时安全降级：原样返回 / missing count degrades to returning all."""
    res = _StubResult(
        radial=np.array([0.0, 1.0, 2.0]),
        intensity=np.array([10.0, 0.0, 30.0]),
        count=None,
    )
    radial, intensity = _drop_empty_bins(res, drop=True)

    assert radial == [0.0, 1.0, 2.0]
    assert intensity == [10.0, 0.0, 30.0]


def test_all_bins_empty_returns_empty() -> None:
    """全部 bin 都空时返回空数组 / fully-masked curve yields empty arrays."""
    res = _StubResult(
        radial=np.array([0.0, 1.0, 2.0]),
        intensity=np.array([0.0, 0.0, 0.0]),
        count=np.array([0, 0, 0]),
    )
    radial, intensity = _drop_empty_bins(res, drop=True)

    assert radial == []
    assert intensity == []


def test_no_empty_bins_keeps_all() -> None:
    """无空 bin 时回归：全部保留（不误伤正常数据）/ regression: no empty bins kept as-is."""
    res = _StubResult(
        radial=np.array([0.0, 1.0, 2.0]),
        intensity=np.array([10.0, 20.0, 30.0]),
        count=np.array([5, 7, 9]),
    )
    radial, intensity = _drop_empty_bins(res, drop=True)

    assert radial == [0.0, 1.0, 2.0]
    assert intensity == [10.0, 20.0, 30.0]
