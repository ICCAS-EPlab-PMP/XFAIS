#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_remote_data.py — SFTP 远程数据下载服务测试（无网络，假 SFTP）。

覆盖：桌面门禁、connect 入参校验、TOFU 指纹策略、list 排序、download
（递归/同尺寸跳过/取消/单文件失败继续/路径拒绝）、纯路径工具。
全程用 duck-typed 假 SFTP 客户端，不建立任何真实连接。
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import os
import stat as stat_mod
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# Ensure python/ (both package roots) is importable / 保证两个包根可导入
_BETA_ROOT = Path(__file__).resolve().parent.parent.parent
_PY_ROOT = _BETA_ROOT / "python"
for _p in (str(_BETA_ROOT), str(_PY_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from python.services import remote_data as rd  # noqa: E402
from python.services.remote_data import (  # noqa: E402
    _HostKeyMismatchError,
    _PinnedHostKeyPolicy,
    fingerprint_from_key_bytes,
    handle_remote_data,
    remote_rel_segments,
    sanitize_remote_segment,
)

FAKE_KEY_BYTES = b"fake-ssh-host-key-material-for-tests"


# ---------------------------------------------------------------------------
# Helpers / 辅助
# ---------------------------------------------------------------------------

async def _noop_progress(fraction: float, message: str) -> None:
    """Stub progress sink. / 进度回调桩。"""


def _cancel_event() -> asyncio.Event:
    return asyncio.Event()


def _run(payload: dict, cancel: asyncio.Event | None = None) -> dict:
    return asyncio.run(handle_remote_data(payload, _noop_progress, cancel or _cancel_event()))


def _ok(result: dict) -> dict:
    assert isinstance(result, dict), result
    assert result.get("status") == "ok", f"expected ok, got: {result}"
    return result


def _err_result(result: dict) -> dict:
    assert isinstance(result, dict), result
    assert result.get("status") == "error", f"expected error, got: {result}"
    assert "message" in result
    return result


def _dir_mode() -> int:
    return stat_mod.S_IFDIR | 0o755


def _file_mode() -> int:
    return stat_mod.S_IFREG | 0o644


class FakeSFTP:
    """Duck-typed paramiko SFTPClient over an in-memory tree.

    tree: {"/abs/dir": None} 表示目录；{"/abs/file": b"bytes"} 表示文件。
    fail_open: 一组 open() 时抛 IOError 的文件路径（模拟远端读失败）。
    """

    def __init__(self, tree: dict, fail_open: frozenset = frozenset()):
        self.tree = dict(tree)
        self.fail_open = set(fail_open)

    def stat(self, path: str):
        if path in self.tree and self.tree[path] is None:
            return SimpleNamespace(st_mode=_dir_mode(), st_size=0, st_mtime=100)
        data = self.tree.get(path)
        assert data is not None, f"no such remote path: {path}"
        return SimpleNamespace(st_mode=_file_mode(), st_size=len(data), st_mtime=100)

    def listdir_attr(self, path: str):
        assert path in self.tree and self.tree[path] is None, f"not a dir: {path}"
        prefix = path.rstrip("/") + "/"
        entries = []
        for child in sorted(self.tree):
            if child.startswith(prefix) and "/" not in child[len(prefix):]:
                if self.tree[child] is None:
                    entries.append(
                        SimpleNamespace(
                            filename=child[len(prefix):], st_mode=_dir_mode(),
                            st_size=0, st_mtime=100,
                        )
                    )
                else:
                    entries.append(
                        SimpleNamespace(
                            filename=child[len(prefix):], st_mode=_file_mode(),
                            st_size=len(self.tree[child]), st_mtime=100,
                        )
                    )
        return entries

    def open(self, path: str, mode: str = "r"):
        assert mode == "rb"
        if path in self.fail_open:
            raise IOError(f"simulated remote read failure: {path}")
        data = self.tree.get(path)
        assert data is not None, f"no such remote file: {path}"
        return io.BytesIO(data)

    def normalize(self, path: str) -> str:
        return "/home/user"

    def get_channel(self):
        return None

    def close(self):
        pass


class FakeTransport:
    def __init__(self, key_bytes: bytes):
        self._key = SimpleNamespace(asbytes=lambda: key_bytes)

    def get_remote_server_key(self):
        return self._key


class FakeClient:
    def __init__(self, sftp: FakeSFTP, key_bytes: bytes = FAKE_KEY_BYTES):
        self.sftp = sftp
        self.transport = FakeTransport(key_bytes)
        self.closed = False

    def get_transport(self):
        return self.transport

    def open_sftp(self):
        return self.sftp

    def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def _clean_connections():
    yield
    with rd._CONNECTIONS_LOCK:
        rd._CONNECTIONS.clear()


def _connect(monkeypatch, sftp: FakeSFTP, key_bytes: bytes = FAKE_KEY_BYTES) -> dict:
    """connect 动作 + monkeypatch 假连接。返回 _ok(connect 结果)。

    注入点：_connect_ssh（返回 FakeClient）与 _open_sftp（绕开 paramiko
    的 from_transport，直接给 FakeSFTP——生产代码中此处返回只读包装）。
    """
    client = FakeClient(sftp, key_bytes)
    monkeypatch.setattr(rd, "_connect_ssh", lambda *a, **k: client)
    monkeypatch.setattr(rd, "_open_sftp", lambda c: c.open_sftp())
    result = _run({
        "action": "connect",
        "_is_desktop": True,
        "host": "192.168.1.10",
        "port": 22,
        "username": "user",
        "password": "secret",
    })
    return _ok(result), client


BASE_TREE = {
    "/data": None,
    "/data/zed_dir": None,
    "/data/zed_dir/deep.edf": b"D" * 10,
    "/data/aaa.edf": b"A" * 5,
    "/data/mmm.edf": b"MMM",
}


# ---------------------------------------------------------------------------
# Desktop gate / 桌面门禁
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("action", ["connect", "list", "download", "disconnect", "bogus"])
def test_desktop_gate_blocks_all_actions(action):
    result = _run({"action": action})
    _err_result(result)
    assert "桌面" in result["message"] or "desktop" in result["message"].lower()


def test_unknown_action_rejected():
    result = _run({"action": "bogus", "_is_desktop": True})
    _err_result(result)


# ---------------------------------------------------------------------------
# connect 入参校验 / connect validation
# ---------------------------------------------------------------------------

def _connect_payload(**overrides):
    payload = {
        "action": "connect",
        "_is_desktop": True,
        "host": "srv.local",
        "port": 22,
        "username": "user",
        "password": "pw",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "overrides",
    [
        {"host": ""}, {"host": "   "}, {"host": 123},
        {"host": "a b"}, {"host": "x" * 254},
        {"port": 0}, {"port": 70000}, {"port": "abc"},
        {"username": ""}, {"username": "x" * 65},
        {"password": "", "keyPath": ""},
        {"hostFingerprint": "md5:abc"},
    ],
)
def test_connect_rejects_bad_params(overrides):
    _err_result(_run(_connect_payload(**overrides)))


def test_connect_rejects_non_string_password():
    _err_result(_run(_connect_payload(password=123)))


def test_connect_happy_path_first_time_tofu(monkeypatch):
    calls = {}

    def fake_connect(host, port, username, password, key_path, key_passphrase, expected_fp):
        calls.update(host=host, port=port, username=username, password=password,
                     key_path=key_path, key_passphrase=key_passphrase, expected_fp=expected_fp)
        return FakeClient(FakeSFTP(BASE_TREE))

    monkeypatch.setattr(rd, "_connect_ssh", fake_connect)
    monkeypatch.setattr(rd, "_open_sftp", lambda c: c.open_sftp())
    result = _ok(_run(_connect_payload()))
    assert result["connId"]
    assert result["rootPath"] == "/home/user"
    assert result["hostFingerprint"] == fingerprint_from_key_bytes(FAKE_KEY_BYTES)
    assert calls == {
        "host": "srv.local", "port": 22, "username": "user",
        "password": "pw", "key_path": None, "key_passphrase": None, "expected_fp": None,
    }
    # 连接进入缓存 / connection cached
    assert result["connId"] in rd._CONNECTIONS


def test_connect_forwards_pinned_fingerprint_and_key(monkeypatch):
    calls = {}

    def fake_connect(*args):
        calls["args"] = args
        return FakeClient(FakeSFTP(BASE_TREE))

    monkeypatch.setattr(rd, "_connect_ssh", fake_connect)
    monkeypatch.setattr(rd, "_open_sftp", lambda c: c.open_sftp())
    fp = fingerprint_from_key_bytes(FAKE_KEY_BYTES)
    _ok(_run(_connect_payload(
        password="", keyPath="C:/keys/id_ed25519", keyPassphrase="kpw", hostFingerprint=fp,
    )))
    host, port, username, password, key_path, key_passphrase, expected_fp = calls["args"]
    assert (host, port, username) == ("srv.local", 22, "user")
    assert password is None  # 密钥模式不再传密码
    assert key_path == "C:/keys/id_ed25519"
    assert key_passphrase == "kpw"
    assert expected_fp == fp


# ---------------------------------------------------------------------------
# TOFU host-key policy / 主机密钥固定指纹策略
# ---------------------------------------------------------------------------

def test_fingerprint_format_matches_openssh_sha256():
    expected = "SHA256:" + __import__("base64").b64encode(
        hashlib.sha256(FAKE_KEY_BYTES).digest()
    ).decode().rstrip("=")
    assert fingerprint_from_key_bytes(FAKE_KEY_BYTES) == expected


def test_policy_rejects_fingerprint_mismatch():
    policy = _PinnedHostKeyPolicy("SHA256:AAAA")
    client = SimpleNamespace(get_host_keys=lambda: SimpleNamespace(add=lambda *a: None))
    with pytest.raises(_HostKeyMismatchError):
        policy.missing_host_key(client, "h", SimpleNamespace(
            asbytes=lambda: FAKE_KEY_BYTES, get_name=lambda: "ssh-ed25519"))


def test_policy_accepts_match_and_first_use():
    fp = fingerprint_from_key_bytes(FAKE_KEY_BYTES)
    added = []
    client = SimpleNamespace(
        get_host_keys=lambda: SimpleNamespace(add=lambda *a: added.append(a))
    )
    key = SimpleNamespace(asbytes=lambda: FAKE_KEY_BYTES, get_name=lambda: "ssh-ed25519")
    _PinnedHostKeyPolicy(fp).missing_host_key(client, "h", key)
    _PinnedHostKeyPolicy(None).missing_host_key(client, "h", key)
    assert len(added) == 2  # 匹配与首连都接受并记录


def test_mismatch_error_message_is_mitm_specific(monkeypatch):
    def raise_mismatch(*a):
        raise _HostKeyMismatchError("expected SHA256:AAA, got SHA256:BBB")

    monkeypatch.setattr(rd, "_connect_ssh", raise_mismatch)
    result = _err_result(_run(_connect_payload()))
    assert "指纹" in result["message"]


def test_connect_empty_fingerprint_string_means_first_use(monkeypatch):
    """空字符串指纹 = 首次连接（TOFU），不得被当格式错误拒绝（回归：
    前端首连曾传 '' 导致"格式非法"被误报为指纹不匹配）。"""
    calls = {}

    def fake_connect(*args):
        calls["args"] = args
        return FakeClient(FakeSFTP(BASE_TREE))

    monkeypatch.setattr(rd, "_connect_ssh", fake_connect)
    monkeypatch.setattr(rd, "_open_sftp", lambda c: c.open_sftp())
    result = _ok(_run(_connect_payload(hostFingerprint="  ")))
    assert calls["args"][6] is None  # expected_fingerprint 归一化为 None
    assert result["hostFingerprint"] == fingerprint_from_key_bytes(FAKE_KEY_BYTES)


# ---------------------------------------------------------------------------
# list / 目录列表
# ---------------------------------------------------------------------------

def test_list_requires_known_connection():
    _err_result(_run({
        "action": "list", "_is_desktop": True, "connId": "nope", "path": "/data",
    }))


def test_list_dirs_first_sorted(monkeypatch):
    (result, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    listing = _ok(_run({
        "action": "list", "_is_desktop": True,
        "connId": result["connId"], "path": "/data",
    }))
    assert listing["action"] == "list"
    names = [e["name"] for e in listing["entries"]]
    assert names == ["zed_dir", "aaa.edf", "mmm.edf"]  # 目录优先 + 名称排序
    assert listing["entries"][0]["isDir"] is True
    assert listing["entries"][1]["isDir"] is False
    assert listing["entries"][1]["size"] == 5


def test_list_rejects_dotdot_path(monkeypatch):
    (result, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    _err_result(_run({
        "action": "list", "_is_desktop": True,
        "connId": result["connId"], "path": "/data/../etc",
    }))


# ---------------------------------------------------------------------------
# download / 下载
# ---------------------------------------------------------------------------

def _download_payload(conn_id: str, dest: str, paths: list, base: str = "/data",
                      cancel: asyncio.Event | None = None, **overrides):
    payload = {
        "action": "download",
        "_is_desktop": True,
        "connId": conn_id,
        "paths": paths,
        "basePath": base,
        "destDir": dest,
        "skipExisting": True,
    }
    payload.update(overrides)
    return payload


def test_download_recursive_creates_tree_and_recovers_bytes(monkeypatch, tmp_path):
    (conn, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    dest = tmp_path / "download"
    result = _ok(_run(_download_payload(
        conn["connId"], str(dest), ["/data/aaa.edf", "/data/zed_dir"],
    )))
    assert result["fileCount"] == 2
    assert result["skipped"] == 0
    assert len(result["downloaded"]) == 2
    assert (dest / "aaa.edf").read_bytes() == b"A" * 5
    assert (dest / "zed_dir" / "deep.edf").read_bytes() == b"D" * 10
    # 无残留临时文件 / no leftover temp files
    leftovers = [p for p in dest.rglob(".xfais-part-*")]
    assert leftovers == []


def test_download_skip_existing_same_size(monkeypatch, tmp_path):
    (conn, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    dest = tmp_path / "download"
    first = _ok(_run(_download_payload(conn["connId"], str(dest), ["/data/aaa.edf"])))
    assert first["skipped"] == 0
    second = _ok(_run(_download_payload(conn["connId"], str(dest), ["/data/aaa.edf"])))
    assert second["skipped"] == 1
    assert second["downloaded"] == []
    # 尺寸不同则重下 / different size re-downloads
    (dest / "aaa.edf").write_bytes(b"XY")
    third = _ok(_run(_download_payload(conn["connId"], str(dest), ["/data/aaa.edf"])))
    assert third["skipped"] == 0
    assert (dest / "aaa.edf").read_bytes() == b"A" * 5


def test_download_cancel_midway_returns_partial(monkeypatch, tmp_path):
    (conn, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    dest = tmp_path / "download"
    cancel = asyncio.Event()
    cancel.set()  # 立即取消 → cancelled 结果且无文件落地
    result = _run(_download_payload(
        conn["connId"], str(dest), ["/data/aaa.edf", "/data/mmm.edf"],
    ), cancel=cancel)
    assert result["status"] == "cancelled"
    assert result["downloaded"] == []
    assert not (dest / "aaa.edf").exists()


def test_download_cancel_mid_file_cleans_temp(monkeypatch, tmp_path):
    big_tree = {
        "/data": None,
        "/data/big.bin": b"B" * (rd.CHUNK_SIZE * 2 + 100),  # 多块读取
    }
    cancel = asyncio.Event()

    class CancelOnSecondChunk(FakeSFTP):
        """第二块读取后置取消事件（不依赖进度节流时序）。"""

        def open(self, path: str, mode: str = "r"):
            raw = super().open(path, mode)
            state = {"n": 0}
            orig_read = raw.read

            def read(n: int = -1):
                buf = orig_read(n)
                state["n"] += 1
                if state["n"] >= 2 and buf:
                    cancel.set()
                return buf

            raw.read = read
            return raw

    (conn, _client) = _connect(monkeypatch, CancelOnSecondChunk(big_tree))
    dest = tmp_path / "download"
    payload = _download_payload(conn["connId"], str(dest), ["/data/big.bin"])
    result = asyncio.run(handle_remote_data(payload, _noop_progress, cancel))
    assert result["status"] == "cancelled"
    assert result["downloaded"] == []
    assert not (dest / "big.bin").exists()
    assert [p for p in dest.rglob(".xfais-part-*")] == []  # 临时文件已清理


def test_download_single_failure_keeps_going(monkeypatch, tmp_path):
    tree = {
        "/data": None,
        "/data/ok1.edf": b"1",
        "/data/bad.edf": b"22",
        "/data/ok2.edf": b"333",
    }
    sftp = FakeSFTP(tree, fail_open=frozenset({"/data/bad.edf"}))
    (conn, _client) = _connect(monkeypatch, sftp)
    dest = tmp_path / "download"
    result = _ok(_run(_download_payload(
        conn["connId"], str(dest), ["/data/ok1.edf", "/data/bad.edf", "/data/ok2.edf"],
    )))
    assert len(result["downloaded"]) == 2
    assert len(result["failed"]) == 1
    assert "bad.edf" in result["failed"][0]["path"]
    assert (dest / "ok1.edf").read_bytes() == b"1"
    assert (dest / "ok2.edf").read_bytes() == b"333"
    assert not (dest / "bad.edf").exists()


@pytest.mark.parametrize(
    "overrides",
    [
        {"destDir": ""},
        {"destDir": "relative/path"},
        {"paths": []},
        {"paths": "/data/aaa.edf"},
        {"paths": ["/data/../etc/passwd"]},
        {"paths": ["not/absolute"]},
        {"basePath": None},
        {"basePath": "/../x"},
    ],
)
def test_download_rejects_bad_payloads(monkeypatch, tmp_path, overrides):
    (conn, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    payload = _download_payload(conn["connId"], str(tmp_path), ["/data/aaa.edf"])
    payload.update(overrides)
    _err_result(_run(payload))


def test_download_use_temp_dir_branch(monkeypatch):
    """useTempDir：destDir 缺省也成功，落在系统 temp 的 xfais-remote-cache。"""
    import tempfile
    (conn, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    result = _ok(_run({
        "action": "download", "_is_desktop": True,
        "connId": conn["connId"],
        "paths": ["/data/aaa.edf"], "basePath": "/data",
        "useTempDir": True,
    }))
    expected_root = os.path.join(tempfile.gettempdir(), "xfais-remote-cache")
    assert os.path.commonpath([expected_root, result["outputDir"]]) == expected_root
    assert (Path(result["outputDir"]) / "aaa.edf").read_bytes() == b"A" * 5


def test_read_only_sftp_wrapper_blocks_all_mutations():
    """远端强制只读：所有写/删/改名/元数据方法一律 EACCES，open 仅 "rb"。

    结构性保证（而非调用纪律）：即使未来误用 put/remove/rename 等，
    也无法对远端产生任何写入、删除或修改。
    """
    sftp = object.__new__(rd._ReadOnlySFTPClient)
    for method in (
        "put", "putfo", "mkdir", "rmdir", "remove", "rename", "posix_rename",
        "symlink", "setstat", "truncate", "chown", "chmod", "utime",
    ):
        with pytest.raises(IOError):
            getattr(sftp, method)("/remote/x", "/remote/y")
    # open 只允许只读模式 / read-only open modes only
    with pytest.raises(IOError):
        sftp.open("/remote/x", "wb")
    with pytest.raises(IOError):
        sftp.open("/remote/x", "r+")
    with pytest.raises(IOError):
        sftp.open("/remote/x", "a")


def test_download_requires_known_connection(tmp_path):
    _err_result(_run(_download_payload("ghost", str(tmp_path), ["/data/a"])))


def test_download_directory_escapes_base_rejected(monkeypatch, tmp_path):
    (conn, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    # basePath 不含所选路径 → relpath 逃逸 → 报错
    _err_result(_run(_download_payload(
        conn["connId"], str(tmp_path), ["/data/aaa.edf"], base="/other",
    )))


def test_download_directory_dotdot_dest_rejected(monkeypatch, tmp_path):
    (conn, _client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    bad_dest = str(tmp_path / "x" / ".." / "y")
    _err_result(_run(_download_payload(conn["connId"], bad_dest, ["/data/aaa.edf"])))


# ---------------------------------------------------------------------------
# disconnect / 断开
# ---------------------------------------------------------------------------

def test_disconnect_is_idempotent(monkeypatch):
    (conn, client) = _connect(monkeypatch, FakeSFTP(BASE_TREE))
    _ok(_run({"action": "disconnect", "_is_desktop": True, "connId": conn["connId"]}))
    assert client.closed is True
    assert conn["connId"] not in rd._CONNECTIONS
    # 幂等 / idempotent
    _ok(_run({"action": "disconnect", "_is_desktop": True, "connId": conn["connId"]}))


# ---------------------------------------------------------------------------
# Pure helpers / 纯路径工具
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    ["", ".", "..", "a/b", "a\\b", "a:b", " spaced ", "CON", "PRN.aux", "x" * 201],
)
def test_sanitize_remote_segment_rejects(bad):
    with pytest.raises(ValueError):
        sanitize_remote_segment(bad)


@pytest.mark.parametrize("good", ["a.edf", "数据_文件.h5", "a.b.c", "x" * 200])
def test_sanitize_remote_segment_accepts(good):
    assert sanitize_remote_segment(good) == good


def test_remote_rel_segments_escapes_rejected():
    with pytest.raises(ValueError):
        remote_rel_segments("/data", "/etc/passwd")
    with pytest.raises(ValueError):
        remote_rel_segments("/data", "/data")


def test_remote_rel_segments_ok():
    assert remote_rel_segments("/data", "/data/sub/f.edf") == ("sub", "f.edf")
    assert remote_rel_segments("/data", "/data/f.edf") == ("f.edf",)


def test_local_target_stays_inside_dest(monkeypatch, tmp_path):
    """下载树不能逃出目标目录（纵深防御：commonpath 圈定）。"""
    tree = {"/data": None, "/data/inside.edf": b"INSIDE"}
    (conn, _client) = _connect(monkeypatch, FakeSFTP(tree))
    dest = tmp_path / "dest"
    result = _ok(_run(_download_payload(conn["connId"], str(dest), ["/data/inside.edf"])))
    assert (dest / "inside.edf").read_bytes() == b"INSIDE"
    produced = set(result["downloaded"])
    assert all(os.path.commonpath([str(dest), p]) == str(dest) for p in produced)


# ---------------------------------------------------------------------------
# 缓存池（无损压缩暂存）/ compressed download cache pool (v0.5.0)
# ---------------------------------------------------------------------------

POOL_TREE = {
    "/data": None,
    "/data/run1": None,
    "/data/run1/scan.tif": b"RAW-TIFF" * 8,
    "/data/run1/notes.dat": b"plain-notes",
}


def _pool_download(monkeypatch, sftp, cache_dir, *, paths, base="/data/run1",
                   cache_compress=True, server_key="srv-1", **overrides):
    (conn, _client) = _connect(monkeypatch, sftp)
    return _run(_download_payload(
        conn["connId"], "", paths, base=base,
        cachePool=True, cacheDir=str(cache_dir),
        cacheCompress=cache_compress, cacheTtlMinutes=60,
        serverKey=server_key, **overrides,
    ))


def _patch_pool_compressor(monkeypatch, fake):
    import python.services.compressor as py_comp
    import services.compressor as svc_comp
    monkeypatch.setattr(py_comp, "compress_files_for_staging", fake)
    if svc_comp is not py_comp:
        monkeypatch.setattr(svc_comp, "compress_files_for_staging", fake)


def test_cache_pool_download_compresses_in_place(monkeypatch, tmp_path):
    """池模式下载 → 可压缩文件就地无损替换、不可压缩保持原样；
    结果路径全部落在池内（<cacheDir>/<serverKey>/<相对路径>）。"""
    sftp = FakeSFTP(POOL_TREE)
    cache_dir = tmp_path / "pool"
    calls: list = []

    async def fake_staging(files, out_dir, send_progress, cancel_event):
        calls.append([os.path.basename(f) for f in files])
        produced = Path(out_dir) / Path(files[0]).name
        produced.parent.mkdir(parents=True, exist_ok=True)
        produced.write_bytes(b"COMPRESSED")
        return {"status": "ok", "files": [{"status": "ok", "outputPath": str(produced)}]}

    _patch_pool_compressor(monkeypatch, fake_staging)
    result = _ok(_pool_download(
        monkeypatch, sftp, cache_dir,
        paths=["/data/run1/scan.tif", "/data/run1/notes.dat"],
    ))
    assert result["cachePool"] is True
    assert result["compressedCount"] == 1
    assert calls == [["scan.tif"]]
    # v2 布局：<cacheDir>/<serverKey>/<操作时间戳>/<远端绝对路径 rel>
    tifs = list(cache_dir.glob("srv-1/*/data/run1/scan.tif"))
    dats = list(cache_dir.glob("srv-1/*/data/run1/notes.dat"))
    assert len(tifs) == 1 and len(dats) == 1
    assert tifs[0].read_bytes() == b"COMPRESSED"   # raw 被压缩副本原子替换
    assert dats[0].read_bytes() == b"plain-notes"  # 非 TIFF/HDF5 保持原样
    for p in result["downloaded"]:
        assert os.path.commonpath([str(cache_dir), p]) == str(cache_dir)
    # 操作时间分文件夹：两个文件在同一 op 目录下
    assert tifs[0].parent == dats[0].parent


def test_cache_pool_hit_skips_transfer(monkeypatch, tmp_path):
    """池内已有同远端文件的副本（任何历史操作文件夹、可能是压缩副本、
    尺寸与远端不等）→ 跳过传输直接取用；对远端零读取。"""
    sftp = FakeSFTP(POOL_TREE)
    cache_dir = tmp_path / "pool"
    # v2 布局命中：<serverKey>/<任意历史 op>/<远端绝对路径 rel>
    pre = cache_dir / "srv-1" / "20260101-000000" / "data" / "run1"
    pre.mkdir(parents=True)
    (pre / "scan.tif").write_bytes(b"CACHED-COPY")

    remote_reads: list = []
    real_open = sftp.open

    def counting_open(path, mode="r"):
        remote_reads.append(path)
        return real_open(path, mode)

    monkeypatch.setattr(sftp, "open", counting_open)
    result = _ok(_pool_download(
        monkeypatch, sftp, cache_dir,
        paths=["/data/run1/scan.tif"], cache_compress=False,
    ))
    assert result["skipped"] == 1
    assert remote_reads == []  # 池命中 → 对服务器零读取（只读属性下尤其重要）
    assert Path(result["downloaded"][0]).read_bytes() == b"CACHED-COPY"


def test_cache_pool_dedupes_across_modules(monkeypatch, tmp_path):
    """同一远端文件经不同模块（不同 basePath）先后下载 → 第二次命中缓存：
    对远端零读取、池内仍只有一份、无重复缓存。"""
    sftp = FakeSFTP(POOL_TREE)
    cache_dir = tmp_path / "pool"

    first = _ok(_pool_download(
        monkeypatch, sftp, cache_dir,
        paths=["/data/run1/scan.tif"], base="/data/run1", cache_compress=False,
    ))
    assert first["skipped"] == 0
    copies = list(cache_dir.glob("srv-1/*/data/run1/scan.tif"))
    assert len(copies) == 1

    # 换一个模块：basePath 变为 /data（rel 变为 run1/scan.tif 的 base 相对形），
    # 但池模式按远端绝对路径存取 → 同一文件 → 命中
    remote_reads: list = []
    real_open = sftp.open

    def counting_open(path, mode="r"):
        remote_reads.append(path)
        return real_open(path, mode)

    monkeypatch.setattr(sftp, "open", counting_open)
    second = _ok(_pool_download(
        monkeypatch, sftp, cache_dir,
        paths=["/data/run1/scan.tif"], base="/data", cache_compress=False,
    ))
    assert second["skipped"] == 1
    assert remote_reads == []
    assert len(list(cache_dir.glob("srv-1/*/data/run1/scan.tif"))) == 1  # 不重复
    assert Path(second["downloaded"][0]).read_bytes() == b"RAW-TIFF" * 8


def test_cache_pool_list_prunes_expired(monkeypatch, tmp_path):
    """cache_pool_list：先做 TTL 惰性回收（过期文件删除、空目录清理），
    再列出剩余条目（含 serverKey 与池内绝对路径）。"""
    import time as _time
    pool = tmp_path / "pool"
    (pool / "srv-1").mkdir(parents=True)
    fresh = pool / "srv-1" / "fresh.tif"
    fresh.write_bytes(b"new")
    stale = pool / "srv-1" / "stale.dat"
    stale.write_bytes(b"old")
    old = _time.time() - 10 * 24 * 3600
    os.utime(stale, (old, old))

    result = _ok(_run({
        "action": "cache_pool_list",
        "_is_desktop": True,
        "cacheDir": str(pool),
        "cacheTtlMinutes": 1440,
    }))
    assert result["pruned"] == 1
    assert [e["name"] for e in result["entries"]] == ["fresh.tif"]
    assert not stale.exists()
    entry = result["entries"][0]
    assert entry["serverKey"] == "srv-1"
    assert entry["path"] == os.path.realpath(str(fresh))


def test_cache_pool_export_requires_pool_containment(tmp_path):
    """cache_pool_export：池外路径一律拒绝；池内文件正常复制到目标目录。"""
    pool = tmp_path / "pool"
    (pool / "srv-1").mkdir(parents=True)
    inside = pool / "srv-1" / "a.tif"
    inside.write_bytes(b"AAA")
    outside = tmp_path / "outside.tif"
    outside.write_bytes(b"OOO")
    dest = tmp_path / "out"
    dest.mkdir()

    ok = _run({
        "action": "cache_pool_export",
        "_is_desktop": True,
        "cacheDir": str(pool),
        "paths": [str(inside)],
        "destDir": str(dest),
    })
    assert ok["status"] == "ok"
    assert len(ok["exported"]) == 1
    assert Path(ok["exported"][0]["path"]).read_bytes() == b"AAA"

    bad = _run({
        "action": "cache_pool_export",
        "_is_desktop": True,
        "cacheDir": str(pool),
        "paths": [str(outside)],
        "destDir": str(dest),
    })
    _err_result(bad)
    assert "缓存池之外" in bad["message"] or "escapes the cache pool" in bad["message"]


def test_cache_pool_actions_require_desktop():
    """缓存池动作同样在桌面门禁之内（web 一律拒绝）。"""
    for action in ("cache_pool_list", "cache_pool_export"):
        result = _run({"action": action})
        _err_result(result)
        assert "桌面" in result["message"] or "desktop" in result["message"].lower()
