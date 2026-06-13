#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_image_loader.py — Tests for H5Handler and ImageLoader."""

import h5py
import numpy as np
import pytest
from python.services.image_loader import H5Handler, ImageLoader, EIGER_4D_CHANNELS


class TestH5Handler:
    def test_find_datasets(self, h5_path):
        info = H5Handler.find_datasets(h5_path)
        assert "data" in info
        ds = info["data"]
        assert ds["shape"] == (10, 10)
        assert ds["ndim"] == 2
        assert ds["is_image"] is True

    def test_find_datasets_missing_file(self):
        with pytest.raises(IOError):
            H5Handler.find_datasets("/nonexistent/file.h5")

    def test_pick_default_dataset(self):
        assert H5Handler.pick_default_dataset([]) is None
        assert H5Handler.pick_default_dataset(["entry/data"]) == "entry/data"
        assert H5Handler.pick_default_dataset(["a/data", "b/data"]) == "a/data"

    def test_load_2d_array(self, h5_path):
        arr, dead = H5Handler.load_2d_array(h5_path, "data")
        assert arr.shape == (10, 10)
        assert arr.dtype == np.float32

    def test_load_2d_array_missing_ds(self, h5_path):
        with pytest.raises(KeyError):
            H5Handler.load_2d_array(h5_path, "nonexistent")

    def test_load_all_frames(self, h5_path):
        frames = H5Handler.load_all_frames(h5_path, "data")
        assert len(frames) == 1
        arr, dead = frames[0]
        assert arr.shape == (10, 10)

    def test_load_4d(self, h5_with_4d):
        info = H5Handler.find_datasets(h5_with_4d)
        assert "data" in info
        assert info["data"]["ndim"] == 4
        assert info["data"]["n_channels"] == 3

        arr, dead = H5Handler.load_2d_array(h5_with_4d, "data", channel="0")
        assert arr.shape == (5, 5)

        frames = H5Handler.load_all_frames(h5_with_4d, "data", channel="0")
        assert len(frames) == 2


class TestImageLoader:
    def test_load_edf(self, edf_path):
        data, dead_mask, meta = ImageLoader.load(edf_path)
        assert data is not None
        assert data.shape == (10, 10)
        assert data.dtype == np.float32
        assert dead_mask is None
        assert meta["ext"] == ".edf"

    def test_load_h5(self, h5_path):
        data, dead_mask, meta = ImageLoader.load(h5_path, h5_dataset_path="data")
        assert data is not None
        assert data.shape == (10, 10)
        assert "h5_dataset" in meta

    def test_load_h5_no_dataset(self, h5_path):
        data, dead_mask, meta = ImageLoader.load(h5_path)
        assert data is None

    def test_load_missing_file(self):
        with pytest.raises(IOError):
            ImageLoader.load("/nonexistent/file.edf")

    def test_load_from_bytes(self, edf_path):
        with open(edf_path, "rb") as f:
            file_bytes = f.read()
        data, dead_mask, meta = ImageLoader.load_from_bytes(file_bytes, "test.edf")
        assert data is not None
        assert data.shape == (10, 10)

    def test_load_all_frames_edf(self, edf_path):
        results = ImageLoader.load_all_frames(edf_path)
        assert len(results) == 1
        data, _, meta = results[0]
        assert data.shape == (10, 10)
        assert meta["n_frames"] == 1
