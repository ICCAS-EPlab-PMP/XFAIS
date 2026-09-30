#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_h5convert.py — Tests for H5Converter."""

import h5py
import os
import numpy as np
import pytest
from pathlib import Path
from python.services.h5convert import (
    H5Converter,
    save_tiff,
    _apply_overflow,
    is_h5_file,
    is_master_file,
    matches_suffix_filter,
    scan_h5_files,
)
from python.service_launcher import handle_h5convert_scan


async def _noop_progress(_progress: float, _message: str) -> None:
    """空进度回调 / No-op progress callback."""


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


class TestExtensionSupport:
    """Nexus (.nxs) and .hdf5 are HDF5 containers and must be recognized.
    Nexus（.nxs）与 .hdf5 本质是 HDF5 容器，必须被识别。"""

    def _create_h5(self, path: str):
        with h5py.File(path, "w") as f:
            f.create_dataset("data", data=np.random.rand(5, 5).astype(np.float32))

    def test_is_h5_file(self):
        assert is_h5_file("a.h5")
        assert is_h5_file("a.NXS")
        assert is_h5_file("a.hdf5")
        assert not is_h5_file("a.tif")
        assert not is_h5_file("a.h5.txt")

    def test_is_master_file(self):
        assert is_master_file("x_master.nxs", "_master")
        assert is_master_file("x_master.hdf5", "_master")
        assert is_master_file("x_master.h5", "_master")
        assert not is_master_file("x_0001.nxs", "_master")
        assert not is_master_file("x_master.tif", "_master")

    def test_matches_suffix_filter(self):
        assert matches_suffix_filter("x_master.nxs", "_master")
        assert matches_suffix_filter("x_master.h5", "_master.h5")
        assert not matches_suffix_filter("x_0001.h5", "_master")
        assert matches_suffix_filter("anything.h5", "")

    def test_scan_h5_files_finds_nexus(self, tmp_path):
        root = str(tmp_path / "src")
        os.makedirs(root)
        self._create_h5(os.path.join(root, "a_master.nxs"))
        self._create_h5(os.path.join(root, "b.hdf5"))
        self._create_h5(os.path.join(root, "c.h5"))
        (tmp_path / "src" / "ignored.tif").write_bytes(b"x")
        found = scan_h5_files(root)
        names = sorted(os.path.basename(f) for f in found)
        assert names == ["a_master.nxs", "b.hdf5", "c.h5"]

    def test_scan_non_recursive(self, tmp_path):
        root = str(tmp_path / "src")
        sub = os.path.join(root, "sub")
        os.makedirs(sub)
        self._create_h5(os.path.join(root, "top.nxs"))
        self._create_h5(os.path.join(sub, "nested.h5"))
        found = scan_h5_files(root, recursive=False)
        assert [os.path.basename(f) for f in found] == ["top.nxs"]


class TestNamingModes:
    """Output first-level folder naming: parent folder (default) / source file
    stem / legacy dataset-path layout.
    输出第一层文件夹命名：源文件所在文件夹（默认）/ 源文件名 / 旧版数据集路径。"""

    def _prepare(self, tmp_path):
        root = str(tmp_path / "批次2024")
        out = str(tmp_path / "output")
        os.makedirs(root)
        with h5py.File(os.path.join(root, "sample_master.h5"), "w") as f:
            f.create_dataset("data", data=np.random.rand(5, 5).astype(np.float32))
        return root, out

    def _convert(self, root: str, out: str, naming_mode: str):
        converter = H5Converter(root, out, master_suffix="_master", naming_mode=naming_mode)
        converter.scan()
        converter.inspect_datasets()
        stats = converter.convert()
        assert stats["files_processed"] == 1
        assert stats["images_exported"] == 1

    def test_default_and_parent_folder_mode(self, tmp_path):
        root, out = self._prepare(tmp_path)
        self._convert(root, out, "parent_folder")
        # Default naming_mode is parent_folder / 默认即按源文件所在文件夹
        assert os.path.exists(os.path.join(out, "批次2024", "data", "sample_master.tif"))

    def test_file_name_mode(self, tmp_path):
        root, out = self._prepare(tmp_path)
        self._convert(root, out, "file_name")
        assert os.path.exists(os.path.join(out, "sample_master", "data", "sample_master.tif"))

    def test_dataset_mode_legacy(self, tmp_path):
        root, out = self._prepare(tmp_path)
        self._convert(root, out, "dataset")
        assert os.path.exists(os.path.join(out, "data", "sample_master.tif"))

    def test_invalid_mode_falls_back(self, tmp_path):
        root, out = self._prepare(tmp_path)
        converter = H5Converter(root, out, master_suffix="_master", naming_mode="bogus")
        assert converter.naming_mode == "parent_folder"

    def test_nxs_master_and_convert(self, tmp_path):
        root = str(tmp_path / "src")
        out = str(tmp_path / "output")
        os.makedirs(root)
        with h5py.File(os.path.join(root, "run_master.nxs"), "w") as f:
            f.create_dataset("data", data=np.random.rand(5, 5).astype(np.float32))

        converter = H5Converter(root, out, master_suffix="_master")
        files = converter.scan()
        assert len(files) == 1
        ds = converter.inspect_datasets()
        assert "data" in ds
        stats = converter.convert()
        assert stats["files_processed"] == 1
        assert os.path.exists(os.path.join(out, "src", "data", "run_master.tif"))

    def test_no_master_suffix_converts_all(self, tmp_path):
        """Without any '<suffix><ext>' file, all found files are converted
        (regression: previously converted nothing). 无后缀匹配文件时转换全部
        （回归：此前会转换 0 个文件）。"""
        root = str(tmp_path / "src")
        out = str(tmp_path / "output")
        os.makedirs(root)
        with h5py.File(os.path.join(root, "run_0001.h5"), "w") as f:
            f.create_dataset("data", data=np.random.rand(5, 5).astype(np.float32))
        with h5py.File(os.path.join(root, "run_0002.h5"), "w") as f:
            f.create_dataset("data", data=np.random.rand(5, 5).astype(np.float32))

        converter = H5Converter(root, out, master_suffix="_master")
        converter.scan()
        converter.inspect_datasets()
        stats = converter.convert()
        assert stats["files_processed"] == 2
        assert stats["images_exported"] == 2


class TestScanHandlerTargets:
    """handle_h5convert_scan must report the HONEST convert target: suffix
    matches convert those files; no match falls back to converting ALL files.
    扫描 handler 必须如实报告转换目标：有后缀匹配转换匹配者，无匹配回退全部。"""

    def _scan(self, src: str):
        import asyncio

        return asyncio.run(
            handle_h5convert_scan(
                {"source_dir": src, "master_suffix": "_master", "recursive": True},
                _noop_progress,
                asyncio.Event(),
            )
        )

    def test_suffix_matched_reports_masters(self, tmp_path):
        root = str(tmp_path / "src")
        os.makedirs(root)
        for name in ("a_master.nxs", "b_0001.nxs", "b_0002.nxs"):
            with h5py.File(os.path.join(root, name), "w") as f:
                f.create_dataset("data", data=np.random.rand(4, 4).astype(np.float32))

        result = self._scan(root)
        assert result["status"] == "ok"
        assert result["suffixMatched"] is True
        assert result["targetH5"] == 1
        assert result["refFile"] == "a_master.nxs"

    def test_no_suffix_match_reports_all(self, tmp_path):
        root = str(tmp_path / "src")
        os.makedirs(root)
        for name in ("x_0001.nxs", "x_0002.nxs"):
            with h5py.File(os.path.join(root, name), "w") as f:
                f.create_dataset("data", data=np.random.rand(4, 4).astype(np.float32))

        result = self._scan(root)
        assert result["status"] == "ok"
        assert result["suffixMatched"] is False
        assert result["targetH5"] == 2

    def test_empty_dir_is_error(self, tmp_path):
        root = str(tmp_path / "empty")
        os.makedirs(root)
        result = self._scan(root)
        assert result["status"] == "error"
        assert ".hdf5" in result["message"]


class TestSelectionSemantics:
    """'Export exactly what is selected' — the UI dataset list is the COMPLETE
    selection: unlisted datasets (e.g. Nexus instrument flatfields / pixel
    masks) must NOT be exported, and a 4D dataset with every channel
    unchecked exports nothing (regression 2026-09-30: inspect() defaulted
    everything to export=True, and channels=[] fell back to "all channels").
    「选什么导什么」——UI 数据集列表是完整选择：未列出的（如 Nexus 仪器平场/
    像素掩码）不得导出；4D 数据集通道全不选时导出零张（2026-09-30 回归：
    inspect 默认全部 export=True、channels=[] 回退成全部通道）。"""

    def _create_master(self, root: str):
        with h5py.File(os.path.join(root, "run_master.h5"), "w") as f:
            f.create_dataset("entry/data/data", data=np.random.rand(4, 4).astype(np.float32))
            f.create_dataset("entry/instrument/eiger/flatfield",
                             data=np.random.rand(4, 4).astype(np.float32))
            f.create_dataset("entry/instrument/eiger/pixel_mask",
                             data=np.random.rand(4, 4).astype(np.float32))

    def test_handler_exports_only_listed_datasets(self, tmp_path):
        import asyncio

        from python.service_launcher import handle_h5convert

        root, out = str(tmp_path / "src"), str(tmp_path / "out")
        os.makedirs(root)
        self._create_master(root)

        result = asyncio.run(handle_h5convert(
            {
                "sourceDir": root,
                "outputDir": out,
                "refSuffix": "_master",
                "imageFormat": "tiff",
                "tableFormat": "csv",
                "namingMode": "parent_folder",
                "datasets": [{"path": "entry/data/data"}],
            },
            _noop_progress,
            asyncio.Event(),
        ))
        assert result["status"] == "ok"
        assert result["stats"]["images_exported"] == 1
        # Only the selected dataset is exported; the unchecked instrument
        # flatfield / pixel mask must not appear anywhere under out.
        # 只导出勾选的数据集；未勾选的仪器平场/像素掩码不得出现在输出目录。
        exported = [p for p in Path(out).rglob("*") if p.is_file()]
        assert [p.name for p in exported] == ["run_master.tif"]

    def test_empty_channel_selection_exports_nothing(self, tmp_path):
        root, out = str(tmp_path / "src"), str(tmp_path / "out")
        os.makedirs(root)
        with h5py.File(os.path.join(root, "run_master.h5"), "w") as f:
            f.create_dataset("data4d", data=np.random.rand(2, 2, 4, 4).astype(np.float32))

        converter = H5Converter(root, out, master_suffix="_master")
        converter.scan()
        converter.inspect_datasets()
        converter.set_all_export(False)
        converter.set_dataset_config("data4d", export=True, channels=[])
        stats = converter.convert()
        assert stats["images_exported"] == 0
        assert os.listdir(out) == []


class TestFlatOutput:
    """flat_output: image exports land directly in output_dir with every
    folder component folded into the file name (user option 2026-09-30).
    扁平导出：图像直接落在输出目录，文件夹组件并入文件名，不建子文件夹。"""

    def _prepare(self, tmp_path):
        root = str(tmp_path / "批次2024")
        out = str(tmp_path / "output")
        os.makedirs(root)
        with h5py.File(os.path.join(root, "sample_master.h5"), "w") as f:
            f.create_dataset("data", data=np.random.rand(5, 5).astype(np.float32))
        return root, out

    def test_flat_folds_folders_into_filename(self, tmp_path):
        root, out = self._prepare(tmp_path)
        converter = H5Converter(root, out, master_suffix="_master",
                                naming_mode="parent_folder", flat_output=True)
        converter.scan()
        converter.inspect_datasets()
        stats = converter.convert()
        assert stats["images_exported"] == 1
        # Parent folder + dataset path fold into the name; no subfolders.
        # 父文件夹名 + 数据集路径并入文件名；不建子文件夹。
        assert os.path.exists(os.path.join(out, "批次2024_data_sample_master.tif"))
        assert all(os.path.isfile(os.path.join(out, e)) for e in os.listdir(out))

    def test_flat_4d_channel_tag_in_name(self, tmp_path):
        root, out = self._prepare(tmp_path)
        with h5py.File(os.path.join(root, "sample_master.h5"), "w") as f:
            f.create_dataset("data4d", data=np.random.rand(1, 2, 4, 4).astype(np.float32))
        converter = H5Converter(root, out, master_suffix="_master",
                                naming_mode="parent_folder", flat_output=True)
        converter.scan()
        converter.inspect_datasets()
        converter.set_all_export(False)
        converter.set_dataset_config("data4d", export=True, channels=[1])
        stats = converter.convert()
        assert stats["images_exported"] == 1
        assert os.path.exists(os.path.join(out, "批次2024_data4d_CH1_sample_master.tif"))


class TestVdsAndLinkedFiles:
    """Nexus masters reference sibling data files via VDS / external links.
    Extraction must carry the companions along; conversion must refuse to
    export fill-value blanks when sources are missing.
    Nexus master 通过 VDS/外链引用同目录数据文件：提取必须带上数据文件；
    源缺失时转换拒绝导出填充值空白图。"""

    def _create_series(self, src: str, data_name: str = "series_480_data_000001.h5"):
        """HEPS/ESRF convention: master + sibling data file, VDS relative ref."""
        with h5py.File(os.path.join(src, data_name), "w") as f:
            f.create_dataset("entry/data/data", data=np.arange(16, dtype="uint32").reshape(4, 4))
        layout = h5py.VirtualLayout(shape=(4, 4), dtype="uint32")
        vsource = h5py.VirtualSource(data_name, "entry/data/data", shape=(4, 4), dtype="uint32")
        layout[:] = vsource
        with h5py.File(os.path.join(src, "series_480_master.h5"), "w") as f:
            f.create_virtual_dataset("entry/data/data", layout, fillvalue=0)

    def test_extract_carries_vds_companions(self, tmp_path):
        from python.services.h5_extractor import H5Extractor

        src, out = str(tmp_path / "src"), str(tmp_path / "out")
        os.makedirs(src)
        self._create_series(src)

        ex = H5Extractor(source_dir=src, target_dir=out, suffix_filter="_master", prepend_folder=False)
        stats = ex.extract(log_fn=lambda m: None)
        assert stats["success_count"] == 1
        assert stats["linked_files_copied"] == 1
        assert os.path.exists(os.path.join(out, "series_480_data_000001.h5"))
        # The extracted copy reads REAL data, not fill values / 提取副本读到真实数据而非填充值
        with h5py.File(os.path.join(out, "series_480_master.h5"), "r") as f:
            assert (f["entry/data/data"][()] == np.arange(16, dtype="uint32").reshape(4, 4)).all()

    def test_extract_carries_external_links(self, tmp_path):
        from python.services.h5_extractor import H5Extractor

        src, out = str(tmp_path / "src"), str(tmp_path / "out")
        os.makedirs(src)
        with h5py.File(os.path.join(src, "data_ext.h5"), "w") as f:
            f.create_dataset("x", data=np.arange(8, dtype="uint32"))
        with h5py.File(os.path.join(src, "m_master.h5"), "w") as f:
            f["entry/link"] = h5py.ExternalLink("data_ext.h5", "x")

        ex = H5Extractor(source_dir=src, target_dir=out, suffix_filter="_master", prepend_folder=False)
        stats = ex.extract(log_fn=lambda m: None)
        assert stats["linked_files_copied"] == 1
        with h5py.File(os.path.join(out, "m_master.h5"), "r") as f:
            assert (f["entry/link"][()] == np.arange(8, dtype="uint32")).all()

    def test_extract_missing_companion_warns(self, tmp_path):
        from python.services.h5_extractor import H5Extractor

        src, out = str(tmp_path / "src"), str(tmp_path / "out")
        os.makedirs(src)
        self._create_series(src, data_name="absent_000001.h5")  # reference, then delete
        os.remove(os.path.join(src, "absent_000001.h5"))

        ex = H5Extractor(source_dir=src, target_dir=out, suffix_filter="_master", prepend_folder=False)
        stats = ex.extract(log_fn=lambda m: None)
        assert stats["success_count"] == 1
        assert stats["linked_files_missing"] == 1

    def test_convert_refuses_missing_vds_sources(self, tmp_path):
        src, out = str(tmp_path / "src"), str(tmp_path / "out")
        os.makedirs(src)
        self._create_series(src, data_name="absent_000001.h5")
        os.remove(os.path.join(src, "absent_000001.h5"))

        converter = H5Converter(root_dir=src, output_dir=out, master_suffix="_master")
        converter.scan()
        converter.inspect_datasets()
        stats = converter.convert()
        assert stats["errors"] == 1
        assert stats["images_exported"] == 0
        assert os.listdir(out) == []  # no fill-value blanks written / 不落空白图
