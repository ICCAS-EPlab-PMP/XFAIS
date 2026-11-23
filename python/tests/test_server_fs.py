#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_server_fs.py — /api/server_fs route (admin-opened folders, server mode)
服务器开放目录浏览/下载暂存路由（handle_server_fs）的单元测试。

Covers: list_roots (configured / unset), list (dirs-first ordering, PATH_DENIED
outside the whitelist), download_prepare (plain staging into the session
workspace, duplicate-basename suffixing, compress path delegated to the
v0.5.0 engine with backend-chosen staging dir, error passthrough).
覆盖：list_roots（已配置/未配置）、list（目录优先排序、白名单外 PATH_DENIED）、
download_prepare（纯暂存拷贝进会话工作区、重名加后缀、压缩路径委托 v0.5.0
引擎且暂存目录由后端自选、错误透传）。
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

_BETA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BETA_ROOT) not in sys.path:
    sys.path.insert(0, str(_BETA_ROOT))

from python.service_launcher import handle_server_fs  # noqa: E402


def run(coro):
    return asyncio.run(coro)


async def nop_progress(progress: float, message: str = "") -> None:
    return None


def _patch_staging(monkeypatch, fake):
    """Patch compress_files_for_staging in BOTH module identities.

    ``handle_server_fs`` imports ``services.compressor`` at call time, while
    tests import the same file as ``python.services.compressor`` — sys.path
    carries both package roots, so the two identities are distinct modules.
    Both must be patched; ``services.compressor`` is imported eagerly here
    because the handler only loads it lazily at call time.
    handle_server_fs 调用时导入的是 services.compressor，而测试以
    python.services.compressor 引用同一文件——两个包根都在 sys.path，
    模块身份不同，补丁必须双份；services.compressor 为惰性导入，需在此
    显式加载以保证补丁生效。
    """
    import python.services.compressor as py_mod
    import services.compressor as svc_mod

    monkeypatch.setattr(py_mod, "compress_files_for_staging", fake)
    if svc_mod is not py_mod:
        monkeypatch.setattr(svc_mod, "compress_files_for_staging", fake)


class TestListRoots:
    def test_configured_returns_existing_roots(self, monkeypatch, tmp_path):
        a = tmp_path / "a"
        a.mkdir()
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(a))
        result = run(handle_server_fs({"action": "list_roots"}, nop_progress, asyncio.Event()))
        assert result["status"] == "ok"
        assert result["configured"] is True
        assert result["roots"][0]["path"] == os.path.realpath(str(a))
        assert result["roots"][0]["name"] == "a"

    def test_unset_reports_unconfigured(self, monkeypatch):
        monkeypatch.delenv("XFAIS_INPUT_ROOTS", raising=False)
        result = run(handle_server_fs({"action": "list_roots"}, nop_progress, asyncio.Event()))
        assert result["status"] == "ok"
        assert result["configured"] is False
        assert result["roots"] == []

    def test_nonexistent_roots_filtered(self, monkeypatch, tmp_path):
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(tmp_path / "missing"))
        result = run(handle_server_fs({"action": "list_roots"}, nop_progress, asyncio.Event()))
        assert result["configured"] is False
        assert result["roots"] == []


class TestList:
    def test_entries_dirs_first_sorted(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "zdir").mkdir()
        (root / "adir").mkdir()
        (root / "b.tif").write_bytes(b"x")
        (root / "a.h5").write_bytes(b"y")
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(root))
        result = run(
            handle_server_fs({"action": "list", "path": str(root)}, nop_progress, asyncio.Event())
        )
        assert result["status"] == "ok"
        kinds = [(entry["kind"], entry["name"]) for entry in result["entries"]]
        assert kinds == [("dir", "adir"), ("dir", "zdir"), ("file", "a.h5"), ("file", "b.tif")]
        assert result["truncated"] is False

    def test_outside_whitelist_denied(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(root))
        result = run(
            handle_server_fs({"action": "list", "path": str(outside)}, nop_progress, asyncio.Event())
        )
        assert result["status"] == "error"
        assert result["code"] == "PATH_DENIED"

    def test_dotdot_denied(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(root))
        result = run(
            handle_server_fs(
                {"action": "list", "path": str(root / ".." / "root")}, nop_progress, asyncio.Event()
            )
        )
        assert result["status"] == "error"
        assert result["code"] == "PATH_DENIED"

    def test_unknown_action(self):
        result = run(handle_server_fs({"action": "nope"}, nop_progress, asyncio.Event()))
        assert result["status"] == "error"
        assert result["code"] == "UNKNOWN_ACTION"


class TestDownloadPrepare:
    @staticmethod
    def _session(tmp_path: Path) -> Path:
        session = tmp_path / "session"
        session.mkdir()
        return session

    def test_plain_staging_lands_in_session_workspace(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "a.dat").write_bytes(b"A" * 10)
        (root / "b.dat").write_bytes(b"B" * 5)
        session = self._session(tmp_path)
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(root))
        result = run(
            handle_server_fs(
                {
                    "action": "download_prepare",
                    "paths": [str(root / "a.dat"), str(root / "b.dat")],
                    "compress": False,
                    "_session_tmp_dir": str(session),
                },
                nop_progress,
                asyncio.Event(),
            )
        )
        assert result["status"] == "ok"
        assert result["compressed"] is False
        assert len(result["files"]) == 2
        for item in result["files"]:
            assert os.path.realpath(item["path"]).startswith(os.path.realpath(str(session)))
            assert os.path.isfile(item["path"])
            assert item["filename"] in {"a.dat", "b.dat"}

    def test_duplicate_basenames_suffixed(self, monkeypatch, tmp_path):
        d1 = tmp_path / "d1"
        d1.mkdir()
        (d1 / "x.dat").write_bytes(b"1")
        d2 = tmp_path / "d2"
        d2.mkdir()
        (d2 / "x.dat").write_bytes(b"2")
        session = self._session(tmp_path)
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", os.pathsep.join([str(d1), str(d2)]))
        result = run(
            handle_server_fs(
                {
                    "action": "download_prepare",
                    "paths": [str(d1 / "x.dat"), str(d2 / "x.dat")],
                    "compress": False,
                    "_session_tmp_dir": str(session),
                },
                nop_progress,
                asyncio.Event(),
            )
        )
        names = [item["filename"] for item in result["files"]]
        assert len(names) == 2
        assert len(set(names)) == 2

    def test_outside_file_denied(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "a.dat").write_bytes(b"x")
        outside = tmp_path / "secret.dat"
        outside.write_bytes(b"s")
        session = self._session(tmp_path)
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(root))
        result = run(
            handle_server_fs(
                {
                    "action": "download_prepare",
                    "paths": [str(outside)],
                    "compress": False,
                    "_session_tmp_dir": str(session),
                },
                nop_progress,
                asyncio.Event(),
            )
        )
        assert result["status"] == "error"
        assert result["code"] == "PATH_DENIED"

    def test_empty_paths_rejected(self, monkeypatch, tmp_path):
        session = self._session(tmp_path)
        result = run(
            handle_server_fs(
                {
                    "action": "download_prepare",
                    "paths": [],
                    "compress": False,
                    "_session_tmp_dir": str(session),
                },
                nop_progress,
                asyncio.Event(),
            )
        )
        assert result["code"] == "NO_FILES"

    def test_compress_delegates_to_staging_engine(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "x.tif").write_bytes(b"fake")
        session = self._session(tmp_path)
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(root))
        calls: dict = {}

        async def fake_staging(files, out_dir, send_progress, cancel_event):
            produced = Path(out_dir) / "x_compressed.tif"
            produced.parent.mkdir(parents=True, exist_ok=True)
            produced.write_bytes(b"c")
            calls["files"] = list(files)
            calls["out_dir"] = str(out_dir)
            return {
                "status": "ok",
                "files": [{"status": "ok", "outputPath": str(produced)}],
                "total": 1,
                "success": 1,
                "failed": 0,
                "skipped": 0,
                "ratio": 0.5,
            }

        _patch_staging(monkeypatch, fake_staging)
        result = run(
            handle_server_fs(
                {
                    "action": "download_prepare",
                    "paths": [str(root / "x.tif")],
                    "compress": True,
                    "_session_tmp_dir": str(session),
                },
                nop_progress,
                asyncio.Event(),
            )
        )
        assert result["status"] == "ok"
        assert result["compressed"] is True
        assert calls["files"] == [os.path.realpath(str(root / "x.tif"))]
        # 暂存目录必须落在会话工作区内 / staging dir must stay in the session tree
        assert os.path.realpath(calls["out_dir"]).startswith(os.path.realpath(str(session)))
        assert result["files"][0]["filename"] == "x_compressed.tif"
        assert result["report"]["ratio"] == 0.5

    def test_compress_error_passthrough(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "x.tif").write_bytes(b"fake")
        session = self._session(tmp_path)
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(root))

        async def fake_staging(files, out_dir, send_progress, cancel_event):
            return {"status": "error", "message": "boom"}

        _patch_staging(monkeypatch, fake_staging)
        result = run(
            handle_server_fs(
                {
                    "action": "download_prepare",
                    "paths": [str(root / "x.tif")],
                    "compress": True,
                    "_session_tmp_dir": str(session),
                },
                nop_progress,
                asyncio.Event(),
            )
        )
        assert result["status"] == "error"
        assert "boom" in result["message"]

    def test_compress_without_output_reports_nothing_staged(self, monkeypatch, tmp_path):
        root = tmp_path / "root"
        root.mkdir()
        (root / "x.tif").write_bytes(b"fake")
        session = self._session(tmp_path)
        monkeypatch.setenv("XFAIS_INPUT_ROOTS", str(root))

        async def fake_staging(files, out_dir, send_progress, cancel_event):
            return {"status": "ok", "files": [], "total": 1, "success": 0, "failed": 0, "skipped": 1}

        _patch_staging(monkeypatch, fake_staging)
        result = run(
            handle_server_fs(
                {
                    "action": "download_prepare",
                    "paths": [str(root / "x.tif")],
                    "compress": True,
                    "_session_tmp_dir": str(session),
                },
                nop_progress,
                asyncio.Event(),
            )
        )
        assert result["status"] == "error"
        assert result["code"] == "NOTHING_STAGED"
