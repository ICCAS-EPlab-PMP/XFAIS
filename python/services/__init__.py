#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
services — Standalone Python business services for WAXS-SAXS Manager
独立 Python 业务服务模块，无 Streamlit/tkinter 依赖
"""

from .image_loader import H5Handler, ImageLoader
from .integrator import IntegratorFactory
from .mask_builder import MaskBuilder
from .export_helper import ExportHelper, IntegrationResult, AdvancedIntegrationOptions
from .colormaps import CMAP_CHOICES, build_cmap, get_cmap
from .h5convert import H5Converter
from .h5_extractor import H5Extractor
from .pnggenerate import PNGGenerator
from .fiber_integrator import FiberIntegratorService
from .bg_subtractor import (
    subtract_with_reference,
    parse_ionchamber_file,
    calc_transmission,
    match_ionchamber,
    subtract_h5_stack,
    find_h5_transmissions,
)

__all__ = [
    "H5Handler",
    "ImageLoader",
    "IntegratorFactory",
    "MaskBuilder",
    "ExportHelper",
    "IntegrationResult",
    "AdvancedIntegrationOptions",
    "CMAP_CHOICES",
    "build_cmap",
    "get_cmap",
    "H5Converter",
    "H5Extractor",
    "PNGGenerator",
    "FiberIntegratorService",
    "subtract_with_reference",
    "parse_ionchamber_file",
    "calc_transmission",
    "match_ionchamber",
    "subtract_h5_stack",
    "find_h5_transmissions",
]
