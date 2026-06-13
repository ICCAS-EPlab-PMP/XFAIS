#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_pnggenerate.py — Tests for PNGGenerator and helpers."""

import os
import numpy as np
import pytest
from pathlib import Path
from PIL import Image
from python.services.pnggenerate import PNGGenerator, _save_png, _apply_overflow, find_all_files


class TestSavePng:
    def test_basic_linear(self, tmp_path, sample_2d):
        path = str(tmp_path / "test.png")
        _save_png(sample_2d, path, "viridis", use_log=False, dpi=100)
        assert os.path.exists(path)
        img = Image.open(path)
        assert img.size[0] == 10
        assert img.size[1] == 10

    def test_log_scale(self, tmp_path, sample_2d):
        path = str(tmp_path / "test_log.png")
        _save_png(sample_2d, path, "viridis", use_log=True)
        assert os.path.exists(path)

    def test_manual_clim(self, tmp_path, sample_2d):
        path = str(tmp_path / "test_clim.png")
        _save_png(sample_2d, path, "viridis", use_log=False, clim=(10.0, 90.0))
        assert os.path.exists(path)

    def test_custom_dpi(self, tmp_path, sample_2d):
        path = str(tmp_path / "test_dpi.png")
        _save_png(sample_2d, path, "viridis", use_log=False, dpi=200)
        assert os.path.exists(path)
        img = Image.open(path)
        assert img.size[0] == 20
        assert img.size[1] == 20

    def test_all_zeros(self, tmp_path):
        path = str(tmp_path / "zeros.png")
        _save_png(np.zeros((5, 5), dtype=np.float32), path, "viridis")
        assert os.path.exists(path)


class TestFindAllFiles:
    def test_mixed_types(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "a.h5").write_bytes(b"dummy")
        (src / "b.tif").write_bytes(b"dummy")
        (src / "c.edf").write_bytes(b"dummy")
        (src / "d.txt").write_bytes(b"dummy")
        result = find_all_files(str(src), recursive=False)
        assert len(result["h5"]) == 1
        assert len(result["tiff"]) == 1
        assert len(result["edf"]) == 1


class TestPNGGenerator:
    def test_default_template(self):
        tmpl = PNGGenerator.default_template()
        assert "colormap" in tmpl
        assert tmpl["dpi"] == 300

    def test_generate_from_edf(self, tmp_path, edf_path):
        src = str(tmp_path / "source")
        out = str(tmp_path / "output")
        os.makedirs(src)
        import shutil
        shutil.copy2(edf_path, os.path.join(src, "test.edf"))

        gen = PNGGenerator(src, out, recursive=False)
        stats = gen.generate()
        assert stats["images_generated"] >= 1
        assert stats["errors"] == 0

        png_files = list(Path(out).glob("*.png"))
        assert len(png_files) >= 1
