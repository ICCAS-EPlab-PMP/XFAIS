#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_web_gates_and_reaper.py — server-mode gates & session TTL reaper (v0.5.0)
服务器模式门禁（pyFAI-calib2 启动器/安装器仅桌面）与会话 TTL 清扫的单元测试。

Covers: launch/install DESKTOP_ONLY rejection without ``_is_desktop`` (no
process must ever be spawned from the unauthenticated API), TTL parsing, and
the reaper sweep (dead+old removed, live kept even when old, fresh kept).
覆盖：无 _is_desktop 时 launch/install 的 DESKTOP_ONLY 拒绝（未鉴权 API 绝不
拉起进程）、TTL 解析、清扫（死旧目录删除、活跃目录即便过旧也保留、新鲜
目录保留）。
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

_BETA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BETA_ROOT) not in sys.path:
    sys.path.insert(0, str(_BETA_ROOT))

from python.service_launcher import (  # noqa: E402
    SessionManager,
    _session_ttl_minutes,
    handle_install_pyfai,
    handle_launch_pyfai,
    sweep_session_dirs,
)


def run(coro):
    return asyncio.run(coro)


async def nop_progress(progress: float, message: str = "") -> None:
    return None


class TestPyfaiServerGates:
    def test_launch_rejected_without_desktop_flag(self):
        result = run(handle_launch_pyfai({}, nop_progress, asyncio.Event()))
        assert result["status"] == "error"
        assert result["code"] == "DESKTOP_ONLY"
        assert "桌面版" in result["message"]

    def test_install_rejected_without_desktop_flag(self):
        result = run(handle_install_pyfai({}, nop_progress, asyncio.Event()))
        assert result["status"] == "error"
        assert result["code"] == "DESKTOP_ONLY"

    def test_launch_rejected_with_forged_false_flag(self):
        # web 客户端伪造 _is_desktop=false 仍被拒（门禁要求显式 True）。
        result = run(handle_launch_pyfai({"_is_desktop": False}, nop_progress, asyncio.Event()))
        assert result["code"] == "DESKTOP_ONLY"


class TestSessionTtlParsing:
    def test_default_is_120_minutes(self, monkeypatch):
        monkeypatch.delenv("XFAIS_SESSION_TTL_MINUTES", raising=False)
        assert _session_ttl_minutes() == 120.0

    def test_override(self, monkeypatch):
        monkeypatch.setenv("XFAIS_SESSION_TTL_MINUTES", "30")
        assert _session_ttl_minutes() == 30.0

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setenv("XFAIS_SESSION_TTL_MINUTES", "0")
        assert _session_ttl_minutes() == 0.0

    def test_invalid_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("XFAIS_SESSION_TTL_MINUTES", "not-a-number")
        assert _session_ttl_minutes() == 120.0

    def test_negative_clamped_to_zero(self, monkeypatch):
        monkeypatch.setenv("XFAIS_SESSION_TTL_MINUTES", "-5")
        assert _session_ttl_minutes() == 0.0


class TestSessionDirSweep:
    @pytest.fixture(autouse=True)
    def _isolated_tempdir(self, tmp_path, monkeypatch):
        # 把系统临时目录指到测试私有目录，清扫绝不触碰真实 %TEMP%。
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))
        self.tmp_path = tmp_path

    def test_dead_old_dir_removed(self):
        dead = self.tmp_path / "xfais_session_deadbeef_1"
        dead.mkdir()
        (dead / "staged.bin").write_bytes(b"x")
        old = time.time() - 9999
        os.utime(dead, (old, old))
        sweep_session_dirs(SessionManager(), ttl_seconds=60.0)
        assert not dead.exists()

    def test_fresh_dead_dir_kept(self):
        dead = self.tmp_path / "xfais_session_deadbeef_2"
        dead.mkdir()
        sweep_session_dirs(SessionManager(), ttl_seconds=3600.0)
        assert dead.exists()

    def test_live_session_dir_kept_even_when_old(self):
        mgr = SessionManager()
        sid = mgr.create_session()
        live_dir = Path(mgr.get_tmp_dir(sid))
        old = time.time() - 9999
        os.utime(live_dir, (old, old))
        sweep_session_dirs(mgr, ttl_seconds=60.0)
        assert live_dir.exists()

    def test_non_session_dirs_untouched(self):
        stranger = self.tmp_path / "unrelated_dir"
        stranger.mkdir()
        old = time.time() - 9999
        os.utime(stranger, (old, old))
        sweep_session_dirs(SessionManager(), ttl_seconds=60.0)
        assert stranger.exists()
