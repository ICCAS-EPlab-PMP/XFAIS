#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_compressor.py — Tests for the lossless compression service.

覆盖 TIFF（Deflate）与 HDF5（Bitshuffle+LZ4）两条路线的无损保证：
像素/数据集逐值一致、元数据逐项一致、原始文件只读、输出目录结构映射、
以及 probe / trial / batch 三个服务动作的报告结构。
"""

import asyncio
import os

import h5py
import hdf5plugin
import numpy as np
import pytest
import tifffile

from python.services import compressor


# ---------------------------------------------------------------------------
# Fixtures / 测试夹具
# ---------------------------------------------------------------------------


def _write_tvx_tiff(path: str, seed: int = 0) -> np.ndarray:
    """Write a TVX-style uncompressed int32 TIFF with extra tags.

    写一个 TVX 风格的未压缩 int32 TIFF（含自定义标签、描述、分辨率）。
    """
    rng = np.random.default_rng(seed)
    data = rng.poisson(4.0, (107, 103)).astype("int32") - 2  # includes negative bias
    tifffile.imwrite(
        path,
        data,
        description="TVX acquisition frame; pixel size 172um",
        software="TVX 1.3.4",
        resolution=(149.0, 149.0),
        datetime="2024:01:02 03:04:05",
        extratags=[
            (65000, "s", 11, "PILATUS3X1M", True),
            (65001, "f", 1, (2.5,), True),
            (65002, "I", 1, (48167,), True),
        ],
    )
    return data


@pytest.fixture
def tiff_src(tmp_path):
    path = str(tmp_path / "frame_00001.tif")
    data = _write_tvx_tiff(path)
    return path, data


@pytest.fixture
def h5_src(tmp_path):
    """HDF5 with group attrs, compressible big dataset, small + string datasets."""
    path = str(tmp_path / "scan_0001.h5")
    rng = np.random.default_rng(7)
    frames = rng.poisson(1.5, (10, 220, 210)).astype("int32")  # ~1.8 MB, low entropy
    with h5py.File(path, "w") as handle:
        handle.attrs["instrument"] = "PILATUS3X1M"
        handle.attrs["frames"] = 10
        group = handle.create_group("entry/data")
        group.attrs["NX_class"] = "NXdata"
        dataset = group.create_dataset("data", data=frames, chunks=(1, 220, 210))
        dataset.attrs["units"] = "counts"
        dataset.attrs["calibration"] = np.array([1.0, 2.0, 3.0])
        group.create_dataset("tiny", data=np.arange(10, dtype="uint16"))
        group.create_dataset("label", data=b"raw")
        scalar = handle.create_dataset("frames_per_file", data=np.int32(10))
        scalar.attrs["unit"] = "1"
    return path, frames


# ---------------------------------------------------------------------------
# TIFF route / TIFF 路线
# ---------------------------------------------------------------------------


class TestTiffLossless:
    def test_pixels_and_tags_preserved(self, tiff_src, tmp_path):
        src, data = tiff_src
        out = str(tmp_path / "out.tif")
        result = compressor._compress_tiff_job(src, out)

        assert result["status"] == "ok", result["message"]
        assert result["checks"]["pixels"] is True
        assert result["checks"]["tags"] is True
        assert result["originalBytes"] > result["compressedBytes"]
        assert result["ratio"] > 1.0

        # 像素 + 元数据逐项一致 / pixel and metadata equality
        with tifffile.TiffFile(out) as tif:
            page = tif.pages[0]
            assert np.array_equal(page.asarray(), data)
            assert page.compression == 32946  # ADOBE_DEFLATE
            assert page.tags["ImageDescription"].value == (
                "TVX acquisition frame; pixel size 172um"
            )
            assert page.tags["Software"].value == "TVX 1.3.4"
            assert page.tags["DateTime"].value == "2024:01:02 03:04:05"
            assert page.tags[65000].value == "PILATUS3X1M"
            assert float(page.tags[65001].value) == 2.5
            assert float(page.tags[65002].value) == 48167.0
            # 坑 1：无 {"shape"} 重复描述条目 / no duplicate JSON description
            raw = open(out, "rb").read()
            assert b'{"shape"' not in raw

    def test_source_file_untouched(self, tiff_src):
        src, _ = tiff_src
        before = (os.path.getsize(src), os.path.getmtime(src))
        with open(src, "rb") as handle:
            payload = handle.read()
        compressor._compress_tiff_job(src, src.replace(".tif", "_c.tif"))
        after = (os.path.getsize(src), os.path.getmtime(src))
        assert before == after
        with open(src, "rb") as handle:
            assert handle.read() == payload

    def test_multipage_preserved(self, tmp_path):
        src = str(tmp_path / "multi.tif")
        page0 = np.full((30, 40), 7, dtype="uint16")
        page1 = np.arange(1200, dtype="uint16").reshape(30, 40)
        with tifffile.TiffWriter(src) as writer:
            writer.write(page0, description="page-0")
            writer.write(page1, description="page-1")
        out = str(tmp_path / "multi_c.tif")

        result = compressor._compress_tiff_job(src, out)

        assert result["status"] == "ok", result["message"]
        assert result["pages"] == 2
        with tifffile.TiffFile(out) as tif:
            assert len(tif.pages) == 2
            assert np.array_equal(tif.pages[0].asarray(), page0)
            assert np.array_equal(tif.pages[1].asarray(), page1)
            assert tif.pages[0].tags["ImageDescription"].value == "page-0"
            assert tif.pages[1].tags["ImageDescription"].value == "page-1"

    def test_already_deflate_is_skipped(self, tmp_path):
        src = str(tmp_path / "already.tif")
        tifffile.imwrite(src, np.zeros((20, 20), dtype="uint8"), compression="deflate")
        out = str(tmp_path / "already_c.tif")

        result = compressor._compress_tiff_job(src, out)

        assert result["status"] == "skipped"
        assert not os.path.exists(out)


# ---------------------------------------------------------------------------
# HDF5 route / HDF5 路线
# ---------------------------------------------------------------------------


class TestHdf5Lossless:
    def test_data_and_attrs_preserved(self, h5_src, tmp_path):
        src, frames = h5_src
        out = str(tmp_path / "scan_0001_c.h5")

        result = compressor._compress_h5_job(src, out)

        assert result["status"] == "ok", result["message"]
        assert result["checks"]["datasets"] is True
        assert result["checks"]["attrs"] is True
        assert result["compressedDatasets"] >= 1
        assert result["originalBytes"] > result["compressedBytes"]

        with h5py.File(out, "r") as handle:
            assert handle.attrs["instrument"] == "PILATUS3X1M"
            assert int(handle.attrs["frames"]) == 10
            group = handle["entry/data"]
            assert group.attrs["NX_class"] == "NXdata"
            dataset = group["data"]
            assert np.array_equal(dataset[()], frames)
            assert dataset.attrs["units"] == "counts"
            assert np.array_equal(dataset.attrs["calibration"], np.array([1.0, 2.0, 3.0]))
            # 大数据集使用 Bitshuffle+LZ4 / big dataset carries the filter
            assert "32008" in dataset._filters
            # 小数据集原样复制，不带滤镜 / small dataset copied as-is
            assert not handle["entry/data/tiny"]._filters
            assert bytes(handle["entry/data/label"][()]) == b"raw"
            assert int(handle["frames_per_file"][()]) == 10

    def test_small_dataset_values_exact(self, h5_src, tmp_path):
        src, _ = h5_src
        out = str(tmp_path / "out.h5")
        compressor._compress_h5_job(src, out)
        with h5py.File(src, "r") as a, h5py.File(out, "r") as b:
            assert np.array_equal(a["entry/data/tiny"][()], b["entry/data/tiny"][()])
            assert a["entry/data/tiny"].dtype == b["entry/data/tiny"].dtype

    def test_string_dataset_preserved(self, h5_src, tmp_path):
        src, _ = h5_src
        out = str(tmp_path / "out.h5")
        compressor._compress_h5_job(src, out)
        with h5py.File(out, "r") as handle:
            assert bytes(handle["entry/data/label"][()]) == b"raw"

    def test_already_bitshuffle_dataset_is_not_recompressed(self, tmp_path):
        """已带 Bitshuffle 的数据集必须原样复制，不重算 chunk。

        实证（用户同步辐射 HDF5）：把 (1,1,2162,2068) 的单 chunk 数据集按 8 MiB
        重新分块后用同一滤镜再压一遍，体积从 133 KB 涨到 158 KB——调大 18%。
        """
        src = str(tmp_path / "eiger_like.h5")
        rng = np.random.default_rng(11)
        frames = rng.poisson(0.4, (1, 1, 300, 280)).astype("uint32")  # ~336 KB
        kwargs = dict(compressor._bitshuffle_lz4())
        with h5py.File(src, "w") as handle:
            dataset = handle.create_dataset(
                "entry/data/data", data=frames, chunks=(1, 1, 300, 280), **kwargs
            )
            dataset.attrs["units"] = "counts"
        out = str(tmp_path / "eiger_like_c.h5")

        result = compressor._compress_h5_job(src, out)

        assert result["status"] in ("ok", "skipped"), result["message"]
        assert result["compressedDatasets"] == 0
        assert result["compressedBytes"] <= result["originalBytes"]
        with h5py.File(src, "r") as a, h5py.File(out, "r") as b:
            # chunk 布局与滤镜原样保留 / chunk layout and filter preserved
            assert b["entry/data/data"].chunks == a["entry/data/data"].chunks
            assert "32008" in b["entry/data/data"]._filters
            assert np.array_equal(a["entry/data/data"][()], b["entry/data/data"][()])
            assert b["entry/data/data"].attrs["units"] == "counts"

    def test_vds_relative_source_is_relinked(self, tmp_path):
        """Eiger master 形态：VDS 源为相对路径，输出到别的目录后仍须读到同样的数据。

        原样 h5py copy 会保留相对文件名，输出目录里没有 data 文件 → 读回全是
        fill value，校验报「数据不一致」，用户看到的就是"不能压缩"。
        """
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        rng = np.random.default_rng(3)
        frames = rng.poisson(2.0, (1, 1, 120, 110)).astype("uint32")
        data_name = "scan_data_000001.h5"
        with h5py.File(str(src_dir / data_name), "w") as handle:
            handle.create_dataset(
                "/entry/data/data", data=frames, chunks=(1, 1, 120, 110),
                **dict(compressor._bitshuffle_lz4())
            )

        master = str(src_dir / "master.h5")
        with h5py.File(master, "w") as handle:
            group = handle.create_group("entry").create_group("data")
            layout = h5py.VirtualLayout(shape=frames.shape, dtype=frames.dtype)
            layout[...] = h5py.VirtualSource(
                data_name, "/entry/data/data", shape=frames.shape, dtype=frames.dtype
            )
            group.create_virtual_dataset(
                "data", layout, fillvalue=np.uint32(4294967295)
            )
            # 让源文件明显可压缩，避免落到 no-gain 分支
            handle.create_dataset("pad", data=np.zeros(200_000, dtype="uint8"))

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        out = str(out_dir / "master.h5")

        result = compressor._compress_h5_job(master, out)

        assert result["status"] == "ok", result["message"]
        assert result["checks"]["virtualCount"] == 1
        assert "relinked" in result["message"]
        with h5py.File(out, "r") as handle:
            dataset = handle["entry/data/data"]
            assert dataset.is_virtual is True
            sources = dataset.virtual_sources()
            assert len(sources) == 1
            assert os.path.isabs(sources[0].file_name)
            assert np.array_equal(dataset[()], frames)

    def test_no_gain_output_is_skipped_and_discarded(self, tmp_path, monkeypatch):
        """重写后体积不减小 → skipped，且不留下任何输出/临时文件。"""
        src = str(tmp_path / "tiny.h5")
        with h5py.File(src, "w") as handle:
            handle.create_dataset("d", data=np.arange(64, dtype="int32"))

        def inflate(src_file, dst_file):
            # 模拟"重压缩反而更大"：写出一块比源文件更大的数据
            dst_file.create_dataset("pad", data=np.zeros(200_000, dtype="uint8"))
            return []

        monkeypatch.setattr(compressor, "_copy_h5_tree", inflate)
        out = str(tmp_path / "tiny_c.h5")

        result = compressor._compress_h5_job(src, out)

        assert result["status"] == "skipped"
        assert result["compressedBytes"] == 0
        assert "no gain" in result["message"]
        assert not os.path.exists(out)
        assert [n for n in os.listdir(str(tmp_path)) if n.startswith(".xfais")] == []

    def test_trial_reports_hdf5_skip_reason(self, tmp_path, monkeypatch):
        """trial 的 note 必须取自作业本身，不能硬编码 TIFF 的 Deflate 文案。"""
        src_dir = str(tmp_path / "src")
        os.makedirs(src_dir)
        with h5py.File(os.path.join(src_dir, "a.h5"), "w") as handle:
            handle.create_dataset("d", data=np.arange(64, dtype="int32"))

        def inflate(src_file, dst_file):
            dst_file.create_dataset("pad", data=np.zeros(200_000, dtype="uint8"))
            return []

        monkeypatch.setattr(compressor, "_copy_h5_tree", inflate)

        async def progress(fraction, message):
            return None

        async def main():
            return await compressor.handle_compress(
                {"action": "trial", "input_dir": src_dir}, progress, asyncio.Event()
            )

        result = _run(main())

        assert result["status"] == "ok"
        assert result["verified"] is True
        assert "Deflate" not in (result["note"] or "")
        assert "no gain" in (result["note"] or "")
        assert not os.path.exists(os.path.join(src_dir, "a_c.h5"))


# ---------------------------------------------------------------------------
# Helpers / 辅助函数
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_ratio(self):
        assert compressor.compression_ratio(1000, 100) == 10.0
        assert compressor.compression_ratio(1000, 0) == 0.0
        assert compressor.compression_ratio(0, 100) == 0.0
        assert compressor.compression_ratio(500, 1000) == 0.5

    def test_values_equal_rational(self):
        assert compressor._tiff_values_equal((1043, 7), (149, 1))
        assert not compressor._tiff_values_equal((1043, 7), (148, 1))
        assert compressor._tiff_values_equal("abc", "abc")
        assert compressor._tiff_values_equal(b"abc", b"abc")

    def test_chunks_within_target(self):
        chunks = compressor._choose_chunks((100, 1043, 981), 4)
        assert chunks is not None
        assert len(chunks) == 3
        total = 4
        for dim, chunk in zip((100, 1043, 981), chunks):
            assert 1 <= chunk <= dim
            total *= chunk
        assert total <= compressor.H5_CHUNK_TARGET_BYTES or chunks[0] == 1

    def test_confined_output_rejects_traversal(self, tmp_path):
        root = str(tmp_path)
        with pytest.raises(ValueError):
            compressor._confined_output_path(root, ["..", "etc"], "x.tif")

    def test_planned_outputs_mirror_subdirs(self, tmp_path):
        root = str(tmp_path)
        entries = [
            {"path": os.path.join(root, "a", "x.tif"), "kind": "tiff", "size": 1},
            {"path": os.path.join(root, "b", "y.h5"), "kind": "hdf5", "size": 1},
        ]
        out_dir = os.path.join(root, "out")
        planned = compressor._planned_outputs(entries, out_dir, root)
        assert planned[0]["outputPath"] == os.path.join(out_dir, "a", "x.tif")
        assert planned[1]["outputPath"] == os.path.join(out_dir, "b", "y.h5")

    def test_unique_output_name_suffixes(self):
        used: set = set()
        assert compressor._unique_output_name(used, [], "x.tif") == "x.tif"
        assert compressor._unique_output_name(used, [], "x.tif") == "x_2.tif"
        assert compressor._unique_output_name(used, [], "x.tif") == "x_3.tif"
        # Different directories do not collide / 不同目录不冲突
        assert compressor._unique_output_name(used, ["sub"], "x.tif") == "x.tif"


# ---------------------------------------------------------------------------
# Service actions / 服务动作
# ---------------------------------------------------------------------------


def _run(coro):
    return asyncio.run(coro)


class TestServiceActions:
    def test_probe_stats(self, tiff_src, h5_src):
        src_dir = os.path.dirname(tiff_src[0])
        reported = []

        async def progress(fraction, message):
            reported.append(fraction)

        async def main():
            return await compressor.handle_compress(
                {"action": "probe", "input_dir": src_dir, "recursive": True},
                progress,
                asyncio.Event(),
            )

        result = _run(main())

        assert result["status"] == "ok"
        assert result["stats"]["tiffCount"] == 1
        assert result["stats"]["hdf5Count"] == 1
        assert result["stats"]["totalBytes"] > 0
        assert len(result["sample"]) == 2

    def test_trial_returns_verified_report(self, tiff_src):
        async def progress(fraction, message):
            return None

        async def main():
            return await compressor.handle_compress(
                {"action": "trial", "input_dir": os.path.dirname(tiff_src[0])},
                progress,
                asyncio.Event(),
            )

        result = _run(main())

        assert result["status"] == "ok"
        assert result["verified"] is True
        assert result["action"] == "trial"
        assert result["ratio"] > 1.0
        # 试压缩不得留下任何输出 / trial leaves no output next to the source
        leftovers = [n for n in os.listdir(os.path.dirname(tiff_src[0])) if n.startswith(".xfais")]
        assert leftovers == []

    def test_batch_writes_outputs_and_keeps_originals(self, tmp_path):
        src_dir = str(tmp_path / "src")
        sub_dir = os.path.join(src_dir, "sub")
        os.makedirs(sub_dir)
        _write_tvx_tiff(os.path.join(src_dir, "a.tif"), seed=1)
        _write_tvx_tiff(os.path.join(sub_dir, "b.tif"), seed=2)
        with h5py.File(os.path.join(src_dir, "c.h5"), "w") as handle:
            handle.create_dataset("d", data=np.arange(2000, dtype="int32"))
        originals = {}
        for name in ("a.tif", os.path.join("sub", "b.tif"), "c.h5"):
            path = os.path.join(src_dir, name)
            originals[path] = (os.path.getsize(path), os.path.getmtime(path))
        out_dir = str(tmp_path / "out")

        async def progress(fraction, message):
            return None

        async def main():
            return await compressor.handle_compress(
                {
                    "action": "batch",
                    "input_dir": src_dir,
                    "output_dir": out_dir,
                    "recursive": True,
                },
                progress,
                asyncio.Event(),
            )

        result = _run(main())

        assert result["status"] == "ok"
        assert result["total"] == 3
        assert result["success"] == 3
        assert result["failed"] == 0
        assert result["ratio"] > 1.0
        assert result["filesOmitted"] == 0
        # 目录结构映射 / directory structure mirrored
        assert os.path.isfile(os.path.join(out_dir, "a.tif"))
        assert os.path.isfile(os.path.join(out_dir, "sub", "b.tif"))
        assert os.path.isfile(os.path.join(out_dir, "c.h5"))
        # 原始文件未被改写 / originals untouched
        for path, before in originals.items():
            assert (os.path.getsize(path), os.path.getmtime(path)) == before
        # 无临时文件残留 / no temp leftovers
        assert [n for n in os.listdir(out_dir) if n.startswith(".xfais")] == []

    def test_batch_rejects_same_output_dir(self, tmp_path):
        src_dir = str(tmp_path / "src")
        os.makedirs(src_dir)
        _write_tvx_tiff(os.path.join(src_dir, "a.tif"))

        async def progress(fraction, message):
            return None

        async def main():
            return await compressor.handle_compress(
                {"action": "batch", "input_dir": src_dir, "output_dir": src_dir},
                progress,
                asyncio.Event(),
            )

        result = _run(main())

        assert result["status"] == "error"
        assert "output dir" in result["message"].lower() or "输出目录" in result["message"]

    def test_batch_cancel_keeps_finished_files(self, tmp_path):
        """A pre-set cancel event stops before any work but returns a report."""
        src_dir = str(tmp_path / "src")
        os.makedirs(src_dir)
        _write_tvx_tiff(os.path.join(src_dir, "a.tif"))
        out_dir = str(tmp_path / "out")
        event = asyncio.Event()

        async def progress(fraction, message):
            return None

        async def main():
            event.set()
            return await compressor.handle_compress(
                {"action": "batch", "input_dir": src_dir, "output_dir": out_dir},
                progress,
                event,
            )

        result = _run(main())

        assert result["status"] == "ok"
        assert result["cancelled"] is True
        assert result["success"] == 0

    def test_probe_requires_input(self):
        async def progress(fraction, message):
            return None

        async def main():
            return await compressor.handle_compress(
                {"action": "probe"}, progress, asyncio.Event()
            )

        result = _run(main())
        assert result["status"] == "error"

    def test_hdf5_reader_filter_registered(self):
        """The filter used for writing is available for reading (hdf5plugin)."""
        assert hdf5plugin.Bitshuffle is not None
        kwargs = dict(compressor._bitshuffle_lz4())
        assert kwargs["compression"] == 32008  # Bitshuffle filter id
