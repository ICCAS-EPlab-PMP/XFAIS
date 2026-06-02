#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pnggenerate.py — Batch PNG generation with colormap/log/linear/clim/DPI (no GUI dependencies)
批量PNG生成 — 色图/对数/线性/对比度范围/DPI设置（无GUI依赖）
"""

from __future__ import annotations

import logging
import io
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional

import h5py
import numpy as np
from PIL import Image

from .image_renderer import ImageRenderer

log = logging.getLogger(__name__)

OVERFLOW_THRESHOLD = 4.25e9
OVERFLOW_VALUE = -1.0

H5_EXTS = {".h5", ".hdf5"}
TIFF_EXTS = {".tif", ".tiff"}
EDF_EXTS = {".edf", ".cbf"}


def _is_image_like(shape: tuple) -> bool:
    return len(shape) >= 2 and shape[-2] >= 2 and shape[-1] >= 2


def _safe_name(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s).strip("_") or "dataset"


def _apply_overflow(arr: np.ndarray) -> np.ndarray:
    arr = arr.astype(np.float32) if not np.issubdtype(arr.dtype, np.floating) else arr.copy()
    arr[arr > OVERFLOW_THRESHOLD] = OVERFLOW_VALUE
    return arr


def _save_png(
    data: np.ndarray,
    path: str,
    cmap_name: str = "viridis",
    use_log: bool = False,
    clim: Optional[tuple[float, float]] = None,
    dpi: int = 300,
    show_colorbar: bool = False,
) -> None:
    """Save 2D array as colour-mapped PNG. 将2D数组保存为色图映射的PNG。"""
    d = data.copy().astype(np.float32)
    valid_mask = d > OVERFLOW_VALUE
    valid = d[valid_mask]

    if valid.size == 0:
        Image.fromarray(np.zeros((*d.shape, 3), dtype=np.uint8)).save(path)
        return

    vmin, vmax = (
        (float(clim[0]), float(clim[1]))
        if clim is not None
        else (float(valid.min()), float(valid.max()))
    )
    if vmax <= vmin:
        vmax = vmin + 1.0
    d[~valid_mask] = vmin

    png_bytes = ImageRenderer.render_png(
        d,
        {
            "cmap": cmap_name,
            "use_log": use_log,
            "clim": (vmin, vmax),
            "show_colorbar": show_colorbar,
        },
    )
    img = Image.open(io.BytesIO(png_bytes))
    if dpi != 100:
        s = dpi / 100
        img = img.resize((int(img.width * s), int(img.height * s)), Image.Resampling.LANCZOS)
    img.save(path, optimize=True)


def find_all_files(folder: str, recursive: bool = True) -> dict[str, list[str]]:
    """Scan folder for H5/TIFF/EDF files. 扫描文件夹中的H5/TIFF/EDF文件。"""
    result: dict[str, list[str]] = {"h5": [], "tiff": [], "edf": []}
    if recursive:
        for root, _dirs, files in os.walk(folder):
            for f in sorted(files):
                ext = Path(f).suffix.lower()
                full = os.path.join(root, f)
                if ext in H5_EXTS:
                    result["h5"].append(full)
                elif ext in TIFF_EXTS:
                    result["tiff"].append(full)
                elif ext in EDF_EXTS:
                    result["edf"].append(full)
    else:
        for f in sorted(os.listdir(folder)):
            full = os.path.join(folder, f)
            if not os.path.isfile(full):
                continue
            ext = Path(f).suffix.lower()
            if ext in H5_EXTS:
                result["h5"].append(full)
            elif ext in TIFF_EXTS:
                result["tiff"].append(full)
            elif ext in EDF_EXTS:
                result["edf"].append(full)
    return result


class PNGGenerator:
    """Batch PNG generation from H5/TIFF/EDF files.
    从H5/TIFF/EDF文件批量生成PNG。"""

    def __init__(
        self,
        source_folder: str | Path,
        output_folder: str | Path,
        template: Optional[dict] = None,
        recursive: bool = True,
    ):
        self.source_folder = str(source_folder)
        self.output_folder = str(output_folder)
        self.template = template or self.default_template()
        self.recursive = recursive

    @staticmethod
    def default_template() -> dict[str, Any]:
        return {
            "colormap": "viridis", "use_log": False,
            "clim_mode": "auto", "clim": [None, None],
            "show_colorbar": False,
            "layout": "flat",
            "h5": {"enabled": True, "datasets": []},
            "tiff": {"enabled": True},
            "edf": {"enabled": True},
            "dpi": 300,
        }

    def generate(
        self,
        log_fn: Optional[Callable[[str], None]] = None,
        progress_fn: Optional[Callable[[float], None]] = None,
        stop_event: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Execute batch PNG generation. 执行批量PNG生成。"""
        def _log(msg: str) -> None:
            log.info(msg)
            if log_fn:
                log_fn(msg)

        def _stopped() -> bool:
            return stop_event is not None and stop_event.is_set()

        os.makedirs(self.output_folder, exist_ok=True)

        file_lists = find_all_files(self.source_folder, self.recursive)
        tmpl = self.template
        cmap_name = tmpl.get("colormap", "viridis")
        use_log = tmpl.get("use_log", False)
        clim_mode = tmpl.get("clim_mode", "auto")
        clim_raw = tmpl.get("clim", [None, None])
        layout = tmpl.get("layout", "flat")
        dpi = tmpl.get("dpi", 300)

        clim = None
        if clim_mode == "manual" and clim_raw and clim_raw[0] is not None and clim_raw[1] is not None:
            clim = (float(clim_raw[0]), float(clim_raw[1]))
        show_colorbar = bool(tmpl.get("show_colorbar", False))

        stats = {"images_generated": 0, "errors": 0}
        all_files = (
            (file_lists.get("tiff", []) if tmpl.get("tiff", {}).get("enabled", True) else []) +
            (file_lists.get("edf", []) if tmpl.get("edf", {}).get("enabled", True) else []) +
            (file_lists.get("h5", []) if tmpl.get("h5", {}).get("enabled", True) else [])
        )
        total = max(len(all_files), 1)

        for idx, fpath in enumerate(all_files):
            if _stopped():
                break

            stem = Path(fpath).stem
            ext = Path(fpath).suffix.lower()
            _log(f"Processing: {stem}")

            try:
                if ext in TIFF_EXTS:
                    frames = self._load_tiff_frames(fpath)
                    self._save_frames(frames, stem, fpath, cmap_name, use_log, clim, dpi, layout, stats, show_colorbar)
                elif ext in EDF_EXTS:
                    frames = self._load_edf_frames(fpath)
                    self._save_frames(frames, stem, fpath, cmap_name, use_log, clim, dpi, layout, stats, show_colorbar)
                elif ext in H5_EXTS:
                    self._process_h5(fpath, stem, cmap_name, use_log, clim, dpi, layout, stats, _log, show_colorbar)
            except Exception as exc:
                _log(f"Error: {exc}")
                stats["errors"] += 1

            if progress_fn:
                progress_fn((idx + 1) / total)

        _log("PNG generation complete.")
        return stats

    def _save_frames(self, frames: list[np.ndarray], stem: str, fpath: str,
                     cmap_name: str, use_log: bool, clim: Optional[tuple],
                     dpi: int, layout: str, stats: dict, show_colorbar: bool) -> None:
        out_d = (
            os.path.join(self.output_folder, Path(fpath).stem)
            if layout == "per_file" else self.output_folder
        )
        os.makedirs(out_d, exist_ok=True)
        for fi, frame in enumerate(frames):
            tag = f"_frame{fi:04d}" if len(frames) > 1 else ""
            _save_png(
                _apply_overflow(frame),
                os.path.join(out_d, f"{stem}{tag}.png"),
                cmap_name, use_log, clim, dpi, show_colorbar,
            )
            stats["images_generated"] += 1

    def _process_h5(self, fpath: str, stem: str, cmap_name: str, use_log: bool,
                    clim: Optional[tuple], dpi: int, layout: str, stats: dict,
                    log_fn: Callable[[str], None], show_colorbar: bool) -> None:
        ds_configs = self.template.get("h5", {}).get("datasets", [])
        if not ds_configs:
            return

        with h5py.File(fpath, "r") as fh:
            for ds_cfg in ds_configs:
                if not ds_cfg.get("enabled", True):
                    continue
                ds_path = ds_cfg["path"]
                if ds_path not in fh:
                    continue
                ds = fh[ds_path]
                if not isinstance(ds, h5py.Dataset):
                    continue
                shape = tuple(ds.shape)
                ndim = ds.ndim

                if ndim not in (2, 3, 4) or not _is_image_like(shape):
                    continue

                sub_dir = os.path.join(
                    self.output_folder if layout == "flat" else os.path.join(self.output_folder, stem),
                    ds_cfg.get("export_subfolder", _safe_name(ds_path))
                )

                def _make_2d(raw: Any) -> np.ndarray:
                    r = np.asarray(raw)
                    dead = r > OVERFLOW_THRESHOLD
                    a = r.astype(np.float32)
                    a[dead] = OVERFLOW_VALUE
                    return a

                if ndim == 2:
                    os.makedirs(sub_dir, exist_ok=True)
                    _save_png(_make_2d(ds[()]), os.path.join(sub_dir, f"{stem}.png"),
                              cmap_name, use_log, clim, dpi, show_colorbar)
                    stats["images_generated"] += 1
                elif ndim == 3:
                    os.makedirs(sub_dir, exist_ok=True)
                    fr_list = ds_cfg.get("frames_to_export") or list(range(shape[0]))
                    for fi in fr_list:
                        if fi >= shape[0]:
                            continue
                        tag = f"_frame{fi:04d}" if shape[0] > 1 else ""
                        _save_png(_make_2d(ds[fi]), os.path.join(sub_dir, f"{stem}{tag}.png"),
                                  cmap_name, use_log, clim, dpi, show_colorbar)
                        stats["images_generated"] += 1
                elif ndim == 4:
                    ch_list = ds_cfg.get("channels_to_export") or list(range(shape[1]))
                    fr_list = ds_cfg.get("frames_to_export") or list(range(shape[0]))
                    for ci in ch_list:
                        if ci >= shape[1]:
                            continue
                        ch_dir = os.path.join(sub_dir, f"CH{ci}")
                        os.makedirs(ch_dir, exist_ok=True)
                        for fi in fr_list:
                            if fi >= shape[0]:
                                continue
                            tag = f"_frame{fi:04d}" if shape[0] > 1 else ""
                            _save_png(_make_2d(ds[fi, ci, :, :]),
                                      os.path.join(ch_dir, f"{stem}{tag}.png"),
                                      cmap_name, use_log, clim, dpi, show_colorbar)
                            stats["images_generated"] += 1

    @staticmethod
    def _load_tiff_frames(path: str) -> list[np.ndarray]:
        import fabio
        frames: list[np.ndarray] = []
        with fabio.open(path) as img:
            n = max(int(getattr(img, "nframes", 1) or 1), 1)
            getframe = getattr(img, "getframe", None)
            for fi in range(n):
                if n > 1 and callable(getframe):
                    frame_obj: Any = getframe(fi)
                    frame = frame_obj.data.copy()
                else:
                    frame = img.data.copy()
                if frame.ndim > 2:
                    frame = frame[0]
                frames.append(frame.astype(np.float32))
        return frames

    @staticmethod
    def _load_edf_frames(path: str) -> list[np.ndarray]:
        import fabio
        frames: list[np.ndarray] = []
        with fabio.open(path) as img:
            n = getattr(img, "nframes", 1)
            for fi in range(n):
                if hasattr(img, "getframe") and n > 1:
                    frame_obj: Any = img.getframe(fi)
                    frame = frame_obj.data.copy()
                else:
                    frame = img.data.copy()
                frames.append(frame.astype(np.float32))
        return frames
