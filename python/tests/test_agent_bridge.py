# -*- coding: utf-8 -*-
"""Tests for the external-agent bridge (v0.3.5 AI build).

Covers the security-relevant surface: whitelist enforcement, enable/token
gating, registry lifecycle, and run_task validation. The full WS relay needs
a live renderer link and is exercised by the Playwright agent-bridge E2E.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

# Same bootstrap as the other service tests: put BETA/ (the dir that contains
# python/) on sys.path so `services.*` imports resolve.
_BETA_ROOT = Path(__file__).resolve().parents[2]
if str(_BETA_ROOT) not in sys.path:
    sys.path.insert(0, str(_BETA_ROOT))

from python.services.agent_bridge import (  # noqa: E402
    AGENT_COMMANDS,
    AgentBridge,
    agent_bridge_from_env,
)


class _FakeWsService:
    """Minimal stand-in: no asyncio loop, routes mirror the real registry."""

    def __init__(self) -> None:
        self._loop = None
        self.routes = {
            "/api/calibration": object(),
            "/api/integrate1d": object(),
            "/api/transmission": object(),
        }


class _FakeAgentWs:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, data: str) -> None:
        self.sent.append(data)


def _make_bridge(tmp_path: Path, enabled: bool = True, token: str = "") -> AgentBridge:
    bridge = AgentBridge(
        _FakeWsService(),
        http_port=8765,
        ws_port=8766,
        mode="desktop",
        enabled=enabled,
        token=token,
    )
    # Redirect the registry into the test sandbox.
    registry = tmp_path / "instances"
    bridge._registry_dir = (lambda d=registry: d)  # type: ignore[method-assign]
    bridge._registry_path = (lambda d=registry: d / f"{os.getpid()}.json")  # type: ignore[method-assign]
    return bridge


def test_command_whitelist_rejects_unknown(_tmp_registry: Path) -> None:
    bridge = _make_bridge(_tmp_registry)
    result = bridge.command("spawn_shell", {}, 1000, {})
    assert result["ok"] is False
    assert "unknown command" in result["error"]
    # Every whitelisted name must be a renderer verb the UI implements.
    assert AGENT_COMMANDS == frozenset(
        {"state", "guide", "modules", "capture", "click", "highlight", "confirm", "navigate", "apply_options"}
    )


def test_disabled_bridge_refuses_everything(_tmp_registry: Path) -> None:
    bridge = _make_bridge(_tmp_registry, enabled=False)
    result = bridge.command("state", {}, 1000, {})
    assert result["ok"] is False
    assert "disabled" in result["error"]


def test_token_required_when_configured(_tmp_registry: Path) -> None:
    bridge = _make_bridge(_tmp_registry, token="s3cret")
    assert bridge.command("state", {}, 1000, {})["ok"] is False
    ok_headers = {"x-agent-token": "s3cret"}
    # No live agent link yet → 503, which proves the token check PASSED.
    result = bridge.command("state", {}, 1000, ok_headers)
    assert result["status"] == 503
    assert "no live agent link" in result["error"]


def test_hello_writes_registry_and_shutdown_removes(_tmp_registry: Path) -> None:
    bridge = _make_bridge(_tmp_registry)
    ws = _FakeAgentWs()

    def sender(text: str) -> None:
        ws.sent.append(text)

    bridge.handle_hello(
        ws,
        {"ai": True, "version": "0.3.5", "route": "calibration", "routePath": "/workspace/calibration"},
        sender,
    )
    path = _tmp_registry / "instances" / f"{os.getpid()}.json"
    assert path.exists()
    info = json.loads(path.read_text(encoding="utf-8"))
    assert info["route"] == "calibration"
    assert info["url"] == "http://127.0.0.1:8765"
    assert info["ai"] is True
    bridge.shutdown()
    assert not path.exists()


def test_result_round_trip_via_sender(_tmp_registry: Path) -> None:
    """command() relays through the sender and resolves on handle_result."""
    bridge = _make_bridge(_tmp_registry)
    ws = _FakeAgentWs()

    def sender(text: str) -> None:
        ws.sent.append(text)
        # Simulate the renderer replying immediately (async → sync driver).
        import threading as _t

        msg = json.loads(text)
        reply_loop = asyncio.new_event_loop()
        try:
            reply_loop.run_until_complete(
                bridge.handle_result(
                    {"req_id": msg["req_id"], "ok": True, "data": {"clicked": True}}
                )
            )
        finally:
            reply_loop.close()

    bridge.handle_hello(ws, {"ai": True, "version": "0.3.5", "route": "home"}, sender)
    result = bridge.command("click", {"target": {"aiId": "x"}}, 3000, {})
    assert result["ok"] is True
    assert result["data"]["clicked"] is True


def test_run_task_validates_route_names(_tmp_registry: Path) -> None:
    bridge = _make_bridge(_tmp_registry)
    assert bridge.run_task("calibration", {}, 5, {})["ok"] is False  # loop is None → 503 AFTER validation? No: validation first
    # Invalid names never reach the service loop.
    result = bridge.run_task("../etc/passwd", {}, 5, {})
    assert result["ok"] is False
    assert "invalid route" in result["error"]
    result = bridge.run_task("unknown_route", {}, 5, {})
    assert result["ok"] is False
    assert "unknown route" in result["error"]


def test_env_gating_web_off_by_default(_tmp_registry: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("XFAIS_AGENT_BRIDGE", raising=False)
    web_bridge = agent_bridge_from_env(_FakeWsService(), http_port=8765, ws_port=None, mode="web")
    assert web_bridge.enabled is False
    desktop_bridge = agent_bridge_from_env(_FakeWsService(), http_port=8765, ws_port=8766, mode="desktop")
    assert desktop_bridge.enabled is True
    monkeypatch.setenv("XFAIS_AGENT_BRIDGE", "1")
    assert agent_bridge_from_env(_FakeWsService(), http_port=8765, ws_port=None, mode="web").enabled is True
    monkeypatch.setenv("XFAIS_AGENT_BRIDGE", "0")
    assert agent_bridge_from_env(_FakeWsService(), http_port=8765, ws_port=8766, mode="desktop").enabled is False


@pytest.fixture
def _tmp_registry(tmp_path: Path) -> Path:
    return tmp_path


# ===========================================================================
# Complex-task gate / 复杂任务门禁（2026-11-01）
# ===========================================================================


class TestComplexTaskGate:
    """Gated routes refuse to run until the user accepts an in-app confirm."""

    def _activate_nonce(self, bridge: AgentBridge, nonce: str, *, confirmed: bool = True) -> dict:
        """Drive command('confirm') with a sender that answers on the spot."""
        ws = _FakeAgentWs()

        def sender(text: str) -> None:
            msg = json.loads(text)
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(
                    bridge.handle_result(
                        {"req_id": msg["req_id"], "ok": True, "data": {"confirmed": confirmed}}
                    )
                )
            finally:
                loop.close()

        bridge.handle_hello(ws, {"ai": True, "version": "0.3.5"}, sender)
        return bridge.command(
            "confirm", {"message": "测试确认", "confirm_nonce": nonce}, 3000, {}
        )

    def test_gated_action_refused_until_user_confirms(self, _tmp_registry: Path) -> None:
        bridge = _make_bridge(_tmp_registry)
        blocked = bridge.run_task("calibration", {"action": "set_center"}, 5, {})
        assert blocked["ok"] is False
        assert blocked["code"] == "need_user_input"
        assert blocked["confirm_nonce"]
        assert blocked["questions"]
        # Bogus nonce retries stay blocked and mint a FRESH nonce.
        again = bridge.run_task(
            "calibration", {"action": "set_center", "_agent_confirm": "bogus"}, 5, {}
        )
        assert again["code"] == "need_user_input"
        assert again["confirm_nonce"] != blocked["confirm_nonce"]
        # The user accepts via the confirm flow → the nonce activates and the
        # retry gets past the gate (then fails deeper on the fake handler).
        reply = self._activate_nonce(bridge, blocked["confirm_nonce"])
        assert reply["ok"] is True
        retry = bridge.run_task(
            "calibration",
            {"action": "set_center", "_agent_confirm": blocked["confirm_nonce"]},
            5,
            {},
        )
        assert retry.get("code") != "need_user_input"

    def test_nonce_is_single_use_and_purpose_bound(self, _tmp_registry: Path) -> None:
        bridge = _make_bridge(_tmp_registry)
        nonce = bridge.run_task("calibration", {"action": "refine"}, 5, {})["confirm_nonce"]
        self._activate_nonce(bridge, nonce)
        first = bridge.run_task(
            "calibration", {"action": "refine", "_agent_confirm": nonce}, 5, {}
        )
        assert first.get("code") != "need_user_input"
        # Second use of the same nonce → gated again.
        second = bridge.run_task(
            "calibration", {"action": "refine", "_agent_confirm": nonce}, 5, {}
        )
        assert second.get("code") == "need_user_input"
        # Purpose-bound: a transmission nonce does not open calibration.
        tnonce = bridge.run_task("transmission", {"action": "measure"}, 5, {})["confirm_nonce"]
        self._activate_nonce(bridge, tnonce)
        cross = bridge.run_task(
            "calibration", {"action": "refine", "_agent_confirm": tnonce}, 5, {}
        )
        assert cross.get("code") == "need_user_input"

    def test_declined_confirm_does_not_activate_nonce(self, _tmp_registry: Path) -> None:
        bridge = _make_bridge(_tmp_registry)
        nonce = bridge.run_task("calibration", {"action": "set_center"}, 5, {})["confirm_nonce"]
        reply = self._activate_nonce(bridge, nonce, confirmed=False)
        assert reply["ok"] is True
        retry = bridge.run_task(
            "calibration", {"action": "set_center", "_agent_confirm": nonce}, 5, {}
        )
        assert retry.get("code") == "need_user_input"

    def test_ungated_actions_and_routes_pass_through(self, _tmp_registry: Path) -> None:
        bridge = _make_bridge(_tmp_registry)
        ungated_action = bridge.run_task("calibration", {"action": "update_peaks"}, 5, {})
        assert ungated_action.get("code") != "need_user_input"
        ungated_route = bridge.run_task("integrate1d", {}, 5, {})
        assert ungated_route.get("code") != "need_user_input"

    def test_transmission_route_gates_all_actions(self, _tmp_registry: Path) -> None:
        bridge = _make_bridge(_tmp_registry)
        assert bridge.run_task("transmission", {}, 5, {}).get("code") == "need_user_input"
        assert (
            bridge.run_task("transmission", {"action": "preview"}, 5, {}).get("code")
            == "need_user_input"
        )

    def test_registry_records_cli_paths(self, _tmp_registry: Path) -> None:
        bridge = _make_bridge(_tmp_registry)
        bridge.handle_hello(_FakeAgentWs(), {"ai": True, "version": "0.3.5"}, lambda _t: None)
        info = json.loads(
            (_tmp_registry / "instances" / f"{os.getpid()}.json").read_text(encoding="utf-8")
        )
        assert info["python"]
        assert info["cli"].endswith("xfais_cli.py")

    # ── PONI fast-path / 用户提供了 PONI ⇒ 几何类问题豁免 ────────────────────

    def _write_poni(self, tmp_path: Path) -> str:
        poni = tmp_path / "user_calib.poni"
        poni.write_text("# PONI file\n", encoding="utf-8")
        return str(poni)

    def test_valid_poni_reduces_calibration_questions(
        self, _tmp_registry: Path, tmp_path: Path
    ) -> None:
        bridge = _make_bridge(_tmp_registry)
        poni = self._write_poni(tmp_path)
        reduced = bridge.run_task(
            "calibration", {"action": "set_center", "poni_path": poni}, 5, {}
        )
        assert reduced["code"] == "need_user_input"
        assert reduced["poni_accepted"] is True
        assert reduced["poni_note"]
        # Geometry questions gone: only sample type + image import remain,
        # renumbered cleanly.
        assert len(reduced["questions"]) == 2
        assert reduced["questions"][0].startswith("①")
        # camelCase key works the same.
        camel = bridge.run_task(
            "calibration", {"action": "refine", "poniPath": poni}, 5, {}
        )
        assert camel.get("poni_accepted") is True
        assert len(camel["questions"]) == 2
        # No poni → full five-question set.
        full = bridge.run_task("calibration", {"action": "set_center"}, 5, {})
        assert "poni_accepted" not in full
        assert len(full["questions"]) == 5

    def test_invalid_poni_does_not_relax_gate(
        self, _tmp_registry: Path, tmp_path: Path
    ) -> None:
        bridge = _make_bridge(_tmp_registry)
        for bogus in (
            str(tmp_path / "missing.poni"),  # non-existent
            str(tmp_path / "notaponi.txt"),  # wrong extension
            "not a path at all",
        ):
            result = bridge.run_task(
                "calibration", {"action": "set_center", "poni_path": bogus}, 5, {}
            )
            assert result["code"] == "need_user_input"
            assert "poni_accepted" not in result
            assert len(result["questions"]) == 5

    def test_poni_never_relaxes_transmission(
        self, _tmp_registry: Path, tmp_path: Path
    ) -> None:
        bridge = _make_bridge(_tmp_registry)
        poni = self._write_poni(tmp_path)
        result = bridge.run_task("transmission", {"poni_path": poni}, 5, {})
        assert result["code"] == "need_user_input"
        assert "poni_accepted" not in result
        assert len(result["questions"]) == 3
