#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_server_read_gate.py — server-mode read whitelist (v0.5.0)
服务器模式读取围栏（services/paths.py + 分发审计）的单元测试。

Covers: ``configured_input_roots`` parsing, ``validate_server_read_path``
containment (input roots / session workspace / output root), ``..``/NUL
rejection, and the payload audit sweep (nested structures; non-path strings
and embedded content must never be flagged).
覆盖：输入根解析、读取围栏 containment（白名单根/会话工作区/输出根）、
``..`` 与 NUL 拒绝、载荷审计（嵌套结构；非路径字符串与内嵌内容不误伤）。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_BETA_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_BETA_ROOT) not in sys.path:
    sys.path.insert(0, str(_BETA_ROOT))

from python.services.paths import (  # noqa: E402
    audit_payload_read_paths,
    configured_input_roots,
    validate_server_read_path,
)


@pytest.fixture
def input_roots(tmp_path, monkeypatch):
    """Two admin-opened folders, each containing one file. 两个开放目录。"""
    root_a = tmp_path / "data_a"
    root_b = tmp_path / "data_b"
    root_a.mkdir()
    (root_a / "sample.tif").write_bytes(b"x")
    root_b.mkdir()
    (root_b / "other.h5").write_bytes(b"y")
    monkeypatch.setenv("XFAIS_INPUT_ROOTS", os.pathsep.join([str(root_a), str(root_b)]))
    return {"a": root_a, "b": root_b}


class TestConfiguredInputRoots:
    def test_parses_and_resolves(self, input_roots):
        roots = configured_input_roots()
        assert os.path.realpath(str(input_roots["a"])) in roots
        assert os.path.realpath(str(input_roots["b"])) in roots

    def test_dedupes_and_skips_empty_entries(self, monkeypatch, tmp_path):
        one = str(tmp_path / "one")
        monkeypatch.setenv(
            "XFAIS_INPUT_ROOTS", os.pathsep.join(["", one, one, "   "])
        )
        assert configured_input_roots() == [os.path.realpath(one)]

    def test_unset_returns_empty(self, monkeypatch):
        monkeypatch.delenv("XFAIS_INPUT_ROOTS", raising=False)
        assert configured_input_roots() == []


class TestValidateServerReadPath:
    def test_inside_root_allowed(self, input_roots):
        target = str(input_roots["a"] / "sample.tif")
        assert validate_server_read_path(target) == os.path.realpath(target)

    def test_session_workspace_allowed(self, input_roots, tmp_path):
        session = tmp_path / "session"
        session.mkdir()
        upload = session / "upload.edf"
        upload.write_bytes(b"z")
        result = validate_server_read_path(str(upload), session_tmp=str(session))
        assert result == os.path.realpath(str(upload))

    def test_outside_everything_rejected(self, input_roots, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("no")
        with pytest.raises(ValueError, match="XFAIS_INPUT_ROOTS"):
            validate_server_read_path(str(secret))

    def test_dotdot_rejected_even_inside_root(self, input_roots):
        with pytest.raises(ValueError, match=r"\.\."):
            validate_server_read_path(str(input_roots["a"] / ".." / "data_b"))

    def test_nul_rejected(self):
        with pytest.raises(ValueError):
            validate_server_read_path("bad\x00path")

    def test_empty_rejected(self):
        with pytest.raises(ValueError):
            validate_server_read_path("   ")

    def test_output_root_allowed(self, input_roots, tmp_path, monkeypatch):
        out_root = tmp_path / "results"
        out_root.mkdir()
        monkeypatch.setenv("XFAIS_OUTPUT_ROOT", str(out_root))
        target = out_root / "x.tif"
        target.write_bytes(b"z")
        assert validate_server_read_path(str(target)) == os.path.realpath(str(target))

    def test_error_message_is_bilingual(self, input_roots, tmp_path):
        secret = tmp_path / "s.bin"
        secret.write_bytes(b"s")
        with pytest.raises(ValueError, match="服务器模式只能读取"):
            validate_server_read_path(str(secret))


class TestPayloadAudit:
    def test_nested_offender_rejects_task(self, input_roots, tmp_path):
        secret = tmp_path / "outside.bin"
        secret.write_bytes(b"s")
        payload = {
            "files": [str(input_roots["a"] / "sample.tif")],
            "extra": {"deep": [str(secret)]},
        }
        with pytest.raises(ValueError, match="outside the server read whitelist"):
            audit_payload_read_paths(payload)

    def test_allowed_paths_pass(self, input_roots, tmp_path):
        session = tmp_path / "session"
        session.mkdir()
        (session / "u.edf").write_bytes(b"u")
        payload = {
            "files": [str(input_roots["a"] / "sample.tif")],
            "filePath": str(session / "u.edf"),
        }
        audit_payload_read_paths(payload, session_tmp=str(session))

    def test_output_dir_outside_allowed_trees_rejected(self, input_roots, tmp_path):
        payload = {"output_dir": str(tmp_path / "anywhere"), "files": []}
        with pytest.raises(ValueError):
            audit_payload_read_paths(payload)

    def test_non_path_strings_ignored(self):
        long_content = "/" + "x" * 4096  # 超长 → 视为内嵌内容，不是路径引用
        payload = {
            "unit": "q_A^-1",
            "script": long_content,
            "url": "https://example.com/data",
            "name": "relative/name.tif",
            "count": 3,
            "flag": True,
        }
        audit_payload_read_paths(payload)

    def test_multiple_offenders_reported_with_truncation(self, input_roots, tmp_path):
        offenders = []
        for idx in range(6):  # 超过 5 条展示上限 → 触发 "(+1 more)" 截断
            p = tmp_path / f"o{idx}.bin"
            p.write_bytes(b"x")
            offenders.append(str(p))
        with pytest.raises(ValueError, match="\\+1 more"):
            audit_payload_read_paths({"files": offenders})
