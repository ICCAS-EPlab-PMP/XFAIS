#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
image_loader.py — H5Handler & ImageLoader: EDF/TIFF/HDF5 loading, frame selection, 4D channels
图像加载器 — H5Handler 和 ImageLoader：EDF/TIFF/HDF5 加载、帧选择、4D通道
"""

from __future__ import annotations

from functools import lru_cache
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fabio
import h5py
import numpy as np

EIGER_4D_CHANNELS: list[str] = ["LowThresholdData", "HighThresholdData", "DiffData"]
H5_DEAD_PIXEL_THRESHOLD: float = 4.25e9
SUPPORTED_IMAGE_EXTS: tuple[str, ...] = (".edf", ".tif", ".tiff", ".h5")


def _normalize_path(file_path: str | Path) -> str:
    """Return a stable absolute path for cache keys.
    返回用于缓存键的稳定绝对路径。"""
    return str(Path(file_path).resolve())


def _file_signature(file_path: str | Path) -> tuple[str, int, int]:
    """Build a file signature from path + mtime + size.
    基于路径 + 修改时间 + 文件大小构建文件签名。"""
    normalized = _normalize_path(file_path)
    stat = Path(normalized).stat()
    return normalized, stat.st_mtime_ns, stat.st_size


def _copy_optional_array(array: Optional[np.ndarray]) -> Optional[np.ndarray]:
    """Return a defensive copy for cached arrays.
    为缓存数组返回防御性副本。"""
    if array is None:
        return None
    return np.array(array, copy=True)


def _coerce_channel_index(channel: Optional[str], n_channels: int) -> int:
    """Resolve a channel selector to a valid integer index.
    将通道选择器解析为有效整数索引。"""
    if n_channels == len(EIGER_4D_CHANNELS) and channel in EIGER_4D_CHANNELS:
        return EIGER_4D_CHANNELS.index(channel)
    try:
        ch_idx = int(channel) if channel is not None else 0
    except (TypeError, ValueError):
        ch_idx = 0
    return max(0, min(ch_idx, n_channels - 1))


def _prepare_frame(raw_2d: Any, is_uint32: bool) -> tuple[np.ndarray, np.ndarray]:
    """Convert raw detector frame to float32 + dead-mask pair.
    将原始探测器帧转换为 float32 + 死像素掩膜。"""
    raw_np = np.asarray(raw_2d)
    if is_uint32:
        dead_mask = raw_np > np.uint32(min(H5_DEAD_PIXEL_THRESHOLD, np.iinfo(np.uint32).max))
    else:
        dead_mask = raw_np > H5_DEAD_PIXEL_THRESHOLD
    arr = raw_np.astype(np.float32)
    arr[dead_mask] = -1.0
    return arr, dead_mask


@lru_cache(maxsize=32)
def _cached_h5_dataset_scan(
    normalized_path: str,
    _mtime_ns: int,
    _file_size: int,
) -> tuple[tuple[str, dict[str, Any]], ...]:
    """Cache HDF5 dataset tree scans by file signature.
    按文件签名缓存 HDF5 数据集树扫描结果。"""
    datasets_info: dict[str, dict[str, Any]] = {}
    try:
        with h5py.File(normalized_path, "r") as fh:

            def _visitor(name: str, obj: Any) -> None:
                if not isinstance(obj, h5py.Dataset):
                    return
                shape = tuple(obj.shape)
                ndim = len(shape)
                dtype = str(obj.dtype)

                if np.issubdtype(obj.dtype, np.unsignedinteger):
                    dtype_kind = "uint"
                elif np.issubdtype(obj.dtype, np.signedinteger):
                    dtype_kind = "int"
                elif np.issubdtype(obj.dtype, np.floating):
                    dtype_kind = "float"
                else:
                    dtype_kind = "other"

                is_image = ndim >= 2 and shape[-2] >= 2 and shape[-1] >= 2
                if ndim == 2:
                    n_frames, n_ch, h, w = None, None, shape[0], shape[1]
                elif ndim == 3:
                    n_frames, n_ch, h, w = shape[0], None, shape[1], shape[2]
                elif ndim == 4:
                    n_frames, n_ch, h, w = shape[0], shape[1], shape[2], shape[3]
                else:
                    n_frames = shape[0] if ndim > 0 else None
                    n_ch = None
                    h = shape[-2] if ndim >= 2 else None
                    w = shape[-1] if ndim >= 1 else None

                datasets_info[name] = {
                    "shape": shape,
                    "ndim": ndim,
                    "dtype": dtype,
                    "dtype_kind": dtype_kind,
                    "n_frames": n_frames,
                    "n_channels": n_ch,
                    "height": h,
                    "width": w,
                    "is_image": is_image,
                }

            fh.visititems(_visitor)
    except Exception as exc:
        raise IOError(f"Cannot read H5 structure: {normalized_path}: {exc}") from exc
    return tuple((name, info.copy()) for name, info in datasets_info.items())


@lru_cache(maxsize=16)
def _cached_h5_frame(
    normalized_path: str,
    _mtime_ns: int,
    _file_size: int,
    dataset_path: str,
    frame_index: int,
    channel: Optional[str],
) -> tuple[np.ndarray, np.ndarray]:
    """Cache a recently accessed HDF5 frame.
    缓存最近访问的 HDF5 单帧。"""
    with h5py.File(normalized_path, "r") as fh:
        if dataset_path not in fh:
            raise KeyError(f"Dataset '{dataset_path}' not found in {normalized_path}")
        ds = fh[dataset_path]
        if not isinstance(ds, h5py.Dataset):
            raise TypeError(f"'{dataset_path}' is not a dataset in {normalized_path}")
        ndim = ds.ndim
        shape = ds.shape
        is_uint32 = ds.dtype == np.uint32

        if ndim == 2:
            raw = ds[()]
        elif ndim == 3:
            idx = max(0, min(frame_index, shape[0] - 1))
            raw = ds[idx]
        elif ndim == 4:
            idx = max(0, min(frame_index, shape[0] - 1))
            ch_idx = _coerce_channel_index(channel, shape[1])
            raw = ds[idx, ch_idx, :, :]
        else:
            raise ValueError(f"Unsupported dataset shape {shape} in '{dataset_path}'")

    return _prepare_frame(raw, is_uint32)


@lru_cache(maxsize=16)
def _cached_disk_probe(
    normalized_path: str,
    _mtime_ns: int,
    _file_size: int,
) -> tuple[int, int | None, int | None]:
    """Cache lightweight frame-count/shape metadata for EDF/TIFF files.
    缓存 EDF/TIFF 文件的轻量帧数/形状元数据。"""
    with fabio.open(normalized_path) as img:
        raw = img.data
        n_frames = max(int(getattr(img, "nframes", 1) or 1), 1)
        if raw.ndim > 2:
            raw = raw[0]
    height = int(raw.shape[0]) if raw.ndim >= 2 else None
    width = int(raw.shape[1]) if raw.ndim >= 2 else None
    return n_frames, height, width


@lru_cache(maxsize=32)
def _cached_disk_frame(
    normalized_path: str,
    _mtime_ns: int,
    _file_size: int,
    frame_index: int,
) -> np.ndarray:
    """Cache a recently decoded EDF/TIFF single frame.
    缓存最近解码的 EDF/TIFF 单帧。"""
    with fabio.open(normalized_path) as img:
        n_frames = max(int(getattr(img, "nframes", 1) or 1), 1)
        if n_frames > 1 and hasattr(img, "getframe"):
            idx = max(0, min(frame_index, n_frames - 1))
            raw = img.getframe(idx).data.copy()
        else:
            raw = img.data
        if raw.ndim > 2:
            raw = raw[0]
    return raw.astype(np.float32)


class H5Handler:
    """Utilities for inspecting and loading HDF5 detector files.
    用于检测和加载HDF5探测器文件的工具类。"""

    @staticmethod
    def find_datasets(h5_file_path: str | Path) -> dict[str, dict[str, Any]]:
        """Recursively scan an HDF5 file and return all dataset paths with full metadata.
        递归扫描HDF5文件，返回所有数据集路径及完整元信息。"""
        signature = _file_signature(h5_file_path)
        entries = _cached_h5_dataset_scan(*signature)
        return {name: info.copy() for name, info in entries}

    @staticmethod
    def pick_default_dataset(paths: list[str]) -> Optional[str]:
        """Auto-select the most likely image dataset from a list of paths.
        从路径列表中自动选择最可能的图像数据集。"""
        if not paths:
            return None
        data_paths = [p for p in paths if p.endswith("/data") or p == "data"]
        if data_paths:
            data_paths.sort(key=lambda x: x.count("/"), reverse=True)
            return data_paths[0]
        return paths[0]

    @staticmethod
    def load_2d_array(
        h5_path: str | Path,
        dataset_path: str,
        channel: Optional[str] = None,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray]]:
        """Load a 2-D image array from an HDF5 dataset.
        从HDF5数据集加载2D图像数组。

        Supports (H,W), (N,H,W), and (N,C,H,W) shapes.
        返回 (data_float32, dead_pixel_mask_bool)。
        """
        return H5Handler.load_frame(h5_path, dataset_path, frame_index=0, channel=channel)

    @staticmethod
    def load_frame(
        h5_path: str | Path,
        dataset_path: str,
        frame_index: int = 0,
        channel: Optional[str] = None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Load a single frame by index from an HDF5 dataset.
        按索引从HDF5数据集加载单帧，返回 (data_float32, dead_pixel_mask_bool)。

        Unlike load_all_frames, this only reads one 2-D slice — O(1) I/O.
        """
        signature = _file_signature(h5_path)
        arr, dead_mask = _cached_h5_frame(*signature, dataset_path, frame_index, channel)
        return np.array(arr, copy=True), np.array(dead_mask, copy=True)

    @staticmethod
    def load_all_frames(
        h5_path: str | Path,
        dataset_path: str,
        channel: Optional[str] = None,
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """Load all frames from an HDF5 dataset.
        从HDF5数据集加载所有帧，返回 list of (data_float32, dead_mask_bool)。"""
        h5_path = str(h5_path)
        frames: list[tuple[np.ndarray, np.ndarray]] = []

        with h5py.File(h5_path, "r") as fh:
            if dataset_path not in fh:
                raise KeyError(f"Dataset '{dataset_path}' not found in {h5_path}")
            ds = fh[dataset_path]
            if not isinstance(ds, h5py.Dataset):
                raise TypeError(f"'{dataset_path}' is not a dataset in {h5_path}")
            ndim = ds.ndim
            shape = ds.shape
            is_uint32 = ds.dtype == np.uint32

            def _make_frame(raw_2d: Any) -> tuple[np.ndarray, np.ndarray]:
                return _prepare_frame(raw_2d, is_uint32)

            if ndim == 2:
                frames.append(_make_frame(ds[()]))
            elif ndim == 3:
                for i in range(shape[0]):
                    frames.append(_make_frame(ds[i]))
            elif ndim == 4:
                n_ch = shape[1]
                if n_ch == len(EIGER_4D_CHANNELS) and channel in EIGER_4D_CHANNELS:
                    ch_idx = EIGER_4D_CHANNELS.index(channel)
                else:
                    try:
                        ch_idx = int(channel) if channel is not None else 0
                    except (TypeError, ValueError):
                        ch_idx = 0
                    ch_idx = max(0, min(ch_idx, n_ch - 1))
                for i in range(shape[0]):
                    frames.append(_make_frame(ds[i, ch_idx, :, :]))
            else:
                raise ValueError(f"Unsupported dataset shape {shape} in '{dataset_path}'")

        return frames


class ImageLoader:
    """Load 2-D detector images from EDF, TIFF, or HDF5 files on disk.
    从磁盘上的EDF、TIFF或HDF5文件加载2D探测器图像。"""

    @staticmethod
    def load(
        file_path: str | Path,
        h5_dataset_path: Optional[str] = None,
        h5_channel: Optional[str] = None,
        frame_index: int = 0,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray], dict]:
        """Load image data from a file path.
        从文件路径加载图像数据。

        ``frame_index`` selects which frame of a multi-frame (3-D/4-D) HDF5
        dataset to read (default first frame). For EDF/TIFF it is ignored.
        Returns (data, dead_mask, meta). dead_mask is non-None only for HDF5.
        """
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        meta: dict = {"filename": file_path.name, "ext": ext}

        try:
            if ext == ".h5":
                # Auto-select the default image dataset when none is specified —
                # the integration routes have no dataset selector in the UI, so
                # without this every .h5 file fails with "No data loaded".
                # Mirrors the viewer/open_file flow (H5Handler.find_datasets +
                # pick_default_dataset).
                if not h5_dataset_path:
                    datasets = H5Handler.find_datasets(str(file_path))
                    h5_dataset_path = H5Handler.pick_default_dataset(list(datasets.keys()))
                if not h5_dataset_path:
                    return None, None, meta
                data, dead_mask = H5Handler.load_frame(
                    str(file_path), h5_dataset_path,
                    frame_index=frame_index, channel=h5_channel,
                )
                meta["h5_dataset"] = h5_dataset_path
                meta["frame_index"] = max(0, int(frame_index))
                if h5_channel:
                    meta["h5_channel"] = h5_channel
                return data, dead_mask, meta

            return ImageLoader.load_frame(file_path, frame_index=0)

        except Exception as exc:
            raise IOError(f"Failed to load: {file_path}: {exc}") from exc

    @staticmethod
    def probe(file_path: str | Path) -> dict[str, Any]:
        """Inspect a disk image file and return frame-count/shape metadata.
        检查磁盘图像文件并返回帧数/形状元数据。"""
        file_path = Path(file_path)
        signature = _file_signature(file_path)
        n_frames, height, width = _cached_disk_probe(*signature)
        return {
            "filename": file_path.name,
            "ext": file_path.suffix.lower(),
            "n_frames": n_frames,
            "height": height,
            "width": width,
        }

    @staticmethod
    def load_frame(
        file_path: str | Path,
        frame_index: int = 0,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray], dict]:
        """Load one frame from EDF/TIFF-style disk images.
        从 EDF/TIFF 类磁盘图像中加载单帧。"""
        file_path = Path(file_path)
        signature = _file_signature(file_path)
        n_frames, _height, _width = _cached_disk_probe(*signature)
        raw = _cached_disk_frame(*signature, frame_index)
        meta: dict = {
            "filename": file_path.name,
            "ext": file_path.suffix.lower(),
            "frame_index": max(0, min(frame_index, max(n_frames - 1, 0))),
            "n_frames": n_frames,
        }
        return np.array(raw, copy=True), None, meta

    @staticmethod
    def load_all_frames(
        file_path: str | Path,
        h5_dataset_path: Optional[str] = None,
        h5_channel: Optional[str] = None,
    ) -> list[tuple[Optional[np.ndarray], Optional[np.ndarray], dict]]:
        """Load all frames from a file.
        从文件加载所有帧。

        Returns list of (data, dead_mask, meta).
        """
        file_path = Path(file_path)
        ext = file_path.suffix.lower()
        base_meta: dict = {"filename": file_path.name, "ext": ext}

        try:
            if ext == ".h5":
                if not h5_dataset_path:
                    return [(None, None, base_meta)]
                frame_list = H5Handler.load_all_frames(
                    str(file_path), h5_dataset_path, channel=h5_channel
                )
                h5_results: list[tuple] = []
                for fi, (arr, dmask) in enumerate(frame_list):
                    meta = dict(base_meta)
                    meta["h5_dataset"] = h5_dataset_path
                    meta["frame_index"] = fi
                    meta["n_frames"] = len(frame_list)
                    if h5_channel:
                        meta["h5_channel"] = h5_channel
                    h5_results.append((arr, dmask, meta))
                return h5_results

            with fabio.open(str(file_path)) as img:
                n_frames = max(int(getattr(img, "nframes", 1) or 1), 1)
                getframe = getattr(img, "getframe", None)
                disk_results: list[tuple[Optional[np.ndarray], Optional[np.ndarray], dict]] = []
                for fi in range(n_frames):
                    if n_frames > 1 and callable(getframe):
                        frame_obj: Any = getframe(fi)
                        raw = frame_obj.data.copy()
                    else:
                        raw = img.data
                    if raw.ndim > 2:
                        raw = raw[0]
                    meta = dict(base_meta)
                    meta["frame_index"] = fi
                    meta["n_frames"] = n_frames
                    disk_results.append((raw.astype(np.float32), None, meta))
                return disk_results

        except Exception as exc:
            raise IOError(f"Failed to load all frames: {file_path}: {exc}") from exc

    @staticmethod
    def load_from_bytes(
        file_bytes: bytes,
        filename: str,
        h5_dataset_path: Optional[str] = None,
        h5_channel: Optional[str] = None,
    ) -> tuple[Optional[np.ndarray], Optional[np.ndarray], dict]:
        """Load image from raw bytes (write to temp file, load, cleanup).
        从原始字节加载图像（写入临时文件，加载后清理）。

        Replaces the Streamlit UploadedFile-based load method.
        替代基于 Streamlit UploadedFile 的加载方法。
        """
        ext = os.path.splitext(filename)[1].lower()
        meta: dict = {"filename": filename, "ext": ext}
        tmp_path: Optional[str] = None

        try:
            with tempfile.NamedTemporaryFile(mode="wb", delete=False, suffix=ext) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            if ext == ".h5":
                if not h5_dataset_path:
                    return None, None, meta
                data, dead_mask = H5Handler.load_2d_array(
                    tmp_path, h5_dataset_path, channel=h5_channel
                )
                meta["h5_dataset"] = h5_dataset_path
                if h5_channel:
                    meta["h5_channel"] = h5_channel
                return data, dead_mask, meta

            with fabio.open(tmp_path) as img:
                raw = img.data
                if raw.ndim > 2:
                    raw = raw[0]
            return raw.astype(np.float32), None, meta

        except Exception as exc:
            raise IOError(f"Failed to load: {filename}: {exc}") from exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                for _ in range(3):
                    try:
                        os.unlink(tmp_path)
                        break
                    except PermissionError:
                        time.sleep(0.05)
