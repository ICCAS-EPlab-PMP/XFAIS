#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""conftest.py — Shared test fixtures and paths."""

import os
from pathlib import Path

import h5py
import numpy as np
import pytest

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "test-fixtures"

EDF_PATH = FIXTURES_DIR / "test.edf"
H5_PATH = FIXTURES_DIR / "test.h5"
PONI_PATH = FIXTURES_DIR / "test.poni"
VIEWER_MULTIFRAME_H5_PATH = FIXTURES_DIR / "viewer-multiframe.h5"


@pytest.fixture
def fixtures_dir():
    return FIXTURES_DIR


@pytest.fixture
def edf_path():
    return str(EDF_PATH)


@pytest.fixture
def h5_path():
    return str(H5_PATH)


@pytest.fixture
def poni_path():
    return str(PONI_PATH)


@pytest.fixture
def viewer_multiframe_h5_path():
    return str(VIEWER_MULTIFRAME_H5_PATH)


@pytest.fixture
def sample_2d():
    return np.random.rand(10, 10).astype(np.float32) * 100


@pytest.fixture
def sample_1d_result():
    from python.services.export_helper import IntegrationResult
    return IntegrationResult(
        radial=np.linspace(0.1, 5.0, 50),
        intensity=np.random.rand(50).astype(np.float32) * 1000,
        label="test_file",
        source_filename="test.edf",
        unit="q_nm^-1",
    )


@pytest.fixture
def tmp_output_dir(tmp_path):
    return str(tmp_path / "output")


@pytest.fixture
def h5_with_4d(tmp_path):
    """Create a small 4D HDF5 test file."""
    path = str(tmp_path / "test_4d.h5")
    with h5py.File(path, "w") as f:
        data = np.random.rand(2, 3, 5, 5).astype(np.uint32)
        f.create_dataset("data", data=data)
    return path
