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
import re
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
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

# poni_data keys that carry detector metadata but are NOT pyFAI poni fields.
# They must not leak into the `.poni` body as bogus `Key: value` lines.
_NONPONI_DATA_KEYS = {"detector_shape", "detector_label", "orientation"}

# A custom detector's friendly name is persisted as a comment because pyFAI's
# factory rejects any non-registry name — the comment is the only channel that
# round-trips the label. The parser reads it back into `detector_label`.
_DETECTOR_LABEL_RE = re.compile(r"^#\s*Detector\s+label\s*:\s*(.+)$", re.IGNORECASE)

# Trailing SI unit on numeric poni values (pyFAI ≥2024): "0.1823 m", "0.001 rad".
# poni 数值尾部 SI 单位（pyFAI ≥2024）："0.1823 m"、"0.001 rad"。
_UNIT_SUFFIX_RE = re.compile(r"^\s*([+-]?[0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)\s*[A-Za-zµμ°%/*0-9^-]*\s*$")


def _strip_unit(text: str) -> str:
    """Return the numeric prefix of a value like '0.1823 m' (identity if none).

    剥离类似 '0.1823 m' 值的尾部单位，返回数字前缀（无单位则原样返回）。
    """
    m = _UNIT_SUFFIX_RE.match(text or "")
    if m:
        return m.group(1)
    return text

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


# Cache of (detector_class -> instantiated detector) for shape matching.
# Instantiating every class on every call is wasteful; we cache once.
_detector_instance_cache: Optional[Dict[str, Any]] = None


def _get_pyfai_detector_instances() -> Dict[str, Any]:
    """Return a dict mapping canonical pyFAI detector name → instantiated
    detector, deduplicated by class. Returns {} if pyFAI is unavailable.
    / 返回 pyFAI 注册名 → 探测器实例 的字典（按类去重）。"""
    global _detector_instance_cache
    if _detector_instance_cache is not None:
        return _detector_instance_cache
    result: Dict[str, Any] = {}
    try:
        import pyFAI.detectors as _detectors  # type: ignore
        registry = getattr(_detectors, "ALL_DETECTORS", {}) or {}
        seen_classes: set = set()
        # Iterate name → class; instantiate once per unique class. The same
        # detector often appears under several aliases (e.g. quantum_315,
        # adsc_q315) — we keep the first canonical name we encounter.
        for name, cls in registry.items():
            try:
                if cls in seen_classes:
                    continue
                inst = cls()
            except Exception:
                # Some detector classes need constructor args or fail to
                # instantiate bare — skip them silently.
                continue
            seen_classes.add(cls)
            # Prefer the class __name__ as the canonical pyFAI name written
            # to the Detector: line in .poni files (e.g. "Pilatus1M"), which
            # is what resolve_detector_name() matches against the registry.
            canonical = getattr(cls, "__name__", name)
            if canonical not in result:
                result[canonical] = inst
    except Exception as exc:  # pragma: no cover - depends on environment
        logger.warning("pyFAI detector instantiation unavailable: %s", exc)
    _detector_instance_cache = result
    return result


def reset_detector_instance_cache() -> None:
    """Test hook: clear the cached detector instances. / 测试钩子：清空缓存。"""
    global _detector_instance_cache
    _detector_instance_cache = None


def match_detector_by_shape(shape: Any) -> Optional[Dict[str, Any]]:
    """Find a pyFAI-registered detector whose full sensor shape matches the
    given 2-D image shape (rows, cols).

    根据 2-D 图像形状 (rows, cols) 在 pyFAI 注册表中查找形状完全匹配的探测器。

    Parameters
    ----------
    shape : sequence of int
        Either a 2-D shape ``(rows, cols)`` (e.g. from an EDF/TIFF), or a
        higher-dimensional shape whose last two axes are the image
        dimensions (e.g. a 4-D HDF5 ``(frames, channels, rows, cols)`` —
        only the last two entries are used).

    Returns
    -------
    dict or None
        ``None`` when no registered detector matches. Otherwise::

            {
                "name":        pyFAI canonical name (for the Detector: line),
                "label":       friendly display name (== class name),
                "pixel1_m":    pixel size along dim 1, in meters,
                "pixel2_m":    pixel size along dim 2, in meters,
                "max_shape":   [rows, cols] of the matched detector,
            }
    """
    try:
        # Accept any iterable; take last two axes as (rows, cols).
        shape_list = [int(s) for s in shape]
    except (TypeError, ValueError):
        return None
    if len(shape_list) < 2:
        return None
    rows, cols = shape_list[-2], shape_list[-1]
    if rows <= 0 or cols <= 0:
        return None
    target = (rows, cols)

    for name, inst in _get_pyfai_detector_instances().items():
        ms = getattr(inst, "max_shape", None)
        if not ms:
            continue
        try:
            ms_tuple = tuple(int(v) for v in ms)
        except (TypeError, ValueError):
            continue
        if ms_tuple == target:
            pixel1 = getattr(inst, "pixel1", None)
            pixel2 = getattr(inst, "pixel2", None)
            return {
                "name": name,
                "label": name,
                "pixel1_m": float(pixel1) if pixel1 is not None else None,
                "pixel2_m": float(pixel2) if pixel2 is not None else None,
                "max_shape": [rows, cols],
            }
    return None


# ---------------------------------------------------------------------------
# PONI file parsing / PONI文件解析
# ---------------------------------------------------------------------------

def parse_poni_file(file_path: str) -> Optional[Dict[str, Any]]:
    """
    Parse a pyFAI .poni file and extract geometry parameters.
    解析 pyFAI .poni 文件并提取几何参数。

    Encoding: pyFAI writes .poni in the locale's text encoding on Windows, so
    files calibrated on a Chinese-locale machine contain GBK bytes in the
    comment lines (e.g. the `# Image: fabio:///D:/.../元数据/...` path). Try
    UTF-8 first, then the preferred locale encoding and common CJK codecs,
    finally latin-1 (never fails; only comments could be garbled).
    编码：pyFAI 在 Windows 上按本地编码写 .poni，中文环境标定出的文件注释里
    含 GBK 字节（如 `# Image: .../元数据/...` 路径）。先试 UTF-8，再试本地
    首选编码与常见 CJK 编码，最后 latin-1（永不失败，至多注释乱码）。

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

    import locale as _locale

    try:
        # Read file content / 读取文件内容
        lines: Optional[list] = None
        last_exc: Optional[Exception] = None
        encodings: list = ["utf-8", "utf-8-sig"]
        preferred = _locale.getpreferredencoding(False)
        if preferred:
            encodings.append(preferred)
        encodings.extend(["gbk", "gb18030", "latin-1"])
        for enc in dict.fromkeys(encodings):  # dedupe, keep order / 去重保序
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    lines = f.readlines()
                break
            except (UnicodeDecodeError, LookupError) as exc:
                last_exc = exc
                continue
        if lines is None:
            raise last_exc or UnicodeDecodeError("poni", b"", 0, 1, "undecodable")


        # Parse key-value pairs / 解析键值对
        result: Dict[str, Any] = {}

        for line in lines:
            line = line.strip()
            # Skip comments and empty lines / 跳过注释和空行
            if not line:
                continue
            if line.startswith('#'):
                # Read back a custom detector's friendly name (written by
                # export_to_poni). pyFAI ignores comments; this is our own
                # round-trip channel for custom detector labels.
                label_match = _DETECTOR_LABEL_RE.match(line)
                if label_match:
                    result['detector_label'] = label_match.group(1).strip()
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

                # Try to parse as a float; pyFAI ≥2024 may append SI units
                # ("0.1823 m", "1.54e-10 m", "0.001 rad") — strip a trailing
                # unit token. Tuple-style values (PixelSize) keep both elements.
                # 优先按数字解析；pyFAI ≥2024 可能带 SI 单位后缀（"0.1823 m"
                # 等）——剥离尾部单位。元组风格值（PixelSize）保留各元素。
                try:
                    value = float(value)
                except ValueError:
                    if ',' in value:
                        parts = [p.strip() for p in value.split(',')]
                        try:
                            value = [float(_strip_unit(p)) for p in parts]
                        except ValueError:
                            pass
                    else:
                        try:
                            value = float(_strip_unit(value))
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

    # Registry detectors (e.g. `Detector: Pilatus300k`) carry their pixel size
    # in the pyFAI detector class, not in a `PixelSize:` line — resolve it so
    # the parsed pixel size (and derived beam-center-in-pixels) is never 0.
    # 注册表探测器（如 `Detector: Pilatus300k`）的像素尺寸保存在 pyFAI 探测器
    # 类中而非 `PixelSize:` 行——此处回退解析，避免像素尺寸（及换算的像素
    # 光束中心）为 0。
    if 'pixel_size' not in normalized:
        det_name = str(raw.get('Detector') or raw.get('detector') or '').strip()
        if det_name:
            try:
                import pyFAI.detectors as _detectors  # type: ignore
                det_cls = getattr(_detectors, det_name, None)
                if det_cls is not None:
                    det = det_cls()
                    pixel1 = getattr(det, 'pixel1', None)
                    if pixel1:
                        normalized['pixel_size'] = float(pixel1)
            except Exception:  # noqa: BLE001 — registry lookup is best-effort
                pass

    # Generic `Detector:` files (pyFAI-native and X-FAIS-exported alike) keep
    # pixel size / shape / orientation inside the `Detector_config` JSON blob.
    # Parse it so a reverse-import can restore the full geometry.
    # 通用 `Detector:` 文件（pyFAI 原生与 X-FAIS 导出）把像素尺寸/形状/方向
    # 存放在 `Detector_config` JSON 中——解析它以便反向导入完整几何。
    config_raw = raw.get('Detector_config') or raw.get('detector_config')
    if isinstance(config_raw, str) and config_raw.strip():
        try:
            cfg = json.loads(config_raw)
        except ValueError:
            cfg = None
        if isinstance(cfg, dict):
            if 'pixel_size' not in normalized:
                p1 = cfg.get('pixel1')
                p2 = cfg.get('pixel2')
                if isinstance(p1, (int, float)) and float(p1) > 0:
                    # Keep pixel2 separately when it differs (square assumed otherwise).
                    # 像素不等时单独保留 pixel2，否则按正方形处理。
                    normalized['pixel_size'] = float(p1)
                    if isinstance(p2, (int, float)) and 0 < float(p2) and float(p2) != float(p1):
                        normalized['pixel2_size'] = float(p2)
            shape = cfg.get('max_shape') or cfg.get('shape')
            if (isinstance(shape, (list, tuple)) and len(shape) == 2
                    and all(isinstance(v, (int, float)) for v in shape)):
                normalized['detector_shape'] = [int(shape[0]), int(shape[1])]
            orient = cfg.get('orientation')
            if isinstance(orient, (int, float)) and int(orient) in (0, 1, 2, 3, 4):
                normalized['orientation'] = int(orient)

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

def _coerce_shape(detector_shape: Any) -> Optional[List[int]]:
    """Normalize a shape spec into ``[rows, cols]`` positive ints, or None.
    将形状规范统一为 ``[行, 列]`` 正整数列表，非法输入返回 None。"""
    if isinstance(detector_shape, (list, tuple)) and len(detector_shape) >= 2:
        try:
            dims = [int(detector_shape[0]), int(detector_shape[1])]
        except (TypeError, ValueError):
            return None
        if dims[0] > 0 and dims[1] > 0:
            return dims
    return None


def resolve_detector_name(
    detector_name: str,
    pixel_size_m: float,
    detector_shape: Any = None,
    orientation: int = 3,
) -> Tuple[str, str, Optional[str]]:
    """Resolve a detector selection to a ``(name, config_json, label)`` triple.
    解析探测器选择为 ``(name, config_json, label)`` 三元组。

    Strategy / 策略:
      1. If ``detector_name`` is non-empty and matches a pyFAI-registered
         detector (case-insensitive), return it with a config containing
         only ``orientation`` if non-default (3). ``detector_shape`` is
         ignored — registered detectors define their own geometry.
      2. Otherwise (unknown name, empty name, or a user-defined "custom"
         detector), fall back to pyFAI's generic ``Detector`` class. The
         pixel size goes into ``Detector_config``; ``detector_shape`` (if
         valid) becomes ``max_shape``; ``orientation`` is included when
         non-default. A non-empty *unknown* name is kept only as a
         human-readable ``label`` — pyFAI's factory raises ``RuntimeError``
         on any non-registry name, so the ``Detector:`` line MUST stay the
         generic ``Detector`` for the file to load.

    Parameters
    ----------
    detector_name : str
        Raw detector name (empty, a known pyFAI name, or a custom label).
    pixel_size_m : float
        Pixel size in meters, used to populate ``Detector_config`` for the
        generic fallback.
    detector_shape : any, optional
        ``[rows, cols]`` for a custom detector → written as ``max_shape``.
        Ignored when ``detector_name`` resolves to a registered detector.
    orientation : int, optional
        pyFAI detector orientation (0-4). 3 is the default (top-left origin).
        When non-default, included in ``Detector_config`` so pyFAI uses the
        correct pixel origin. / pyFAI 探测器方向（0-4）。3 为默认值（左上角原点）。
        非默认值时写入 ``Detector_config``，使 pyFAI 使用正确的像素原点。

    Returns
    -------
    (name, config_str, label)
        ``name`` — canonical name for the ``Detector:`` line (always
        loadable). ``config_str`` — bare JSON for ``Detector_config:``
        (``{}`` for known detectors with default orientation, else includes
        ``orientation`` and/or ``pixel1``/``pixel2``/``max_shape``).
        ``label`` — user-facing name to persist as a comment, or None.
    """
    registry = _get_pyfai_detector_registry()
    name_clean = (detector_name or "").strip()

    # Normalize orientation to int; default is 3 (top-left origin).
    try:
        orient = int(orientation)
    except (TypeError, ValueError):
        orient = 3
    # Only 0-4 are valid; everything else falls back to 3.
    if orient not in (0, 1, 2, 3, 4):
        orient = 3

    if name_clean:
        # Exact match first (preserves correct casing in output).
        if name_clean in registry:
            if orient != 3:
                return name_clean, json.dumps({"orientation": orient}), None
            return name_clean, "{}", None
        # Case-insensitive fallback.
        for name in registry:
            if name.lower() == name_clean.lower():
                if orient != 3:
                    return name, json.dumps({"orientation": orient}), None
                return name, "{}", None

    # Unknown / empty / custom: use pyFAI's generic Detector class so the
    # file always loads. An arbitrary user-typed name CANNOT be the
    # `Detector:` value (pyFAI's factory rejects non-registry names), so we
    # keep it only as a comment label.
    config: Dict[str, Any] = {"pixel1": pixel_size_m, "pixel2": pixel_size_m}
    shape = _coerce_shape(detector_shape)
    if shape is not None:
        config["max_shape"] = shape
    if orient != 3:
        config["orientation"] = orient
    label = name_clean or None
    if name_clean:
        logger.info(
            "Detector %r is not in the pyFAI registry; using the generic "
            "Detector class with the form's geometry (label saved as a comment).",
            name_clean,
        )
    return "Detector", json.dumps(config), label


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
        name, config, label = resolve_detector_name(
            resolved.get("detector_name", "") or "",
            pixel_size_m,
            resolved.get("detector_shape"),
            resolved.get("orientation", 3),
        )
        resolved["detector_name"] = name
        resolved["detector_config"] = config
        if label:
            resolved["_detector_label"] = label

    lines = [
        "# PONI file generated by X-FAIS",
        "# Generated from imported PONI data",
    ]

    # Persist a custom detector's user-facing name as a comment. pyFAI can't
    # store an arbitrary detector name (its factory rejects non-registry
    # names), so this comment is the only place the label round-trips; the
    # parser reads it back into `detector_label`.
    label = resolved.pop("_detector_label", None)
    if label:
        lines.append(f"# Detector label: {label}")

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
        if key not in written_keys and not key.startswith('_') and key not in _NONPONI_DATA_KEYS:
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
    # poni1/poni2 are in METERS in PONI data; convert via pixel size so the
    # exported "beam_center in pixels" contract actually holds.
    # poni1/poni2 在 PONI 数据中以米为单位；需按像素尺寸换算为像素，
    # 才符合导出 "beam_center 单位为像素" 的约定。
    if 'poni1' in poni_data and 'poni2' in poni_data:
        pixel_m = float(poni_data.get('pixel_size') or 0.0)
        if pixel_m > 0:
            manual_params['beam_center'] = [
                poni_data['poni1'] / pixel_m,
                poni_data['poni2'] / pixel_m,
            ]
        else:
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
    orientation: int = 3,
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
    orientation : int, optional
        pyFAI detector orientation (0-4). Default 3 = top-left origin.
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
    resolved_name, resolved_config, label = resolve_detector_name(
        detector_name, pixel_size_m, orientation=orientation
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
    # Propagate a custom detector's label so export_to_poni can write the
    # comment line (it skips re-resolution since name+config are already set).
    if label:
        poni_data['_detector_label'] = label

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
                f"poni1={parsed.get('poni1')}, "
                f"label={parsed.get('detector_label')!r}"
            )

            # A custom (non-registry) detector name must map to the generic
            # `Detector` class + a label comment — this is the regression
            # test for the bug where unknown names produced an un-loadable
            # `Detector: <user_name>` line.
            if label == "unknown_name":
                assert "Detector: Detector" in contents, \
                    "unknown detector must resolve to generic Detector"
                assert "# Detector label: MyCustomDetector" in contents, \
                    "custom detector label comment must be written"
                assert parsed.get("detector_label") == "MyCustomDetector", \
                    "parser must round-trip the custom detector label"

            # Load via pyFAI's own AzimuthalIntegrator (the downstream
            # consumer). Every case now loads: known detectors use their
            # real class; custom/empty names fall back to the generic
            # `Detector` class with a pixel-size config.
            try:
                ai = AzimuthalIntegrator()
                ai.load(out_path)
                print(f"pyFAI load: OK (detector={ai.detector.name})")
            except Exception as exc:
                print(f"pyFAI load: FAILED — {exc}")
                all_ok = False

        # Exercise a custom detector with an explicit array size → the
        # `max_shape` must land in `Detector_config` and the file must load.
        print("\n=== Case: custom_shape (Homemade CCD, 512x512) ===")
        shape_path = os.path.join(tmp, "custom_shape.poni")
        shape_data = dict(
            distance=0.1, wavelength=1.5418e-10, pixel_size=75e-6,
            poni1=0.0384, poni2=0.0384, rot1=0.0, rot2=0.0, rot3=0.0,
            detector_name="Homemade CCD",
            detector_shape=[512, 512],
        )
        export_to_poni(shape_data, shape_path)
        with open(shape_path, "r", encoding="utf-8") as fh:
            shape_contents = fh.read()
        print(shape_contents)
        assert "Detector: Detector" in shape_contents
        assert '"max_shape": [512, 512]' in shape_contents, \
            "detector_shape must be written as max_shape"
        try:
            ai = AzimuthalIntegrator()
            ai.load(shape_path)
            print(f"pyFAI load: OK (detector={ai.detector.name}, "
                  f"shape={ai.detector.max_shape})")
        except Exception as exc:
            print(f"pyFAI load: FAILED — {exc}")
            all_ok = False

        print("\n" + ("ALL OK" if all_ok else "SOME FAILED"))
        sys.exit(0 if all_ok else 1)
