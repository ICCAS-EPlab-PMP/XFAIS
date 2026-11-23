#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
compressor.py — Lossless compression service for TIFF (Deflate) and HDF5 (Bitshuffle+LZ4)
compressor.py — TIFF（Deflate）与 HDF5（Bitshuffle+LZ4）无损压缩服务

Two独立路线 / Two independent routes:
  * TIFF : 标准 TIFF Deflate (level 9)，读取端零依赖；元数据逐标签原值复制，
           写后四项校验（像素 / 描述 / 标签 / 无重复 JSON 描述条目）。
  * HDF5 : hdf5plugin Bitshuffle + LZ4（与 DECTRIS Eiger 原生一致），
           递归保持 group/dataset/attrs 树形结构；逐 dataset 读回比对。

原始文件只读 / Source files are opened read-only:
  本模块任何分支都不对输入路径执行写、删、改名。输出先写同目录内的
  系统临时文件（mkstemp），校验通过后 os.replace 原子落位。

服务入口 / Service entry:
  ``handle_compress(payload, send_progress, cancel_event)`` — actions:
  probe（扫描统计）/ trial（试压缩第一个文件）/ batch（批量导出）/ cancel。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path, PurePath
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

import numpy as np

from .paths import validated_output_path

log = logging.getLogger(__name__)

# Supported container extensions / 受支持的容器扩展名
TIFF_EXTS = (".tif", ".tiff")
HDF5_EXTS = (".h5", ".hdf5", ".nxs", ".hdf", ".nexus")

TIFF_ALGORITHM = "TIFF Deflate (level 9)"
HDF5_ALGORITHM = "HDF5 Bitshuffle + LZ4"

TIFF_DEFLATE_LEVEL = 9

# Hard limits / 硬上限
MAX_FILES = 200_000
# TIFF 需要整帧读入内存，故限制 4 GiB；HDF5 走分块，上限放宽。
# TIFF frames are loaded fully into memory (4 GiB guard); HDF5 is chunked.
MAX_TIFF_BYTES = 4 * 1024 * 1024 * 1024
MAX_HDF5_BYTES = 256 * 1024 * 1024 * 1024
SAMPLE_LIST_LIMIT = 300  # probe 返回的文件名样本数 / filenames echoed by probe
REPORT_FILE_LIMIT = 2000  # batch 报告逐文件条目上限 / per-file rows in the report
TRIAL_MAX_BYTES = 2 * 1024 * 1024 * 1024  # 试压缩单文件上限 / trial size guard

# HDF5 chunking / HDF5 分块
H5_CHUNK_TARGET_BYTES = 8 * 1024 * 1024
H5_COMPRESS_MIN_BYTES = 1024 * 1024  # <1 MiB 原样复制 / copy as-is below 1 MiB

# hdf5plugin.Bitshuffle 的滤镜 id（与 DECTRIS Eiger 原生写入一致）。
# hdf5plugin.Bitshuffle filter id (identical to DECTRIS Eiger native output).
BITSHUFFLE_FILTER_ID = 32008

# tifffile 自己写的结构性标签，或必须走 write() 专用参数的标签
# （description / software / resolution / resolutionunit）；其余标签经
# extratags 原值复制。与 tifffile.TIFF.TAG_FILTERED 保持一致，避免
# "not writing extratag" 警告。
# Structural tags written by tifffile itself, plus tags that must go through
# dedicated write() parameters; everything else is copied verbatim via extratags.
TIFF_SKIP_TAGS = {
    256,  # ImageWidth
    257,  # ImageLength
    258,  # BitsPerSample
    259,  # Compression
    262,  # PhotometricInterpretation
    266,  # FillOrder
    270,  # ImageDescription -> description=
    273,  # StripOffsets
    277,  # SamplesPerPixel
    278,  # RowsPerStrip
    279,  # StripByteCounts
    282,  # XResolution -> resolution=
    283,  # YResolution -> resolution=
    284,  # PlanarConfiguration
    296,  # ResolutionUnit -> resolutionunit=
    305,  # Software -> software=
    317,  # Predictor (we write no predictor)
    322,  # TileWidth
    323,  # TileLength
    324,  # TileOffsets
    325,  # TileByteCounts
    330,  # SubIFDs
    338,  # ExtraSamples -> extrasamples=
    339,  # SampleFormat
    400,  # GlobalParametersIFD
    32997,  # ImageDepth
    32998,  # TileDepth
    34665,  # ExifTag
    34853,  # GPSTag
    40965,  # InteroperabilityTag
}


class CompressError(Exception):
    """Per-file compression failure with a human-readable reason.
    单文件压缩失败（带可读原因）。"""


# ---------------------------------------------------------------------------
# Small helpers / 小型辅助
# ---------------------------------------------------------------------------


def compression_ratio(original_bytes: int, compressed_bytes: int) -> float:
    """original / compressed (e.g. 6.51 means 6.51× smaller). 压缩比。

    Returns 0.0 when either side is unusable, so the UI can render "—".
    任一侧不可用时返回 0.0，界面显示为 "—"。
    """
    try:
        original = float(original_bytes)
        compressed = float(compressed_bytes)
    except (TypeError, ValueError):
        return 0.0
    if original <= 0 or compressed <= 0:
        return 0.0
    return round(original / compressed, 4)


def _file_kind(name: str) -> Optional[str]:
    """'tiff' | 'hdf5' | None for one filename. 按扩展名判定容器类型。"""
    low = name.lower()
    if low.endswith(TIFF_EXTS):
        return "tiff"
    if low.endswith(HDF5_EXTS):
        return "hdf5"
    return None


def _algorithm(kind: str) -> str:
    return TIFF_ALGORITHM if kind == "tiff" else HDF5_ALGORITHM


def _tiff_values_equal(src_value: Any, dst_value: Any) -> bool:
    """Compare TIFF tag values, treating integer 2-tuples as rationals (num/den).

    TVX 原文件把 ASCII 零填充到固定长度、RATIONAL 允许化简形式不同，
    因此按"值相等"而非"存储形式相等"比较。仅当两侧都是整数二元组时才按
    RATIONAL 交叉相乘（浮点二元组直接落回字节/字符串比较，避免误判）。
    """
    if (
        isinstance(src_value, tuple)
        and isinstance(dst_value, tuple)
        and len(src_value) == 2
        and len(dst_value) == 2
        and isinstance(src_value[0], (int, np.integer))
        and isinstance(dst_value[0], (int, np.integer))
    ):
        try:
            return src_value[0] * dst_value[1] == dst_value[0] * src_value[1]
        except Exception:  # noqa: BLE001 — fall through to byte comparison
            pass
    try:
        return bytes(src_value) == bytes(dst_value)
    except (TypeError, ValueError):
        return str(src_value) == str(dst_value)


def _tag_value(page: Any, code: int) -> Any:
    """Tag value or None when absent. 标签值（缺失返回 None）。"""
    try:
        tag = page.tags.get(code)
    except Exception:  # noqa: BLE001
        tag = None
    return None if tag is None else tag.value


def _decode_text(value: Any) -> Optional[str]:
    """Bytes/str tag value → str (None stays None). 文本标签解码。"""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _ratio_from(fraction_num: int, fraction_den: int) -> Optional[float]:
    """(num, den) rational → float; None when malformed. 有理数转浮点。"""
    try:
        num = float(fraction_num)
        den = float(fraction_den)
    except (TypeError, ValueError):
        return None
    if den == 0:
        return None
    return num / den


# ---------------------------------------------------------------------------
# TIFF route / TIFF 路线
# ---------------------------------------------------------------------------


def _tiff_page_plan(page: Any) -> Dict[str, Any]:
    """Read one page and build the parameters needed to rewrite it losslessly.

    读取一页并构造无损重写所需的参数（不写文件）。
    """
    desc = _decode_text(_tag_value(page, 270))
    software = _decode_text(_tag_value(page, 305))
    xres = _tag_value(page, 282)
    yres = _tag_value(page, 283)
    resunit = _tag_value(page, 296)

    extratags: List[Tuple[int, str, int, Any, bool]] = []
    expected_tags: Dict[int, Any] = {}
    for tag in page.tags.values():
        if tag.code in TIFF_SKIP_TAGS:
            continue
        extratags.append((tag.code, tag.dtype, tag.count, tag.value, True))
        expected_tags[tag.code] = tag.value

    return {
        "array": page.asarray(),
        "description": desc,
        "software": software,
        "xres": xres,
        "yres": yres,
        "resolutionunit": resunit,
        "extratags": extratags,
        "expected_tags": expected_tags,
        "photometric": int(page.photometric),
        "planarconfig": int(page.planarconfig) if page.planarconfig is not None else None,
        "extrasamples": getattr(page, "extrasamples", None),
        "shape": tuple(page.shape),
        "dtype": page.dtype,
    }


def _write_tiff_pages(pages: List[Dict[str, Any]], dst_path: str) -> None:
    """Write all planned pages into dst_path with Deflate level 9. 写出全部页。"""
    import tifffile

    with tifffile.TiffWriter(dst_path, mode="w") as writer:
        for plan in pages:
            array = plan["array"]
            kwargs: Dict[str, Any] = {
                "photometric": plan["photometric"],
                "compression": "deflate",
                "compressionargs": {"level": TIFF_DEFLATE_LEVEL},
                # 单条带，与原始文件一致；超大帧退回 tifffile 默认分段。
                # Single strip like the source; fall back to default for huge frames.
                "rowsperstrip": (
                    int(array.shape[0])
                    if array.ndim >= 2 and int(array.nbytes) < 1_000_000_000
                    else None
                ),
                # 关键：禁止 tifffile 追加 {"shape": [...]} JSON 重复 tag 270 条目
                # Critical: no duplicate JSON ImageDescription entry.
                "metadata": False,
                "extratags": plan["extratags"],
            }
            if plan["description"] is not None:
                kwargs["description"] = plan["description"]
            if plan["software"] is not None:
                kwargs["software"] = plan["software"]
            xres, yres = plan["xres"], plan["yres"]
            if xres is not None and yres is not None:
                x_val = _ratio_from(xres[0], xres[1])
                y_val = _ratio_from(yres[0], yres[1])
                if x_val is not None and y_val is not None:
                    # 坑 2：resolution 收两个浮点，不是 num/den 元组。
                    kwargs["resolution"] = (x_val, y_val)
                    if plan["resolutionunit"] is not None:
                        kwargs["resolutionunit"] = int(plan["resolutionunit"])
            if plan["photometric"] in (2, 5) and plan["planarconfig"] is not None:
                kwargs["planarconfig"] = plan["planarconfig"]
            if plan["extrasamples"]:
                kwargs["extrasamples"] = plan["extrasamples"]
            writer.write(array, **kwargs)


def _verify_tiff_file(
    src_path: str,
    dst_path: str,
    pages: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Four-way verification of the freshly written TIFF.

    四项校验：① 像素逐值相等 ② ImageDescription 逐字符一致
    ③ 全部复制标签值相等（RATIONAL 交叉相乘）④ 无 {"shape"} 重复描述条目。
    """
    import tifffile

    with tifffile.TiffFile(dst_path) as tif:
        if len(tif.pages) != len(pages):
            raise CompressError(
                f"page count mismatch ({len(tif.pages)} != {len(pages)}) / 页数不一致"
            )
        for index, plan in enumerate(pages):
            page = tif.pages[index]
            got_desc = _decode_text(_tag_value(page, 270))
            if got_desc != plan["description"]:
                raise CompressError(
                    f"page {index}: ImageDescription mismatch / 描述不一致"
                )
            array = page.asarray()
            if tuple(array.shape) != tuple(plan["shape"]):
                raise CompressError(f"page {index}: shape changed / 尺寸改变")
            if array.dtype != plan["dtype"]:
                raise CompressError(f"page {index}: dtype changed / 数据类型改变")
            if not np.array_equal(array, plan["array"]):
                raise CompressError(f"page {index}: pixel mismatch / 像素不一致")
            for code, expected in plan["expected_tags"].items():
                tag = page.tags.get(code)
                if tag is None:
                    raise CompressError(f"page {index}: missing tag {code} / 标签丢失")
                if not _tiff_values_equal(expected, tag.value):
                    raise CompressError(
                        f"page {index}: tag {code} value mismatch / 标签值不一致"
                    )
            got_software = _decode_text(_tag_value(page, 305))
            if got_software != plan["software"]:
                raise CompressError(f"page {index}: Software mismatch / Software 不一致")
            xres, yres = plan["xres"], plan["yres"]
            if xres is not None and yres is not None:
                got_x = _tag_value(page, 282)
                got_y = _tag_value(page, 283)
                if not (
                    isinstance(got_x, tuple)
                    and len(got_x) == 2
                    and _tiff_values_equal(xres, got_x)
                ):
                    raise CompressError(f"page {index}: XResolution mismatch / X 分辨率不一致")
                if not (
                    isinstance(got_y, tuple)
                    and len(got_y) == 2
                    and _tiff_values_equal(yres, got_y)
                ):
                    raise CompressError(f"page {index}: YResolution mismatch / Y 分辨率不一致")

    # ④ 字节级检查：tifffile 的 metadata=False 生效（坑 1）。
    # 源文件本身若已含该模式（非 tifffile 产物可能如此），跳过本条以免误报。
    with open(dst_path, "rb") as handle:
        dst_bytes = handle.read()
    if b'{"shape"' in dst_bytes:
        with open(src_path, "rb") as handle:
            src_has_pattern = b'{"shape"' in handle.read()
        if not src_has_pattern:
            raise CompressError("duplicate JSON description entry / 重复 JSON 描述条目")

    return {
        "pixels": True,
        "description": True,
        "tags": True,
        "pages": True,
        "noDupJsonDescription": True,
    }


class _AlreadyCompressed(Exception):
    """Source TIFF already uses Deflate — recorded as skipped. 源已 Deflate。"""


def compress_tiff_to(src_path: str, tmp_path: str) -> Dict[str, Any]:
    """Compress one TIFF into tmp_path (caller supplies a temp path).

    把一个 TIFF 无损压缩到 tmp_path（由调用方提供系统临时路径）。
    """
    import tifffile

    with tifffile.TiffFile(src_path) as tif:
        if not tif.pages:
            raise CompressError("empty TIFF / 空 TIFF 文件")
        plans: List[Dict[str, Any]] = []
        for page in tif.pages:
            compression = int(page.compression or 1)
            if compression in (8, 32946):
                # 已是 Deflate：跳过（避免无意义重写）/ already Deflate
                raise _AlreadyCompressed()
            if int(page.photometric) == 6:
                raise CompressError(
                    "YCbCr photometric is not supported for lossless rewrite / "
                    "不支持 YCbCr 色彩空间的 TIFF"
                )
            plans.append(_tiff_page_plan(page))
    _write_tiff_pages(plans, tmp_path)
    checks = _verify_tiff_file(src_path, tmp_path, plans)
    return {"checks": checks, "pages": len(plans)}


def _compress_tiff_job(src_path: str, final_path: str) -> Dict[str, Any]:
    """One TIFF job: temp write → verify → atomic rename to final_path.

    单个 TIFF 作业：临时写入 → 校验 → 原子改名落位。失败时删除临时文件。
    """
    dest_dir = os.path.dirname(final_path)
    original_bytes = os.path.getsize(src_path)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".xfais-compress-", suffix=".tif.tmp", dir=dest_dir
    )
    os.close(fd)
    try:
        info = compress_tiff_to(src_path, tmp_path)
        compressed_bytes = os.path.getsize(tmp_path)
        os.replace(tmp_path, final_path)
    except _AlreadyCompressed:
        _remove_quietly(tmp_path)
        return {
            "path": src_path,
            "outputPath": "",
            "kind": "tiff",
            "algorithm": TIFF_ALGORITHM,
            "originalBytes": original_bytes,
            "compressedBytes": 0,
            "ratio": 0.0,
            "status": "skipped",
            "checks": {},
            "message": "already Deflate-compressed / 已是 Deflate 压缩",
        }
    except BaseException as exc:  # noqa: BLE001 — per-file failure, batch continues
        _remove_quietly(tmp_path)
        return _failed_entry(src_path, "tiff", original_bytes, exc)
    return {
        "path": src_path,
        "outputPath": final_path,
        "kind": "tiff",
        "algorithm": TIFF_ALGORITHM,
        "originalBytes": original_bytes,
        "compressedBytes": compressed_bytes,
        "ratio": compression_ratio(original_bytes, compressed_bytes),
        "status": "ok",
        "checks": info["checks"],
        "pages": info["pages"],
        "message": "",
    }


# ---------------------------------------------------------------------------
# HDF5 route / HDF5 路线
# ---------------------------------------------------------------------------


def _bitshuffle_lz4() -> Dict[str, Any]:
    """Bitshuffle+LZ4 filter kwargs, tolerant of hdf5plugin 4/5/6 API drift.

    兼容 hdf5plugin 各版本：5.x/6.x 用 nelems，早期版本用 nelem；
    6.0 起推荐 cname='lz4'（lz4 参数已废弃）。
    """
    import hdf5plugin

    factory = hdf5plugin.Bitshuffle
    try:
        params = inspect.signature(factory.__init__).parameters
    except (TypeError, ValueError):  # pragma: no cover - exotic builds
        params = {}
    kwargs: Dict[str, Any] = {"cname": "lz4"} if "cname" in params else {"lz4": True}
    kwargs["nelems" if "nelems" in params else "nelem"] = 0
    return factory(**kwargs)


def _is_numeric_dtype(dtype: Any) -> bool:
    try:
        return bool(np.issubdtype(dtype, np.number))
    except (TypeError, ValueError):
        return False


def _choose_chunks(shape: Tuple[int, ...], itemsize: int) -> Optional[Tuple[int, ...]]:
    """Chunk shape with ~target chunk bytes; last axes stay contiguous.

    选择约 8 MiB 的分块（末轴保持连续，压缩率与小文件随机读取兼顾）。
    """
    if not shape or any(int(dim) <= 0 for dim in shape):
        return None
    chunks = [int(dim) for dim in shape]
    target = H5_CHUNK_TARGET_BYTES
    total = itemsize
    for dim in chunks:
        total *= dim
    guard = 0
    while total > target and guard < 128:
        guard += 1
        index = max(range(len(chunks)), key=lambda i: chunks[i])
        if chunks[index] <= 1:
            break
        chunks[index] = max(1, chunks[index] // 2)
        total = itemsize
        for dim in chunks:
            total *= dim
    return tuple(chunks)


def _copy_attrs(src_obj: Any, dst_obj: Any) -> None:
    """Copy every attribute value verbatim. 原值复制全部属性。"""
    for key, value in src_obj.attrs.items():
        dst_obj.attrs[key] = value


def _attr_values_equal(left: Any, right: Any) -> bool:
    """Attribute comparison tolerant of numpy scalars / arrays / bytes."""
    if isinstance(left, np.ndarray) or isinstance(right, np.ndarray):
        try:
            return bool(np.array_equal(np.asarray(left), np.asarray(right)))
        except Exception:  # noqa: BLE001
            return False
    if isinstance(left, (bytes, np.bytes_)) or isinstance(right, (bytes, np.bytes_)):
        try:
            return bytes(left) == bytes(right)
        except Exception:  # noqa: BLE001
            return False
    try:
        result = left == right
        if isinstance(result, np.ndarray):
            return bool(result.all())
        return bool(result)
    except Exception:  # noqa: BLE001
        return repr(left) == repr(right)


def _attrs_equal(src_obj: Any, dst_obj: Any) -> bool:
    src_keys = set(src_obj.attrs.keys())
    dst_keys = set(dst_obj.attrs.keys())
    if src_keys != dst_keys:
        return False
    for key in src_keys:
        if not _attr_values_equal(src_obj.attrs[key], dst_obj.attrs[key]):
            return False
    return True


def _already_bitshuffle(dataset: Any) -> bool:
    """True when the dataset already carries the Bitshuffle filter we would write.

    数据集已带 Bitshuffle 滤镜（Eiger 原生产物或本服务输出）时重写无收益：
    同样算法再压一遍只会丢掉作者选择的 chunk 布局，体积通常还会变大。
    """
    try:
        plist = dataset.id.get_create_plist()
        for index in range(int(plist.get_nfilters())):
            if int(plist.get_filter(index)[0]) == BITSHUFFLE_FILTER_ID:
                return True
    except Exception:  # noqa: BLE001 — exotic layouts/dtypes
        return False
    return False


def _should_compress_dataset(dataset: Any) -> bool:
    """Numeric + large enough + not virtual/already compressed; else copy as-is.

    数值型、≥1 MiB、非虚拟且未带 Bitshuffle 的数据集才重写为压缩数据集。
    """
    if getattr(dataset, "is_virtual", False):
        return False
    if not dataset.shape:
        return False
    if int(dataset.nbytes) < H5_COMPRESS_MIN_BYTES:
        return False
    if _already_bitshuffle(dataset):
        return False
    return _is_numeric_dtype(dataset.dtype)


def _slab_ranges(shape: Tuple[int, ...], chunks: Optional[Tuple[int, ...]]):
    """Yield slices along axis 0 so large datasets never load fully."""
    if not shape:
        yield ()
        return
    step = int(shape[0])
    if chunks and len(chunks) == len(shape) and int(chunks[0]) > 0:
        step = min(step, int(chunks[0]))
    for start in range(0, int(shape[0]), max(1, step)):
        yield (slice(start, min(start + step, int(shape[0]))),)


def _write_compressed_dataset(src_ds: Any, dst_group: Any, name: str) -> bool:
    """Rewrite one dataset with Bitshuffle+LZ4; False → caller copies as-is.

    以 Bitshuffle+LZ4 重写一个数据集；返回 False 表示无法压缩（调用方原样复制）。
    """
    chunks = _choose_chunks(tuple(src_ds.shape), int(src_ds.dtype.itemsize))
    if chunks is None:
        return False
    kwargs: Dict[str, Any] = {"chunks": chunks}
    kwargs.update(_bitshuffle_lz4())
    create: Dict[str, Any] = {
        "shape": tuple(src_ds.shape),
        "dtype": src_ds.dtype,
    }
    if src_ds.maxshape and tuple(src_ds.maxshape) != tuple(src_ds.shape):
        create["maxshape"] = tuple(src_ds.maxshape)
    try:
        fillvalue = src_ds.fillvalue
        if fillvalue is not None:
            create["fillvalue"] = fillvalue
    except Exception:  # noqa: BLE001 — exotic dtypes may not expose fillvalue
        pass
    try:
        dst_ds = dst_group.create_dataset(name, **create, **kwargs)
    except Exception as exc:  # noqa: BLE001 — filter/dtype combination rejected
        log.warning("dataset %s: compression unavailable (%s), copying as-is", name, exc)
        return False
    try:
        for slab in _slab_ranges(tuple(src_ds.shape), chunks):
            dst_ds[slab] = src_ds[slab]
    except BaseException:
        del dst_group[name]
        raise
    _copy_attrs(src_ds, dst_ds)
    return True


def _copy_vds_dataset(src_ds: Any, dst_parent: Any, leaf: str, src_path: str) -> bool:
    """Re-create a virtual dataset (VDS) in dst with ABSOLUTE source paths.

    Eiger/NeXus master 文件的核心结构：entry/data/data 是 VDS，映射里的源文件名是
    相对路径（如 series_483_data_000001.h5）。原样 h5py copy 会保留相对路径，
    压缩文件写到别的目录后所有映射都解析失败、读回全是 fill value——校验阶段就表现
    为「数据不一致」。这里按原始 DCPL 逐条重映射，把源文件名改写为绝对路径，虚拟
    结构语义原样保留（读取端仍需要 data 系列文件在场，且必须 import hdf5plugin）。

    返回 False 表示无法安全重建（复杂子区映射等），由调用方原样复制。
    注意：不能直接把源文件的 SpaceID 传给新 DCPL 的 set_virtual——跨文件复用
    会报 "Invalid mapping selections"（2026-11-17 实测）。
    """
    import h5py

    dcpl = src_ds.id.get_create_plist()
    count = int(dcpl.get_virtual_count())
    if count <= 0:
        return False
    if int(dcpl.get_nfilters()) or tuple(src_ds.maxshape) != tuple(src_ds.shape):
        return False
    src_dir = os.path.dirname(src_path)

    try:
        layout = h5py.VirtualLayout(shape=tuple(src_ds.shape), dtype=src_ds.dtype)
        for index in range(count):
            file_name = dcpl.get_virtual_filename(index)
            dset_name = dcpl.get_virtual_dsetname(index)
            if not file_name or not dset_name:
                return False
            if not os.path.isabs(file_name):
                file_name = os.path.normpath(os.path.join(src_dir, file_name))
            vspace = dcpl.get_virtual_vspace(index)
            # 仅支持"整块连续"映射；带步长/多块的复杂映射走原样复制。
            lower, upper = vspace.get_select_bounds()
            selection = tuple(
                slice(int(lo), int(hi) + 1) for lo, hi in zip(lower, upper)
            )
            extent = 1
            for part in selection:
                extent *= max(0, part.stop - part.start)
            if extent != int(vspace.get_select_npoints()):
                return False
            with h5py.File(file_name, "r") as external:  # 只读打开原始数据文件
                target = external[dset_name]
                shape, dtype = tuple(target.shape), target.dtype
            layout[selection] = h5py.VirtualSource(
                file_name, dset_name, shape=shape, dtype=dtype
            )
        kwargs: Dict[str, Any] = {}
        try:
            fillvalue = src_ds.fillvalue
            if fillvalue is not None:
                kwargs["fillvalue"] = fillvalue
        except Exception:  # noqa: BLE001 — exotic dtypes
            pass
        dst_ds = dst_parent.create_virtual_dataset(leaf, layout, **kwargs)
    except Exception as exc:  # noqa: BLE001 — fall back to a verbatim copy
        log.warning("VDS %s: relink unavailable (%s), copying as-is", leaf, exc)
        if leaf in dst_parent:  # 半成品不能挡住后续原样复制
            del dst_parent[leaf]
        return False
    _copy_attrs(src_ds, dst_ds)
    return True


def _copy_h5_tree(src_file: Any, dst_file: Any) -> List[str]:
    """Recursively mirror groups/datasets/attrs; returns compressed dataset paths.

    递归复制 group/dataset/attrs，返回被重写为压缩数据集的路径列表。
    """
    import h5py

    compressed: List[str] = []
    _copy_attrs(src_file, dst_file)

    def visit(name: str, obj: Any) -> None:
        if isinstance(obj, h5py.Group):
            group = dst_file.require_group(name)
            _copy_attrs(obj, group)
            return
        if not isinstance(obj, h5py.Dataset):
            return
        if obj.name == "/" or name.endswith("/") or not name:
            return
        if getattr(obj, "is_virtual", False):
            # VDS：重建虚拟映射（源路径改写为绝对路径），不做数据压缩重写。
            # Relink relative VDS sources to absolute paths; fall through to a
            # verbatim copy when the mapping is too exotic to rebuild.
            parent_path, _, leaf = name.rpartition("/")
            parent = dst_file.require_group(parent_path) if parent_path else dst_file
            if _copy_vds_dataset(obj, parent, leaf, src_file.filename):
                return
        if _should_compress_dataset(obj):
            parent_path, _, leaf = name.rpartition("/")
            parent = dst_file.require_group(parent_path) if parent_path else dst_file
            if _write_compressed_dataset(obj, parent, leaf):
                compressed.append("/" + name)
                return
        # 原样复制（小数据集 / 非数值 / 虚拟 / 压缩不可用）
        # Copy as-is (small, non-numeric, virtual, or filter unavailable).
        src_file.copy(obj, dst_file, name=name)

    src_file.visititems(visit)
    return compressed


def _verify_h5_file(src_path: str, dst_path: str) -> Dict[str, Any]:
    """Compare every dataset value and every attrs mapping. 逐 dataset/attrs 比对。"""
    import h5py

    dataset_count = 0
    virtual_count = 0
    with h5py.File(src_path, "r") as src, h5py.File(dst_path, "r") as dst:
        if not _attrs_equal(src, dst):
            raise CompressError("root attributes mismatch / 根属性不一致")

        def visit(name: str, obj: Any) -> None:
            nonlocal dataset_count, virtual_count
            if isinstance(obj, h5py.Group):
                target = dst.get(name)
                if not isinstance(target, h5py.Group) or not _attrs_equal(obj, target):
                    raise CompressError(f"group mismatch: /{name} / 组不一致")
                return
            if not isinstance(obj, h5py.Dataset):
                return
            target = dst.get(name)
            if not isinstance(target, h5py.Dataset):
                raise CompressError(f"missing dataset: /{name} / 数据集缺失")
            dataset_count += 1
            if tuple(target.shape) != tuple(obj.shape) or target.dtype != obj.dtype:
                raise CompressError(f"dataset shape/dtype changed: /{name} / 形状或类型改变")
            if bool(getattr(obj, "is_virtual", False)) != bool(
                getattr(target, "is_virtual", False)
            ):
                raise CompressError(f"virtual dataset lost: /{name} / 虚拟数据集结构改变")
            if getattr(obj, "is_virtual", False):
                virtual_count += 1
            if not _attrs_equal(obj, target):
                raise CompressError(f"dataset attrs mismatch: /{name} / 数据集属性不一致")
            chunks = _choose_chunks(tuple(obj.shape), int(obj.dtype.itemsize))
            for slab in _slab_ranges(tuple(obj.shape), chunks):
                if not np.array_equal(obj[slab], target[slab]):
                    raise CompressError(f"dataset data mismatch: /{name} / 数据不一致")

        src.visititems(visit)

    return {
        "datasets": True,
        "attrs": True,
        "datasetCount": dataset_count,
        "virtualCount": virtual_count,
    }


def _compress_h5_job(src_path: str, final_path: str) -> Dict[str, Any]:
    """One HDF5 job: temp write → verify → atomic rename. 单个 HDF5 作业.

    重写后体积未变小（源已是同算法压缩）时不留输出，按 skipped 报告——
    绝不产出比原始文件更大的"压缩"文件。
    """
    dest_dir = os.path.dirname(final_path)
    original_bytes = os.path.getsize(src_path)
    fd, tmp_path = tempfile.mkstemp(
        prefix=".xfais-compress-", suffix=".h5.tmp", dir=dest_dir
    )
    os.close(fd)
    try:
        import h5py
        import hdf5plugin  # noqa: F401 — 必须先 import hdf5plugin 注册滤镜

        with h5py.File(src_path, "r") as src, h5py.File(tmp_path, "w") as dst:
            compressed_datasets = _copy_h5_tree(src, dst)
        compressed_bytes = os.path.getsize(tmp_path)
        if compressed_bytes > original_bytes:
            # 无收益：源文件已是最优压缩，重压缩只会更大 / no gain, drop the copy
            _remove_quietly(tmp_path)
            return _skipped_entry(
                src_path,
                "hdf5",
                original_bytes,
                f"no gain: {original_bytes} B → {compressed_bytes} B / "
                f"重压缩后体积未减小（源文件可能已是 Bitshuffle 压缩），已跳过",
            )
        checks = _verify_h5_file(src_path, tmp_path)
        os.replace(tmp_path, final_path)
    except BaseException as exc:  # noqa: BLE001 — per-file failure, batch continues
        _remove_quietly(tmp_path)
        return _failed_entry(src_path, "hdf5", original_bytes, exc)
    message = ""
    if checks.get("virtualCount"):
        # 让用户知道这份输出仍依赖原始 data 文件 / tell the user the VDS still needs them
        message = (
            f"{checks['virtualCount']} virtual dataset(s) relinked to absolute paths — "
            f"keep the original data files in place / "
            f"{checks['virtualCount']} 个虚拟数据集已改写为绝对路径，原始数据文件需保留在原位置"
        )
    return {
        "path": src_path,
        "outputPath": final_path,
        "kind": "hdf5",
        "algorithm": HDF5_ALGORITHM,
        "originalBytes": original_bytes,
        "compressedBytes": compressed_bytes,
        "ratio": compression_ratio(original_bytes, compressed_bytes),
        "status": "ok",
        "checks": checks,
        "compressedDatasets": len(compressed_datasets),
        "message": message,
    }


# ---------------------------------------------------------------------------
# Shared job helpers / 共用作业辅助
# ---------------------------------------------------------------------------


def _remove_quietly(path: str) -> None:
    """Best-effort removal of OUR temp file only. 仅清理本服务生成的临时文件。"""
    try:
        os.remove(path)
    except OSError:
        pass


def _failed_entry(src_path: str, kind: str, original_bytes: int, exc: BaseException) -> Dict[str, Any]:
    reason = str(exc) if isinstance(exc, CompressError) else f"{type(exc).__name__}: {exc}"
    return {
        "path": src_path,
        "outputPath": "",
        "kind": kind,
        "algorithm": _algorithm(kind),
        "originalBytes": original_bytes,
        "compressedBytes": 0,
        "ratio": 0.0,
        "status": "failed",
        "checks": {},
        "message": reason,
    }


def _skipped_entry(src_path: str, kind: str, original_bytes: int, message: str) -> Dict[str, Any]:
    """File left untouched on purpose (already compressed / no gain). 有意跳过。

    skipped 不代表失败：没有输出文件，原始文件保持原样。
    """
    return {
        "path": src_path,
        "outputPath": "",
        "kind": kind,
        "algorithm": _algorithm(kind),
        "originalBytes": original_bytes,
        "compressedBytes": 0,
        "ratio": 0.0,
        "status": "skipped",
        "checks": {},
        "message": message,
    }


# ---------------------------------------------------------------------------
# Input scanning / 输入扫描
# ---------------------------------------------------------------------------


def _require_abs_path(raw: Any, field: str) -> str:
    """Validate a read-only input path (absolute, no `..`, exists). 只读输入校验。"""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{field} is required / {field} 不能为空")
    if "\x00" in raw:
        raise ValueError(f"invalid {field}: NUL byte / 路径含非法字符")
    if ".." in PurePath(raw).parts:
        raise ValueError(f"invalid {field}: '..' not allowed / 路径含 .. 段，已拒绝")
    path = os.path.abspath(os.path.expanduser(raw))
    if not os.path.isabs(path):
        raise ValueError(f"invalid {field}: must be absolute / 路径必须是绝对路径")
    return path


def _require_input_dir(raw: Any) -> str:
    path = _require_abs_path(raw, "input_dir")
    if not os.path.isdir(path):
        raise ValueError(f"input directory not found / 输入目录不存在：{path}")
    return path


def collect_inputs(
    input_dir: str = "",
    files: Optional[List[str]] = None,
    recursive: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Collect supported files (read-only). Returns (entries, skipped).

    收集受支持的文件（只读）。返回（条目, 跳过项）；条目按路径排序去重。
    """
    entries: List[Dict[str, Any]] = []
    skipped: List[Dict[str, str]] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        if len(entries) >= MAX_FILES:
            raise ValueError(
                f"too many files (>{MAX_FILES}) / 文件数超过上限 {MAX_FILES}"
            )
        real = os.path.realpath(path)
        if real in seen:
            return
        kind = _file_kind(path)
        if kind is None:
            skipped.append({"path": path, "reason": "unsupported type / 不支持的类型"})
            return
        try:
            size = os.path.getsize(path)
        except OSError as exc:
            skipped.append({"path": path, "reason": f"{type(exc).__name__}: {exc}"})
            return
        limit = MAX_TIFF_BYTES if kind == "tiff" else MAX_HDF5_BYTES
        if size > limit:
            skipped.append({"path": path, "reason": "file too large / 文件超过单文件上限"})
            return
        seen.add(real)
        entries.append({"path": real, "name": os.path.basename(path), "kind": kind, "size": size})

    selected = [f for f in (files or []) if isinstance(f, str) and f.strip()]
    if selected:
        for raw in selected:
            path = _require_abs_path(raw, "files[]")
            if not os.path.isfile(path):
                raise ValueError(f"file not found / 文件不存在：{path}")
            add(path)
    elif input_dir:
        root = _require_input_dir(input_dir)
        if recursive:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames.sort()
                for filename in sorted(filenames):
                    if _file_kind(filename):
                        add(os.path.join(dirpath, filename))
        else:
            for filename in sorted(os.listdir(root)):
                full = os.path.join(root, filename)
                if os.path.isfile(full) and _file_kind(filename):
                    add(full)
    else:
        raise ValueError("input_dir or files is required / 请选择文件夹或文件")

    entries.sort(key=lambda item: item["path"].lower())
    return entries, skipped


def _stats(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    tiff = [e for e in entries if e["kind"] == "tiff"]
    hdf5 = [e for e in entries if e["kind"] == "hdf5"]
    return {
        "totalCount": len(entries),
        "tiffCount": len(tiff),
        "hdf5Count": len(hdf5),
        "totalBytes": sum(int(e["size"]) for e in entries),
        "tiffBytes": sum(int(e["size"]) for e in tiff),
        "hdf5Bytes": sum(int(e["size"]) for e in hdf5),
    }


# ---------------------------------------------------------------------------
# Output path planning / 输出路径规划
# ---------------------------------------------------------------------------


def _output_relative_parts(entry_path: str, root: str) -> List[str]:
    """Relative directory parts from root; rejects traversal eagerly.

    计算相对根目录的目录分量；含 `..` 一律拒绝（输出路径不得穿越）。
    """
    try:
        rel = os.path.relpath(entry_path, root)
    except ValueError:
        rel = os.path.basename(entry_path)
    parts = [part for part in PurePath(rel).parts if part not in ("", ".")]
    if any(part == ".." for part in parts) or os.path.isabs(rel):
        return []
    return parts[:-1]


def _confined_output_path(root_real: str, rel_parts: List[str], filename: str) -> str:
    """Join under root_real and enforce containment on the final path.

    拼接输出路径并在最终位置做 realpath + commonpath 圈定；相对分量里出现
    `..` 直接拒绝（不静默丢弃，便于报告失败原因）。
    """
    if any(part == ".." for part in rel_parts):
        raise ValueError("output path contains '..' / 输出路径含 .. 段，已拒绝")
    safe_parts = [p for p in rel_parts if p not in ("", ".")]
    candidate = os.path.abspath(os.path.join(root_real, *safe_parts, filename))
    root_norm = os.path.normpath(root_real)
    try:
        inside = os.path.commonpath([root_norm, candidate]) == root_norm
    except ValueError:  # different drives / 跨盘符
        inside = False
    if not inside:
        raise ValueError("output path escapes output dir / 输出路径越出输出目录")
    return candidate


def _unique_output_name(used: set[str], dir_parts: List[str], filename: str) -> str:
    """Add a numeric suffix when two sources map to the same output name.

    同名冲突时追加数字后缀（不覆盖、不丢弃）。
    """
    key = os.path.normcase(os.path.join(*dir_parts, filename))
    if key not in used:
        used.add(key)
        return filename
    stem, ext = os.path.splitext(filename)
    index = 2
    while True:
        candidate = f"{stem}_{index}{ext}"
        key = os.path.normcase(os.path.join(*dir_parts, candidate))
        if key not in used:
            used.add(key)
            return candidate
        index += 1


def _planned_outputs(entries: List[Dict[str, Any]], output_dir: str, root: str) -> List[Dict[str, Any]]:
    """Attach outputPath to each entry (dir structure preserved). 规划输出路径。"""
    used: set[str] = set()
    source_paths = {os.path.realpath(e["path"]) for e in entries}
    planned: List[Dict[str, Any]] = []
    for entry in entries:
        dir_parts = _output_relative_parts(entry["path"], root)
        stem = Path(entry["path"]).stem
        ext = ".tif" if entry["kind"] == "tiff" else ".h5"
        filename = _unique_output_name(used, dir_parts, f"{stem}{ext}")
        out_path = _confined_output_path(output_dir, dir_parts, filename)
        if os.path.realpath(out_path) in source_paths:
            planned.append({**entry, "outputPath": "", "dirParts": dir_parts,
                            "error": "output equals a source file / 输出路径与原始文件相同"})
            continue
        planned.append({**entry, "outputPath": out_path, "dirParts": dir_parts, "error": ""})
    return planned


# ---------------------------------------------------------------------------
# Progress bridge / 进度桥
# ---------------------------------------------------------------------------


class _ProgressBridge:
    """Thread-safe, throttled progress forwarder (~10 Hz). 线程安全进度转发。"""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        send_progress: Callable[[float, str], Awaitable[None]],
    ) -> None:
        self._loop = loop
        self._send = send_progress
        self._last = 0.0

    def report(self, fraction: float, message: str) -> None:
        now = time.monotonic()
        if now - self._last < 0.1 and fraction < 1.0:
            return
        self._last = now
        clamped = max(0.0, min(1.0, fraction))
        asyncio.run_coroutine_threadsafe(self._send(clamped, message), self._loop)


# ---------------------------------------------------------------------------
# Actions / 动作处理
# ---------------------------------------------------------------------------


def _err(message: str, message_zh: str = "") -> Dict[str, Any]:
    text = f"{message} / {message_zh}" if message_zh else message
    return {"status": "error", "message": text}


def _action_probe(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Scan the selection and return counts + sizes (no compression)."""
    try:
        entries, skipped = collect_inputs(
            input_dir=str(payload.get("input_dir") or ""),
            files=payload.get("files"),
            recursive=bool(payload.get("recursive", True)),
        )
    except ValueError as exc:
        return _err(str(exc))
    stats = _stats(entries)
    sample = [
        {"path": e["path"], "name": e["name"], "kind": e["kind"], "size": e["size"]}
        for e in entries[:SAMPLE_LIST_LIMIT]
    ]
    return {
        "status": "ok",
        "action": "probe",
        "stats": stats,
        "sample": sample,
        "truncated": len(entries) > len(sample),
        "skipped": skipped[:SAMPLE_LIST_LIMIT],
        "skippedCount": len(skipped),
    }


def _action_trial(payload: Dict[str, Any], bridge: _ProgressBridge) -> Dict[str, Any]:
    """Compress the FIRST file into a temp dir, verify, then discard."""
    try:
        entries, _skipped = collect_inputs(
            input_dir=str(payload.get("input_dir") or ""),
            files=payload.get("files"),
            recursive=bool(payload.get("recursive", True)),
        )
    except ValueError as exc:
        return _err(str(exc))
    if not entries:
        return _err("no supported files found", "未找到受支持的 TIFF/HDF5 文件")
    entry = entries[0]
    if int(entry["size"]) > TRIAL_MAX_BYTES:
        return _err(
            f"trial file too large ({entry['size']} bytes)",
            "试压缩文件超过 2 GiB，请直接批量压缩",
        )

    bridge.report(0.1, f"试压缩：{entry['name']} / Trial: {entry['name']}")
    temp_dir = tempfile.mkdtemp(prefix="xfais-compress-trial-")
    base = Path(entry["path"]).stem
    try:
        if entry["kind"] == "tiff":
            job = _compress_tiff_job(entry["path"], os.path.join(temp_dir, base + ".tif"))
        else:
            job = _compress_h5_job(entry["path"], os.path.join(temp_dir, base + ".h5"))
    finally:
        # 试压缩产物立即丢弃（不留在用户目录） / trial output is discarded
        for child in os.listdir(temp_dir):
            _remove_quietly(os.path.join(temp_dir, child))
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass
    verified = job["status"] in ("ok", "skipped")
    # skipped 有两种来源（TIFF 已 Deflate / HDF5 无收益），说明文字一律取自作业本身。
    # Skipped covers both "TIFF already Deflate" and "HDF5 no gain" — use the job message.
    note = job.get("message", "") if job["status"] == "skipped" else ""
    return {
        **job,
        "action": "trial",
        "sourceCount": len(entries),
        "verified": verified,
        "status": "ok" if verified else "error",
        "note": note,
        "message": job.get("message") or ("" if verified else "verification failed / 校验未通过"),
        "checkedFile": entry["name"],
    }


def _batch_worker_count(payload: Dict[str, Any], count: int) -> int:
    raw = payload.get("max_workers")
    try:
        requested = int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        requested = 0
    if requested <= 0:
        requested = min(8, os.cpu_count() or 4)
    return max(1, min(requested, 32, max(1, count)))


def _action_batch(
    payload: Dict[str, Any],
    bridge: _ProgressBridge,
    cancel_event: asyncio.Event,
    *,
    validate_output_dir: bool = True,
) -> Dict[str, Any]:
    """Batch compress → verify → write into output_dir (originals untouched)."""
    try:
        if validate_output_dir:
            output_dir = validated_output_path(payload.get("output_dir"), field="output_dir")
        else:
            # Backend-internal staging (server_fs download prep): the
            # destination is chosen by the server itself inside the session
            # workspace, so the user-output gate does not apply. The raw
            # value is still normalized; containment is the caller's duty.
            # 后端内部暂存（server_fs 下载准备）：输出目录由服务器自选
            # （会话工作区内），不适用用户输出路径门；仍做归一化，containment
            # 由调用方负责。
            raw_out = payload.get("output_dir")
            if not isinstance(raw_out, str) or not raw_out.strip() or "\x00" in raw_out:
                return _err("invalid output_dir: must be a non-empty string", "输出目录非法")
            output_dir = os.path.realpath(os.path.abspath(os.path.expanduser(raw_out)))
    except ValueError as exc:
        return _err(str(exc))
    try:
        entries, skipped = collect_inputs(
            input_dir=str(payload.get("input_dir") or ""),
            files=payload.get("files"),
            recursive=bool(payload.get("recursive", True)),
        )
    except ValueError as exc:
        return _err(str(exc))
    if not entries:
        return _err("no supported files found", "未找到受支持的 TIFF/HDF5 文件")

    input_dir_raw = str(payload.get("input_dir") or "")
    if input_dir_raw:
        root = _require_input_dir(input_dir_raw)
        if os.path.realpath(root) == os.path.realpath(output_dir):
            return _err(
                "output dir must differ from the input dir",
                "输出目录不能与输入目录相同（避免覆盖原始文件）",
            )
    else:
        parents = sorted({os.path.dirname(os.path.realpath(e["path"])) for e in entries})
        if len(parents) > 1:
            try:
                root = os.path.commonpath(parents)
            except ValueError:  # different drives / 跨盘符
                root = parents[0]
        else:
            root = parents[0]

    planned = _planned_outputs(entries, output_dir, root)
    for item in planned:
        if item["error"]:
            continue
        try:
            os.makedirs(os.path.dirname(item["outputPath"]), exist_ok=True)
        except OSError as exc:
            item["error"] = f"{type(exc).__name__}: {exc}"

    total = len(planned)
    done = 0
    started = time.perf_counter()
    results: List[Dict[str, Any]] = []
    tiff_jobs = [
        item for item in planned
        if item["kind"] == "tiff" and not item["error"]
    ]
    h5_jobs = [
        item for item in planned
        if item["kind"] == "hdf5" and not item["error"]
    ]
    cancelled = cancel_event.is_set()

    def record(item: Dict[str, Any], result: Dict[str, Any]) -> None:
        nonlocal done
        # 强制输出路径为规划值，防止作业返回篡改路径 / pin the planned path
        result["outputPath"] = item["outputPath"] if result["status"] == "ok" else ""
        results.append(result)
        done += 1
        bridge.report(
            done / max(1, total),
            f"已压缩 {done}/{total}：{item['name']} / Compressed {done}/{total}: {item['name']}",
        )

    for item in planned:
        if item["error"]:
            results.append(_failed_entry(item["path"], item["kind"], int(item["size"]),
                                         CompressError(item["error"])))
            done += 1

    bridge.report(max(0.0, done / max(1, total)), f"准备压缩 {total} 个文件 / Preparing {total} files")

    # ---- TIFF：线程池（zlib 压缩在 C 层释放 GIL）/ TIFF: thread pool ----
    if tiff_jobs and not cancel_event.is_set():
        workers = _batch_worker_count(payload, len(tiff_jobs))
        pending: Dict[Any, Dict[str, Any]] = {}
        queue = iter(tiff_jobs)
        pool = ThreadPoolExecutor(max_workers=workers)
        try:
            def fill() -> None:
                while len(pending) < workers * 2:
                    try:
                        item = next(queue)
                    except StopIteration:
                        return
                    pending[pool.submit(_compress_tiff_job, item["path"],
                                        item["outputPath"])] = item

            fill()
            while pending:
                if cancel_event.is_set():
                    cancelled = True
                    break
                for future in as_completed(list(pending)):
                    item = pending.pop(future)
                    try:
                        result = future.result()
                    except BaseException as exc:  # noqa: BLE001
                        result = _failed_entry(item["path"], item["kind"], int(item["size"]), exc)
                    record(item, result)
                    fill()
                    break
        finally:
            # 取消时丢弃尚未开始的作业（不写任何输出）/ drop queued jobs on cancel
            pool.shutdown(wait=True, cancel_futures=cancelled)

    # ---- HDF5：串行（h5py 全局锁，并行无收益）/ HDF5: serial (global HDF5 lock) ----
    for item in h5_jobs:
        if cancel_event.is_set():
            cancelled = True
            break
        try:
            result = _compress_h5_job(item["path"], item["outputPath"])
        except BaseException as exc:  # noqa: BLE001
            result = _failed_entry(item["path"], item["kind"], int(item["size"]), exc)
        record(item, result)

    ok = [r for r in results if r["status"] == "ok"]
    failed = [r for r in results if r["status"] == "failed"]
    skipped_results = [r for r in results if r["status"] == "skipped"]
    original_bytes = sum(int(r["originalBytes"]) for r in ok)
    compressed_bytes = sum(int(r["compressedBytes"]) for r in ok)
    elapsed = round(time.perf_counter() - started, 2)

    report_files = results[:REPORT_FILE_LIMIT]
    bridge.report(1.0, f"完成：成功 {len(ok)}，失败 {len(failed)} / Done")

    return {
        "status": "ok",
        "action": "batch",
        "outputDir": output_dir,
        "total": total,
        "success": len(ok),
        "failed": len(failed),
        "skipped": len(skipped_results),
        "originalBytes": original_bytes,
        "compressedBytes": compressed_bytes,
        "ratio": compression_ratio(original_bytes, compressed_bytes),
        "savedBytes": max(0, original_bytes - compressed_bytes),
        "elapsed": elapsed,
        "files": report_files,
        "filesOmitted": max(0, len(results) - len(report_files)),
        "failures": [{"path": r["path"], "reason": r["message"]} for r in failed][:500],
        "scanSkipped": skipped[:200],
        "cancelled": cancelled,
        "hdf5ReaderNote": (
            "HDF5 输出使用 Bitshuffle+LZ4 滤镜，读取端需 import hdf5plugin / "
            "HDF5 output requires hdf5plugin on the reading side"
        ),
    }


# ---------------------------------------------------------------------------
# Entry point / 唯一入口
# ---------------------------------------------------------------------------


async def handle_compress(
    payload: dict,
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict:
    """Single entry point of the lossless-compression service.

    无损压缩服务的唯一入口。动作：probe / trial / batch / cancel。
    重量级工作全部在线程中执行，进度经线程安全桥回送。
    """
    action = str(payload.get("action") or "probe")

    if action == "cancel":
        return {"status": "ok", "action": "cancel", "cancelled": cancel_event.is_set()}

    if action == "probe":
        await send_progress(0.1, "扫描输入 / Scanning input")
        result = await asyncio.to_thread(_action_probe, payload)
        if result.get("status") == "ok":
            await send_progress(1.0, "扫描完成 / Scan complete")
        return result

    loop = asyncio.get_running_loop()
    bridge = _ProgressBridge(loop, send_progress)

    if action == "trial":
        result = await asyncio.to_thread(_action_trial, payload, bridge)
        if result.get("status") == "ok":
            await send_progress(1.0, "试压缩完成 / Trial complete")
        return result

    if action == "batch":
        return await asyncio.to_thread(_action_batch, payload, bridge, cancel_event)

    return _err(f"Unknown action: {action!r}", f"未知操作：{action!r}")


async def compress_files_for_staging(
    files: list[str],
    output_dir: str,
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict:
    """Backend-internal batch compression into a server-chosen staging dir.

    Used by the server_fs download-staging flow, where the destination is
    picked by the backend itself (inside the session workspace) so the
    user-supplied output gate (:func:`validated_output_path`) does not apply;
    containment is the caller's responsibility. This function is not routed,
    so a client payload can never reach the unvalidated path.
    后端内部批量压缩到服务器自选暂存目录（server_fs 下载暂存专用）：输出
    目录由后端自选（会话工作区内），不经过用户输出路径门；本函数不在路由
    表内，客户端载荷无法触达未校验通道。
    """
    loop = asyncio.get_running_loop()
    bridge = _ProgressBridge(loop, send_progress)
    result = await asyncio.to_thread(
        _action_batch,
        {"action": "batch", "files": list(files), "output_dir": output_dir},
        bridge,
        cancel_event,
        validate_output_dir=False,
    )
    if result.get("status") == "ok":
        await send_progress(1.0, "压缩完成 / Compression complete")
    return result
