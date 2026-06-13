#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_h5convert.py — Tests for H5Converter."""

import h5py
import os
import numpy as np
import pytest
from pathlib import Path
from python.services.h5convert import H5Converter, save_tiff, _apply_overflow


class TestHelperFunctions:
    def test_apply_overflow(self):
        arr = np.array([1.0, 5e9, 100.0], dtype=np.float32)
        result = _apply_overflow(arr)
        assert result[0] == 1.0
        assert result[1] == -1.0
        assert result[2] == 100.0

    def test_save_tiff(self, tmp_path, sample_2d):
        path = str(tmp_path / "test.tif")
        save_tiff(sample_2d, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0


class TestH5Converter:
    def _create_test_h5(self, path: str):
        with h5py.File(path, "w") as f:
            f.create_dataset("data", data=np.random.rand(5, 5).astype(np.float32))
            f.create_dataset("metadata/scan", data=np.array([1.0, 2.0, 3.0]))

    def test_scan_and_convert(self, tmp_path):
        root = str(tmp_path / "source")
        out = str(tmp_path / "output")
        os.makedirs(root)

        self._create_test_h5(os.path.join(root, "test_master.h5"))

        converter = H5Converter(root, out, master_suffix="_master")
        files = converter.scan()
        assert len(files) == 1

        ds = converter.inspect_datasets()
        assert "data" in ds
        assert "metadata/scan" in ds

        stats = converter.convert()
        assert stats["files_processed"] == 1
        assert stats["images_exported"] >= 1

    def test_no_datasets_selected(self, tmp_path):
        root = str(tmp_path / "source")
        out = str(tmp_path / "output")
        os.makedirs(root)
        self._create_test_h5(os.path.join(root, "test_master.h5"))

        converter = H5Converter(root, out)
        converter.scan()
        converter.inspect_datasets()
        for k in converter._ds_cfg:
            converter._ds_cfg[k]["export"] = False
        with pytest.raises(ValueError):
            converter.convert()
