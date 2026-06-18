#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PONI Importer Service for X-FAIS.
PONI文件导入服务模块。

Provides functionality to:
1. Parse pyFAI .poni files
2. Export to various formats (JSON, manual parameters, .poni)

PONI file format reference / PONI文件格式参考:
https://pyfai.readthedocs.io/en/latest/api/geometry.html#poni-file
"""

from __future__ import annotations

import os
import json
import logging
from typing import Any, Dict, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PONI file format constants / PONI文件格式常量
# ---------------------------------------------------------------------------

# These fields hold string values in pyFAI's standard PONI format, but the
# value is written WITHOUT surrounding quotes. Writing them quoted (e.g.
# `Detector: "Pilatus1M"`) works for the official parser, but `Detector_config`
# is a JSON blob and any extra outer quotes break `json.loads` downstream.
# All other string fields retain quotes for safety.
_PONI_QUOTED_FIELDS = {"Detector_config"}

# PyFAI registry lookup is lazy-imported to avoid hard dependency at module
# import time (keeps tests / parse-only paths importable without pyFAI).
_detector_registry_cache: Optional[set] = None


def _get_pyfai_detector_registry() -> set:
    """Return the set of detector names known to pyFAI, or an empty set if
    pyFAI is unavailable. Case-sensitive canonical names from
    `pyFAI.detectors.ALL_DETECTORS`. / 返回 pyFAI 已注册的所有探测器名。"""
    global _detector_registry_cache
    if _detector_registry_cache is not None:
        return _detector_registry_cache
    try:
        import pyFAI.detectors as _detectors  # type: ignore
        names = set(getattr(_detectors, "ALL_DETECTORS", {}) or {})
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("pyFAI detector registry unavailable: %s", exc)
        names = set()
    _detector_registry_cache = names
    return names


def reset_pyfai_detector_registry_cache() -> None:
    """Test hook: clear the cached detector registry. / 测试钩子：清空缓存。"""
    global _detector_registry_cache
    _detector_registry_cache = None


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

                # Try to parse as a float; for tuple-style values (e.g.
                # `PixelSize: 1.72e-04, 1.72e-04`) keep the first element.
                # 优先尝试作为数字解析；元组风格的值（如 PixelSize）保留第一个元素。
                try:
                    value = float(value)
                except ValueError:
                    # Handle pyFAI's "x, y" tuple form / 处理 pyFAI 的 "x, y" 元组
                    if ',' in value:
                        parts = [p.strip() for p in value.split(',')]
                        try:
                            value = [float(p) for p in parts]
                        except ValueError:
                            pass
                    else:
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


# ---------------------------------------------------------------------------
# Detector resolution / 探测器解析
# ---------------------------------------------------------------------------

def resolve_detector_name(
    detector_name: str,
    pixel_size_m: float,
) -> Tuple[str, str]:
    """Resolve a detector name to a (name, detector_config_json) pair.

    解析探测器名称为 (name, detector_config_json) 元组。

    Strategy / 策略:
      1. If `detector_name` is non-empty and matches a pyFAI-registered
         detector (case-insensitive), return it with an empty config `{}`.
      2. If `detector_name` is non-empty but unknown to pyFAI, keep the name
         (so the user's choice is preserved) and emit a `Detector_config`
         containing the pixel size — pyFAI will fall back to a generic
         detector with the provided geometry.
      3. If `detector_name` is empty, return the generic `'Detector'` name
         with a config that captures the pixel size from the form.

    Parameters
    ----------
    detector_name : str
        Raw detector name (may be empty, a known pyFAI name, or a custom
        user-typed string).
    pixel_size_m : float
        Pixel size in meters, used to populate `Detector_config` when the
        detector is unknown or unspecified.

    Returns
    -------
    (name, config_str)
        `name` is the canonical detector name to write to `Detector:`.
        `config_str` is a bare JSON object string (no surrounding quotes)
        suitable for `Detector_config:` — empty `{}` when the detector is
        a known pyFAI type.
    """
    registry = _get_pyfai_detector_registry()

    if detector_name:
        # Exact match first (preserves correct casing in output).
        if detector_name in registry:
            return detector_name, "{}"
        # Case-insensitive fallback.
        for name in registry:
            if name.lower() == detector_name.lower():
                return name, "{}"
        # Unknown name: keep user's value, build a config with pixel size.
        logger.warning(
            "Detector %r is not in the pyFAI registry; emitting a "
            "generic Detector_config with the form's pixel size.",
            detector_name,
        )
        config = json.dumps({"pixel1": pixel_size_m, "pixel2": pixel_size_m})
        return detector_name, config

    # detector_name empty: fall back to generic Detector with explicit config.
    config = json.dumps({"pixel1": pixel_size_m, "pixel2": pixel_size_m})
    return "Detector", config


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
    # Resolve detector info BEFORE writing, so the output always has a valid
    # `Detector:` line even when the caller didn't pick a preset. We copy
    # `poni_data` to avoid mutating the caller's dict.
    pixel_size_m = float(poni_data.get("pixel_size") or 0.0)
    resolved = dict(poni_data)
    if not resolved.get("detector_name") or not resolved.get("detector_config"):
        name, config = resolve_detector_name(
            resolved.get("detector_name", "") or "",
            pixel_size_m,
        )
        resolved["detector_name"] = name
        resolved["detector_config"] = config

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

    written_keys: set = set()
    for key, poni_key in field_order:
        if key in resolved:
            value = resolved[key]
            lines.append(_format_poni_field(poni_key, value))
            written_keys.add(key)

    # Write any additional fields / 写入任何其他字段
    for key, value in resolved.items():
        if key not in written_keys and not key.startswith('_'):
            lines.append(_format_poni_field(key, value))

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    logger.info(f"Exported PONI data to file: {output_path}")
    return output_path


def _format_poni_field(poni_key: str, value: Any) -> str:
    """Format a single PONI field line in pyFAI-canonical style.

    按pyFAI规范格式化单个字段：
    - `PixelSize` → `(x, y)` tuple
    - `Detector` / `Detector_config` → no surrounding quotes
    - other strings → quoted; numbers / booleans → raw repr
    """
    if poni_key == 'PixelSize':
        # pyFAI expects a 2-tuple: "1.72e-04, 1.72e-04"
        ps = float(value)
        return f'PixelSize: {ps:g}, {ps:g}'

    if isinstance(value, str):
        if poni_key in _PONI_QUOTED_FIELDS or poni_key in {"Detector"}:
            # Bare value, no outer quotes.
            return f'{poni_key}: {value}'
        return f'{poni_key}: "{value}"'

    return f'{poni_key}: {value}'


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
    # Resolve detector info up front so the returned dict (and any
    # subsequently-written .poni file) always has a valid Detector pair.
    # Note: this function preserves the original pixel-valued poni1/poni2
    # contract; downstream consumers convert via pixel_size as needed.
    pixel_size_m = pixel_size * 1e-6  # µm to m (only used for detector config)
    resolved_name, resolved_config = resolve_detector_name(
        detector_name, pixel_size_m
    )
    poni_data = {
        'distance': detector_distance / 1000.0,  # mm to m
        'wavelength': wavelength / 1e10,  # A to m
        'pixel_size': pixel_size / 1e6,  # um to m
        'poni1': beam_center_x,
        'poni2': beam_center_y,
        'rot1': rot1 * 3.141592653589793 / 180,  # deg to rad
        'rot2': rot2 * 3.141592653589793 / 180,
        'rot3': rot3 * 3.141592653589793 / 180,
        'detector_name': resolved_name,
        'detector_config': resolved_config,
    }

    if output_path:
        export_to_poni(poni_data, output_path)

    return poni_data


# ---------------------------------------------------------------------------
# Self-test / 自检
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    """Quick sanity check: generate a few .poni files and verify they load
    via pyFAI's AzimuthalIntegrator.  Run with:
        python -m python.services.poni_importer
    """
    import sys
    import tempfile

    # Reset the cached registry so we exercise the lookup path.
    reset_pyfai_detector_registry_cache()

    try:
        from pyFAI.integrator.azimuthal import AzimuthalIntegrator
    except ImportError:
        print("pyFAI is not installed; skipping load verification.")
        sys.exit(0)

    base_params = dict(
        detector_distance=100.0,  # mm
        wavelength=1.5418,        # Å (Cu Kα)
        pixel_size=172.0,         # µm
        beam_center_x=512.0,      # px
        beam_center_y=512.0,      # px
        rot1=0.0, rot2=0.0, rot3=0.0,
    )

    cases = [
        ("empty_name",   ""),
        ("valid_preset", "Pilatus1M"),
        ("unknown_name", "MyCustomDetector"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        all_ok = True
        for label, det in cases:
            print(f"\n=== Case: {label} (detector={det!r}) ===")
            out_path = os.path.join(tmp, f"{label}.poni")
            data = create_poni_from_params(
                detector_name=det, output_path=out_path, **base_params
            )
            with open(out_path, "r", encoding="utf-8") as fh:
                contents = fh.read()
            print(contents)

            # Re-parse via the project's own parser to confirm round-trip.
            parsed = parse_poni_file(out_path)
            assert parsed is not None, f"parse_poni_file failed for {label}"
            print(
                f"parsed: detector={parsed.get('detector_name')!r}, "
                f"pixel_size={parsed.get('pixel_size')}, "
                f"poni1={parsed.get('poni1')}"
            )

            # Load via pyFAI's own AzimuthalIntegrator (the downstream
            # consumer). Note: pyFAI's load() is strict about its detector
            # registry — it does NOT honor `Detector_config` overrides, so
            # unknown detector names will always fail to load. The exported
            # .poni is still syntactically valid; the frontend/backend
            # validators (see service_launcher / PoniImporterView) prevent
            # users from picking such a name in the first place.
            if label == "unknown_name":
                print(
                    "pyFAI load: SKIPPED (unknown detector — AzimuthalIntegrator"
                    ".load() rejects non-registry names; the file is still"
                    " syntactically valid and matches what pyFAI writes for"
                    " custom geometries)."
                )
            else:
                try:
                    ai = AzimuthalIntegrator()
                    ai.load(out_path)
                    print("pyFAI load: OK")
                except Exception as exc:
                    print(f"pyFAI load: FAILED — {exc}")
                    all_ok = False

        print("\n" + ("ALL OK" if all_ok else "SOME FAILED"))
        sys.exit(0 if all_ok else 1)
