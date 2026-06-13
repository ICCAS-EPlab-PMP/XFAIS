#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_service_framework.py — WebSocket service framework tests
test_service_framework.py — WebSocket 服务框架测试
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading

import pytest

from python.service_launcher import (
    API_ROUTES,
    WebSocketService,
    stub_route_handler,
)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _slow_handler(payload, send_progress, cancel_event):
    """Handler that runs slowly for cancellation testing."""
    await send_progress(0.0, "Starting slow task...")
    for i in range(50):
        if cancel_event.is_set():
            raise asyncio.CancelledError("Task was cancelled")
        await asyncio.sleep(0.05)
        await send_progress((i + 1) / 50, f"Step {i + 1}/50")
    return {"status": "completed"}


async def _error_handler(payload, send_progress, cancel_event):
    """Handler that raises an error."""
    await send_progress(0.0, "About to fail...")
    raise ValueError("Deliberate test error")


@pytest.fixture()
def ws_server():
    """Start a WebSocketService on a free port with all stub routes registered."""
    service = WebSocketService()
    for route in API_ROUTES:
        service.register_route(route, stub_route_handler)
    service.register_route("/api/test/slow", _slow_handler)
    service.register_route("/api/test/error", _error_handler)

    port = _find_free_port()

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(service.start("127.0.0.1", port))
        except Exception:
            pass

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    assert service.ready.wait(timeout=5), "WebSocket server did not start in time"

    yield service, port

    service.stop()
    thread.join(timeout=5)


def _ws_client(port: int):
    """Return an async function that connects and runs a test scenario."""
    import websockets

    async def connect():
        return websockets.connect(f"ws://127.0.0.1:{port}")

    return connect


def test_ws_connect(ws_server):
    """WebSocket 客户端能成功连接 / Client can connect to WebSocket server."""
    service, port = ws_server

    async def go():
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # websockets >=13 uses .state instead of .open
            assert ws.state.name == 'OPEN' if hasattr(ws, 'state') else ws.open is True

    asyncio.run(go())


def test_ws_submit_task(ws_server):
    """提交任务后收到 accepted + progress + complete / Submit yields accepted, progress, complete."""
    service, port = ws_server

    async def go():
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "type": "task_submit",
                "task_id": "t1",
                "route": "/api/integrate1d",
                "payload": {"test": True},
            }))

            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "task_accepted"
            assert msg["task_id"] == "t1"

            messages: list[dict] = []
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                messages.append(msg)
                if msg["type"] in ("task_complete", "task_error"):
                    break

            progress_msgs = [m for m in messages if m["type"] == "task_progress"]
            assert len(progress_msgs) >= 3

            complete = [m for m in messages if m["type"] == "task_complete"]
            assert len(complete) == 1
            assert complete[0]["result"]["status"] == "ok"

    asyncio.run(go())


def test_ws_progress_events(ws_server):
    """进度事件递增且包含消息 / Progress events are increasing and carry messages."""
    service, port = ws_server

    async def go():
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "type": "task_submit",
                "task_id": "prog-1",
                "route": "/api/integrate_cake",
                "payload": {},
            }))

            messages: list[dict] = []
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                messages.append(msg)
                if msg["type"] in ("task_complete", "task_error"):
                    break

            progress = [m for m in messages if m["type"] == "task_progress"]
            assert len(progress) >= 3
            values = [m["progress"] for m in progress]
            assert values == sorted(values)
            for p in progress:
                assert isinstance(p["message"], str)

    asyncio.run(go())


def test_ws_cancel_task(ws_server):
    """取消运行中的任务收到 task_cancelled / Cancelling a task yields task_cancelled."""
    service, port = ws_server

    async def go():
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "type": "task_submit",
                "task_id": "cancel-1",
                "route": "/api/test/slow",
                "payload": {},
            }))

            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "task_accepted"

            await asyncio.sleep(0.15)

            await ws.send(json.dumps({
                "type": "task_cancel",
                "task_id": "cancel-1",
            }))

            messages: list[dict] = []
            while True:
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                    messages.append(msg)
                    if msg["type"] in ("task_cancelled", "task_error", "task_complete"):
                        break
                except asyncio.TimeoutError:
                    break

            cancelled = [m for m in messages if m["type"] == "task_cancelled"]
            assert len(cancelled) == 1
            assert cancelled[0]["task_id"] == "cancel-1"

    asyncio.run(go())


def test_ws_error_unknown_route(ws_server):
    """未知路由返回 ROUTE_NOT_FOUND / Unknown route returns ROUTE_NOT_FOUND."""
    service, port = ws_server

    async def go():
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "type": "task_submit",
                "task_id": "err-route",
                "route": "/api/nonexistent",
                "payload": {},
            }))

            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg["type"] == "task_error"
            assert msg["task_id"] == "err-route"
            assert msg["code"] == "ROUTE_NOT_FOUND"

    asyncio.run(go())


def test_ws_error_handler_exception(ws_server):
    """处理函数抛出异常时返回 INTERNAL_ERROR / Handler exception yields INTERNAL_ERROR."""
    service, port = ws_server

    async def go():
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "type": "task_submit",
                "task_id": "err-handler",
                "route": "/api/test/error",
                "payload": {},
            }))

            messages: list[dict] = []
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                messages.append(msg)
                if msg["type"] in ("task_error", "task_complete"):
                    break

            errors = [m for m in messages if m["type"] == "task_error"]
            assert len(errors) == 1
            assert errors[0]["code"] == "INTERNAL_ERROR"
            assert "Deliberate test error" in errors[0]["error"]

    asyncio.run(go())


def test_ws_shutdown():
    """服务可以被干净地关闭 / Service can be shut down cleanly."""
    service = WebSocketService()
    service.register_route("/api/integrate1d", stub_route_handler)

    port = _find_free_port()

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(service.start("127.0.0.1", port))
        except Exception:
            pass

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    assert service.ready.wait(timeout=5)

    async def connect_and_verify():
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            assert ws.state.name == 'OPEN' if hasattr(ws, 'state') else ws.open is True

    asyncio.run(connect_and_verify())

    service.stop()
    thread.join(timeout=5)

    async def try_connect_after_shutdown():
        import websockets

        try:
            async with websockets.connect(f"ws://127.0.0.1:{port}", close_timeout=1):
                return False
        except (ConnectionRefusedError, OSError, Exception):
            return True

    assert asyncio.run(try_connect_after_shutdown())
