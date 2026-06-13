#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_integrator.py — Tests for IntegratorFactory."""

import pytest
from python.services.integrator import IntegratorFactory


class TestFromPoniPath:
    def test_load_valid_poni(self, poni_path):
        ai, cx, cy = IntegratorFactory.from_poni_path(poni_path)
        assert ai is not None
        assert cx > 0
        assert cy > 0
        assert ai.wavelength > 0
        assert ai.dist > 0

    def test_load_invalid_path(self):
        with pytest.raises(ValueError):
            IntegratorFactory.from_poni_path("/nonexistent/file.poni")

    def test_center_pixel_values(self, poni_path):
        ai, cx, cy = IntegratorFactory.from_poni_path(poni_path)
        expected_cx = ai.poni2 / ai.pixel2
        expected_cy = ai.poni1 / ai.pixel1
        assert abs(cx - expected_cx) < 0.01
        assert abs(cy - expected_cy) < 0.01


class TestFromPoniBytes:
    def test_from_bytes(self, poni_path):
        with open(poni_path, "rb") as f:
            poni_bytes = f.read()
        ai, cx, cy = IntegratorFactory.from_poni_bytes(poni_bytes)
        assert ai is not None

    def test_from_invalid_bytes(self):
        with pytest.raises(ValueError):
            IntegratorFactory.from_poni_bytes(b"not a poni file")


class TestFromManualParams:
    def test_basic_creation(self):
        ai, cx, cy = IntegratorFactory.from_manual_params(
            pixel_size_um=172.0, dist_mm=200.0, wavelength_A=1.5418,
            center_x_px=512.0, center_y_px=512.0,
        )
        assert ai is not None
        assert cx == 512.0
        assert cy == 512.0
        assert abs(ai.dist - 0.2) < 1e-6
        assert abs(ai.wavelength - 1.5418e-10) < 1e-15

    def test_with_rotations(self):
        ai, cx, cy = IntegratorFactory.from_manual_params(
            pixel_size_um=172.0, dist_mm=200.0, wavelength_A=1.0,
            center_x_px=100.0, center_y_px=100.0,
            rot1_deg=10.0, rot2_deg=5.0, rot3_deg=3.0,
        )
        assert ai is not None
