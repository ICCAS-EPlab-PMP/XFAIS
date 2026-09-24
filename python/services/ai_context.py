#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ai_context.py — Deterministic context computation for the AI assistant
AI 助手的确定性上下文计算（无任何 AI 参与，纯几何计算）

The assistant (Jev / LLM / rules) NEVER guesses physics numbers. This module
computes them from the user's actual .poni so that template decisions are
grounded in real geometry:
  poni_summary → distance / wavelength / pixel size / beam center / reachable
                 q range at the detector corners.

助手（Jev / LLM / 规则）绝不猜测物理数值——本模块从用户真实的 .poni 计算
这些数字，使模板决策建立在真实几何之上。
"""

from __future__ import annotations

import asyncio
import math
from typing import Any, Awaitable, Callable

from .integrator import IntegratorFactory
from .poni_importer import parse_poni_file

# Cu Kα weighted wavelength (Å). Tolerance covers the Kα1 (1.5406) / Kα2
# (1.5444) doublet and lab-source calibration drift ("相近值").
# 铜靶 Kα 加权波长（Å）；容差覆盖 Kα1/Kα2 双线与实验官认定漂移（“相近值”）。
CU_KALPHA_A = 1.5418
CU_KALPHA_TOL_A = 0.01


def _reachable_q_range(ai: Any) -> dict[str, Any]:
    """q + 2θ at the detector corners via pyFAI's own pixel→physics mapping.

    Primary path: ``calc_pos_zyx`` on the four corner pixel centers (cheap).
    Fallback: analytic small-angle estimate from the detector diagonal.
    Returns the max corner 2θ (deg) alongside q_min/q_max so callers never
    re-derive scattering angles from q.
    主路径：对四个角像素中心调用 pyFAI 的 calc_pos_zyx（开销极小）。
    回退：按探测器对角线做解析小角近似。
    同时返回最大角点 2θ（度），调用方无需从 q 反推散射角。
    """
    shape = getattr(ai.detector, "max_shape", None) or getattr(ai.detector, "shape", None)
    pixel1 = float(ai.pixel1)
    pixel2 = float(ai.pixel2)
    wavelength = float(ai.wavelength or 0.0)
    if not shape or not wavelength:
        return {"q_min_nm": None, "q_max_nm": None, "tth_max_deg": None, "approx": True}

    rows, cols = int(shape[0]), int(shape[1])
    corners_rc = [(0.0, 0.0), (0.0, cols - 1.0), (rows - 1.0, 0.0), (rows - 1.0, cols - 1.0)]

    tth_values: list[float] = []
    try:
        import numpy as np

        dc1 = np.array([r * pixel1 for r, _ in corners_rc], dtype=np.float64)
        dc2 = np.array([c * pixel2 for _, c in corners_rc], dtype=np.float64)
        z, y, x = ai.calc_pos_zyx(dc1, dc2)
        for zi, yi, xi in zip(z, y, x):
            r_xy = math.sqrt(float(yi) ** 2 + float(xi) ** 2)
            tth_values.append(math.atan2(r_xy, float(zi)))
    except Exception:  # noqa: BLE001 — analytic fallback / 解析回退
        dist = float(ai.dist or 0.0)
        if dist <= 0:
            return {"q_min_nm": None, "q_max_nm": None, "tth_max_deg": None, "approx": True}
        half_diag_m = 0.5 * math.hypot(rows * pixel1, cols * pixel2)
        tth_values = [2.0 * math.atan(half_diag_m / dist)]  # upper bound only / 仅上界

    qs = [4.0 * math.pi * math.sin(t / 2.0) / wavelength for t in tth_values]  # m^-1
    qs_nm = [q * 1e-9 for q in qs]  # nm^-1

    # Beam center inside the detector → q_min = 0; otherwise the nearest
    # corner sets the minimum. / 光束中心在探测器内 → q_min = 0；否则取最近角。
    cx_px = float(ai.poni2) / pixel2 if pixel2 else 0.0
    cy_px = float(ai.poni1) / pixel1 if pixel1 else 0.0
    center_inside = 0.0 <= cx_px <= cols and 0.0 <= cy_px <= rows
    q_min_nm = 0.0 if center_inside else min(qs_nm)
    return {
        "q_min_nm": q_min_nm,
        "q_max_nm": max(qs_nm),
        "tth_max_deg": math.degrees(max(tth_values)),
        "approx": False,
    }


def _poni_summary(file_path: str) -> dict[str, Any]:
    parsed = parse_poni_file(file_path)
    if not parsed:
        return {"status": "error", "message": f"无法解析 PONI 文件 / Cannot parse PONI file: {file_path}"}

    distance_m = float(parsed.get("distance") or 0.0)
    wavelength_m = float(parsed.get("wavelength") or 0.0)
    pixel_m = float(parsed.get("pixel_size") or 0.0)
    if distance_m <= 0 or wavelength_m <= 0 or pixel_m <= 0:
        return {"status": "error", "message": "PONI 缺少距离/波长/像素尺寸 / PONI missing distance/wavelength/pixel size"}

    ai, cx, cy = IntegratorFactory.from_poni_path(file_path)
    if ai is None:
        return {"status": "error", "message": "pyFAI 无法加载该 PONI / pyFAI could not load this PONI"}

    q_range = _reachable_q_range(ai)
    q_max_nm = q_range.get("q_max_nm")
    wavelength_a = wavelength_m * 1e10
    return {
        "status": "ok",
        "filePath": file_path,
        "detector_name": parsed.get("detector_name"),
        "detector_shape": parsed.get("detector_shape"),
        "distance_mm": distance_m * 1e3,
        "wavelength_A": wavelength_a,
        # Cu-target pre-check the unit rule keys on ("相近值" tolerated).
        # 单位规则所依据的铜靶预判定（容忍“相近值”）。
        "wavelength_is_cu": abs(wavelength_a - CU_KALPHA_A) <= CU_KALPHA_TOL_A,
        "pixel_size_um": pixel_m * 1e6,
        "beam_center": [float(cx or 0.0), float(cy or 0.0)],  # [x, y] in px / 像素
        "q_min_nm": q_range.get("q_min_nm"),
        "q_max_nm": q_max_nm,
        # Handy pre-computed unit variants / 便捷单位换算
        "q_max_A": (q_max_nm / 10.0) if q_max_nm is not None else None,
        # Max reachable 2θ at the detector corners (deg) — pre-computed so the
        # assistant judges units from real angles, never guessed ones.
        # 角点最大可达 2θ（度）——助手据此判定单位，绝不臆测角度。
        "tth_max_deg": q_range.get("tth_max_deg"),
        "q_max_approx": q_range.get("approx", True),
    }


async def handle_ai_context(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """Route handler: /api/ai_context. See module docstring. 路由处理函数。"""
    action = payload.get("action", "")
    if action == "poni_summary":
        await send_progress(0.2, "Parsing PONI...")
        file_path = str(payload.get("filePath") or "")
        if not file_path:
            return {"status": "error", "message": "缺少 filePath / filePath is required"}
        result = await asyncio.get_event_loop().run_in_executor(None, _poni_summary, file_path)
        await send_progress(1.0, "Complete")
        return result
    return {"status": "error", "message": f"未知 action / Unknown action: {action!r}"}
