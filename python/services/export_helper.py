#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_helper.py — ExportHelper: TXT/HDF5/TIFF/EDF/NPY export with metadata
导出辅助类 — 将积分结果导出为多种格式
"""

from __future__ import annotations

import io
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fabio
import h5py
import numpy as np
import pyFAI
from fabio.edfimage import EdfImage
from fabio.tifimage import TifImage


@dataclass
class AdvancedIntegrationOptions:
    """Container for advanced integration parameters. 高级积分参数容器。"""
    method: str = "splitpixel"
    correct_solid_angle: bool = False
    polarization_factor: Optional[float] = None
    dark: Optional[np.ndarray] = None
    flat: Optional[np.ndarray] = None


@dataclass
class IntegrationResult:
    """Holds one 1-D integration result with metadata. 保存单次1D积分结果及元数据。"""
    radial: np.ndarray
    intensity: np.ndarray
    label: str
    source_filename: str
    unit: str
    sigma: Optional[np.ndarray] = None


class ExportHelper:
    """Export integration results to TXT / HDF5 / TIFF / EDF / NPY.
    将积分结果导出为TXT/HDF5/TIFF/EDF/NPY格式。"""

    UNIT_LABELS: dict[str, str] = {
        "q_nm^-1": "q (1/nm)", "q_A^-1": "q (1/Å)",
        "2th_deg": "2θ (degrees)", "r_mm": "Radius (mm)",
        "chi_deg": "χ (degrees)", "chi_rad": "χ (radians)",
    }

    @classmethod
    def to_txt(
        cls,
        results: List[IntegrationResult],
        unit_display: str,
        extra_header_lines: Optional[List[str]] = None,
    ) -> str:
        """Serialise 1D results to tab-separated text. 将1D结果序列化为制表符分隔文本。"""
        buf = io.StringIO()
        buf.write(f"# X_value unit: {unit_display}\n")
        if extra_header_lines:
            for line in extra_header_lines:
                buf.write(f"# {line}\n")
        buf.write("X_value\t" + "\t".join(r.label for r in results) + "\n")

        ref_x = results[0].radial
        q_like = any(k in (results[0].unit if results else "") for k in ("q_nm", "q_A"))
        for i in range(len(ref_x)):
            fmt = f"{ref_x[i]:.6e}" if q_like else f"{ref_x[i]:.6f}"
            row = [fmt] + [f"{r.intensity[i]:.6f}" if i < len(r.intensity) else "" for r in results]
            buf.write("\t".join(row) + "\n")
        return buf.getvalue()

    @classmethod
    def to_hdf5_bytes(
        cls,
        results: List[IntegrationResult],
        unit_display: str,
        extra_meta: Optional[dict] = None,
    ) -> bytes:
        """Serialise 1D results to in-memory HDF5. 将1D结果序列化为内存HDF5。"""
        buf = io.BytesIO()
        with h5py.File(buf, "w") as fh:
            meta_grp = fh.create_group("metadata")
            meta_grp.attrs["unit"] = unit_display
            meta_grp.attrs["pyfai_version"] = pyFAI.version
            meta_grp.attrs["n_files"] = len(results)
            if extra_meta:
                for k, v in extra_meta.items():
                    try:
                        meta_grp.attrs[str(k)] = str(v)
                    except Exception:
                        pass

            res_grp = fh.create_group("results")
            for idx, r in enumerate(results):
                grp = res_grp.create_group(f"file_{idx:04d}")
                grp.create_dataset("radial", data=r.radial.astype(np.float32), compression="gzip")
                grp.create_dataset("intensity", data=r.intensity.astype(np.float32), compression="gzip")
                if r.sigma is not None:
                    grp.create_dataset("sigma", data=r.sigma.astype(np.float32), compression="gzip")
                grp.attrs["label"] = r.label
                grp.attrs["source_filename"] = r.source_filename
                grp.attrs["unit"] = r.unit
        return buf.getvalue()

    @classmethod
    def to_hdf5_2d_bytes(
        cls,
        intensity: np.ndarray,
        axis_ip: np.ndarray,
        axis_oop: np.ndarray,
        unit_ip: str = "qip_nm^-1",
        unit_oop: str = "qoop_nm^-1",
        extra_meta: Optional[dict] = None,
    ) -> bytes:
        """Serialise a 2-D integration map (e.g. GIWAXS) to in-memory HDF5.
        将2D积分图序列化为内存HDF5。"""
        buf = io.BytesIO()
        with h5py.File(buf, "w") as fh:
            meta = fh.create_group("metadata")
            meta.attrs["unit_ip"] = unit_ip
            meta.attrs["unit_oop"] = unit_oop
            meta.attrs["pyfai_version"] = pyFAI.version
            meta.attrs["intensity_shape"] = list(intensity.shape)
            meta.attrs["axis0_is"] = "oop"
            meta.attrs["axis1_is"] = "ip"
            if extra_meta:
                for k, v in extra_meta.items():
                    try:
                        meta.attrs[str(k)] = str(v)
                    except Exception:
                        pass
            fh.create_dataset("intensity", data=intensity.astype(np.float32), compression="gzip")
            fh.create_dataset("axis_ip", data=axis_ip.astype(np.float64), compression="gzip")
            fh.create_dataset("axis_oop", data=axis_oop.astype(np.float64), compression="gzip")
        return buf.getvalue()

    @classmethod
    def to_hdf5_batch_2d_bytes(
        cls,
        batch_results: List[dict],
        unit_ip: str = "qip_nm^-1",
        unit_oop: str = "qoop_nm^-1",
    ) -> bytes:
        """Merge multiple 2-D fiber-integration results into one HDF5.
        将多个2D纤维积分结果合并为一个HDF5。"""
        buf = io.BytesIO()
        with h5py.File(buf, "w") as fh:
            meta_grp = fh.create_group("metadata")
            meta_grp.attrs["n_files"] = len(batch_results)
            meta_grp.attrs["unit_ip"] = unit_ip
            meta_grp.attrs["unit_oop"] = unit_oop
            meta_grp.attrs["pyfai_version"] = pyFAI.version
            meta_grp.attrs["axis0_is"] = "oop"
            meta_grp.attrs["axis1_is"] = "ip"

            res_grp = fh.create_group("results")
            seen_names: dict[str, int] = {}

            for item in batch_results:
                stem = str(item.get("stem", "result"))
                intensity = item["intensity"]
                axis_ip = item["axis_ip"]
                axis_oop = item["axis_oop"]
                extra = item.get("meta", {})

                safe_stem = stem.replace("/", "_").replace("\\", "_")
                if safe_stem in seen_names:
                    seen_names[safe_stem] += 1
                    safe_stem = f"{safe_stem}_{seen_names[safe_stem]:03d}"
                else:
                    seen_names[safe_stem] = 0

                grp = res_grp.create_group(safe_stem)
                grp.create_dataset("intensity", data=intensity.astype(np.float32), compression="gzip")
                grp.create_dataset("axis_ip", data=axis_ip.astype(np.float64), compression="gzip")
                grp.create_dataset("axis_oop", data=axis_oop.astype(np.float64), compression="gzip")
                grp.attrs["source_file"] = stem
                grp.attrs["unit_ip"] = unit_ip
                grp.attrs["unit_oop"] = unit_oop
                grp.attrs["shape"] = list(intensity.shape)
                if extra:
                    for k, v in extra.items():
                        try:
                            grp.attrs[str(k)] = str(v)
                        except Exception:
                            pass

        buf.seek(0)
        return buf.getvalue()

    @classmethod
    def write_hdf5_batch_2d_streaming(
        cls,
        output_path: str | Path,
        batch_results: List[dict],
        unit_ip: str = "qip_nm^-1",
        unit_oop: str = "qoop_nm^-1",
    ) -> str:
        """Write multiple 2-D fiber-integration results directly to HDF5.
        直接将多个 2D 纤维积分结果写入磁盘 HDF5，避免额外内存字节缓冲。"""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with h5py.File(out, "w") as fh:
            meta_grp = fh.create_group("metadata")
            meta_grp.attrs["n_files"] = len(batch_results)
            meta_grp.attrs["unit_ip"] = unit_ip
            meta_grp.attrs["unit_oop"] = unit_oop
            meta_grp.attrs["pyfai_version"] = pyFAI.version
            meta_grp.attrs["axis0_is"] = "oop"
            meta_grp.attrs["axis1_is"] = "ip"

            res_grp = fh.create_group("results")
            seen_names: dict[str, int] = {}
            for item in batch_results:
                stem = str(item.get("stem", "result"))
                intensity = item["intensity"]
                axis_ip = item["axis_ip"]
                axis_oop = item["axis_oop"]
                extra = item.get("meta", {})

                safe_stem = stem.replace("/", "_").replace("\\", "_")
                if safe_stem in seen_names:
                    seen_names[safe_stem] += 1
                    safe_stem = f"{safe_stem}_{seen_names[safe_stem]:03d}"
                else:
                    seen_names[safe_stem] = 0

                grp = res_grp.create_group(safe_stem)
                grp.create_dataset("intensity", data=intensity.astype(np.float32), compression="gzip")
                grp.create_dataset("axis_ip", data=axis_ip.astype(np.float64), compression="gzip")
                grp.create_dataset("axis_oop", data=axis_oop.astype(np.float64), compression="gzip")
                grp.attrs["source_file"] = stem
                grp.attrs["unit_ip"] = unit_ip
                grp.attrs["unit_oop"] = unit_oop
                grp.attrs["shape"] = list(intensity.shape)
                if extra:
                    for k, v in extra.items():
                        try:
                            grp.attrs[str(k)] = str(v)
                        except Exception:
                            pass
        return str(out)

    @classmethod
    def to_image_bytes(cls, data: np.ndarray, fmt: str = "tiff") -> bytes:
        """Serialise a 2-D float array to TIFF or EDF bytes via fabio.
        通过fabio将2D浮点数组序列化为TIFF或EDF字节。"""
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{fmt}") as tmp:
                tmp_path = tmp.name
            # Replace NaN/Inf with 0 before writing (fabio cannot handle them)
            # 写入前将 NaN/Inf 替换为 0（fabio 无法处理这些值）
            arr = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)
            if fmt == "tiff":
                TifImage(data=arr).write(tmp_path)
            else:
                EdfImage(data=arr).write(tmp_path)
            with open(tmp_path, "rb") as fh:
                return fh.read()
        except Exception as exc:
            raise RuntimeError(f"Export {fmt.upper()} failed: {exc}") from exc
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @classmethod
    def to_npy_dict(
        cls,
        intensity: np.ndarray,
        axis_ip: np.ndarray,
        axis_oop: np.ndarray,
        unit_ip: str = "qip_nm^-1",
        unit_oop: str = "qoop_nm^-1",
        extra_meta: Optional[dict] = None,
    ) -> bytes:
        """Serialise 2D result as NPY dict with axes and metadata.
        将2D结果序列化为含坐标轴和元数据的NPY字典。"""
        pixel_ip = float(abs(axis_ip[-1] - axis_ip[0]) / max(len(axis_ip) - 1, 1))
        pixel_oop = float(abs(axis_oop[-1] - axis_oop[0]) / max(len(axis_oop) - 1, 1))
        npy_dict = {
            "intensity": intensity.astype(np.float32),
            "qip": axis_ip.astype(np.float64),
            "qoop": axis_oop.astype(np.float64),
            "info": {
                "unit_ip": unit_ip,
                "unit_oop": unit_oop,
                "pixel_size_ip": pixel_ip,
                "pixel_size_oop": pixel_oop,
                "ip_range": [float(axis_ip[0]), float(axis_ip[-1])],
                "oop_range": [float(axis_oop[0]), float(axis_oop[-1])],
                "axis0_is": "oop",
                "axis1_is": "ip",
                **(extra_meta or {}),
            },
        }
        npy_buf = io.BytesIO()
        obj = np.empty((), dtype=object)
        obj[()] = npy_dict
        np.save(npy_buf, obj)
        return npy_buf.getvalue()
