#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fiber_integrator.py — Fiber GIWAXS integration core (no GUI dependencies)
纤维GIWAXS积分核心 — 2D掠入射衍射积分（无GUI依赖）
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pyFAI
import pyFAI.detectors
from pyFAI.integrator.fiber import FiberIntegrator
from pyFAI.io.ponifile import PoniFile

from .image_loader import ImageLoader
from .mask_builder import MaskBuilder
from .export_helper import ExportHelper

FIBER_UNITS_IP: list[str] = [
    "qip_nm^-1", "qip_A^-1", "qxgi_nm^-1", "qygi_nm^-1", "qzgi_nm^-1",
    "qtot_nm^-1", "qxgi_A^-1", "qygi_A^-1", "qzgi_A^-1", "qtot_A^-1",
    "scattering_angle_horz_rad", "exit_angle_horz_rad", "exit_angle_horz_deg",
    "chigi_rad", "chigi_deg",
]

FIBER_UNITS_OOP: list[str] = [
    "qoop_nm^-1", "qoop_A^-1", "qxgi_nm^-1", "qygi_nm^-1", "qzgi_nm^-1",
    "qtot_nm^-1", "qxgi_A^-1", "qygi_A^-1", "qzgi_A^-1", "qtot_A^-1",
    "scattering_angle_vert_rad", "exit_angle_vert_rad", "exit_angle_vert_deg",
    "chigi_rad", "chigi_deg",
]


class FiberIntegratorService:
    """GIWAXS fiber 2D integration service.
    GIWAXS纤维2D积分服务。"""

    @staticmethod
    def build_integrator(
        poni_path: Optional[str] = None,
        poni_bytes: Optional[bytes] = None,
        use_poni_rot3: bool = True,
        override_rot3_rad: float = 0.0,
        raw_shape: Optional[tuple] = None,
        manual_params: Optional[dict] = None,
    ) -> Optional[FiberIntegrator]:
        """Build a FiberIntegrator from PONI or manual parameters.
        从PONI或手动参数构建FiberIntegrator。"""
        try:
            if (poni_path or poni_bytes) and not manual_params:
                if poni_bytes:
                    import tempfile
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".poni") as tmp:
                        tmp.write(poni_bytes)
                        tmp_path = tmp.name
                    poni = PoniFile(data=tmp_path)
                    os.unlink(tmp_path)
                else:
                    poni = PoniFile(data=str(poni_path))

                eff_rot3 = poni.rot3 if use_poni_rot3 else override_rot3_rad
                return FiberIntegrator(
                    dist=poni.dist, poni1=poni.poni1, poni2=poni.poni2,
                    wavelength=poni.wavelength,
                    rot1=poni.rot1, rot2=poni.rot2, rot3=eff_rot3,
                    detector=poni.detector,
                )
            elif manual_params:
                # Use actual pixel size if provided, fallback to default 172µm
                # 使用实际像素尺寸（如有），回退到默认 172µm
                pixel_size_um = manual_params.get("pixel_size_um", 172.0)
                pixel_size_m = float(pixel_size_um) * 1e-6
                detector = pyFAI.detectors.Detector(
                    pixel1=pixel_size_m, pixel2=pixel_size_m
                )
                return FiberIntegrator(
                    dist=manual_params["dist"],
                    poni1=manual_params["poni1"],
                    poni2=manual_params["poni2"],
                    wavelength=manual_params["wavelength"],
                    rot1=manual_params.get("rot1", 0.0),
                    rot2=manual_params.get("rot2", 0.0),
                    rot3=manual_params.get("rot3", 0.0),
                    detector=detector,
                )
        except Exception as exc:
            raise ValueError(f"Failed to build FiberIntegrator: {exc}") from exc
        return None

    @staticmethod
    def integrate_single(
        fi: FiberIntegrator,
        data: np.ndarray,
        mask: np.ndarray,
        params: dict,
        dark: Optional[np.ndarray] = None,
        flat: Optional[np.ndarray] = None,
        correct_solid_angle: bool = True,
        polarization_factor: Optional[float] = None,
    ) -> dict[str, Any]:
        """Integrate a single image. 积分单张图像。

        Returns dict with intensity, axis_ip, axis_oop, and metadata.
        """
        proc_data = data.copy()
        if dark is not None and dark.shape == proc_data.shape:
            proc_data -= dark
        if flat is not None and flat.shape == proc_data.shape:
            np.divide(proc_data, flat, out=proc_data, where=flat != 0)

        kw: dict[str, Any] = {
            "data": proc_data,
            "npt_ip": params["npt_ip"],
            "npt_oop": params["npt_oop"],
            "unit_ip": params.get("unit_ip", "qip_nm^-1"),
            "unit_oop": params.get("unit_oop", "qoop_nm^-1"),
            "sample_orientation": params.get("sample_orientation", 1),
            "incident_angle": params.get("incident_rad", 0.0),
            "tilt_angle": params.get("tilt_rad", 0.0),
            "angle_unit": "rad",
            "correctSolidAngle": correct_solid_angle,
            "mask": mask.astype(np.uint8),
        }
        if polarization_factor is not None:
            kw["polarization_factor"] = polarization_factor
        if not params.get("use_auto", False):
            kw["ip_range"] = params.get("ip_range")
            kw["oop_range"] = params.get("oop_range")

        result = fi.integrate2d_grazing_incidence(**kw)

        if hasattr(result, "intensity"):
            I, qip, qoop = result.intensity, result.radial, result.azimuthal
        else:
            I, qip, qoop = result

        return {
            "intensity": I,
            "axis_ip": qip,
            "axis_oop": qoop,
            "shape": list(I.shape),
        }

    @staticmethod
    def integrate_batch(
        fi: FiberIntegrator,
        file_paths: list[str | Path],
        params: dict,
        valid_min: float = 0.0,
        valid_max: float = 1e10,
        h5_dataset_path: Optional[str] = None,
        h5_channel: Optional[str] = None,
        custom_mask: Optional[np.ndarray] = None,
        dark: Optional[np.ndarray] = None,
        flat: Optional[np.ndarray] = None,
        correct_solid_angle: bool = True,
        polarization_factor: Optional[float] = None,
        progress_fn: Optional[Any] = None,
        error_collector: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Batch integrate multiple files. 批量积分多个文件。"""
        results: list[dict[str, Any]] = []
        n_files = len(file_paths)

        for file_idx, fpath in enumerate(file_paths):
            fpath = Path(fpath)
            try:
                raw_data, dead_mask, meta = ImageLoader.load(
                    fpath, h5_dataset_path, h5_channel
                )
                if raw_data is None:
                    err_msg = f"{fpath.name}: ImageLoader.load returned None"
                    if error_collector is not None:
                        error_collector.append(err_msg)
                    continue

                final_mask = MaskBuilder.build(
                    raw_data, valid_min, valid_max, dead_mask, custom_mask
                )

                result = FiberIntegratorService.integrate_single(
                    fi, raw_data, final_mask, params,
                    dark=dark, flat=flat,
                    correct_solid_angle=correct_solid_angle,
                    polarization_factor=polarization_factor,
                )

                result["stem"] = fpath.stem + "_fiber_integration"
                result["filename"] = fpath.name
                results.append(result)

            except Exception as exc:
                err_msg = f"{fpath.name}: {exc}"
                if error_collector is not None:
                    error_collector.append(err_msg)
                continue

            if progress_fn:
                progress_fn((file_idx + 1) / max(n_files, 1))

        return results
