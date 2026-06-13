#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PONI Importer Service for X-FAIS.
PONI文件导入服务模块。

Provides functionality to:
1. Parse pyFAI .poni files
2. Export to various formats (JSON, manual parameters)

PONI file format reference / PONI文件格式参考:
https://pyfai.readthedocs.io/en/latest/api/geometry.html#poni-file
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PONI file parsing / PONI文件解析
# ---------------------------------------------------------------------------

def parse_poni_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Parse a pyFAI .poni file and extract geometry parameters.
    解析 pyFAI .poni 文件并提取几何参数。

    Parameters
    ----------
    file_path : str
        Path to the .poni file.

    Returns
    -------
    dict or None
        Dictionary containing parsed PONI data, or None on failure.

    Keys include / 包含的键:
        - distance: Detector distance (meters)
        - wavelength: X-ray wavelength (meters)
        - pixel_size: Pixel size (meters)
        - poni1: Beam center X (pixels from left)
        - poni2: Beam center Y (pixels from top)
        - rot1: Rotation 1 (radians, optional)
        - rot2: Rotation 2 (radians, optional)
        - rot3: Rotation 3 (radians, optional)
        - detector_name: Detector name (optional)
        - detector_config: Detector configuration (optional)
    """
    if not os.path.isfile(file_path):
        logger.error(f"PONI file not found: {file_path}")
        return None

    try:
        # Read file content / 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Parse key-value pairs / 解析键值对
        result: Dict[str, Any] = {}

        for line in lines:
            line = line.strip()
            # Skip comments and empty lines / 跳过注释和空行
            if not line or line.startswith('#'):
                continue

            # Parse key: value format / 解析 key: value 格式
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present / 移除引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                # Convert to float for numeric values / 数值转换为float
                try:
                    value = float(value)
                except ValueError:
                    pass

                result[key] = value

        # Normalize to standard keys / 规范化为标准键
        normalized = _normalize_poni_data(result)
        logger.info(f"Parsed PONI file: {file_path}")
        return normalized

    except Exception as exc:
        logger.error(f"Failed to parse PONI file {file_path}: {exc}")
        return None


def _normalize_poni_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize raw PONI data to standard format.
    将原始PONI数据规范化为标准格式。

    Handles various naming conventions used in different pyFAI versions.
    处理不同pyFAI版本中的不同命名约定。
    """
    normalized: Dict[str, Any] = {}

    # Distance / 距离
    for key in ['Distance', 'distance', 'Detector_Distance']:
        if key in raw:
            normalized['distance'] = float(raw[key])
            break

    # Wavelength / 波长
    for key in ['Wavelength', 'wavelength', 'WaveLength']:
        if key in raw:
            normalized['wavelength'] = float(raw[key])
            break

    # Pixel size / 像素尺寸
    for key in ['PixelSize', 'pixel_size', 'Pixel_Size', 'pixelSize']:
        if key in raw:
            val = raw[key]
            # Check if it's a list/tuple / 检查是否是列表/元组
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                # Assume square pixel if both values are same
                # 如果两个值相同，假设为正方形像素
                normalized['pixel_size'] = float(val[0])
            else:
                normalized['pixel_size'] = float(val)
            break

    # PONI1 (beam center X / 光束中心X)
    for key in ['Poni1', 'poni1', 'Poni_1', 'beam_center_x']:
        if key in raw:
            normalized['poni1'] = float(raw[key])
            break

    # PONI2 (beam center Y / 光束中心Y)
    for key in ['Poni2', 'poni2', 'Poni_2', 'beam_center_y']:
        if key in raw:
            normalized['poni2'] = float(raw[key])
            break

    # Rotations / 旋转
    for key in ['Rot1', 'rot1', 'Rotation1', 'rotation1']:
        if key in raw:
            normalized['rot1'] = float(raw[key])

    for key in ['Rot2', 'rot2', 'Rotation2', 'rotation2']:
        if key in raw:
            normalized['rot2'] = float(raw[key])

    for key in ['Rot3', 'rot3', 'Rotation3', 'rotation3']:
        if key in raw:
            normalized['rot3'] = float(raw[key])

    # Detector info / 探测器信息
    for key in ['Detector', 'detector', 'Detector_Name', 'detector_name']:
        if key in raw:
            normalized['detector_name'] = str(raw[key])
            break

    for key in ['Detector_config', 'detector_config', 'DetectorConfig']:
        if key in raw:
            normalized['detector_config'] = str(raw[key])
            break

    # Copy any additional fields / 复制任何其他字段
    for key, value in raw.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


# ---------------------------------------------------------------------------
# Export functions / 导出函数
# ---------------------------------------------------------------------------

def export_to_json(poni_data: Dict[str, Any], output_path: Optional[str] = None) -> str:
    """
    Export PONI data to JSON format.
    将PONI数据导出为JSON格式。

    Parameters
    ----------
    poni_data : dict
        Parsed PONI data.
    output_path : str, optional
        Output file path. If None, returns JSON string.

    Returns
    -------
    str
        JSON string or output file path.
    """
    json_str = json.dumps(poni_data, indent=2)

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(json_str)
        logger.info(f"Exported PONI data to JSON: {output_path}")
        return output_path

    return json_str


def export_to_poni(poni_data: Dict[str, Any], output_path: str) -> str:
    """
    Export PONI data to .poni file format.
    将PONI数据导出为.poni文件格式。

    Parameters
    ----------
    poni_data : dict
        Parsed PONI data.
    output_path : str
        Output file path.

    Returns
    -------
    str
        Output file path.
    """
    lines = [
        "# PONI file generated by X-FAIS",
        "# Generated from imported PONI data",
    ]

    # Write standard fields in pyFAI order / 按pyFAI顺序写入标准字段
    field_order = [
        ('distance', 'Distance'),
        ('wavelength', 'Wavelength'),
        ('pixel_size', 'PixelSize'),
        ('poni1', 'Poni1'),
        ('poni2', 'Poni2'),
        ('rot1', 'Rot1'),
        ('rot2', 'Rot2'),
        ('rot3', 'Rot3'),
        ('detector_name', 'Detector'),
        ('detector_config', 'Detector_config'),
    ]

    for key, poni_key in field_order:
        if key in poni_data:
            value = poni_data[key]
            if isinstance(value, str):
                lines.append(f"{poni_key}: \"{value}\"")
            else:
                lines.append(f"{poni_key}: {value}")

    # Write any additional fields / 写入任何其他字段
    written_keys = {k for k, _ in field_order if k in poni_data}
    for key, value in poni_data.items():
        if key not in written_keys and not key.startswith('_'):
            if isinstance(value, str):
                lines.append(f"{key}: \"{value}\"")
            else:
                lines.append(f"{key}: {value}")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    logger.info(f"Exported PONI data to file: {output_path}")
    return output_path


def export_to_manual_params(poni_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Export PONI data to manual parameters format for X-FAIS integration.
    将PONI数据导出为X-FAIS集成用的手动参数格式。

    Returns
    -------
    dict
        Manual parameters dictionary with:
        - detector_distance: mm
        - wavelength: Angstrom
        - pixel_size: micrometers
        - beam_center: [x, y] in pixels
        - rotations: [rot1, rot2, rot3] in degrees
    """
    manual_params: Dict[str, Any] = {}

    # Distance in mm / 距离（毫米）
    if 'distance' in poni_data:
        manual_params['detector_distance'] = poni_data['distance'] * 1000  # m to mm

    # Wavelength in Angstrom / 波长（埃）
    if 'wavelength' in poni_data:
        manual_params['wavelength'] = poni_data['wavelength'] * 1e10  # m to A

    # Pixel size in micrometers / 像素尺寸（微米）
    if 'pixel_size' in poni_data:
        manual_params['pixel_size'] = poni_data['pixel_size'] * 1e6  # m to um

    # Beam center in pixels / 光束中心（像素）
    if 'poni1' in poni_data and 'poni2' in poni_data:
        manual_params['beam_center'] = [poni_data['poni1'], poni_data['poni2']]

    # Rotations in degrees / 旋转（度）
    rotations = []
    for key in ['rot1', 'rot2', 'rot3']:
        if key in poni_data:
            rot_rad = poni_data[key]
            rot_deg = rot_rad * 180 / 3.141592653589793
            rotations.append(rot_deg)
        else:
            rotations.append(0.0)

    manual_params['rotations'] = rotations

    # Detector info / 探测器信息
    if 'detector_name' in poni_data:
        manual_params['detector_name'] = poni_data['detector_name']

    return manual_params


def create_poni_from_params(
    detector_distance: float,
    wavelength: float,
    pixel_size: float,
    beam_center_x: float,
    beam_center_y: float,
    rot1: float = 0.0,
    rot2: float = 0.0,
    rot3: float = 0.0,
    detector_name: str = "Detector",
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create PONI data structure from manual parameters.
    从手动参数创建PONI数据结构。

    Parameters
    ----------
    detector_distance : float
        Detector distance in mm.
    wavelength : float
        Wavelength in Angstrom.
    pixel_size : float
        Pixel size in micrometers.
    beam_center_x : float
        Beam center X in pixels.
    beam_center_y : float
        Beam center Y in pixels.
    rot1, rot2, rot3 : float
        Rotations in degrees.
    detector_name : str
        Detector name.
    output_path : str, optional
        If provided, exports to .poni file.

    Returns
    -------
    dict
        PONI data dictionary.
    """
    poni_data = {
        'distance': detector_distance / 1000.0,  # mm to m
        'wavelength': wavelength / 1e10,  # A to m
        'pixel_size': pixel_size / 1e6,  # um to m
        'poni1': beam_center_x,
        'poni2': beam_center_y,
        'rot1': rot1 * 3.141592653589793 / 180,  # deg to rad
        'rot2': rot2 * 3.141592653589793 / 180,
        'rot3': rot3 * 3.141592653589793 / 180,
        'detector_name': detector_name,
    }

    if output_path:
        export_to_poni(poni_data, output_path)

    return poni_data
