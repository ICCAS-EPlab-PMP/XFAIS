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
# Export: detector identity, naming, rot lines, truncation / 导出行为
# ---------------------------------------------------------------------------

#: Registry detector whose pixel size matches the ground truth (172 µm) so the
#: whole flow converges with detectorName set. / 像素尺寸与真值一致的注册表
#: 探测器，使设置探测器后全流程仍可收敛。
_EXPORT_DETECTOR = "Pilatus1M"


def test_export_poni_detector_naming_and_rot_lines(synthetic_edf: str, tmp_path: Path):
    """export_poni contract (用户反馈 2026-09-29):
    1. the file lands under the name the user typed (.poni appended when
       missing) — never an auto-generated name;
    2. the registry detector identity is written (Detector: <name> +
       Detector_config), like pyFAI-calib2's export, not an anonymous
       "Detector" with bare pixel sizes;
    3. rotations the user never enabled are written as EXACTLY 0.0 — the tilt
       that guess_poni()'s innermost-ring ellipse fit silently seeds must not
       leak into the file (calib2 format: "Rot: 0.0"); an enabled non-zero rot
       is kept;
    4. re-exporting to the same path replaces the file (pyFAI's save appends
       and readers would pick the stale first block).
    导出契约：①按用户输入命名落盘（缺 .poni 自动补齐），绝不用自动名；
    ②写出注册表探测器身份（与 calib2 一致），而非只有像素尺寸的匿名
    "Detector"；③用户未启用的旋转角在文件中严格为 0.0（calib2 格式），启用过
    的非零 rot 保留；
    ④同路径重复导出为覆盖写（pyFAI save 是追加模式，读取方会取陈旧首块）。
    """
    from pyFAI.integrator.azimuthal import AzimuthalIntegrator

    from python.services import calibration as calib_mod

    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "detectorName": _EXPORT_DETECTOR,
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
    # Default refine (rotations never enabled): guess_poni()'s ellipse fit
    # must NOT leak a tilt into the working geometry — dist/poni are fitted
    # under rot=0, which is exactly what the export then contains.
    # 默认精修（从未启用旋转角）：guess_poni() 的椭圆拟合不得把倾角漏进工作
    # 几何——dist/poni 在 rot=0 下拟合，导出内容与此完全一致。
    _ok(_run({"action": "refine", "sessionId": sid, "passes": 2}))
    gr = calib_mod._SESSIONS[sid]["gr"]
    assert gr.rot1 == 0.0 and gr.rot2 == 0.0 and gr.rot3 == 0.0

    # -- 1) user-typed name without extension / 用户输入的名字缺后缀 -----------
    exported = _ok(_run({
        "action": "export_poni",
        "sessionId": sid,
        "savePath": str(tmp_path / "my-calib"),
    }))
    poni_path = Path(exported["savePath"])
    assert poni_path == tmp_path / "my-calib.poni"
    text = poni_path.read_text(encoding="utf-8")

    # -- 2) detector identity + provenance comments / 探测器身份 + 溯源注释 -----
    assert f"Detector: {_EXPORT_DETECTOR}" in text, text
    assert "Detector_config:" in text, text
    assert '"pixel1"' in text and '"orientation"' in text, text
    assert f"# Calibrant: {CALIBRANT_NAME}" in text, text
    assert "# Image: " in text, text

    # -- 3) never-enabled rotations read exactly 0.0 / 未启用的旋转角严格为 0 ---
    assert "Rot1: 0.0" in text, text
    assert "Rot2: 0.0" in text, text
    assert "Rot3: 0.0" in text, text

    # -- 3b) an enabled non-zero rot survives / 启用过的非零 rot 保留 -----------
    calib_mod._SESSIONS[sid]["gr"].rot1 = 0.01
    _ok(_run({"action": "export_poni", "sessionId": sid, "savePath": str(poni_path)}))
    text2 = poni_path.read_text(encoding="utf-8")
    assert "Rot1: 0.01" in text2, text2
    assert "Rot2: 0.0" in text2 and "Rot3: 0.0" in text2, text2

    # -- 4) re-export truncates / 重复导出为覆盖写 ------------------------------
    assert text2.count("poni_version:") == 1, "append-mode block stacking"

    # -- loads everywhere / 各读取方均可加载 ------------------------------------
    ai = AzimuthalIntegrator()
    ai.load(str(poni_path))
    assert ai.detector.__class__.__name__ == _EXPORT_DETECTOR
    assert ai.rot1 == pytest.approx(0.01, abs=1e-12)
    assert ai.rot2 == 0.0 and ai.rot3 == 0.0
    seeded = _ok(_run({"action": "seed_from_poni", "filePath": str(poni_path)}))
    assert seeded["seed"]["pixel_size_um"] == pytest.approx(PIXEL_UM, rel=1e-6)
    assert seeded["seed"]["rot1_deg"] == pytest.approx(0.01 * 180.0 / math.pi, abs=1e-9)
    assert seeded["seed"]["rot2_deg"] == pytest.approx(0.0, abs=1e-12)


def test_engaged_rot_seeded_from_guess_and_exported(synthetic_edf: str, tmp_path: Path):
    """Rotations the user enables must NOT start the refine from 0: the
    pre-pin guess_poni() ellipse estimate is kept in the session and seeds
    first-time engagement (calib2-like start for genuinely tilted detectors).
    An already-set (non-zero) value is never clobbered, and the engaged rot's
    refined value lands in both the geometry summary and the exported file.
    用户放开的旋转角不得从 0 起步：钉零前的椭圆估计保留在会话中，首次启用时
    作为精修起点（真倾斜探测器的 calib2 式起步）。已被设置的非零值绝不覆盖，
    且启用 rot 精修后的值同时落在几何摘要与导出文件中。
    """
    from python.services import calibration as calib_mod

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

    # Pinned working geometry, pre-pin ellipse estimate preserved.
    # 工作几何已钉零，钉零前的椭圆估计已保留。
    session = calib_mod._SESSIONS[sid]
    gr = session["gr"]
    assert gr.rot1 == 0.0 and gr.rot2 == 0.0 and gr.rot3 == 0.0
    guess = session["guess_rot"]
    assert len(guess) == 3 and all(isinstance(v, float) and math.isfinite(v) for v in guess)

    # First-time engagement seeds rot1 from the estimate, leaves the others.
    # 首次启用：rot1 从估计值起步，其余不动。
    free = {"rot1": True, "rot2": False, "rot3": False}
    calib_mod._seed_newly_engaged_rots(session, free, set())
    assert gr.rot1 == guess[0]
    assert gr.rot2 == 0.0 and gr.rot3 == 0.0

    # An already-set (non-zero) value is never clobbered by re-seeding.
    # 已被设置的非零值绝不被重新播种覆盖。
    gr.rot1 = 0.05
    calib_mod._seed_newly_engaged_rots(session, free, set())
    assert gr.rot1 == 0.05

    # Refine with rot1 engaged, then export: summary and file agree on rad.
    # 放开 rot1 精修后导出：几何摘要与文件中的弧度值一致。
    gr.rot1 = 0.0  # reset to the seeded-start condition / 复位到播种前状态
    calib_mod._seed_newly_engaged_rots(session, free, set())
    refined = _ok(_run({
        "action": "refine", "sessionId": sid, "passes": 2, "free": free,
    }))
    assert math.isfinite(refined["geometry"]["rot1_deg"])
    exported = _ok(_run({
        "action": "export_poni", "sessionId": sid,
        "savePath": str(tmp_path / "engaged.poni"),
    }))
    text = Path(exported["savePath"]).read_text(encoding="utf-8")
    rot1_line = next(l for l in text.splitlines() if l.startswith("Rot1:"))
    rot1_file_rad = float(rot1_line.split(":", 1)[1])
    assert rot1_file_rad * 180.0 / math.pi == pytest.approx(
        refined["geometry"]["rot1_deg"], rel=1e-9,
    )
    assert "Rot2: 0.0" in text and "Rot3: 0.0" in text, text


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


# ---------------------------------------------------------------------------
# Seeded beam centre (ring fit, no internal standard) / 圆环拟合中心种子
# ---------------------------------------------------------------------------

#: Seed from a user's ring fit: 30 px right / 25 px down of the true centre, so
#: any (286, 281) result can only come from CONSUMING the seed — not from the
#: truth (256, 256) nor from guess_poni()'s ellipse estimate (≈256/258 px).
#: 用户圆环拟合种子：比真值右 30 px、下 25 px——结果出现 (286, 281) 只能说明
#: 种子确被消费，而非真值或 guess_poni() 椭圆估计（约 256/258 px）。
SEED_CENTER_X_PX = CENTER_X_PX + 30.0
SEED_CENTER_Y_PX = CENTER_Y_PX + 25.0


def test_setup_seeded_center_consumed(synthetic_edf: str):
    """setup 载荷里的 centerX/centerY（用户在圆环上点选拟合出的束流中心，
    无需内标）必须被消费为几何初值：

    1. 不带中心 → 响应 seededCenterPx 为 None、会话 center0 为 None；
    2. 带中心 → 响应回显该中心，会话 center0 以米制存储（poni1=y·pixel1、
       poni2=x·pixel2），且 update_peaks 构建的初值几何中心恰为种子
       （覆盖 guess_poni() 的椭圆估计——对照不带中心的会话，后者的初值
       中心来自椭圆拟合、约为真值中心）；
    3. 全参数固定的 refine 保持中心为种子值，证明种子一路进入返回几何；
       距离仍收敛到真值 3% 以内。

    The seeded centre is 30/25 px off the truth, so a (286, 281) result proves
    consumption of the seed rather than recovery of the truth.
    """
    from python.services import calibration as calib_module

    # -- 1) no seed: response echo + session are both None --------------------
    plain = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    plain_sid = plain["sessionId"]
    assert plain["seededCenterPx"] is None
    assert calib_module._SESSIONS[plain_sid]["center0"] is None

    # Unseeded first guess, for contrast: guess_poni()'s innermost-ring ellipse
    # fit — close to the TRUE centre, i.e. NOT the seed.
    # 无种子首猜作对照：guess_poni() 椭圆拟合——接近真值中心，绝非种子值。
    np.random.seed(RNG_SEED)
    plain_peaks = _ok(_run({"action": "detect_peaks", "sessionId": plain_sid}))["peaks"]
    _ok(_run({
        "action": "update_peaks", "sessionId": plain_sid,
        "peaks": [{"y": p["y"], "x": p["x"]} for p in plain_peaks],
    }))
    plain_gr = calib_module._SESSIONS[plain_sid]["gr"]
    plain_cx = plain_gr.poni2 / PIXEL_M
    plain_cy = plain_gr.poni1 / PIXEL_M
    assert abs(plain_cx - SEED_CENTER_X_PX) > 5.0, plain_cx
    assert abs(plain_cy - SEED_CENTER_Y_PX) > 5.0, plain_cy

    # -- 2) seeded setup: echoed back + stored in metres + seeds the guess ----
    seeded = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "calibrantName": CALIBRANT_NAME,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
        "centerX": SEED_CENTER_X_PX,
        "centerY": SEED_CENTER_Y_PX,
    }))
    sid = seeded["sessionId"]
    echo = seeded["seededCenterPx"]
    assert echo == {"x": SEED_CENTER_X_PX, "y": SEED_CENTER_Y_PX}, echo
    # poni1 runs along rows (y), poni2 along columns (x). / poni1 沿行、poni2 沿列。
    center0 = calib_module._SESSIONS[sid]["center0"]
    assert center0 == pytest.approx(
        (SEED_CENTER_Y_PX * PIXEL_M, SEED_CENTER_X_PX * PIXEL_M), rel=1e-9,
    )

    np.random.seed(RNG_SEED)
    peaks = _ok(_run({"action": "detect_peaks", "sessionId": sid}))["peaks"]
    assert len(peaks) >= 50, f"too few auto-picked peaks: {len(peaks)}"
    _ok(_run({
        "action": "update_peaks", "sessionId": sid,
        "peaks": [{"y": p["y"], "x": p["x"]} for p in peaks],
    }))
    # The seeded centre OVERRODE the ellipse estimate in the initial geometry.
    # 初值几何里种子中心已覆盖椭圆估计。
    gr = calib_module._SESSIONS[sid]["gr"]
    assert gr.poni2 / PIXEL_M == pytest.approx(SEED_CENTER_X_PX, abs=1e-9)
    assert gr.poni1 / PIXEL_M == pytest.approx(SEED_CENTER_Y_PX, abs=1e-9)

    # -- 3) all-fixed refine: the centre survives verbatim ---------------------
    # All seven parameters fixed → the returned geometry IS the initial one, so
    # the centre can only be (286, 281) if the seed really was consumed there.
    # 七参全固定 → 返回几何即初值几何：中心为 (286, 281) 只能源于种子确被
    # 消费为初值。（pyFAI 的 refine3 支持全固定，无报错，故无需退化为常规
    # free 精修路径。）
    pre_dist_mm = gr.dist * 1e3
    fixed = {
        "dist": False, "poni1": False, "poni2": False,
        "rot1": False, "rot2": False, "rot3": False, "wavelength": False,
    }
    refined = _ok(_run({
        "action": "refine", "sessionId": sid, "passes": 2, "free": fixed,
    }))
    geometry = refined["geometry"]
    assert geometry["center_x_px"] == pytest.approx(SEED_CENTER_X_PX, abs=1e-9), geometry
    assert geometry["center_y_px"] == pytest.approx(SEED_CENTER_Y_PX, abs=1e-9), geometry
    # The seed only overrides the centre: dist keeps its guess_poni() value.
    # 种子只覆盖中心：距离保持 guess_poni() 给出的值。
    assert geometry["dist_mm"] == pytest.approx(pre_dist_mm, rel=1e-9), geometry
    # And the verified centre is provably NOT the truth: the seed is 30/25 px
    # off, so recovering (286, 281) means consuming the seed.
    # 且该中心可证非真值：种子偏 30/25 px，得到 (286, 281) 即种子被消费。
    assert abs(geometry["center_x_px"] - CENTER_X_PX) > 5.0, geometry
    assert abs(geometry["center_y_px"] - CENTER_Y_PX) > 5.0, geometry
    # chi² is informational (None when pyFAI cannot compute it) — when present
    # it must be a real, non-negative number, not NaN/inf.
    # χ² 为信息性字段（pyFAI 算不出时可为 None）；存在时必须是有限非负实数。
    if refined["chi2"] is not None:
        assert math.isfinite(refined["chi2"]) and refined["chi2"] >= 0, refined["chi2"]


# ---------------------------------------------------------------------------
# Internal-standard mode / 内标定标模式
# ---------------------------------------------------------------------------

def _setup_internal(edf_path: str) -> str:
    """Setup WITHOUT any calibrant → internal-standard session.
    不带任何标样的 setup → 内标会话。"""
    return _ok(_run({
        "action": "setup",
        "filePath": edf_path,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))["sessionId"]


def _first_ring_tth_rad() -> float:
    """Ground-truth 2θ (radians) of LaB6's first ring at the test wavelength —
    the value ring_standard must recover from the ring geometry.
    测试波长下 LaB6 首环的真实 2θ（弧度）——ring_standard 必须从环几何恢复。"""
    import pyFAI.calibrant as calibrant_mod

    calibrant = calibrant_mod.get_calibrant(CALIBRANT_NAME)
    calibrant.wavelength = WAVELENGTH_M
    tth0 = calibrant.get_2th()[0]
    assert tth0 is not None
    return float(tth0)


def _assert_bilingual_error(result: dict) -> str:
    """Assert an _err payload carrying BOTH languages (EN + 中文 in one
    'EN / ZH' string). / 断言 _err 载荷双语齐备。"""
    assert result.get("status") == "error", result
    message = str(result.get("message") or "")
    assert " / " in message, message
    assert any("\u4e00" <= ch <= "\u9fff" for ch in message), message
    assert any(("a" <= ch.lower() <= "z") for ch in message), message
    return message


def test_setup_internal_mode(synthetic_edf: str):
    """No calibrant → an internal-standard session; the calibrant-dependent
    actions refuse it bilingually, detect_peaks still works.
    无标样 → 内标会话；依赖标样的动作双语拒绝，detect_peaks 仍可用。"""
    from python.services import calibration as calib_module

    # A calibrant setup is NOT internal mode (the flag tracks the mode).
    # 带标样的 setup 不是内标模式（标志跟随模式）。
    assert calib_module._SESSIONS[_setup_session(synthetic_edf)]["internal_standard"] is False

    setup = _ok(_run({
        "action": "setup",
        "filePath": synthetic_edf,
        "pixelSizeUm": PIXEL_UM,
        "wavelengthA": WAVELENGTH_A,
        "distGuessMm": DIST_MM,
    }))
    sid = setup["sessionId"]
    assert setup["calibrantName"] is None
    session = calib_module._SESSIONS[sid]
    assert session["internal_standard"] is True
    assert session["calibrant_name"] is None
    # The empty Calibrant() sentinel keeps direct session["calibrant"] consumers
    # (e.g. _build_refinement's constructor argument) from crashing.
    # 空 Calibrant() 哨兵保证直接读 session["calibrant"] 的路径不炸。
    assert session["calibrant"] is not None

    # Calibrant-dependent actions: bilingual refusal naming the mode.
    # 依赖标样的动作：双语拒绝并指明模式。
    for payload in (
        {"action": "update_peaks", "sessionId": sid, "peaks": [{"y": 10, "x": 10}]},
        {"action": "refine", "sessionId": sid},
        {"action": "ring_overlay", "sessionId": sid},
    ):
        message = _assert_bilingual_error(_run(payload))
        assert "internal-standard" in message, message
        assert "内标定标" in message, message

    # detect_peaks has no calibrant dependency — it must still run.
    # detect_peaks 不含标样依赖——必须照常可用。
    np.random.seed(RNG_SEED)
    detect = _ok(_run({"action": "detect_peaks", "sessionId": sid}))
    assert len(detect["peaks"]) >= 50, f"too few auto-picked peaks: {len(detect['peaks'])}"


def test_ring_standard_units(synthetic_edf: str):
    """One KNOWN ring (8 points on the true first ring) → full geometry, for
    every supported unit: centre (256, 256) ±1e-6, radius = truth, SD = 200 mm
    (rel 1e-6), 2θ recovered for the q/d/2θ variants (null for dist_mm).
    已知环（真值首环上 8 点）→ 完整几何：中心 (256,256)±1e-6、半径 = 真值、
    SD = 200 mm（rel 1e-6）；q/d/2θ 变体恢复 2θ（dist_mm 为 null）。"""
    sid = _setup_internal(synthetic_edf)
    r0 = _first_ring_radius_px()
    tth0 = _first_ring_tth_rad()
    points = _ring_guide_points(r0, [a * 45.0 for a in range(8)])

    # Truths converted from the ring's 2θ: q = 4π·sinθ/λ (SI metres).
    # 由环 2θ 换算的真值：q = 4π·sinθ/λ（SI 米制）。
    q_m = 4.0 * math.pi * math.sin(tth0 / 2.0) / WAVELENGTH_M
    cases = {
        "q_nm": q_m / 1e9,                       # nm⁻¹
        "q_A": q_m / 1e10,                       # Å⁻¹
        "d_A": (2.0 * math.pi / q_m) * 1e10,     # Å
        "d_nm": (2.0 * math.pi / q_m) * 1e9,     # nm
        "tth_deg": math.degrees(tth0),           # degrees
        "dist_mm": DIST_MM,                      # mm (direct)
    }
    for unit, value in cases.items():
        result = _ok(_run({
            "action": "ring_standard", "sessionId": sid, "points": points,
            "value": value, "unit": unit,
        }))
        assert result["centerXPx"] == pytest.approx(CENTER_X_PX, abs=1e-6), (unit, result)
        assert result["centerYPx"] == pytest.approx(CENTER_Y_PX, abs=1e-6), (unit, result)
        assert result["radiusPx"] == pytest.approx(r0, rel=1e-6), (unit, result)
        assert result["rmsPx"] is not None and result["rmsPx"] >= 0.0, (unit, result)
        assert result["distMm"] == pytest.approx(DIST_MM, rel=1e-6), (unit, result)
        assert result["unit"] == unit
        assert result["value"] == pytest.approx(value, rel=1e-12)
        assert result["internalStandard"] is True
        if unit == "dist_mm":
            # The distance was given directly — no ring 2θ to report.
            # 距离直给——没有可报的环 2θ。
            assert result["tthDeg"] is None
        else:
            assert result["tthDeg"] == pytest.approx(math.degrees(tth0), rel=1e-6), (unit, result)
        geometry = result["geometry"]
        assert geometry["dist_mm"] == pytest.approx(DIST_MM, rel=1e-6), (unit, geometry)
        assert geometry["center_x_px"] == pytest.approx(CENTER_X_PX, abs=1e-6), (unit, geometry)
        assert geometry["center_y_px"] == pytest.approx(CENTER_Y_PX, abs=1e-6), (unit, geometry)
        assert geometry["wavelength_A"] == pytest.approx(WAVELENGTH_A, rel=1e-9)
        # No tilt information in a single ring → rot stays exactly 0.
        # 单环不含倾角信息 → rot 严格为 0。
        assert geometry["rot1_deg"] == 0.0 and geometry["rot2_deg"] == 0.0
        assert geometry["rot3_deg"] == 0.0


def test_ring_standard_errors(synthetic_edf: str):
    """Every invalid ring_standard input is refused bilingually: fewer than 3
    finite points, unknown unit, value ≤ 0, sinθ > 1, 2θ ≥ 90°, and a
    non-physical distance (≤ 0.01 mm on the low rail, > 50 m on the high one).
    所有非法输入双语拒绝：有效点不足 3、未知单位、value ≤ 0、sinθ > 1、
    2θ ≥ 90°、距离非物理（下限 ≤ 0.01 mm、上限 > 50 m）。"""
    sid = _setup_internal(synthetic_edf)
    r0 = _first_ring_radius_px()
    points = _ring_guide_points(r0, [0.0, 45.0, 90.0, 135.0])

    bad_calls = [
        # < 3 finite points (a NaN coordinate does not count as a point).
        # 有效点不足 3（NaN 坐标不算点）。
        {"points": points[:2], "value": 1.0, "unit": "q_nm"},
        {"points": [points[0], points[1], {"y": float("nan"), "x": 10.0}],
         "value": 1.0, "unit": "q_nm"},
        # Unknown unit / 未知单位
        {"points": points, "value": 1.0, "unit": "furlong"},
        # value ≤ 0 / 数值 ≤ 0
        {"points": points, "value": 0.0, "unit": "q_nm"},
        # sinθ > 1: q·λ/(4π) beyond the reachable range.
        # sinθ > 1：q·λ/(4π) 超出可达范围。
        {"points": points, "value": 1e9, "unit": "q_A"},
        # 2θ ≥ 90° given directly / 直给 2θ ≥ 90°。
        {"points": points, "value": 90.0, "unit": "tth_deg"},
        # Non-physical distance: 0.001 mm ≤ 0.01 mm floor.
        # 非物理距离：0.001 mm ≤ 0.01 mm 下限。
        {"points": points, "value": 0.001, "unit": "dist_mm"},
        # …and the 50 m ceiling: 1e6 mm = 1000 m (a wrong unit scale).
        # ……以及 50 m 上限：1e6 mm = 1000 m（单位量级填错）。
        {"points": points, "value": 1e6, "unit": "dist_mm"},
    ]
    for extra in bad_calls:
        _assert_bilingual_error(_run({
            "action": "ring_standard", "sessionId": sid, **extra,
        }))


def test_ring_standard_export_and_preview(synthetic_edf: str, tmp_path: Path):
    """ring_standard's geometry is a first-class session geometry: export_poni
    writes it (read back with pyFAI's own PoniFile — dist / poni1 / poni2 /
    wavelength / rot=0) and integrate_preview consumes it (non-empty 1D/2D).
    ring_standard 的几何是一等公民：export_poni 落盘（用 pyFAI 自带 PoniFile
    读回 dist / poni1 / poni2 / wavelength / rot=0），integrate_preview 可用
    （1D/2D 非空）。"""
    sid = _setup_internal(synthetic_edf)
    r0 = _first_ring_radius_px()
    tth0 = _first_ring_tth_rad()
    q_m = 4.0 * math.pi * math.sin(tth0 / 2.0) / WAVELENGTH_M
    points = _ring_guide_points(r0, [a * 45.0 for a in range(8)])
    fitted = _ok(_run({
        "action": "ring_standard", "sessionId": sid, "points": points,
        "value": q_m / 1e9, "unit": "q_nm",
    }))

    poni_path = tmp_path / "internal_standard.poni"
    exported = _ok(_run({
        "action": "export_poni", "sessionId": sid, "savePath": str(poni_path),
    }))
    assert poni_path.is_file()
    assert exported["summary"]["dist_mm"] == pytest.approx(DIST_MM, rel=1e-6)
    assert exported["summary"]["dist_mm"] == pytest.approx(fitted["distMm"], rel=1e-12)

    from pyFAI.io.ponifile import PoniFile

    pf = PoniFile()
    pf.read_from_file(str(poni_path))
    assert pf.dist == pytest.approx(DIST_M, rel=1e-6)
    assert pf.poni1 == pytest.approx(CENTER_Y_PX * PIXEL_M, rel=1e-6)
    assert pf.poni2 == pytest.approx(CENTER_X_PX * PIXEL_M, rel=1e-6)
    assert pf.wavelength == pytest.approx(WAVELENGTH_M, rel=1e-6)
    assert pf.rot1 == 0.0 and pf.rot2 == 0.0 and pf.rot3 == 0.0

    preview = _ok(_run({"action": "integrate_preview", "sessionId": sid}))
    one, two = preview["1d"], preview["2d"]
    assert len(one["x"]) == 1024 and len(one["y"]) == 1024
    assert any(v is not None for v in one["y"]), "1-D preview must have data"
    assert two["nRad"] > 0 and two["nAzim"] > 0
    assert len(two["intensity"]) == two["nRad"] * two["nAzim"]
    assert any(v is not None for v in two["intensity"]), "2-D cake must have data"


def test_ring_standard_default_dist(synthetic_edf: str, tmp_path: Path):
    """ring_standard WITHOUT a value (user request): the centre still comes
    from the circle fit while the distance defaults to the initial guess
    (dist0 = 200 mm); the response flags ``distDefaulted`` and export_poni
    annotates the .poni with ``Dist-default``. A later valued run on the SAME
    session clears the flag and the annotation.
    不带 value 的 ring_standard（用户要求）：中心仍由圆拟合得出，距离取初始
    猜测（dist0 = 200 mm）；响应以 ``distDefaulted`` 标记，export_poni 在
    .poni 中写入 ``Dist-default`` 注释。同一会话随后带值重跑则标志与注释一并
    消失。"""
    from python.services import calibration as calib_module

    sid = _setup_internal(synthetic_edf)
    r0 = _first_ring_radius_px()
    points = _ring_guide_points(r0, [a * 45.0 for a in range(8)])

    # No value, no unit → the default-distance branch. The unit is skipped
    # entirely (a stale dropdown entry would be meaningless).
    # 无 value 无 unit → 默认距离分支。单位校验整体跳过（下拉残留无意义）。
    defaulted = _ok(_run({
        "action": "ring_standard", "sessionId": sid, "points": points,
    }))
    assert defaulted["distDefaulted"] is True
    assert defaulted["unit"] is None and defaulted["value"] is None
    assert defaulted["tthDeg"] is None
    # The distance is exactly the session's initial guess (dist0 = 200 mm),
    # the centre is the ground truth from the circle fit.
    # 距离恰为会话初始猜测（dist0 = 200 mm），中心为圆拟合得到的真值。
    assert defaulted["distMm"] == pytest.approx(DIST_MM, rel=1e-12)
    assert defaulted["centerXPx"] == pytest.approx(CENTER_X_PX, abs=1e-6)
    assert defaulted["centerYPx"] == pytest.approx(CENTER_Y_PX, abs=1e-6)
    assert calib_module._SESSIONS[sid]["ring_standard"]["dist_defaulted"] is True

    # The annotation lands in the exported .poni. ASCII probes only: the file
    # may be written in the locale encoding (GBK here), so decode lossily and
    # match ASCII substrings that survive any encoding.
    # 标注须出现在导出的 .poni 中。仅用 ASCII 探针：文件可能按本地编码
    # （此处 GBK）写出，故有损解码并匹配任意编码下都存活的 ASCII 子串。
    poni_defaulted = tmp_path / "defaulted.poni"
    _ok(_run({
        "action": "export_poni", "sessionId": sid, "savePath": str(poni_defaulted),
    }))
    assert "Dist-default" in poni_defaulted.read_text(encoding="utf-8", errors="replace")
    assert "200.0 mm" in poni_defaulted.read_text(encoding="utf-8", errors="replace")

    # A valued run on the SAME session restores the exact path: no flag, no
    # annotation. / 同一会话带值重跑恢复精确路径：无标志、无注释。
    tth0 = _first_ring_tth_rad()
    q_m = 4.0 * math.pi * math.sin(tth0 / 2.0) / WAVELENGTH_M
    valued = _ok(_run({
        "action": "ring_standard", "sessionId": sid, "points": points,
        "value": q_m / 1e9, "unit": "q_nm",
    }))
    assert valued["distDefaulted"] is False
    assert valued["distMm"] == pytest.approx(DIST_MM, rel=1e-6)
    assert calib_module._SESSIONS[sid]["ring_standard"]["dist_defaulted"] is False

    poni_valued = tmp_path / "valued.poni"
    _ok(_run({
        "action": "export_poni", "sessionId": sid, "savePath": str(poni_valued),
    }))
    assert "Dist-default" not in poni_valued.read_text(encoding="utf-8", errors="replace")
