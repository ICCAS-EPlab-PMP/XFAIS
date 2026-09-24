#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_web_session_cleanup.py — serve_web regression tests.

Covers two web-mode fixes:
1. WebSocket disconnect must destroy the session (pop + rmtree its temp dir).
   Regression guard for the AttributeError path that used to call the
   non-existent SessionManager.remove_session on every disconnect, leaking
   one xfais_session_* temp dir per connection.
2. HTML responses (index.html + SPA fallback) must carry Cache-Control:
   no-cache while hashed assets stay immutable.
覆盖两个 web 模式修复：
1. WebSocket 断开必须销毁 session（弹出并 rmtree 其临时目录）——回归防护
   曾因调用不存在的 SessionManager.remove_session 导致每次断开泄漏一个
   xfais_session_* 临时目录的缺陷。
2. HTML 响应（index.html 与 SPA fallback）必须带 Cache-Control: no-cache，
   哈希资源保持 immutable。
"""

from __future__ import annotations

import base64
import http.client
import json
import os
import socket
import struct
import tempfile
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import python.service_launcher as sl


# ---------------------------------------------------------------------------
# Server fixture — mirrors run_web_server's wiring without its serve_forever
# ---------------------------------------------------------------------------


class _WebServer:
    def __init__(self, dist_dir: str) -> None:
        self.session_manager = sl.SessionManager()
        self._prev_ws_service = sl._ws_service
        sl._ws_service = sl.WebSocketService(session_manager=self.session_manager)
        handler = type("TestWebHandler", (sl.WebHealthHandler,), {
            "expected_python": "3",
            "requirements_lock": "",
            "ws_port": None,
            "cached_report": None,
            "dist_dir": dist_dir,
        })
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def start(self) -> "_WebServer":
        self.thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        sl._ws_service = self._prev_ws_service


@pytest.fixture()
def web_server(tmp_path: Path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>entry</html>", encoding="utf-8")
    (dist / "assets" / "app-abc123.js").write_text("console.log(1)", encoding="utf-8")
    server = _WebServer(str(dist)).start()
    try:
        yield server
    finally:
        server.stop()


def _wait_until(condition, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.1)
    raise AssertionError("condition not met within timeout")


# ---------------------------------------------------------------------------
# 1. WebSocket session cleanup on disconnect
# ---------------------------------------------------------------------------


def _read_ws_frame(makefile) -> tuple[int, bytes]:
    header = makefile.read(2)
    assert len(header) == 2, "connection closed mid-frame"
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack("!H", makefile.read(2))[0]
    elif length == 127:
        length = struct.unpack("!Q", makefile.read(8))[0]
    return opcode, makefile.read(length)


def test_ws_disconnect_destroys_session_and_tmp_dir(web_server: _WebServer) -> None:
    """断开后 session 与临时目录必须被清理 / Disconnect must clean both."""
    sm = web_server.session_manager
    before = sm.active_count
    sessions_before = {
        os.path.basename(p)
        for p in _session_dirs()
    }

    sock = socket.create_connection(("127.0.0.1", web_server.port), timeout=10)
    try:
        sock.settimeout(10)
        key = base64.b64encode(os.urandom(16)).decode()
        sock.sendall((
            f"GET /ws HTTP/1.1\r\n"
            f"Host: 127.0.0.1:{web_server.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        ).encode())

        stream = sock.makefile("rb")
        status = stream.readline()
        assert b"101" in status, status
        while True:  # drain remaining handshake headers
            line = stream.readline()
            if line in (b"\r\n", b""):
                break

        opcode, payload = _read_ws_frame(stream)
        assert opcode == 0x01
        session_id = json.loads(payload.decode("utf-8"))["session_id"]

        tmp_dir = sm.get_session(session_id)["tmp_dir"]
        assert os.path.isdir(tmp_dir), "session temp dir should exist while connected"
        assert sm.active_count == before + 1

        # Client close frame (masked, as RFC 6455 requires from clients).
        mask = os.urandom(4)
        sock.sendall(bytes([0x88, 0x80 | 0x00]) + mask)
    finally:
        sock.close()

    _wait_until(lambda: sm.active_count == before and not os.path.isdir(tmp_dir))
    assert sm.active_count == before
    assert not os.path.isdir(tmp_dir)
    assert {
        os.path.basename(p)
        for p in _session_dirs()
    } == sessions_before


def _session_dirs() -> list[str]:
    import glob
    return glob.glob(os.path.join(tempfile.gettempdir(), "xfais_session_*"))


# ---------------------------------------------------------------------------
# 2. Cache-Control on HTML vs hashed assets
# ---------------------------------------------------------------------------


def _get(port: int, path: str) -> http.client.HTTPResponse:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", path)
        response = conn.getresponse()
        response.body = response.read()  # type: ignore[attr-defined]
        return response
    finally:
        conn.close()


def test_index_html_served_with_no_cache(web_server: _WebServer) -> None:
    """/ 入口 HTML 必须 no-cache / Entry HTML must revalidate."""
    response = _get(web_server.port, "/")
    assert response.status == 200
    assert response.getheader("Cache-Control") == "no-cache"
    assert b"entry" in response.body  # type: ignore[attr-defined]


def test_hashed_assets_stay_immutable(web_server: _WebServer) -> None:
    """哈希资源保持 immutable 长缓存 / Hashed assets stay immutable."""
    response = _get(web_server.port, "/assets/app-abc123.js")
    assert response.status == 200
    assert response.getheader("Cache-Control") == "public, max-age=31536000, immutable"


def test_spa_fallback_served_with_no_cache(web_server: _WebServer) -> None:
    """SPA fallback 的 index.html 也要 no-cache / SPA fallback revalidates."""
    response = _get(web_server.port, "/analysis/scan")
    assert response.status == 200
    assert response.getheader("Cache-Control") == "no-cache"
    assert response.getheader("Content-Type", "").startswith("text/html")
