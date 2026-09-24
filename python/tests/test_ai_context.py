#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_ai_context.py — poni_summary deterministic context tests (v0.3.0)
AI 上下文确定性计算测试（v0.3.0）

The assistant's WAXS/SAXS template decision must be grounded in REAL numbers
computed here — this test pins the contract: parsed geometry + a plausible
reachable q range for a known synthetic .poni.
助手的 WAXS/SAXS 模板决策必须基于此处计算的真实数字——本测试钉住契约：
解析出的几何 + 已知合成 .poni 的合理可达 q 范围。
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest

_PYTHON_DIR = str(Path(__file__).resolve().parent.parent)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

from services.ai_context import handle_ai_context  # noqa: E402
from services.poni_importer import export_to_poni  # noqa: E402


async def _noop_progress(fraction: float, message: str) -> None:  # noqa: ARG001
    return None


def _make_poni(tmpdir: str, wavelength_m: float = 1.5418e-10) -> str:
    path = os.path.join(tmpdir, "test.poni")
    # Write a pyFAI-loadable poni directly in METERS (create_poni_from_params
    # keeps a pixel-valued poni1/poni2 contract meant for reverse form import,
    # not for pyFAI load). Empty detector name → generic Detector with pixel
    # size + max_shape in Detector_config.
    # 直接按米制写 pyFAI 可加载的 poni（create_poni_from_params 的
    # poni1/poni2 是像素值约定，供反向导表用，非 pyFAI 加载语义）。
    # 空探测器名 → 泛型 Detector，像素尺寸与 max_shape 写入 Detector_config。
    pixel_m = 172e-6
    export_to_poni(
        {
            "distance": 0.2,
            "wavelength": wavelength_m,
            "pixel_size": pixel_m,
            "poni1": 512.0 * pixel_m,
            "poni2": 512.0 * pixel_m,
            "rot1": 0.0,
            "rot2": 0.0,
            "rot3": 0.0,
            "detector_name": "",
            "detector_shape": [1024, 1024],
        },
        path,
    )
    return path


def _run(payload: dict) -> dict:
    return asyncio.run(handle_ai_context(payload, _noop_progress, asyncio.Event()))


def test_poni_summary_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        poni = _make_poni(tmp)
        result = _run({"action": "poni_summary", "filePath": poni})

    assert result["status"] == "ok"
    assert result["distance_mm"] == pytest.approx(200.0, abs=1e-6)
    assert result["wavelength_A"] == pytest.approx(1.5418, abs=1e-6)
    assert result["pixel_size_um"] == pytest.approx(172.0, abs=1e-6)
    assert result["beam_center"][0] == pytest.approx(512.0, abs=1.0)
    # Beam center inside a generic Detector (max_shape unset → shape from
    # beam-center geometry): q_min = 0 when center is on-detector.
    # / 光束中心在探测器内时 q_min = 0。
    assert (result["q_min_nm"] or 0.0) == pytest.approx(0.0, abs=1e-9)
    # q_max must be positive and finite / q_max 必须为正有限值
    assert result["q_max_nm"] is not None and result["q_max_nm"] > 0
    assert result["q_max_A"] == pytest.approx(result["q_max_nm"] / 10.0, rel=1e-9)


def test_poni_summary_cu_wavelength_and_tth_max():
    """System-pre-computed unit facts: Cu-target check (λ=1.5418 Å → True;
    close Kα1 1.5406 → True; Mo 0.7107 → False) and corner-reachable 2θ_max
    (≈63.8° for the 200 mm / 1024 px / 172 µm geometry).
    系统预计算单位事实：铜靶判定（λ=1.5418 → True；相近值 1.5406 → True；
    Mo 0.7107 → False）与角点可达 2θ_max（该几何 ≈63.8°）。"""
    with tempfile.TemporaryDirectory() as tmp:
        result = _run({"action": "poni_summary", "filePath": _make_poni(tmp)})

    assert result["status"] == "ok"
    assert result["wavelength_is_cu"] is True
    tth_max = result["tth_max_deg"]
    # 2*atan(0.5·√2·1024·172µm / 200 mm) ≈ 63.8° — sanity window, not identity.
    assert tth_max is not None and 50.0 < tth_max < 80.0, f"implausible tth_max_deg: {tth_max}"

    with tempfile.TemporaryDirectory() as tmp:
        close = _run({"action": "poni_summary", "filePath": _make_poni(tmp, 1.5406e-10)})
        other = _run({"action": "poni_summary", "filePath": _make_poni(tmp, 0.7107e-10)})
    assert close["status"] == "ok" and close["wavelength_is_cu"] is True
    assert other["status"] == "ok" and other["wavelength_is_cu"] is False


def test_poni_summary_q_max_order_of_magnitude():
    """1 m detector-diagonal scale sanity: a ~200 mm/172 µm/512 px setup reaches
    a few tens of nm⁻¹ at the corner — WAXS territory.
    数量级健全性：200 mm/172 µm/512 px 的设置在角部可达数十 nm⁻¹——WAXS 区。"""
    with tempfile.TemporaryDirectory() as tmp:
        poni = _make_poni(tmp)
        result = _run({"action": "poni_summary", "filePath": poni})

    assert result["status"] == "ok"
    q_max = result["q_max_nm"]
    assert q_max is not None
    assert 1.0 < q_max < 500.0, f"implausible q_max_nm: {q_max}"


def test_missing_file_and_action():
    missing = _run({"action": "poni_summary", "filePath": ""})
    assert missing["status"] == "error"
    unknown = _run({"action": "bogus"})
    assert unknown["status"] == "error"
