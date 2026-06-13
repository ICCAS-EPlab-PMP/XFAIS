#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_h5_extractor.py — Tests for H5Extractor."""

import h5py
import os
import numpy as np
import pytest
from pathlib import Path
from python.services.h5_extractor import H5Extractor


def _create_h5_tree(base: str):
    sub1 = os.path.join(base, "scan1")
    sub2 = os.path.join(base, "scan2")
    os.makedirs(sub1, exist_ok=True)
    os.makedirs(sub2, exist_ok=True)
    for path in [
        os.path.join(sub1, "data_master.h5"),
        os.path.join(sub1, "data_00001.h5"),
        os.path.join(sub2, "data_master.h5"),
        os.path.join(sub2, "other.h5"),
    ]:
        with h5py.File(path, "w") as f:
            f.create_dataset("data", data=np.zeros((2, 2), dtype=np.float32))


class TestH5Extractor:
    def test_find_all_files(self, tmp_path):
        root = str(tmp_path / "source")
        _create_h5_tree(root)
        ext = H5Extractor(root, "/dev/null")
        files = ext.find_h5_files(recursive=True)
        assert len(files) == 4

    def test_filter_by_suffix(self, tmp_path):
        root = str(tmp_path / "source")
        _create_h5_tree(root)
        ext = H5Extractor(root, "/dev/null", suffix_filter="_master")
        all_files = ext.find_h5_files(recursive=True)
        filtered = ext.filter_files(all_files)
        assert len(filtered) == 2
        for f in filtered:
            assert "_master.h5" in f.lower()

    def test_extract_with_prepend(self, tmp_path):
        root = str(tmp_path / "source")
        out = str(tmp_path / "output")
        _create_h5_tree(root)
        ext = H5Extractor(root, out, suffix_filter="_master", prepend_folder=True)
        stats = ext.extract()
        assert stats["success_count"] == 2
        assert stats["errors"] == 0
        assert os.path.exists(os.path.join(out, "scan1_data_master.h5"))
        assert os.path.exists(os.path.join(out, "scan2_data_master.h5"))

    def test_extract_no_prepend(self, tmp_path):
        root = str(tmp_path / "source")
        out = str(tmp_path / "output")
        _create_h5_tree(root)
        ext = H5Extractor(root, out, suffix_filter="_master", prepend_folder=False)
        stats = ext.extract()
        assert stats["success_count"] == 2
        assert os.path.exists(os.path.join(out, "data_master.h5"))

    def test_extract_no_filter(self, tmp_path):
        root = str(tmp_path / "source")
        out = str(tmp_path / "output")
        _create_h5_tree(root)
        ext = H5Extractor(root, out, suffix_filter="", prepend_folder=True)
        stats = ext.extract()
        assert stats["success_count"] == 4

    def test_extract_empty_source(self, tmp_path):
        root = str(tmp_path / "empty")
        out = str(tmp_path / "output")
        os.makedirs(root)
        ext = H5Extractor(root, out)
        stats = ext.extract()
        assert stats["success_count"] == 0
        assert stats["total_files"] == 0
