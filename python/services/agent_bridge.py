# -*- coding: utf-8 -*-
"""agent_bridge.py — External AI-agent bridge for X-FAIS (v0.3.5, AI build).

Lets MCP agents (ZCode / Claude Code / Codex / WorkBuddy) observe and operate
a RUNNING X-FAIS instance without ever tearing it down between operations:

    agent (stdio MCP) ──HTTP──▶ /api/agent_command ──WS push──▶ renderer
    renderer executes (state / guide / capture / click / highlight / confirm /
    navigate / apply_options) and replies over the same WebSocket; the bridge
    returns the reply to the agent. Task execution goes through the renderer's
    OWN task transport internally (`/api/agent_task` → a sink WebSocket), so
    agents get exactly the same handlers as the UI — no second implementation.

Instance registry: every instance with a live agent link writes
``~/.xfais/instances/<pid>.json`` (HTTP port, WS port, version, AI flag,
current route). MCP's ``list_instances`` scans that directory, which is how
multi-open disambiguation works — each desktop window is its own Python
process with its own port, and the registry tells the agent which is which.

Security model:
  * The bridge only RELAYS UI commands; it opens no outbound connections and
    fetches no URLs, so there is no SSRF surface here.
  * Command names are whitelist-only; payloads must be JSON objects capped at
    256 KB; timeouts clamped to ≤ 60 s.
  * Desktop (`serve`) binds 127.0.0.1 and the bridge is on by default (it can
    be disabled with XFAIS_AGENT_BRIDGE=0). Web (`serve_web`) deployments are
    exposed to networks, so the bridge stays OFF unless the operator sets
    XFAIS_AGENT_BRIDGE=1.
  * Optional shared token: set XFAIS_AGENT_TOKEN and every agent HTTP call
    must carry the same value in the X-Agent-Token header.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import re
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

# Whitelisted renderer commands — anything else is rejected before relay.
# `guide` (2026-10-25) serializes the module's internal guided-tutorial table
# (steps, live done-flags = user position, anchor presence) for the agent;
# `modules` (2026-10-25) returns the all-module capability directory with
# routing keywords + the anti-hallucination golden rule.
AGENT_COMMANDS = frozenset(
    {"state", "guide", "modules", "capture", "click", "highlight", "confirm", "navigate", "apply_options"}
)

MAX_COMMAND_BYTES = 256 * 1024
MAX_TIMEOUT_MS = 60_000
MAX_TASK_TIMEOUT_S = 300

# ── Complex-task gate / 复杂任务门禁（2026-11-01） ─────────────────────────────
#
# Some tasks depend on experiment facts only the USER knows (calibrant,
# detector, wavelength, distance, which image is the direct beam…). An agent
# that guesses them produces confidently wrong science, so gated routes are
# REFUSED until the agent has asked the user through the in-app confirm
# dialog and the user clicked 确认. Mechanically: a gated run_task mints a
# single-use nonce; the agent must present the questions via `confirm`
# carrying that nonce; an accepted confirm activates the nonce; the retry
# consumes it. The UI's own submitTask path never goes through run_task, so
# real users are never gated — this binds external agents only.
# 部分任务依赖只有用户掌握的实验信息（标样、探测器、波长、距离、哪张是直通
# 光……），agent 擅自猜测会产出“自信的错误科学”。被门禁的任务在 agent 通过
# 应用内确认弹窗向用户提问、且用户点「确认」之前一律拒绝执行。机制：被拦截
# 的 run_task 铸造一次性 nonce → agent 携带 nonce 调 confirm 提问 → 用户确认
# 激活 → 重试时消费。UI 自身的 submitTask 不经过 run_task，门禁只约束外部
# agent，不影响真人操作。
COMPLEX_TASK_GATES: dict[str, dict[str, Any]] = {
    "calibration": {
        "actions": frozenset({"set_center", "refine", "ring_standard"}),
        "why": (
            "光斑中心查找/标定几何精修依赖实验元信息，agent 不能替用户决定："
            "标样、探测器、波长/能量、距离初值与图像数据本身都必须由用户提供。"
        ),
        # Full question set. Geometry facts (detector/wavelength/distance/
        # beam centre) are carried by a PONI — when the task params bring a
        # valid poni_path, the reduced list below replaces them (user-provided
        # PONI ⇒ geometry questions are dropped, see _poni_provided).
        # 完整问题集。几何事实（探测器/波长/距离/光束中心）由 PONI 携带——任务
        # 参数带有效 poni_path 时改用下方精简集（用户提供了 PONI ⇒ 几何类问题
        # 不再询问）。
        "questions": [
            "标样是什么（AgBeh / CeO2 / LaB6 / 自备标样及其 d-spacings）？",
            "探测器型号与像素尺寸（或让用户在界面里选好探测器配置）？",
            "X 射线波长（Å）或能量（keV）？",
            "样品-探测器距离初值（mm）？光斑大致位置由用户点选还是沿用默认？",
            "直通光/标样图像是否已由用户导入？请引导用户在界面上完成导入。",
        ],
        "questions_poni": [
            "标样是什么（AgBeh / CeO2 / LaB6 / 自备标样及其 d-spacings）？",
            "直通光/标样图像是否已由用户导入？请引导用户在界面上完成导入。",
        ],
        "poni_note": (
            "已接受 poni_path：几何信息（探测器/波长/距离/光束中心）以该 PONI 为准，"
            "几何类问题豁免。执行前先调用未门禁的 calibration seed_from_poni 把 "
            "PONI 载入会话，确保任务真正使用它。"
        ),
    },
    "transmission": {
        "actions": None,  # all actions gated / 所有动作都拦截
        "why": (
            "直通光透过率测量的光斑区域与参考图必须由用户确认，"
            "区域选错会静默污染整批透过率数值。"
        ),
        # PONI says nothing about the direct-beam region or the reference
        # frame — no poni fast-path here.
        # PONI 回答不了光斑区域与参考图——本门禁无 PONI 快速通道。
        "questions": [
            "直通光区域如何选取（矩形框坐标，或让用户在界面拖拽框选）？",
            "哪一张作为参考（first / last / 指定文件）？",
            "样品图与直通光图分别有哪些文件？",
        ],
    },
}
CONFIRM_TTL_S = 600  # minted nonce → user confirms within 10 minutes

#: Questions are numbered at response time so reduced sets renumber cleanly.
#: 问题编号在组包时补上，精简集自动重排。
_QUESTION_MARKS = "①②③④⑤⑥⑦⑧⑨⑩"


def _poni_provided(params: dict[str, Any]) -> bool:
    """True when params carry a real .poni file (poni_path/poniPath/poni).

    A PONI supplied BY THE USER answers the geometry questions on its own, so
    gates may drop them. Must exist on disk and carry the .poni extension —
    a bare string must never silently relax a gate.
    任务参数携带真实存在的 .poni 文件时视为用户提供了几何数据。必须存在且
    带 .poni 扩展名——随意一个字符串绝不能悄悄放宽门禁。
    """
    for key in ("poni_path", "poniPath", "poni"):
        raw = params.get(key)
        if isinstance(raw, str) and raw.strip():
            path = raw.strip()
            if path.lower().endswith(".poni") and os.path.isfile(path):
                return True
    return False

ENV_ENABLE = "XFAIS_AGENT_BRIDGE"
ENV_TOKEN = "XFAIS_AGENT_TOKEN"


def _registry_dir() -> Path:
    return Path.home() / ".xfais" / "instances"


class _TaskSink:
    """Duck-typed WebSocket the task runner can reply into.

    ``WebSocketService._run_task`` only ever calls ``ws.send(str|bytes)`` on
    its socket, so a queue-backed sink is enough to run a task with the SAME
    handler chain as the UI and collect progress/result/binary frames.
    """

    def __init__(self) -> None:
        self.frames: list[tuple[str, Any]] = []

    async def send(self, data: Any) -> None:
        if isinstance(data, bytes):
            self.frames.append(("binary", data))
        else:
            self.frames.append(("text", data))


class AgentBridge:
    """Relay between agent HTTP calls and the renderer's agent WebSocket."""

    def __init__(
        self,
        ws_service: Any,
        *,
        http_port: int,
        ws_port: int | None,
        mode: str,
        enabled: bool,
        token: str = "",
    ) -> None:
        self.ws_service = ws_service
        self.http_port = http_port
        self.ws_port = ws_port
        self.mode = mode  # 'desktop' | 'web'
        self.enabled = enabled
        self.token = token
        # Latest agent link wins — one active operator per instance. The
        # renderer keeps its link open across operations (no per-command
        # teardown), which is what "operate without closing" requires.
        # The sender is mode-specific: desktop schedules onto the connection's
        # asyncio loop; web single-port mode writes frames synchronously under
        # a lock (its WS loop is a blocking reader on the handler thread).
        self._agent_token: Any = None
        self._agent_sender: Callable[[str], None] | None = None
        self._agent_info: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._pending: dict[str, dict[str, Any]] = {}
        # Complex-task gate nonces (see COMPLEX_TASK_GATES above).
        self._confirm_tokens: dict[str, dict[str, Any]] = {}

    # ── WebSocket side ───────────────────────────────────────────────────────

    def handle_hello(
        self,
        token: Any,
        payload: dict[str, Any],
        sender: Callable[[str], None],
    ) -> None:
        """Register the active agent link (called from either WS loop).

        ``token`` is an opaque connection identity used by handle_disconnect;
        ``sender(text)`` delivers one JSON frame to the renderer from ANY
        thread (it must be thread-safe itself).
        """
        info = {
            "pid": os.getpid(),
            "mode": self.mode,
            "httpPort": self.http_port,
            "wsPort": self.ws_port,
            "url": f"http://127.0.0.1:{self.http_port}",
            "ai": bool(payload.get("ai", True)),
            "version": str(payload.get("version", "")),
            "route": str(payload.get("route", "")),
            "routePath": str(payload.get("routePath", "")),
            "locale": str(payload.get("locale", "")),
            "label": str(payload.get("label", "")),
            "platform": str(payload.get("platform", "")),
            # CLI discovery (2026-11-01): the bundled interpreter running this
            # backend and the xfais_cli.py next to services/ let agents run
            # pyFAI-style CLI commands locally without any UI round trip.
            # CLI 发现（2026-11-01）：捆绑解释器与同目录 xfais_cli.py，让 agent
            # 可不经 UI 直接本地执行 pyFAI 风格命令。
            "python": sys.executable,
            "cli": str(Path(__file__).resolve().parents[1] / "xfais_cli.py"),
            "startedAt": time.time(),
            "lastSeen": time.time(),
        }
        with self._lock:
            self._agent_token = token
            self._agent_sender = sender
            self._agent_info = info
        self._write_registry(info)

    async def handle_result(self, data: dict[str, Any]) -> None:
        req_id = str(data.get("req_id", ""))
        with self._lock:
            box = self._pending.get(req_id)
        if box is not None:
            box["result"] = {
                "ok": bool(data.get("ok", False)),
                "data": data.get("data") if isinstance(data.get("data"), dict) else {},
                "error": data.get("error"),
            }
            box["event"].set()

    def handle_disconnect(self, token: Any) -> None:
        with self._lock:
            if self._agent_token is token:
                self._agent_token = None
                self._agent_sender = None
        self._remove_registry()

    # ── HTTP side (called from request threads) ──────────────────────────────

    def _reject(self, status: int, message: str) -> dict[str, Any]:
        return {"ok": False, "status": status, "error": message}

    def _check_token(self, headers: dict[str, str]) -> bool:
        if not self.token:
            return True
        return headers.get("x-agent-token", "") == self.token

    def command(
        self,
        command: str,
        payload: dict[str, Any],
        timeout_ms: int,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Relay one whitelisted command to the renderer and await its reply."""
        if not self.enabled:
            return self._reject(403, "agent bridge disabled")
        if not self._check_token(headers):
            return self._reject(401, "bad or missing X-Agent-Token")
        if command not in AGENT_COMMANDS:
            return self._reject(400, f"unknown command: {command}")
        timeout_ms = max(100, min(int(timeout_ms or 15_000), MAX_TIMEOUT_MS))

        with self._lock:
            sender = self._agent_sender
        if sender is None:
            return self._reject(503, "no live agent link (is the X-FAIS window open?)")

        req_id = uuid.uuid4().hex
        box: dict[str, Any] = {"event": threading.Event(), "result": None}
        with self._lock:
            self._pending[req_id] = box

        message = json.dumps(
            {"type": "agent_command", "req_id": req_id, "command": command, "payload": payload}
        )
        try:
            sender(message)
        except Exception as exc:
            with self._lock:
                self._pending.pop(req_id, None)
            return self._reject(503, f"agent link send failed: {exc}")

        if not box["event"].wait(timeout=timeout_ms / 1000.0):
            with self._lock:
                self._pending.pop(req_id, None)
            return self._reject(504, "agent command timed out")
        with self._lock:
            self._pending.pop(req_id, None)
        result = box["result"] or {"ok": False, "error": "empty reply"}
        result["status"] = 200
        # Complex-task gate: an accepted confirm carrying a gate nonce
        # activates that nonce for its (route, action) purpose.
        # 复杂任务门禁：用户确认且确认携带了门禁 nonce，则激活该 nonce。
        if command == "confirm" and result.get("ok"):
            nonce = str(payload.get("confirm_nonce", ""))
            if nonce and (result.get("data") or {}).get("confirmed") is True:
                with self._lock:
                    meta = self._confirm_tokens.get(nonce)
                    if meta is not None and meta["expires"] > time.time():
                        meta["confirmed"] = True
        # Route changes are worth persisting to the registry right away so
        # list_instances reflects where the operator currently is.
        if command in ("state", "navigate"):
            data = result.get("data") or {}
            route = data.get("route") or {}
            if isinstance(route, dict) and route.get("name"):
                with self._lock:
                    if self._agent_info:
                        self._agent_info["route"] = str(route.get("name", ""))
                        self._agent_info["routePath"] = str(route.get("path", ""))
                        self._agent_info["lastSeen"] = time.time()
                        self._write_registry(self._agent_info)
        return result

    def run_task(
        self,
        route: str,
        params: dict[str, Any],
        timeout_s: int,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Run one backend task through the UI's own handler chain.

        Desktop mode reuses the shared asyncio loop via _handle_submit with a
        queue-backed sink; web single-port mode has no shared loop, so the
        handler is awaited on a private loop exactly like the inline /ws loop
        does (session fields injected the same way).
        """
        if not self.enabled:
            return self._reject(403, "agent bridge disabled")
        if not self._check_token(headers):
            return self._reject(401, "bad or missing X-Agent-Token")
        if not re.match(r"^[a-z0-9_]{1,64}$", route or ""):
            return self._reject(400, "invalid route name")
        known = {r.removeprefix("/api/") for r in getattr(self.ws_service, "routes", {})}
        if route not in known:
            return self._reject(404, f"unknown route: {route}")
        timeout_s = max(1, min(int(timeout_s or 60), MAX_TASK_TIMEOUT_S))
        params = dict(params) if isinstance(params, dict) else {}

        # Complex-task gate (see COMPLEX_TASK_GATES): refuse until the agent
        # has asked the user via confirm and the user accepted. A user-provided
        # PONI (valid poni_path in params) answers the geometry facts itself,
        # so calibration's question list shrinks to what remains.
        # 复杂任务门禁：agent 未通过 confirm 获得用户确认前一律拒绝。用户提供的
        # PONI（params 带有效 poni_path）本身即几何事实，标定问题集相应缩减。
        gate = COMPLEX_TASK_GATES.get(route)
        if gate is not None:
            action = str(params.get("action", ""))
            gated_actions = gate.get("actions")
            if gated_actions is None or action in gated_actions:
                # A user-provided PONI only shrinks the list when this gate
                # actually declares a poni-reduced set (transmission does not).
                # 只有门禁真正声明了 PONI 精简集才缩减（transmission 没有）。
                poni_ok = _poni_provided(params) and bool(gate.get("questions_poni"))
                raw_questions = gate.get(
                    "questions_poni" if poni_ok else "questions",
                    [],
                )
                if not self._consume_confirmation(route, action, str(params.get("_agent_confirm", ""))):
                    fresh = self._mint_confirmation(route, action)
                    params.pop("_agent_confirm", None)
                    reply: dict[str, Any] = {
                        "ok": False,
                        "status": 200,
                        "code": "need_user_input",
                        "error": (
                            f"复杂任务已拦截（route={route}"
                            + (f" action={action}" if action else "")
                            + "）：必须先通过 confirm 命令向用户提问，用户在应用内确认后方可重试"
                        ),
                        "why": str(gate.get("why", "")),
                        "questions": [
                            f"{_QUESTION_MARKS[i]} {q}" if i < len(_QUESTION_MARKS) else f"{i + 1}. {q}"
                            for i, q in enumerate(str(q) for q in raw_questions)
                        ],
                        "confirm_nonce": fresh,
                        "how_to": (
                            "① 调用 confirm 命令（MCP: xfais_confirm），message 把 questions "
                            "逐条转述给用户并附你的执行计划，同时携带 confirm_nonce="
                            + fresh
                            + "；② 用户点击「确认」后令牌激活（10 分钟内有效，单次使用）；"
                            "③ 重新发起本任务，params 里带 _agent_confirm="
                            + fresh
                            + "。禁止未经用户确认重试、换路由或换命令绕过。"
                        ),
                    }
                    if poni_ok:
                        reply["poni_accepted"] = True
                        note = str(gate.get("poni_note", ""))
                        if note:
                            reply["poni_note"] = note
                    return reply
        params.pop("_agent_confirm", None)  # internal field never reaches handlers

        task_id = uuid.uuid4().hex
        sink = _TaskSink()
        loop = getattr(self.ws_service, "_loop", None)

        if loop is not None:
            message = {
                "type": "task_submit",
                "task_id": task_id,
                "route": f"/api/{route}",
                "payload": params,
            }

            async def _submit() -> None:
                await self.ws_service._handle_submit(sink, message)

            fut = asyncio.run_coroutine_threadsafe(_submit(), loop)
            try:
                fut.result(timeout=5)
            except Exception as exc:
                return self._reject(503, f"task submit failed: {exc}")
        else:
            # Web single-port mode: mirror the inline /ws loop — create a
            # session, inject isolation fields, await the handler directly.
            session_id = ""
            if getattr(self.ws_service, "session_manager", None) is not None:
                session_id = self.ws_service.session_manager.create_session()
            payload = dict(params)
            payload["_session_id"] = session_id
            payload["_session_tmp_dir"] = (
                self.ws_service.session_manager.get_tmp_dir(session_id)
                if session_id
                else ""
            )
            handler_fn = self.ws_service.routes.get(f"/api/{route}")
            cancel_event = asyncio.Event()
            private_loop = asyncio.new_event_loop()
            try:

                async def _run_direct() -> None:
                    async def send_progress(progress: float, message: str = "") -> None:
                        await sink.send(
                            json.dumps(
                                {
                                    "type": "task_progress",
                                    "task_id": task_id,
                                    "progress": progress,
                                    "message": message,
                                }
                            )
                        )

                    result = await handler_fn(payload, send_progress, cancel_event)
                    await sink.send(
                        json.dumps({"type": "task_complete", "task_id": task_id, "result": result})
                    )

                private_loop.run_until_complete(_run_direct())
            except Exception as exc:
                return {"ok": False, "status": 200, "error": f"task failed: {exc}"}
            finally:
                private_loop.close()
                if session_id and getattr(self.ws_service, "session_manager", None) is not None:
                    self.ws_service.session_manager.destroy_session(session_id)

        deadline = time.time() + timeout_s
        result: dict[str, Any] | None = None
        progress: list[dict[str, Any]] = []
        binaries: list[str] = []
        while time.time() < deadline:
            if not sink.frames:
                time.sleep(0.05)
                continue
            kind, frame = sink.frames.pop(0)
            if kind == "binary":
                binaries.append(base64.b64encode(frame).decode("ascii"))
                continue
            try:
                data = json.loads(frame)
            except (TypeError, ValueError):
                continue
            msg_type = data.get("type")
            if msg_type == "task_progress":
                progress.append(
                    {"progress": data.get("progress"), "message": data.get("message", "")}
                )
            elif msg_type in ("task_result", "task_complete"):
                result = data
                break
            elif msg_type == "task_error":
                return {
                    "ok": False,
                    "status": 200,
                    "error": data.get("error", "task failed"),
                    "code": data.get("code"),
                }
        if result is None:
            return self._reject(504, "task timed out")
        payload_out = result.get("data") if isinstance(result.get("data"), dict) else None
        if payload_out is None:
            payload_out = result.get("result") if isinstance(result.get("result"), dict) else {}
        # Binary frames stay base64; large payloads are the agent's problem to
        # slice, but cap the JSON we hand back to keep MCP responses sane.
        return {
            "ok": True,
            "status": 200,
            "data": payload_out,
            "binaries": binaries[:4],
            "progress": progress[-5:],
        }

    # ── Complex-task gate nonces ─────────────────────────────────────────────

    def _mint_confirmation(self, route: str, action: str) -> str:
        """Mint a single-use gate nonce bound to (route, action); purge stale."""
        nonce = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            for key in [k for k, m in self._confirm_tokens.items() if m["expires"] <= now]:
                self._confirm_tokens.pop(key, None)
            self._confirm_tokens[nonce] = {
                "route": route,
                "action": action,
                "expires": now + CONFIRM_TTL_S,
                "confirmed": False,
            }
        return nonce

    def _consume_confirmation(self, route: str, action: str, nonce: str) -> bool:
        """Consume a nonce that was activated by an accepted user confirm."""
        if not nonce:
            return False
        with self._lock:
            meta = self._confirm_tokens.pop(nonce, None)
        return bool(
            meta
            and meta["confirmed"]
            and meta["route"] == route
            and meta["action"] == action
        )

    # ── Instance registry ────────────────────────────────────────────────────

    def _registry_path(self) -> Path:
        return _registry_dir() / f"{os.getpid()}.json"

    def _write_registry(self, info: dict[str, Any]) -> None:
        if not self.enabled:
            return
        try:
            path = self._registry_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        except OSError:
            # Registry is best-effort — a read-only home must not break the app.
            pass

    def _remove_registry(self) -> None:
        try:
            self._registry_path().unlink(missing_ok=True)
        except OSError:
            pass

    def shutdown(self) -> None:
        self._remove_registry()


def agent_bridge_from_env(
    ws_service: Any, *, http_port: int, ws_port: int | None, mode: str
) -> AgentBridge:
    """Build a bridge honouring the enable/token environment variables."""
    raw = os.environ.get(ENV_ENABLE, "").strip().lower()
    if mode == "web":
        enabled = raw == "1" or raw in ("true", "yes", "on")
    else:
        enabled = raw not in ("0", "false", "no", "off")
    return AgentBridge(
        ws_service,
        http_port=http_port,
        ws_port=ws_port,
        mode=mode,
        enabled=enabled,
        token=os.environ.get(ENV_TOKEN, "").strip(),
    )
