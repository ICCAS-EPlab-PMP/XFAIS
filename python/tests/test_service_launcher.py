#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_service_launcher.py — Tests for embedded Python service launcher
test_service_launcher.py — 内置 Python 服务启动器测试
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import numpy as np

from python.service_launcher import (
    WebSocketService,
    build_health_report,
    handle_integrate_cake,
    handle_viewer_config,
    normalize_requirement_name,
    parse_required_packages,
)


def test_normalize_requirement_name() -> None:
    """标准化名称一致 / Requirement names normalize consistently."""
    assert normalize_requirement_name("PyYAML") == "pyyaml"
    assert normalize_requirement_name("my.package_name") == "my-package-name"


def test_parse_required_packages_reads_lock_file(tmp_path: Path) -> None:
    """锁文件可被正确解析 / Lock files are parsed correctly."""
    lock_file = tmp_path / "requirements.lock.txt"
    lock_file.write_text("numpy==1.0.0\n# comment\npyFAI>=0.1\n", encoding="utf-8")

    assert parse_required_packages(str(lock_file)) == ["numpy", "pyfai"]


def test_build_health_report_marks_missing_dependency(tmp_path: Path) -> None:
    """缺失依赖会标记为 missing / Missing deps are marked as missing."""
    lock_file = tmp_path / "requirements.lock.txt"
    lock_file.write_text("definitely-not-installed-package==9.9.9\n", encoding="utf-8")

    report = build_health_report("3", str(lock_file))

    assert report["dependency_status"] == "missing"
    assert report["health_ok"] is False
    assert json.loads(json.dumps(report))["missing_dependencies"] == ["definitely-not-installed-package"]


async def _noop_progress(_progress: float, _message: str) -> None:
    """空进度回调 / No-op progress callback."""


def test_handle_viewer_config_load_preview_returns_image_data() -> None:
    """预览加载返回真实图像 / Preview loading returns real image data."""
    fixture = Path(__file__).resolve().parents[2] / "test-fixtures" / "test.edf"

    result = asyncio.run(
        handle_viewer_config(
            {"action": "load_preview", "files": [str(fixture)]},
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert result["imageData"]
    assert result["metadata"]["height"] > 0
    assert result["metadata"]["width"] > 0
    assert result["metadata"]["fileType"] == "edf"


def test_handle_viewer_config_load_preview_can_omit_image_data_with_camel_case() -> None:
    """轻量预览可省略 imageData / Lightweight preview can omit imageData."""
    fixture = Path(__file__).resolve().parents[2] / "test-fixtures" / "test.edf"

    result = asyncio.run(
        handle_viewer_config(
            {"action": "load_preview", "files": [str(fixture)], "includeImageData": False},
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert "imageData" not in result
    assert result["metadata"]["height"] > 0
    assert result["metadata"]["width"] > 0
    assert result["stats"]
    assert result["contrast"]


def test_handle_viewer_config_load_h5_returns_image_and_metadata() -> None:
    """H5 加载返回图像与数据集元信息 / H5 load returns image and dataset metadata."""
    fixture = Path(__file__).resolve().parents[2] / "test-fixtures" / "test.h5"

    result = asyncio.run(
        handle_viewer_config(
            {"action": "load", "files": [str(fixture)]},
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert result["imageData"]
    assert result["metadata"]["height"] > 0
    assert result["metadata"]["width"] > 0
    assert result["metadata"]["fileType"] == "h5"
    assert result["metadata"]["h5Datasets"]


def test_handle_viewer_config_load_h5_can_omit_image_data_with_snake_case() -> None:
    """轻量 H5 加载可省略 imageData / Lightweight H5 load can omit imageData."""
    fixture = Path(__file__).resolve().parents[2] / "test-fixtures" / "test.h5"

    result = asyncio.run(
        handle_viewer_config(
            {"action": "load", "files": [str(fixture)], "include_image_data": False},
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert "imageData" not in result
    assert result["metadata"]["height"] > 0
    assert result["metadata"]["width"] > 0
    assert result["metadata"]["fileType"] == "h5"
    assert result["metadata"]["h5Datasets"]
    assert result["stats"]
    assert result["contrast"]


def test_handle_viewer_config_png_export_writes_file(tmp_path: Path) -> None:
    """PNG 导出直接写入目标文件 / PNG export writes directly to output path."""
    fixture = Path(__file__).resolve().parents[2] / "test-fixtures" / "test.edf"
    output_path = tmp_path / "viewer-export.png"

    result = asyncio.run(
        handle_viewer_config(
            {
                "action": "png_export",
                "filePath": str(fixture),
                "output_path": str(output_path),
                "settings": {
                    "use_log": False,
                    "clim": [0.0, 10.0],
                    "dpi": 100,
                },
            },
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert result["savedPath"] == str(output_path)
    assert output_path.exists()
    assert output_path.read_bytes().startswith(b"\x89PNG")


def test_handle_viewer_config_load_thumbnails_chunk_returns_partial_results() -> None:
    """缩略图分块加载仅返回请求区间 / Thumbnail chunk loading returns the requested slice only."""
    fixture = Path(__file__).resolve().parents[2] / "test-fixtures" / "viewer-multiframe.h5"

    result = asyncio.run(
        handle_viewer_config(
            {
                "action": "load_thumbnails_chunk",
                "filePath": str(fixture),
                "start": 0,
                "count": 1,
            },
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert result["totalFrames"] == 2
    assert result["nextStart"] == 1
    thumbnails = result["thumbnails"]
    assert len(thumbnails) == 1
    assert thumbnails[0]["index"] == 0
    assert isinstance(thumbnails[0]["b64"], str)


def test_handle_viewer_config_open_file_returns_first_frame_and_thumbnails() -> None:
    """单次打开返回首帧和首批缩略图 / One-shot open returns the first frame and first thumbnails."""
    fixture = Path(__file__).resolve().parents[2] / "test-fixtures" / "viewer-multiframe.h5"

    result = asyncio.run(
        handle_viewer_config(
            {
                "action": "open_file",
                "filePath": str(fixture),
            },
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert result["metadata"]["totalFrames"] == 2
    assert result["metadata"]["selectedDataset"]
    assert result["stats"]
    assert result["contrast"]
    assert result["thumbnails"] == []
    assert result["nextStart"] == 0
    assert result["mime"] == "image/png"


def test_handle_viewer_config_open_file_non_h5_keeps_multiframe_metadata(monkeypatch) -> None:
    """非 H5 多帧打开保留帧数信息 / Non-H5 multi-frame open preserves frame count metadata."""

    def _fake_probe(_path: str) -> dict[str, object]:
        return {"n_frames": 3, "height": 4, "width": 5}

    def _fake_load_frame(_path: str, frame_index: int):
        return np.ones((4, 5), dtype=np.float32) * (frame_index + 1), None, {"frame_index": frame_index, "n_frames": 3}

    monkeypatch.setattr("python.service_launcher.ImageLoader.probe", _fake_probe)
    monkeypatch.setattr("python.service_launcher.ImageLoader.load_frame", _fake_load_frame)

    result = asyncio.run(
        handle_viewer_config(
            {
                "action": "open_file",
                "filePath": "fake.edf",
                "frame_index": 1,
            },
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert result["metadata"]["totalFrames"] == 3
    assert result["metadata"]["frameIndex"] == 1
    assert result["nextStart"] == 0


def test_handle_viewer_config_load_thumbnails_chunk_non_h5_reads_requested_slice(monkeypatch) -> None:
    """非 H5 缩略图分块按请求区间读取 / Non-H5 thumbnail chunking reads the requested slice."""

    def _fake_probe(_path: str) -> dict[str, object]:
        return {"n_frames": 3, "height": 4, "width": 5}

    def _fake_load_frame(_path: str, frame_index: int):
        return np.ones((4, 5), dtype=np.float32) * (frame_index + 1), None, {"frame_index": frame_index, "n_frames": 3}

    monkeypatch.setattr("python.service_launcher.ImageLoader.probe", _fake_probe)
    monkeypatch.setattr("python.service_launcher.ImageLoader.load_frame", _fake_load_frame)

    result = asyncio.run(
        handle_viewer_config(
            {
                "action": "load_thumbnails_chunk",
                "filePath": "fake.edf",
                "start": 1,
                "count": 2,
            },
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert result["totalFrames"] == 3
    assert result["nextStart"] is None
    assert [item["index"] for item in result["thumbnails"]] == [1, 2]


def test_websocket_binary_header_omits_image_data_when_result_omits_it() -> None:
    """轻量二进制帧头不带 imageData / Lightweight binary header omits imageData."""

    class DummyWebSocket:
        def __init__(self) -> None:
            self.messages: list[bytes | str] = []

        async def send(self, payload) -> None:
            self.messages.append(payload)

    async def _binary_handler(_payload, _send_progress, _cancel_event):
        return {
            "status": "ok",
            "__binary_png__": b"png-bytes",
            "mime": "image/png",
            "width": 4,
            "height": 3,
            "frame": 0,
            "metadata": {"fileType": "edf"},
            "stats": {"mean": 1.0},
            "contrast": {"autoMin": 0.0, "autoMax": 1.0, "logMin": 0.0, "logMax": 1.0},
        }

    ws = DummyWebSocket()
    service = WebSocketService()
    service.register_route("/api/test/binary", _binary_handler)

    asyncio.run(service._run_task(ws, "task-1", "/api/test/binary", {}, asyncio.Event()))

    assert len(ws.messages) == 1
    frame = ws.messages[0]
    assert isinstance(frame, bytes)
    header_len = int.from_bytes(frame[:4], "big")
    header = json.loads(frame[4:4 + header_len].decode("utf-8"))
    assert header["type"] == "task_binary"
    assert header["task_id"] == "task-1"
    assert "imageData" not in header


def test_handle_integrate_cake_returns_displayable_traces(monkeypatch) -> None:
    """CAKE 返回前端可绘制 traces / CAKE returns frontend-displayable traces."""

    captured: dict[str, object] = {}

    class DummyResult:
        radial = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        intensity = np.array([10.0, 20.0, 30.0], dtype=np.float32)

    class DummyIntegrator:
        def integrate1d(self, **kwargs):
            captured.update(kwargs)
            return DummyResult()

    def _fake_from_manual_params(**_kwargs):
        return DummyIntegrator(), 0.0, 0.0

    def _fake_image_load(_path):
        return np.ones((4, 4), dtype=np.float32), np.zeros((4, 4), dtype=bool), {"filename": "cake.edf"}

    def _fake_mask_build(data, *_args, **_kwargs):
        return np.zeros_like(data, dtype=bool)

    monkeypatch.setattr("python.service_launcher.IntegratorFactory.from_manual_params", _fake_from_manual_params)
    monkeypatch.setattr("python.service_launcher.ImageLoader.load", _fake_image_load)
    monkeypatch.setattr("python.service_launcher.MaskBuilder.build", _fake_mask_build)

    result = asyncio.run(
        handle_integrate_cake(
            {
                "files": ["cake.edf"],
                "geometry": {
                    "manual": {
                        "pixel_size_um": 172.0,
                        "dist_mm": 200.0,
                        "wavelength_A": 1.5418,
                        "center_x_px": 512.0,
                        "center_y_px": 512.0,
                    }
                },
                "options": {
                    "npt_rad": 3,
                    "unit": "q_nm^-1",
                    "azimuth_min": -30.0,
                    "azimuth_max": 45.0,
                    "radial_min": 0.1,
                    "radial_max": 0.3,
                    "correct_solid_angle": True,
                },
            },
            _noop_progress,
            asyncio.Event(),
        )
    )

    assert result["status"] == "ok"
    assert result["traces"] == [{
        "x": [0.10000000149011612, 0.20000000298023224, 0.30000001192092896],
        "y": [10.0, 20.0, 30.0],
        "name": "cake.edf",
    }]
    assert captured["azimuth_range"] == (-30.0, 45.0)
    assert captured["radial_range"] == (0.1, 0.3)
