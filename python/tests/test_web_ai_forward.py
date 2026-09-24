#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_web_ai_forward.py — serve_web Jev 转发端点测试。

POST /api/ai/systemone lets a serve_web deployment share one admin-configured
Jev (TypeSafe AI) key with every browser client (api.typesafe.ai sends no CORS
headers, so the browser can never call it directly). Covers: 501 when the
admin has not set XFAIS_JEV_API_KEY, SSRF validation of the admin-configured
upstream URL, upstream pass-through (status + body), and request guards
(JSON object, size cap).
POST /api/ai/systemone 使 serve_web 部署能向所有浏览器客户端共享一个由管理
员配置的 Jev（TypeSafe AI）Key（api.typesafe.ai 不发 CORS 头，浏览器无法直
连）。覆盖：未设置 XFAIS_JEV_API_KEY 时的 501、上游 URL 的 SSRF 校验、上游
状态码与响应体透传、以及请求侧防护（JSON 对象、大小上限）。
"""

from __future__ import annotations

import http.client
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

import python.service_launcher as sl


# ---------------------------------------------------------------------------
# Server fixtures (X-FAIS web handler + mock Jev upstream)
# ---------------------------------------------------------------------------


class _WebServer:
    def __init__(self) -> None:
        self._prev_ws_service = sl._ws_service
        sl._ws_service = sl.WebSocketService(session_manager=sl.SessionManager())
        handler = type("TestWebAiHandler", (sl.WebHealthHandler,), {
            "expected_python": "3",
            "requirements_lock": "",
            "ws_port": None,
            "cached_report": None,
            "dist_dir": "",
        })
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        sl._ws_service = self._prev_ws_service


@pytest.fixture()
def web_server():
    server = _WebServer()
    try:
        yield server
    finally:
        server.stop()


class _MockUpstreamHandler(BaseHTTPRequestHandler):
    """Records the forwarded request and replays a configured response."""

    seen: dict = {}
    respond_status: int = 200
    respond_body: bytes = b'{"answers": {"q1": {"choice": "waxs"}}}'

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)
        _MockUpstreamHandler.seen = {
            "path": self.path,
            "auth": self.headers.get("Authorization"),
            "content_type": self.headers.get("Content-Type"),
            "body": json.loads(body),
        }
        payload = _MockUpstreamHandler.respond_body
        self.send_response(_MockUpstreamHandler.respond_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture()
def mock_upstream(monkeypatch: pytest.MonkeyPatch):
    _MockUpstreamHandler.seen = {}
    _MockUpstreamHandler.respond_status = 200
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _MockUpstreamHandler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()


def _post(port: int, path: str, body: bytes, content_type: str = "application/json"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("POST", path, body=body, headers={"Content-Type": content_type})
        response = conn.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        conn.close()


def _get_health(port: int) -> dict:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        conn.request("GET", "/health")
        response = conn.getresponse()
        return json.loads(response.read())
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# SSRF validation of the admin-configured upstream URL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("url", [
    "ftp://api.typesafe.ai/v1/systemone",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_x",
    "/v1/systemone",                 # no scheme/host
    "http://localhost/v1/systemone",
    "http://127.0.0.1/v1/systemone",
    "http://10.0.0.5/v1/systemone",
    "http://192.168.1.4/v1/systemone",
    "http://172.16.0.9/v1/systemone",
    "http://169.254.169.254/latest/meta-data",  # cloud metadata
    "http://0.0.0.0/v1/systemone",
    "http://[::1]/v1/systemone",
    "https://[fe80::1]/v1/systemone",           # link-local
])
def test_upstream_validator_rejects_non_public(url: str) -> None:
    """非公网上游必须被拒 / Non-public upstreams must be rejected."""
    assert sl._validate_public_http_url(url) is not None


def test_upstream_validator_accepts_public_literal_ip() -> None:
    """公网字面 IP 通过（无需 DNS）/ Public literal IP passes without DNS."""
    assert sl._validate_public_http_url("https://8.8.8.8/v1/systemone") is None


# ---------------------------------------------------------------------------
# Endpoint behaviour
# ---------------------------------------------------------------------------


def test_endpoint_501_when_admin_key_missing(web_server: _WebServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """管理员未配 Key → 501，前端据此回退规则路由 / No key → 501."""
    monkeypatch.delenv(sl._JEV_API_KEY_ENV, raising=False)
    status, _, body = _post(web_server.port, "/api/ai/systemone", b'{"state": {}}')
    assert status == 501
    assert "not configured" in json.loads(body)["error"]
    assert _get_health(web_server.port)["jev_api"] is False


def test_endpoint_rejects_internal_upstream_config(web_server: _WebServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """配置成内网地址的上游必须被 SSRF 校验拦下 / Internal upstream rejected."""
    monkeypatch.setenv(sl._JEV_API_KEY_ENV, "test-key")
    monkeypatch.setenv(sl._JEV_API_URL_ENV, "http://127.0.0.1:9/v1/systemone")
    status, _, body = _post(web_server.port, "/api/ai/systemone", b'{"state": {}}')
    assert status == 502
    assert "rejected" in json.loads(body)["error"]


def test_endpoint_forwards_with_admin_key(web_server: _WebServer, mock_upstream: ThreadingHTTPServer,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """管理员 Key 全员共享：上游收到 Bearer Key 与原样 body / Shared key forwards."""
    monkeypatch.setenv(sl._JEV_API_KEY_ENV, "shared-admin-key")
    monkeypatch.setenv(sl._JEV_API_URL_ENV, f"http://127.0.0.1:{mock_upstream.server_address[1]}/v1/systemone")
    # SSRF 校验已由上方单测覆盖；此处仅为允许 loopback mock 上游而放行。
    monkeypatch.setattr(sl, "_validate_public_http_url", lambda url: None)

    request = json.dumps({"state": {"q": 1}, "model": "jev-latest", "questions": {}}).encode()
    status, headers, body = _post(web_server.port, "/api/ai/systemone", request)

    assert status == 200
    assert json.loads(body) == {"answers": {"q1": {"choice": "waxs"}}}
    assert headers["Content-Type"] == "application/json"
    assert _get_health(web_server.port)["jev_api"] is True
    seen = _MockUpstreamHandler.seen
    assert seen["auth"] == "Bearer shared-admin-key"
    assert seen["content_type"] == "application/json"
    assert seen["path"] == "/v1/systemone"
    assert seen["body"] == json.loads(request)  # byte-identical passthrough


def test_endpoint_passes_upstream_error_through(web_server: _WebServer, mock_upstream: ThreadingHTTPServer,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """上游 401 原样透传（前端映射为 no_key）/ Upstream 401 passes through."""
    _MockUpstreamHandler.respond_status = 401
    _MockUpstreamHandler.respond_body = b'{"error": "bad key"}'
    monkeypatch.setenv(sl._JEV_API_KEY_ENV, "shared-admin-key")
    monkeypatch.setenv(sl._JEV_API_URL_ENV, f"http://127.0.0.1:{mock_upstream.server_address[1]}/v1/systemone")
    monkeypatch.setattr(sl, "_validate_public_http_url", lambda url: None)

    status, _, body = _post(web_server.port, "/api/ai/systemone", b'{"state": {}}')
    assert status == 401
    assert json.loads(body) == {"error": "bad key"}


@pytest.mark.parametrize("payload", [
    b"not-json{",
    b'"just a string"',
    b"[1, 2, 3]",
])
def test_endpoint_rejects_malformed_bodies(web_server: _WebServer, monkeypatch: pytest.MonkeyPatch,
                                           payload: bytes) -> None:
    """非 JSON 对象的请求体 → 400 / Non-JSON-object bodies → 400."""
    monkeypatch.setenv(sl._JEV_API_KEY_ENV, "test-key")
    monkeypatch.setattr(sl, "_validate_public_http_url", lambda url: None)
    status, _, _body = _post(web_server.port, "/api/ai/systemone", payload)
    assert status == 400


def test_endpoint_rejects_oversized_body(web_server: _WebServer, monkeypatch: pytest.MonkeyPatch) -> None:
    """超过大小上限的请求体 → 413 / Oversized body → 413."""
    monkeypatch.setenv(sl._JEV_API_KEY_ENV, "test-key")
    monkeypatch.setattr(sl, "_validate_public_http_url", lambda url: None)
    monkeypatch.setattr(sl, "_JEV_MAX_BODY_BYTES", 8)
    status, _, _body = _post(web_server.port, "/api/ai/systemone", b'{"state": {}}')
    assert status == 413
