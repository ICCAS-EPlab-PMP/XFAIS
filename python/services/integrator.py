#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
integrator.py — IntegratorFactory: PONI/manual params → AzimuthalIntegrator, unit mapping
积分器工厂 — 从PONI文件或手动参数创建AzimuthalIntegrator
"""

from __future__ import annotations

import math
import os
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import pyFAI
from pyFAI.integrator.azimuthal import AzimuthalIntegrator


def _sanitize_poni_text(raw: str) -> str:
    """Strip non-ASCII lines (e.g. Chinese comments) so pyFAI can parse on any locale.
    移除非ASCII行（如中文注释），使 pyFAI 在任何系统编码下均可解析。"""
    return "\n".join(
        line for line in raw.splitlines()
        if not line.strip() or line.strip().startswith("#") and line.isascii() or not line.strip().startswith("#") and line.isascii()
        if line.isascii()
    )

INTEGRATION_METHODS: dict[str, str] = {
    "splitpixel": "splitpixel",
    "csr": "csr",
    "lut": "lut",
    "bbox": "bbox",
    "numpy": "numpy",
}

UNIT_LABELS: dict[str, str] = {
    "q_nm^-1": "q (1/nm)",
    "q_A^-1": "q (1/Å)",
    "2th_deg": "2θ (degrees)",
    "r_mm": "Radius (mm)",
    "chi_deg": "χ (degrees)",
    "chi_rad": "χ (radians)",
}


class IntegratorFactory:
    """Build or load an AzimuthalIntegrator instance.
    构建或加载 AzimuthalIntegrator 实例。"""

    @staticmethod
    def from_poni_path(
        poni_path: str | Path,
    ) -> Tuple[Optional[AzimuthalIntegrator], Optional[float], Optional[float]]:
        try:
            poni_path = str(poni_path)
            with open(poni_path, encoding="utf-8", errors="replace") as fh:
                raw = fh.read()
            clean = _sanitize_poni_text(raw)
            tmp: Optional[str] = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".poni", delete=False, encoding="ascii"
                ) as tf:
                    tf.write(clean)
                    tmp = tf.name
                ai = AzimuthalIntegrator()
                ai.load(tmp)
            finally:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
            center_x = ai.poni2 / ai.pixel2
            center_y = ai.poni1 / ai.pixel1
            return ai, center_x, center_y
        except Exception as exc:
            raise ValueError(f"Failed to load PONI file: {exc}") from exc

    @staticmethod
    def from_poni_bytes(
        poni_bytes: bytes,
    ) -> Tuple[Optional[AzimuthalIntegrator], Optional[float], Optional[float]]:
        try:
            raw = poni_bytes.decode("utf-8", errors="replace")
            clean = _sanitize_poni_text(raw)
            tmp: Optional[str] = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".poni", delete=False, encoding="ascii"
                ) as tf:
                    tf.write(clean)
                    tmp = tf.name
                return IntegratorFactory.from_poni_path(tmp)
            finally:
                if tmp and os.path.exists(tmp):
                    os.unlink(tmp)
        except Exception as exc:
            raise ValueError(f"Failed to load PONI from bytes: {exc}") from exc

    @staticmethod
    def from_manual_params(
        pixel_size_um: float,
        dist_mm: float,
        wavelength_A: float,
        center_x_px: float,
        center_y_px: float,
        rot1_deg: float = 0.0,
        rot2_deg: float = 0.0,
        rot3_deg: float = 0.0,
    ) -> Tuple[AzimuthalIntegrator, float, float]:
        """Create an integrator from manually entered parameters.
        从手动输入的参数创建积分器。Returns (ai, center_x_px, center_y_px)."""
        try:
            ps = pixel_size_um * 1e-6
            dist = dist_mm * 1e-3
            wl = wavelength_A * 1e-10
            ai = AzimuthalIntegrator(
                dist=dist,
                poni1=center_y_px * ps,
                poni2=center_x_px * ps,
                rot1=math.radians(rot1_deg),
                rot2=math.radians(rot2_deg),
                rot3=math.radians(rot3_deg),
                pixel1=ps,
                pixel2=ps,
                wavelength=wl,
            )
            return ai, center_x_px, center_y_px
        except Exception as exc:
            raise ValueError(f"Failed to build integrator: {exc}") from exc
