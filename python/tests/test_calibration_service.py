#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_calibration_service.py — closed-loop tests for the calibration service
标定服务闭环测试（合成图像，无需大体积测试数据）

Builds a synthetic LaB6 calibration image with the installed pyFAI, then walks
the full headless-calib2 loop: setup → detect_peaks → update_peaks → refine →
ring_overlay → export_poni → seed_from_poni, asserting the recovered geometry
matches the ground truth. Also covers list_calibrants, the refine constraint
(wavelength fixed) and the bilingual error paths.
用 pyFAI 生成合成 LaB6 标定图，然后走完 无界面 calib2 全流程：
setup → detect_peaks → update_peaks → refine → ring_overlay → export_poni →
seed_from_poni，并断言恢复的几何与真值一致。另覆盖 list_calibrants、精修
约束（波长固定）与双语错误路径。

Ground truth / 真值：512x512, pixel 172 µm, dist 200 mm, beam centre (256, 256),
rotations 0. NOTE on wavelength: the task sketch suggested 1.5418 Å, but at
200 mm on a 512x512 / 172 µm detector the corner only reaches 2θ ≈ 17.3° while
LaB6's first ring sits at 2θ ≈ 21.4° for Cu Kα — no ring would be visible and
calibration would be impossible. The test therefore uses λ = 0.5 Å
(≈ 24.8 keV, a routine synchrotron calibration energy) which puts 3 LaB6 rings
cleanly on the detector (radii ≈ 141 / 206 / 257 px).
波长说明：任务草案建议 1.5418 Å，但在 200 mm、512x512、172 µm 探测器上
角落仅到 2θ ≈ 17.3°，而 Cu Kα 下 LaB6 首环在 2θ ≈ 21.4°——探测器上无任何
环可用，无法标定。故改用 λ = 0.5 Å（≈ 24.8 keV，常见同步辐射标定能量），
使 3 个 LaB6 环完整落在探测器内（半径约 141 / 206 / 257 像素）。

Determinism: pyFAI's ``Massif.peaks_from_area`` shuffles candidate points via
the global ``numpy.random`` state, so the test seeds it before peak picking;
everything else (fake image, refine, contours) is deterministic.
确定性：``Massif.peaks_from_area`` 内部用全局 ``numpy.random`` 洗牌候选点，
故测试在寻峰前固定随机种子；其余步骤（合成图、精修、等值线）均确定性。
"""

from __future__ import annotations

import asyncio
import math
import sys
import time
from pathlib import Path

import fabio
import numpy as np
import pytest

# Ensure python/ is importable / 确保 python/ 在导入路径上
_BETA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BETA_ROOT) not in sys.path:
    sys.path.insert(0, str(_BETA_ROOT))

from python.services.calibration import (  # noqa: E402
    _CUSTOM_CALIBRANTS as _CUSTOM_D_SPACINGS,
    handle_calibration,
)

# ---------------------------------------------------------------------------
# Ground truth / 真值
# ---------------------------------------------------------------------------
SHAPE = (512, 512)
PIXEL_UM = 172.0
PIXEL_M = PIXEL_UM * 1e-6
DIST_MM = 200.0
DIST_M = DIST_MM * 1e-3
WAVELENGTH_A = 0.5
WAVELENGTH_M = WAVELENGTH_A * 1e-10
CENTER_Y_PX = 256.0
CENTER_X_PX = 256.0
CALIBRANT_NAME = "LaB6"
RNG_SEED = 20260922


# ---------------------------------------------------------------------------
# Helpers / 辅助函数
# ---------------------------------------------------------------------------

async def _noop_progress(fraction: float, message: str) -> None:
    """Stub progress sink. / 进度回调桩。"""


def _cancel_event() -> asyncio.Event:
    return asyncio.Event()


def _run(payload: dict) -> dict:
    """Synchronous wrapper around handle_calibration. / 同步执行一次调用。"""
    return asyncio.run(handle_calibration(payload, _noop_progress, _cancel_event()))


def _ok(result: dict) -> dict:
    assert isinstance(result, dict), result
    assert result.get("status") == "ok", f"expected ok, got: {result}"
    return result


@pytest.fixture(scope="module")
def synthetic_edf(tmp_path_factory) -> str:
    """Generate the synthetic calibration frame as an .edf (fabio-readable,
    hence ImageLoader-compatible). / 生成合成标定图并保存为 .edf
    （fabio 可读，即 ImageLoader 可加载）。"""
    import pyFAI.calibrant as calibrant_mod
    from pyFAI.detectors import Detector
    from pyFAI.integrator.azimuthal import AzimuthalIntegrator

    calibrant = calibrant_mod.get_calibrant(CALIBRANT_NAME)
    detector = Detector(pixel1=PIXEL_M, pixel2=PIXEL_M, max_shape=SHAPE)
    ai = AzimuthalIntegrator(
        dist=DIST_M,
        poni1=CENTER_Y_PX * PIXEL_M,
        poni2=CENTER_X_PX * PIXEL_M,
        detector=detector,
        wavelength=WAVELENGTH_M,
    )
    image = calibrant.fake_calibration_image(ai, shape=SHAPE, Imax=1000.0)
    assert float(np.nanmax(image)) > 0

    path = tmp_path_factory.mktemp("calib") / "synthetic_lab6.edf"
    fabio.edfimage.EdfImage(data=np.asarray(image, dtype=np.float64)).write(str(path))
    return str(path)


# ---------------------------------------------------------------------------
# list_calibrants / 标样列表
# ---------------------------------------------------------------------------

def test_list_calibrants():
    result = _ok(_run({"action": "list_calibrants"}))
    calibrants = result["calibrants"]
    assert isinstance(calibrants, list) and len(calibrants) > 10
    assert calibrants == sorted(calibrants)
    assert CALIBRANT_NAME in calibrants


# ---------------------------------------------------------------------------
# Full closed-loop calibration / 全流程闭环标定
# ---------------------------------------------------------------------------

def test_full_calibration_flow(synthetic_edf: str, tmp_path: Path):
    # -- setup ---------------------------------------------------------------
    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,  # exact guess on purpose / 故意使用准确初值
    }))
    session_id = setup["sessionId"]
    assert setup["shape"] == [SHAPE[0], SHAPE[1]]
    assert setup["calibrantName"] == CALIBRANT_NAME
    assert setup["pixelSizeUm"] == pytest.approx(PIXEL_UM, rel=1e-6)
    assert setup["wavelengthA"] == pytest.approx(WAVELENGTH_A, rel=1e-9)
    assert setup["distMm"] == pytest.approx(DIST_MM, rel=1e-9)

    # -- detect_peaks (seeded for determinism) --------------------------------
    np.random.seed(RNG_SEED)
    detect = _ok(_run({"action": "detect_peaks", "sessionId": session_id}))
    peaks = detect["peaks"]
    assert len(peaks) >= 50, f"too few auto-picked peaks: {len(peaks)}"
    for peak in peaks:
        assert 0 <= peak["y"] < SHAPE[0] and 0 <= peak["x"] < SHAPE[1]
        assert peak["ring"] is None
        assert peak["intensity"] > 0

    # -- update_peaks (echo the full detected list back, as the UI would) ------
    edited = [{"y": p["y"], "x": p["x"]} for p in peaks]
    updated = _ok(_run({"action": "update_peaks", "sessionId": session_id, "peaks": edited}))
    assert len(updated["peaks"]) == len(edited)
    ring_numbers = {p["ring"] for p in updated["peaks"]}
    assert len(ring_numbers) >= 2, f"peaks should span several rings, got {ring_numbers}"
    assert all(isinstance(r, int) for r in ring_numbers)

    # -- refine (defaults: all free except wavelength; passes=2) --------------
    refined = _ok(_run({"action": "refine", "sessionId": session_id, "passes": 2}))
    geometry = refined["geometry"]
    assert refined["chi2"] is None or refined["chi2"] >= 0
    assert refined["residuals"], "residuals must not be empty"
    for res in refined["residuals"]:
        assert res["delta_deg"] == pytest.approx(
            res["tth_meas_deg"] - res["tth_theo_deg"], abs=1e-12,
        )

    # Ground-truth recovery: dist within 3%, beam centre within 5 px.
    # 真值恢复：距离 3% 以内，光束中心 5 像素以内。
    assert geometry["dist_mm"] == pytest.approx(DIST_MM, rel=0.03), geometry
    assert abs(geometry["center_x_px"] - CENTER_X_PX) <= 5.0, geometry
    assert abs(geometry["center_y_px"] - CENTER_Y_PX) <= 5.0, geometry
    # Wavelength was FIXED (default free={'wavelength': False}) → unchanged.
    # 波长默认固定 → 应保持不变。
    assert geometry["wavelength_A"] == pytest.approx(WAVELENGTH_A, rel=1e-9)
    # Untilted truth → refined tilts stay essentially zero. / 真值无倾角。
    assert abs(geometry["rot1_deg"]) < 1.0 and abs(geometry["rot2_deg"]) < 1.0

    # -- ring_overlay ----------------------------------------------------------
    overlay = _ok(_run({"action": "ring_overlay", "sessionId": session_id}))
    rings = overlay["rings"]
    assert len(rings) >= 3, f"expected >= 3 overlay rings, got {len(rings)}"
    for ring in rings:
        assert isinstance(ring["ring"], int)
        assert ring["d_spacing_A"] and ring["d_spacing_A"] > 0
        points = ring["points"]
        assert 0 < len(points) <= 600
        for row, col in points:
            assert 0.0 <= row < SHAPE[0]
            assert 0.0 <= col < SHAPE[1]

    # -- export_poni + seed_from_poni roundtrip --------------------------------
    poni_path = tmp_path / "refined.poni"
    exported = _ok(_run({
        "action": "export_poni",
        "sessionId": session_id,
        "savePath": str(poni_path),
    }))
    assert poni_path.is_file()
    assert exported["summary"]["dist_mm"] == pytest.approx(geometry["dist_mm"], rel=1e-12)
    assert exported["citation"]["pyfai_paper"].startswith("Ashiotis")
    assert "MIT" in exported["citation"]["license"]

    seeded = _ok(_run({"action": "seed_from_poni", "filePath": str(poni_path)}))
    seed = seeded["seed"]
    assert seed["dist_mm"] == pytest.approx(geometry["dist_mm"], rel=1e-6)
    assert seed["wavelength_A"] == pytest.approx(WAVELENGTH_A, rel=1e-6)
    assert seed["pixel_size_um"] == pytest.approx(PIXEL_UM, rel=1e-6)
    assert seed["center_x_px"] == pytest.approx(geometry["center_x_px"], rel=1e-6)
    assert seed["center_y_px"] == pytest.approx(geometry["center_y_px"], rel=1e-6)
    assert seed["rot3_deg"] == pytest.approx(geometry["rot3_deg"], abs=1e-9)

    # -- integrate_preview (calib2 Integration parity, with timing) ----------
    t0 = time.perf_counter()
    preview = _ok(_run({"action": "integrate_preview", "sessionId": session_id}))
    t_integrate = time.perf_counter() - t0
    one, two = preview["1d"], preview["2d"]
    assert len(one["x"]) == 1024 and len(one["y"]) == 1024
    assert two["nAzim"] <= 360 and two["nRad"] <= 400
    assert len(two["intensity"]) == two["nRad"] * two["nAzim"]
    assert two["xRange"][0] < two["xRange"][1]
    assert two["yRange"][0] < two["yRange"][1]
    # Strict-JSON safety: every value is a finite float or None (never NaN).
    # 严格 JSON 安全：每个值要么是有限浮点要么 None（绝不能是 NaN）。
    for v in one["x"] + one["y"]:
        assert v is None or math.isfinite(v)
    for v in two["intensity"]:
        assert v is None or math.isfinite(v)
    assert preview["unit"] == "q_nm^-1"
    print(
        f"[timing] closed-loop E2E 512²: integrate_preview={t_integrate:.3f}s "
        f"(1d npt={len(one['x'])}, 2d {two['nRad']}×{two['nAzim']})",
    )

    # -- ring_overlay twice: identical output + 2θ-map cache HIT -------------
    overlay_b = _ok(_run({"action": "ring_overlay", "sessionId": session_id}))
    assert overlay_b["rings"] == rings, "unchanged geometry must reuse the cached 2θ map"


# ---------------------------------------------------------------------------
# PERFORMANCE: session Massif cache / 会话级 Massif 缓存
# ---------------------------------------------------------------------------

def _setup_session(edf_path: str) -> str:
    """Fresh setup on the standard synthetic frame; returns the session id.
    在标准合成图上新建会话并返回会话 id。"""
    return _ok(_run({
        "action": "setup",
        "filePath": edf_path,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))["sessionId"]


def test_massif_cache_equivalence_and_hit_logged(synthetic_edf: str, caplog):
    """Two ring_picks with the session Massif cache give IDENTICAL results,
    the second call logs a cache HIT, and clearing the cache (the old
    rebuild-per-call behaviour) reproduces the same peaks too.
    会话 Massif 缓存：两次 ring_pick 结果完全一致；第二次记录缓存命中日志；
    清空缓存（旧的一次一建行为）重跑结果仍一致。"""
    import logging

    sid = _setup_session(synthetic_edf)
    r0 = _first_ring_radius_px()
    guides = _ring_guide_points(r0, [0.0, 90.0, 180.0])

    with caplog.at_level(logging.INFO, logger="python.services.calibration"):
        np.random.seed(RNG_SEED)
        first = _ok(_run({"action": "ring_pick", "sessionId": sid, "points": guides}))
        np.random.seed(RNG_SEED)
        second = _ok(_run({"action": "ring_pick", "sessionId": sid, "points": guides}))

    assert first["peaks"] and second["peaks"]
    assert [(p["y"], p["x"]) for p in first["peaks"]] == [
        (p["y"], p["x"]) for p in second["peaks"]
    ], "cached ring_pick must be equivalent to the uncached one"
    assert "massif cache: MISS" in caplog.text
    assert "massif cache: HIT" in caplog.text, "second pick must log a cache HIT"

    # Old behaviour (rebuilt Massif per call) — same seeded result.
    # 旧行为（每次重建 Massif）——同种子结果一致。
    from python.services import calibration as calib_module

    session = calib_module._SESSIONS[sid]
    session["massif_cache"] = {}
    np.random.seed(RNG_SEED)
    rebuilt = _ok(_run({"action": "ring_pick", "sessionId": sid, "points": guides}))
    assert [(p["y"], p["x"]) for p in rebuilt["peaks"]] == [
        (p["y"], p["x"]) for p in first["peaks"]
    ], "cache clearing must not change the harvest"


@pytest.fixture(scope="module")
def synthetic_edf_2048(tmp_path_factory) -> str:
    """2048² synthetic LaB6 frame — the 大图 the performance fix targets.
    2048² 合成 LaB6 图——性能修复针对的大图。"""
    import pyFAI.calibrant as calibrant_mod
    from pyFAI.detectors import Detector
    from pyFAI.integrator.azimuthal import AzimuthalIntegrator

    calibrant = calibrant_mod.get_calibrant(CALIBRANT_NAME)
    detector = Detector(pixel1=PIXEL_M, pixel2=PIXEL_M, max_shape=(2048, 2048))
    ai = AzimuthalIntegrator(
        dist=DIST_M,
        poni1=1024.0 * PIXEL_M,
        poni2=1024.0 * PIXEL_M,
        detector=detector,
        wavelength=WAVELENGTH_M,
    )
    image = calibrant.fake_calibration_image(ai, shape=(2048, 2048), Imax=1000.0)
    path = tmp_path_factory.mktemp("calib2048") / "synthetic_lab6_2048.edf"
    fabio.edfimage.EdfImage(data=np.asarray(image, dtype=np.float64)).write(str(path))
    return str(path)


def test_massif_cache_speedup_2048(synthetic_edf_2048: str, caplog):
    """PERFORMANCE acceptance: on a 2048² frame, three consecutive ring_pick
    calls with the session Massif cache are FASTER than three calls that
    rebuild the Massif each time (the pre-fix behaviour); the pick_peak path
    (which recomputes ``get_labeled_massif`` per call in pyFAI — the dominant
    cost) is timed the same way. Timings are printed as an explicit
    before/after comparison. / 性能验收：2048² 图上，启用会话缓存的连续 3 次
    ring_pick 快于每次重建（修复前行为）；pick_peak 路径（pyFAI 中每次调用都
    会重算 get_labeled_massif——主要耗时）同样计时；打印前后耗时对比。"""
    import logging

    sid = _setup_session(synthetic_edf_2048)
    r0 = _first_ring_radius_px()
    guides = _ring_guide_points(r0, [0.0, 90.0, 180.0])
    on_ring = {"y": 1024 + int(r0), "x": 1024}

    from python.services import calibration as calib_module

    session = calib_module._SESSIONS[sid]

    def _timed_calls(action: str, payload: dict, clear_cache: bool) -> list:
        times = []
        for _ in range(3):
            if clear_cache:
                session["massif_cache"] = {}
            np.random.seed(RNG_SEED)
            t0 = time.perf_counter()
            result = _ok(_run({"action": action, "sessionId": sid, **payload}))
            times.append(time.perf_counter() - t0)
            assert result["peaks"], "every harvest must succeed"
        return times

    with caplog.at_level(logging.INFO, logger="python.services.calibration"):
        # BEFORE (pre-fix behaviour): Massif rebuilt on every call.
        ring_uncached = _timed_calls("ring_pick", {"points": guides}, clear_cache=True)
        pick_uncached = _timed_calls("pick_peak", on_ring, clear_cache=True)
        # AFTER: session cache keeps the Massif (and its labeled massif).
        ring_cached = _timed_calls("ring_pick", {"points": guides}, clear_cache=False)
        pick_cached = _timed_calls("pick_peak", on_ring, clear_cache=False)
    assert "massif cache: HIT" in caplog.text

    def _mean(xs: list) -> float:
        return sum(xs) / len(xs)

    print(f"[timing] ring_pick  2048² BEFORE cache (rebuild Massif): "
          f"{[f'{t:.3f}s' for t in ring_uncached]} mean={_mean(ring_uncached):.3f}s")
    print(f"[timing] ring_pick  2048² AFTER  cache (session cache):   "
          f"{[f'{t:.3f}s' for t in ring_cached]} mean={_mean(ring_cached):.3f}s")
    print(f"[timing] pick_peak  2048² BEFORE cache (rebuild Massif + labeled massif): "
          f"{[f'{t:.3f}s' for t in pick_uncached]} mean={_mean(pick_uncached):.3f}s")
    print(f"[timing] pick_peak  2048² AFTER  cache (session cache):   "
          f"{[f'{t:.3f}s' for t in pick_cached]} mean={_mean(pick_cached):.3f}s")
    print(f"[timing] speedup pick_peak: {_mean(pick_uncached) / _mean(pick_cached):.1f}×")

    # ring_pick's cost on a synthetic frame is dominated by the numpy band
    # computation (peaks_from_area never touches get_labeled_massif), so its
    # before/after comparison stays a PRINT; output equivalence is asserted in
    # test_massif_cache_equivalence_and_hit_logged. The ordering assertion
    # lives on pick_peak, where the cached labeled massif is decisive.
    # 合成图上 ring_pick 的耗时由环带 numpy 计算主导（peaks_from_area 不触发
    # get_labeled_massif），故其前后对比仅打印；结果等价由
    # test_massif_cache_equivalence_and_hit_logged 断言；先后断言放在
    # pick_peak 上——缓存的 labeled massif 在该路径起决定作用。
    assert _mean(pick_cached) < 0.5 * _mean(pick_uncached), (
        f"cached pick_peak ({_mean(pick_cached):.3f}s mean) must beat the rebuilt one "
        f"({_mean(pick_uncached):.3f}s mean) by >2×"
    )


# ---------------------------------------------------------------------------
# integrate_preview: shapes / ranges sanity / 积分预览：形状与范围检查
# ---------------------------------------------------------------------------

def test_integrate_preview_shapes_ranges_and_errors(synthetic_edf: str):
    """integrate_preview returns a 1-D curve and a downsampled 2-D cake with
    consistent shapes/ranges; custom npt parameters are honored; calling
    before any peak assignment errors bilingually. / 积分预览返回 1D 曲线与
    降采样 2D cake，形状/范围自洽；自定义 npt 生效；未分配峰时双语报错。"""
    sid = _setup_session(synthetic_edf)

    # No gr yet → the same bilingual error as ring_overlay.
    err = _run({"action": "integrate_preview", "sessionId": sid})
    assert err["status"] == "error"
    assert "update_peaks" in err["message"]

    np.random.seed(RNG_SEED)
    peaks = _ok(_run({"action": "detect_peaks", "sessionId": sid}))["peaks"]
    _ok(_run({
        "action": "update_peaks", "sessionId": sid,
        "peaks": [{"y": p["y"], "x": p["x"]} for p in peaks],
    }))
    _ok(_run({"action": "refine", "sessionId": sid, "passes": 2}))

    # Custom bin counts: 1d npt=256, 2d 100×90 (both below the transport caps,
    # so no downsampling — lengths must match exactly).
    preview = _ok(_run({
        "action": "integrate_preview", "sessionId": sid,
        "npt1d": 256, "npt2dRad": 100, "npt2dAzim": 90,
    }))
    one, two = preview["1d"], preview["2d"]
    assert len(one["x"]) == 256 and len(one["y"]) == 256
    assert two["nRad"] == 100 and two["nAzim"] == 90
    assert len(two["intensity"]) == 100 * 90
    # Ranges: ascending; azimuth spans ~[-180, 180] degrees (bin centers are
    # inset by half a bin, so allow one bin width: 360/90 = 4°).
    # 范围递增；方位角覆盖约 [-180, 180]（箱中心内缩半个箱宽，容差取一箱 4°）。
    assert two["xRange"][0] < two["xRange"][1]
    assert two["yRange"][0] == pytest.approx(-180.0, abs=4.0)
    assert two["yRange"][1] == pytest.approx(180.0, abs=4.0)
    for v in two["intensity"]:
        assert v is None or math.isfinite(v)

    # Default caps: npt2dRad=800 downsamples to ≤400 radial columns.
    default_preview = _ok(_run({"action": "integrate_preview", "sessionId": sid}))
    assert default_preview["2d"]["nRad"] <= 400
    assert default_preview["2d"]["nAzim"] <= 360

    # autoSave export (去积分): unique temp path, file exists, summary present.
    # autoSave 导出（去积分）：唯一临时路径、文件存在、附几何摘要。
    import tempfile

    auto = _ok(_run({"action": "export_poni", "sessionId": sid, "autoSave": True}))
    auto_path = Path(auto["savePath"])
    try:
        assert auto_path.is_file()
        assert str(auto_path).startswith(str(Path(tempfile.gettempdir())))
        assert auto_path.suffix == ".poni"
        assert auto["summary"]["dist_mm"] > 0
    finally:
        auto_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Refine constraint variants / 精修约束变体
# ---------------------------------------------------------------------------

def test_refine_fixed_dist_and_wavelength(synthetic_edf: str, tmp_path: Path):
    """With dist and wavelength both fixed the refinement must not move them.

    Note: "fixed" pins a parameter at its pre-refine value, and that value is
    NOT the raw user guess — update_peaks' GeometryRefinement constructor runs
    guess_poni(), whose innermost-ring ellipse fit already refines dist/poni.
    So the reference is captured via export_poni (which does not refine) and
    the fixed params are asserted unchanged by the refine call itself.
    固定 dist 与 wavelength 后，精修不得改变二者。注意：“固定”是钉在精修前的
    当前值上，而该值并非用户的原始初值——update_peaks 构造 GeometryRefinement
    时 guess_poni() 的最内环椭圆拟合已经改进过 dist/poni。故先经 export_poni
    （不精修）截取参考几何，再断言精修本身未改动被固定的参数。
    """
    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    sid = setup["sessionId"]
    np.random.seed(RNG_SEED)
    peaks = _ok(_run({"action": "detect_peaks", "sessionId": sid}))["peaks"]
    _ok(_run({
        "action": "update_peaks", "sessionId": sid,
        "peaks": [{"y": p["y"], "x": p["x"]} for p in peaks],
    }))
    # Snapshot the pre-refine (guess_poni-improved) geometry. / 截取精修前几何。
    before = _ok(_run({
        "action": "export_poni",
        "sessionId": sid,
        "savePath": str(tmp_path / "pre_refine.poni"),
    }))["summary"]
    refined = _ok(_run({
        "action": "refine", "sessionId": sid, "passes": 3,
        "free": {"dist": False, "wavelength": False},
    }))
    geometry = refined["geometry"]
    assert geometry["dist_mm"] == pytest.approx(before["dist_mm"], rel=1e-9)
    assert geometry["wavelength_A"] == pytest.approx(WAVELENGTH_A, rel=1e-9)
    # Centre still recovered while dist is pinned. / 距离钉死时中心仍可恢复。
    assert abs(geometry["center_x_px"] - CENTER_X_PX) <= 5.0
    assert abs(geometry["center_y_px"] - CENTER_Y_PX) <= 5.0


# ---------------------------------------------------------------------------
# Custom X-FAIS calibrants (Y2O3 / polypropylene) / 补充标样
# ---------------------------------------------------------------------------

CUSTOM_CALIBRANT_CASES = [
    # (name, min expected overlay rings) / (标样名, 理论环叠加下限)
    # At the standard truth geometry (512², 172 µm, 200 mm, λ=0.5 Å) Y2O3
    # places 2 rings on the detector (r≈192/223 px; 3rd at ≈318 px is off);
    # polypropylene's 39-line computed table (Mencik/COD 1552371, I≥1 %,
    # d≥1.93 Å) puts many rings in reach — keep the ≥2 floor.
    # 该几何下 Y2O3 可见 2 环；聚丙烯 39 线表（Mencik/COD 1552371 计算表，
    # I≥1%、d≥1.93 Å）可见环数远超 2，此处仅保留下限。
    ("Y2O3_custom", 2),
    ("Polypropylene_custom", 2),
]


@pytest.mark.parametrize("calibrant_name,min_rings", CUSTOM_CALIBRANT_CASES)
def test_custom_calibrant_setup_and_overlay(calibrant_name: str, min_rings: int,
                                            tmp_path: Path):
    """X-FAIS supplementary calibrants must be listed, accepted by setup and
    produce theoretical rings (detect → update → ring_overlay ≥ 2 rings).
    X-FAIS 补充标样：必须出现在列表中、被 setup 接受，并给出 ≥2 个理论环。
    """
    # Listed. / 出现在 list_calibrants。
    listed = _ok(_run({"action": "list_calibrants"}))["calibrants"]
    assert calibrant_name in listed

    # Synthetic frame from the custom calibrant's own d-spacings.
    # 用补充标样自身的 d 间距生成合成图。
    import pyFAI.calibrant as calibrant_mod
    from pyFAI.detectors import Detector
    from pyFAI.integrator.azimuthal import AzimuthalIntegrator

    custom = calibrant_mod.Calibrant(
        dspacing=list(_CUSTOM_D_SPACINGS[calibrant_name]),
    )
    custom.wavelength = WAVELENGTH_M
    detector = Detector(pixel1=PIXEL_M, pixel2=PIXEL_M, max_shape=SHAPE)
    ai = AzimuthalIntegrator(
        dist=DIST_M,
        poni1=CENTER_Y_PX * PIXEL_M,
        poni2=CENTER_X_PX * PIXEL_M,
        detector=detector,
        wavelength=WAVELENGTH_M,
    )
    image = custom.fake_calibration_image(ai, shape=SHAPE, Imax=1000.0)
    edf = tmp_path / f"synthetic_{calibrant_name}.edf"
    fabio.edfimage.EdfImage(data=np.asarray(image, dtype=np.float64)).write(str(edf))

    # setup accepts the custom name. / setup 接受补充标样名。
    setup = _ok(_run({
        "action": "setup",
        "filePath": str(edf),
        "calibrantName": calibrant_name,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    assert setup["calibrantName"] == calibrant_name
    sid = setup["sessionId"]

    # Full peak path → ring overlay. / 完整峰路径 → 理论环叠加。
    np.random.seed(RNG_SEED)
    peaks = _ok(_run({"action": "detect_peaks", "sessionId": sid}))["peaks"]
    assert peaks, f"detect_peaks found no peaks for {calibrant_name}"
    _ok(_run({
        "action": "update_peaks", "sessionId": sid,
        "peaks": [{"y": p["y"], "x": p["x"]} for p in peaks],
    }))
    overlay = _ok(_run({"action": "ring_overlay", "sessionId": sid}))
    assert len(overlay["rings"]) >= min_rings, (
        f"{calibrant_name}: expected >= {min_rings} overlay rings, "
        f"got {len(overlay['rings'])}"
    )
    for ring in overlay["rings"]:
        assert ring["d_spacing_A"] > 0


# ---------------------------------------------------------------------------
# Error paths / 错误路径
# ---------------------------------------------------------------------------

def test_unknown_action_returns_bilingual_error():
    result = _run({"action": "does_not_exist"})
    assert result["status"] == "error"
    assert "does_not_exist" in result["message"]


def test_missing_session_id_returns_error():
    result = _run({"action": "detect_peaks", "sessionId": "no-such-session"})
    assert result["status"] == "error"
    assert "no-such-session" in result["message"]


def test_setup_requires_wavelength(synthetic_edf: str):
    result = _run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "distGuessMm": DIST_MM,
    })
    assert result["status"] == "error"
    assert "wavelengthA" in result["message"]


def test_setup_rejects_unknown_calibrant(synthetic_edf: str):
    result = _run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": "NotACalibrant",
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    })
    assert result["status"] == "error"
    assert "NotACalibrant" in result["message"]


def test_refine_before_peaks_returns_error(synthetic_edf: str):
    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    result = _run({"action": "refine", "sessionId": setup["sessionId"]})
    assert result["status"] == "error"
    assert "update_peaks" in result["message"]


# ---------------------------------------------------------------------------
# STEP 1: empty update_peaks is a no-op clear / 空列表 = 清空而非报错
# ---------------------------------------------------------------------------

def test_update_peaks_empty_list_is_noop_clear(synthetic_edf: str):
    """The 完成环选 bug: an empty peaks list used to hard-error with
    “peaks must be a non-empty list of {'y','x'}”. It must now clear the
    session peaks and succeed. / 空峰列表必须清空会话并返回成功。"""
    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    sid = setup["sessionId"]
    np.random.seed(RNG_SEED)
    peaks = _ok(_run({"action": "detect_peaks", "sessionId": sid}))["peaks"]
    assert peaks
    _ok(_run({
        "action": "update_peaks", "sessionId": sid,
        "peaks": [{"y": p["y"], "x": p["x"]} for p in peaks],
    }))
    # The failing call from the bug report. / 缺陷报告中的失败调用。
    cleared = _ok(_run({"action": "update_peaks", "sessionId": sid, "peaks": []}))
    assert cleared["peaks"] == []
    # A missing/None peaks key still errors (payload contract unchanged).
    # 缺少 peaks 键仍然报错（载荷契约不变）。
    bad = _run({"action": "update_peaks", "sessionId": sid})
    assert bad["status"] == "error"


# ---------------------------------------------------------------------------
# STEP 2a: ring_pick calib2 extraction variants / 环选两种提取语义
# ---------------------------------------------------------------------------

def _first_ring_radius_px() -> float:
    """Ground-truth pixel radius of LaB6's first ring at the test geometry.
    测试几何下 LaB6 首环的真实像素半径。"""
    import math

    import pyFAI.calibrant as calibrant_mod

    calibrant = calibrant_mod.get_calibrant(CALIBRANT_NAME)
    calibrant.wavelength = WAVELENGTH_M
    tth0 = next(v for v in calibrant.get_2th() if v is not None)
    return DIST_M * math.tan(tth0) / PIXEL_M


def _ring_guide_points(radius_px: float, angles_deg) -> list:
    """Guide points ON the first ring at the given angles. / 按给定角度在首环
    上取引导点（角度与后端 atan2(y-cy, x-cx) 同约定）。"""
    import math

    return [
        {
            "y": CENTER_Y_PX + radius_px * math.sin(math.radians(a)),
            "x": CENTER_X_PX + radius_px * math.cos(math.radians(a)),
        }
        for a in angles_deg
    ]


def _peak_angles_deg(peaks: list, cy: float, cx: float) -> list:
    import math

    out = []
    for p in peaks:
        a = math.degrees(math.atan2(p["y"] - cy, p["x"] - cx)) % 360.0
        out.append(a)
    return out


def test_ring_pick_contiguous_arc_and_beyond_mask(synthetic_edf: str):
    """Contiguous ("Arc", extract contiguous peaks) harvests only the traced
    arc; beyond-mask ("Ring", extract peaks beyond masked values) harvests the
    full 360° band. / 连续模式只收所画弧段；越过掩码模式收整环。"""
    import math

    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    sid = setup["sessionId"]
    r0 = _first_ring_radius_px()
    assert 100.0 < r0 < 200.0, f"unexpected first-ring radius: {r0}"
    # A contiguous ~60° arc of guide points. / 连续约 60° 的引导点弧段。
    guides = _ring_guide_points(r0, [80.0, 110.0, 140.0])

    # -- contiguous (default) ------------------------------------------------
    np.random.seed(RNG_SEED)
    cont = _ok(_run({
        "action": "ring_pick", "sessionId": sid, "points": guides,
    }))
    assert cont["mode"] == "contiguous"
    assert cont["region"]["arc"] is not None
    c_peaks = cont["peaks"]
    assert len(c_peaks) >= 5, f"contiguous harvest too small: {len(c_peaks)}"
    cy = cont["region"]["cy"]
    cx = cont["region"]["cx"]
    tol = cont["region"]["tolPx"]
    radius = cont["region"]["radiusPx"]
    assert abs(radius - r0) <= 3.0  # circle fit recovers the guide circle
    for p in c_peaks:
        # On the band (valley snapping may drift a little beyond tol).
        assert abs(math.hypot(p["y"] - cy, p["x"] - cx) - radius) <= tol + 15.0
    # Every peak inside the traced arc [50°, 170°] (60° span + 30° margins).
    for a in _peak_angles_deg(c_peaks, cy, cx):
        assert 50.0 <= a <= 170.0, f"peak outside contiguous arc: {a}"

    # -- beyond mask -----------------------------------------------------------
    np.random.seed(RNG_SEED)
    full = _ok(_run({
        "action": "ring_pick", "sessionId": sid, "points": guides,
        "extractMode": "beyond_mask",
    }))
    assert full["mode"] == "beyond_mask"
    assert full["region"]["arc"] is None
    f_peaks = full["peaks"]
    # Full-ring harvest beats the single-arc harvest. / 整环多于单弧。
    assert len(f_peaks) > len(c_peaks), (
        f"beyond-mask harvest ({len(f_peaks)}) should exceed contiguous ({len(c_peaks)})"
    )
    angles = sorted(_peak_angles_deg(f_peaks, full["region"]["cy"], full["region"]["cx"]))
    biggest_gap = max(
        b - a for a, b in zip(angles, angles[1:])
    )
    assert biggest_gap < 90.0, f"full-ring harvest leaves a dead arc: {biggest_gap}"
    for p in f_peaks:
        d = abs(
            math.hypot(p["y"] - full["region"]["cy"], p["x"] - full["region"]["cx"])
            - full["region"]["radiusPx"]
        )
        assert d <= full["region"]["tolPx"] + 15.0


def test_ring_pick_requires_three_points(synthetic_edf: str):
    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    r0 = _first_ring_radius_px()
    result = _run({
        "action": "ring_pick",
        "sessionId": setup["sessionId"],
        "points": _ring_guide_points(r0, [0.0, 90.0]),
    })
    assert result["status"] == "error"
    assert "3" in result["message"]


# ---------------------------------------------------------------------------
# STEP 2c: keep/assign modes + per-peak self-check / 环号保留与自检
# ---------------------------------------------------------------------------

def test_update_peaks_keep_mode_and_suspect_selfcheck(synthetic_edf: str):
    """mode='keep' honors user-edited ring numbers and flags peaks that sit
    closer to a neighbouring ring (suspect=True); the default re-assigns.
    keep 模式尊重用户环号并标记偏离峰；默认模式全部重分配。"""
    import pyFAI.calibrant as calibrant_mod

    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    sid = setup["sessionId"]
    np.random.seed(RNG_SEED)
    detect = _ok(_run({"action": "detect_peaks", "sessionId": sid}))["peaks"]
    edited = [{"y": p["y"], "x": p["x"]} for p in detect]

    assigned = _ok(_run({
        "action": "update_peaks", "sessionId": sid, "peaks": edited,
    }))["peaks"]
    assert all("dtheta_deg" in p and "suspect" in p for p in assigned)

    # A well-placed peak (smallest |Δ2θ|) must pass the self-check.
    good_idx = min(range(len(assigned)), key=lambda i: abs(assigned[i]["dtheta_deg"]))
    good = assigned[good_idx]
    assert good["suspect"] is False

    # Number of REACHABLE rings (get_2th may hold None past the wavelength).
    calibrant = calibrant_mod.get_calibrant(CALIBRANT_NAME)
    calibrant.wavelength = WAVELENGTH_M
    n_reachable = sum(1 for v in calibrant.get_2th() if v is not None)
    assert n_reachable >= 2

    # Relabel the good peak onto a WRONG ring and keep it (user edit).
    wrong_ring = good["ring"] + 1 if good["ring"] + 1 < n_reachable else good["ring"] - 1
    assert wrong_ring >= 0 and wrong_ring != good["ring"]
    keep_payload = [
        {"y": p["y"], "x": p["x"], "ring": wrong_ring if i == good_idx else None}
        for i, p in enumerate(assigned)
    ]
    kept = _ok(_run({
        "action": "update_peaks", "sessionId": sid, "peaks": keep_payload,
        "mode": "keep",
    }))["peaks"]
    kept_good = kept[good_idx]
    assert kept_good["ring"] == wrong_ring, "keep mode must honor the user edit"
    assert kept_good["suspect"] is True, "a peak on a wrong ring must be flagged"

    # Default mode re-assigns everything from the current geometry.
    reassigned = _ok(_run({
        "action": "update_peaks", "sessionId": sid, "peaks": edited,
    }))["peaks"]
    assert reassigned[good_idx]["ring"] == good["ring"]
    assert reassigned[good_idx]["suspect"] is False


# ---------------------------------------------------------------------------
# beyondMask on pick_peak / detect_peaks / 单峰与自动拾取的越过掩码开关
# ---------------------------------------------------------------------------

def test_pick_peak_beyond_mask_variants(synthetic_edf: str):
    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    sid = setup["sessionId"]
    r0 = _first_ring_radius_px()
    on_ring = {"y": int(CENTER_Y_PX + r0), "x": int(CENTER_X_PX)}

    for extra in ({}, {"beyondMask": True}):
        np.random.seed(RNG_SEED)
        result = _ok(_run({
            "action": "pick_peak", "sessionId": sid, **on_ring, **extra,
        }))
        assert result["peaks"], f"pick_peak returned nothing for {extra}"
        for p in result["peaks"]:
            assert 0 <= p["y"] < SHAPE[0] and 0 <= p["x"] < SHAPE[1]

    np.random.seed(RNG_SEED)
    auto = _ok(_run({
        "action": "detect_peaks", "sessionId": sid, "beyondMask": True,
    }))
    assert len(auto["peaks"]) >= 50


# ---------------------------------------------------------------------------
# REQ 1: mask at setup / setup 阶段掩膜（防止拾取错误）
# ---------------------------------------------------------------------------

def _disk(shape, cy: float, cx: float, radius: float) -> np.ndarray:
    """Boolean disk mask (True inside). / 圆盘布尔掩膜（内部为 True）。"""
    yy, xx = np.ogrid[0:shape[0], 0:shape[1]]
    return np.hypot(yy - cy, xx - cx) <= radius


def test_setup_without_mask_reports_empty_stats(synthetic_edf: str):
    """No mask inputs → zero maskStats and no overlay. / 无掩膜输入 →
    maskStats 全零且无叠加网格。"""
    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    assert setup["maskStats"] == {"maskedPixels": 0, "ratio": 0.0}
    assert setup["maskOverlay"] is None


def test_setup_with_mask_file_and_thresholds(synthetic_edf: str, tmp_path: Path):
    """Mask file (.npy via numpy) + maskMin → correct maskStats/maskOverlay,
    and a planted masked bright blob ON the ring is NEVER harvested by
    ring_pick (full-ring contiguous harvest, guides encircling the ring).
    setup 掩膜文件 + 强度下限 → maskStats/叠加正确；被掩膜的高亮斑在整环
    收峰中绝不被拾取。"""
    import math

    with fabio.open(synthetic_edf) as img:
        image = np.asarray(img.data, dtype=np.float64)

    # Plant a saturated blob on the FIRST ring at 45° — exactly the artifact a
    # user masks to prevent wrong picks. / 在首环 45° 处植入饱和亮斑。
    r0 = _first_ring_radius_px()
    blob_cy = CENTER_Y_PX + r0 * math.sin(math.radians(45.0))
    blob_cx = CENTER_X_PX + r0 * math.cos(math.radians(45.0))
    blob_r = 6.0
    blob = _disk(SHAPE, blob_cy, blob_cx, blob_r)
    assert blob.sum() > 50  # a real disk, not a couple of pixels / 确为圆盘
    image[blob] = 1.0e5
    blobbed_edf = tmp_path / "blob.edf"
    fabio.edfimage.EdfImage(data=image).write(str(blobbed_edf))

    # Mask file covers the blob WITH margin so no blob pixel stays pickable.
    # 掩膜文件以一定余量覆盖亮斑，确保亮斑像素全部不可拾取。
    mask_r = blob_r + 3.0
    mask = _disk(SHAPE, blob_cy, blob_cx, mask_r)
    mask_npy = tmp_path / "mask.npy"
    np.save(str(mask_npy), mask.astype(np.uint8))

    mask_min = 50.0
    setup = _ok(_run({
        "action": "setup",
        "filePath": str(blobbed_edf),
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
        "maskPath": str(mask_npy),
        "maskMin": mask_min,
    }))
    sid = setup["sessionId"]

    # maskStats: file mask | (data < maskMin) | dead pixels (none here).
    # Compare in float32 — the session stores the frame as float32.
    expected = int(
        (mask | (image.astype(np.float32) < mask_min)).sum()
    )
    stats = setup["maskStats"]
    assert stats["maskedPixels"] == expected
    assert stats["ratio"] == pytest.approx(
        expected / (SHAPE[0] * SHAPE[1]), rel=1e-9,
    )

    # maskOverlay: ≤256×256 tile-any grid, blob tile flagged.
    overlay = setup["maskOverlay"]
    assert overlay is not None
    assert overlay["rows"] == 256 and overlay["cols"] == 256
    grid = overlay["grid"]
    assert len(grid) == 256 * 256
    assert set(grid) <= {0, 1}
    assert 0 < sum(grid) < 256 * 256
    tile_r = min(255, int(blob_cy * 256 / SHAPE[0]))
    tile_c = min(255, int(blob_cx * 256 / SHAPE[1]))
    assert grid[tile_r * 256 + tile_c] == 1, "blob tile must be masked / 亮斑所在格必须为 1"

    # Guides encircling the ring → contiguous mode harvests the FULL ring;
    # the masked blob inside the band must contribute NO peak while the rest
    # of the ring is still harvested normally.
    # 引导点环绕整环 → 连续模式收整环；环带内被掩膜的亮斑不出峰，其余正常。
    np.random.seed(RNG_SEED)
    guides = _ring_guide_points(r0, [0.0, 90.0, 180.0, 270.0])
    result = _ok(_run({
        "action": "ring_pick", "sessionId": sid, "points": guides,
    }))
    peaks = result["peaks"]
    assert len(peaks) >= 5, f"ring harvest starved by the mask: {len(peaks)}"
    for p in peaks:
        d = math.hypot(p["y"] - blob_cy, p["x"] - blob_cx)
        assert d > mask_r - 0.5, f"masked blob was harvested (distance {d})"


# ---------------------------------------------------------------------------
# REQ 2: ring_pick assignRing / 逐环收峰直接打环号
# ---------------------------------------------------------------------------

def test_ring_pick_assign_ring(synthetic_edf: str):
    """assignRing=3 stamps EVERY harvested peak with ring 3 (instead of
    leaving it for theoretical nearest-ring assignment); absent/null keeps the
    legacy unassigned behaviour. / assignRing=3 时所有收峰峰环号均为 3；
    缺省/null 保持原有的不分配行为。"""
    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    sid = setup["sessionId"]
    r0 = _first_ring_radius_px()
    guides = _ring_guide_points(r0, [0.0, 90.0, 180.0, 270.0])

    np.random.seed(RNG_SEED)
    stamped = _ok(_run({
        "action": "ring_pick", "sessionId": sid, "points": guides,
        "assignRing": 3,
    }))
    peaks = stamped["peaks"]
    assert peaks, "assignRing harvest must not be empty / 收峰不能为空"
    assert stamped["assignRing"] == 3
    assert all(p["ring"] == 3 for p in peaks)

    # The stamped rings survive update_peaks mode 'keep' (user edit wins).
    # 打上的环号经 keep 模式推送保留（用户编辑优先）。
    kept = _ok(_run({
        "action": "update_peaks", "sessionId": sid, "mode": "keep",
        "peaks": [{"y": p["y"], "x": p["x"], "ring": p["ring"]} for p in peaks],
    }))["peaks"]
    assert all(p["ring"] == 3 for p in kept)

    # Legacy behaviour without assignRing: unassigned peaks (no ring key).
    np.random.seed(RNG_SEED)
    legacy = _ok(_run({
        "action": "ring_pick", "sessionId": sid, "points": guides,
    }))
    assert legacy["peaks"]
    assert legacy["assignRing"] is None
    assert all(p.get("ring") is None for p in legacy["peaks"])
