#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h5convert.py — H5 to TIFF/CSV/DAT conversion (no GUI dependencies)
H5格式转换 — 将HDF5数据转换为TIFF/CSV/DAT（无GUI依赖）
"""

from __future__ import annotations

import csv
import logging
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional

import h5py
import numpy as np

OVERFLOW_THRESHOLD = 4.25e9
OVERFLOW_VALUE = -1.0

log = logging.getLogger(__name__)


def _is_image_like(shape: tuple) -> bool:
    return len(shape) >= 2 and shape[-2] >= 2 and shape[-1] >= 2


def _dataset_kind(shape: tuple) -> str:
    nd = len(shape)
    if nd == 0:
        return "scalar"
    if nd == 1:
        return "1d"
    if _is_image_like(shape):
        return f"{nd}d_image"
    return f"{nd}d"


def _safe_folder_name(ds_path: str) -> str:
    return re.sub(r"[^\w\-]", "_", ds_path).strip("_") or "dataset"


def _apply_overflow(arr: np.ndarray) -> np.ndarray:
    if not np.issubdtype(arr.dtype, np.floating):
        arr = arr.astype(np.float32)
    else:
        arr = arr.copy()
    arr[arr > OVERFLOW_THRESHOLD] = OVERFLOW_VALUE
    return arr


def save_tiff(data: np.ndarray, path: str) -> None:
    """Save 2D array as TIFF via fabio. 通过fabio将2D数组保存为TIFF。"""
    import fabio

    if data.ndim != 2:
        raise ValueError(f"TIFF requires 2D array, got shape: {data.shape}")
    fabio.tifimage.TifImage(data=data).write(path)


def save_edf(data: np.ndarray, path: str) -> None:
    """Save 2D array as EDF via fabio. 通过fabio将2D数组保存为EDF。"""
    import fabio

    if data.ndim != 2:
        raise ValueError(f"EDF requires 2D array, got shape: {data.shape}")
    fabio.edfimage.EdfImage(data=data).write(path)


class H5Converter:
    """Convert HDF5 datasets to TIFF/CSV/DAT. 将HDF5数据集转换为TIFF/CSV/DAT。"""

    def __init__(
        self,
        root_dir: str | Path,
        output_dir: str | Path,
        master_suffix: str = "_master",
        table_format: str = "csv",
        image_format: str = "tiff",
    ):
        self.root_dir = str(root_dir)
        self.output_dir = str(output_dir)
        self.master_suffix = master_suffix
        self.table_format = table_format
        self.image_format = image_format
        self._all_h5: list[str] = []
        self._master_h5: Optional[str] = None
        self._ds_cfg: dict[str, dict] = {}

    def scan(self) -> list[str]:
        """Scan root_dir for all .h5 files. 扫描根目录所有H5文件。"""
        import glob
        self._all_h5 = glob.glob(
            os.path.join(self.root_dir, "**", "*.h5"), recursive=True
        )
        sfx = self.master_suffix
        masters = [f for f in self._all_h5
                   if os.path.basename(f).lower().endswith(sfx.lower() + ".h5")]
        self._master_h5 = masters[0] if masters else None
        return self._all_h5

    def inspect_datasets(self) -> dict[str, dict]:
        """Inspect datasets from master H5. 从参考H5检查数据集。"""
        if not self._master_h5:
            raise FileNotFoundError("No master H5 file found. Call scan() first.")
        self._ds_cfg.clear()
        with h5py.File(self._master_h5, "r") as f:
            def _visit(name: str, obj: Any) -> None:
                if not isinstance(obj, h5py.Dataset):
                    return
                shape = obj.shape
                channels = list(range(shape[1])) if len(shape) == 4 else None
                self._ds_cfg[name] = {
                    "export": True,
                    "shape": shape,
                    "dtype": str(obj.dtype),
                    "kind": _dataset_kind(shape),
                    "channels": channels,
                }
            f.visititems(_visit)
        return self._ds_cfg

    def set_dataset_config(self, ds_path: str, export: bool = True,
                           channels: Optional[list[int]] = None) -> None:
        if ds_path in self._ds_cfg:
            self._ds_cfg[ds_path]["export"] = export
            if channels is not None:
                self._ds_cfg[ds_path]["channels"] = channels

    def convert(
        self,
        log_fn: Optional[Callable[[str], None]] = None,
        progress_fn: Optional[Callable[[float], None]] = None,
        stop_event: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Execute the conversion. 执行转换。

        Returns dict with summary stats. 返回含汇总统计的字典。
        """
        def _log(msg: str) -> None:
            log.info(msg)
            if log_fn:
                log_fn(msg)

        def _stopped() -> bool:
            return stop_event is not None and stop_event.is_set()

        os.makedirs(self.output_dir, exist_ok=True)
        selected = {k: v for k, v in self._ds_cfg.items() if v["export"]}
        if not selected:
            raise ValueError("No datasets selected for export")

        sfx = self.master_suffix
        data_h5 = [f for f in self._all_h5
                    if os.path.basename(f).lower().endswith(sfx.lower() + ".h5")]
        if not data_h5:
            data_h5 = [self._master_h5] if self._master_h5 else []

        ds_dirs: dict[str, str] = {}
        for ds_path, cfg in selected.items():
            if "image" in cfg["kind"]:
                nd = len(cfg["shape"])
                if nd != 4:
                    folder = os.path.join(self.output_dir, _safe_folder_name(ds_path))
                    os.makedirs(folder, exist_ok=True)
                    ds_dirs[ds_path] = folder
                else:
                    ds_dirs[ds_path] = os.path.join(self.output_dir, _safe_folder_name(ds_path))

        scalar_acc: dict = {}
        stats = {"files_processed": 0, "images_exported": 0, "errors": 0}
        total = len(data_h5)

        for h5_idx, h5_path in enumerate(data_h5):
            if _stopped():
                break
            file_stem = Path(h5_path).stem
            _log(f"Processing: {file_stem}")
            try:
                with h5py.File(h5_path, "r") as f:
                    for ds_path, cfg in selected.items():
                        if ds_path not in f:
                            continue
                        ds = f[ds_path]
                        if "image" in cfg["kind"]:
                            n = self._export_image(ds, ds_path, cfg, ds_dirs[ds_path], file_stem)
                            stats["images_exported"] += n
                        else:
                            self._accumulate_scalar(ds, ds_path, file_stem, scalar_acc)
            except Exception as exc:
                _log(f"Error ({file_stem}): {exc}")
                stats["errors"] += 1
            stats["files_processed"] += 1
            if progress_fn:
                progress_fn((h5_idx + 1) / max(total, 1))

        if scalar_acc:
            ext = "csv" if self.table_format == "csv" else "dat"
            out_path = os.path.join(self.output_dir, f"non_image_data.{ext}")
            if self.table_format == "csv":
                self._write_csv(scalar_acc, out_path)
            else:
                self._write_dat(scalar_acc, out_path)
            _log(f"Non-image data → {out_path}")

        _log("Conversion complete.")
        return stats

    def _export_image(self, ds: h5py.Dataset, ds_path: str, cfg: dict,
                      out_dir: str, file_stem: str) -> int:
        shape = ds.shape
        nd = len(shape)
        count = 0
        ext = ".edf" if self.image_format == "edf" else ".tif"
        _save = save_edf if self.image_format == "edf" else save_tiff

        if nd == 2:
            data = _apply_overflow(ds[()])
            path = os.path.join(out_dir, f"{file_stem}{ext}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _save(data, path)
            count = 1
        elif nd == 3:
            n_frames = shape[0]
            os.makedirs(out_dir, exist_ok=True)
            data = ds[()]
            for fi in range(n_frames):
                frame = _apply_overflow(data[fi])
                path = os.path.join(out_dir, f"{file_stem}_frame{fi:04d}{ext}")
                _save(frame, path)
            count = n_frames
        elif nd == 4:
            channels = cfg.get("channels") or list(range(shape[1]))
            n_frames = shape[0]
            data = ds[()]
            for ci in channels:
                if ci >= shape[1]:
                    continue
                ch_dir = os.path.join(out_dir, f"CH{ci}")
                os.makedirs(ch_dir, exist_ok=True)
                for fi in range(n_frames):
                    slice2d = _apply_overflow(data[fi, ci, :, :])
                    frame_tag = f"_frame{fi:04d}" if n_frames > 1 else ""
                    path = os.path.join(ch_dir, f"{file_stem}{frame_tag}{ext}")
                    _save(slice2d, path)
            count = n_frames * len(channels)
        return count

    def _accumulate_scalar(self, ds: h5py.Dataset, ds_path: str,
                           file_stem: str, acc: dict) -> None:
        try:
            flat = np.ravel(ds[()])
        except Exception:
            return
        if ds_path not in acc:
            acc[ds_path] = {"files": [], "values": []}
        acc[ds_path]["files"].append(file_stem)
        acc[ds_path]["values"].append(flat)

    def _build_table(self, acc: dict) -> tuple[list[str], list[list]]:
        header = ["source_file"]
        col_widths: dict[str, int] = {}
        for ds_path, info in acc.items():
            mx = max((len(v) for v in info["values"]), default=1)
            col_widths[ds_path] = mx
            if mx == 1:
                header.append(ds_path)
            else:
                header.extend(f"{ds_path}[{i}]" for i in range(mx))

        all_files: list[str] = []
        seen: set[str] = set()
        for info in acc.values():
            for fn in info["files"]:
                if fn not in seen:
                    all_files.append(fn)
                    seen.add(fn)

        rows = []
        for fn in all_files:
            row = [fn]
            for ds_path, info in acc.items():
                w = col_widths[ds_path]
                if fn in info["files"]:
                    idx = info["files"].index(fn)
                    vals = info["values"][idx].tolist()
                    vals += [""] * max(0, w - len(vals))
                    row.extend(vals[:w])
                else:
                    row.extend([""] * w)
            rows.append(row)
        return header, rows

    def _write_csv(self, acc: dict, path: str) -> None:
        header, rows = self._build_table(acc)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)

    def _write_dat(self, acc: dict, path: str) -> None:
        header, rows = self._build_table(acc)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\t".join(str(h) for h in header) + "\n")
            for row in rows:
                fh.write("\t".join(str(v) for v in row) + "\n")
