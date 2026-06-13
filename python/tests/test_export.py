#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_export.py — Tests for ExportHelper."""

import h5py
import io
import numpy as np
import pytest
from python.services.export_helper import ExportHelper, IntegrationResult


class TestToTxt:
    def test_single_result(self, sample_1d_result):
        txt = ExportHelper.to_txt([sample_1d_result], "q (nm⁻¹)")
        assert "X_value" in txt
        assert "test_file" in txt
        lines = txt.strip().split("\n")
        assert len(lines) == 52  # header + col header + 50 data rows

    def test_multiple_results(self, sample_1d_result):
        r2 = IntegrationResult(
            radial=sample_1d_result.radial,
            intensity=np.random.rand(50).astype(np.float32) * 500,
            label="file2", source_filename="file2.edf", unit="q_nm^-1",
        )
        txt = ExportHelper.to_txt([sample_1d_result, r2], "q (nm⁻¹)")
        lines = txt.strip().split("\n")
        cols = lines[2].split("\t")
        assert len(cols) == 3


class TestToHdf5Bytes:
    def test_1d_roundtrip(self, sample_1d_result):
        h5_bytes = ExportHelper.to_hdf5_bytes([sample_1d_result], "q (nm⁻¹)")
        buf = io.BytesIO(h5_bytes)
        with h5py.File(buf, "r") as f:
            assert "metadata" in f
            assert "results" in f
            grp = f["results/file_0000"]
            assert grp["radial"][()].shape == (50,)
            assert grp["intensity"][()].shape == (50,)
            assert grp.attrs["unit"] == "q_nm^-1"

    def test_2d_roundtrip(self, sample_2d):
        axis_ip = np.linspace(-10, 10, 50)
        axis_oop = np.linspace(-10, 10, 50)
        intensity = np.random.rand(50, 50).astype(np.float32)
        h5_bytes = ExportHelper.to_hdf5_2d_bytes(intensity, axis_ip, axis_oop)
        buf = io.BytesIO(h5_bytes)
        with h5py.File(buf, "r") as f:
            assert f["intensity"][()].shape == (50, 50)
            assert f["axis_ip"][()].shape == (50,)
            assert f["axis_oop"][()].shape == (50,)


class TestToImageBytes:
    def test_tiff(self, sample_2d):
        tiff_bytes = ExportHelper.to_image_bytes(sample_2d, "tiff")
        assert len(tiff_bytes) > 0
        assert tiff_bytes[:2] in (b"II", b"MM")

    def test_edf(self, sample_2d):
        edf_bytes = ExportHelper.to_image_bytes(sample_2d, "edf")
        assert len(edf_bytes) > 0


class TestToNpyDict:
    def test_roundtrip(self, sample_2d):
        axis_ip = np.linspace(-10, 10, 50)
        axis_oop = np.linspace(-10, 10, 50)
        npy_bytes = ExportHelper.to_npy_dict(sample_2d, axis_ip, axis_oop)
        buf = io.BytesIO(npy_bytes)
        d = np.load(buf, allow_pickle=True).item()
        assert "intensity" in d
        assert "qip" in d
        assert "qoop" in d
        assert "info" in d
