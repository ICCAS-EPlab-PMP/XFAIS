#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_bg_ionchamber_continuous.py — Regression tests for the continuous-scan
ionchamber upgrade (2026-11-05 batch).

Covers the defects found with the 2026-11-03 SSRF test data (continuous
heating-series scans whose ionchamber files omit the detector segment and use
a ``BG-`` prefix, plus a shutter-closed warm-up segment):

    1. Detector-token normalization: data ``...-TEST-waxs-9.9s_00001`` must
       match ion ``...-TEST-9.9s_1`` at high priority (the old code compared
       the raw state fragments and never considered them equal).
    2. Nearest-number fallback: with fewer ionchamber files than data files,
       files without a same-number donor must take the CLOSEST-numbered
       donor, not silently the first same-state one.
    3. Time-window matching: high-confidence name pairs calibrate the
       constant clock offset between the ionchamber software and the
       detector; unplaced files then match by which recording window
       contains their calibrated acquisition time.
    4. Warm-up rejection: leading shutter-closed rows (orders of magnitude
       below the median) no longer bias mean / trimmed_mean.
    5. Dual-channel transmission formula
       T = (sample_after/sample_before) * (bg_before/bg_after) — corrected
       2026-11-06 (the 2026-11-04 first version was its reciprocal) — with
       truth recovery, same-channel rejection and a <100% sanity bound.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure BETA/python is on sys.path so service_launcher can import `services.*`
_PYTHON_DIR = str(Path(__file__).resolve().parent.parent)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

import numpy as np
import pandas as pd
import pytest

from python.services.bg_subtractor import (
    _calc_ion_intensity,
    calc_transmission,
    calc_transmission_dual,
    match_ionchamber,
    parse_ionchamber_file,
)


# ---------------------------------------------------------------------------
# Helpers / 辅助
# ---------------------------------------------------------------------------

_ION_HEADER = "# Time  Ionchamber0  Ionchamber1  Ionchamber2"


def _write_ion_file(
    path: Path,
    start: str,
    n_rows: int = 5,
    period_s: float = 1.0,
    values=(("1.0e-7", "9.0e-8", "1.0e-5"),),
) -> None:
    """Write an ionchamber text file with ``n_rows`` rows from ``start``."""
    from datetime import datetime, timedelta

    t = datetime.strptime(start[:19], "%Y-%m-%d %H:%M:%S")
    lines = [_ION_HEADER]
    for i in range(n_rows):
        stamp = (t + timedelta(seconds=i * period_s)).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        vals = values[i % len(values)]
        lines.append(f"{stamp}.130671238  {vals[0]}  {vals[1]}  {vals[2]}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_tiff_like(path: Path, acq_time: str) -> None:
    """Write a minimal binary file whose header carries a Pilatus-style
    ASCII acquisition time (the reader scans the first 8 KB only)."""
    header = (
        b"II*\x00 TVX TIFF v 1.3\n"
        + f"{acq_time}\n".encode("ascii")
        + b"# Pixel_size 172e-6 m x 172e-6 m\n"
        + b"# Exposure_time 9.9000000 s\n"
    )
    path.write_bytes(header + b"\x00" * 256)


# ---------------------------------------------------------------------------
# 1. Detector-token normalization / 探测器段归一化
# ---------------------------------------------------------------------------


class TestDetectorTokenNormalization:
    def test_missing_waxs_segment_matches_high(self) -> None:
        # Real 2026-11-03 naming: ion file omits the "waxs" segment entirely.
        data = ["DADT-1ST-HEATING-10-180-TEST-waxs-9.9s_00001.tif"]
        ions = ["DADT-1ST-HEATING-10-180-TEST-9.9s_1.Ionchamber"]
        result = match_ionchamber(data, ions)
        assert result[0]["matched_ion"] == ions[0]
        # base_state (priority 2) instead of a fuzzy/base-only fallback.
        assert result[0]["method"] == "base_state"
        assert result[0]["score"] >= 0.95

    def test_bg_prefix_pair_matches_high(self) -> None:
        data = ["BG-10S-waxs-9.9s_00001.tif"]
        ions = ["BG-10S-9.9s_1.Ionchamber"]
        result = match_ionchamber(data, ions)
        assert result[0]["matched_ion"] == ions[0]
        assert result[0]["method"] == "base_state"
        assert result[0]["score"] >= 0.95

    def test_normalization_does_not_cross_match_bases(self) -> None:
        # The detector segment must be the ONLY loose part — different bases
        # still never match each other.
        data = ["DADT-1ST-HEATING-waxs-9.9s_00001.tif"]
        ions = ["OTHER-1ST-HEATING-9.9s_1.Ionchamber"]
        result = match_ionchamber(data, ions)
        assert result[0]["method"] != "base_state"


# ---------------------------------------------------------------------------
# 2. Nearest-number fallback / 最近编号兜底
# ---------------------------------------------------------------------------


class TestNearestNumberFallback:
    def test_extra_files_take_closest_number(self) -> None:
        # 6 data files, 3 ionchamber files with genuinely different state
        # fragments — priority 2 (same state) cannot absorb the extras, so
        # same-number files go through priority 3 and the rest through 3b.
        data = [f"SCAN-red_0000{i}.tif" for i in range(1, 7)]
        ions = [f"SCAN-blue_{i}.Ionchamber" for i in (1, 2, 3)]
        result = match_ionchamber(data, ions)
        by_data = {r["data_file"]: r for r in result}
        # Same-number files keep priority 3 (their state differs, so the
        # score sits at the 0.80 floor).
        assert by_data[data[0]]["method"] == "base_num_best_state"
        assert by_data[data[0]]["matched_ion"] == ions[0]
        assert by_data[data[1]]["matched_ion"] == ions[1]
        assert by_data[data[2]]["matched_ion"] == ions[2]
        # Extras take the CLOSEST number, not the first in list order.
        assert by_data[data[3]]["method"] == "base_num_nearest"
        assert by_data[data[3]]["matched_ion"] == ions[2]  # |3-4| = 1
        assert by_data[data[4]]["matched_ion"] == ions[2]  # |3-5| = 2 < |2-5| = 3
        assert by_data[data[5]]["matched_ion"] == ions[2]
        # Nearest-number rows score below the trusted band (UI warning).
        assert by_data[data[3]]["score"] < 0.8

    def test_closest_number_tiebreak_prefers_similar_state(self) -> None:
        data = ["SCAN-serie1_00004.tif"]
        ions = ["SCAN-serieA_3.Ionchamber", "SCAN-serie1_5.Ionchamber"]
        result = match_ionchamber(data, ions)
        # |3-4| == |5-4| — the state-similar donor wins the tiebreak.
        assert result[0]["matched_ion"] == ions[1]


# ---------------------------------------------------------------------------
# 3. Time-window matching / 时间窗匹配
# ---------------------------------------------------------------------------


class TestTimeWindowMatching:
    def test_unplaced_file_matches_by_calibrated_time(self, tmp_path: Path) -> None:
        # Two confident pairs calibrate the clock offset (ionchamber clock
        # runs ~1h05m ahead of the detector, as on 2026-11-03).
        img_a = tmp_path / "DADT-1ST-HEATING-10-180-TEST-waxs-9.9s_00001.tif"
        img_b = tmp_path / "BG-10S-waxs-9.9s_00001.tif"
        img_c = tmp_path / "UNRELATED-SCAN_00009.tif"
        _write_tiff_like(img_a, "2026:11:03 01:57:13")
        _write_tiff_like(img_b, "2026:11:03 04:46:47")
        # C was acquired inside ionchamber A's recording window
        # (03:02:56 + offset 1:05:45 → detector ~01:57:11..01:57:47).
        _write_tiff_like(img_c, "2026:11:03 01:57:30")

        ion_a = tmp_path / "DADT-1ST-HEATING-10-180-TEST-9.9s_1.Ionchamber"
        ion_b = tmp_path / "BG-10S-9.9s_1.Ionchamber"
        _write_ion_file(ion_a, "2026-11-03 03:02:56", n_rows=36)
        _write_ion_file(ion_b, "2026-11-03 05:52:32", n_rows=26)

        result = match_ionchamber([str(img_a), str(img_b), str(img_c)],
                                  [str(ion_a), str(ion_b)])
        by_data = {r["data_file"]: r for r in result}
        # Confident pairs keep their name matches.
        assert by_data[str(img_a)]["method"] == "base_state"
        assert by_data[str(img_b)]["method"] == "base_state"
        # The unplaced file is recovered by time, not by fuzzy guesswork.
        assert by_data[str(img_c)]["method"] == "time_window"
        assert by_data[str(img_c)]["matched_ion"] == str(ion_a)
        assert by_data[str(img_c)]["score"] == pytest.approx(0.85)

    def test_no_confident_pair_skips_time_window(self, tmp_path: Path) -> None:
        # Without any high-confidence pair there is no calibration, so the
        # old name-based result must survive untouched.
        img = tmp_path / "ZZZ-scan_00001.tif"
        _write_tiff_like(img, "2026:11:03 01:57:13")
        ion = tmp_path / "QQQ-other_1.Ionchamber"
        _write_ion_file(ion, "2026-11-03 03:02:56", n_rows=5)
        result = match_ionchamber([str(img)], [str(ion)])
        assert result[0]["method"] != "time_window"

    def test_unparsable_ion_file_is_not_a_window(self, tmp_path: Path) -> None:
        # A stray report .txt (no timestamps) must never become a window
        # donor nor a calibration pair.
        img_a = tmp_path / "SCAN-serie1_00001.tif"
        img_c = tmp_path / "ZZZ-scan_00009.tif"
        _write_tiff_like(img_a, "2026:11:03 01:57:13")
        _write_tiff_like(img_c, "2026:11:03 01:57:30")
        (tmp_path / "report.txt").write_text("no timestamps here\n")
        result = match_ionchamber([str(img_a), str(img_c)],
                                  [str(tmp_path / "report.txt")])
        by_data = {r["data_file"]: r for r in result}
        assert by_data[str(img_c)]["method"] != "time_window"


# ---------------------------------------------------------------------------
# 4. Warm-up rejection / 预热段剔除
# ---------------------------------------------------------------------------


class TestWarmupRejection:
    def _df(self) -> pd.DataFrame:
        # 4 shutter-closed rows (~1e-11) then 10 open-shutter rows (~1e-5).
        vals = [3.3e-11] * 4 + [1.065e-5] * 10
        return pd.DataFrame({
            "Time": [f"2026-11-03 03:02:{56 + i:02d}" for i in range(14)],
            "Ionchamber0": vals,
            "Ionchamber1": [4.7e-8] * 14,
            "Ionchamber2": vals,
        })

    def test_mean_no_longer_biased(self) -> None:
        df = self._df()
        raw_mean = float(np.mean(df["Ionchamber0"].to_numpy(dtype=float)))
        clean = _calc_ion_intensity(df, "Ionchamber0", "mean")
        # Without rejection the mean sits ~29% below the true level.
        assert raw_mean < 8e-6
        assert clean == pytest.approx(1.065e-5, rel=1e-9)

    def test_trimmed_mean_no_longer_biased(self) -> None:
        df = self._df()
        clean = _calc_ion_intensity(df, "Ionchamber0", "trimmed_mean")
        assert clean == pytest.approx(1.065e-5, rel=1e-9)

    def test_median_unchanged(self) -> None:
        df = self._df()
        assert _calc_ion_intensity(df, "Ionchamber0", "median") == \
            pytest.approx(1.065e-5, rel=1e-9)

    def test_warmup_never_eats_majority(self) -> None:
        # If MOST rows are low (a genuinely dark channel), nothing is dropped.
        vals = [3.3e-11] * 10 + [1.065e-5] * 4
        df = pd.DataFrame({
            "Time": [f"2026-11-03 03:02:{56 + i:02d}" for i in range(14)],
            "Ionchamber0": vals,
            "Ionchamber1": [4.7e-8] * 14,
            "Ionchamber2": [0.0] * 14,
        })
        assert _calc_ion_intensity(df, "Ionchamber0", "mean") == \
            pytest.approx(float(np.mean(vals)))

    def test_transmission_with_warmup_matches_clean(self) -> None:
        # End to end: a warm-up segment must not change the transmission.
        clean = pd.DataFrame({
            "Time": ["2026-11-03 03:02:56"] * 10,
            "Ionchamber0": [1.065e-5] * 10,
            "Ionchamber1": [4.7e-8] * 10,
            "Ionchamber2": [1.065e-5] * 10,
        })
        warm = pd.DataFrame({
            "Time": ["2026-11-03 03:02:56"] * 14,
            "Ionchamber0": [3.3e-11] * 4 + [1.065e-5] * 10,
            "Ionchamber1": [4.7e-8] * 14,
            "Ionchamber2": [3.3e-11] * 4 + [1.065e-5] * 10,
        })
        bg = pd.DataFrame({
            "Time": ["2026-11-03 05:52:32"] * 10,
            "Ionchamber0": [1.04e-5] * 10,
            "Ionchamber1": [4.7e-8] * 10,
            "Ionchamber2": [1.04e-5] * 10,
        })
        assert calc_transmission(warm, bg, "Ionchamber0", "mean") == \
            pytest.approx(calc_transmission(clean, bg, "Ionchamber0", "mean"),
                          rel=1e-9)


# ---------------------------------------------------------------------------
# 5. Dual-channel transmission / 前后通道透射公式
# ---------------------------------------------------------------------------


class TestCalcTransmissionDual:
    def _df(self, before: float, after: float, n_rows: int = 8) -> pd.DataFrame:
        return pd.DataFrame({
            "Time": [f"2026-11-03 03:02:{56 + i:02d}" for i in range(n_rows)],
            "Ionchamber0": [before] * n_rows,
            "Ionchamber1": [after] * n_rows,
            "Ionchamber2": [1.0e-5] * n_rows,
        })

    def test_formula_truth_recovery(self) -> None:
        sample = self._df(1.0e-7, 5.0e-8)   # sample absorbs half → 0.5
        bg = self._df(1.0e-7, 9.0e-8)       # bg_before/bg_after = 1/0.9
        t = calc_transmission_dual(
            sample, bg,
            sample_before="Ionchamber0", sample_after="Ionchamber1",
            bg_before="Ionchamber0", bg_after="Ionchamber1",
        )
        # T = (sample_after/sample_before) * (bg_before/bg_after) = 0.5/0.9
        # (corrected 2026-11-06; the 2026-11-04 first version returned the
        # reciprocal 1.8 and read as ">100%").
        # 公式修正回归：0.5 × (1/0.9) ≈ 0.5556，且必须小于 1。
        assert t == pytest.approx(0.5 / 0.9, rel=1e-9)
        assert t < 1.0

    def test_warmup_rows_do_not_shift_dual_result(self) -> None:
        # 12 rows with a 4-row warm-up segment: the guard drops leading low
        # rows only when they are strictly fewer than half (4 < 6 here).
        sample = self._df(1.0e-7, 5.0e-8)
        bg = self._df(1.0e-7, 9.0e-8, n_rows=12)
        # Inject a warm-up segment into the bg "before" channel.
        bg_warm = bg.copy()
        bg_warm.loc[0:3, "Ionchamber0"] = 3.3e-11
        t_clean = calc_transmission_dual(
            sample, bg,
            sample_before="Ionchamber0", sample_after="Ionchamber1",
            bg_before="Ionchamber0", bg_after="Ionchamber1", method="mean",
        )
        t_warm = calc_transmission_dual(
            sample, bg_warm,
            sample_before="Ionchamber0", sample_after="Ionchamber1",
            bg_before="Ionchamber0", bg_after="Ionchamber1", method="mean",
        )
        assert t_warm == pytest.approx(t_clean, rel=1e-9)

    def test_same_sample_channels_rejected(self) -> None:
        sample = self._df(1.0e-7, 5.0e-8)
        bg = self._df(1.0e-7, 9.0e-8)
        with pytest.raises(ValueError, match="must differ"):
            calc_transmission_dual(
                sample, bg,
                sample_before="Ionchamber0", sample_after="Ionchamber0",
                bg_before="Ionchamber0", bg_after="Ionchamber1",
            )

    def test_same_bg_channels_rejected(self) -> None:
        sample = self._df(1.0e-7, 5.0e-8)
        bg = self._df(1.0e-7, 9.0e-8)
        with pytest.raises(ValueError, match="must differ"):
            calc_transmission_dual(
                sample, bg,
                sample_before="Ionchamber0", sample_after="Ionchamber1",
                bg_before="Ionchamber2", bg_after="Ionchamber2",
            )

    def test_missing_channel_rejected(self) -> None:
        sample = self._df(1.0e-7, 5.0e-8)
        bg = self._df(1.0e-7, 9.0e-8)
        with pytest.raises(ValueError, match="Cannot compute ion intensity"):
            calc_transmission_dual(
                sample, bg,
                sample_before="Ionchamber0", sample_after="Ionchamber9",
                bg_before="Ionchamber0", bg_after="Ionchamber1",
            )

    def test_real_files_single_channel_baseline(self) -> None:
        # The 2026-11-03 real pair: single-channel T must stay at the
        # documented value (guards against accidental formula changes).
        real_dir = Path(
            r"C:\Users\mamam\xwechat_files\ma96yi_91f8\msg\file\2026-11"
        )
        ion_s = real_dir / "DADT-1ST-HEATING-10-180-TEST-9.9s_1.Ionchamber"
        ion_b = real_dir / "BG-10S-9.9s_1.Ionchamber"
        if not (ion_s.is_file() and ion_b.is_file()):
            pytest.skip("real 2026-11-03 ionchamber files not on this machine")
        s_df = parse_ionchamber_file(str(ion_s))
        b_df = parse_ionchamber_file(str(ion_b))
        assert s_df is not None and b_df is not None
        t = calc_transmission(s_df, b_df, "Ionchamber0", "median")
        assert t == pytest.approx(1.0254, abs=1e-3)
