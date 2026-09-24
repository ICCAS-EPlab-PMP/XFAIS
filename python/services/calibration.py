#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
calibration.py — pyFAI-based geometry calibration engine (headless core of pyFAI-calib2)
标定服务 — 基于 pyFAI 的几何标定引擎（pyFAI-calib2 的无界面核心）

Implements the full powder-diffraction calibration workflow on top of pyFAI:
实现了完整的粉末衍射标定流程：

  1. ``list_calibrants`` — enumerate the calibrants shipped with pyFAI
     枚举 pyFAI 自带标样
  2. ``setup``           — load a calibration image + calibrant + detector,
                           creating an in-memory session / 加载标定图与标样，
                           建立内存会话
  3. ``detect_peaks``    — automatic peak-group extraction via
                           ``pyFAI.massif.Massif`` / 用 Massif 自动提取峰组
  4. ``update_peaks``    — (re)assign user-edited peak lists to theoretical
                           rings / 将（用户编辑后的）峰列表对齐到理论环
  5. ``refine``          — constrain-fit the geometry
                           (``GeometryRefinement.refine1/2/3``) / 约束精修几何
  6. ``ring_overlay``    — iso-contour polylines of every visible theoretical
                           ring (silx marching squares) / 理论环等值线叠加
  7. ``integrate_preview`` — quick 1-D curve + 2-D cake of the calibrant
                           frame under the CURRENT refined geometry
                           / 以当前精修几何对标定图做 1D/2D 积分预览
  8. ``export_poni``     — persist the refined geometry as a standard .poni
                           (``autoSave`` writes to the OS temp dir and returns
                           the path — the 去积分 auto-import path)
                           / 将精修结果保存为标准 .poni 文件（autoSave 时
                           写入系统临时目录并返回路径——去积分自动导入用）
  9. ``seed_from_poni``  — parse an existing .poni back into seed parameters
                           / 解析已有 .poni 作为初始参数

All heavy compute (massif, refine, contours) runs in the default
``ThreadPoolExecutor`` so the asyncio event loop is never blocked.
所有重计算（massif、精修、等值线）均在线程池中执行，不阻塞事件循环。

Only headless dependencies are used (numpy / pyFAI / silx) — no GUI.
仅依赖无界面库（numpy / pyFAI / silx），不含任何 GUI 依赖。
"""

from __future__ import annotations

import asyncio
import logging
import math
import time
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module constants / 模块常量
# ---------------------------------------------------------------------------

#: Bounded session cache (FIFO). / 有界会话缓存（先进先出淘汰）。
_MAX_SESSIONS: int = 4

#: Session store keyed by session id. / 以会话 id 为键的会话表。
_SESSIONS: Dict[str, Dict[str, Any]] = {}

#: Ring-index order understood by GeometryRefinement. / 精修器接受的参数顺序。
_PARAM_ORDER: tuple = (
    "dist", "poni1", "poni2", "rot1", "rot2", "rot3", "wavelength",
)

#: Default per-parameter refinement flags. X-FAIS default (v0.3.x 用户反馈):
#: refine distance + beam centre (poni1/poni2) only — rot1–3 stay FIXED
#: (lab detectors are mounted near-normal, freeing tilts with few rings
#: makes the fit degenerate) and the wavelength stays fixed (known source).
#: 各参数默认精修开关：默认只精修距离与光束中心（poni1/poni2）；rot1–3 默认
#: 固定（实验室探测器近似正对光束，环数不多时放开倾角易退化），波长默认固定。
_DEFAULT_FREE: Dict[str, bool] = {
    "dist": True, "poni1": True, "poni2": True,
    "rot1": False, "rot2": False, "rot3": False,
    "wavelength": False,
}

#: Search tolerance (percent) applied around the current guess before
#: refining — mirrors ``pyFAI.gui.cli_calibration.Recalibrate`` (set_tolerance(10),
#: relaxed a little for first guesses further from truth).
#: 精修前在当前初值附近施加的搜索容差（百分比）——对标 pyFAI 官方
#: Recalibrate 流程的 set_tolerance(10)，稍放宽以容忍较差初值。
_REFINE_TOLERANCE_PCT: float = 15.0

#: Maximum theoretical rings rendered by ``ring_overlay``. / 叠加环数上限。
_MAX_OVERLAY_RINGS: int = 64

#: Downsample target for one ring polyline. / 单环折线的降采样点数上限。
_MAX_RING_POINTS: int = 600

#: Peak cap returned by ``pick_peak`` — one click yields the whole clicked
#: massif REGION (seed maximum first, neighbors included), like calib2.
#: 单击拾取返回的峰数上限——一次点击收取整个所点峰群（种子极大优先，含邻近）。
_PICK_PEAK_NMAX: int = 30

#: Default harvest cap for ``ring_pick`` — calib2 sizes full-circle extraction
#: at "360 points for a full circle" (one per degree, RingExtractor._extract);
#: the old fixed 80 starved continuous whole-ring harvests.
#: 环选默认收峰上限——calib2 整环按“每度一点共 360”计（RingExtractor._extract）；
#: 原固定值 80 会截断整环连续收峰。
_RING_PICK_KEEP: int = 360

#: Candidate-pixel floor before ``ring_pick`` relaxes its adaptive threshold
#: from band mean+std to band mean — mirrors calib2's ``size2 < 1000`` rule
#: (RingExtractor._extract). / 环选自适应阈值放宽前的候选像素下限——对标
#: calib2 RingExtractor._extract 的 ``size2 < 1000`` 规则。
_RING_PICK_MIN_PIXELS: int = 1000

#: X-FAIS supplementary calibrants offered in addition to pyFAI's factory
#: set (.D registry). d-spacings in ANGSTROM, descending — exactly the unit
#: and ordering convention of pyFAI's own ``pyFAI/resources/calibration/*.D``
#: files (verified against LaB6.D: "4.15682600 # (1 0 0)"), which
#: ``Calibrant(dspacing=...)`` expects. / X-FAIS 补充标样（pyFAI 工厂标样
#: 之外）。d 间距单位为埃、降序——与 pyFAI 自带 .D 文件（见 LaB6.D）的
#: 单位与排序约定完全一致，直接喂给 ``Calibrant(dspacing=...)``。
#:
# Y2O3 — cubic bixbyite (Ia-3), a = 10.604 Å (standard NIST-class calibrant
# value). d = a / sqrt(h²+k²+l²) for the strong allowed reflections
# (222)(400)(440)(622)(444)(800):
#   10.604/sqrt(12)=3.061111  sqrt(16)=2.651  sqrt(32)=1.87454
#   sqrt(44)=1.598613  sqrt(48)=1.530556  sqrt(64)=1.3255
_CUSTOM_Y2O3_D: List[float] = [
    3.061111, 2.651, 1.87454, 1.598613, 1.530556, 1.3255,
]

# Polypropylene — isotactic α-form powder standard (monoclinic P2₁/c).
#
# PROVENANCE (v0.3.x 用户反馈"丢失了很多线"): the original hand-typed 6-line
# list stopped at d = 3.12 Å (2θ ≈ 28.6° Cu), so every higher-angle ring was
# invisible to picking/overlay. This table was COMPUTED from the published
# crystal structure — Mencik, J. Macromol. Sci. B 6 (1972) 101, COD entry
# 1552371 (P 1 21/c 1; coordinates) on the canonical cell
# a = 6.65 Å, b = 20.78 Å, c = 6.495 Å, β = 99.62° — via full structure
# factors (36 C atoms, Cromer–Mann carbon form factor, Lorentz-polarisation
# weighting). Reflections within 0.4 % in d merge into one line (e.g. 111+050
# at 4.156 Å, the 140/13̄1 doublet at ~4.07 Å). Selection: I ≥ 1 % of the
# (110) line and d ≥ 1.93 Å (2θ ≤ 47.3° Cu Kα) → 39 observable lines, the
# same convention as pyFAI's own .D files (LaB6.D carries >1000).
# 复核锚点：110→6.2526, 040→5.1950, 130→4.7616, 111/050→4.1560,
# 140/13̄1→4.0718, 041→4.0344, 150→3.5102, 060→3.4633, 200/14̄1→3.2851,
# 220/20̄1→3.1386 …，与文献 α-iPP 粉末图一致。
_CUSTOM_PP_D: List[float] = [
    6.2526, 5.1950, 4.7616, 4.1560, 4.0718, 4.0344, 3.9262, 3.6166,
    3.5102, 3.4633, 3.2851, 3.2018, 3.1645, 3.1386, 3.0877, 3.0623,
    2.8588, 2.7257, 2.7044, 2.6933, 2.6543, 2.5552, 2.5046, 2.4224,
    2.4070, 2.3808, 2.3257, 2.3089, 2.1855, 2.1735, 2.1567, 2.1480,
    2.1264, 2.0976, 2.0425, 2.0172, 1.9644, 1.9357, 1.9200,
]

#: name → d-spacing list (Å). Names show up in ``list_calibrants`` and are
#: accepted by ``setup`` (calibrantName / calibrant). / 名称→d 间距列表（埃）。
#: 名称会出现在 ``list_calibrants`` 中并可被 ``setup`` 接受。
_CUSTOM_CALIBRANTS: Dict[str, List[float]] = {
    "Y2O3_custom": list(_CUSTOM_Y2O3_D),
    "Polypropylene_custom": list(_CUSTOM_PP_D),
}

#: Citation block returned by export_poni. / 导出时附带的文献引用信息。
_CITATION: Dict[str, str] = {
    "calib2_paper": (
        "Kieffer, Valls, Blanc & Hennig, J. Synchrotron Rad. 27 (2020) "
        "558-566, doi:10.1107/S1600577520000776"
    ),
    "pyfai_paper": (
        "Ashiotis et al., J. Appl. Cryst. 48 (2015) 510-519, "
        "doi:10.1107/S1600576715004306"
    ),
    "license": "pyFAI is MIT-licensed",
    # Ready-made DOI links so the frontend never has to guess.
    # 现成 DOI 链接，前端无需再兜底猜值。
    "calib2_url": "https://doi.org/10.1107/S1600577520000776",
    "pyfai_url": "https://doi.org/10.1107/S1600576715004306",
}


# ---------------------------------------------------------------------------
# Small helpers / 小工具
# ---------------------------------------------------------------------------

def _err(message_en: str, message_zh: str = "") -> Dict[str, str]:
    """Build a bilingual error payload. / 构造双语错误返回。"""
    msg = f"{message_en}" + (f" / {message_zh}" if message_zh else "")
    return {"status": "error", "message": msg}


def _check_cancel(cancel_event: Optional[asyncio.Event]) -> None:
    """Raise asyncio.CancelledError if the caller requested cancellation.
    若调用方请求取消则抛出 asyncio.CancelledError。"""
    if cancel_event is not None and cancel_event.is_set():
        raise asyncio.CancelledError("calibration cancelled / 标定已取消")


async def _run_blocking(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Run ``fn`` in the default thread-pool executor. / 在默认线程池中执行 fn。"""
    loop = asyncio.get_running_loop()
    call = partial(fn, *args, **kwargs) if kwargs else partial(fn, *args)
    return await loop.run_in_executor(None, call)


async def _progress(send_progress: Optional[Callable], fraction: float, message: str) -> None:
    """Fire a progress callback if provided. / 存在回调时上报进度。"""
    if send_progress is not None:
        await send_progress(float(fraction), message)


def _get_session(session_id: Any) -> Optional[Dict[str, Any]]:
    """Fetch a live calibration session. / 按 id 取会话。"""
    if not isinstance(session_id, str):
        return None
    return _SESSIONS.get(session_id)


def _store_session(session: Dict[str, Any]) -> None:
    """Insert/refresh a session with FIFO eviction beyond the cap.
    插入或刷新会话，超限按先进先出淘汰。"""
    sid = session["id"]
    if sid in _SESSIONS:
        _SESSIONS.pop(sid)
    _SESSIONS[sid] = session
    while len(_SESSIONS) > _MAX_SESSIONS:
        oldest = next(iter(_SESSIONS))
        _SESSIONS.pop(oldest)


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """Coerce to float, falling back to ``default``. / 安全转 float。"""
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _sweep_2d(data: np.ndarray) -> np.ndarray:
    """Reduce a loaded array to a plain 2-D frame. / 将加载数组规约为 2D 帧。"""
    arr = np.asarray(data)
    while arr.ndim > 2:
        arr = arr[0]
    return arr


def _massif_mask(session: Dict[str, Any], beyond: bool) -> Optional[np.ndarray]:
    """Picking mask for pyFAI ``Massif`` — the session mask (mask file +
    intensity bounds + dead pixels, see ``setup``), None when the calib2-style
    "extract peaks, beyond masked values" variant is requested.
    供 Massif 使用的拾取掩膜——即会话掩膜（掩膜文件 + 强度上下限 + 死像素）；
    勾选“越过掩码提取”（calib2 Ring 工具）时返回 None 不设掩膜。
    """
    if beyond:
        return None
    mask = session.get("mask")
    if mask is not None:
        return mask
    # Legacy fallback for mask-less sessions: dead pixels only.
    # 无掩膜会话的兜底：仅死像素。
    dead = session["data"] < 0
    return dead if bool(dead.any()) else None


def _session_massif(session: Dict[str, Any], beyond: bool) -> Any:
    """Cached pyFAI ``Massif`` per mask variant (PERFORMANCE, 大图响应过慢).

    ``Massif.__init__`` builds a ``Bilinear`` over the full frame and its
    ``peaks_from_area`` / ``find_peaks`` lazily compute ``get_labeled_massif``
    (binning + gaussian blur + labeling) — together several seconds on a
    2048² frame. calib2 keeps ONE Massif for the lifetime of the peak-picking
    task; the old code rebuilt the object inside every pick_peak / ring_pick /
    detect_peaks call, recomputing the labeled massif each time. This helper
    caches one Massif per mask variant ("masked" = session pick mask, "nomask"
    = the beyond-mask calib2 Ring variant) in the session; the expensive
    labeled-massif state lives INSIDE the Massif and is therefore reused
    automatically. Invalidated by ``setup`` (``massif_cache`` reset), which is
    the only path that can change the image or the mask.
    会话级 Massif 缓存（性能修复：大图响应过慢）。按掩膜变体缓存一个 Massif；
    昂贵的 labeled massif 状态在 Massif 对象内部，随对象复用自动命中。仅在
    setup（可能更换图像/掩膜的唯一路径）时重置缓存。cache 命中会记 INFO 日志
    （测试据 "massif cache: HIT" 断言）。
    """
    from pyFAI.massif import Massif

    mask = None if beyond else _massif_mask(session, False)
    key = "nomask" if mask is None else "masked"
    cache = session.setdefault("massif_cache", {})
    massif = cache.get(key)
    if massif is None:
        massif = Massif(data=session["data"], mask=mask)
        cache[key] = massif
        logger.info(
            "calibration massif cache: MISS → built %s Massif (session %s)",
            key, session.get("id"),
        )
    else:
        logger.info(
            "calibration massif cache: HIT (%s variant, session %s)",
            key, session.get("id"),
        )
    return massif


def _downsample_mask_grid(mask: np.ndarray, max_dim: int = 256) -> Dict[str, Any]:
    """Coarse tile-any downsample of a boolean mask for the canvas overlay.

    The mask is reduced to ≤ ``max_dim``×``max_dim`` tiles; a tile is True
    (1) when ANY of its pixels is masked, so no masked cluster can hide between
    tiles. Grid is returned row-major flattened as 0/1 ints.
    将布尔掩膜降采样为 ≤256×256 的粗网格用于画布叠加；任一像素被屏蔽则该格
    为 1（tile-any），屏蔽簇不会藏在格间。grid 按行优先展平为 0/1。
    """
    h, w = mask.shape
    rows = min(max_dim, int(h))
    cols = min(max_dim, int(w))
    # linspace starts are strictly increasing ints while rows <= h (spacing ≥1),
    # so reduceat segments tile the frame exactly.
    # rows ≤ h 时 linspace 起点严格递增，reduceat 分段恰好铺满整帧。
    row_starts = np.linspace(0, int(h), rows + 1).astype(np.intp)[:-1]
    col_starts = np.linspace(0, int(w), cols + 1).astype(np.intp)[:-1]
    tiles = np.logical_or.reduceat(
        np.logical_or.reduceat(mask, row_starts, axis=0),
        col_starts, axis=1,
    )
    return {
        "rows": int(rows),
        "cols": int(cols),
        "grid": tiles.astype(np.uint8).ravel().tolist(),
    }


def _geometry_summary(gr: Any, pixel1: float, pixel2: float) -> Dict[str, Any]:
    """Export a refined geometry in UI-friendly units. / 以界面友好单位导出几何。"""
    return {
        "dist_mm": float(gr.dist) * 1e3,
        "poni1_mm": float(gr.poni1) * 1e3,
        "poni2_mm": float(gr.poni2) * 1e3,
        "rot1_deg": float(gr.rot1) * 180.0 / math.pi,
        "rot2_deg": float(gr.rot2) * 180.0 / math.pi,
        "rot3_deg": float(gr.rot3) * 180.0 / math.pi,
        "wavelength_A": float(gr.wavelength) * 1e10,
        # poni1 runs along rows (y), poni2 along columns (x).
        # poni1 沿行（y），poni2 沿列（x）。
        "center_x_px": float(gr.poni2) / pixel2,
        "center_y_px": float(gr.poni1) / pixel1,
    }


# ---------------------------------------------------------------------------
# Lazy pyFAI / silx access (import cost + testability)
# pyFAI / silx 延迟导入（降低导入开销，便于测试）
# ---------------------------------------------------------------------------

def _pyfai_calibrant_module():
    import pyFAI.calibrant as calibrant_mod
    return calibrant_mod


def _resolve_calibrant(
    calibrant_name: Optional[str],
    calibrant_file: Optional[str],
    wavelength_m: float,
) -> Any:
    """Build a wavelength-synced pyFAI Calibrant from a name or a .D file.
    依据标样名或 .D 文件构建已同步波长的 pyFAI 标样对象。"""
    calibrant_mod = _pyfai_calibrant_module()

    calibrant = None
    name_used = ""
    if calibrant_name:
        name_used = str(calibrant_name)
        if name_used in _CUSTOM_CALIBRANTS:
            # X-FAIS supplementary calibrant (no .D file in pyFAI's registry):
            # build straight from the d-spacing list via the public pyFAI
            # calibrant API, same Å unit a .D file would carry.
            # X-FAIS 补充标样（pyFAI 注册表中无对应 .D 文件）：直接按 d 间距
            # 列表经 pyFAI 公共标样 API 构建，单位（埃）与 .D 文件一致。
            calibrant = calibrant_mod.Calibrant(
                dspacing=list(_CUSTOM_CALIBRANTS[name_used]),
            )
        elif not calibrant_mod.CALIBRANT_FACTORY.has_key(name_used):
            raise KeyError(
                f"Unknown calibrant '{name_used}'. / 未知标样 “{name_used}”。"
            )
        else:
            calibrant = calibrant_mod.get_calibrant(name_used)
    elif calibrant_file:
        path = Path(calibrant_file)
        if not path.is_file():
            raise FileNotFoundError(
                f"Calibrant file not found: {path} / 未找到标样文件：{path}"
            )
        calibrant = calibrant_mod.Calibrant(filename=str(path))
        name_used = path.stem
    else:
        raise ValueError(
            "Either calibrantName or calibrantFile is required. / "
            "必须提供 calibrantName 或 calibrantFile 之一。"
        )

    # Sync the ring 2θ list to the session wavelength (PEP8 property setter).
    # 将环 2θ 列表与会话波长同步（PEP8 属性赋值）。
    calibrant.wavelength = float(wavelength_m)
    if not len(calibrant.dspacing):
        raise ValueError(
            f"Calibrant '{name_used}' has no d-spacings. / "
            f"标样 “{name_used}” 不含 d 间距数据。"
        )
    return calibrant, name_used


# ---------------------------------------------------------------------------
# Action handlers / 各 action 处理函数
# ---------------------------------------------------------------------------

async def _action_list_calibrants(payload: dict) -> dict:
    """Enumerate pyFAI's factory calibrants plus the X-FAIS supplements.
    枚举 pyFAI 工厂标样 + X-FAIS 补充标样。"""
    calibrant_mod = _pyfai_calibrant_module()
    names = sorted(
        set(str(n) for n in calibrant_mod.CALIBRANT_FACTORY.keys())
        | set(_CUSTOM_CALIBRANTS.keys()),
    )
    return {"status": "ok", "calibrants": names}


async def _action_setup(payload: dict, send_progress, cancel_event) -> dict:
    """Load image + calibrant + detector and create a calibration session.
    加载标定图、标样与探测器参数，建立标定会话。

    Payload keys / 载荷键：
      filePath       (str, required)  image path / 图像路径
      frame          (int, optional)  HDF5 frame index / HDF5 帧序号
      calibrantName  (str, optional)  pyFAI factory name / pyFAI 标样名
      calibrantFile  (str, optional)  path to a .D d-spacing file / .D 文件路径
      detectorName   (str, optional)  pyFAI registry detector / pyFAI 注册探测器
      pixelSizeUm    (float, optional) fallback pixel size / 兜底像素尺寸（微米）
      wavelengthA    (float, required) wavelength in Å / 波长（埃）
      distGuessMm    (float, required) initial distance guess / 初始距离猜测（毫米）
      sessionId      (str, optional)  reuse an existing session / 复用已有会话
      maskPath       (str, optional)  mask file (.edf/.npy/.tif/.tiff/.npz)
                                       loaded via MaskBuilder / 掩膜文件
      maskMin        (float, optional) intensity lower bound: data < min is
                                       masked / 强度下限：低于者屏蔽
      maskMax        (float, optional) intensity upper bound: data > max is
                                       masked / 强度上限：高于者屏蔽
    """
    from .image_loader import ImageLoader

    await _progress(send_progress, 0.0, "Setting up calibration session / 正在建立标定会话")
    _check_cancel(cancel_event)

    file_path = payload.get("filePath")
    if not file_path or not Path(str(file_path)).is_file():
        return _err(
            f"Image file not found: {file_path}",
            f"未找到图像文件：{file_path}",
        )

    wavelength_a = _as_float(payload.get("wavelengthA"))
    dist_guess_mm = _as_float(payload.get("distGuessMm"))
    if wavelength_a is None or wavelength_a <= 0:
        return _err("wavelengthA is required and must be > 0 / 必须提供有效波长 wavelengthA（> 0）")
    if dist_guess_mm is None or dist_guess_mm <= 0:
        return _err("distGuessMm is required and must be > 0 / 必须提供有效初始距离 distGuessMm（> 0）")
    wavelength_m = wavelength_a * 1e-10
    dist_guess_m = dist_guess_mm * 1e-3

    frame = int(_as_float(payload.get("frame"), 0.0) or 0.0)

    # -- calibrant / 标样 ---------------------------------------------------
    # Accept both spellings: the canonical `calibrantName` and the frontend's
    # short `calibrant` / `detector` (CalibrationView payload style).
    # 同时接受两种拼写：规范名 calibrantName 与前端简写 calibrant/detector。
    try:
        calibrant, calibrant_name = _resolve_calibrant(
            payload.get("calibrantName") or payload.get("calibrant"),
            payload.get("calibrantFile"), wavelength_m,
        )
    except (KeyError, ValueError, FileNotFoundError) as exc:
        return _err(str(exc))

    await _progress(send_progress, 0.25, "Loading image / 正在加载图像")
    _check_cancel(cancel_event)

    # -- image / 图像 -------------------------------------------------------
    try:
        data, dead_mask, _meta = await _run_blocking(
            ImageLoader.load, str(file_path), None, None, frame,
        )
    except Exception as exc:  # noqa: BLE001 — surfaced to the frontend
        return _err(f"Failed to load image: {exc}", f"图像加载失败：{exc}")
    if data is None:
        return _err("No image data loaded / 未能加载图像数据")
    image = _sweep_2d(data)
    if image.ndim != 2 or min(image.shape) < 8:
        return _err("Image is not a valid 2-D frame / 图像不是有效的 2D 帧")
    shape = (int(image.shape[0]), int(image.shape[1]))

    # -- mask / 掩膜 ----------------------------------------------------------
    # REQ 1 (mask at setup, 防止拾取错误): an optional mask FILE plus optional
    # intensity bounds combine with dead pixels into session["mask"]; EVERY
    # later picking action (pick_peak / ring_pick / detect_peaks) feeds it to
    # Massif and subtracts it from the candidate area, so hot spots / beamstop
    # edges / saturated blobs can never be harvested as peaks.
    # 可选掩膜文件 + 可选强度上下限 + 死像素合并进会话掩膜；后续所有拾取
    # 动作都把该掩膜喂给 Massif 并从候选区扣除——亮点/遮挡/饱和斑绝不会被收峰。
    mask_path = payload.get("maskPath")
    mask_file: Optional[np.ndarray] = None
    if mask_path:
        if not Path(str(mask_path)).is_file():
            return _err(
                f"Mask file not found: {mask_path}",
                f"未找到掩膜文件：{mask_path}",
            )
        try:
            from .mask_builder import MaskBuilder
            mask_file = await _run_blocking(MaskBuilder.load_mask_file, str(mask_path))
        except Exception as exc:  # noqa: BLE001 — surfaced to the frontend
            return _err(f"Failed to load mask file: {exc}", f"掩膜文件加载失败：{exc}")
        if tuple(mask_file.shape) != shape:
            return _err(
                f"Mask shape {tuple(mask_file.shape)} does not match image shape "
                f"{shape}",
                f"掩膜尺寸 {tuple(mask_file.shape)} 与图像 {shape} 不一致",
            )
    mask_min = _as_float(payload.get("maskMin"))
    mask_max = _as_float(payload.get("maskMax"))

    session_mask: Optional[np.ndarray] = None
    if (mask_file is not None or mask_min is not None or mask_max is not None
            or dead_mask is not None):
        session_mask = np.zeros(shape, dtype=bool)
        if mask_file is not None:
            session_mask |= mask_file
        if mask_min is not None:
            session_mask |= image < mask_min
        if mask_max is not None:
            session_mask |= image > mask_max
        # Dead pixels always count / 死像素始终计入.
        session_mask |= image < 0
        if dead_mask is not None and tuple(getattr(dead_mask, "shape", ())) == shape:
            session_mask |= np.asarray(dead_mask, dtype=bool)

    masked_pixels = int(session_mask.sum()) if session_mask is not None else 0
    mask_stats = {
        "maskedPixels": masked_pixels,
        "ratio": float(masked_pixels) / float(shape[0] * shape[1]),
    }
    mask_overlay = (
        _downsample_mask_grid(session_mask) if session_mask is not None else None
    )

    # -- detector / 探测器像素 ---------------------------------------------
    pixel_size_um = _as_float(payload.get("pixelSizeUm"))
    pixel1 = pixel2 = None
    detector_name = payload.get("detectorName") or payload.get("detector")
    if detector_name:
        try:
            from pyFAI.detectors import detector_factory
            det = detector_factory(str(detector_name))
            pixel1 = _as_float(getattr(det, "pixel1", None))
            pixel2 = _as_float(getattr(det, "pixel2", None))
        except Exception as exc:  # noqa: BLE001 — fall back to pixelSizeUm
            logger.warning("detector_factory(%r) failed: %s", detector_name, exc)
            pixel1 = pixel2 = None
    if (pixel1 is None or pixel2 is None or pixel1 <= 0 or pixel2 <= 0):
        if pixel_size_um is None or pixel_size_um <= 0:
            return _err(
                "Cannot resolve pixel size: provide a valid detectorName or "
                "pixelSizeUm / 无法确定像素尺寸：请提供有效的 detectorName 或 pixelSizeUm",
            )
        pixel1 = pixel2 = pixel_size_um * 1e-6
    pixel_size_um = 0.5 * (pixel1 + pixel2) * 1e6

    # -- session / 会话 ------------------------------------------------------
    session_id = payload.get("sessionId")
    session = _get_session(session_id)
    if session is None:
        session = {"id": uuid4().hex}
    session.update(
        {
            "data": image.astype(np.float32, copy=True),
            "calibrant": calibrant,
            "pixel1": float(pixel1),
            "pixel2": float(pixel2),
            "shape": shape,
            "wavelength": wavelength_m,
            "dist0": dist_guess_m,
            "peaks": [],
            "gr": None,
            "mask": session_mask,
            # PERFORMANCE (大图响应过慢): picking caches die with the frame.
            # setup is the ONLY path that can change the image or the mask,
            # so resetting here covers every invalidation case.
            # setup 是唯一可能更换图像/掩膜的路径，在此重置即覆盖全部失效场景。
            "massif_cache": {},
            "tth_cache": None,
        },
    )
    _store_session(session)

    await _progress(send_progress, 1.0, "Session ready / 会话就绪")
    return {
        "status": "ok",
        "sessionId": session["id"],
        "shape": [shape[0], shape[1]],
        "calibrantName": calibrant_name,
        "pixelSizeUm": pixel_size_um,
        "wavelengthA": wavelength_a,
        "distMm": dist_guess_mm,
        "maskStats": mask_stats,
        "maskOverlay": mask_overlay,
    }


async def _action_detect_peaks(
    session: Dict[str, Any], payload: dict, send_progress, cancel_event,
) -> dict:
    """Automatic peak-group extraction with pyFAI.massif.Massif.
    用 pyFAI.massif.Massif 自动提取峰组。

    Sensitivity mapping (pyFAI 2026.3.0 has no direct "sensitivity" knob on
    Massif, so it drives the two underlying controls of
    ``Massif.peaks_from_area``):
    灵敏度映射（2026.3.0 的 Massif 没有 “灵敏度” 旋钮，因此映射到
    ``peaks_from_area`` 的两个底层控制量）：
      * intensity cutoff = data_max * lerp(0.5 → 0.1, sensitivity)
        — higher sensitivity lowers the cutoff so fainter rings contribute;
        更高的灵敏度降低强度阈值，让弱环也能出点；
      * keep            = 60 + 340 * sensitivity
        — total control points retained (with dmin = 10 px de-duplication).
        控制点总数上限（配合 dmin = 10 px 去重）。
    """
    await _progress(send_progress, 0.0, "Detecting peaks / 正在自动寻峰")
    _check_cancel(cancel_event)

    sensitivity = _as_float(payload.get("sensitivity"), 0.5)
    if sensitivity is None:
        sensitivity = 0.5
    sensitivity = min(max(sensitivity, 0.0), 1.0)

    def _massif_pick(session: Dict[str, Any], beyond_mask: bool, cutoff: float,
                     keep: int, dmin: float) -> list:
        # Contiguous default: the SESSION mask (mask file + thresholds + dead
        # pixels) blocks extraction; the calib2-style "extract beyond masked
        # values" toggle disables it. Masked pixels are ALSO removed from the
        # candidate area — peaks_from_area admits any position inside the area,
        # so the area must exclude masked ones for them to be truly unpickable.
        # PERFORMANCE: the Massif comes from the session cache (labeled-massif
        # state is reused instead of being rebuilt per call).
        # 默认连续提取：会话掩膜（文件 + 阈值 + 死像素）阻断提取；勾选“越过掩码
        # 提取”后禁用。掩膜像素同时从候选区扣除；Massif 改用会话缓存（labeled
        # massif 状态复用，不再每次重建）。
        pick_mask = None if beyond_mask else _massif_mask(session, False)
        massif = _session_massif(session, beyond_mask)
        image = session["data"]
        area = image > cutoff
        if pick_mask is not None:
            area = area & ~pick_mask
        if not area.any():
            return []
        return massif.peaks_from_area(area, Imin=cutoff, keep=keep, dmin=dmin)

    data = session["data"]
    data_max = float(np.nanmax(data))
    if not math.isfinite(data_max) or data_max <= 0:
        return _err("Image has no usable signal / 图像无有效信号")
    cutoff = data_max * (0.5 * (1.0 - sensitivity) + 0.1 * sensitivity)
    keep = int(60 + 340 * sensitivity)
    dmin = 10.0
    beyond_mask = bool(payload.get("beyondMask"))

    await _progress(send_progress, 0.2, "Running massif peak picking / 正在运行 massif 寻峰")
    try:
        found = await _run_blocking(
            _massif_pick, session, beyond_mask, cutoff, keep, dmin,
        )
    except Exception as exc:  # noqa: BLE001 — surfaced to the frontend
        return _err(f"Peak detection failed: {exc}", f"寻峰失败：{exc}")
    _check_cancel(cancel_event)

    h, w = session["shape"]
    peaks: List[Dict[str, Any]] = []
    for pt in found:
        y = float(pt[0])
        x = float(pt[1])
        if not (0.0 <= y < h and 0.0 <= x < w):
            continue
        iy, ix = int(round(y)), int(round(x))
        iy = min(max(iy, 0), h - 1)
        ix = min(max(ix, 0), w - 1)
        peaks.append(
            {"y": iy, "x": ix, "intensity": float(data[iy, ix]), "ring": None},
        )

    session["peaks"] = peaks

    await _progress(send_progress, 1.0, f"Found {len(peaks)} peaks / 找到 {len(peaks)} 个峰")
    result: Dict[str, Any] = {"status": "ok", "peaks": peaks}
    if not peaks:
        result["message"] = (
            "No peaks found; try raising sensitivity or check the image. / "
            "未找到峰；可尝试提高灵敏度或检查图像。"
        )
    return result


def _guess_integrator(session: Dict[str, Any]):
    """AzimuthalIntegrator for the CURRENT geometry (refined if available,
    else the image-centre first guess). rows=y → poni1, cols=x → poni2.
    以当前几何（有精修结果则用之，否则图像中心初值）构建积分器。"""
    from pyFAI.integrator.azimuthal import AzimuthalIntegrator

    gr = session.get("gr")
    if gr is not None:
        return AzimuthalIntegrator(
            dist=gr.dist, poni1=gr.poni1, poni2=gr.poni2,
            rot1=gr.rot1, rot2=gr.rot2, rot3=gr.rot3,
            pixel1=session["pixel1"], pixel2=session["pixel2"],
            wavelength=session["wavelength"],
        )
    return AzimuthalIntegrator(
        dist=session["dist0"],
        poni1=0.5 * session["shape"][0] * session["pixel1"],
        poni2=0.5 * session["shape"][1] * session["pixel2"],
        pixel1=session["pixel1"], pixel2=session["pixel2"],
        wavelength=session["wavelength"],
    )


def _assign_rings_detailed(
    session: Dict[str, Any],
    ys: np.ndarray,
    xs: np.ndarray,
    kept_rings: Optional[np.ndarray] = None,
    honor_kept: bool = False,
) -> tuple:
    """Assign each peak to the nearest REACHABLE theoretical ring and self-check.

    Returns ``(rings, dtheta_deg, suspect)``:
      rings      — 0-based ring index per peak (``argmin`` of |Δ2θ|; user-kept
                   ring numbers win when ``honor_kept`` and valid);
      dtheta_deg — signed per-peak deviation from the assigned ring's 2θ
                   (degrees; positive = peak sits at larger angle);
      suspect    — per-peak self-check flag, True when the peak lies beyond the
                   midpoint between its assigned ring and the neighbouring ring
                   (i.e. closer to "between rings" than to its own ring).
                   Mirrors the sanity check behind calib2's ring table +
                   geometry residuals, surfaced per peak for the UI's
                   刷新环号/自检 button.

    Unreachable rings (``get_2th()`` → None because sin(θ)>1 at this
    wavelength) map to +inf so they can never be assigned.
    将每个峰匹配到最近的可到达理论环，并做逐峰自检。返回（环号、偏差角
    （度）、可疑标志）。不可达环（get_2th() 为 None）置为 +inf，绝不分配。
    """
    guess = _guess_integrator(session)

    tth_raw = session["calibrant"].get_2th()
    n_rings = len(tth_raw)
    tth_rings = np.array(
        [np.inf if v is None else float(v) for v in tth_raw],
        dtype=np.float64,
    )
    tth_peaks = np.asarray(guess.tth(ys, xs), dtype=np.float64)

    if not np.isfinite(tth_rings).any():
        # Wavelength reaches none of the calibrant's d-spacings — nothing to
        # assign against. Flag everything instead of crashing on all-inf argsort.
        # 波长下无任何可达环——无法分配；全峰标记可疑而非在 inf 上崩溃。
        n = len(tth_peaks)
        return np.zeros(n, dtype=int), np.zeros(n, dtype=np.float64), np.ones(n, dtype=bool)

    diff = np.abs(tth_rings[None, :] - tth_peaks[:, None])
    order = np.argsort(diff, axis=1)
    assigned = order[:, 0].astype(int).copy()
    if honor_kept and kept_rings is not None:
        kept = np.asarray(
            [
                int(r) if (r is not None and np.isfinite(r) and 0 <= int(r) < n_rings
                           and np.isfinite(tth_rings[int(r)])) else -1
                for r in kept_rings
            ],
            dtype=int,
        )
        use = kept >= 0
        assigned[use] = kept[use]

    deg = 180.0 / math.pi
    dtheta = (tth_peaks - tth_rings[assigned]) * deg
    # Ambiguity scale: distance from the assigned ring to the nearest OTHER
    # ring (excluding the assigned one — with a user-kept wrong ring, the
    # second-closest ring to the peak IS the assigned ring, which would zero
    # the gap and silence the check). / 二义性尺度：所分配环到最近“其它”环的
    # 距离（必须排除自身——用户保留错误环号时，峰的次近环恰为所分配环，
    # 不排除会把间距清零、令自检失明）。
    diff_other = diff.copy()
    rows = np.arange(diff_other.shape[0])
    diff_other[rows, assigned] = np.inf
    other = np.argmin(diff_other, axis=1)
    gap = np.abs(tth_rings[other] - tth_rings[assigned]) * deg
    suspect = np.abs(dtheta) > 0.5 * gap
    # No other reachable ring → no ambiguity to warn about.
    # 没有其它可达环 → 无二义性，不告警。
    suspect &= np.isfinite(gap) & (gap > 0.0)
    return assigned, dtheta, suspect


def _assign_rings(session: Dict[str, Any], ys: np.ndarray, xs: np.ndarray) -> np.ndarray:
    """Backward-compatible thin wrapper: ring indices only.
    兼容旧接口的薄封装：仅返回环号。"""
    rings, _dtheta, _suspect = _assign_rings_detailed(session, ys, xs)
    return rings


def _build_refinement(session: Dict[str, Any], ys: np.ndarray, xs: np.ndarray,
                      rings: np.ndarray) -> Any:
    """Instantiate GeometryRefinement from peaks + current guess geometry.
    依据峰列表与当前初值几何构建 GeometryRefinement。"""
    from pyFAI.geometryRefinement import GeometryRefinement

    data = np.column_stack([ys, xs, rings.astype(np.float64)])
    gr_prev = session.get("gr")
    kwargs: Dict[str, Any] = {
        "data": data,
        "calibrant": session["calibrant"],
        "dist": gr_prev.dist if gr_prev is not None else session["dist0"],
        "pixel1": session["pixel1"],
        "pixel2": session["pixel2"],
        "wavelength": session["wavelength"],
    }
    if gr_prev is not None:
        # Iterating on a refined geometry: reuse its full parameter set.
        # 在已精修几何上迭代：复用其完整参数。
        kwargs.update(
            poni1=gr_prev.poni1, poni2=gr_prev.poni2,
            rot1=gr_prev.rot1, rot2=gr_prev.rot2, rot3=gr_prev.rot3,
        )
    # else: poni1/poni2 omitted → constructor guess_poni() fits the
    # innermost ring (centroid / ellipse), exactly like pyFAI-calib2.
    # 否则省略 poni1/poni2 → 构造器 guess_poni() 用最内环质心/椭圆拟合，
    # 与 pyFAI-calib2 行为一致。
    return GeometryRefinement(**kwargs)


async def _action_update_peaks(
    session: Dict[str, Any], payload: dict, send_progress, cancel_event,
) -> dict:
    """Replace the peak list with the frontend's FULL edited list and assign rings.
    以前端回传的完整峰列表替换会话峰值并分配环号。

    Payload keys / 载荷键：
      sessionId (str, required)
      peaks     (list of {'y','x'(,'ring')}, required; an EMPTY list is a
                tolerated no-op clear — the fix for 完成环选报
                “peaks must be a non-empty list of {'y','x'}”)
      mode      ('assign' (default) | 'keep') — 'keep' honors each peak's own
                ring number (user-edited in the peak table, calib2 semantics)
                and only assigns the ones without one; 'assign' re-derives
                every ring number from the CURRENT geometry (the 刷新环号/自检
                refresh path). / 'keep' 尊重用户在峰表中编辑过的环号，仅对缺失
                者分配；'assign'（默认）全部按当前几何重新分配（自检刷新路径）。

    Response peaks carry ``ring`` plus the per-peak self-check fields
    ``dtheta_deg`` (signed deviation from the assigned ring, degrees) and
    ``suspect`` (peak beyond the midpoint toward a neighbouring ring).
    返回的每个峰除 ``ring`` 外还带 ``dtheta_deg`` 与 ``suspect`` 自检字段。
    """
    await _progress(send_progress, 0.0, "Assigning rings to peaks / 正在为峰分配环号")
    _check_cancel(cancel_event)

    raw_peaks = payload.get("peaks")
    if raw_peaks is None or not isinstance(raw_peaks, list):
        return _err("peaks must be a non-empty list of {'y','x'} / peaks 必须是非空的 {'y','x'} 列表")
    if not raw_peaks:
        # STEP 1 fix: an empty list means "clear", not an error. The old
        # hard error here was the toast the user saw right after 完成环选 when
        # the ring harvest had yielded nothing (frontend then pushed its
        # still-empty list). Clear the session peaks and succeed.
        # 空列表 = 清空而非报错。原硬报错正是“完成环选”后收峰为空时前端
        # 推送空列表所致的弹窗；此处清空会话峰并返回成功。
        session["peaks"] = []
        await _progress(send_progress, 1.0, "Peak list cleared / 峰列表已清空")
        return {
            "status": "ok",
            "peaks": [],
            "message": "Peak list cleared (no-op) / 峰列表已清空",
        }

    honor_kept = str(payload.get("mode", "assign")) == "keep"

    h, w = session["shape"]
    clean: List[tuple] = []
    for pt in raw_peaks:
        y = _as_float(pt.get("y") if isinstance(pt, dict) else None)
        x = _as_float(pt.get("x") if isinstance(pt, dict) else None)
        if y is None or x is None:
            continue
        if not (0.0 <= y < h and 0.0 <= x < w):
            continue
        ring = None
        if isinstance(pt, dict):
            ring_num = _as_float(pt.get("ring"))
            if ring_num is not None and float(ring_num).is_integer() and ring_num >= 0:
                ring = int(ring_num)
        elif isinstance(pt, (list, tuple)) and len(pt) > 2:
            ring_num = _as_float(pt[2])
            if ring_num is not None and float(ring_num).is_integer() and ring_num >= 0:
                ring = int(ring_num)
        clean.append((y, x, ring))
    if not clean:
        return _err("No valid peaks inside the image / 图像范围内没有有效峰")

    ys = np.array([p[0] for p in clean], dtype=np.float64)
    xs = np.array([p[1] for p in clean], dtype=np.float64)
    kept = np.array([p[2] for p in clean], dtype=object)

    try:
        rings, dtheta, suspect = await _run_blocking(
            _assign_rings_detailed, session, ys, xs, kept, honor_kept,
        )
        gr = await _run_blocking(_build_refinement, session, ys, xs, rings)
    except Exception as exc:  # noqa: BLE001 — surfaced to the frontend
        return _err(f"Peak assignment failed: {exc}", f"峰环分配失败：{exc}")
    _check_cancel(cancel_event)

    session["gr"] = gr
    data = session["data"]
    peaks_out: List[Dict[str, Any]] = []
    for (y, x, _user_ring), ring, dth, susp in zip(clean, rings, dtheta, suspect):
        iy, ix = int(round(y)), int(round(x))
        iy = min(max(iy, 0), h - 1)
        ix = min(max(ix, 0), w - 1)
        peaks_out.append(
            {
                "y": iy, "x": ix,
                "intensity": float(data[iy, ix]),
                "ring": int(ring),
                "dtheta_deg": float(dth) if np.isfinite(dth) else None,
                "suspect": bool(susp),
            },
        )
    session["peaks"] = peaks_out

    await _progress(send_progress, 1.0, "Peaks updated / 峰列表已更新")
    return {"status": "ok", "peaks": peaks_out}


def _run_refine(gr: Any, passes: int, fix: List[str]) -> None:
    """Synchronous refinement step (executed in the thread pool).
    同步精修（在线程池中执行）。

    Constraint handling / 约束处理（pyFAI 2026.3.0 实测）：
      * ``GeometryRefinement.refine3(maxiter, fix=[names])`` provides a clean
        per-parameter fix API — fixed names are held as constants inside the
        SLSQP optimiser. ``refine2`` is a thin wrapper over ``refine3`` whose
        only extra behaviour is re-defaulting ``fix`` to ``["wavelength"]``
        when handed an EMPTY list; therefore refine2 is called only with a
        non-empty fix list, and an empty list (everything free) goes straight
        to refine3 so a user-freed wavelength is genuinely refined.
        ``refine3(maxiter, fix)`` 提供干净的分参数固定 API（固定项作为常量进入
        SLSQP 优化器）；``refine2`` 只是对 refine3 的薄封装，唯一附加行为是在
        收到空 fix 列表时把 fix 重置为 ``["wavelength"]``。因此仅在 fix 非空时
        调用 refine2，fix 为空（全部自由）时直连 refine3，确保用户放开的波长
        真正参与精修。
      * ``refine1`` (unconstrained leastsq, 6 geometry params, wavelength
        inherently fixed) has NO fix argument, so it is used only when the
        requested fix set is a subset of {"wavelength"}; any geometry
        parameter fixed with passes=1 falls back to refine3's constrained
        solver (documented deviation — refine-then-restore is never used).
        ``refine1``（无约束最小二乘，仅 6 个几何参数，波长天然固定）不支持
        fix 参数，故仅当需要固定的参数是 {"wavelength"} 子集时使用；
        passes=1 且固定了几何参数时退回 refine3 的约束求解器（此处为偏差
        说明——绝不采用“先精修再回写”的做法）。
    """
    gr.set_tolerance(_REFINE_TOLERANCE_PCT)
    if passes <= 1:
        if set(fix) <= {"wavelength"}:
            gr.refine1()
        else:
            gr.refine3(fix=fix)
    elif passes == 2:
        if fix:
            gr.refine2(fix=fix)
        else:
            gr.refine3(fix=fix)
    else:
        gr.refine3(fix=fix)


def _refine_residuals(gr: Any) -> List[Dict[str, Any]]:
    """Per-ring measured-vs-theoretical 2θ residuals (degrees).
    每环实测 2θ 与理论 2θ 之差（度）。"""
    data = np.asarray(gr.data, dtype=np.float64)
    rings = data[:, 2].astype(int)
    tth_rings = np.asarray(gr.calibrant.get_2th(), dtype=np.float64)
    deg = 180.0 / math.pi
    out: List[Dict[str, Any]] = []
    for ring in sorted(set(rings.tolist())):
        sel = rings == ring
        if not sel.any() or ring >= len(tth_rings):
            continue
        tth_meas = float(np.mean(gr.tth(data[sel, 0], data[sel, 1]))) * deg
        tth_theo = float(tth_rings[ring]) * deg
        out.append(
            {
                "ring": int(ring),
                "tth_meas_deg": tth_meas,
                "tth_theo_deg": tth_theo,
                "delta_deg": tth_meas - tth_theo,
            },
        )
    return out


async def _action_refine(
    session: Dict[str, Any], payload: dict, send_progress, cancel_event,
) -> dict:
    """Constrain-refine the session geometry. / 约束精修会话几何。

    Payload keys / 载荷键：
      sessionId (str, required)
      free      (dict, optional) {dist,poni1,poni2,rot1,rot2,rot3,wavelength}→bool
                defaults: dist/poni1/poni2 free; rot1–3 and wavelength fixed
                / 默认 dist/poni1/poni2 自由，rot1–3 与波长固定
      passes    (int, optional) 1|2|3 (default 2) → refine1 / refine2 / refine3
    """
    await _progress(send_progress, 0.0, "Refining geometry / 正在精修几何")
    _check_cancel(cancel_event)

    gr = session.get("gr")
    if gr is None:
        return _err(
            "No peaks assigned yet: run update_peaks first / 尚未分配峰：请先执行 update_peaks",
        )

    free_raw = payload.get("free") or {}
    if not isinstance(free_raw, dict):
        return _err("free must be a dict of parameter→bool / free 必须是 参数→bool 的字典")
    free = dict(_DEFAULT_FREE)
    for name in _PARAM_ORDER:
        if name in free_raw:
            free[name] = bool(free_raw[name])
    fix = [name for name in _PARAM_ORDER if not free[name]]

    passes = int(_as_float(payload.get("passes"), 2.0) or 2.0)
    passes = min(max(passes, 1), 3)

    await _progress(send_progress, 0.15, f"Refining (passes={passes}) / 精修中（passes={passes}）")
    try:
        await _run_blocking(_run_refine, gr, passes, fix)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 — surfaced to the frontend
        return _err(f"Refinement failed: {exc}", f"精修失败：{exc}")
    _check_cancel(cancel_event)

    chi2: Optional[float] = None
    try:
        chi2 = float(gr.chi2())
    except Exception:  # noqa: BLE001 — chi2 is informational
        chi2 = None

    residuals = await _run_blocking(_refine_residuals, gr)
    geometry = _geometry_summary(gr, session["pixel1"], session["pixel2"])

    await _progress(send_progress, 1.0, "Refinement complete / 精修完成")
    return {"status": "ok", "geometry": geometry, "chi2": chi2, "residuals": residuals}


def _extract_ring_overlay(session: Dict[str, Any], gr: Any, calibrant: Any,
                          shape: tuple) -> List[Dict[str, Any]]:
    """Synchronous ring-contour extraction (executed in the thread pool).
    同步环等值线提取（在线程池中执行）。

    PERFORMANCE: the full-frame 2θ map (``gr.array_from_unit``) is cached on
    the session keyed by the geometry parameter tuple — unchanged geometry
    (e.g. a re-draw after a failed refine, or repeated overlays) reuses the
    map instead of recomputing it. setup resets the cache.
    性能：整帧 2θ 图按几何参数元组缓存在会话上；几何不变时复用，不再重算。
    """
    from pyFAI.units import TTH_DEG
    from silx.image.marchingsquares import find_contours

    h, w = int(shape[0]), int(shape[1])
    cache_key = (
        float(gr.dist), float(gr.poni1), float(gr.poni2),
        float(gr.rot1), float(gr.rot2), float(gr.rot3),
        float(gr.wavelength), h, w,
    )
    cache = session.get("tth_cache")
    tth_map: Optional[np.ndarray] = None
    if isinstance(cache, dict) and cache.get("key") == cache_key:
        tth_map = cache.get("map")
        logger.info("calibration tth cache: HIT (session %s)", session.get("id"))
    if tth_map is None:
        tth_map = np.asarray(
            gr.array_from_unit(shape=shape, typ="center", unit=TTH_DEG, scale=True),
            dtype=np.float64,
        )
        session["tth_cache"] = {"key": cache_key, "map": tth_map}
        logger.info("calibration tth cache: MISS → built 2θ map (session %s)", session.get("id"))
    map_min = float(tth_map.min())
    map_max = float(tth_map.max())

    tth_rings = np.asarray(calibrant.get_2th(), dtype=np.float64) * 180.0 / math.pi
    d_spacings = calibrant.dspacing

    rings_out: List[Dict[str, Any]] = []
    for ring_idx in range(len(tth_rings)):
        if len(rings_out) >= _MAX_OVERLAY_RINGS:
            break
        level = float(tth_rings[ring_idx])
        if not (map_min <= level <= map_max):
            continue
        polygons = find_contours(tth_map, level=level)
        if not polygons:
            continue
        pts = np.concatenate([np.asarray(p, dtype=np.float64) for p in polygons], axis=0)
        # Downsample to <= _MAX_RING_POINTS per ring, then clip to the frame.
        # 每环降采样至 ≤600 点，并裁剪到图像范围内。
        if len(pts) > _MAX_RING_POINTS:
            idx = np.unique(np.linspace(0, len(pts) - 1, _MAX_RING_POINTS).round().astype(int))
            pts = pts[idx]
        pts = pts[
            (pts[:, 0] >= 0) & (pts[:, 0] <= h - 1)
            & (pts[:, 1] >= 0) & (pts[:, 1] <= w - 1)
        ]
        if not len(pts):
            continue
        d_val = d_spacings[ring_idx] if ring_idx < len(d_spacings) else None
        rings_out.append(
            {
                "ring": int(ring_idx),
                "d_spacing_A": float(d_val) if d_val is not None else None,
                "points": [[float(r), float(c)] for r, c in pts],
            },
        )
    return rings_out


async def _action_ring_overlay(
    session: Dict[str, Any], payload: dict, send_progress, cancel_event,
) -> dict:
    """Compute iso-contour polylines of every visible theoretical ring.
    计算所有可见理论环的等值线折线（ring_overlay）。

    Payload keys / 载荷键：sessionId (str, required)
    """
    await _progress(send_progress, 0.0, "Building ring overlay / 正在生成理论环叠加")
    _check_cancel(cancel_event)

    gr = session.get("gr")
    if gr is None:
        return _err(
            "No geometry available yet: run update_peaks (and refine) first / "
            "尚无几何信息：请先执行 update_peaks（与 refine）",
        )

    try:
        rings_out = await _run_blocking(
            _extract_ring_overlay, session, gr, session["calibrant"], session["shape"],
        )
    except Exception as exc:  # noqa: BLE001 — surfaced to the frontend
        return _err(f"Ring overlay failed: {exc}", f"理论环叠加失败：{exc}")
    _check_cancel(cancel_event)

    await _progress(send_progress, 1.0, f"{len(rings_out)} rings / {len(rings_out)} 个环")
    return {"status": "ok", "rings": rings_out}


#: Payload caps for integrate_preview's 2-D cake (JSON transport budget).
#: integrate_preview 2D cake 的尺寸上限（JSON 传输预算）。
_INTEGRATE_2D_MAX_RAD: int = 400
_INTEGRATE_2D_MAX_AZIM: int = 360


def _finite_round3(values: np.ndarray) -> list:
    """Round to 3 decimals; non-finite → None (strict-JSON safe).
    保留 3 位小数；非有限值转 None（保证严格 JSON 可解析）。"""
    out = []
    for v in np.round(np.asarray(values, dtype=np.float64).ravel(), 3):
        out.append(float(v) if np.isfinite(v) else None)
    return out


def _integrate_preview_sync(session: Dict[str, Any], gr: Any, npt1d: int,
                            npt_rad: int, npt_azim: int, unit: str) -> dict:
    """Synchronous calibrant integration (executed in the thread pool).
    同步标定图积分（在线程池中执行）。"""
    from pyFAI.integrator.azimuthal import AzimuthalIntegrator

    ai = AzimuthalIntegrator(
        dist=gr.dist, poni1=gr.poni1, poni2=gr.poni2,
        rot1=gr.rot1, rot2=gr.rot2, rot3=gr.rot3,
        pixel1=session["pixel1"], pixel2=session["pixel2"],
        wavelength=session["wavelength"],
    )
    data = session["data"]

    res1d = ai.integrate1d(data, npt1d, unit=unit, method="csr")
    res2d = ai.integrate2d(data, npt_rad, npt_azim, unit=unit, method="csr")

    # 2-D cake: pyFAI returns intensity shaped (nAzim, nRad) — rows are
    # azimuth bins, columns radial bins. Downsample each axis by plain
    # striding to the transport caps, then flatten ROW-MAJOR with the
    # rounded/None-sanitized values.
    # 2D cake：pyFAI 的 intensity 形状为 (nAzim, nRad)——行为方位角、列为径向。
    # 按步长降采样到传输上限后行优先展平（3 位小数、非有限值转 None）。
    intensity = np.asarray(res2d.intensity, dtype=np.float64)
    radial = np.asarray(res2d.radial, dtype=np.float64)
    azimuthal = np.asarray(res2d.azimuthal, dtype=np.float64)
    stride_rad = max(1, math.ceil(intensity.shape[1] / _INTEGRATE_2D_MAX_RAD))
    stride_azim = max(1, math.ceil(intensity.shape[0] / _INTEGRATE_2D_MAX_AZIM))
    intensity = intensity[::stride_azim, ::stride_rad]
    radial = radial[::stride_rad]
    azimuthal = azimuthal[::stride_azim]

    return {
        "1d": {
            "x": [float(v) if np.isfinite(v) else None for v in res1d.radial],
            "y": _finite_round3(res1d.intensity),
        },
        "2d": {
            "intensity": _finite_round3(intensity),
            "nRad": int(intensity.shape[1]),
            "nAzim": int(intensity.shape[0]),
            "xRange": [float(radial[0]), float(radial[-1])],
            "yRange": [float(azimuthal[0]), float(azimuthal[-1])],
        },
        "unit": unit,
    }


async def _action_integrate_preview(
    session: Dict[str, Any], payload: dict, send_progress, cancel_event,
) -> dict:
    """Quick 1-D + 2-D integration preview of the CALIBRANT frame under the
    CURRENT refined geometry (calib2 Integration-task parity).
    以当前精修几何对标定图做 1D/2D 积分预览（对标 calib2 的 Integration 任务）。

    Payload keys / 载荷键：
      sessionId   (str, required)
      npt1d       (int, optional) 1-D bins, default 1024 / 1D 点数，默认 1024
      npt2dRad    (int, optional) 2-D radial bins, default 800 (downsampled
                  to ≤400 before transport) / 2D 径向点数，默认 800（传输前
                  降采样到 ≤400）
      npt2dAzim   (int, optional) 2-D azimuth bins, default 360 / 2D 方位角
                  点数，默认 360
      unit        (str, optional) pyFAI unit, default "q_nm^-1" / pyFAI 单位

    The AzimuthalIntegrator is built exactly like ring_overlay's (refined
    GeometryRefinement parameters); no picking mask is applied — this is a
    raw geometry-QC view, like calib2's integration preview.
    积分器构造与 ring_overlay 完全一致（取精修后的几何参数）；不套拾取掩膜——
    这是几何质检视图，与 calib2 的积分预览一致。
    """
    await _progress(send_progress, 0.0, "Integrating calibrant preview / 正在积分标定预览")
    _check_cancel(cancel_event)

    gr = session.get("gr")
    if gr is None:
        return _err(
            "No geometry available yet: run update_peaks (and refine) first / "
            "尚无几何信息：请先执行 update_peaks（与 refine）",
        )

    npt1d = int(_as_float(payload.get("npt1d"), 1024.0) or 1024.0)
    npt_rad = int(_as_float(payload.get("npt2dRad"), 800.0) or 800.0)
    npt_azim = int(_as_float(payload.get("npt2dAzim"), 360.0) or 360.0)
    unit = str(payload.get("unit") or "q_nm^-1")
    npt1d = min(max(npt1d, 16), 8192)
    npt_rad = min(max(npt_rad, 16), 4096)
    npt_azim = min(max(npt_azim, 16), 720)

    await _progress(send_progress, 0.2, "Running 1D + 2D integration / 正在执行 1D + 2D 积分")
    try:
        result = await _run_blocking(
            _integrate_preview_sync, session, gr, npt1d, npt_rad, npt_azim, unit,
        )
    except Exception as exc:  # noqa: BLE001 — surfaced to the frontend
        return _err(f"Integration preview failed: {exc}", f"积分预览失败：{exc}")
    _check_cancel(cancel_event)

    await _progress(send_progress, 1.0, "Integration preview ready / 积分预览就绪")
    return {"status": "ok", **result}


async def _action_export_poni(
    session: Dict[str, Any], payload: dict, send_progress, cancel_event,
) -> dict:
    """Persist the refined geometry as a standard .poni file.
    将精修几何保存为标准 .poni 文件（export_poni）。

    Payload keys / 载荷键：
      sessionId (str, required)
      savePath  (str, optional) explicit destination / 显式保存路径
      autoSave  (bool, optional) with no savePath, write to the OS temp dir
                (unique name) and return the path — the backend half of the
                wizard's 去积分 auto-import (frontend then routes to
                /workspace/integrate-1d?poni=<path>) / 无 savePath 时写入系统
                临时目录（唯一文件名）并返回路径——去积分自动导入的后端半边。
    """
    await _progress(send_progress, 0.0, "Exporting .poni / 正在导出 .poni")
    _check_cancel(cancel_event)

    gr = session.get("gr")
    if gr is None:
        return _err("No refined geometry to export / 没有可导出的精修几何")

    save_path = payload.get("savePath")
    if not save_path and bool(payload.get("autoSave")):
        import tempfile

        save_path = str(
            Path(tempfile.gettempdir())
            / f"xfais-calib-{time.strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}.poni"
        )
    if not save_path:
        return _err("savePath is required / 必须提供 savePath")
    out = Path(str(save_path))
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _err(f"Cannot create output directory: {exc}", f"无法创建输出目录：{exc}")

    try:
        await _run_blocking(gr.save, str(out))
    except Exception as exc:  # noqa: BLE001 — surfaced to the frontend
        return _err(f"PONI export failed: {exc}", f"PONI 导出失败：{exc}")
    _check_cancel(cancel_event)

    await _progress(send_progress, 1.0, f"Saved {out} / 已保存 {out}")
    return {
        "status": "ok",
        "savePath": str(out),
        "summary": _geometry_summary(gr, session["pixel1"], session["pixel2"]),
        "citation": dict(_CITATION),
    }


async def _action_seed_from_poni(payload: dict, send_progress) -> dict:
    """Parse an existing .poni back into setup-form seed parameters.
    解析已有 .poni，回填 setup 表单的初始参数（seed_from_poni）。

    Payload keys / 载荷键：filePath (str, required)
    """
    await _progress(send_progress, 0.0, "Parsing .poni / 正在解析 .poni")

    from .poni_importer import parse_poni_file

    file_path = payload.get("filePath")
    if not file_path or not Path(str(file_path)).is_file():
        return _err(f"PONI file not found: {file_path}", f"未找到 PONI 文件：{file_path}")

    parsed = await _run_blocking(parse_poni_file, str(file_path))
    if not parsed:
        return _err(f"Failed to parse PONI file: {file_path}", f"PONI 解析失败：{file_path}")

    distance_m = _as_float(parsed.get("distance"))
    wavelength_m = _as_float(parsed.get("wavelength"))
    poni1_m = _as_float(parsed.get("poni1"))
    poni2_m = _as_float(parsed.get("poni2"))
    pixel_m = _as_float(parsed.get("pixel_size"))
    if not pixel_m or pixel_m <= 0:
        pixel_m = _as_float(parsed.get("pixel2_size"))

    deg = 180.0 / math.pi

    def _px(poni_m: Optional[float]) -> Optional[float]:
        """metres → pixels using the parsed pixel size. / 米 → 像素。"""
        if poni_m is None:
            return None
        if not pixel_m or pixel_m <= 0:
            return None
        return poni_m / pixel_m

    seed = {
        "dist_mm": distance_m * 1e3 if distance_m is not None else None,
        "wavelength_A": wavelength_m * 1e10 if wavelength_m is not None else None,
        "pixel_size_um": pixel_m * 1e6 if (pixel_m and pixel_m > 0) else None,
        # poni1 is along rows (y), poni2 along columns (x); the beam-centre-in-
        # pixels conversion is done here from metres / pixel-size because
        # parse_poni_file keeps poni1/poni2 in metres.
        # poni1 沿行（y），poni2 沿列（x）；parse_poni_file 返回的 poni1/poni2
        # 单位是米，故像素换算在此完成。
        "center_x_px": _px(poni2_m),
        "center_y_px": _px(poni1_m),
        "rot1_deg": _as_float(parsed.get("rot1"), 0.0) * deg,
        "rot2_deg": _as_float(parsed.get("rot2"), 0.0) * deg,
        "rot3_deg": _as_float(parsed.get("rot3"), 0.0) * deg,
    }
    await _progress(send_progress, 1.0, "Seed ready / 初始参数就绪")
    return {"status": "ok", "seed": seed}


# ---------------------------------------------------------------------------
# Entry point / 唯一入口
# ---------------------------------------------------------------------------

async def _action_list_detectors(payload: dict) -> dict:
    """Enumerate pyFAI's registered detector names for the setup dropdown.
    枚举 pyFAI 注册的探测器名，供设置表单下拉选择。"""
    def _list() -> list:
        from .poni_importer import _get_pyfai_detector_registry
        return sorted(_get_pyfai_detector_registry())

    try:
        names = await asyncio.get_event_loop().run_in_executor(None, _list)
        return {"status": "ok", "detectors": names}
    except Exception as exc:  # noqa: BLE001
        return _err(f"Failed to list detectors: {exc}", f"探测器列表获取失败：{exc}")


async def _action_probe_image(payload: dict) -> dict:
    """Peek at an image: shape + auto-detected pyFAI detector (by max_shape).
    预检图像：尺寸 + 按形状自动匹配的 pyFAI 探测器。

    Used by the setup form right after the user picks a file, so the detector
    dropdown can be pre-selected automatically (user may still override).
    供用户选定图像后立即预填探测器下拉（用户仍可手动改选）。
    """
    file_path = payload.get("filePath")
    if not file_path:
        return _err("filePath is required", "缺少 filePath")
    frame = int(_as_float(payload.get("frame"), 0.0) or 0.0)

    def _probe() -> dict:
        from .image_loader import ImageLoader as _Loader
        data, _dead, _meta = _Loader.load(str(file_path), None, None, frame)
        if data is None:
            raise RuntimeError("no data")
        image = _sweep_2d(data)
        shape = (int(image.shape[0]), int(image.shape[1]))
        from .poni_importer import match_detector_by_shape
        matched = match_detector_by_shape(shape)
        return {
            "shape": list(shape),
            "detector": matched["name"] if matched else None,
            "pixelSizeUm": (matched["pixel1_m"] * 1e6) if matched and matched.get("pixel1_m") else None,
        }

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _probe)
        return {"status": "ok", "filePath": str(file_path), **result}
    except Exception as exc:  # noqa: BLE001
        return _err(f"Failed to probe image: {exc}", f"图像预检失败：{exc}")


async def _action_pick_peak(payload: dict, session: dict) -> dict:
    """Click picking with massif snapping (calib2 'pick' tool).
    点击拾取，massif 吸附并收取所点峰群（calib2 的 pick 工具）。

    A single click returns ALL peaks of the clicked massif REGION (the seed
    maximum first, then its neighbors) — the same behaviour as pyFAI-calib2,
    where one pick yields the whole resolved group, not a single pixel.
    ``Massif.find_peaks`` is called with ``nmax=_PICK_PEAK_NMAX`` instead of 1
    so the region's neighboring maxima are included.
    单次点击返回所点峰群 REGION 内的全部峰（先是种子极大值，再是邻近峰）——
    与 pyFAI-calib2 一致：一次拾取得到整组已分辨的峰，而非单个像素。
    find_peaks 以 nmax=_PICK_PEAK_NMAX（而非 1）调用，纳入区域内邻近极大。

    The frontend merges every returned point into its peak list and then calls
    ``update_peaks`` for ring assignment, exactly like calib2's peak table.
    The backward-compatible single-peak key ``peak`` equals ``peaks[0]``.
    前端把全部返回点并入峰列表后再调 update_peaks 做环号分配（与 calib2 一致）。
    兼容旧前端的单峰键 ``peak`` 恒等于 ``peaks[0]``。
    """
    y = _as_float(payload.get("y"))
    x = _as_float(payload.get("x"))
    if y is None or x is None:
        return _err("y/x required", "缺少 y/x")

    data = session["data"]
    h, w = session["shape"]
    iy = min(max(int(round(y)), 0), h - 1)
    ix = min(max(int(round(x)), 0), w - 1)

    def _snap() -> list:
        # beyondMask → calib2 "Ring" tool ("Extract peaks, beyond masked
        # values"): dead pixels stop blocking the snap. Default keeps the
        # contiguous ("Arc") behaviour with the SESSION mask (file + thresholds
        # + dead pixels). PERFORMANCE: the Massif comes from the session cache
        # so the labeled massif is computed once per image/mask, not per click.
        # beyondMask 对应 calib2 Ring 工具（越过掩码值提取）；默认保持 Arc
        # （连续）行为并启用会话掩膜；Massif 走会话缓存，labeled massif 每图
        # 每掩膜只算一次。
        massif = _session_massif(session, bool(payload.get("beyondMask")))
        # find_peaks expects an INT (y, x) tuple — float tuples break its
        # internal numpy indexing. / find_peaks 需要 int (y,x) 元组——浮点
        # 元组会破坏其内部 numpy 索引。
        found = massif.find_peaks((iy, ix), nmax=_PICK_PEAK_NMAX)
        out: List[Dict[str, Any]] = []
        for pt in found:
            fy, fx = float(pt[0]), float(pt[1])
            if not (0.0 <= fy < h and 0.0 <= fx < w):
                continue
            py_, px_ = int(round(fy)), int(round(fx))
            py_ = min(max(py_, 0), h - 1)
            px_ = min(max(px_, 0), w - 1)
            if any(p["y"] == py_ and p["x"] == px_ for p in out):
                continue
            out.append(
                {"y": py_, "x": px_, "intensity": float(data[py_, px_])},
            )
        if not out:
            # No massif group at the click — fall back to the raw click point.
            # 点击处无峰群 — 回退为原始点击坐标。
            out.append({"y": iy, "x": ix, "intensity": float(data[iy, ix])})
        return out

    try:
        peaks = await _run_blocking(_snap)
        return {"status": "ok", "peaks": peaks, "peak": peaks[0]}
    except Exception as exc:  # noqa: BLE001
        return _err(f"Peak pick failed: {exc}", f"单峰拾取失败：{exc}")


def _guide_arc(pts: List[tuple], cy: float, cx: float) -> Optional[tuple]:
    """Angular span covered by the guide points around the fitted centre.

    Returns ``(a0, a1)`` in radians (``a1 - a0 ∈ (0, 2π)``, angles measured
    like ``atan2(y - cy, x - cx)``), grown by a small margin, or ``None`` when
    the points encircle the centre (largest angular gap ≤ π) — then the whole
    ring should be harvested. This is the backend of the "extract CONTIGUOUS
    peaks" (calib2 Arc tool) variant: only the arc the user traced is
    harvested, instead of the full circle.
    计算引导点绕拟合圆心的角度覆盖范围（弧度，a1-a0 ∈ (0,2π)，含少量边距）；
    当点环绕圆心（最大角间隙 ≤ π）时返回 None——应收整环。这是“连续提取”
    （calib2 Arc 工具）语义的后端实现：只收用户画过的那段弧，而非整圆。
    """
    angles = sorted(math.atan2(p[0] - cy, p[1] - cx) for p in pts)
    n = len(angles)
    gaps = [(angles[(i + 1) % n] - angles[i]) % (2.0 * math.pi) for i in range(n)]
    biggest = max(range(n), key=lambda i: gaps[i])
    gap = gaps[biggest]
    if gap <= math.pi:
        return None
    # The contiguous arc starts right after the biggest gap and ends on its
    # other side; grow it by ≤ min(gap/4, 30°) so the harvest reaches a little
    # beyond the traced guides (the massif region would, in calib2).
    # 连续弧从最大间隙之后开始、在其另一侧结束；外扩 ≤ min(gap/4, 30°)。
    grow = min(0.25 * gap, math.radians(30.0))
    a0 = angles[(biggest + 1) % n] - grow
    span = min((2.0 * math.pi - gap) + 2.0 * grow, 2.0 * math.pi)
    a0 = math.remainder(a0, 2.0 * math.pi)
    return a0, a0 + span


async def _action_ring_pick(payload: dict, session: dict) -> dict:
    """Ring picking (calib2 ring/arc tools): user clicks ≥3 points on one ring.

    Least-squares circle fit through the points, then a ring-band mask
    ``|r - R| < tolPx`` feeds ``Massif.peaks_from_area`` — the same mechanism
    calib2 uses to harvest all peaks along a drawn ring/arc.
    环选拾取（calib2 的 ring/arc 工具）：用户在同一环上点 ≥3 个点。对点做最小
    二乘圆拟合，构造 |r-R|<tolPx 环带遮罩送入 Massif.peaks_from_area——与
    calib2 沿所画环/弧批量收峰的机制一致。

    Ring-by-ring workflow (REQ 2): ``assignRing`` (int, 0-based pyFAI ring
    index; null = current behaviour) stamps every harvested peak with that ring
    number directly instead of leaving it for theoretical nearest-ring
    assignment — the backend of the wizard's 当前环号 spinner.
    逐环工作流：``assignRing``（0 起环号；null = 原行为）把收到的峰直接打上该
    环号，而非留给理论最近环分配——向导“当前环号”数字框的后端。

    Extraction variants (STEP 0 study of PeakPickingTask.py:1243-1265):
      * ``extractMode="contiguous"`` (default) — calib2 "Arc" tool,
        tooltip "Extract contiguous peaks": harvest ONLY the contiguous arc
        spanned by the guide points (``_guide_arc``), the SESSION mask
        (setup mask file + thresholds + dead pixels) blocks extraction.
        只收引导点连续覆盖的弧段（连续提取，Arc 工具），会话掩膜阻断提取。
      * ``extractMode="beyond_mask"`` (or legacy ``beyondMask: true``) —
        calib2 "Ring" tool, tooltip "Extract peaks, beyond masked values":
        harvest the FULL 360° ring band and disable the massif mask so masked
        positions never block extraction. 收整环且禁用掩码（越过掩码值提取，
        Ring 工具）。
    Threshold is calib2's adaptive rule (RingExtractor._extract): band
    mean+std, relaxed to band mean when fewer than ``_RING_PICK_MIN_PIXELS``
    candidates survive — replacing the old global ``0.2·max`` cutoff that
    silently starved faint rings (harvest zero → the STEP 1 empty-push bug).
    阈值采用 calib2 的自适应规则（环带 mean+std，候选不足时放宽到 mean），
    取代原先一刀切的全局 0.2·max 截断（弱环收空 → 触发 STEP 1 空推送缺陷）。
    """
    raw_pts = payload.get("points") or []
    pts = []
    for p in raw_pts:
        py_, px_ = _as_float(p.get("y") if isinstance(p, dict) else p[0]), _as_float(
            p.get("x") if isinstance(p, dict) else p[1]
        )
        if py_ is not None and px_ is not None:
            pts.append((py_, px_))
    if len(pts) < 3:
        return _err("Ring picking needs at least 3 points on the ring", "环选需要环上至少 3 个点")
    tol = _as_float(payload.get("tolPx"), 15.0) or 15.0
    keep = int(_as_float(payload.get("keep"), float(_RING_PICK_KEEP)) or _RING_PICK_KEEP)
    mode = str(payload.get("extractMode") or "")
    if not mode:
        mode = "beyond_mask" if payload.get("beyondMask") else "contiguous"
    beyond = mode == "beyond_mask"

    # REQ 2: optional explicit ring stamp on the harvest. / 收峰直接打上的环号。
    assign_ring: Optional[int] = None
    raw_ring = _as_float(payload.get("assignRing"))
    if raw_ring is not None and float(raw_ring).is_integer() and raw_ring >= 0:
        assign_ring = int(raw_ring)

    data = session["data"]
    h, w = session["shape"]

    def _harvest():
        ys = np.array([p[0] for p in pts], dtype=np.float64)
        xs = np.array([p[1] for p in pts], dtype=np.float64)
        # Algebraic circle fit (Kåsa): minimize a·x²+y² + b·x + c·y + d.
        # 代数圆拟合（Kåsa）。
        A = np.column_stack([xs, ys, np.ones_like(xs)])
        bb = xs ** 2 + ys ** 2
        sol, *_ = np.linalg.lstsq(A, bb, rcond=None)
        cx, cy = sol[0] / 2.0, sol[1] / 2.0
        radius = math.sqrt(max(sol[2] + cx * cx + cy * cy, 0.0))
        yy, xx = np.ogrid[0:h, 0:w]
        band = np.abs(np.hypot(yy - cy, xx - cx) - radius) <= tol

        # Session mask (REQ 1): masked pixels never contribute candidates, are
        # excluded from the band statistics, and (unless beyond_mask) are fed
        # to Massif so they cannot be harvested either.
        # 会话掩膜：屏蔽像素既不进候选、也不进环带统计；非越过掩码模式下
        # 一并喂给 Massif，确保屏蔽处绝不被收峰。
        pick_mask = None if beyond else _massif_mask(session, False)
        valid_band = band if pick_mask is None else (band & ~pick_mask)

        # calib2-style adaptive cutoff from the band's own statistics.
        # 基于环带自身统计的 calib2 式自适应阈值。
        sub = data[valid_band]
        mean = float(np.nanmean(sub))
        std = float(np.nanstd(sub))
        upper = mean + std
        area = valid_band & (data > upper)
        if int(area.sum()) < _RING_PICK_MIN_PIXELS:
            upper = mean
            area = valid_band & (data > upper)

        arc = _guide_arc(pts, cy, cx)
        if not beyond and arc is not None:
            a0, a1 = arc
            ang = np.arctan2(yy - cy, xx - cx)
            in_arc = np.mod(ang - a0, 2.0 * math.pi) <= (a1 - a0)
            area = area & in_arc
            arc_out = {"a0": a0, "a1": a1}
        else:
            arc_out = None

        if not area.any():
            return [], radius, cy, cx, arc_out, upper
        # PERFORMANCE: session-cached Massif — the labeled massif behind
        # peaks_from_area is built once per image/mask variant and reused by
        # every subsequent 完成本环 (the dominant cost on large frames).
        # 会话缓存 Massif：peaks_from_area 背后的 labeled massif 每图每掩膜
        # 只构建一次，后续每次完成本环直接复用（大图的主要耗时来源）。
        massif = _session_massif(session, beyond)
        found = massif.peaks_from_area(area, Imin=upper, keep=keep, dmin=8.0)
        out = []
        for pt in found:
            fy, fx = float(pt[0]), float(pt[1])
            if 0.0 <= fy < h and 0.0 <= fx < w:
                iy2, ix2 = int(round(fy)), int(round(fx))
                peak = {"y": iy2, "x": ix2, "intensity": float(data[iy2, ix2])}
                if assign_ring is not None:
                    peak["ring"] = assign_ring
                out.append(peak)
        return out, radius, cy, cx, arc_out, upper

    try:
        peaks, radius, cy, cx, arc, upper = await _run_blocking(_harvest)
        result: Dict[str, Any] = {
            "status": "ok",
            "peaks": peaks,
            "radiusPx": radius,
            "mode": mode,
            "assignRing": assign_ring,
        }
        # Region description so the frontend can apply its duplicate-handling
        # options ("remove a set of already identified peaks") on the SAME
        # band/arc that was harvested. / 返回收峰区域描述，供前端在同一环带/
        # 弧段上执行“移除已有点”等重复处理选项。
        result["region"] = {
            "cy": float(cy), "cx": float(cx),
            "radiusPx": float(radius), "tolPx": float(tol), "arc": arc,
        }
        result["cutoff"] = float(upper) if math.isfinite(upper) else None
        if not peaks:
            result["message"] = (
                "No peaks found in the ring band; check the guide points or "
                "raise the tolerance. / 环带内未找到峰；请检查引导点或提高容差。"
            )
        return result
    except Exception as exc:  # noqa: BLE001
        return _err(f"Ring picking failed: {exc}", f"环选拾取失败：{exc}")


async def handle_calibration(payload: dict, send_progress, cancel_event) -> dict:
    """Single entry point of the calibration service.

    标定服务的唯一入口。

    Parameters
    ----------
    payload : dict
        Must contain ``action`` plus the action-specific keys documented on
        each handler above. / 必含 ``action`` 及各处理函数说明的载荷键。
    send_progress : async (fraction: float, message: str) -> None
        Coarse progress reporter. / 粗粒度进度回调。
    cancel_event : asyncio.Event
        Checked before/after heavy steps; raising asyncio.CancelledError.
        在重计算前后检查；置位则抛出 asyncio.CancelledError。

    Returns
    -------
    dict
        ``{'status': 'ok', ...}`` on success, ``{'status': 'error',
        'message': str}`` on failure (bilingual message). / 成功返回
        ``{'status':'ok', ...}``，失败返回 ``{'status':'error','message':...}``（双语）。
    """
    action = payload.get("action")

    if action == "list_calibrants":
        return await _action_list_calibrants(payload)

    if action == "list_detectors":
        return await _action_list_detectors(payload)

    if action == "probe_image":
        return await _action_probe_image(payload)

    if action == "seed_from_poni":
        return await _action_seed_from_poni(payload, send_progress)

    # Every remaining action needs a session / 其余 action 均需要会话
    session = _get_session(payload.get("sessionId"))
    if action not in {
        "setup", "detect_peaks", "update_peaks", "refine",
        "ring_overlay", "export_poni", "pick_peak", "ring_pick",
        "integrate_preview",
    }:
        return _err(f"Unknown action: {action!r}", f"未知操作：{action!r}")
    if session is None and action != "setup":
        return _err(
            f"sessionId not found or expired: {payload.get('sessionId')!r}",
            f"会话不存在或已过期：{payload.get('sessionId')!r}",
        )

    if action == "setup":
        return await _action_setup(payload, send_progress, cancel_event)
    if action == "detect_peaks":
        return await _action_detect_peaks(session, payload, send_progress, cancel_event)
    if action == "pick_peak":
        return await _action_pick_peak(payload, session)
    if action == "ring_pick":
        return await _action_ring_pick(payload, session)
    if action == "update_peaks":
        return await _action_update_peaks(session, payload, send_progress, cancel_event)
    if action == "refine":
        return await _action_refine(session, payload, send_progress, cancel_event)
    if action == "ring_overlay":
        return await _action_ring_overlay(session, payload, send_progress, cancel_event)
    if action == "integrate_preview":
        return await _action_integrate_preview(session, payload, send_progress, cancel_event)
    if action == "export_poni":
        return await _action_export_poni(session, payload, send_progress, cancel_event)
    return _err(f"Unhandled action: {action!r}", f"未处理的操作：{action!r}")
