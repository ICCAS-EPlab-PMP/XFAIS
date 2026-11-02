#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xfais-mcp — MCP server for operating a running X-FAIS instance.

Lets AI agents (ZCode / Claude Code / Codex / anything MCP-capable) observe
and operate X-FAIS in real time:

  * ``list_instances`` — every running X-FAIS on this machine registers itself
    in ``~/.xfais/instances/``; with several windows open the agent can tell
    them apart (pid, port, version, AI flag, current route) and address each.
  * ``get_state`` / ``screenshot`` — live UI state and canvas captures (the
    screenshot comes back as MCP image content, so vision-capable agents can
    judge things like beam-spot centring directly).
  * ``click`` / ``highlight`` / ``confirm`` / ``navigate`` / ``apply_options``
    — operate the UI: click buttons or canvas coordinates, spotlight a control,
    ask the user to confirm a KEY action in-app (nothing destructive happens
    without a human click), switch pages, pre-select module options.
  * ``run_task`` — run a backend task (integration, calibration, fitting…)
    through the exact same handler chain as the UI. Complex tasks (beam-centre
    search, geometry refinement, transmission) are GATED: the app refuses with
    ``need_user_input`` until the agent asked the user via ``confirm`` and the
    user clicked 确认 (single-use nonce flow) — the agent cannot silently guess
    user-supplied facts.
  * ``run_cli`` — run the bundled pyFAI-style CLI (``python/xfais_cli.py``) on
    the local machine with the instance's own interpreter, discovered from the
    instance registry; batch computation without any UI round trip.

The instance is never restarted or closed by the agent — commands flow over a
persistent link, one call per tool invocation.

Outbound-request security (SSRF model):
  * http/https schemes only; redirects are refused (a 3xx can never hop the
    request somewhere else); link-local / reserved addresses are blocked.
  * Loopback targets are always allowed — local desktop instances ARE the
    intended destination and register themselves as 127.0.0.1.
  * Every NON-loopback target must exactly match an operator-configured base
    URL in the XFAIS_AGENT_TARGETS environment variable. The agent cannot
    point this server at arbitrary internal hosts.

Zero dependencies (Python ≥ 3.9 standard library only). Configure with env:

  XFAIS_AGENT_TARGETS  comma-separated base URLs of remote/web deployments
                       (local desktop instances are auto-discovered)
  XFAIS_AGENT_TOKEN    shared token when the deployment set XFAIS_AGENT_TOKEN

Usage (stdio):  python mcp_server.py
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "xfais-mcp", "version": "0.3.7"}
REGISTRY_DIR = Path.home() / ".xfais" / "instances"
HTTP_TIMEOUT_S = 70


# ── Outbound target validation (SSRF model) ───────────────────────────────────

def _configured_remote_bases() -> list[str]:
    return [raw.strip().rstrip("/") for raw in os.environ.get("XFAIS_AGENT_TARGETS", "").split(",") if raw.strip()]


def _validate_base(base: str) -> str:
    """Allow loopback always; non-loopback only when operator-configured.

    Refuses non-http(s) schemes, unresolved hosts, link-local/reserved
    addresses, and any non-loopback host that is not an exact entry of
    XFAIS_AGENT_TARGETS. Applied to EVERY outbound request, whichever side
    supplied the URL (tool argument, registry file, or default instance).
    """
    base = base.rstrip("/")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"invalid instance url (http/https only): {base!r}")
    hostname = parsed.hostname
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"cannot resolve instance host {hostname!r}: {exc}") from exc
    addresses = set()
    for info in infos:
        try:
            addresses.add(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    if not addresses:
        raise ValueError(f"instance host {hostname!r} resolved to no addresses")
    for ip in addresses:
        if ip.is_link_local or ip.is_reserved:
            raise ValueError(f"instance host {hostname!r} resolves to a blocked address ({ip})")
    if all(ip.is_loopback for ip in addresses):
        return base  # local X-FAIS instance — the bridge's intended target
    if base in _configured_remote_bases():
        return base  # operator-approved web deployment
    raise ValueError(
        f"non-loopback instance {base!r} is not configured — add it to the "
        "XFAIS_AGENT_TARGETS environment variable (operator action)"
    )


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Refuse redirects so a compromised endpoint cannot hop the request."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        raise urllib.error.URLError(f"redirect refused ({code})")


_OPENER = urllib.request.build_opener(_NoRedirects)


# ── Instance discovery ────────────────────────────────────────────────────────

def list_instances() -> list[dict[str, Any]]:
    """Local registry files + operator-configured remote targets."""
    found: list[dict[str, Any]] = []
    try:
        entries = sorted(REGISTRY_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        entries = []
    for path in entries:
        try:
            info = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(info, dict) and info.get("url"):
            found.append(info)
    for base in _configured_remote_bases():
        found.append(
            {
                "url": base,
                "mode": "remote",
                "ai": None,
                "route": "",
                "label": "configured target",
                "pid": None,
            }
        )
    return found


def default_url(explicit: str | None) -> tuple[str, dict[str, Any] | None]:
    """Pick the instance to talk to: explicit arg > newest local > configured."""
    if explicit:
        return _validate_base(explicit), None
    instances = list_instances()
    if not instances:
        raise RuntimeError(
            "no running X-FAIS found — open X-FAIS (AI build) first, or set "
            "XFAIS_AGENT_TARGETS for a web deployment"
        )
    first = instances[0]
    return _validate_base(str(first["url"])), first


# ── HTTP plumbing ─────────────────────────────────────────────────────────────

def _post(base: str, path: str, body: dict[str, Any], timeout: int = 65) -> dict[str, Any]:
    """POST JSON to a validated X-FAIS instance."""
    base = _validate_base(base)
    token = os.environ.get("XFAIS_AGENT_TOKEN", "").strip()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Agent-Token"] = token
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        base + path, data=data, headers=headers, method="POST"
    )
    try:
        with _OPENER.open(request, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8", "replace")
        except Exception:
            detail = ""
        return {"ok": False, "error": f"HTTP {exc.code}: {detail[:300]}"}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": f"cannot reach {base}: {exc.reason}"}


def _agent_command(base: str, command: str, payload: dict[str, Any], timeout_ms: int = 20_000) -> dict[str, Any]:
    return _post(
        base,
        "/api/agent_command",
        {"command": command, "payload": payload, "timeout_ms": timeout_ms},
        timeout=int(timeout_ms / 1000) + 10,
    )


# ── Situation rendering / 态势渲染（2026-10-27） ──────────────────────────────
#
# The renderer attaches a `context` block (route + workspace digest + guided-
# workflow position) to every command reply, and every MCP tool prints it as
# trailing SITUATION lines. The agent therefore learns "did it work, where am
# I, what's next" from the reply it already has — the follow-up get_state
# round trips were the main token sink. 渲染层在每次回复附态势，MCP 统一渲染
# 为尾部「态势」行——agent 从当次返回即知结果与下一步。


def _short(value: Any, limit: int = 48) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def _workspace_line(snap: Any) -> str | None:
    """One compact line from a workspace snapshot (filesCount/hasPoni/…)."""
    if not isinstance(snap, dict) or not snap:
        return None
    parts = [
        f"files={snap.get('filesCount')}",
        "poni=" + ("yes" if snap.get("hasPoni") else "no"),
        "canRun=" + ("yes" if snap.get("canRun") else "no"),
        f"phase={snap.get('phase')}",
    ]
    extras = snap.get("extras") or {}
    if isinstance(extras, dict):
        extras_s = " ".join(
            f"{k}={_short(v)}"
            for k, v in extras.items()
            if isinstance(v, (str, int, float, bool)) and v != ""
        )
        if extras_s:
            parts.append(extras_s)
    return " | ".join(parts)


def _guide_lines(guide: Any) -> list[str]:
    if not isinstance(guide, dict) or not guide.get("hasGuide"):
        return []
    position = guide.get("position")
    where = "全部步骤已完成" if position is None else f"第{position + 1}/{guide.get('total')}步"
    nxt = guide.get("next") or {}
    if nxt:
        anchor = nxt.get("aiId") or "-"
        if not nxt.get("anchorPresent"):
            anchor_state = "NOT-IN-DOM(该控件当前不在页面)"
        elif not nxt.get("enabled"):
            anchor_state = "GRAYED-OUT(前置条件未满足)"
        else:
            anchor_state = "ready"
        return [
            f"教程「{guide.get('title')}」: {where} → 下一步「{nxt.get('title')}」"
            f" ({anchor}, {anchor_state})"
        ]
    return [f"教程「{guide.get('title')}」: {where}"]


def _situation_lines(data: dict[str, Any]) -> list[str]:
    """SITUATION lines for any reply shape: a command reply (`context` block),
    a full state payload (route/guide/snapshots — e.g. navigate's reply), or a
    state fetched as a follow-up. Empty when nothing usable is present."""
    if not isinstance(data, dict):
        return []
    ctx = data.get("context")
    if not isinstance(ctx, dict):
        ctx = data
    route = ctx.get("route") or {}
    lines = [f"—— 态势 SITUATION —— {route.get('name')} {route.get('path')} 「{route.get('title')}」"]
    snap = ctx.get("snapshot")
    if not isinstance(snap, dict) or not snap:
        snaps = ctx.get("snapshots")
        if isinstance(snaps, dict):
            snap = snaps.get(str(route.get("name") or ""))
    workspace = _workspace_line(snap)
    if workspace:
        lines.append(f"workspace: {workspace}")
    lines.extend(_guide_lines(ctx.get("guide")))
    return lines


def _with_situation(data: dict[str, Any], text: str) -> list[dict[str, Any]]:
    """Tool result blocks: the tool's own text + trailing SITUATION lines."""
    blocks = [{"type": "text", "text": text}]
    situation = _situation_lines(data)
    if situation:
        blocks.append({"type": "text", "text": "\n".join(situation)})
    return blocks


# ── Tool implementations ──────────────────────────────────────────────────────

def _text_result(text: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": text}]


def tool_list_instances(_args: dict[str, Any]) -> list[dict[str, Any]]:
    instances = list_instances()
    lines = []
    for i, inst in enumerate(instances):
        label = inst.get("label") or ""
        lines.append(
            f"[{i}] {inst['url']}  pid={inst.get('pid')}  ai={inst.get('ai')}  "
            f"route={inst.get('route') or '?'}  v{inst.get('version') or '?'}  {label}"
        )
    if not lines:
        lines.append("no running X-FAIS instances (open the app, or set XFAIS_AGENT_TARGETS)")
    return _text_result("\n".join(lines))


def tool_get_state(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    result = _agent_command(base, "state", {})
    if not result.get("ok"):
        return _text_result(f"state failed: {result.get('error')}")
    data = result.get("data") or {}
    route = data.get("route") or {}
    canvases = data.get("canvases") or []
    lines = [
        f"X-FAIS v{data.get('version')} ({data.get('platform')}, AI build) — "
        f"route: {route.get('name')} {route.get('path')} 「{route.get('title')}」",
        f"locale: {data.get('locale')}  poni: {data.get('poniPath') or '(none)'}",
        f"canvases: {len(canvases)} "
        + "; ".join(
            f"#{c.get('index')} {c.get('cssWidth')}x{c.get('cssHeight')}css {c.get('role') or 'main'}"
            for c in canvases[:6]
        ),
    ]
    # Current-route workspace snapshot digest (the full per-route snapshots
    # stay in `data`, but printing them all was pure token waste).
    # 只打印当前模块的工作区摘要；全量留在 data（verbose 才回传 JSON）。
    snaps = data.get("snapshots") or {}
    workspace = _workspace_line(snaps.get(route.get("name")))
    if workspace:
        lines.append(f"workspace: {workspace}")
    other_snaps = [k for k in snaps.keys() if k != route.get("name")]
    if other_snaps:
        lines.append("其他模块快照已备: " + ", ".join(sorted(other_snaps)))
    lines.extend(_guide_lines(data.get("guide")))
    if data.get("hasManual"):
        lines.append(f"本模块有详细说明 → xfais_get_modules route={route.get('name')}（操作前必读）；分步教程 → xfais_get_guide")
    lines.append("提示：每次工具返回末尾都带「态势」行；verbose=true 才回传完整 JSON。")
    if args.get("verbose"):
        lines.append("")
        lines.append(json.dumps(data, ensure_ascii=False)[:9000])
    return [{"type": "text", "text": "\n".join(lines)}]


def tool_get_guide(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    payload: dict[str, Any] = {}
    if args.get("route"):
        payload["route"] = str(args["route"])
    result = _agent_command(base, "guide", payload)
    if not result.get("ok"):
        return _text_result(f"guide failed: {result.get('error')}")
    data = result.get("data") or {}
    if not data.get("hasGuide"):
        return _text_result(
            f"no guided tutorial for {data.get('routeName') or 'this route'} — read the module manual via "
            f"xfais_get_modules route={data.get('routeName') or ''}, describe the goal to the user, then use get_state + screenshot to operate"
        )
    position = data.get("position")
    head = (
        f"{data.get('title')} — module tutorial, {data.get('doneCount')}/{data.get('total')} steps done"
        + ("" if position is None else f", next = step {position + 1}")
    )
    if not data.get("applicable"):
        head += f"\nNOT APPLICABLE in the current mode: {data.get('note')}"
    lines = [head]
    for i, step in enumerate(data.get("steps") or []):
        flag = "done" if step.get("done") else "NEXT" if i == position else "todo"
        if step.get("aiId"):
            if not step.get("anchorPresent"):
                anchor = f"aiId {step.get('aiId')} (NOT in DOM right now)"
            elif not step.get("enabled"):
                anchor = f"aiId {step.get('aiId')} (GRAYED OUT — its preconditions are not met yet, usually the earlier steps)"
            else:
                anchor = f"aiId {step.get('aiId')}"
        else:
            anchor = "info"
        lines.append(f"[{flag}] {i + 1}. {step.get('title')} — {step.get('tip')} ({anchor})")
    # Manual digest: overview + workflow titles (full text via get_modules).
    # 说明摘要：概述 + 流程标题；全文经 get_modules route= 获取。
    caps = data.get("caps") or {}
    manual = caps.get("manual")
    if isinstance(manual, dict):
        lines.append("")
        lines.append(f"详细说明摘要「{caps.get('routeName')}」: {manual.get('overview')}")
        for s in manual.get("workflow") or []:
            lines.append(f"  · {s.get('title')}")
        lines.append("  （前提/产出/坑点/agent 提示全文 → xfais_get_modules route=%s）" % caps.get("routeName"))
    lines.append(
        "教学优先：不确定/缺信息时先向用户解释并 highlight 对应控件，让用户自己完成文件选择等操作；"
        "只有用户要求代做或动作安全（查询/加载）时才代替点击；运行/导出/覆盖必须先 xfais_confirm。"
    )
    blocks = [{"type": "text", "text": "\n".join(lines)}]
    situation = _situation_lines(data)
    if situation:
        blocks.append({"type": "text", "text": "\n".join(situation)})
    if args.get("verbose"):
        blocks.append({"type": "text", "text": json.dumps(data, ensure_ascii=False)[:9000]})
    return blocks


def _render_manual(manual: dict[str, Any]) -> list[str]:
    """The detailed manual as text: overview / 前提 / 流程 / 产出 / 坑点 / 提示."""
    lines: list[str] = []
    lines.append(f"概述: {manual.get('overview')}")
    inputs = manual.get("inputs") or []
    if inputs:
        lines.append("前提（开始前必须具备）:")
        lines.extend(f"  - {s}" for s in inputs)
    workflow = manual.get("workflow") or []
    if workflow:
        lines.append("流程（真实 UI 顺序）:")
        for i, s in enumerate(workflow):
            lines.append(f"  {i + 1}. {s.get('title')} — {s.get('detail')}")
    outputs = manual.get("outputs") or []
    if outputs:
        lines.append("产出与去向:")
        lines.extend(f"  - {s}" for s in outputs)
    pitfalls = manual.get("pitfalls") or []
    if pitfalls:
        lines.append("坑点:")
        lines.extend(f"  ! {s}" for s in pitfalls)
    tips = manual.get("agentTips") or []
    if tips:
        lines.append("给 agent 的提示（教学优先）:")
        lines.extend(f"  * {s}" for s in tips)
    return lines


def tool_get_modules(args: dict[str, Any]) -> list[dict[str, Any]]:
    """All-module directory (or one full card via `route`) + golden rules."""
    base, _inst = default_url(args.get("url"))
    payload: dict[str, Any] = {}
    if args.get("route"):
        payload["route"] = str(args["route"])
    result = _agent_command(base, "modules", payload)
    if not result.get("ok"):
        return _text_result(f"modules failed: {result.get('error')}")
    data = result.get("data") or {}
    module = data.get("module")
    if isinstance(module, dict):
        lines = [f"{module.get('routeName')} — {module.get('purpose') or module.get('title')}"]
        manual = module.get("manual")
        if isinstance(manual, dict):
            lines.append("")
            lines.extend(_render_manual(manual))
        capabilities = module.get("capabilities") or []
        if capabilities:
            lines.append("")
            lines.append("能力（速览）:")
            lines.extend(f"  • {cap}" for cap in capabilities)
        queries = module.get("liveQueries") or []
        if queries:
            lines.append("  实时查询（run_task 配方——查了再说，禁止凭记忆断言）:")
            for q in queries:
                lines.append(f"    - {q.get('note')}")
                lines.append(
                    f"      command={q.get('command')}  params={json.dumps(q.get('params') or {}, ensure_ascii=False)}"
                )
        related = module.get("related") or []
        if related:
            lines.append("  干不了时去哪:")
            for r in related:
                lines.append(f"    - {r.get('routeName')}: {r.get('note')}")
        kw = module.get("keywords") or []
        if kw:
            lines.append(f"  keywords: {', '.join(kw)}")
        blocks = [{"type": "text", "text": "\n".join(lines)}]
        situation = _situation_lines(data)
        if situation:
            blocks.append({"type": "text", "text": "\n".join(situation)})
        return blocks
    mods = data.get("modules") or []
    lines = [f"X-FAIS module directory ({len(mods)} modules)"]
    for m in mods:
        lines.append(f"- {m.get('routeName')} ({m.get('title')}) — {m.get('purpose')}")
    lines.append("")
    lines.append("单模块详细说明（操作前必读）: xfais_get_modules route=<routeName>")
    rule = data.get("rule")
    if rule:
        lines.append("")
        lines.append(str(rule))
    return [
        {"type": "text", "text": "\n".join(lines)},
        {"type": "text", "text": json.dumps(data, ensure_ascii=False)[:9000]},
    ]


def tool_screenshot(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    payload: dict[str, Any] = {}
    if "canvas" in args:
        payload["canvas"] = args["canvas"]
    payload["maxWidth"] = int(args.get("maxWidth", 1400))
    result = _agent_command(base, "capture", payload)
    if not result.get("ok"):
        return _text_result(f"capture failed: {result.get('error')}")
    data = result.get("data") or {}
    png_b64 = str(data.get("png", ""))
    if not png_b64:
        return _text_result("capture returned no image")
    blocks: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": f"canvas {data.get('width')}x{data.get('height')} px captured — use vision to inspect it (e.g. beam centre, ring positions, curve shape)",
        },
        {"type": "image", "data": png_b64, "mimeType": "image/png"},
    ]
    situation = _situation_lines(data)
    if situation:
        blocks.append({"type": "text", "text": "\n".join(situation)})
    return blocks


def tool_click(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    target: dict[str, Any] = {}
    for key in ("aiId", "testId", "text"):
        if args.get(key):
            target[key] = args[key]
    if "canvasX" in args and "canvasY" in args:
        target["canvas"] = {"x": float(args["canvasX"]), "y": float(args["canvasY"])}
        if "canvasIndex" in args:
            target["canvasIndex"] = int(args["canvasIndex"])
    if not target:
        return _text_result("click needs aiId | testId | text | canvasX+canvasY")
    result = _agent_command(base, "click", {"target": target})
    if not result.get("ok"):
        return _text_result(
            f"click failed: {result.get('error')} — 若是前置条件未满足，先读态势/教程并向用户解释，不要重试刷运气"
        )
    data = result.get("data") or {}
    return _with_situation(data, f"clicked: {json.dumps(data, ensure_ascii=False)}")


def tool_highlight(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    payload = {"aiId": str(args.get("aiId", ""))}
    if args.get("note"):
        payload["note"] = str(args["note"])
    result = _agent_command(base, "highlight", payload)
    if not result.get("ok"):
        return _text_result(f"highlight failed: {result.get('error')}")
    data = result.get("data") or {}
    return _with_situation(
        data, f"spotlighted {payload['aiId']} — the user sees it pulsing; pair with an explanation or confirm"
    )


def tool_confirm(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    payload = {"message": str(args.get("message", "确认执行该操作？"))}
    for key in ("aiId", "note"):
        if args.get(key):
            payload[key] = str(args[key])
    # Complex-task gate nonce (from run_task's need_user_input reply): an
    # accepted confirm carrying it ACTIVATES the nonce for the retry.
    # 复杂任务门禁 nonce（来自 run_task 的 need_user_input 应答）：用户确认
    # 即激活，随后凭它重试被拦截的任务。
    if args.get("confirmNonce"):
        payload["confirm_nonce"] = str(args["confirmNonce"])
    timeout_ms = int(args.get("timeout_s", 300)) * 1000
    result = _agent_command(base, "confirm", payload, timeout_ms=timeout_ms)
    if not result.get("ok"):
        return _text_result(f"confirm failed: {result.get('error')}")
    data = result.get("data") or {}
    verdict = "user CONFIRMED the action" if data.get("confirmed") else "user CANCELLED (or closed) the action"
    if data.get("confirmed") and payload.get("confirm_nonce"):
        verdict += (
            f" — gate nonce {payload['confirm_nonce']} is now ACTIVE: retry the "
            f"gated task with params._agent_confirm=\"{payload['confirm_nonce']}\""
        )
    return _with_situation(data, verdict)


def tool_navigate(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    result = _agent_command(base, "navigate", {"path": str(args.get("path", ""))})
    if not result.get("ok"):
        return _text_result(f"navigate failed: {result.get('error')}")
    data = result.get("data") or {}
    route = data.get("route") or {}
    head = f"navigated to {route.get('name')} {route.get('path')} 「{route.get('title')}」 — 模块说明: xfais_get_modules route={route.get('name')}"
    return _with_situation(data, head)


def tool_apply_options(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    options = args.get("options")
    if not isinstance(options, dict) or not args.get("routeName"):
        return _text_result("apply_options needs routeName + options object")
    result = _agent_command(
        base, "apply_options", {"routeName": str(args["routeName"]), "options": options}
    )
    if not result.get("ok"):
        return _text_result(f"apply_options failed: {result.get('error')}")
    data = result.get("data") or {}
    return _with_situation(
        data,
        "options dispatched — the view applies what it supports; 态势行确认当前模式/选项是否已生效（不生效时向用户说明，不要反复重试）",
    )


def tool_run_task(args: dict[str, Any]) -> list[dict[str, Any]]:
    base, _inst = default_url(args.get("url"))
    command = str(args.get("command", ""))
    if not re.match(r"^[a-z0-9_]{1,64}$", command):
        return _text_result("invalid command name")
    body: dict[str, Any] = {
        "command": command,
        "params": args.get("params") if isinstance(args.get("params"), dict) else {},
        "timeout_s": int(args.get("timeout_s", 120)),
    }
    result = _post(base, "/api/agent_task", body, timeout=body["timeout_s"] + 15)
    if result.get("code") == "need_user_input":
        # Complex-task gate: the app itself refuses to run until the user has
        # been asked and confirmed in-app. This is a HARD rule — render the
        # mandatory ask-first instructions instead of a bare failure.
        # 复杂任务门禁：应用侧直接拒绝，直到用户被提问并在应用内确认。
        # 这是硬规则——渲染"必须先问"的完整指引而非普通失败。
        lines = [
            "⛔ 复杂任务已被应用拦截 — 必须先向用户提问，用户在应用内点「确认」后才能执行。",
            f"原因: {result.get('why') or result.get('error')}",
        ]
        if result.get("poni_accepted"):
            lines.append(f"PONI 快速通道: {result.get('poni_note')}")
        lines.extend(f"必须向用户确认: {q}" for q in (result.get("questions") or []))
        nonce = str(result.get("confirm_nonce") or "")
        lines += [
            "强制流程（不要跳步，不要绕过）:",
            f"1) 调用 xfais_confirm：message 完整转述上述问题清单 + 你的执行计划，并传 confirmNonce=\"{nonce}\"",
            "2) 用户点击「确认」后令牌激活（10 分钟内有效，单次使用）",
            f"3) 重新调用 xfais_run_task，params 里加 \"_agent_confirm\": \"{nonce}\"",
            "未获用户确认前禁止重试、禁止换命令/换路由绕过。",
        ]
        return _text_result("\n".join(lines))
    if not result.get("ok"):
        return _text_result(f"task failed: {result.get('error')} ({result.get('code')})")
    data = result.get("data") or {}
    text = json.dumps(data, ensure_ascii=False)
    blocks = _text_result(f"task {command} ok — " + text[:4000])
    for png_b64 in (result.get("binaries") or [])[:1]:
        blocks.append({"type": "image", "data": png_b64, "mimeType": "image/png"})
    # Task replies end with a FRESH situation (state fetched after the task):
    # the workspace phase/files change as a result of the run, and the agent
    # needs that to decide the next step without another round trip.
    # 任务返回附带新鲜态势：运行后工作区已变化，agent 据此定下一步。
    state_result = _agent_command(base, "state", {}, timeout_ms=8_000)
    if state_result.get("ok"):
        situation = _situation_lines(state_result.get("data") or {})
        if situation:
            blocks.append({"type": "text", "text": "\n".join(situation)})
    return blocks


# ── CLI passthrough (pyFAI-style local commands, 2026-11-01) ─────────────────
#
# X-FAIS ships a pyFAI-flavoured CLI next to its backend (python/xfais_cli.py).
# The instance registry records the bundled interpreter + the CLI script path,
# so agents can run batch computation locally (info/poni/average/integrate/
# bgsubtract/transmission/lamellar/orientation) without any UI round trip.
# This tool is a thin, guarded wrapper: subcommand whitelist, string-only argv
# (no shell), bounded output, hard timeout. The agent may equally call the CLI
# itself via its own shell using the registry's python/cli paths.

CLI_SUBCOMMANDS = (
    "average",
    "bgsubtract",
    "info",
    "integrate",
    "lamellar",
    "orientation",
    "poni",
    "transmission",
    "version",
)
CLI_MAX_ARGS = 512
CLI_MAX_OUTPUT_BYTES = 512 * 1024
CLI_MAX_TIMEOUT_S = 900


def _local_cli_paths(inst: dict[str, Any] | None) -> tuple[str, str]:
    """(python, cli) paths from the given local registry entry or the newest."""
    candidates: list[dict[str, Any]] = []
    if isinstance(inst, dict) and inst.get("python"):
        candidates.append(inst)
    candidates.extend(list_instances())
    for candidate in candidates:
        python_path = str(candidate.get("python") or "")
        cli_path = str(candidate.get("cli") or "")
        if python_path and cli_path and os.path.isfile(cli_path):
            return python_path, cli_path
    raise RuntimeError(
        "no local X-FAIS instance with CLI info found — open X-FAIS (AI build "
        "v0.3.5+) once; its registry entry in ~/.xfais/instances/*.json carries "
        "the python/cli paths"
    )


def tool_run_cli(args: dict[str, Any]) -> list[dict[str, Any]]:
    sub = str(args.get("command", "")).strip()
    if sub not in CLI_SUBCOMMANDS:
        return _text_result(
            f"unknown CLI subcommand: {sub!r} (allowed: {', '.join(CLI_SUBCOMMANDS)})"
        )
    cli_args = args.get("args")
    if cli_args is None:
        cli_args = []
    if (
        not isinstance(cli_args, list)
        or len(cli_args) > CLI_MAX_ARGS
        or not all(isinstance(a, str) for a in cli_args)
    ):
        return _text_result("args must be an array of strings (≤512 entries)")
    try:
        base, inst = default_url(args.get("url"))
    except Exception as exc:
        return _text_result(str(exc))
    try:
        python_path, cli_path = _local_cli_paths(inst)
    except RuntimeError as exc:
        return _text_result(str(exc))
    timeout_s = max(1, min(int(args.get("timeout_s", 300)), CLI_MAX_TIMEOUT_S))
    argv = [python_path, cli_path, sub, *cli_args]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return _text_result(f"CLI timed out after {timeout_s}s: xfais {sub} …")
    except OSError as exc:
        return _text_result(f"failed to launch CLI: {exc}")
    out = (proc.stdout or "")[-CLI_MAX_OUTPUT_BYTES:]
    err = (proc.stderr or "")[-CLI_MAX_OUTPUT_BYTES:]
    parts = [f"$ xfais {sub} (exit={proc.returncode})", out]
    if err.strip():
        parts.append("[stderr]\n" + err)
    return _text_result("\n".join(parts))


# ── Tool schema ───────────────────────────────────────────────────────────────

TOOL_BEHAVIOR_NOTE = (
    "Every tool reply ends with SITUATION lines (当前页面/工作区/教程位置与下一步) — "
    "read them before acting; they save a follow-up get_state round trip. "
    "TEACH FIRST: when information is missing, read the module manual "
    "(xfais_get_modules route=<name>), explain to the user and spotlight controls "
    "instead of blindly clicking; act on the user's behalf only when asked or when "
    "the action is safe (query/load), and confirm before run/export/overwrite. "
    "COMPLEX-TASK GATE (hard rule): calibration tasks (set_center/refine/"
    "ring_standard) and ALL transmission tasks are gated by the app — "
    "when run_task replies code=need_user_input you MUST ask the user the listed "
    "questions via xfais_confirm (carrying its confirm_nonce), and only after the "
    "user clicks 确认 retry with params._agent_confirm=<nonce>. PONI fast-path: "
    "a user-provided .poni passed as params.poni_path waives the geometry "
    "questions of calibration automatically (sample type & image import still "
    "need the user). Never retry, guess the missing facts, or switch commands "
    "to bypass the gate."
)

_URL_DESC = "Base URL of the X-FAIS instance (omit = newest local instance; non-loopback URLs must be operator-configured)"

TOOLS: list[dict[str, Any]] = [
    {
        "name": "xfais_list_instances",
        "description": "List every running X-FAIS instance on this machine (pid, port, route, AI flag). Call this first when several windows are open.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "xfais_get_state",
        "description": "Live state of an instance: current route/page, locale, version, canvases (sizes for coordinate clicks), CURRENT module's workspace digest, PONI path, and a guide briefing (where the user is in the module's tutorial + the next step). Output is compact by design — the raw JSON needs verbose=true. Also: EVERY tool reply ends with SITUATION lines, so you rarely need repeat get_state calls.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "verbose": {"type": "boolean", "description": "append the full state JSON (default false — compact text only, saves tokens)"},
            },
        },
    },
    {
        "name": "xfais_get_guide",
        "description": "The current module's internal tutorial + capability card: ordered steps, what each control does (zh), each step's live done-flag (= the user's current position — they may have clicked ahead), whether its anchor is in the DOM, and whether it is ENABLED or still grayed out (preconditions unmet — do not click, tell the user what to do first). Ends with a manual digest (overview + workflow titles); the FULL manual is xfais_get_modules route=<name>. Call before operating an unfamiliar module; another route's guide via `route`.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "route": {"type": "string", "description": "routeName (default: current route)"},
                "verbose": {"type": "boolean", "description": "append the full serialized JSON (default false)"},
            },
        },
    },
    {
        "name": "xfais_get_modules",
        "description": "Module directory: every X-FAIS module with its purpose + routing keywords (answers 'which module handles this request?'). With `route`: that module's FULL card — DETAILED MANUAL (概述/前提/真实流程/产出/坑点/给 agent 的教学提示 — read before operating), capabilities, LIVE-QUERY recipes (facts like calibrant/detector lists are queryable via run_task — query, never guess) and related modules. GOLDEN RULE 1 (anti-hallucination): never claim X-FAIS 'has no X / cannot do X' before running the relevant live query — lists are machine-specific (users add *_custom entries), only the query result is authoritative. GOLDEN RULE 2 (teach first): when unsure, teach — explain + highlight, don't blind-click. " + TOOL_BEHAVIOR_NOTE,
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "route": {"type": "string", "description": "routeName for one full card (omit = whole directory)"},
            },
        },
    },
    {
        "name": "xfais_screenshot",
        "description": "Capture the current main canvas as PNG (returned as an image you can read with vision) — judge beam centre, rings, curves, overlays. Reply ends with SITUATION lines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "canvas": {"type": ["integer", "string"], "description": "canvas index or 'largest' (default largest)"},
                "maxWidth": {"type": "integer", "description": "downscale cap in px (default 1400)"},
            },
        },
    },
    {
        "name": "xfais_click",
        "description": "Click a control or a canvas point. Buttons: aiId / testId / visible text. Images: canvasX+canvasY in CSS pixels from get_state. TEACH FIRST: if a target is missing/grayed out or you are unsure what it does, read xfais_get_guide / xfais_get_modules, EXPLAIN to the user and xfais_highlight instead of retrying clicks. Reply ends with SITUATION lines (did it work, what's next).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "aiId": {"type": "string"},
                "testId": {"type": "string"},
                "text": {"type": "string", "description": "visible button text (substring match)"},
                "canvasX": {"type": "number"},
                "canvasY": {"type": "number"},
                "canvasIndex": {"type": "integer"},
            },
        },
    },
    {
        "name": "xfais_highlight",
        "description": "Spotlight (pulse) a control by its data-ai-id so the user sees where to act. Non-blocking — pair it with a one-sentence explanation (teach first). Reply ends with SITUATION lines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "aiId": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": ["aiId"],
        },
    },
    {
        "name": "xfais_confirm",
        "description": "Ask the user to confirm a KEY action in-app (modal + optional spotlight). Blocks until the user clicks 确认/取消. Use before running/exporting/overwriting — and it is MANDATORY for gated complex tasks (run_task replies need_user_input): pass the confirmNonce from that reply, put the required questions in message, and after the user confirms retry with params._agent_confirm=<nonce>. Reply ends with SITUATION lines.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "message": {"type": "string", "description": "what the agent wants to do (shown to the user); for gated tasks include every listed question"},
                "aiId": {"type": "string"},
                "note": {"type": "string"},
                "confirmNonce": {"type": "string", "description": "gate nonce from a run_task need_user_input reply — an accepted confirm activates it"},
                "timeout_s": {"type": "integer", "description": "default 300"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "xfais_navigate",
        "description": "Navigate the instance to an in-app path (e.g. /workspace/calibration, /workspace/curve-fitting). Reply includes the new route's workspace digest + tutorial position, and points at the module manual.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "path": {"type": "string"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "xfais_apply_options",
        "description": "Pre-select module options from the module vocabulary (calibration mode: calibrant|internal|com; orientation methods list; …). Views validate their own state first. Reply ends with SITUATION lines so you can verify the option took effect.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "routeName": {"type": "string"},
                "options": {"type": "object"},
            },
            "required": ["routeName", "options"],
        },
    },
    {
        "name": "xfais_run_task",
        "description": "Run a backend task by command name (e.g. integrate1d, calibration, curve_fitting, orientation_analysis) with its params dict — same handlers as the UI. Complex tasks (calibration set_center/refine/ring_standard, all transmission) are GATED: the reply carries code=need_user_input + questions + confirm_nonce — ask the user via xfais_confirm, then retry with params._agent_confirm=<nonce>. PONI FAST-PATH: when the USER provided a .poni, pass its absolute path as params.poni_path — calibration's geometry questions (detector/wavelength/distance/centre) are waived automatically (load it first via the ungated calibration action seed_from_poni). Confirm with the user first for long jobs. On success the reply ends with a FRESH SITUATION (state re-fetched after the task) so you can decide the next step immediately.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": _URL_DESC},
                "command": {"type": "string"},
                "params": {"type": "object"},
                "timeout_s": {"type": "integer", "description": "default 120"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "xfais_run_cli",
        "description": "Run X-FAIS's bundled pyFAI-style CLI on the LOCAL machine (the instance's own Python runtime, paths from ~/.xfais/instances) — batch computation with no UI round trip. Subcommands: info (file probe) / poni (geometry summary) / average (multi-image mean/median/min/max/sum) / integrate (1D with .poni → column text, pyFAI-waxs/saxs style) / bgsubtract (reference subtraction, optional ionchamber matching) / transmission (direct-beam region ratios) / lamellar / orientation (curve analyses → JSON) / version. args = raw CLI tokens, wildcards like \"D:/data/*.edf\" are expanded by the CLI itself. Prefer a user-visible output folder; long jobs: confirm first (xfais_confirm).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "CLI subcommand", "enum": list(CLI_SUBCOMMANDS)},
                "args": {"type": "array", "items": {"type": "string"}, "description": "raw CLI tokens, e.g. [\"-p\", \"x.poni\", \"--unit\", \"q_nm^-1\", \"D:/data/*.edf\"]"},
                "timeout_s": {"type": "integer", "description": "default 300, cap 900"},
                "url": {"type": "string", "description": _URL_DESC},
            },
            "required": ["command"],
        },
    },
]

TOOL_IMPLS: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {
    "xfais_list_instances": tool_list_instances,
    "xfais_get_state": tool_get_state,
    "xfais_get_modules": tool_get_modules,
    "xfais_get_guide": tool_get_guide,
    "xfais_screenshot": tool_screenshot,
    "xfais_click": tool_click,
    "xfais_highlight": tool_highlight,
    "xfais_confirm": tool_confirm,
    "xfais_navigate": tool_navigate,
    "xfais_apply_options": tool_apply_options,
    "xfais_run_task": tool_run_task,
    "xfais_run_cli": tool_run_cli,
}


# ── Minimal MCP stdio JSON-RPC loop ──────────────────────────────────────────

def handle_request(msg: dict[str, Any]) -> dict[str, Any] | None:
    method = str(msg.get("method", ""))
    msg_id = msg.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        name = str((msg.get("params") or {}).get("name", ""))
        impl = TOOL_IMPLS.get(name)
        if impl is None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": f"unknown tool: {name}"}], "isError": True},
            }
        args = (msg.get("params") or {}).get("arguments") or {}
        try:
            content = impl(args if isinstance(args, dict) else {})
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"content": content}}
        except Exception as exc:  # surface tool errors to the agent, never crash the server
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}], "isError": True},
            }
    # notifications (no id) must not get a reply
    if msg_id is None:
        return None
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"method not found: {method}"}}


def main() -> int:
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    for raw_line in stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            continue
        if not isinstance(msg, dict):
            continue
        reply = handle_request(msg)
        if reply is not None:
            stdout.write(json.dumps(reply, ensure_ascii=False).encode("utf-8") + b"\n")
            stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
