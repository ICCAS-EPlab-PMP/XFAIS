#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_poni_match.py — Tests for the detector auto-match feature.

Covers `match_detector_by_shape` (the function backing the poni_importer
`match_detector` action), including the 4D-shape edge case where only the
last two axes are image dimensions.
"""

import pytest

from python.services import poni_importer as pi


def setup_function(_function):
    """Reset the detector instance cache between tests for isolation."""
    pi.reset_detector_instance_cache()
    pi.reset_pyfai_detector_registry_cache()


def test_match_known_pilatus1m_shape():
    """Pilatus1M's MAX_SHAPE is (1043, 981) — should match exactly."""
    result = pi.match_detector_by_shape([1043, 981])
    assert result is not None
    assert result["name"] == "Pilatus1M"
    assert result["pixel1_m"] == pytest.approx(172e-6, rel=1e-3)
    assert result["pixel2_m"] == pytest.approx(172e-6, rel=1e-3)
    assert result["max_shape"] == [1043, 981]


def test_match_eiger2_1m_shape():
    """Eiger2 1M's MAX_SHAPE is (1062, 1028)."""
    result = pi.match_detector_by_shape([1062, 1028])
    assert result is not None
    assert result["name"] == "Eiger2_1M"
    assert result["pixel1_m"] == pytest.approx(75e-6, rel=1e-3)


def test_match_unrecognized_shape_returns_none():
    """An arbitrary shape not in the registry returns None (→ custom mode)."""
    assert pi.match_detector_by_shape([999, 999]) is None
    assert pi.match_detector_by_shape([1, 1]) is None


def test_match_4d_shape_uses_last_two_axes():
    """4D shape (frames × channels × rows × cols): only last two are used."""
    result = pi.match_detector_by_shape([10, 2, 1043, 981])
    assert result is not None
    assert result["name"] == "Pilatus1M"
    assert result["max_shape"] == [1043, 981]


def test_match_invalid_shape_returns_none():
    """Garbage input gracefully returns None rather than raising."""
    assert pi.match_detector_by_shape(None) is None
    assert pi.match_detector_by_shape([]) is None
    assert pi.match_detector_by_shape([5]) is None
    assert pi.match_detector_by_shape([0, 0]) is None
    assert pi.match_detector_by_shape(["a", "b"]) is None


def test_match_returns_consistent_pixel_sizes():
    """pixel1_m and pixel2_m are floats (or None), not strings."""
    result = pi.match_detector_by_shape([1043, 981])
    assert result is not None
    assert isinstance(result["pixel1_m"], float)
    assert isinstance(result["pixel2_m"], float)
    assert result["pixel1_m"] > 0
