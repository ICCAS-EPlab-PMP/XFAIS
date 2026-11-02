#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_transmission.py — Tests for the direct-beam transmission service.

Covers:
    Group A: region_pixel_sum (rect / poly integration, clipping, NaN, border)
    Group B: compute_transmission_rows (ratios, reference validation)
    Group C: CSV / JSON export + parse round-trips (BOM, Chinese names)
    Group D: match_transmission_entries (basename, case, duplicates)
    Group E: _merge_payload_transmissions (batch payload merge)

Library-level only — handlers / asyncio are not exercised here; the
validated-output-path wiring is covered by the handler tests elsewhere.
本文件只做纯库级测试（不测 handler/asyncio）：区域积分、透过率比值、导出/
解析往返、按文件名匹配，以及批量载荷的透过率合并。
"""

import json
import os

import numpy as np
import pytest

from python.services.transmission import (
    compute_transmission_rows,
    export_transmission_csv,
    export_transmission_json,
    match_transmission_entries,
    parse_transmission_file,
    region_pixel_sum,
    validate_region,
)
from python.service_launcher import _merge_payload_transmissions


# ---------------------------------------------------------------------------
# Group A: region_pixel_sum — full integration semantics
# ---------------------------------------------------------------------------


class TestRegionPixelSum:
    def test_rect_sum_and_stats(self):
        """rect: 2×3 block of the 0..24 ramp sums to 6+7+8+11+12+13 = 57."""
        data = np.arange(25, dtype=np.float64).reshape(5, 5)
        result = region_pixel_sum(
            data, {"kind": "rect", "y0": 1, "y1": 3, "x0": 1, "x1": 4},
        )
        assert result["total"] == pytest.approx(57.0)
        assert result["pixel_count"] == 6
        assert result["mean"] == pytest.approx(9.5)
        assert result["bg_level"] is None

    def test_rect_clipped_into_image(self):
        """Out-of-image corners are clipped: rows/cols 0..1 → 0+1+5+6 = 12."""
        data = np.arange(25, dtype=np.float64).reshape(5, 5)
        result = region_pixel_sum(
            data, {"kind": "rect", "y0": -10, "y1": 2, "x0": -10, "x1": 2},
        )
        assert result["total"] == pytest.approx(12.0)
        assert result["pixel_count"] == 4

    def test_polygon_triangle_dicts_and_lists(self):
        """Triangle (0,0)-(0,6)-(6,0) covers 6+5+4+3+2+1 = 21 pixels.

        Hand-computed on the 0..35 ramp: 15+40+54+57+49+30 = 245 — and the
        dict / list vertex spellings must agree pixel for pixel.
        """
        ramp = np.arange(36, dtype=np.float64).reshape(6, 6)
        ones = np.ones((6, 6), dtype=np.float64)
        dict_points = {"kind": "poly", "points": [
            {"y": 0, "x": 0}, {"y": 0, "x": 6}, {"y": 6, "x": 0},
        ]}
        list_points = {"kind": "poly", "points": [[0, 0], [0, 6], [6, 0]]}

        assert region_pixel_sum(ones, dict_points)["total"] == pytest.approx(21.0)
        result = region_pixel_sum(ramp, list_points)
        assert result["total"] == pytest.approx(245.0)
        assert result["pixel_count"] == 21

    def test_empty_region_raises(self):
        """A rect entirely outside the image has no pixel → ValueError."""
        data = np.ones((5, 5), dtype=np.float64)
        with pytest.raises(ValueError, match="outside the image"):
            region_pixel_sum(
                data, {"kind": "rect", "y0": 10, "y1": 12, "x0": 10, "x1": 12},
            )

    def test_polygon_outside_image_raises(self):
        """A polygon whose rasterization misses every pixel → ValueError."""
        data = np.ones((5, 5), dtype=np.float64)
        with pytest.raises(ValueError, match="outside the image"):
            region_pixel_sum(
                data,
                {"kind": "poly", "points": [[10, 10], [10, 12], [12, 10]]},
            )

    def test_nan_pixels_contribute_zero(self):
        """NaN inside the ROI is treated as 0 (integral stays finite)."""
        data = np.array([[1.0, np.nan], [3.0, 4.0]], dtype=np.float64)
        result = region_pixel_sum(
            data, {"kind": "rect", "y0": 0, "y1": 2, "x0": 0, "x1": 2},
        )
        assert result["total"] == pytest.approx(8.0)
        assert result["pixel_count"] == 4

    def test_rect_border_subtraction_removes_flat_background(self):
        """Constant 100 background + 4×4 block at 200 → total = 16 × 100."""
        data = np.full((20, 20), 100.0)
        data[8:12, 8:12] = 200.0
        result = region_pixel_sum(
            data,
            {"kind": "rect", "y0": 0, "y1": 20, "x0": 0, "x1": 20},
            subtract_border=True,
        )
        assert result["bg_level"] == pytest.approx(100.0)
        assert result["total"] == pytest.approx(1600.0)
        assert result["pixel_count"] == 400
        assert result["mean"] == pytest.approx(4.0)

    def test_polygon_border_subtraction_removes_flat_background(self):
        """Same physics with a full-frame polygon: the mask edge is the border."""
        data = np.full((20, 20), 100.0)
        data[8:12, 8:12] = 200.0
        result = region_pixel_sum(
            data,
            {"kind": "poly", "points": [(0, 0), (0, 20), (20, 20), (20, 0)]},
            subtract_border=True,
        )
        assert result["bg_level"] == pytest.approx(100.0)
        assert result["total"] == pytest.approx(1600.0)

    def test_border_subtraction_clips_negative_contributions(self):
        """Pixels dimmer than the border median are clipped at 0, never negative."""
        data = np.full((10, 10), 100.0)
        data[4:6, 4:6] = 50.0  # dimmer than the border → clipped to zero
        result = region_pixel_sum(
            data,
            {"kind": "rect", "y0": 0, "y1": 10, "x0": 0, "x1": 10},
            subtract_border=True,
        )
        assert result["total"] == pytest.approx(0.0)
        assert result["total"] >= 0.0

    def test_negative_integral_raises(self):
        """A region made only of negative values cannot be an intensity."""
        data = np.full((4, 4), -5.0)
        with pytest.raises(ValueError, match="not a valid intensity"):
            region_pixel_sum(
                data, {"kind": "rect", "y0": 0, "y1": 4, "x0": 0, "x1": 4},
            )

    def test_flat_region_raises(self):
        data = np.ones((4, 4), dtype=np.float64)
        with pytest.raises(ValueError, match="needs ≥1 pixel"):
            region_pixel_sum(
                data, {"kind": "rect", "y0": 2, "y1": 2, "x0": 0, "x1": 2},
            )

    def test_unknown_region_kind_raises(self):
        with pytest.raises(ValueError, match="Unknown region kind"):
            validate_region({"kind": "circle", "r": 3})

    def test_polygon_needs_three_vertices(self):
        with pytest.raises(ValueError, match="at least 3 vertices"):
            validate_region({"kind": "poly", "points": [[0, 0], [1, 1]]})

    def test_rect_requires_four_corners(self):
        with pytest.raises(ValueError, match="y0/y1/x0/x1"):
            validate_region({"kind": "rect", "y0": 0, "y1": 5, "x0": 0})


# ---------------------------------------------------------------------------
# Group B: compute_transmission_rows
# ---------------------------------------------------------------------------


class TestComputeTransmissionRows:
    def _rows(self):
        return [
            {"file": "C:/data/ref.edf", "intensity": 200.0, "pixel_count": 9},
            {"file": "C:/data/sample_a.edf", "intensity": 100.0},
            {"file": "C:/data/sample_b.edf", "intensity": 50.0},
        ]

    def test_ratio_and_reference_row(self):
        rows = self._rows()
        out = compute_transmission_rows(rows, "C:/data/ref.edf")
        assert [row["transmission"] for row in out] == [1.0, 0.5, 0.25]
        # Extra keys survive; the input list is untouched.
        assert out[0]["pixel_count"] == 9
        assert all("transmission" not in row for row in rows)

    @pytest.mark.skipif(
        os.path.normcase("A") != "a", reason="normcase is case-sensitive here",
    )
    def test_reference_matched_by_normcase_path(self):
        out = compute_transmission_rows(self._rows(), "c:/DATA/ref.edf")
        assert out[0]["transmission"] == 1.0

    def test_reference_missing_raises(self):
        with pytest.raises(ValueError, match="not among the integrated rows"):
            compute_transmission_rows(self._rows(), "C:/data/missing.edf")

    def test_zero_reference_intensity_raises(self):
        rows = [
            {"file": "ref.edf", "intensity": 0.0},
            {"file": "sample.edf", "intensity": 10.0},
        ]
        with pytest.raises(ValueError, match="finite positive"):
            compute_transmission_rows(rows, "ref.edf")

    def test_nonfinite_reference_intensity_raises(self):
        rows = [
            {"file": "ref.edf", "intensity": float("nan")},
            {"file": "sample.edf", "intensity": 10.0},
        ]
        with pytest.raises(ValueError, match="finite positive"):
            compute_transmission_rows(rows, "ref.edf")

    def test_nonfinite_row_intensity_raises(self):
        rows = [
            {"file": "ref.edf", "intensity": 10.0},
            {"file": "sample.edf", "intensity": float("inf")},
        ]
        with pytest.raises(ValueError, match="no finite intensity"):
            compute_transmission_rows(rows, "ref.edf")


# ---------------------------------------------------------------------------
# Group C: export / parse round-trips
# ---------------------------------------------------------------------------


class TestTransmissionFiles:
    def _rows(self):
        return [
            {"file": "直通光_ref.edf", "intensity": 1234.5, "transmission": 1.0},
            {"file": "样品_A.edf", "intensity": 617.25, "transmission": 0.5},
        ]

    def test_csv_roundtrip_with_bom_and_chinese_names(self, tmp_path):
        path = tmp_path / "transmission.csv"
        written = export_transmission_csv(self._rows(), str(path))
        assert os.path.isfile(written)

        raw = path.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")  # Excel-friendly BOM

        entries = parse_transmission_file(str(path))
        assert [e["file"] for e in entries] == ["直通光_ref.edf", "样品_A.edf"]
        assert entries[0]["intensity"] == pytest.approx(1234.5)
        assert entries[1]["transmission"] == pytest.approx(0.5)

    def test_export_writes_basenames_not_session_paths(self, tmp_path):
        # Web uploads land in a server session dir; the exported file column
        # must be the portable basename (2026-10-25 same-session re-import
        # fix). / web 上传落在服务器会话目录；导出 file 列必须是可移植的
        # 纯文件名（2026-10-25 同会话再导入修复）。
        rows = [
            {
                "file": r"C:\srv\xfais_session_x\direct.edf",
                "intensity": 100.0,
                "transmission": 1.0,
            },
            {
                "file": r"C:\srv\xfais_session_x\sample.edf",
                "intensity": 60.0,
                "transmission": 0.6,
            },
        ]
        csv_path = tmp_path / "transmission.csv"
        export_transmission_csv(rows, str(csv_path))
        entries = parse_transmission_file(str(csv_path))
        assert [e["file"] for e in entries] == ["direct.edf", "sample.edf"]

        json_path = tmp_path / "transmission.json"
        export_transmission_json(rows, str(json_path))
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert [e["file"] for e in payload] == ["direct.edf", "sample.edf"]

    def test_json_roundtrip_and_no_intensity(self, tmp_path):
        path = tmp_path / "transmission.json"
        export_transmission_json(self._rows(), str(path))

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload == [
            {"file": "直通光_ref.edf", "transmission": 1.0},
            {"file": "样品_A.edf", "transmission": 0.5},
        ]
        entries = parse_transmission_file(str(path))
        assert entries[1]["transmission"] == pytest.approx(0.5)
        assert entries[1]["intensity"] is None

    def test_json_wrapped_files_object(self, tmp_path):
        path = tmp_path / "wrapped.json"
        path.write_text(
            json.dumps({"files": [{"file": "a.edf", "transmission": 0.25}]}),
            encoding="utf-8",
        )
        entries = parse_transmission_file(str(path))
        assert entries == [{"file": "a.edf", "intensity": None, "transmission": 0.25}]

    def test_json_detected_from_content(self, tmp_path):
        path = tmp_path / "mislabeled.csv"
        path.write_text('[{"file": "a.edf", "transmission": 0.5}]', encoding="utf-8")
        entries = parse_transmission_file(str(path))
        assert entries[0]["transmission"] == pytest.approx(0.5)

    def test_csv_missing_transmission_column_raises(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("file,intensity\na.edf,10\n", encoding="utf-8")
        with pytest.raises(ValueError, match="transmission"):
            parse_transmission_file(str(path))

    def test_csv_missing_value_names_the_file(self, tmp_path):
        path = tmp_path / "bad.csv"
        path.write_text("file,intensity,transmission\na.edf,10,\n", encoding="utf-8")
        with pytest.raises(ValueError, match="a.edf"):
            parse_transmission_file(str(path))

    def test_csv_header_tolerates_case_and_spaces(self, tmp_path):
        path = tmp_path / "t.csv"
        path.write_text(" File , Transmission \na.edf,0.5\n", encoding="utf-8")
        entries = parse_transmission_file(str(path))
        assert entries[0]["file"] == "a.edf"
        assert entries[0]["transmission"] == pytest.approx(0.5)

    def test_csv_gbk_fallback(self, tmp_path):
        path = tmp_path / "gbk.csv"
        path.write_bytes("file,intensity,transmission\n直通光.edf,10,1.0\n".encode("gbk"))
        entries = parse_transmission_file(str(path))
        assert entries[0]["file"] == "直通光.edf"

    def test_parse_missing_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            parse_transmission_file(str(tmp_path / "nope.csv"))

    def test_parse_empty_file_raises(self, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            parse_transmission_file(str(path))

    def test_parse_invalid_json_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not json at all", encoding="utf-8")
        with pytest.raises(ValueError, match="JSON"):
            parse_transmission_file(str(path))

    def test_parse_json_missing_transmission_raises(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text('[{"file": "a.edf"}]', encoding="utf-8")
        with pytest.raises(ValueError, match="a.edf"):
            parse_transmission_file(str(path))

    def test_export_rejects_missing_transmission(self, tmp_path):
        path = tmp_path / "transmission.csv"
        with pytest.raises(ValueError, match="no finite transmission"):
            export_transmission_csv(
                [{"file": "a.edf", "intensity": 1.0}], str(path),
            )


# ---------------------------------------------------------------------------
# Group D: match_transmission_entries
# ---------------------------------------------------------------------------


class TestMatchTransmissionEntries:
    def test_exact_basename_match(self):
        entries = [
            {"file": "D:/ref/ref.edf", "intensity": None, "transmission": 1.0},
            {"file": "D:/ref/sample.edf", "intensity": None, "transmission": 0.4},
        ]
        matches = match_transmission_entries(
            ["C:/data/ref.edf", "C:/data/sample.edf"], entries,
        )
        assert [m["transmission"] for m in matches] == [1.0, 0.4]
        assert matches[0]["matched_file"] == "D:/ref/ref.edf"
        assert matches[0]["note"] == ""

    def test_unmatched_entry_has_note(self):
        matches = match_transmission_entries(
            ["C:/data/other.edf"], [{"file": "ref.edf", "transmission": 1.0}],
        )
        assert matches[0]["transmission"] is None
        assert matches[0]["matched_file"] == ""
        assert "未在透过率文件中找到匹配" in matches[0]["note"]

    def test_empty_entries_mark_everything_unmatched(self):
        matches = match_transmission_entries(["a.edf", "b.edf"], [])
        assert len(matches) == 2
        assert all(m["transmission"] is None for m in matches)

    @pytest.mark.skipif(
        os.path.normcase("A") != "a", reason="normcase is case-sensitive here",
    )
    def test_case_insensitive_on_windows(self):
        entries = [{"file": "C:/Data/SAMPLE.EDF", "transmission": 0.75}]
        matches = match_transmission_entries(["c:/data/sample.edf"], entries)
        assert matches[0]["transmission"] == pytest.approx(0.75)

    def test_duplicate_basename_uses_first_and_notes_it(self):
        entries = [
            {"file": "D:/one/sample.edf", "transmission": 0.3},
            {"file": "D:/two/sample.edf", "transmission": 0.9},
        ]
        matches = match_transmission_entries(["D:/data/sample.edf"], entries)
        assert matches[0]["transmission"] == pytest.approx(0.3)
        assert matches[0]["matched_file"] == "D:/one/sample.edf"
        assert "已取第一个" in matches[0]["note"]

    def test_reuploaded_data_file_matches_via_conflict_suffix(self):
        # Same-session re-upload renames direct.edf → direct_1.edf on the
        # DATA side; the CSV still says direct.edf. The loose pass must find
        # it and flag the fuzzy hit in the note.
        # 同会话重传把 direct.edf 改名为 direct_1.edf（数据侧），CSV 里仍是
        # direct.edf——宽松匹配应命中并在 note 中标注。
        entries = [{"file": "direct.edf", "transmission": 1.0}]
        matches = match_transmission_entries(
            [r"C:\srv\session2\direct_1.edf"], entries,
        )
        assert matches[0]["transmission"] == pytest.approx(1.0)
        assert matches[0]["matched_file"] == "direct.edf"
        assert "_N" in matches[0]["note"]

    def test_reuploaded_entry_side_matches_via_conflict_suffix(self):
        # Reverse direction: the CSV was exported AFTER a re-upload (entries
        # carry the _1 names), then imported into a fresh session where the
        # files have their original names.
        # 反方向：CSV 在重传之后导出（条目带 _1 名），导入到全新会话（文件是
        # 原名）。
        entries = [{"file": "sample60_1.edf", "transmission": 0.6}]
        matches = match_transmission_entries(["sample60.edf"], entries)
        assert matches[0]["transmission"] == pytest.approx(0.6)
        assert "_N" in matches[0]["note"]

    def test_exact_hit_is_never_marked_fuzzy(self):
        entries = [{"file": "a.edf", "transmission": 0.5}]
        matches = match_transmission_entries(["x/y/a.edf"], entries)
        assert matches[0]["note"] == ""

    def test_plain_number_name_stays_unmatched_without_counterpart(self):
        # sample60.edf strips to sample.edf, but unless that name exists on
        # the entry side nothing matches — no false positives from the loose
        # pass alone. / sample60.edf 会剥成 sample.edf，但只要条目侧不存在
        # 该名字就不命中——宽松匹配自身不产生假阳性。
        entries = [{"file": "direct.edf", "transmission": 1.0}]
        matches = match_transmission_entries(["sample60.edf"], entries)
        assert matches[0]["transmission"] is None


# ---------------------------------------------------------------------------
# Group E: _merge_payload_transmissions (bg_subtract batch integration)
# ---------------------------------------------------------------------------


class TestMergePayloadTransmissions:
    def test_exact_path_and_unique_basename(self):
        files = ["C:/data/a.edf", "C:/data/b.edf"]
        merged = _merge_payload_transmissions(
            files, {"C:/data/a.edf": 0.5, "b.edf": "2.0"},
        )
        assert merged == {"C:/data/a.edf": 0.5, "C:/data/b.edf": 2.0}

    def test_duplicate_basenames_are_skipped(self):
        files = ["C:/x/a.edf", "C:/y/a.edf"]
        merged = _merge_payload_transmissions(files, {"a.edf": 0.5})
        assert merged == {}
        # An exact path still resolves even when the basename is ambiguous.
        merged = _merge_payload_transmissions(files, {"C:/y/a.edf": 0.5})
        assert merged == {"C:/y/a.edf": 0.5}

    def test_nonpositive_and_junk_values_are_dropped(self):
        files = ["a.edf", "b.edf", "c.edf", "d.edf"]
        merged = _merge_payload_transmissions(
            files,
            {"a.edf": 0, "b.edf": -1.5, "c.edf": "nan", "d.edf": "not a number"},
        )
        assert merged == {}

    def test_missing_or_invalid_map(self):
        assert _merge_payload_transmissions(["a.edf"], None) == {}
        assert _merge_payload_transmissions(["a.edf"], "0.5") == {}
        assert _merge_payload_transmissions([], {"a.edf": 0.5}) == {}

    def test_unmatched_key_is_ignored(self):
        merged = _merge_payload_transmissions(["a.edf"], {"zzz.edf": 0.5})
        assert merged == {}
