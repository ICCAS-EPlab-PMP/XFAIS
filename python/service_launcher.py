#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
service_launcher.py — Embedded Python health and WebSocket service entrypoint
service_launcher.py — 内置 Python 健康检查与 WebSocket 服务入口
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import re
import shutil
import struct
import tempfile
from pathlib import Path
import sys
import threading
import traceback
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Awaitable, Callable

from services.export_helper import ExportHelper, IntegrationResult

# 确保无论从哪里启动都能找到 python 包 / ensure the python package is importable
_PACKAGE_DIR = Path(__file__).resolve().parent.parent  # electron/
if str(_PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(_PACKAGE_DIR))

SERVICE_NAME = "waxs_saxs_embedded_runtime"

# ---------------------------------------------------------------------------
# Business API route registry — stub routes for the WebSocket service
# 业务 API 路由注册表 — WebSocket 服务的桩路由
# ---------------------------------------------------------------------------

API_ROUTES: list[str] = [
    "/api/integrate1d",
    "/api/integrate_azimuth",
    "/api/integrate_cake",
    "/api/integrate_fiber",
    "/api/viewer_config",
    "/api/h5convert",
    "/api/h5convert_scan",
    "/api/h5_extract",
    "/api/h5_list_files",
    "/api/png_generate",
    "/api/export_integration",
    "/api/calibrant_generate",
    "/api/cell_calibrant_generate",
    "/api/manual_calibrant_generate",
    "/api/list_space_groups",
]

THUMBNAIL_CHUNK_SIZE = 24

# Type alias: route handler receives (payload, send_progress, cancel_event)
# 类型别名：路由处理函数接收 (payload, send_progress, cancel_event)
RouteHandler = Callable[
    [dict, Callable[[float, str], Awaitable[None]], asyncio.Event],
    Awaitable[dict],
]


class _LazyImportProxy:
    """延迟导入代理 / Lazy import proxy.

    Keeps heavyweight scientific modules out of the startup path until a
    handler actually touches them.
    保持重量级科学计算模块不进入启动路径，直到处理函数真正访问它们。
    """

    def __init__(self, module_name: str, attribute_name: str | None = None) -> None:
        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_attribute_name", attribute_name)
        object.__setattr__(self, "_loaded_target", None)
        object.__setattr__(self, "_overrides", {})

    def _load_target(self) -> Any:
        target = object.__getattribute__(self, "_loaded_target")
        if target is None:
            module = importlib.import_module(object.__getattribute__(self, "_module_name"))
            attribute_name = object.__getattribute__(self, "_attribute_name")
            target = getattr(module, attribute_name) if attribute_name else module
            object.__setattr__(self, "_loaded_target", target)
        return target

    def __getattr__(self, name: str) -> Any:
        overrides = object.__getattribute__(self, "_overrides")
        if name in overrides:
            return overrides[name]
        return getattr(self._load_target(), name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        overrides = object.__getattribute__(self, "_overrides")
        overrides[name] = value

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._load_target()(*args, **kwargs)


# Lightweight proxies so health checks do not import the full processing stack.
# 轻量代理，避免健康检查提前导入整套处理栈。
np = _LazyImportProxy("numpy")
H5Handler = _LazyImportProxy("python.services.image_loader", "H5Handler")
ImageLoader = _LazyImportProxy("python.services.image_loader", "ImageLoader")
IntegratorFactory = _LazyImportProxy("python.services.integrator", "IntegratorFactory")
MaskBuilder = _LazyImportProxy("python.services.mask_builder", "MaskBuilder")
ExportHelper = _LazyImportProxy("python.services.export_helper", "ExportHelper")
IntegrationResult = _LazyImportProxy("python.services.export_helper", "IntegrationResult")
AdvancedIntegrationOptions = _LazyImportProxy("python.services.export_helper", "AdvancedIntegrationOptions")
H5Converter = _LazyImportProxy("python.services.h5convert", "H5Converter")
H5Extractor = _LazyImportProxy("python.services.h5_extractor", "H5Extractor")
PNGGenerator = _LazyImportProxy("python.services.pnggenerate", "PNGGenerator")
FiberIntegratorService = _LazyImportProxy("python.services.fiber_integrator", "FiberIntegratorService")
ImageRenderer = _LazyImportProxy("python.services.image_renderer", "ImageRenderer")
fabio = _LazyImportProxy("fabio")
Cell = _LazyImportProxy("pyFAI.crystallography.cell", "Cell")


# ---------------------------------------------------------------------------
# Requirement / health helpers (unchanged from original)
# 依赖/健康辅助函数（保持原有逻辑）
# ---------------------------------------------------------------------------


def normalize_requirement_name(name: str) -> str:
    """标准化依赖名 / Normalize a requirement name."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def parse_required_packages(requirements_lock: str) -> list[str]:
    """读取锁文件包名 / Read package names from a lock file."""
    if not requirements_lock or not os.path.isfile(requirements_lock):
        return []
    packages: list[str] = []
    with open(requirements_lock, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            package_name = re.split(r"[<>=;\[]", line, maxsplit=1)[0].strip()
            if package_name:
                packages.append(normalize_requirement_name(package_name))
    return packages


def collect_installed_packages(package_names: list[str] | None = None) -> dict[str, str]:
    """收集已安装分发包 / Collect installed distributions.

    When package names are provided, query only those packages to keep health
    checks lightweight.
    提供包名时仅查询这些包，以保持健康检查轻量。
    """
    installed: dict[str, str] = {}

    if package_names is not None:
        for package_name in package_names:
            normalized_name = normalize_requirement_name(package_name)
            if normalized_name in installed:
                continue
            try:
                installed[normalized_name] = importlib.metadata.version(package_name)
            except importlib.metadata.PackageNotFoundError:
                continue
        return installed

    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name")
        if not name:
            continue
        installed[normalize_requirement_name(name)] = distribution.version
    return installed


def build_health_report(expected_python: str, requirements_lock: str, ws_port: int | None = None) -> dict[str, Any]:
    """构建健康报告 / Build a health report."""
    required_packages = parse_required_packages(requirements_lock)
    installed = collect_installed_packages(required_packages)
    missing_dependencies = [package for package in required_packages if package not in installed]
    dependency_status = "ready" if not missing_dependencies else "missing"
    python_version = ".".join(str(part) for part in sys.version_info[:3])
    health_ok = python_version.startswith(expected_python) and dependency_status == "ready"

    report: dict[str, Any] = {
        "dependency_status": dependency_status,
        "expected_python": expected_python,
        "health_ok": health_ok,
        "missing_dependencies": missing_dependencies,
        "python_executable": sys.executable,
        "python_version": python_version,
        "service_name": SERVICE_NAME,
    }
    if ws_port is not None:
        report["ws_port"] = ws_port
    return report


# ---------------------------------------------------------------------------
# WebSocket service — connection management, task routing, progress, cancel
# WebSocket 服务 — 连接管理、任务路由、进度、取消
# ---------------------------------------------------------------------------


class SessionManager:
    """Per-session state: temporary files, cancel events, metadata.
    每个 session 的状态：临时文件、取消事件、元数据。
    
    Ensures different access sources never share data (files, caches, tasks).
    确保不同访问源的数据不串台（文件、缓存、任务）。
    """

    def __init__(self) -> None:
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def create_session(self, session_id: str | None = None) -> str:
        """Create a new session and return its ID. 创建新 session 并返回 ID。"""
        sid = session_id or str(uuid.uuid4())
        tmp_dir = tempfile.mkdtemp(prefix=f"xfais_session_{sid[:8]}_")
        with self._lock:
            self._sessions[sid] = {
                "id": sid,
                "tmp_dir": tmp_dir,
                "created_at": __import__("time").monotonic(),
            }
        return sid

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._sessions.get(session_id)

    def get_tmp_dir(self, session_id: str) -> str:
        """Get the isolated temp directory for a session. 获取 session 的隔离临时目录。"""
        session = self.get_session(session_id)
        if session is None:
            return tempfile.gettempdir()
        return session["tmp_dir"]

    def destroy_session(self, session_id: str) -> None:
        """Destroy a session and clean up its temp files. 销毁 session 并清理临时文件。"""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            tmp_dir = session.get("tmp_dir")
            if tmp_dir and os.path.isdir(tmp_dir):
                try:
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                except Exception:
                    pass

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._sessions)


class WebSocketService:
    """Manages WebSocket connections, task lifecycle and route dispatch.
    管理 WebSocket 连接、任务生命周期和路由分发。
    
    Supports session-based isolation: each connection gets its own session_id,
    ensuring data from different users never mixes.
    支持 session 隔离：每个连接有独立的 session_id，确保不同用户的数据不串台。
    """

    def __init__(self, *, session_manager: SessionManager | None = None) -> None:
        self.routes: dict[str, RouteHandler] = {}
        self.connections: set[Any] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: Any = None
        self._shutdown_event: asyncio.Event | None = None
        self._ready_event = threading.Event()
        self._cancel_events: dict[str, asyncio.Event] = {}
        # Session isolation / Session 隔离
        self.session_manager: SessionManager = session_manager or SessionManager()
        # Map: websocket → session_id / WebSocket 连接到 session 的映射
        self._connection_sessions: dict[Any, str] = {}

    # -- public API ---------------------------------------------------------

    def register_route(self, path: str, handler: RouteHandler) -> None:
        """Register a handler for a given API route path."""
        self.routes[path] = handler

    async def start(self, host: str, port: int) -> None:
        """Start the WebSocket server.  Blocks until ``stop()`` is called."""
        import websockets

        self._loop = asyncio.get_running_loop()
        self._shutdown_event = asyncio.Event()

        async with websockets.serve(
            self._handle_connection,
            host,
            port,
            ping_interval=20,
            ping_timeout=60,
            max_size=256 * 1024 * 1024,
        ):
            self._ready_event.set()
            await self._shutdown_event.wait()

    def stop(self) -> None:
        """Signal the running server to shut down."""
        ev = self._shutdown_event
        if ev is not None and self._loop is not None and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(ev.set)

    @property
    def ready(self) -> threading.Event:
        """Event that is set once the server is accepting connections."""
        return self._ready_event

    # -- internal -----------------------------------------------------------

    async def _handle_connection(self, websocket: Any) -> None:
        """Handle a single WebSocket connection for its full lifetime.
        Each connection gets its own session_id for data isolation.
        每个 WebSocket 连接获得独立的 session_id，保证数据隔离。
        """
        import websockets

        session_id = self.session_manager.create_session()
        self._connection_sessions[websocket] = session_id
        self.connections.add(websocket)
        try:
            # Send session info to the client / 发送 session 信息给客户端
            try:
                await websocket.send(json.dumps({
                    "type": "session_info",
                    "session_id": session_id,
                }))
            except Exception:
                pass

            async for raw in websocket:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send(
                        json.dumps({"type": "task_error", "task_id": "", "error": "Invalid JSON", "code": "INVALID_JSON"})
                    )
                    continue
                # Inject session_id into payload for handler isolation / 注入 session_id 以实现处理函数隔离
                if "payload" in data and isinstance(data["payload"], dict):
                    data["payload"]["_session_id"] = session_id
                    data["payload"]["_session_tmp_dir"] = self.session_manager.get_tmp_dir(session_id)
                await self._dispatch(websocket, data)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.connections.discard(websocket)
            sid = self._connection_sessions.pop(websocket, None)
            if sid:
                # Cancel all tasks for this session / 取消该 session 的所有任务
                tasks_to_cancel = [
                    tid for tid, ev in list(self._cancel_events.items())
                ]
                for tid in tasks_to_cancel:
                    self._cancel_events[tid].set()
                # Clean up session temp files / 清理 session 临时文件
                self.session_manager.destroy_session(sid)

    async def _dispatch(self, ws: Any, data: dict[str, Any]) -> None:
        """Route an incoming message to the appropriate handler."""
        msg_type = data.get("type")
        if msg_type == "task_submit":
            await self._handle_submit(ws, data)
        elif msg_type == "task_cancel":
            await self._handle_cancel(ws, data)
        else:
            await ws.send(
                json.dumps(
                    {
                        "type": "task_error",
                        "task_id": data.get("task_id", ""),
                        "error": f"Unknown message type: {msg_type}",
                        "code": "UNKNOWN_TYPE",
                    }
                )
            )

    async def _handle_submit(self, ws: Any, data: dict[str, Any]) -> None:
        """Accept a new task, reply with *task_accepted*, run in background."""
        task_id = data.get("task_id") or str(uuid.uuid4())
        route = data.get("route", "")
        payload = data.get("payload", {})

        if route not in self.routes:
            await ws.send(
                json.dumps(
                    {
                        "type": "task_error",
                        "task_id": task_id,
                        "error": f"Unknown route: {route}",
                        "code": "ROUTE_NOT_FOUND",
                    }
                )
            )
            return

        cancel_event = asyncio.Event()
        self._cancel_events[task_id] = cancel_event

        await ws.send(json.dumps({"type": "task_accepted", "task_id": task_id}))

        if self._loop is None:
            return
        self._loop.create_task(self._run_task(ws, task_id, route, payload, cancel_event))

    async def _run_task(
        self,
        ws: Any,
        task_id: str,
        route: str,
        payload: dict[str, Any],
        cancel_event: asyncio.Event,
    ) -> None:
        """Execute a registered route handler, emitting progress / complete / error."""
        try:
            handler = self.routes[route]

            async def send_progress(progress: float, message: str = "") -> None:
                await ws.send(
                    json.dumps({"type": "task_progress", "task_id": task_id, "progress": progress, "message": message})
                )

            result = await handler(payload, send_progress, cancel_event)

            if cancel_event.is_set():
                return

            # Binary image transfer / 二进制图像传输
            if isinstance(result, dict) and result.get("__binary_png__"):
                png_data: Any = result["__binary_png__"]
                if isinstance(png_data, str):
                    png_data = png_data.encode("utf-8")
                header_payload: dict[str, Any] = {
                    "type": "task_binary",
                    "task_id": task_id,
                    "mime": result.get("mime", "image/png"),
                    "frame": result.get("frame", 0),
                    "width": result.get("width", 0),
                    "height": result.get("height", 0),
                    "status": result.get("status", "ok"),
                    "metadata": result.get("metadata"),
                    "stats": result.get("stats"),
                    "contrast": result.get("contrast"),
                    "thumbnails": result.get("thumbnails"),
                    "nextStart": result.get("nextStart"),
                    "chunkSize": result.get("chunkSize"),
                }
                if "imageData" in result:
                    header_payload["imageData"] = result["imageData"]
                header_json = json.dumps(header_payload)
                header_bytes = header_json.encode("utf-8")
                header_len = len(header_bytes)
                frame_data = header_len.to_bytes(4, "big") + header_bytes + png_data
                await ws.send(frame_data)
            else:
                await ws.send(json.dumps({"type": "task_complete", "task_id": task_id, "result": result}))

        except asyncio.CancelledError:
            # Silently swallowed — cancellation is reported via task_cancelled
            pass
        except Exception as exc:
            traceback.print_exc()
            await ws.send(
                json.dumps(
                    {
                        "type": "task_error",
                        "task_id": task_id,
                        "error": str(exc),
                        "code": "INTERNAL_ERROR",
                    }
                )
            )
        finally:
            self._cancel_events.pop(task_id, None)

    async def _handle_cancel(self, ws: Any, data: dict[str, Any]) -> None:
        """Cancel a running task."""
        task_id = data.get("task_id", "")
        cancel_event = self._cancel_events.get(task_id)
        if cancel_event is not None:
            cancel_event.set()
            await ws.send(json.dumps({"type": "task_cancelled", "task_id": task_id}))
        else:
            await ws.send(
                json.dumps(
                    {
                        "type": "task_error",
                        "task_id": task_id,
                        "error": f"Task not found: {task_id}",
                        "code": "TASK_NOT_FOUND",
                    }
                )
            )


# ---------------------------------------------------------------------------
# Stub route handler — lightweight handler used by framework tests
# 桩路由处理函数 — 框架测试使用的轻量处理函数
# ---------------------------------------------------------------------------


async def stub_route_handler(payload, send_progress, cancel_event):
    await send_progress(0.0, "Initializing...")
    await asyncio.sleep(0.005)
    if cancel_event.is_set():
        raise asyncio.CancelledError()
    await send_progress(0.5, "Processing...")
    await asyncio.sleep(0.005)
    if cancel_event.is_set():
        raise asyncio.CancelledError()
    await send_progress(1.0, "Complete")
    return {"status": "ok", "message": "Not yet implemented"}


# ---------------------------------------------------------------------------
# Real route handlers — call service modules
# 真实路由处理函数 — 调用服务模块
# ---------------------------------------------------------------------------


async def _run_blocking(fn, *args, **kwargs):
    """Run a blocking function in a thread pool. 在线程池中运行阻塞函数。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _render_thumbnail_item(
    frame_data: Any,
    index: int,
    header: dict[str, Any],
    render_settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render one thumbnail payload for the viewer strip.
    为查看器缩略图条渲染单个缩略图载荷。

    When *render_settings* is provided the thumbnail is rendered with those
    viewer-side settings (sync mode).  Otherwise a per-frame auto-contrast
    fallback is used.
    当提供 *render_settings* 时，缩略图将使用这些查看器设置（同步模式）渲染。
    否则使用每帧自动对比度后备方案。
    """
    stats = ImageRenderer.compute_stats(frame_data)
    if render_settings is not None:
        thumb_settings = render_settings
    else:
        thumb_settings = {
            "cmap": "viridis",
            "use_log": False,
            "clim": (float(stats.get("min", 0.0)), float(stats.get("adjustedMax", 1.0) or 1.0)),
        }
    return {
        "index": index,
        "b64": ImageRenderer.render_thumbnail(frame_data, thumb_settings),
        "header": header,
        "stats": stats,
    }


def _build_render_settings(
    payload: dict[str, Any],
    contrast: dict[str, float],
) -> dict[str, Any]:
    """Build rendering settings from viewer payload + computed contrast.
    基于查看器载荷与计算出的对比度构建渲染设置。"""
    raw_settings = payload.get("settings", {})
    if not isinstance(raw_settings, dict):
        raw_settings = {}

    cmap = raw_settings.get("colormap") or raw_settings.get("cmap") or "viridis"
    use_log = bool(raw_settings.get("use_log", raw_settings.get("useLog", False)))
    clim_mode = raw_settings.get("clim_mode") or raw_settings.get("climMode") or "auto"
    raw_clim = raw_settings.get("clim")

    preview_scale = float(raw_settings.get("preview_scale", 1.0))

    if clim_mode == "manual" and isinstance(raw_clim, (list, tuple)) and len(raw_clim) >= 2:
        try:
            vmin = float(raw_clim[0])
            vmax = float(raw_clim[1])
            return {"cmap": cmap, "use_log": use_log, "clim": (vmin, vmax), "preview_scale": preview_scale}
        except (TypeError, ValueError):
            pass

    auto_clim = (
        (contrast.get("logMin", 1e-6), contrast.get("logMax", 1.0))
        if use_log else
        (contrast.get("autoMin", 0.0), contrast.get("autoMax", 1.0))
    )
    return {"cmap": cmap, "use_log": use_log, "clim": auto_clim, "preview_scale": preview_scale}


def _maybe_downsample(data: Any, render_settings: dict[str, Any]) -> Any:
    preview_scale = render_settings.pop("preview_scale", 1.0)
    if 0 < preview_scale < 1.0:
        step = max(1, int(round(1 / preview_scale)))
        data = data[::step, ::step]
    return data


def _warm_viewer_runtime() -> None:
    """Warm key image modules after service startup.
    在服务启动后预热关键图像模块。"""
    try:
        sample = np.zeros((16, 16), dtype=np.float32)
        ImageRenderer.render_png(sample, ImageRenderer.get_default_settings())
    except Exception as exc:
        print(f"[python-service] Warmup skipped: {exc}")


def _serialize_image_data(data: Any) -> list[list[float | None]]:
    """Convert 2D array data into JSON-safe nested lists.
    将二维数组转换为可 JSON 序列化的嵌套列表。"""
    arr = np.asarray(data, dtype=np.float32)
    arr = np.squeeze(arr)
    if arr.ndim != 2:
        raise ValueError(f"Expected 2D image data, got shape {arr.shape}")

    serialized: list[list[float | None]] = []
    for row in arr.tolist():
        serialized.append([
            None if value is None or not np.isfinite(value) else float(value)
            for value in row
        ])
    return serialized


def _load_fiber_batch_cache(cache_path: str) -> list[dict[str, Any]]:
    """Load serialized GIWAXS batch cache from a .npz file.
    从 .npz 文件加载序列化 GIWAXS 批量缓存。"""
    results: list[dict[str, Any]] = []
    with np.load(cache_path, allow_pickle=True) as cache:
        count = int(cache["count"])
        for idx in range(count):
            results.append({
                "stem": str(cache[f"stem_{idx}"]),
                "filename": str(cache[f"filename_{idx}"]),
                "intensity": np.array(cache[f"intensity_{idx}"], dtype=np.float32),
                "axis_ip": np.array(cache[f"axis_ip_{idx}"], dtype=np.float64),
                "axis_oop": np.array(cache[f"axis_oop_{idx}"], dtype=np.float64),
            })
    return results


def _is_image_like(shape: tuple) -> bool:
    return len(shape) >= 2 and shape[-2] >= 2 and shape[-1] >= 2


def _dataset_kind(shape: tuple) -> str:
    nd = len(shape)
    if nd == 0:
        return "scalar"
    if nd == 1:
        return "1d"
    if _is_image_like(shape):
        return f"{nd}d_image"
    return f"{nd}d"


def _serialize_h5_datasets(datasets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert HDF5 dataset scan results to renderer-friendly metadata.
    将 HDF5 数据集扫描结果转换为前端友好的元数据。"""
    serialized: list[dict[str, Any]] = []
    for ds_path, info in datasets.items():
        if not info.get("is_image"):
            continue
        serialized.append({
            "path": ds_path,
            "ndim": int(info.get("ndim", 0) or 0),
            "shape": list(info.get("shape", [])),
            "nFrames": int(info.get("n_frames", 1) or 1),
            "nChannels": int(info.get("n_channels", 0) or 0),
        })
    serialized.sort(key=lambda item: item["path"])
    return serialized


def _resolve_include_image_data(payload: dict[str, Any], default: bool = True) -> bool:
    """Resolve optional image-data inclusion flag from payload.
    从载荷中解析可选的图像数据包含开关。
    """
    value = payload.get("includeImageData")
    if value is None:
        value = payload.get("include_image_data")
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off", ""}
    return bool(value)


# ── export_integration: write integration results to file ────────────
# 导出积分结果到文件
async def handle_export_integration(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """Export integration results to the specified file format.
    将积分结果导出为指定格式的文件。"""
    fmt: str = payload.get("format", "txt")
    output_path: str = payload.get("outputPath", "")
    data_type: str = payload.get("dataType", "1d")
    mode: str = payload.get("mode", "single")
    results = payload.get("results", [])

    if not output_path:
        return {"success": False, "error": "No output path specified."}

    print(f"[export] type={data_type} fmt={fmt} mode={mode} path={output_path} results={len(results)}", flush=True)
    await send_progress(0.1, f"Preparing {fmt.upper()} export...")

    try:
        if data_type == "1d" or data_type == "azimuth" or data_type == "cake":
            # 1D / azimuth / cake: results is a list of {radial, intensity, label, unit}
            integration_results = []
            for r in results:
                radial = np.array(r.get("radial", []), dtype=np.float64)
                intensity = np.array(r.get("intensity", []), dtype=np.float64)
                if len(radial) == 0 or len(intensity) == 0:
                    continue
                integration_results.append(IntegrationResult(
                    radial=radial,
                    intensity=intensity,
                    label=r.get("label", r.get("filename", "curve")),
                    source_filename=r.get("label", r.get("filename", "unknown")),
                    unit=r.get("unit", "q_nm^-1"),
                    sigma=np.array(r.get("sigma", []), dtype=np.float64) if r.get("sigma") else None,
                ))

            if not integration_results:
                return {"success": False, "error": "No valid results to export."}

            unit_display = ExportHelper.UNIT_LABELS.get(
                integration_results[0].unit, integration_results[0].unit
            )
            if not isinstance(unit_display, str):
                unit_display = str(integration_results[0].unit)

            if mode == "separate":
                out_dir = Path(output_path)
                out_dir.mkdir(parents=True, exist_ok=True)
                written = []
                for idx, ir in enumerate(integration_results):
                    stem = ir.label or f"curve_{idx:04d}"
                    safe_stem = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem)
                    if fmt == "txt":
                        content = ExportHelper.to_txt([ir], unit_display)
                        p = out_dir / f"{safe_stem}.txt"
                        p.write_text(content, encoding="utf-8")
                    elif fmt == "csv":
                        content = ExportHelper.to_txt([ir], unit_display).replace("\t", ",")
                        p = out_dir / f"{safe_stem}.csv"
                        p.write_text(content, encoding="utf-8")
                    elif fmt == "xy":
                        lines = [f"{ir.radial[i]:.6e}\t{ir.intensity[i]:.6f}" for i in range(min(len(ir.radial), len(ir.intensity)))]
                        p = out_dir / f"{safe_stem}.xy"
                        p.write_text("\n".join(lines), encoding="utf-8")
                    elif fmt == "hdf5":
                        h5_bytes = ExportHelper.to_hdf5_bytes([ir], unit_display, extra_meta={"data_type": data_type})
                        p = out_dir / f"{safe_stem}.h5"
                        p.write_bytes(h5_bytes)
                    else:
                        return {"success": False, "error": f"Unsupported format: {fmt}"}
                    written.append(str(p))
                await send_progress(1.0, f"Exported {len(written)} files to {out_dir}")
                return {"success": True, "path": output_path, "files": written}

            if fmt == "txt":
                content = ExportHelper.to_txt(integration_results, unit_display)
                Path(output_path).write_text(content, encoding="utf-8")
            elif fmt == "csv":
                # CSV: comma-separated variant of TXT
                content = ExportHelper.to_txt(integration_results, unit_display)
                csv_content = content.replace("\t", ",")
                Path(output_path).write_text(csv_content, encoding="utf-8")
            elif fmt == "xy":
                # XY format: two columns per curve, simple
                lines = []
                for r in integration_results:
                    for i in range(min(len(r.radial), len(r.intensity))):
                        lines.append(f"{r.radial[i]:.6e}\t{r.intensity[i]:.6f}")
                    lines.append("")  # blank line between curves
                Path(output_path).write_text("\n".join(lines), encoding="utf-8")
            elif fmt == "hdf5":
                h5_bytes = ExportHelper.to_hdf5_bytes(
                    integration_results, unit_display,
                    extra_meta={"data_type": data_type},
                )
                Path(output_path).write_bytes(h5_bytes)
            else:
                return {"success": False, "error": f"Unsupported format for 1D: {fmt}"}

        elif data_type == "fiber":
            batch_cache_path = payload.get("batchCachePath")
            unit_ip = payload.get("unitIp", "qip_nm^-1")
            unit_oop = payload.get("unitOop", "qoop_nm^-1")

            if batch_cache_path:
                try:
                    batch_results = _load_fiber_batch_cache(batch_cache_path)
                except Exception as exc:
                    return {"success": False, "error": f"Failed to load GIWAXS batch cache: {exc}"}

                if not batch_results:
                    return {"success": False, "error": "No valid cached 2D data to export."}

                if mode == "separate":
                    out_dir = Path(output_path)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    written = []
                    for idx, item in enumerate(batch_results):
                        stem = str(item.get("stem") or item.get("filename") or f"fiber_{idx:04d}")
                        safe_stem = "".join(c if c.isalnum() or c in "-_." else "_" for c in stem)
                        intensity = item["intensity"]
                        axis_ip = item["axis_ip"]
                        axis_oop = item["axis_oop"]
                        if fmt in ("hdf5", "h5"):
                            p = out_dir / f"{safe_stem}.h5"
                            p.write_bytes(ExportHelper.to_hdf5_2d_bytes(intensity, axis_ip, axis_oop, unit_ip, unit_oop))
                        elif fmt in ("tiff", "tif"):
                            p = out_dir / f"{safe_stem}.tiff"
                            p.write_bytes(ExportHelper.to_image_bytes(intensity, fmt="tiff"))
                        elif fmt == "edf":
                            p = out_dir / f"{safe_stem}.edf"
                            p.write_bytes(ExportHelper.to_image_bytes(intensity, fmt="edf"))
                        elif fmt == "npy":
                            p = out_dir / f"{safe_stem}.npy"
                            p.write_bytes(ExportHelper.to_npy_dict(intensity, axis_ip, axis_oop, unit_ip, unit_oop))
                        elif fmt == "csv":
                            import csv
                            p = out_dir / f"{safe_stem}.csv"
                            with open(p, "w", newline="", encoding="utf-8") as f:
                                writer = csv.writer(f)
                                writer.writerow(["oop_index", "ip_index", "axis_oop", "axis_ip", "intensity"])
                                for i, oop_val in enumerate(axis_oop):
                                    for j, ip_val in enumerate(axis_ip):
                                        val = intensity[i][j] if i < len(intensity) and j < len(intensity[i]) else ""
                                        writer.writerow([i, j, f"{oop_val:.6e}", f"{ip_val:.6e}", f"{val:.6e}" if val != "" else ""])
                        else:
                            return {"success": False, "error": f"Unsupported format for fiber: {fmt}"}
                        written.append(str(p))
                    await send_progress(1.0, f"Exported {len(written)} files to {out_dir}")
                    return {"success": True, "path": output_path, "files": written}

                if fmt in ("hdf5", "h5"):
                    ExportHelper.write_hdf5_batch_2d_streaming(
                        output_path, batch_results, unit_ip=unit_ip, unit_oop=unit_oop
                    )
                else:
                    return {"success": False, "error": f"Format {fmt} only supports separate export for batch GIWAXS."}
            else:
                # 2D fiber: single result payload
                intensity = np.array(payload.get("intensity", []), dtype=np.float64)
                axis_ip = np.array(payload.get("axisIp", []), dtype=np.float64)
                axis_oop = np.array(payload.get("axisOop", []), dtype=np.float64)

                if intensity.size == 0 or axis_ip.size == 0 or axis_oop.size == 0:
                    return {"success": False, "error": "No valid 2D data to export."}

                intensity = np.where(intensity is None, np.nan, intensity).astype(np.float32)

                if fmt in ("hdf5", "h5"):
                    h5_bytes = ExportHelper.to_hdf5_2d_bytes(
                        intensity, axis_ip, axis_oop, unit_ip, unit_oop,
                    )
                    Path(output_path).write_bytes(h5_bytes)
                elif fmt == "tiff" or fmt == "tif":
                    img_bytes = ExportHelper.to_image_bytes(intensity, fmt="tiff")
                    Path(output_path).write_bytes(img_bytes)
                elif fmt == "edf":
                    img_bytes = ExportHelper.to_image_bytes(intensity, fmt="edf")
                    Path(output_path).write_bytes(img_bytes)
                elif fmt == "npy":
                    npy_bytes = ExportHelper.to_npy_dict(
                        intensity, axis_ip, axis_oop, unit_ip, unit_oop,
                    )
                    Path(output_path).write_bytes(npy_bytes)
                elif fmt == "csv":
                    import csv
                    with open(output_path, "w", newline="", encoding="utf-8") as f:
                        writer = csv.writer(f)
                        writer.writerow(["oop_index", "ip_index", "axis_oop", "axis_ip", "intensity"])
                        for i, oop_val in enumerate(axis_oop):
                            for j, ip_val in enumerate(axis_ip):
                                val = intensity[i][j] if i < len(intensity) and j < len(intensity[i]) else ""
                                writer.writerow([i, j, f"{oop_val:.6e}", f"{ip_val:.6e}", f"{val:.6e}" if val != "" else ""])
                else:
                    return {"success": False, "error": f"Unsupported format for fiber: {fmt}"}
        else:
            return {"success": False, "error": f"Unknown data type: {data_type}"}

        await send_progress(1.0, f"Exported to {output_path}")
        return {"success": True, "path": output_path}

    except Exception as exc:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(exc)}


async def handle_integrate1d(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """1D radial integration handler. 1D径向积分处理函数。"""
    print(f"[integrate1d] payload keys: {list(payload.keys())}", flush=True)
    print(f"[integrate1d] files count: {len(payload.get('files', []))}", flush=True)
    print(f"[integrate1d] geometry keys: {list(payload.get('geometry', {}).keys())}", flush=True)
    print(f"[integrate1d] options: {payload.get('options', {})}", flush=True)
    await send_progress(0.0, "Loading geometry...")

    geo = payload.get("geometry", {})
    if geo.get("poni_path"):
        ai, cx, cy = await _run_blocking(IntegratorFactory.from_poni_path, geo["poni_path"])
    elif geo.get("poni_bytes"):
        ai, cx, cy = await _run_blocking(IntegratorFactory.from_poni_bytes, geo["poni_bytes"].encode())
    elif geo.get("manual"):
        m = geo["manual"]
        ai, cx, cy = await _run_blocking(
            IntegratorFactory.from_manual_params,
            m.get("pixel_size_um", 172.0), m.get("dist_mm", 200.0),
            m.get("wavelength_A", 1.5418), m.get("center_x_px", 512.0),
            m.get("center_y_px", 512.0), m.get("rot1_deg", 0.0),
            m.get("rot2_deg", 0.0), m.get("rot3_deg", 0.0),
        )
    else:
        return {"status": "error", "message": "No geometry parameters provided"}

    if ai is None:
        return {"status": "error", "message": "Failed to create integrator"}

    files = payload.get("files", [])
    if not isinstance(files, list):
        files = [files] if isinstance(files, str) else []
    if len(files) == 0:
        single = payload.get("filePath") or payload.get("file")
        if isinstance(single, str):
            files = [single]
    print(f"[integrate1d] Processing {len(files)} files", flush=True)

    results: list[dict] = []
    failed: list[dict] = []
    for i, fpath in enumerate(files):
        if cancel_event.is_set():
            raise asyncio.CancelledError()
        await send_progress((i + 0.5) / max(len(files), 1), f"Integrating ({i+1}/{len(files)}) {fpath}")

        try:
            data, dead_mask, meta = await _run_blocking(
                ImageLoader.load, fpath,
                payload.get("h5_dataset_path"), payload.get("h5_channel"),
            )
            if data is None:
                failed.append({"file": fpath, "reason": "No data loaded"})
                continue

            mask = await _run_blocking(
                MaskBuilder.build, data,
                payload.get("valid_min", 0.0), payload.get("valid_max", 1e10),
                dead_mask, None,
            )

            opts = payload.get("options", {})
            method = opts.get("method", "splitpixel")
            integrator = opts.get("integrator", "ng")
            integrate_kwargs = {
                "data": data,
                "npt": opts.get("npt", 1000),
                "unit": opts.get("unit", "q_nm^-1"),
                "mask": mask.astype(np.uint8),
                "method": method,
                "correctSolidAngle": opts.get("correct_solid_angle", True),
                "polarization_factor": opts.get("polarization_factor"),
            }
            if integrator == "ng" and hasattr(ai, "integrate1d_ng"):
                res = ai.integrate1d_ng(**integrate_kwargs)
            else:
                res = ai.integrate1d(**integrate_kwargs)
            results.append({
                "radial": res.radial.tolist(),
                "intensity": res.intensity.tolist(),
                "label": meta.get("filename", fpath),
                "filename": meta.get("filename", fpath),
                "unit": opts.get("unit", "q_nm^-1"),
            })
            print(f"[integrate1d] OK ({i+1}/{len(files)}): {fpath} → {len(res.radial)} points", flush=True)
        except Exception as file_exc:
            failed.append({"file": fpath, "reason": str(file_exc)})
            print(f"[integrate1d] ERROR on {fpath}: {file_exc}", flush=True)
            traceback.print_exc()

    await send_progress(1.0, "Complete")
    print(f"[integrate1d] Done: {len(results)} success, {len(failed)} failed out of {len(files)} total", flush=True)
    if not results and not failed:
        return {"status": "error", "message": "No files provided."}
    if not results:
        return {"status": "error", "message": f"All {len(files)} file(s) failed.", "failed": failed}
    return {"status": "ok", "results": results, "failed": failed}


async def handle_integrate_azimuth(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """Azimuthal integration handler. 方位角积分处理函数。"""
    await send_progress(0.0, "Loading geometry...")
    geo = payload.get("geometry", {})
    if geo.get("poni_path"):
        ai, cx, cy = await _run_blocking(IntegratorFactory.from_poni_path, geo["poni_path"])
    elif geo.get("manual"):
        m = geo["manual"]
        ai, cx, cy = await _run_blocking(IntegratorFactory.from_manual_params, **m)
    else:
        return {"status": "error", "message": "No geometry parameters"}
    if ai is None:
        return {"status": "error", "message": "Failed to create integrator"}

    files = payload.get("files", [])
    results: list[dict] = []
    failed: list[dict] = []
    for i, fpath in enumerate(files):
        if cancel_event.is_set():
            raise asyncio.CancelledError()
        await send_progress((i + 0.5) / max(len(files), 1), f"Integrating {fpath}")
        try:
            data, dead_mask, meta = await _run_blocking(
                ImageLoader.load, fpath,
                payload.get("h5_dataset_path"), payload.get("h5_channel"),
            )
            if data is None:
                failed.append({"file": fpath, "reason": "No data loaded"})
                continue
            mask = await _run_blocking(
                MaskBuilder.build,
                data,
                payload.get("valid_min", 0.0),
                payload.get("valid_max", 1e10),
                dead_mask,
                None,
            )
            opts = payload.get("options", {})
            kw: dict[str, Any] = {
                "data": data,
                "npt": opts.get("npt", 360),
                "unit": opts.get("unit", "chi_deg"),
                "mask": mask.astype(np.uint8),
                "method": opts.get("method", "splitpixel"),
            }
            azimuth_min = opts.get("azimuth_min")
            azimuth_max = opts.get("azimuth_max")
            if azimuth_min is not None and azimuth_max is not None:
                kw["azimuth_range"] = (float(azimuth_min), float(azimuth_max))
            radial_min = opts.get("radial_min")
            radial_max = opts.get("radial_max")
            if radial_min is not None and radial_max is not None:
                kw["radial_range"] = (float(radial_min), float(radial_max))
            res = ai.integrate_radial(**kw)
            results.append({
                "radial": res.radial.tolist(),
                "intensity": res.intensity.tolist(),
                "label": meta.get("filename", fpath),
                "filename": meta.get("filename", fpath),
                "chi": res.radial.tolist(),
                "unit": opts.get("unit", "chi_deg"),
            })
        except Exception as file_exc:
            failed.append({"file": fpath, "reason": str(file_exc)})
            print(f"[integrate_azimuth] ERROR on {fpath}: {file_exc}", flush=True)
            traceback.print_exc()

    await send_progress(1.0, "Complete")
    if not results and not failed:
        return {"status": "error", "message": "No files provided."}
    if not results:
        return {"status": "error", "message": f"All {len(files)} file(s) failed.", "failed": failed}
    return {"status": "ok", "results": results, "failed": failed}


async def handle_integrate_cake(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """CAKE 1D sector integration handler. CAKE一维扇区积分处理函数。"""
    await send_progress(0.0, "Loading geometry...")
    geo = payload.get("geometry", {})
    if geo.get("poni_path"):
        ai, cx, cy = await _run_blocking(IntegratorFactory.from_poni_path, geo["poni_path"])
    elif geo.get("manual"):
        m = geo["manual"]
        ai, cx, cy = await _run_blocking(IntegratorFactory.from_manual_params, **m)
    else:
        return {"status": "error", "message": "No geometry parameters"}
    if ai is None:
        return {"status": "error", "message": "Failed to create integrator"}

    files = payload.get("files", [])
    traces: list[dict[str, Any]] = []
    failed: list[dict] = []
    for i, fpath in enumerate(files):
        if cancel_event.is_set():
            raise asyncio.CancelledError()
        await send_progress((i + 0.5) / max(len(files), 1), f"Integrating {fpath}")
        try:
            data, dead_mask, meta = await _run_blocking(
                ImageLoader.load, fpath,
                payload.get("h5_dataset_path"), payload.get("h5_channel"),
            )
            if data is None:
                failed.append({"file": fpath, "reason": "No data loaded"})
                continue
            mask = await _run_blocking(
                MaskBuilder.build,
                data,
                payload.get("valid_min", 0.0),
                payload.get("valid_max", 1e10),
                dead_mask,
                None,
            )
            opts = payload.get("options", {})
            azimuth_min = opts.get("azimuth_min")
            azimuth_max = opts.get("azimuth_max")
            integrate_kwargs: dict[str, Any] = {
                "data": data,
                "npt": opts.get("npt_rad", 500),
                "unit": opts.get("unit", "q_nm^-1"),
                "mask": mask.astype(np.uint8),
                "method": opts.get("method", "splitpixel"),
                "correctSolidAngle": opts.get("correct_solid_angle", True),
                "polarization_factor": opts.get("polarization_factor"),
            }
            if azimuth_min is not None and azimuth_max is not None:
                integrate_kwargs["azimuth_range"] = (float(azimuth_min), float(azimuth_max))

            radial_min = opts.get("radial_min")
            radial_max = opts.get("radial_max")
            if radial_min is not None and radial_max is not None:
                integrate_kwargs["radial_range"] = (float(radial_min), float(radial_max))

            res = ai.integrate1d(
                **integrate_kwargs,
            )
            traces.append({
                "x": res.radial.tolist(),
                "y": res.intensity.tolist(),
                "name": meta.get("filename", "") or Path(fpath).name,
            })
        except Exception as file_exc:
            failed.append({"file": fpath, "reason": str(file_exc)})
            print(f"[integrate_cake] ERROR on {fpath}: {file_exc}", flush=True)
            traceback.print_exc()

    await send_progress(1.0, "Complete")
    return {"status": "ok", "traces": traces, "failed": failed}


async def handle_integrate_fiber(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """GIWAXS fiber integration handler. GIWAXS纤维积分处理函数。

    Two modes:
    - Preview (default): batch → .npz cache → return first result + summary
    - Batch-to-folder (outputPath provided): integrate + write to disk one-by-one
    """
    await send_progress(0.0, "Building FiberIntegrator...")

    geo = payload.get("geometry", {})
    fi = await _run_blocking(
        FiberIntegratorService.build_integrator,
        poni_path=geo.get("poni_path"),
        poni_bytes=geo.get("poni_bytes", "").encode() if geo.get("poni_bytes") else None,
        use_poni_rot3=geo.get("use_poni_rot3", True),
        override_rot3_rad=geo.get("override_rot3_rad", 0.0),
        manual_params=geo.get("manual"),
    )
    if fi is None:
        return {"status": "error", "message": "Failed to build FiberIntegrator"}

    files = payload.get("files", [])
    params = payload.get("params", {})
    opts = payload.get("options", {})

    # ── Determine mode ──
    output_path = payload.get("outputPath")
    output_format = payload.get("outputFormat", "npy")
    batch_to_folder = bool(output_path)

    if batch_to_folder:
        # ═══════════════════════════════════════════════════════════════
        # BATCH TO FOLDER: integrate + export to disk, one by one
        # ═══════════════════════════════════════════════════════════════
        out_dir = Path(output_path)
        out_dir.mkdir(parents=True, exist_ok=True)
        n_files = len(files)
        generated: list[str] = []
        errors: list[str] = []

        for idx, fpath_str in enumerate(files):
            if cancel_event.is_set():
                raise asyncio.CancelledError()

            fpath = Path(fpath_str)
            await send_progress(
                idx / max(n_files, 1),
                f"Processing [{idx + 1}/{n_files}] {fpath.name}...",
            )

            try:
                raw_data, dead_mask, meta = await _run_blocking(
                    ImageLoader.load, fpath,
                    payload.get("h5_dataset_path"), payload.get("h5_channel"),
                )
                if raw_data is None:
                    errors.append(f"{fpath.name}: failed to load")
                    continue

                custom_mask = None
                custom_mask_path = opts.get("custom_mask_path") or payload.get("custom_mask_path")
                if custom_mask_path:
                    custom_mask = MaskBuilder.load_mask_file(str(custom_mask_path))
                final_mask = MaskBuilder.build(
                    raw_data, opts.get("valid_min", 0.0), opts.get("valid_max", 1e10),
                    dead_mask, custom_mask,
                )

                result = FiberIntegratorService.integrate_single(
                    fi, raw_data, final_mask, params,
                    correct_solid_angle=opts.get("correct_solid_angle", True),
                    polarization_factor=opts.get("polarization_factor"),
                )

                stem = fpath.stem + "_fiber"
                unit_ip = params.get("unit_ip", "qip_nm^-1")
                unit_oop = params.get("unit_oop", "qoop_nm^-1")
                I = result["intensity"]
                qip = result["axis_ip"]
                qoop = result["axis_oop"]

                if output_format in ("hdf5", "h5"):
                    out_file = out_dir / f"{stem}.h5"
                    out_file.write_bytes(ExportHelper.to_hdf5_2d_bytes(I, qip, qoop, unit_ip, unit_oop))
                elif output_format in ("tiff", "tif"):
                    out_file = out_dir / f"{stem}.tiff"
                    out_file.write_bytes(ExportHelper.to_image_bytes(I, fmt="tiff"))
                elif output_format == "edf":
                    out_file = out_dir / f"{stem}.edf"
                    out_file.write_bytes(ExportHelper.to_image_bytes(I, fmt="edf"))
                elif output_format == "npy":
                    out_file = out_dir / f"{stem}.npy"
                    out_file.write_bytes(ExportHelper.to_npy_dict(I, qip, qoop, unit_ip, unit_oop))
                else:
                    errors.append(f"{fpath.name}: unsupported format '{output_format}'")
                    continue

                generated.append(str(out_file))

            except Exception as exc:
                errors.append(f"{fpath.name}: {exc}")
                continue

        await send_progress(1.0, f"Complete: {len(generated)} files written")
        return {
            "status": "ok",
            "generated": generated,
            "errors": errors,
            "count": len(generated),
        }

    # ═══════════════════════════════════════════════════════════════
    # PREVIEW MODE: batch → .npz cache → return first result
    # ═══════════════════════════════════════════════════════════════

    def _batch():
        custom_mask = None
        custom_mask_path = opts.get("custom_mask_path") or payload.get("custom_mask_path")
        if custom_mask_path:
            custom_mask = MaskBuilder.load_mask_file(str(custom_mask_path))
        batch_errors: list[str] = []
        results = FiberIntegratorService.integrate_batch(
            fi, files, params,
            valid_min=opts.get("valid_min", 0.0),
            valid_max=opts.get("valid_max", 1e10),
            h5_dataset_path=payload.get("h5_dataset_path"),
            h5_channel=payload.get("h5_channel"),
            custom_mask=custom_mask,
            correct_solid_angle=opts.get("correct_solid_angle", True),
            polarization_factor=opts.get("polarization_factor"),
            error_collector=batch_errors,
        )
        return results, batch_errors

    batch_results, preview_errors = await _run_blocking(_batch)

    if not batch_results:
        detail = "; ".join(preview_errors[:5]) if preview_errors else "unknown errors"
        return {"status": "error", "message": f"No fiber integration results were produced: {detail}"}

    serialized = []
    for r in batch_results:
        serialized.append({
            "stem": r.get("stem", ""),
            "filename": r.get("filename", ""),
            "intensity_shape": r.get("shape", []),
        })

    with tempfile.NamedTemporaryFile(delete=False, suffix=".npz") as tmp:
        cache_path = tmp.name
    cache_payload: dict[str, Any] = {"count": len(batch_results)}
    for idx, item in enumerate(batch_results):
        cache_payload[f"stem_{idx}"] = str(item.get("stem", ""))
        cache_payload[f"filename_{idx}"] = str(item.get("filename", ""))
        cache_payload[f"intensity_{idx}"] = item.get("intensity")
        cache_payload[f"axis_ip_{idx}"] = item.get("axis_ip")
        cache_payload[f"axis_oop_{idx}"] = item.get("axis_oop")
    np.savez_compressed(cache_path, **cache_payload)

    first = batch_results[0]
    await send_progress(1.0, "Complete")
    return {
        "status": "ok",
        "intensity": first.get("intensity").tolist() if first.get("intensity") is not None else [],
        "axisIp": first.get("axis_ip").tolist() if first.get("axis_ip") is not None else [],
        "axisOop": first.get("axis_oop").tolist() if first.get("axis_oop") is not None else [],
        "unitIp": params.get("unit_ip", "qip_nm^-1"),
        "unitOop": params.get("unit_oop", "qoop_nm^-1"),
        "results_count": len(batch_results),
        "results_summary": serialized,
        "batchCachePath": cache_path,
    }


async def handle_viewer_config(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """Viewer configuration handler. 查看器配置处理函数。"""
    action = payload.get("action")

    # ── resolve_geometry_center: resolve pyFAI/Fit2D beam centre in pixels ──
    if action == "resolve_geometry_center":
        geo = payload.get("geometry", {}) or {}
        try:
            if geo.get("poniPath") or geo.get("poni_path"):
                _ai, center_x, center_y = await _run_blocking(
                    IntegratorFactory.from_poni_path,
                    geo.get("poniPath") or geo.get("poni_path"),
                )
            else:
                _ai, center_x, center_y = await _run_blocking(
                    IntegratorFactory.from_manual_params,
                    float(geo.get("pixel1", 172.0)),
                    float(geo.get("distance", 200.0)),
                    float(geo.get("wavelength", 1.5418)),
                    float(geo.get("centerX", 512.0)),
                    float(geo.get("centerY", 512.0)),
                )
            return {"status": "ok", "centerX": center_x, "centerY": center_y}
        except Exception as exc:
            return {"status": "error", "message": f"Failed to resolve geometry center: {exc}"}

    # ── png_export: render a single frame with custom settings ──────────
    if action == "png_export":
        await send_progress(0.0, "Rendering PNG export...")
        fpath = payload.get("filePath", "")
        if not fpath:
            return {"status": "error", "message": "No filePath provided"}

        frame_index = max(0, int(payload.get("frame", 0) or 0))
        dataset_path = payload.get("dataset")
        h5_channel = payload.get("channel")
        output_path = payload.get("output_path") or payload.get("outputPath")
        user_settings = payload.get("settings", {})
        dpi = int(user_settings.get("dpi", 100))

        ext = os.path.splitext(fpath)[1].lower()
        if ext in {".h5", ".hdf5"}:
            if not dataset_path:
                datasets = await _run_blocking(H5Handler.find_datasets, fpath)
                entries = _serialize_h5_datasets(datasets)
                dataset_path = H5Handler.pick_default_dataset([item["path"] for item in entries])
                if not dataset_path:
                    return {"status": "error", "message": "No image dataset found"}
            data, _dead = await _run_blocking(
                H5Handler.load_frame, fpath, dataset_path, frame_index, h5_channel,
            )
        else:
            data, _dead, _meta = await _run_blocking(
                ImageLoader.load, fpath, dataset_path, h5_channel,
            )
        if data is None:
            return {"status": "error", "message": "Failed to load frame"}

        render_settings = {
            "cmap": user_settings.get("colormap") or user_settings.get("cmap", "viridis"),
            "use_log": bool(user_settings.get("use_log", False)),
            "clim": tuple(user_settings.get("clim", (0.0, 1.0))),
            "show_colorbar": bool(user_settings.get("show_colorbar", False)),
        }
        if render_settings["show_colorbar"]:
            png_bytes = await _run_blocking(
                ImageRenderer.render_png_mpl, data,
                render_settings["cmap"], render_settings["use_log"],
                render_settings["clim"], dpi,
            )
        else:
            png_bytes = await _run_blocking(ImageRenderer.render_png, data, render_settings)
            if dpi != 100:
                from PIL import Image as _PILImage
                import io as _io

                def _rescale_png(raw: bytes, target_dpi: int) -> bytes:
                    img = _PILImage.open(_io.BytesIO(raw))
                    s = target_dpi / 100
                    img = img.resize(
                        (int(img.width * s), int(img.height * s)),
                        _PILImage.Resampling.NEAREST,
                    )
                    buf = _io.BytesIO()
                    img.save(buf, format="PNG", optimize=True)
                    return buf.getvalue()

                png_bytes = await _run_blocking(_rescale_png, png_bytes, dpi)

        if output_path:
            output_file = Path(str(output_path))

            def _write_png_bytes(target: Path, raw_bytes: bytes) -> str:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw_bytes)
                return str(target)

            saved_path = await _run_blocking(_write_png_bytes, output_file, png_bytes)
            await send_progress(1.0, "Complete")
            return {"status": "ok", "savedPath": saved_path}

        b64 = base64.b64encode(png_bytes).decode()
        await send_progress(1.0, "Complete")
        return {"status": "ok", "pngB64": b64}

    # ── preview: fast 256×256 thumbnail for instant display / 快速256×256预览 ──
    if action == "preview":
        await send_progress(0.0, "Generating preview…")
        fpath = payload.get("filePath", payload.get("files", [None])[0])
        if not fpath:
            return {"status": "error", "message": "No filePath provided"}

        ext = os.path.splitext(fpath)[1].lower()
        dataset_path = payload.get("dataset") or payload.get("h5_dataset_path")
        h5_channel = payload.get("channel") if payload.get("channel") is not None else payload.get("h5_channel")
        frame_index = max(0, int(payload.get("frame", payload.get("frame_index", 0)) or 0))

        # Load single frame / 加载单帧
        if ext in {".h5", ".hdf5"}:
            if not dataset_path:
                datasets = await _run_blocking(H5Handler.find_datasets, fpath)
                entries = _serialize_h5_datasets(datasets)
                dataset_path = H5Handler.pick_default_dataset([item["path"] for item in entries])
                if not dataset_path:
                    return {"status": "error", "message": "No image dataset found"}
            data, _dead = await _run_blocking(
                H5Handler.load_frame, fpath, dataset_path, frame_index, h5_channel,
            )
        else:
            result = await _run_blocking(ImageLoader.load, fpath)
            data, _dead, _meta = result

        if data is None:
            return {"status": "error", "message": "Failed to load frame"}

        # Fast downscale via slicing / 快速降采样（numpy切片，极快）
        h, w = data.shape
        scale = max(1, max(h, w) // 256)
        if scale > 1:
            preview_data = data[::scale, ::scale]
        else:
            preview_data = data

        # Render with thumbnail sync settings when provided / 提供同步设置时按其渲染缩略图
        raw_thumb_settings = payload.get("thumb_render_settings")
        _auto_clim = (0.0, float(np.nanmax(preview_data)) if np.any(np.isfinite(preview_data)) else 1.0)
        if isinstance(raw_thumb_settings, dict) and raw_thumb_settings.get("cmap"):
            raw_clim = raw_thumb_settings.get("clim")
            # clim may be None/[None,None] from JSON — fall back to auto
            if raw_clim is not None and isinstance(raw_clim, (list, tuple)):
                clim_vals = tuple(raw_clim)
                if all(isinstance(v, (int, float)) and np.isfinite(v) for v in clim_vals) and len(clim_vals) >= 2:
                    safe_clim = clim_vals[:2]
                else:
                    safe_clim = _auto_clim
            else:
                safe_clim = _auto_clim
            settings = {
                "cmap": raw_thumb_settings.get("cmap", "viridis"),
                "use_log": bool(raw_thumb_settings.get("use_log", False)),
                "clim": safe_clim,
            }
        else:
            settings = {
                "cmap": "viridis",
                "use_log": False,
                "clim": _auto_clim,
            }
        rgb = ImageRenderer._apply_colormap_lut(preview_data, settings)
        from PIL import Image as _PILImg
        import io as _io
        img = _PILImg.fromarray(rgb)
        img.thumbnail((256, 256), _PILImg.Resampling.NEAREST)
        buf = _io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        preview_png_bytes = buf.getvalue()

        await send_progress(1.0, "Complete")
        import base64 as _b64
        preview_b64 = _b64.b64encode(preview_png_bytes).decode("ascii")
        return {
            "status": "ok",
            "previewB64": preview_b64,
            "mime": "image/png",
            "width": int(w),
            "height": int(h),
            "frame": frame_index,
            "origHeight": int(h),
            "origWidth": int(w),
        }

    # ── fiber_result_preview: cached GIWAXS 2D result preview / 缓存GIWAXS结果预览 ──
    if action == "fiber_result_preview":
        await send_progress(0.0, "Loading GIWAXS result preview...")
        cache_path = payload.get("batchCachePath") or payload.get("batch_cache_path") or ""
        if not cache_path:
            return {"status": "error", "message": "No batchCachePath provided"}

        result_index = max(0, int(payload.get("resultIndex", payload.get("result_index", 0)) or 0))
        thumbnail_only = bool(payload.get("thumbnailOnly", payload.get("thumbnail_only", False)))
        try:
            batch_results = await _run_blocking(_load_fiber_batch_cache, cache_path)
        except Exception as exc:
            return {"status": "error", "message": f"Failed to load GIWAXS batch cache: {exc}"}

        if result_index >= len(batch_results):
            return {"status": "error", "message": f"Invalid result index: {result_index}"}

        item = batch_results[result_index]
        intensity = item["intensity"]
        stats = ImageRenderer.compute_stats(intensity)
        gmin_lin, gmax_lin = ImageRenderer.global_range([intensity], use_log=False)
        gmin_log, gmax_log = ImageRenderer.global_range([intensity], use_log=True)
        contrast = {
            "autoMin": float(gmin_lin),
            "autoMax": float(gmax_lin),
            "logMin": float(gmin_log),
            "logMax": float(gmax_log),
        }
        render_settings = _build_render_settings(payload, contrast)
        display_b64 = await _run_blocking(ImageRenderer.render_thumbnail, intensity, render_settings, (768, 768))
        preview_b64 = await _run_blocking(ImageRenderer.render_thumbnail, intensity, render_settings, (160, 160))
        await send_progress(1.0, "Complete")
        result_payload = {
            "status": "ok",
            "metadata": {
                "width": int(intensity.shape[1]),
                "height": int(intensity.shape[0]),
                "filename": item.get("filename", ""),
                "stem": item.get("stem", ""),
            },
            "stats": stats,
            "contrast": contrast,
            "displayB64": display_b64,
            "previewB64": preview_b64,
            "axisIp": item["axis_ip"].tolist(),
            "axisOop": item["axis_oop"].tolist(),
            "filename": item.get("filename", ""),
            "stem": item.get("stem", ""),
        }
        if thumbnail_only:
            return result_payload
        return result_payload

    # ── fiber_exported_preview: load exported result from disk / 从磁盘加载导出结果 ──
    if action == "fiber_exported_preview":
        await send_progress(0.0, "Loading exported GIWAXS result...")
        fpath = payload.get("filePath") or payload.get("file_path") or ""
        if not fpath:
            return {"status": "error", "message": "No filePath provided"}

        try:
            ext = os.path.splitext(fpath)[1].lower()
            if ext in (".npy",):
                data_dict = await _run_blocking(
                    lambda: np.load(fpath, allow_pickle=True).item()
                )
                intensity = np.asarray(data_dict.get("intensity", []), dtype=np.float32)
                axis_ip = np.asarray(data_dict.get("qip", data_dict.get("axis_ip", [])), dtype=np.float64)
                axis_oop = np.asarray(data_dict.get("qoop", data_dict.get("axis_oop", [])), dtype=np.float64)
            elif ext in (".h5", ".hdf5"):
                import h5py
                def _load_h5(p: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
                    with h5py.File(p, "r") as fh:
                        grp = fh.get("results", fh)
                        # find first dataset group or root datasets
                        keys = list(grp.keys())
                        if "intensity" in keys:
                            I = grp["intensity"][()]
                            qip = grp.get("axis_ip", grp.get("qip", np.array([])))[()]
                            qoop = grp.get("axis_oop", grp.get("qoop", np.array([])))[()]
                        elif keys:
                            sub = grp[keys[0]]
                            I = sub.get("intensity", np.array([]))[()]
                            qip = sub.get("axis_ip", sub.get("qip", np.array([])))[()]
                            qoop = sub.get("axis_oop", sub.get("qoop", np.array([])))[()]
                        else:
                            I = np.array([])
                            qip = np.array([])
                            qoop = np.array([])
                    return I, qip, qoop
                intensity, axis_ip, axis_oop = await _run_blocking(_load_h5, fpath)
            else:
                # TIFF/EDF: load as raw image, no calibrated axes
                raw_data, _dead, _meta = await _run_blocking(ImageLoader.load, Path(fpath))
                if raw_data is None:
                    return {"status": "error", "message": f"Failed to load {fpath}"}
                intensity = raw_data.astype(np.float32)
                axis_ip = np.arange(intensity.shape[1], dtype=np.float64)
                axis_oop = np.arange(intensity.shape[0], dtype=np.float64)
        except Exception as exc:
            return {"status": "error", "message": f"Failed to load preview: {exc}"}

        if intensity.size == 0:
            return {"status": "error", "message": "No intensity data found"}

        stats = ImageRenderer.compute_stats(intensity)
        gmin_lin, gmax_lin = ImageRenderer.global_range([intensity], use_log=False)
        gmin_log, gmax_log = ImageRenderer.global_range([intensity], use_log=True)
        contrast = {
            "autoMin": float(gmin_lin), "autoMax": float(gmax_lin),
            "logMin": float(gmin_log), "logMax": float(gmax_log),
        }
        render_settings = _build_render_settings(payload, contrast)
        display_b64 = await _run_blocking(ImageRenderer.render_thumbnail, intensity, render_settings, (768, 768))
        await send_progress(1.0, "Complete")
        return {
            "status": "ok",
            "displayB64": display_b64,
            "imageData": _serialize_image_data(intensity),
            "axisIp": axis_ip.tolist(),
            "axisOop": axis_oop.tolist(),
            "contrast": contrast,
            "stats": stats,
        }

    # ── probe: metadata only, no pixel data / 仅元数据，无像素数据 ──
    if action == "probe":
        await send_progress(0.0, "Inspecting file…")
        fpath = payload.get("filePath", payload.get("files", [None])[0])
        if not fpath:
            return {"status": "error", "message": "No filePath provided"}

        ext = os.path.splitext(fpath)[1].lower()
        metadata: dict[str, Any] = {"fileType": ext.lstrip(".")}

        if ext in {".h5", ".hdf5"}:
            await send_progress(0.5, "Scanning HDF5 structure…")
            datasets = await _run_blocking(H5Handler.find_datasets, fpath)
            dataset_entries = _serialize_h5_datasets(datasets)
            dataset_path = H5Handler.pick_default_dataset([item["path"] for item in dataset_entries])

            metadata["h5Datasets"] = dataset_entries
            metadata["nChannels"] = 0
            if dataset_path and dataset_entries:
                selected = next((item for item in dataset_entries if item["path"] == dataset_path), dataset_entries[0])
                metadata["totalFrames"] = int(selected.get("nFrames", 1))
                metadata["nChannels"] = int(selected.get("nChannels", 0))
                metadata["selectedDataset"] = dataset_path
            else:
                metadata["totalFrames"] = 1
        else:
            try:
                probe_meta = await _run_blocking(ImageLoader.probe, fpath)
                metadata["totalFrames"] = int(probe_meta.get("n_frames", 1) or 1)
                if probe_meta.get("height") is not None and probe_meta.get("width") is not None:
                    metadata["height"] = int(probe_meta["height"])
                    metadata["width"] = int(probe_meta["width"])
                metadata["nChannels"] = 0
            except Exception:
                metadata["totalFrames"] = 1
                metadata["nChannels"] = 0

        await send_progress(1.0, "Complete")
        return {"status": "ok", "metadata": metadata}

    # ── load_all: thumbnails + stats for every frame ────────────────────
    if action == "load_all":
        await send_progress(0.0, "Loading all frames...")
        fpath = payload.get("filePath", "")
        if not fpath:
            return {"status": "error", "message": "No filePath provided"}

        dataset_path = payload.get("dataset")
        h5_channel = payload.get("channel")
        ext = os.path.splitext(fpath)[1].lower()

        metadata: dict[str, Any] = {"fileType": ext.lstrip(".")}

        if ext in {".h5", ".hdf5"}:
            await send_progress(0.15, "Inspecting HDF5 datasets...")
            datasets = await _run_blocking(H5Handler.find_datasets, fpath)
            dataset_entries = _serialize_h5_datasets(datasets)
            dataset_path = dataset_path or H5Handler.pick_default_dataset(
                [item["path"] for item in dataset_entries]
            )
            if not dataset_path:
                return {"status": "error", "message": "No image dataset found"}

            await send_progress(0.3, "Reading all frames...")
            frames = await _run_blocking(H5Handler.load_all_frames, fpath, dataset_path, h5_channel)
            if not frames:
                return {"status": "error", "message": "No frames available"}

            selected_info = next((item for item in dataset_entries if item["path"] == dataset_path), None)
            metadata.update({
                "totalFrames": int(selected_info.get("nFrames", len(frames)) if selected_info else len(frames)),
                "h5Datasets": dataset_entries,
                "nChannels": int(selected_info.get("nChannels", 0) if selected_info else 0),
                "selectedDataset": dataset_path,
            })
            if h5_channel is not None:
                metadata["selectedChannel"] = h5_channel

            all_data = [frm[0] for frm in frames if frm[0] is not None]
        else:
            await send_progress(0.3, "Reading all frames...")
            frame_list = await _run_blocking(ImageLoader.load_all_frames, fpath)
            valid = [f for f in frame_list if f[0] is not None]
            if not valid:
                return {"status": "error", "message": "Failed to load image data"}

            metadata.update({
                "totalFrames": int(valid[0][2].get("n_frames", len(valid)) or len(valid)),
                "nChannels": 0,
            })
            all_data = [f[0] for f in valid]

        if not all_data:
            return {"status": "error", "message": "No image data available"}

        h, w = all_data[0].shape
        metadata.update({"height": int(h), "width": int(w)})

        await send_progress(0.5, "Computing contrast & thumbnails...")
        if cancel_event.is_set():
            raise asyncio.CancelledError()

        gmin_lin, gmax_lin = ImageRenderer.global_range(all_data, use_log=False)
        gmin_log, gmax_log = ImageRenderer.global_range(all_data, use_log=True)

        thumb_settings = {
            "cmap": "viridis",
            "use_log": False,
            "clim": (gmin_lin, gmax_lin),
        }

        n = len(all_data)
        thumbnails: list[dict[str, Any]] = []
        for idx in range(n):
            if cancel_event.is_set():
                raise asyncio.CancelledError()

            frm_data = all_data[idx]
            stats = ImageRenderer.compute_stats(frm_data)
            b64 = ImageRenderer.render_thumbnail(frm_data, thumb_settings)

            header: dict[str, Any] = {
                "filename": os.path.basename(fpath),
                "frameIndex": idx,
            }
            if dataset_path:
                header["dataset"] = dataset_path
            if h5_channel is not None:
                header["channel"] = h5_channel

            thumbnails.append({"index": idx, "b64": b64, "header": header, "stats": stats})
            if idx % max(1, n // 10) == 0:
                await send_progress(0.5 + 0.5 * (idx / n), f"Thumbnail {idx + 1}/{n}")

        await send_progress(1.0, "Complete")
        return {
            "status": "ok",
            "metadata": metadata,
            "contrast": {
                "autoMin": float(gmin_lin),
                "autoMax": float(gmax_lin),
                "logMin": float(gmin_log),
                "logMax": float(gmax_log),
            },
            "thumbnails": thumbnails,
        }

    # ── open_file: one-shot open with first frame + metadata + first thumbs ──
    if action == "open_file":
        await send_progress(0.0, "Opening file...")
        fpath = payload.get("filePath", payload.get("files", [None])[0])
        if not fpath:
            return {"status": "error", "message": "No filePath provided"}

        ext = os.path.splitext(fpath)[1].lower()
        frame_index = max(0, int(payload.get("frame_index", 0) or 0))
        dataset_path = payload.get("dataset") or payload.get("h5_dataset_path")
        h5_channel = payload.get("channel") if payload.get("channel") is not None else payload.get("h5_channel")

        metadata: dict[str, Any] = {
            "fileType": ext.lstrip("."),
            "frameIndex": frame_index,
        }
        effective_frame_index = frame_index

        thumbnails: list[dict[str, Any]] = []
        next_start: int | None = None
        total_frames = 1

        if ext in {".h5", ".hdf5"}:
            await send_progress(0.15, "Scanning HDF5 datasets...")
            datasets = await _run_blocking(H5Handler.find_datasets, fpath)
            dataset_entries = _serialize_h5_datasets(datasets)
            dataset_path = dataset_path or H5Handler.pick_default_dataset([item["path"] for item in dataset_entries])
            if not dataset_path:
                return {"status": "error", "message": "No image dataset found"}

            selected_info = next((item for item in dataset_entries if item["path"] == dataset_path), None)
            total_frames = int(selected_info.get("nFrames", 1) if selected_info else 1)
            metadata.update({
                "totalFrames": total_frames,
                "h5Datasets": dataset_entries,
                "nChannels": int(selected_info.get("nChannels", 0) if selected_info else 0),
                "selectedDataset": dataset_path,
            })
            if h5_channel is not None:
                metadata["selectedChannel"] = h5_channel

            await send_progress(0.4, "Reading first frame...")
            data, _dead_mask = await _run_blocking(H5Handler.load_frame, fpath, dataset_path, frame_index, h5_channel)
            if total_frames > 1:
                next_start = 0
        else:
            await send_progress(0.4, "Reading image data...")
            probe_meta = await _run_blocking(ImageLoader.probe, fpath)
            total_frames = int(probe_meta.get("n_frames", 1) or 1)
            data, _dead_mask, load_meta = await _run_blocking(ImageLoader.load_frame, fpath, frame_index)
            if data is None:
                return {"status": "error", "message": "Failed to load image data"}
            metadata.update({
                "totalFrames": total_frames,
                "nChannels": 0,
            })
            if probe_meta.get("height") is not None and probe_meta.get("width") is not None:
                metadata["height"] = int(probe_meta["height"])
                metadata["width"] = int(probe_meta["width"])
            effective_frame_index = int(load_meta.get("frame_index", frame_index) or frame_index)
            metadata["frameIndex"] = effective_frame_index
            if total_frames > 1:
                next_start = 0

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        if data is None:
            return {"status": "error", "message": "No image data available"}

        height, width = data.shape
        metadata.update({
            "frameIndex": effective_frame_index,
            "height": int(height),
            "width": int(width),
        })

        await send_progress(0.8, "Rendering image...")
        stats = ImageRenderer.compute_stats(data)
        gmin_lin, gmax_lin = ImageRenderer.global_range([data], use_log=False)
        gmin_log, gmax_log = ImageRenderer.global_range([data], use_log=True)
        contrast = {
            "autoMin": float(gmin_lin),
            "autoMax": float(gmax_lin),
            "logMin": float(gmin_log),
            "logMax": float(gmax_log),
        }
        render_settings = _build_render_settings(payload, contrast)
        data = _maybe_downsample(data, render_settings)
        png_bytes = ImageRenderer.render_png(data, render_settings)

        await send_progress(1.0, "Complete")
        return {
            "status": "ok",
            "__binary_png__": png_bytes,
            "mime": "image/png",
            "width": int(data.shape[1]),
            "height": int(data.shape[0]),
            "frame": effective_frame_index,
            "metadata": metadata,
            "stats": stats,
            "contrast": contrast,
            "thumbnails": thumbnails,
            "nextStart": next_start,
            "chunkSize": THUMBNAIL_CHUNK_SIZE,
        }

    # ── load_thumbnails_chunk: page-based thumbnail loading ──────
    if action == "load_thumbnails_chunk":
        await send_progress(0.0, "Loading thumbnail chunk...")
        fpath = payload.get("filePath", "")
        if not fpath:
            return {"status": "error", "message": "No filePath provided"}

        start = max(0, int(payload.get("start", 0) or 0))
        count = max(1, int(payload.get("count", THUMBNAIL_CHUNK_SIZE) or THUMBNAIL_CHUNK_SIZE))
        dataset_path = payload.get("dataset")
        h5_channel = payload.get("channel")
        ext = os.path.splitext(fpath)[1].lower()

        # Sync mode: use viewer render settings for thumbnails / 同步模式
        raw_thumb_settings = payload.get("thumb_render_settings")
        thumb_render: dict[str, Any] | None = None
        if isinstance(raw_thumb_settings, dict) and raw_thumb_settings.get("cmap"):
            thumb_render = {
                "cmap": raw_thumb_settings["cmap"],
                "use_log": bool(raw_thumb_settings.get("use_log", False)),
                "clim": tuple(raw_thumb_settings.get("clim", (0.0, 1.0))),
            }

        thumbnails: list[dict[str, Any]] = []
        total_frames = 1

        if ext in {".h5", ".hdf5"}:
            if not dataset_path:
                datasets = await _run_blocking(H5Handler.find_datasets, fpath)
                dataset_entries = _serialize_h5_datasets(datasets)
                dataset_path = H5Handler.pick_default_dataset([item["path"] for item in dataset_entries])
                if not dataset_path:
                    return {"status": "error", "message": "No image dataset found"}
            else:
                dataset_entries = _serialize_h5_datasets(await _run_blocking(H5Handler.find_datasets, fpath))

            selected_info = next((item for item in dataset_entries if item["path"] == dataset_path), None)
            total_frames = int(selected_info.get("nFrames", 1) if selected_info else 1)
            end = min(total_frames, start + count)

            for frame_index in range(start, end):
                if cancel_event.is_set():
                    raise asyncio.CancelledError()
                frame_data, _dead_mask = await _run_blocking(
                    H5Handler.load_frame, fpath, dataset_path, frame_index, h5_channel,
                )
                header = {"filename": os.path.basename(fpath), "frameIndex": frame_index, "dataset": dataset_path}
                if h5_channel is not None:
                    header["channel"] = h5_channel
                thumbnails.append(await _run_blocking(_render_thumbnail_item, frame_data, frame_index, header, thumb_render))
        else:
            if start > 0:
                probe_meta = await _run_blocking(ImageLoader.probe, fpath)
                total_frames = int(probe_meta.get("n_frames", 1) or 1)
                if start >= total_frames:
                    await send_progress(1.0, "Complete")
                    return {"status": "ok", "thumbnails": [], "totalFrames": total_frames, "nextStart": None}
            else:
                probe_meta = await _run_blocking(ImageLoader.probe, fpath)
                total_frames = int(probe_meta.get("n_frames", 1) or 1)

            end = min(total_frames, start + count)
            for frame_index in range(start, end):
                frame_data, _dead_mask, _meta = await _run_blocking(ImageLoader.load_frame, fpath, frame_index)
                if frame_data is None:
                    continue
                header = {"filename": os.path.basename(fpath), "frameIndex": frame_index}
                thumbnails.append(await _run_blocking(_render_thumbnail_item, frame_data, frame_index, header, thumb_render))

        next_start = start + len(thumbnails)
        if next_start >= total_frames:
            next_start = None

        await send_progress(1.0, "Complete")
        return {
            "status": "ok",
            "thumbnails": thumbnails,
            "totalFrames": total_frames,
            "nextStart": next_start,
            "chunkSize": count,
        }

    # ── batch_png_export: export multiple files to PNG in one action ──
    if action == "batch_png_export":
        files_list = payload.get("files", [])
        if not files_list:
            return {"status": "error", "message": "No files provided"}

        user_settings = payload.get("settings", {})
        dpi = int(user_settings.get("dpi", 100))
        show_colorbar = bool(user_settings.get("show_colorbar", False))
        cmap_name = user_settings.get("colormap") or user_settings.get("cmap") or "viridis"
        use_log = bool(user_settings.get("use_log", False))
        raw_clim = user_settings.get("clim")

        if isinstance(raw_clim, (list, tuple)) and len(raw_clim) >= 2 and raw_clim[0] is not None:
            clim = (float(raw_clim[0]), float(raw_clim[1]))
        else:
            clim = None

        generated = 0
        errors: list[str] = []
        n = len(files_list)

        for i, entry in enumerate(files_list):
            if cancel_event.is_set():
                break

            in_path = entry.get("input", "") if isinstance(entry, dict) else str(entry)
            out_path = entry.get("output", "") if isinstance(entry, dict) else ""

            if not in_path or not out_path:
                continue

            await send_progress(i / n, f"Exporting {i + 1}/{n}...")

            try:
                ext = os.path.splitext(in_path)[1].lower()
                if ext in {".h5", ".hdf5"}:
                    datasets = await _run_blocking(H5Handler.find_datasets, in_path)
                    entries = _serialize_h5_datasets(datasets)
                    ds_path = H5Handler.pick_default_dataset([item["path"] for item in entries])
                    if not ds_path:
                        errors.append(os.path.basename(in_path))
                        continue
                    data, _dead = await _run_blocking(H5Handler.load_frame, in_path, ds_path, 0, None)
                else:
                    data, _dead, _meta = await _run_blocking(ImageLoader.load, in_path)

                if data is None:
                    errors.append(os.path.basename(in_path))
                    continue

                frame_clim = clim
                if frame_clim is None:
                    stats = ImageRenderer.compute_stats(data)
                    frame_clim = (float(stats["min"]), float(stats["adjustedMax"] or stats["max"]))

                if show_colorbar:
                    png_bytes = await _run_blocking(
                        ImageRenderer.render_png_mpl, data,
                        cmap_name, use_log, frame_clim, dpi,
                    )
                else:
                    from PIL import Image as _Img
                    render_settings = {
                        "cmap": cmap_name,
                        "use_log": use_log,
                        "clim": frame_clim,
                    }
                    rgb = ImageRenderer._apply_colormap_lut(data, render_settings)
                    img = _Img.fromarray(rgb)
                    if dpi != 100:
                        s = dpi / 100
                        img = img.resize(
                            (int(img.width * s), int(img.height * s)),
                            _Img.Resampling.NEAREST,
                        )
                    buf = io.BytesIO()
                    img.save(buf, format="PNG", optimize=True)
                    png_bytes = buf.getvalue()

                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                Path(out_path).write_bytes(png_bytes)
                generated += 1

            except Exception as exc:
                errors.append(f"{os.path.basename(in_path)}: {exc}")

        await send_progress(1.0, "Complete")
        return {"status": "ok", "generated": generated, "errors": errors}

    # ── scan_folder: list image files in a directory ──────────
    if action == "scan_folder":
        folder = payload.get("folder", "")
        if not folder:
            return {"status": "error", "message": "Missing folder path"}
        
        is_desktop = bool(payload.get("_is_desktop", False))
        
        if not is_desktop:
            session_tmp_dir = payload.get("_session_tmp_dir", "")
            if not session_tmp_dir:
                return {"status": "error", "message": "Session not initialized"}
            
            real_tmp_dir = os.path.realpath(session_tmp_dir)
            real_folder = os.path.realpath(folder)
            
            # Path traversal protection: folder must be inside session tmp dir
            # 路径遍历防护：文件夹必须在 session 临时目录内
            if not real_folder.startswith(real_tmp_dir + os.sep) and real_folder != real_tmp_dir:
                return {"status": "error", "message": "Access denied: can only scan uploaded files"}
        else:
            real_folder = os.path.realpath(folder)
        
        if not os.path.isdir(real_folder):
            return {"status": "error", "message": "Invalid folder path"}
        
        recursive = bool(payload.get("recursive", False))
        image_exts = {".edf", ".tif", ".tiff", ".h5", ".hdf5"}
        files: list[str] = []
        if recursive:
            for root, _dirs, filenames in os.walk(real_folder):
                for fn in sorted(filenames):
                    if os.path.splitext(fn)[1].lower() in image_exts:
                        files.append(os.path.join(root, fn))
        else:
            for fn in sorted(os.listdir(real_folder)):
                full = os.path.join(real_folder, fn)
                if os.path.isfile(full) and os.path.splitext(fn)[1].lower() in image_exts:
                    files.append(full)
        return {"status": "ok", "files": files, "count": len(files)}

    # ── load / load_preview: single frame (fast path) ──
    if action in {"load", "load_preview"}:
        await send_progress(0.0, "Loading image...")
        fpath = payload.get("filePath", payload.get("files", [None])[0])
        if not fpath:
            return {"status": "error", "message": "No filePath provided"}

        include_image_data = _resolve_include_image_data(payload, default=True)
        ext = os.path.splitext(fpath)[1].lower()
        # Frontend sends 'frame', fall back to 'frame_index' / 前端发送 'frame'，回退到 'frame_index'
        frame_index = max(0, int(payload.get("frame", payload.get("frame_index", 0)) or 0))
        dataset_path = payload.get("dataset") or payload.get("h5_dataset_path")
        h5_channel = payload.get("channel") if payload.get("channel") is not None else payload.get("h5_channel")

        metadata: dict[str, Any] = {
            "fileType": ext.lstrip("."),
            "frameIndex": frame_index,
        }

        if ext in {".h5", ".hdf5"}:
            if not dataset_path:
                await send_progress(0.2, "Scanning HDF5 datasets...")
                datasets = await _run_blocking(H5Handler.find_datasets, fpath)
                dataset_entries = _serialize_h5_datasets(datasets)
                dataset_path = H5Handler.pick_default_dataset([item["path"] for item in dataset_entries])
                if not dataset_path:
                    return {"status": "error", "message": "No image dataset found"}
            else:
                dataset_entries = []

            await send_progress(0.5, "Reading frame…")
            data, _dead_mask = await _run_blocking(
                H5Handler.load_frame, fpath, dataset_path, frame_index, h5_channel,
            )

            if dataset_entries:
                selected_info = next((item for item in dataset_entries if item["path"] == dataset_path), None)
                metadata.update({
                    "totalFrames": int(selected_info.get("nFrames", 1) if selected_info else 1),
                    "h5Datasets": dataset_entries,
                    "nChannels": int(selected_info.get("nChannels", 0) if selected_info else 0),
                    "selectedDataset": dataset_path,
                })
            else:
                metadata["selectedDataset"] = dataset_path

            if h5_channel is not None:
                metadata["selectedChannel"] = h5_channel
        else:
            await send_progress(0.5, "Reading image data...")
            probe_meta = await _run_blocking(ImageLoader.probe, fpath)
            data, _dead_mask, meta = await _run_blocking(ImageLoader.load_frame, fpath, frame_index)
            if data is None:
                return {"status": "error", "message": "Failed to load image data"}
            metadata.update({
                "totalFrames": int(probe_meta.get("n_frames", 1) or 1),
                "nChannels": 0,
            })

        if cancel_event.is_set():
            raise asyncio.CancelledError()

        if data is None:
            return {"status": "error", "message": "No image data available"}

        height, width = data.shape
        metadata.update({
            "frameIndex": frame_index,
            "height": int(height),
            "width": int(width),
        })

        await send_progress(0.85, "Rendering image…")

        stats = ImageRenderer.compute_stats(data)
        gmin_lin, gmax_lin = ImageRenderer.global_range([data], use_log=False)
        gmin_log, gmax_log = ImageRenderer.global_range([data], use_log=True)
        contrast = {
            "autoMin": float(gmin_lin),
            "autoMax": float(gmax_lin),
            "logMin": float(gmin_log),
            "logMax": float(gmax_log),
        }

        render_settings = _build_render_settings(payload, contrast)
        data = _maybe_downsample(data, render_settings)
        png_bytes = ImageRenderer.render_png(data, render_settings)

        await send_progress(1.0, "Complete")
        result = {
            "status": "ok",
            "__binary_png__": png_bytes,
            "mime": "image/png",
            "width": int(data.shape[1]),
            "height": int(data.shape[0]),
            "frame": frame_index,
            "metadata": metadata,
            "stats": stats,
            "contrast": contrast,
        }
        if include_image_data:
            result["imageData"] = _serialize_image_data(data)
        return result

    # ── default fallback: scan datasets ─────────────────────────────────
    await send_progress(0.0, "Inspecting files...")
    files = payload.get("files", [])
    datasets: dict[str, Any] = {}
    for i, fpath in enumerate(files):
        await send_progress((i + 1) / max(len(files), 1), f"Scanning {fpath}")
        ext = os.path.splitext(fpath)[1].lower()
        if ext == ".h5":
            try:
                ds_info = await _run_blocking(H5Handler.find_datasets, fpath)
                datasets[fpath] = ds_info
            except Exception:
                datasets[fpath] = {"error": "Failed to inspect"}
    await send_progress(1.0, "Complete")
    return {"status": "ok", "datasets": datasets}


async def handle_h5convert(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """H5 conversion handler. H5格式转换处理函数。"""
    import time as _time
    await send_progress(0.0, "Initializing conversion...")

    source_dir = payload.get("source_dir", "") or payload.get("sourceDir", "")
    output_dir = payload.get("output_dir", "") or payload.get("outputDir", "")
    master_suffix = payload.get("master_suffix", "") or payload.get("refSuffix", "_master")
    table_format = payload.get("table_format", "csv") or payload.get("format", "csv")
    image_format = payload.get("image_format", "tiff") or payload.get("imageFormat", "tiff")

    converter = H5Converter(
        root_dir=source_dir,
        output_dir=output_dir,
        master_suffix=master_suffix,
        table_format=table_format,
        image_format=image_format,
    )

    dataset_config = payload.get("dataset_config", {}) or payload.get("datasets", {})
    datasets_list = payload.get("datasets", [])
    if isinstance(datasets_list, list):
        dataset_config = {item["path"]: item for item in datasets_list if isinstance(item, dict) and "path" in item}

    stop_event = threading.Event()

    def _on_stop():
        stop_event.set()
    cancel_event.add_done_callback(lambda _: _on_stop()) if hasattr(cancel_event, 'add_done_callback') else None

    t0 = _time.monotonic()
    loop = asyncio.get_event_loop()

    def _log(msg: str):
        pass

    def _progress(frac: float):
        asyncio.run_coroutine_threadsafe(
            send_progress(frac, f"Converting {int(frac * 100)}%..."), loop
        )

    def _run():
        converter.scan()
        converter.inspect_datasets()
        for ds_path, cfg in dataset_config.items():
            channels = cfg.get("channels") if isinstance(cfg, dict) else None
            export = cfg.get("export", True) if isinstance(cfg, dict) else True
            converter.set_dataset_config(ds_path, export=export, channels=channels)
        return converter.convert(log_fn=_log, progress_fn=_progress, stop_event=stop_event)

    stats = await _run_blocking(_run)
    elapsed = round(_time.monotonic() - t0, 2)
    await send_progress(1.0, "Complete")
    return {
        "status": "ok",
        "total": stats.get("files_processed", 0),
        "success": stats.get("images_exported", 0) + stats.get("files_processed", 0),
        "failed": stats.get("errors", 0),
        "elapsed": elapsed,
        "stats": stats,
    }


async def handle_h5convert_scan(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """H5 scan handler: scan directory and inspect datasets. H5扫描处理函数。"""
    import glob as _glob
    import h5py as _h5py

    await send_progress(0.0, "Scanning directory...")
    source_dir = payload.get("source_dir", "") or payload.get("sourceDir", "")
    master_suffix = payload.get("master_suffix", "") or payload.get("refSuffix", "_master")
    recursive = bool(payload.get("recursive", True))

    if not source_dir or not os.path.isdir(source_dir):
        return {"status": "error", "message": "Invalid source directory."}

    if recursive:
        all_h5 = _glob.glob(os.path.join(source_dir, "**", "*.h5"), recursive=True)
    else:
        all_h5 = []
        for f in sorted(os.listdir(source_dir)):
            full = os.path.join(source_dir, f)
            if os.path.isfile(full) and f.lower().endswith(".h5"):
                all_h5.append(full)
    if not all_h5:
        return {"status": "error", "message": "No .h5 files found."}

    sfx = master_suffix.strip() or "_master"
    masters = [f for f in all_h5
               if os.path.basename(f).lower().endswith(sfx.lower() + ".h5")]
    if not masters:
        masters = [all_h5[0]]

    ref_file = masters[0]
    target_count = len(masters)

    await send_progress(0.5, "Inspecting datasets...")

    datasets = []
    try:
        with _h5py.File(ref_file, "r") as f:
            def _visit(name: str, obj: Any) -> None:
                if not isinstance(obj, _h5py.Dataset):
                    return
                shape = obj.shape
                nd = len(shape)
                datasets.append({
                    "path": name,
                    "shape": str(shape),
                    "dtype": str(obj.dtype),
                    "ndim": nd,
                    "kind": _dataset_kind(shape),
                })
            f.visititems(_visit)
    except Exception as exc:
        return {"status": "error", "message": f"Failed to inspect H5: {exc}"}

    await send_progress(1.0, "Complete")
    return {
        "status": "ok",
        "datasets": datasets,
        "totalH5": len(all_h5),
        "targetH5": target_count,
        "refFile": os.path.basename(ref_file),
    }


async def handle_h5_extract(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """H5 extraction handler. H5提取处理函数。"""
    import time as _time
    await send_progress(0.0, "Starting extraction...")

    source_dir = payload.get("source_dir", "") or payload.get("sourceDir", "")
    output_dir = payload.get("output_dir", "") or payload.get("targetDir", "") or payload.get("outputDir", "")
    suffix_filter = payload.get("suffix_filter", "") or payload.get("suffix", "")
    prepend_folder = payload.get("prepend_folder", True) or payload.get("prependFolder", True)
    prefix = payload.get("prefix", "")
    conflict_policy = payload.get("conflict_policy", "rename") or payload.get("conflictPolicy", "rename")

    extractor = H5Extractor(
        source_dir=source_dir,
        target_dir=output_dir,
        suffix_filter=suffix_filter,
        prepend_folder=bool(prepend_folder),
        prefix=prefix,
        conflict_policy=conflict_policy,
    )

    stop_event = threading.Event()

    t0 = _time.monotonic()
    loop = asyncio.get_event_loop()

    def _log(msg: str):
        pass

    def _progress(frac: float):
        asyncio.run_coroutine_threadsafe(
            send_progress(frac, f"Extracting {int(frac * 100)}%..."), loop
        )

    def _run():
        return extractor.extract(log_fn=_log, progress_fn=_progress, stop_event=stop_event)

    stats = await _run_blocking(_run)
    elapsed = round(_time.monotonic() - t0, 2)
    await send_progress(1.0, "Complete")
    return {
        "status": "ok",
        "total": stats.get("total_files", 0),
        "success": stats.get("success_count", 0),
        "failed": stats.get("errors", 0),
        "elapsed": elapsed,
        "stats": stats,
    }


async def handle_h5_list_files(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """Scan directory for H5 files and return file list with metadata.
    扫描目录中的 H5 文件并返回带有元数据的文件列表。"""
    await send_progress(0.0, "扫描 H5 文件...")
    import glob as _glob

    source_dir = payload.get("source_dir", "") or payload.get("sourceDir", "")
    suffix_filter = (payload.get("suffix_filter", "") or payload.get("suffix", "")).strip().lower()
    recursive = bool(payload.get("recursive", True))

    if not source_dir or not os.path.isdir(source_dir):
        return {"status": "error", "message": "无效的源目录。"}

    if recursive:
        all_h5 = _glob.glob(os.path.join(source_dir, "**", "*.h5"), recursive=True)
    else:
        all_h5 = []
        for f in sorted(os.listdir(source_dir)):
            full = os.path.join(source_dir, f)
            if os.path.isfile(full) and f.lower().endswith(".h5"):
                all_h5.append(full)

    # Apply suffix filter / 应用后缀过滤
    if suffix_filter:
        target_ext = f"{suffix_filter}.h5" if not suffix_filter.endswith(".h5") else suffix_filter
        filtered = [f for f in all_h5 if os.path.basename(f).lower().endswith(target_ext)]
    else:
        filtered = all_h5

    # Build file info list / 构建文件信息列表
    files_info: list[dict[str, Any]] = []
    for fpath in sorted(filtered):
        try:
            stat = os.stat(fpath)
            files_info.append({
                "path": fpath,
                "name": os.path.basename(fpath),
                "size": stat.st_size,
                "parentDir": os.path.basename(os.path.dirname(fpath)),
            })
        except OSError:
            continue

    await send_progress(1.0, "完成")
    return {
        "status": "ok",
        "files": files_info,
        "total": len(files_info),
    }


def _cif_parse_error_hint(err_msg: str) -> str:
    """Generate a helpful hint for common CIF parse errors.
    为常见 CIF 解析错误生成有帮助的提示信息。"""
    err_lower = err_msg.lower()

    if "no structure" in err_lower:
        return ("提示：CIF 文件中未找到可解析的晶体结构。请确认文件包含 _atom_site_* 数据。\n"
                "Hint: No crystal structure found in CIF. Make sure the file contains _atom_site_* data.")
    if "occupancy" in err_lower:
        return ("提示：CIF 中存在无序原子位点（occupancy 异常），可尝试手动修正占有率值。\n"
                "Hint: Disordered atomic sites detected. Try fixing occupancy values manually.")
    if "custom" in err_lower:
        return ("提示：CIF 使用了 'Custom' 空间群名称，请替换为标准 H-M 符号（如 P2₁/c）。\n"
                "Hint: 'Custom' space group name is not supported. Use a standard H-M symbol.")
    if "space group" in err_lower or "symmetry" in err_lower:
        return ("提示：CIF 的空间群信息可能不标准，请检查 _symmetry_space_group_name_H-M 字段。\n"
                "Hint: The space group information may be non-standard. Check _symmetry_space_group_name_H-M.")
    if "parse" in err_lower or "syntax" in err_lower or "unexpected" in err_lower:
        return ("提示：CIF 文件格式可能有误，请检查是否包含非标准关键字或缺少必要字段。\n"
                "Hint: The CIF file format may be invalid. Check for non-standard keys or missing required fields.")
    if "not enough" in err_lower or "incomplete" in err_lower:
        return ("提示：CIF 文件信息不完整，缺少必要的晶体学数据（如晶胞参数或原子坐标）。\n"
                "Hint: The CIF file is incomplete. Lattice parameters or atomic coordinates may be missing.")

    return ("提示：请确认 CIF 文件是标准晶体结构文件（含晶胞参数和原子坐标），可从 CSD/ICSD/COD 等数据库获取。\n"
            "Hint: Ensure the CIF file is a standard crystal structure file with lattice parameters and atomic coordinates. "
            "Valid sources: CSD, ICSD, COD databases.")


async def handle_calibrant_generate(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """Calibrant generator handler. 标样生成器处理函数。

    Converts a CIF crystal structure file to a PyFAI .d calibrant file
    using pymatgen's XRD calculator.
    使用 pymatgen 的 XRD 计算器将 CIF 晶体结构文件转换为 PyFAI .d 标样文件。
    """
    await send_progress(0.0, "Reading CIF file...")

    file_path: str = payload.get("filePath", "")
    intensity_threshold: float = payload.get("intensityThreshold", 1.0)
    wavelength: str = "CuKa"

    if not file_path:
        return {"status": "error", "message": "No CIF file path provided."}

    try:
        with open(file_path, "r", encoding="utf-8") as fh:
            cif_content = fh.read()
    except Exception as exc:
        return {"status": "error", "message": f"Failed to read CIF file: {exc}"}

    try:
        from pymatgen.core import Structure
        from pymatgen.analysis.diffraction.xrd import XRDCalculator
    except ImportError:
        return {"status": "error", "message": "pymatgen is not installed. Please install it: pip install pymatgen"}

    # Try parsing; retry strategies for known CIF issues:
    # 1. Empty file → early check with clear message
    # 2. 'Custom' spacegroup → strip that line and retry
    # 3. occupancy sum > 1 (no structures) → increase occupancy_tolerance and retry
    # 尝试解析；针对已知 CIF 问题的重试策略：
    # 1. 空文件 → 提前检查并给出明确提示
    # 2. 'Custom' 空间群 → 去掉该行后重试
    # 3. 占有率总和 > 1（no structures）→ 提高 occupancy_tolerance 后重试
    if not cif_content.strip():
        return {"status": "error", "message":
                "CIF 文件为空，请提供有效的晶体结构 CIF 文件。\n"
                "The CIF file is empty. Please provide a valid CIF file with crystal structure data."}

    structure = None
    parse_error = None
    retried_occupancy = False
    retried_custom = False

    for attempt in range(3):
        try:
            kwargs = {"fmt": "cif"}
            if attempt >= 1:
                # Retry with higher occupancy tolerance for disordered structures
                # 针对无序结构提高占有率容差
                kwargs["occupancy_tolerance"] = 3.0
            structure = await _run_blocking(Structure.from_str, cif_content, **kwargs)
            break
        except Exception as exc:
            parse_error = str(exc)
            err_msg = str(exc)

            if "Custom" in err_msg and not retried_custom:
                retried_custom = True
                # Strip lines containing 'Custom' and retry
                # 去掉包含 'Custom' 的行后重试
                lines = cif_content.splitlines()
                filtered = [line for line in lines
                            if not (line.strip().startswith("_symmetry_space_group_name_H-M")
                                    and "Custom" in line)]
                cif_content = "\n".join(filtered)
                continue

            if ("Invalid CIF file with no structures" in err_msg
                    or "occupancies" in err_msg.lower()
                    or "occupancy" in err_msg.lower()):
                if not retried_occupancy:
                    retried_occupancy = True
                    # Retry with higher occupancy_tolerance
                    # 用提高后的 occupancy_tolerance 重试
                    continue
                else:
                    return {"status": "error", "message":
                            "CIF 文件中存在占有率超限的无序原子（occupancy sum > 1），"
                            "已尝试提高容差仍无法解析。请检查 CIF 文件中 _atom_site_occupancy 数据，"
                            "或将无序组分拆分为独立结构。\n"
                            "The CIF file contains disordered atoms with occupancy sum > 1. "
                            "Please check the _atom_site_occupancy values in your CIF file "
                            "or split disordered sites into separate structures."}

            # All other errors → return with a helpful hint
            hint = _cif_parse_error_hint(err_msg)
            return {"status": "error", "message": f"CIF parse error: {parse_error}\n{hint}"}

    if structure is None:
        hint = _cif_parse_error_hint(parse_error or "")
        return {"status": "error", "message": f"CIF parse error: {parse_error}\n{hint}"}

    await send_progress(0.3, "Calculating XRD pattern...")

    try:
        calculator = await _run_blocking(lambda: XRDCalculator(wavelength="CuKa"))
        pattern = await _run_blocking(calculator.get_pattern, structure)
    except Exception as exc:
        return {"status": "error", "message": f"XRD calculation failed: {exc}"}

    await send_progress(0.6, "Filtering peaks...")

    # pattern.x = 2θ, pattern.y = intensity
    # pattern.x = 2θ, pattern.y = 强度
    two_theta = pattern.x
    intensities = pattern.y

    if len(intensities) == 0:
        return {"status": "error", "message": "No diffraction peaks found."}

    max_intensity = float(np.max(intensities))
    if max_intensity <= 0:
        return {"status": "error", "message": "All intensities are zero."}

    # Convert to relative intensity and filter
    # 转换为相对强度并过滤
    rel_intensities = (intensities / max_intensity) * 100.0
    threshold = float(intensity_threshold)

    # Build hkl list from pattern.hkls (pymatgen 2023+ API, works in 2026.x)
    # 从 pattern.hkls 构建 hkl 列表（pymatgen 2023+ API，在 2026.x 可用）
    hkls_raw = None
    try:
        hkls_raw = pattern.hkls
        hkl_list = []
        for entry in hkls_raw:
            if entry and len(entry) > 0:
                first = entry[0]
                if isinstance(first, dict) and "hkl" in first:
                    hkl_raw = first["hkl"]
                    # pymatgen returns 4-index (h k i l) for hexagonal, 3-index (h k l) otherwise
                    # 4-index Miller-Bravais: i = -(h+k), drop it for pyFAI .d format
                    h = int(hkl_raw[0])
                    k = int(hkl_raw[1])
                    l = int(hkl_raw[3]) if len(hkl_raw) >= 4 else int(hkl_raw[2])
                    hkl_list.append((str(h), str(k), str(l)))
                else:
                    hkl_list.append(("", "", ""))
            else:
                hkl_list.append(("", "", ""))
    except Exception:
        hkl_list = [("", "", "")] * len(two_theta)

    # Build all detected peaks (unfiltered for chart) and filtered peaks (for table/.d file)
    # 构建全部峰（未过滤，用于图表）和过滤后峰（用于表格/.d文件）
    all_peaks = []
    filtered_peaks = []
    for i in range(len(two_theta)):
        rel_i = float(rel_intensities[i])
        tt = float(two_theta[i])
        wavelength_A = calculator.wavelength
        d_spacing = wavelength_A / (2.0 * np.sin(np.radians(tt / 2.0)))
        h, k, l = hkl_list[i] if i < len(hkl_list) else ("", "", "")
        hkl_str = f"({h} {k} {l})" if h != "" or k != "" or l != "" else "—"
        mult = 0
        if hkls_raw is not None and i < len(hkls_raw) and hkls_raw[i] and len(hkls_raw[i]) > 0:
            mult = hkls_raw[i][0].get("multiplicity", 0)
        peak = {
            "dSpacing": round(d_spacing, 6),
            "intensity": round(rel_i, 1),
            "twoTheta": round(tt, 4),
            "hkl": hkl_str,
            "multiplicity": mult,
        }
        all_peaks.append(peak)
        if rel_i >= threshold:
            filtered_peaks.append(peak)

    # Sort filtered peaks by d-spacing descending (PyFAI .d file convention)
    # 过滤后按 d 值降序排列（PyFAI .d 文件惯例）
    filtered_peaks.sort(key=lambda p: p["dSpacing"], reverse=True)

    if not filtered_peaks:
        return {"status": "error", "message": "No peaks retained above threshold. Please lower the threshold."}

    # Extract crystal info
    # 提取晶体信息
    formula = structure.composition.reduced_formula
    lattice = structure.lattice
    lattice_params = {
        "a": round(lattice.a, 4),
        "b": round(lattice.b, 4),
        "c": round(lattice.c, 4),
        "alpha": round(lattice.alpha, 2),
        "beta": round(lattice.beta, 2),
        "gamma": round(lattice.gamma, 2),
    }

    await send_progress(0.8, "Generating .d file...")

    # Build .d file content with proper format
    # 构建 .d 文件内容（标准格式）
    cell_str = f"a={lattice.a:.4f} b={lattice.b:.4f} c={lattice.c:.4f} alpha={lattice.alpha:.2f} beta={lattice.beta:.2f} gamma={lattice.gamma:.2f}"
    d_lines = [
        f"# Calibrant: {formula} ({formula})",
        f"# Cell: {cell_str}",
        "# Ref:",
        "",
        "# d_spacing  # (h k l)  mult  intensity",
    ]
    for p in filtered_peaks:
        d_lines.append(f"  {p['dSpacing']:.8f}  # {p['hkl']:>8s}  {p['multiplicity']:>4d}  {p['intensity']:.1f}")
    d_file_content = "\n".join(d_lines) + "\n"

    await send_progress(1.0, "Complete")
    return {
        "status": "ok",
        "formula": formula,
        "latticeParams": lattice_params,
        "peaks": filtered_peaks,
        "allPeaks": all_peaks,
        "dFileContent": d_file_content,
        "peaksCount": len(filtered_peaks),
        "wavelength": wavelength,
        "twoTheta": [float(x) for x in two_theta],
        "intensity": [float(y) for y in intensities],
    }


async def handle_png_generate(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """PNG generation handler. PNG生成处理函数。"""
    await send_progress(0.0, "Initializing PNG generation...")
    gen = PNGGenerator(
        source_folder=payload.get("source_dir", ""),
        output_folder=payload.get("output_dir", ""),
        template=payload.get("template"),
        recursive=payload.get("recursive", True),
    )

    def _run():
        return gen.generate()

    stats = await _run_blocking(_run)
    await send_progress(1.0, "Complete")
    return {"status": "ok", "stats": stats}


# Crystal system → space group number ranges / 晶系 → 空间群编号范围
CRYSTAL_SYSTEM_RANGES: dict[str, tuple[int, int]] = {
    "triclinic": (1, 2),
    "monoclinic": (3, 15),
    "orthorhombic": (16, 74),
    "tetragonal": (75, 142),
    "rhombohedral": (143, 167),
    "hexagonal": (168, 194),
    "cubic": (195, 230),
}

# Lattice type restrictions by crystal system / 各晶系允许的点阵类型
LATTICE_TYPES_BY_SYSTEM: dict[str, list[str]] = {
    "triclinic": ["P"],
    "monoclinic": ["P", "B", "A", "C", "I", "F"],
    "orthorhombic": ["P", "C", "A", "B", "I", "F"],
    "tetragonal": ["P", "I"],
    "rhombohedral": ["P", "R"],
    "hexagonal": ["P", "R"],
    "cubic": ["P", "I", "F"],
}

def get_cell_params(lattice: str) -> list[str]:
    required = {
        "cubic": ["a"],
        "tetragonal": ["a", "c"],
        "hexagonal": ["a", "c"],
        "rhombohedral": ["a", "alpha"],
        "orthorhombic": ["a", "b", "c"],
        "monoclinic": ["a", "b", "c", "beta"],
        "triclinic": ["a", "b", "c", "alpha", "beta", "gamma"],
    }
    return required.get(lattice, ["a", "b", "c", "alpha", "beta", "gamma"])


async def handle_cell_calibrant_generate(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """Cell-based calibrant generator. 晶胞参数标样生成器。

    Uses pyFAI Cell class to generate .D file from unit cell parameters.
    使用 pyFAI Cell 类从晶胞参数生成 .D 标样文件。
    """
    await send_progress(0.0, "Initializing cell parameters...")

    lattice: str = payload.get("lattice", "cubic")
    lattice_type: str = payload.get("latticeType", "P")
    space_group_num: int = payload.get("spaceGroupNumber", 1)
    long_name: str = payload.get("longName", "")
    doi: str = payload.get("doi", "")
    dmin: float = payload.get("dmin", 0.7)
    a: float = payload.get("a", 1.0)
    b: float = payload.get("b", 1.0)
    c: float = payload.get("c", 1.0)
    alpha: float = payload.get("alpha", 90.0)
    beta: float = payload.get("beta", 90.0)
    gamma: float = payload.get("gamma", 90.0)

    try:
        await send_progress(0.1, "Creating crystal cell...")
        cell = Cell(a=a, b=b, c=c, alpha=alpha, beta=beta, gamma=gamma,
                    lattice=lattice, lattice_type=lattice_type)

        if space_group_num > 0:
            import re as _re
            from pyFAI.crystallography.space_groups import ReflectionCondition
            for _name in dir(ReflectionCondition):
                _m = _re.match(r"^group(\d+)_(.+)$", _name)
                if _m and int(_m.group(1)) == space_group_num:
                    cell.selection_rules.append(getattr(ReflectionCondition, _name))
                    break

        await send_progress(0.3, f"Calculating reflections (dmin={dmin} Å)...")

        import tempfile as _tf, os as _os, shutil as _shutil
        tmp_dir = _tf.mkdtemp(prefix="cell_calibrant_")
        try:
            stem = long_name.replace(" ", "_") if long_name else "calibrant"
            cell.save(stem, long_name=long_name or "User-defined calibrant",
                      doi=doi or "", dmin=dmin, dest_dir=tmp_dir)

            d_file_path = _os.path.join(tmp_dir, f"{stem}.D")
            with open(d_file_path, "r", encoding="utf-8", errors="replace") as fh:
                d_file_content = fh.read()

            await send_progress(0.6, "Parsing reflections...")
            peaks = []
            for line in d_file_content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("#")
                if len(parts) < 2:
                    continue
                try:
                    d_val = float(parts[0].strip())
                except ValueError:
                    continue
                comment = parts[1].strip()
                hkl_match = __import__("re").search(r"\((-?\d+)\s+(-?\d+)\s+(-?\d+)(?:\s+(-?\d+))?\)", comment)
                if hkl_match:
                    # For 4-index (h k i l), skip i (group 3)
                    h, k = hkl_match.group(1), hkl_match.group(2)
                    l = hkl_match.group(4) if hkl_match.group(4) else hkl_match.group(3)
                    hkl_str = f"({h} {k} {l})"
                else:
                    hkl_str = ""
                mult_match = __import__("re").search(r"\)\s+(\d+)", comment)
                mult = int(mult_match.group(1)) if mult_match else 0
                peaks.append({"dSpacing": round(d_val, 6), "hkl": hkl_str,
                              "multiplicity": mult, "intensity": 1.0})

            peaks.sort(key=lambda p: p["dSpacing"], reverse=True)

            await send_progress(0.8, "Building response...")
            result = {
                "status": "ok",
                "dFileContent": d_file_content,
                "peaks": peaks,
                "peaksCount": len(peaks),
                "latticeParams": {"a": round(a, 4), "b": round(b, 4), "c": round(c, 4),
                                  "alpha": round(alpha, 2), "beta": round(beta, 2), "gamma": round(gamma, 2)},
                "lattice": lattice, "latticeType": lattice_type,
                "spaceGroupNumber": space_group_num, "longName": long_name, "dmin": dmin,
            }
            await send_progress(1.0, "Complete")
            return result
        finally:
            if _os.path.exists(tmp_dir):
                _shutil.rmtree(tmp_dir)
    except Exception as exc:
        return {"status": "error", "message": f"Cell calibrant generation failed: {exc}"}


async def handle_list_space_groups(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """List all space groups with metadata. 列出所有空间群。"""
    import re as _re
    from pyFAI.crystallography.space_groups import ReflectionCondition
    groups: list[dict[str, Any]] = []
    for name in dir(ReflectionCondition):
        m = _re.match(r"^group(\d+)_(.+)$", name)
        if m:
            num = int(m.group(1))
            cs = "triclinic"
            for sys_name, (lo, hi) in CRYSTAL_SYSTEM_RANGES.items():
                if lo <= num <= hi:
                    cs = sys_name
                    break
            groups.append({"number": num, "hmSymbol": m.group(2).replace("_", " ").replace("bar", "̄"),
                           "hmRaw": m.group(2), "crystalSystem": cs})
    groups.sort(key=lambda g: g["number"])
    return {"status": "ok", "spaceGroups": groups}


async def handle_manual_calibrant_generate(
    payload: dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict[str, Any]:
    """Manual calibrant generator. 手动标样生成器。

    Accepts a list of d-spacing (or q / 2θ) values from the user and
    generates a .D calibrant file.
    接受用户输入的 d 值（或 q / 2θ）列表，生成 .D 标样文件。
    """
    import re as _re
    import math as _math

    await send_progress(0.0, "Parsing input values...")

    text: str = payload.get("values", "")
    unit: str = payload.get("unit", "d")
    wavelength: float = payload.get("wavelength", 1.5406)

    if not text.strip():
        return {"status": "error", "message": "No values provided / 未输入任何数值。"}

    # Extract all numbers from the text (one per line or space/comma separated)
    # 从文本中提取所有数值
    numbers = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        # Split by whitespace, comma, semicolon
        parts = _re.split(r"[\s,;]+", line)
        for p in parts:
            p = p.strip()
            if not p:
                continue
            try:
                v = float(p)
                numbers.append(v)
            except ValueError:
                continue

    if not numbers:
        return {"status": "error", "message": "No numeric values found in input / 未找到有效的数值。"}

    await send_progress(0.3, f"Converting {len(numbers)} values to d-spacing...")

    # Convert to d-spacing
    # 转换为 d 值
    d_values = []
    for v in numbers:
        if v <= 0:
            continue
        if unit == "d":
            d = v
        elif unit == "q":
            # q = 2π / d → d = 2π / q
            d = 2.0 * _math.pi / v
        elif unit == "2theta":
            # Bragg: nλ = 2d sinθ → d = λ / (2 sin(θ))
            theta_rad = _math.radians(v / 2.0)
            sin_t = _math.sin(theta_rad)
            if sin_t <= 0:
                continue
            d = wavelength / (2.0 * sin_t)
        else:
            continue
        if d > 0:
            d_values.append(round(d, 6))

    if not d_values:
        return {"status": "error", "message": "No valid d-spacing values after conversion / 转换后没有有效的 d 值。"}

    d_values.sort(reverse=True)

    await send_progress(0.6, "Generating .D file...")

    # Build .D file content
    # 构建 .D 文件内容
    unit_label = {"d": "d (Å)", "q": "q (Å⁻¹)", "2theta": "2θ (°)"}.get(unit, unit)
    lines = [
        "# Calibrant: User Manual Input",
        "",
        f"# Input unit: {unit_label}",
        f"# Wavelength: {wavelength} Å" if unit == "2theta" else "",
        "",
        "# d_spacing  # (h k l)  mult  intensity",
    ]
    # Remove empty strings from wavelength line
    lines = [l for l in lines if l]

    peaks = []
    for i, d in enumerate(d_values):
        d_str = f"{d:.8f}"
        hkl_idx = i + 1
        hkl_str = f"({hkl_idx} 0 0)"
        comment = f"# {hkl_str:>8s}      1    100.0"
        lines.append(f"  {d_str}  {comment}")
        peaks.append({"dSpacing": d, "hkl": hkl_str, "multiplicity": 1})

    d_file_content = "\n".join(lines) + "\n"

    await send_progress(1.0, "Complete")
    return {
        "status": "ok",
        "dFileContent": d_file_content,
        "peaks": peaks,
        "peaksCount": len(peaks),
    }


# Route → handler mapping / 路由→处理函数映射
ROUTE_HANDLERS: dict[str, RouteHandler] = {
    "/api/integrate1d": handle_integrate1d,
    "/api/integrate_azimuth": handle_integrate_azimuth,
    "/api/integrate_cake": handle_integrate_cake,
    "/api/integrate_fiber": handle_integrate_fiber,
    "/api/viewer_config": handle_viewer_config,
    "/api/h5convert": handle_h5convert,
    "/api/h5convert_scan": handle_h5convert_scan,
    "/api/h5_extract": handle_h5_extract,
    "/api/h5_list_files": handle_h5_list_files,
    "/api/png_generate": handle_png_generate,
    "/api/export_integration": handle_export_integration,
    "/api/calibrant_generate": handle_calibrant_generate,
    "/api/cell_calibrant_generate": handle_cell_calibrant_generate,
    "/api/manual_calibrant_generate": handle_manual_calibrant_generate,
    "/api/list_space_groups": handle_list_space_groups,
}


# ---------------------------------------------------------------------------
# Module-level WebSocket service reference for shutdown coordination
# 模块级 WebSocket 服务引用，用于关机协调
# ---------------------------------------------------------------------------

_ws_service: WebSocketService | None = None


# ---------------------------------------------------------------------------
# HTTP health handler — existing endpoints preserved, ws_port added
# HTTP 健康处理程序 — 保留现有端点，添加 ws_port
# ---------------------------------------------------------------------------


class HealthHandler(BaseHTTPRequestHandler):
    """Embedded HTTP health service.
    内置 HTTP 健康服务。
    """

    expected_python: str = ""
    requirements_lock: str = ""
    ws_port: int | None = None
    cached_report: dict[str, Any] | None = None

    def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/download"):
            if _ws_service is not None:
                DownloadHandler.handle(self, _ws_service.session_manager)
            else:
                self._write_json({"error": "Service not ready"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if self.path != "/health":
            self._write_json({"error": "not-found"}, HTTPStatus.NOT_FOUND)
            return

        report = dict(self.cached_report or build_health_report(self.expected_python, self.requirements_lock, ws_port=self.ws_port))
        if self.ws_port is not None:
            report["ws_port"] = self.ws_port
        self._write_json(report)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/upload":
            if _ws_service is not None:
                UploadHandler.handle(self, _ws_service.session_manager)
            else:
                self._write_json({"error": "Service not ready"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if self.path == "/shutdown":
            self._write_json({"ok": True})
            # Stop WebSocket service first
            if _ws_service is not None:
                _ws_service.stop()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        if self.path == "/crash":
            self._write_json({"ok": True, "mode": "forced-crash"})
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(17)
        self._write_json({"error": "not-found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        """Write to stdout for Electron capture / 写入 stdout 供 Electron 捕获。"""
        print(f"[python-service] {self.address_string()} - {format % args}")


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------


def run_health(expected_python: str, requirements_lock: str) -> int:
    """CLI one-shot health check / 命令行一次性健康检查。"""
    report = build_health_report(expected_python, requirements_lock)
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["health_ok"] else 1


def _start_ws_in_thread(service: WebSocketService, host: str, port: int) -> None:
    """Run the WebSocket server in a dedicated thread with its own event loop."""
    try:
        asyncio.run(service.start(host, port))
    except Exception as exc:
        print(f"[python-service] WebSocket error: {exc}")
        import traceback
        traceback.print_exc()


def run_server(host: str, port: int, expected_python: str, requirements_lock: str) -> int:
    """Start the combined HTTP + WebSocket service / 启动 HTTP + WebSocket 组合服务。"""
    global _ws_service

    report = build_health_report(expected_python, requirements_lock)
    print(json.dumps({"startup": report}, ensure_ascii=False))
    if not report["health_ok"]:
        return 2

    session_mgr = SessionManager()
    ws_service = WebSocketService(session_manager=session_mgr)
    _ws_service = ws_service
    for route in API_ROUTES:
        handler_fn = ROUTE_HANDLERS.get(route)
        if handler_fn is None:
            continue
        ws_service.register_route(route, handler_fn)

    cached_report = dict(report)
    cached_report["ws_port"] = None
    handler = type("ConfiguredHealthHandler", (HealthHandler,), {
        "expected_python": expected_python,
        "requirements_lock": requirements_lock,
        "ws_port": None,
        "cached_report": cached_report,
    })

    print(f"[python-service] HTTP + WebSocket on {host}:{port}")

    threading.Thread(target=_warm_viewer_runtime, daemon=True).start()

    with ThreadingHTTPServer((host, port), handler) as httpd:
        httpd.serve_forever()
    return 0


# ---------------------------------------------------------------------------
# CORS-aware HTTP handler for standalone web deployment
# 用于独立 Web 部署的带 CORS 支持的 HTTP 处理程序
# ---------------------------------------------------------------------------

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Session-Id",
    "Access-Control-Max-Age": "86400",
}


class WebHealthHandler(BaseHTTPRequestHandler):
    """HTTP handler for standalone web server mode with CORS + WebSocket upgrade.
    独立 Web 服务器模式的 HTTP 处理程序（带 CORS 支持 + WebSocket 升级）。
    """

    expected_python: str = ""
    requirements_lock: str = ""
    ws_port: int | None = None
    cached_report: dict[str, Any] | None = None
    dist_dir: str = ""

    protocol_version = "HTTP/1.1"

    # MIME types for static file serving
    _MIME_TYPES: dict[str, str] = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".eot": "application/vnd.ms-fontobject",
    }

    # -- WebSocket upgrade support (single-port mode) --------------------------

    def _handle_ws_upgrade(self) -> None:
        """Handle WebSocket upgrade request on /ws path."""
        ws_key = self.headers.get("Sec-WebSocket-Key", "")
        if not ws_key:
            self._write_json({"error": "Missing Sec-WebSocket-Key"}, HTTPStatus.BAD_REQUEST)
            return

        # Compute accept key per RFC 6455
        accept_val = base64.b64encode(
            hashlib.sha1((ws_key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()
        ).decode()

        # Send 101 Switching Protocols
        self.send_response(HTTPStatus.SWITCHING_PROTOCOLS)
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept_val)
        for k, v in _CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

        # Create a new session for this connection
        session_id = _ws_service.session_manager.create_session() if _ws_service else ""

        # Send session_info
        self._ws_send(json.dumps({"type": "session_info", "session_id": session_id}))

        # Run the WebSocket message loop with its own asyncio event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task_ok = True
        try:
            while True:
                raw = self._ws_recv()
                if raw is None:
                    break
                try:
                    data = json.loads(raw)
                    msg_type = data.get("type", "")

                    if msg_type == "task_submit":
                        task_id = data.get("task_id", "")
                        route = data.get("route", "")
                        payload = data.get("payload", {})
                        cancel_event = asyncio.Event()
                        if _ws_service is not None:
                            _ws_service._cancel_events[task_id] = cancel_event

                        handler_fn = ROUTE_HANDLERS.get(route) if _ws_service else None
                        if handler_fn is None:
                            self._ws_send(json.dumps({
                                "type": "task_error",
                                "task_id": task_id,
                                "error": f"Unknown route: {route}",
                                "code": "UNKNOWN_ROUTE",
                            }))
                            continue

                        async def _send_progress(pct: float, msg: str = "") -> None:
                            if task_ok:
                                self._ws_send(json.dumps({
                                    "type": "task_progress",
                                    "task_id": task_id,
                                    "progress": pct,
                                    "message": msg,
                                }))

                        try:
                            result = loop.run_until_complete(
                                handler_fn(payload, _send_progress, session_id)
                            )
                            if not task_ok:
                                continue
                            # Check for binary payload
                            if isinstance(result, dict):
                                bin_data = result.pop("__binary_png__", None)
                                if bin_data is not None:
                                    header = json.dumps({
                                        "type": "task_binary",
                                        "task_id": task_id,
                                        **{k: v for k, v in result.items() if k != "data"},
                                    }).encode("utf-8")
                                    frame = struct.pack("!I", len(header)) + header + bin_data
                                    self._ws_send(frame, binary=True)

                                self._ws_send(json.dumps({
                                    "type": "task_complete",
                                    "task_id": task_id,
                                    "result": result,
                                }))
                            else:
                                self._ws_send(json.dumps({
                                    "type": "task_complete",
                                    "task_id": task_id,
                                    "result": result,
                                }))
                        except asyncio.CancelledError:
                            self._ws_send(json.dumps({
                                "type": "task_cancelled",
                                "task_id": task_id,
                            }))
                        except Exception as exc:
                            if task_ok:
                                task_ok = False
                                self._ws_send(json.dumps({
                                    "type": "task_error",
                                    "task_id": task_id,
                                    "error": str(exc),
                                    "code": "TASK_FAILED",
                                }))

                    elif msg_type == "task_cancel":
                        task_id = data.get("task_id", "")
                        if _ws_service is not None:
                            ev = _ws_service._cancel_events.pop(task_id, None)
                            if ev is not None:
                                ev.set()

                except (json.JSONDecodeError, KeyError):
                    continue
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            loop.close()
            # Cleanup session
            if _ws_service is not None and session_id:
                _ws_service.session_manager.remove_session(session_id)

    def _ws_send(self, data: str | bytes, binary: bool = False) -> None:
        """Send a WebSocket frame."""
        if isinstance(data, str):
            payload = data.encode("utf-8")
            opcode = 0x01  # text
        else:
            payload = data
            opcode = 0x02  # binary

        frame = bytearray()
        frame.append(0x80 | opcode)  # FIN + opcode

        length = len(payload)
        if length < 126:
            frame.append(length)
        elif length < 65536:
            frame.append(126)
            frame.extend(struct.pack("!H", length))
        else:
            frame.append(127)
            frame.extend(struct.pack("!Q", length))

        frame.extend(payload)
        self.wfile.write(bytes(frame))
        self.wfile.flush()

    def _ws_recv(self) -> str | None:
        """Receive a single WebSocket text frame. Returns None on close."""
        try:
            header = self.rfile.read(2)
            if len(header) < 2:
                return None

            opcode = header[0] & 0x0F
            masked = (header[1] & 0x80) != 0
            length = header[1] & 0x7F

            if opcode == 0x08:  # close
                return None

            if length == 126:
                ext = self.rfile.read(2)
                length = struct.unpack("!H", ext)[0]
            elif length == 127:
                ext = self.rfile.read(8)
                length = struct.unpack("!Q", ext)[0]

            mask_key = self.rfile.read(4) if masked else b""

            payload = self.rfile.read(length)
            if masked and mask_key:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

            if opcode == 0x02:  # binary — not expected from client, skip
                return None

            return payload.decode("utf-8", errors="replace")
        except (ConnectionResetError, BrokenPipeError, OSError):
            return None

    # -- HTTP handlers ----------------------------------------------------------

    def _write_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in _CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self) -> bool:
        """Serve static files from dist directory."""
        if not self.dist_dir:
            return False

        # Normalize path
        path = self.path.split("?")[0].split("#")[0]
        if path == "/":
            path = "/index.html"

        # Build file path (prevent directory traversal)
        file_path = os.path.normpath(os.path.join(self.dist_dir, path.lstrip("/")))
        if not file_path.startswith(self.dist_dir):
            self.send_error(HTTPStatus.FORBIDDEN)
            return True

        # Try to serve the file
        if os.path.isfile(file_path):
            ext = os.path.splitext(file_path)[1].lower()
            content_type = self._MIME_TYPES.get(ext, "application/octet-stream")

            try:
                file_size = os.path.getsize(file_path)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(file_size))
                # Cache static assets
                if ext in (".js", ".css", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".woff", ".woff2", ".ttf"):
                    self.send_header("Cache-Control", "public, max-age=31536000, immutable")
                for k, v in _CORS_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()

                if self.command != "HEAD":
                    with open(file_path, "rb") as f:
                        shutil.copyfileobj(f, self.wfile)
                return True
            except OSError:
                pass

        # SPA fallback: serve index.html for unmatched routes
        if not os.path.splitext(path)[1]:
            index_path = os.path.join(self.dist_dir, "index.html")
            if os.path.isfile(index_path):
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                index_size = os.path.getsize(index_path)
                self.send_header("Content-Length", str(index_size))
                for k, v in _CORS_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()

                if self.command != "HEAD":
                    with open(index_path, "rb") as f:
                        shutil.copyfileobj(f, self.wfile)
                return True

        return False

    def do_HEAD(self) -> None:  # noqa: N802
        if self.path == "/health":
            self.do_GET()
            return
        if not self._serve_static():
            self.send_error(HTTPStatus.NOT_FOUND)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        for k, v in _CORS_HEADERS.items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        # WebSocket upgrade on /ws
        if self.path == "/ws" and self.headers.get("Upgrade", "").lower() == "websocket":
            self._handle_ws_upgrade()
            return

        if self.path.startswith("/api/download"):
            if _ws_service is not None:
                DownloadHandler.handle(self, _ws_service.session_manager)
            else:
                self._write_json({"error": "Service not ready"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if self.path == "/health":
            report = dict(self.cached_report or build_health_report(
                self.expected_python, self.requirements_lock or "", ws_port=self.ws_port))
            if self.ws_port is not None:
                report["ws_port"] = self.ws_port
            report["mode"] = "web_server"
            self._write_json(report)
            return

        # Try to serve static files
        if self._serve_static():
            return

        self._write_json({"error": "not-found", "hint": "Available: GET /health"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/upload":
            if _ws_service is not None:
                UploadHandler.handle(self, _ws_service.session_manager)
            else:
                self._write_json({"error": "Service not ready"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if self.path == "/shutdown":
            self._write_json({"ok": True})
            if _ws_service is not None:
                _ws_service.stop()
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return
        self._write_json({"error": "not-found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[web-server] {self.address_string()} - {format % args}")


# ---------------------------------------------------------------------------
# Upload / Download HTTP handlers
# ---------------------------------------------------------------------------


class UploadHandler:
    """Handle POST /api/upload — save uploaded files to session-isolated tmp dir."""

    @staticmethod
    def handle(handler: BaseHTTPRequestHandler, session_manager: SessionManager) -> None:
        session_id = handler.headers.get("X-Session-Id")
        if not session_id:
            handler._write_json({"error": "Missing X-Session-Id header"}, HTTPStatus.BAD_REQUEST)
            return

        tmp_dir = session_manager.get_tmp_dir(session_id)
        tmp_dir_real = os.path.realpath(tmp_dir)
        if not os.path.isdir(tmp_dir_real):
            handler._write_json({"error": "Session directory not found"}, HTTPStatus.NOT_FOUND)
            return

        content_type = handler.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            handler._write_json({"error": "Expected multipart/form-data"}, HTTPStatus.BAD_REQUEST)
            return

        # Extract boundary from Content-Type header
        boundary: str | None = None
        for segment in content_type.split(";"):
            segment = segment.strip()
            if segment.startswith("boundary="):
                boundary = segment[9:].strip()
                if boundary.startswith('"') and boundary.endswith('"'):
                    boundary = boundary[1:-1]
                break

        if not boundary:
            handler._write_json({"error": "No boundary in Content-Type"}, HTTPStatus.BAD_REQUEST)
            return

        # Read request body
        content_length_str = handler.headers.get("Content-Length", "")
        try:
            content_length = int(content_length_str)
        except (ValueError, TypeError):
            content_length = 0

        if content_length <= 0:
            handler._write_json({"error": "No data received"}, HTTPStatus.BAD_REQUEST)
            return

        body = handler.rfile.read(content_length)

        # ---- manual multipart parser (stdlib-only) ----
        boundary_bytes = boundary.encode("utf-8")
        parts = body.split(b"--" + boundary_bytes)

        saved_files: list[dict[str, Any]] = []
        for part in parts:
            stripped = part.strip(b" \r\n")
            if stripped in (b"", b"--"):
                continue

            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue

            headers_bytes = part[:header_end]
            part_body = part[header_end + 4:]
            if part_body.endswith(b"\r\n"):
                part_body = part_body[:-2]

            # Parse Content-Disposition
            headers_text = headers_bytes.decode("utf-8", errors="replace")
            content_disposition: str | None = None
            for line in headers_text.split("\r\n"):
                if line.lower().startswith("content-disposition:"):
                    content_disposition = line[20:].strip()
                    break

            if not content_disposition:
                continue

            # Extract filename (skip non-file form fields)
            raw_filename: str | None = None
            for attr in content_disposition.split(";"):
                attr = attr.strip()
                if attr.lower().startswith("filename="):
                    raw_value = attr[9:].strip()
                    if raw_value.startswith('"') and raw_value.endswith('"'):
                        raw_value = raw_value[1:-1]
                    elif raw_value.startswith("'") and raw_value.endswith("'"):
                        raw_value = raw_value[1:-1]
                    raw_filename = raw_value
                    break

            if not raw_filename:
                continue

            # Security: use only the basename, strip directory components
            safe_name = os.path.basename(raw_filename)
            if not safe_name:
                continue

            # Conflict resolution: add _1, _2, … suffixes
            dest = os.path.join(tmp_dir_real, safe_name)
            counter = 1
            while os.path.exists(dest):
                name_part, ext_part = os.path.splitext(safe_name)
                dest = os.path.join(tmp_dir_real, f"{name_part}_{counter}{ext_part}")
                counter += 1

            with open(dest, "wb") as f:
                f.write(part_body)

            saved_files.append({
                "path": dest,
                "filename": os.path.basename(dest),
                "size": len(part_body),
            })

        handler._write_json({"files": saved_files})


class DownloadHandler:
    """Handle GET /api/download — stream a file from session directory."""

    @staticmethod
    def handle(handler: BaseHTTPRequestHandler, session_manager: SessionManager) -> None:
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(handler.path)
        query_params = parse_qs(parsed.query)

        requested_path = query_params.get("path", [None])[0]
        if not requested_path:
            handler._write_json({"error": "Missing 'path' query parameter"}, HTTPStatus.BAD_REQUEST)
            return

        session_id = handler.headers.get("X-Session-Id")
        if not session_id:
            handler._write_json({"error": "Missing X-Session-Id header"}, HTTPStatus.BAD_REQUEST)
            return

        tmp_dir = session_manager.get_tmp_dir(session_id)
        if not tmp_dir:
            handler._write_json({"error": "Session not found"}, HTTPStatus.NOT_FOUND)
            return

        session_dir = os.path.realpath(tmp_dir)

        # Resolve requested path: absolute → use directly, relative → join with session dir
        if os.path.isabs(requested_path):
            real_path = os.path.realpath(requested_path)
        else:
            real_path = os.path.realpath(os.path.join(session_dir, requested_path))

        # Path traversal protection — the file MUST be inside the session tmp dir
        if not real_path.startswith(session_dir + os.sep) and real_path != session_dir:
            handler._write_json({"error": "Access denied"}, HTTPStatus.FORBIDDEN)
            return

        if not os.path.isfile(real_path):
            handler._write_json({"error": "File not found"}, HTTPStatus.NOT_FOUND)
            return

        # Stream the file back
        file_size = os.path.getsize(real_path)
        filename = os.path.basename(real_path)

        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", "application/octet-stream")
        handler.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        handler.send_header("Content-Length", str(file_size))
        for k, v in _CORS_HEADERS.items():
            handler.send_header(k, v)
        handler.end_headers()

        with open(real_path, "rb") as f:
            shutil.copyfileobj(f, handler.wfile)


def run_web_server(host: str, port: int, requirements_lock: str | None = None) -> int:
    """Start standalone web server mode (no Electron dependency).
    启动独立 Web 服务器模式（无 Electron 依赖）。
    
    Binds to 0.0.0.0 by default for external access.
    Includes CORS headers for browser-based clients.
    HTTP and WebSocket share the same port (WebSocket via /ws upgrade).
    默认绑定 0.0.0.0 以允许外部访问。
    包含 CORS 头供浏览器客户端使用。
    HTTP 和 WebSocket 共享同一端口（WebSocket 通过 /ws 路径升级）。
    """
    global _ws_service

    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    expected_python = python_version

    report = build_health_report(expected_python, requirements_lock or "")
    print(json.dumps({"startup": report, "mode": "web_server"}, ensure_ascii=False))

    session_mgr = SessionManager()
    ws_service = WebSocketService(session_manager=session_mgr)
    _ws_service = ws_service
    for route in API_ROUTES:
        handler_fn = ROUTE_HANDLERS.get(route)
        if handler_fn is None:
            continue
        ws_service.register_route(route, handler_fn)

    cached_report = dict(report)
    cached_report["ws_port"] = None

    # Find dist directory for static file serving
    script_dir = os.path.dirname(os.path.abspath(__file__))
    dist_dir = os.path.join(os.path.dirname(script_dir), "dist")
    if not os.path.isdir(dist_dir):
        dist_dir = ""

    handler = type("WebConfiguredHandler", (WebHealthHandler,), {
        "expected_python": expected_python,
        "requirements_lock": requirements_lock or "",
        "ws_port": None,
        "cached_report": cached_report,
        "dist_dir": dist_dir,
    })

    print(f"[web-server] HTTP + WebSocket on {host}:{port} (single-port mode)")
    print(f"[web-server] Session isolation enabled. Each client gets isolated temp directory.")
    print(f"[web-server] No pyFAI-calib2 launcher — server mode only.")

    threading.Thread(target=_warm_viewer_runtime, daemon=True).start()

    try:
        with ThreadingHTTPServer((host, port), handler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[web-server] Shutting down...")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build CLI arguments / 构建 CLI 参数。"""
    parser = argparse.ArgumentParser(description="X-FAIS Python runtime service")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health", help="run a one-shot health check")
    health_parser.add_argument("--expected-python", required=True)
    health_parser.add_argument("--requirements-lock", required=True)

    serve_parser = subparsers.add_parser("serve", help="start the Electron-embedded runtime server")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, required=True)
    serve_parser.add_argument("--expected-python", required=True)
    serve_parser.add_argument("--requirements-lock", required=True)

    web_parser = subparsers.add_parser(
        "serve_web",
        help="start standalone web server (no Electron, session-isolated, CORS enabled)",
    )
    web_parser.add_argument("--host", default="0.0.0.0",
                            help="bind address (default: 0.0.0.0 for external access)")
    web_parser.add_argument("--port", type=int, default=8765,
                            help="HTTP port (default: 8765, WebSocket on port+1)")
    web_parser.add_argument("--requirements-lock", default=None,
                            help="optional requirements.lock.txt for dependency check")

    return parser


def main() -> int:
    """Main entrypoint / 主入口。"""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "health":
        return run_health(args.expected_python, args.requirements_lock)
    if args.command == "serve":
        return run_server(args.host, args.port, args.expected_python, args.requirements_lock)
    if args.command == "serve_web":
        return run_web_server(args.host, args.port, args.requirements_lock)

    parser.error("Unsupported command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
