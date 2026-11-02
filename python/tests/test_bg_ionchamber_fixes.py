#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_bg_ionchamber_fixes.py — Regression tests for the ionchamber import/match
fixes (2026-11-01, AI-build batch).

Covers the three defects found in the "does bg subtraction still mishandle
ionchamber files?" audit:

    1. utf-8 BOM files (typical for Windows-written .Ionchamber/.txt) failed
       to parse entirely — with a BOM the header line no longer starts with
       '#' and ``float("Ionchamber0")`` raised, so NO transmission was ever
       computed (the UI silently showed an empty 透过率 column).
    2. match_ionchamber priority 2 claimed "closest number" but picked the
       LOWEST number — wrong ion file paired with a data file, silently
       wrong transmission.
    3. The ionchamber folder scan treated every non-image file as an
       ionchamber candidate (the ``_ion_exts`` whitelist was computed but
       never used); reports/CSV results sharing the folder could donate a
       bogus transmission.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure BETA/python is on sys.path so service_launcher can import `services.*`
_PYTHON_DIR = str(Path(__file__).resolve().parent.parent)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

import pytest

from python.services.bg_subtractor import (
    match_ionchamber,
    parse_ionchamber_file,
)

_ION_HEADER = "# Time  Ionchamber0  Ionchamber1  Ionchamber2"


def _write_ion_text(path: Path, *, bom: bool = False) -> None:
    rows = [
        "2026-01-19 12:34:34.130671238  2.807135e-7  2.388761e-8  9.71103e-10",
        "2026-01-19 12:34:35.130671238  2.812000e-7  2.390000e-8  9.71200e-10",
    ]
    text = "\n".join([_ION_HEADER, *rows]) + "\n"
    raw = text.encode("utf-8-sig" if bom else "utf-8")
    path.write_bytes(raw)


# ---------------------------------------------------------------------------
# Fix 1: BOM parsing
# ---------------------------------------------------------------------------


class TestBomParsing:
    def test_utf8_bom_ionchamber_parses(self, tmp_path: Path) -> None:
        """A BOM-prefixed .Ionchamber file must parse, not return None."""
        p = tmp_path / "wkf-G1-Q-30-2-waxs-11.9s_00001.Ionchamber"
        _write_ion_text(p, bom=True)
        df = parse_ionchamber_file(str(p))
        assert df is not None
        assert len(df) == 2
        assert list(df.columns) == ["Time", "Ionchamber0", "Ionchamber1", "Ionchamber2"]
        assert df["Ionchamber0"].iloc[0] == pytest.approx(2.807135e-7)

    def test_utf8_bom_plain_txt_parses(self, tmp_path: Path) -> None:
        p = tmp_path / "sample.txt"
        _write_ion_text(p, bom=True)
        assert parse_ionchamber_file(str(p)) is not None

    def test_utf8_no_bom_still_parses(self, tmp_path: Path) -> None:
        p = tmp_path / "sample.Ionchamber"
        _write_ion_text(p, bom=False)
        df = parse_ionchamber_file(str(p))
        assert df is not None and len(df) == 2


# ---------------------------------------------------------------------------
# Fix 2: priority-2 "closest number" matching
# ---------------------------------------------------------------------------


class TestClosestNumberMatching:
    DATA = "D:/data/wkf-G1-Q-30-2-waxs-11.9s_00010.tif"

    IONS = [
        "D:/ion/wkf-G1-Q-30-2-waxs-11.9s_00001.Ionchamber",
        "D:/ion/wkf-G1-Q-30-2-waxs-11.9s_00009.Ionchamber",
        "D:/ion/wkf-G1-Q-30-2-waxs-11.9s_00020.Ionchamber",
    ]

    def test_same_state_picks_closest_number(self) -> None:
        """All ions share base+state; the data's own number (10) must pick 9,
        not the lowest number (1)."""
        results = match_ionchamber([self.DATA], list(self.IONS))
        assert results[0]["matched_ion"] == self.IONS[1]  # _00009
        assert results[0]["method"] == "base_state"

    def test_closest_number_symmetric(self) -> None:
        """A data file numbered 19 must pick _00020 over _00009."""
        data = "D:/data/wkf-G1-Q-30-2-waxs-11.9s_00019.tif"
        results = match_ionchamber([data], list(self.IONS))
        assert results[0]["matched_ion"] == self.IONS[2]  # _00020

    def test_data_without_number_falls_back(self) -> None:
        """No number on the data file: the old lowest-number rule applies."""
        data = "D:/data/wkf-G1-Q-30-2-waxs-11.9s.tif"
        results = match_ionchamber([data], list(self.IONS))
        assert results[0]["matched_ion"] == self.IONS[0]  # lowest number
        assert results[0]["method"] == "base_state"

    def test_exact_match_untouched(self) -> None:
        """Exact base+state+number still wins outright."""
        ion10 = "D:/ion/wkf-G1-Q-30-2-waxs-11.9s_00010.Ionchamber"
        results = match_ionchamber([self.DATA], [ion10, *self.IONS])
        assert results[0]["matched_ion"] == ion10
        assert results[0]["method"] == "exact"


# ---------------------------------------------------------------------------
# Fix 3: ionchamber folder scan (whitelist first, non-image fallback)
# ---------------------------------------------------------------------------


async def _noop_progress(_progress: float, _message: str) -> None:
    """No-op progress callback."""


class TestIonFolderScan:
    def _run_match(self, tmp_path: Path, ion_names: list[str]) -> list[dict]:
        """Drive the real handler with a folder containing the given names."""
        from python.service_launcher import handle_bg_subtract

        data_dir = tmp_path / "data"
        ion_dir = tmp_path / "ion"
        data_dir.mkdir()
        ion_dir.mkdir()
        (data_dir / "wkf-G1-Q-30-2-waxs-11.9s_00001.tif").write_bytes(b"")
        for name in ion_names:
            (ion_dir / name).write_bytes(b"")

        result = asyncio.run(
            handle_bg_subtract(
                {
                    "action": "ionchamber_match",
                    "data_files": [str(data_dir / "wkf-G1-Q-30-2-waxs-11.9s_00001.tif")],
                    "ionchamber_folder": str(ion_dir),
                    "bg_ionchamber_path": "",
                },
                _noop_progress,
                asyncio.Event(),
            )
        )
        assert result.get("status") == "ok", result
        matches = result.get("matches") or []
        assert len(matches) == 1
        matched = matches[0].get("matched_ion") or ""
        return [Path(matched).name] if matched else []

    def test_whitelist_wins_over_stray_files(self, tmp_path: Path) -> None:
        """A results CSV in the ion folder must not shadow the real ion file."""
        matched = self._run_match(
            tmp_path,
            [
                "wkf-G1-Q-30-2-waxs-11.9s_00001.Ionchamber",
                "bg_subtract_results_2026-11-01.csv",
            ],
        )
        assert matched == ["wkf-G1-Q-30-2-waxs-11.9s_00001.Ionchamber"]

    def test_nonimage_fallback_kept_for_other_conventions(self, tmp_path: Path) -> None:
        """Folders using an unknown ion extension still match (old behaviour)."""
        matched = self._run_match(
            tmp_path,
            ["wkf-G1-Q-30-2-waxs-11.9s_00001.monitor"],
        )
        assert matched == ["wkf-G1-Q-30-2-waxs-11.9s_00001.monitor"]
