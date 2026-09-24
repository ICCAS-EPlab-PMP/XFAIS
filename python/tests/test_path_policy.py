#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_path_policy.py — output-path choke point (v0.3.0 security hardening)
输出路径统一校验（services/paths.py）的单元测试。

Covers: malformed-input rejection, normalization (relative/``..`` collapse),
optional passthrough semantics, and XFAIS_OUTPUT_ROOT containment including
``..`` escapes and out-of-root absolute paths. Desktop mode (no root
configured) must keep accepting arbitrary absolute paths unchanged in
semantics — the helper only normalizes.
覆盖：非法输入拒绝、路径归一（相对路径与 ``..`` 折叠）、optional 空值透传、
XFAIS_OUTPUT_ROOT 目录约束（含 ``..`` 逃逸与根外绝对路径）。桌面模式
（未配置根目录）必须继续接受任意绝对路径——仅做归一化。
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
    validated_output_path,
    validated_output_path_optional,
)


class TestMalformedInput:
    @pytest.mark.parametrize("bad", [None, "", "   ", 123, ["x"], b"/tmp/x"])
    def test_rejects_non_string_or_empty(self, bad):
        with pytest.raises(ValueError):
            validated_output_path(bad)

    def test_rejects_nul_byte(self):
        with pytest.raises(ValueError):
            validated_output_path("C:\\out\\x\x00.png")

    def test_optional_passes_empty_through(self):
        assert validated_output_path_optional(None) == ""
        assert validated_output_path_optional("") == ""
        assert validated_output_path_optional("   ") == ""


class TestNormalization:
    def test_relative_becomes_absolute(self):
        result = validated_output_path("out_dir/result.dat")
        assert os.path.isabs(result)
        assert result.endswith("result.dat")

    def test_dotdot_segments_hard_rejected(self):
        # Raw `..` is treated as hostile regardless of where it resolves.
        with pytest.raises(ValueError):
            validated_output_path("out_dir/../result.dat")
        with pytest.raises(ValueError):
            validated_output_path("/tmp/a/../../etc/passwd")

    def test_absolute_survives_normalized(self, tmp_path):
        target = tmp_path / "sub" / "res.txt"
        result = validated_output_path(str(target), field="output_path")
        assert os.path.isabs(result)
        assert result.endswith("res.txt")


class TestRootContainment:
    def test_inside_root_passes(self, tmp_path, monkeypatch):
        root = tmp_path / "results"
        root.mkdir()
        monkeypatch.setenv("XFAIS_OUTPUT_ROOT", str(root))
        ok = validated_output_path(str(root / "a" / "b.dat"))
        assert ok.startswith(str(root))

    def test_dotdot_escape_rejected(self, tmp_path, monkeypatch):
        root = tmp_path / "results"
        root.mkdir()
        monkeypatch.setenv("XFAIS_OUTPUT_ROOT", str(root))
        escape = str(root / ".." / "escape.dat")
        with pytest.raises(ValueError):
            validated_output_path(escape)

    def test_symlink_escape_rejected(self, tmp_path, monkeypatch):
        # Symlink inside the root pointing outside — caught by the realpath
        # containment check even though the raw path has no `..`.
        root = tmp_path / "results"
        root.mkdir()
        outside = tmp_path / "elsewhere"
        outside.mkdir()
        link = root / "jump"
        try:
            link.symlink_to(outside)
        except OSError:
            pytest.skip("symlink creation not permitted on this platform / 本平台无权创建符号链接")
        monkeypatch.setenv("XFAIS_OUTPUT_ROOT", str(root))
        with pytest.raises(ValueError):
            validated_output_path(str(link / "x.dat"))

    def test_outside_absolute_rejected(self, tmp_path, monkeypatch):
        root = tmp_path / "results"
        root.mkdir()
        other = tmp_path / "elsewhere"
        other.mkdir()
        monkeypatch.setenv("XFAIS_OUTPUT_ROOT", str(root))
        with pytest.raises(ValueError):
            validated_output_path(str(other / "x.dat"))

    def test_no_root_accepts_any_absolute(self, tmp_path, monkeypatch):
        monkeypatch.delenv("XFAIS_OUTPUT_ROOT", raising=False)
        result = validated_output_path(str(tmp_path / "anywhere.dat"))
        assert result.endswith("anywhere.dat")
