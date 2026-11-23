#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remote_data.py — SFTP 远程数据下载服务（桌面版专用）

让 X-FAIS 桌面版作为 SFTP 客户端连接用户自己的数据服务器，浏览目录并把
原始数据文件下载到本地目录（下载完成后即普通本地文件，直接进入既有
导入/批处理流程）。典型场景：数据存放在一台无法运行 Electron/Python 3
的老服务器上，本机经内网拉取。

动作 / Actions
  1. ``connect``    — 建立连接（密码或私钥认证），返回 connId 与主机指纹
  2. ``list``       — 列出远端目录（目录优先排序）
  3. ``download``   — 下载选中的文件/目录（递归、同尺寸跳过、可取消、
                      字节级进度、临时文件 fd 写入 + 原子改名）
  4. ``disconnect`` — 显式关闭连接（幂等）

安全模型 / Security model
  - 这是后端**第一个出站连接**能力，特权完全依赖 ``_is_desktop`` 标志：
    该标志仅由 Electron 主进程在回环 WS 上注入（web 浏览器无法伪造，
    与 scan_folder 的桌面特权同一先例）。非桌面载荷一律拒绝。
  - **远端强制只读**（_ReadOnlySFTPClient）：对远端只允许 stat/
    listdir/open("rb")/normalize 纯读取；写入、上传、删除、改名、
    修改元数据等全部在 SFTP 通道层硬拒（EACCES）。数据处理一律先
    下载到本地（mkstemp 临时文件 → 原子改名）后进行，绝不在远端
    原地处理。
  - 目标主机由本机用户在界面显式输入（内网数据服务器是本功能的用途，
    不做网段限制）；本服务不做 http/https URL 抓取，协议固定为 SSH/SFTP。
  - 主机密钥采用**固定指纹策略**（TOFU）：载荷可带 ``hostFingerprint``
    （前端记忆档案）。带有期望指纹时，握手层发现不匹配直接拒绝连接
    （认证前失败，防中间人）；首次连接（无期望指纹）接受并在响应中
    回传实际指纹，由前端存档供后续校验。
  - 凭据（密码/口令）只在连接建立时使用，绝不写入任何响应、日志或
    结果文件；连接缓存只保留 SSH 客户端对象。
  - 路径收口（**所有文件系统/远端操作集中在动作的 ``work()`` 闭包内
    就地完成**，不用跨函数传递载荷派生路径）：
    * 远端路径就地「PurePosixPath 拒 ``..`` 段 → posixpath.normpath →
      必须绝对路径」三连（防御恶意服务器返回构造文件名）；
    * 本地目标目录先经 ``validated_output_path_optional`` 策略门（保留
      ``XFAIS_OUTPUT_ROOT`` 圈定，门的结果不入数据流），随后就地
      「拒 ``..`` 段 → realpath(abspath())」归一化；
    * 每个文件目标以「段净化 → 拒 ``..`` → normpath 拼接 → commonpath
      圈定在目标根内」构造；写入经 ``tempfile.mkstemp``（fd 写入，不
      以路径开写文件句柄）+ ``os.replace`` 原子落位，临时路径由系统
      生成、失败/取消即删。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import posixpath
import re
import shutil
import socket
import stat as stat_mod
import tempfile
import threading
import time
import uuid
from pathlib import PurePosixPath
from typing import Any, Awaitable, Callable, Dict, List, Sequence, Tuple

import paramiko

from services.paths import validated_output_path_optional

__all__ = ["handle_remote_data"]


# ---------------------------------------------------------------------------
# Constants / 常量
# ---------------------------------------------------------------------------

#: 下载块大小（256 KB）/ transfer chunk size
CHUNK_SIZE = 256 * 1024

#: 连接/认证超时（秒）/ connect + auth timeout
CONNECT_TIMEOUT_S = 10

#: 单次 read 超时（秒），防止僵死服务器挂住任务 / per-read timeout
IO_TIMEOUT_S = 30

#: 空闲连接回收阈值（秒）/ idle TTL of cached connections
IDLE_TTL_S = 30 * 60

#: 连接缓存上限（超过时逐出最旧空闲连接）/ max cached connections
MAX_CONNECTIONS = 4

#: 单次下载 walk 收集的文件数上限 / max files per download task
MAX_FILES_PER_TASK = 20_000

#: 目录列表返回上限（超出置 truncated）/ max entries per listing
MAX_LIST_ENTRIES = 5_000

#: 远端路径最大递归深度 / max recursion depth when walking remote dirs
MAX_WALK_DEPTH = 32


def _err(message_en: str, message_zh: str = "") -> Dict[str, str]:
    """Build a bilingual error payload. / 构造双语错误返回。"""
    msg = f"{message_en}" + (f" / {message_zh}" if message_zh else "")
    return {"status": "error", "message": msg}


# ---------------------------------------------------------------------------
# Pure path helpers — unit-testable without any network
# 纯路径工具 — 无网络可单测
# ---------------------------------------------------------------------------

#: Windows 保留设备名（不含上标变体，经典集合已足够防御）
_WINDOWS_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_remote_segment(name: Any) -> str:
    """Validate one remote filename segment as a safe local name component.

    检验远端文件名单段，作为本地路径组成部分必须安全：拒绝空段、
    ``.``/``..``、分隔符、NUL、冒号（Windows 盘符/ADS）、首尾空白、
    结尾句点、Windows 保留设备名与超长名。
    """
    if not isinstance(name, str) or not name:
        raise ValueError("invalid remote name: empty segment / 远端文件名为空")
    if "\x00" in name:
        raise ValueError("invalid remote name: NUL byte / 远端文件名含 NUL")
    if name in {".", ".."}:
        raise ValueError(f"invalid remote name: dot segment / 远端文件名为保留段：{name!r}")
    if "/" in name or "\\" in name or ":" in name:
        raise ValueError(
            f"invalid remote name: separator in segment / 远端文件名含路径分隔符：{name!r}"
        )
    if name != name.strip():
        raise ValueError(
            f"invalid remote name: leading/trailing whitespace / 远端文件名首尾含空白：{name!r}"
        )
    if name.endswith("."):
        raise ValueError(f"invalid remote name: trailing dot / 远端文件名以句点结尾：{name!r}")
    if name.split(".")[0].upper() in _WINDOWS_RESERVED:
        raise ValueError(
            f"invalid remote name: Windows reserved / 远端文件名为 Windows 保留名：{name!r}"
        )
    if len(name) > 200:
        raise ValueError(f"invalid remote name: too long / 远端文件名过长：{name[:32]!r}…")
    return name


def _require_abs_remote(path: Any, field: str = "remote path") -> str:
    """Validate + normalize an absolute POSIX remote path (precheck helper).

    远端路径入参预检（拒 ``..`` 段、反斜杠、NUL、非绝对路径）。仅用于
    动作入口的双语报错；真正触达远端操作的位置仍在 ``work()`` 闭包内
    就地重做「PurePosixPath 拒 ``..`` → normpath → 绝对路径」三连。
    """
    if not isinstance(path, str) or not path.strip():
        raise ValueError(f"missing {field} / 缺少 {field}")
    if "\x00" in path or "\\" in path:
        raise ValueError(f"invalid {field}: {path!r} / {field} 非法")
    if ".." in PurePosixPath(path).parts:
        raise ValueError(
            f"invalid {field}: '..' segments are not allowed / {field} 含 .. 段，已拒绝"
        )
    norm = posixpath.normpath(path)
    if not norm.startswith("/"):
        raise ValueError(f"{field} must be absolute: {path!r} / {field} 必须是绝对路径")
    return norm


def remote_rel_segments(base_path: str, remote_path: str) -> Tuple[str, ...]:
    """Relative segments of ``remote_path`` under ``base_path``.

    计算远端路径相对浏览基准目录的段序列；逃出基准目录（``..``）视为
    非法——下载只保留所选子树结构。
    """
    base = posixpath.normpath(base_path)
    rel = posixpath.relpath(posixpath.normpath(remote_path), base)
    if rel == "." or rel.startswith(".."):
        raise ValueError(
            f"remote path escapes base directory / 远端路径不在基准目录内：{remote_path}"
        )
    return tuple(rel.split("/"))


def fingerprint_from_key_bytes(key_bytes: bytes) -> str:
    """OpenSSH-style SHA256 fingerprint of a host key. / 主机密钥指纹。"""
    digest = hashlib.sha256(key_bytes).digest()
    return "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("=")


# ---------------------------------------------------------------------------
# Host-key policy — pinned fingerprint (TOFU), never blindly accept
# 主机密钥策略 — 固定指纹（TOFU），绝不盲目接受未知密钥
# ---------------------------------------------------------------------------


class _HostKeyMismatchError(paramiko.SSHException):
    """Raised when the server key differs from the pinned fingerprint.

    服务器密钥与固定指纹不一致——疑似中间人/服务器换密钥，握手层拒绝。
    """


class _PinnedHostKeyPolicy(paramiko.MissingHostKeyPolicy):
    """TOFU policy: enforce a pinned fingerprint when one is known.

    期望指纹已知时：不匹配 → 认证前拒绝连接（防中间人）；匹配 → 接受。
    期望指纹未知（首次连接）→ 接受并记录指纹（响应中回传，由前端存档）。
    替代 paramiko 默认 RejectPolicy / AutoAddPolicy 的两个极端。
    """

    def __init__(self, expected_fingerprint: str | None) -> None:
        self.expected_fingerprint = expected_fingerprint
        self.seen_fingerprint: str | None = None

    def missing_host_key(self, client, hostname, key) -> None:  # noqa: ANN001
        fingerprint = fingerprint_from_key_bytes(key.asbytes())
        self.seen_fingerprint = fingerprint
        if self.expected_fingerprint and fingerprint != self.expected_fingerprint:
            raise _HostKeyMismatchError(
                f"Host key fingerprint mismatch: expected {self.expected_fingerprint}, "
                f"got {fingerprint}"
            )
        client.get_host_keys().add(hostname, key.get_name(), key)


# ---------------------------------------------------------------------------
# Connection cache / 连接缓存
# ---------------------------------------------------------------------------

_CONNECTIONS: Dict[str, Dict[str, Any]] = {}
_CONNECTIONS_LOCK = threading.Lock()


def _close_quietly(entry: Dict[str, Any]) -> None:
    for key in ("sftp", "client"):
        obj = entry.get(key)
        if obj is None:
            continue
        try:
            obj.close()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass


def _prune_connections(now: float) -> None:
    """Drop idle connections (caller holds the lock). / 回收空闲连接。"""
    expired = [cid for cid, e in _CONNECTIONS.items() if now - e["last_used"] > IDLE_TTL_S]
    for cid in expired:
        _close_quietly(_CONNECTIONS.pop(cid))


def _get_connection(conn_id: Any) -> Dict[str, Any] | None:
    if not isinstance(conn_id, str) or not conn_id:
        return None
    with _CONNECTIONS_LOCK:
        entry = _CONNECTIONS.get(conn_id)
        if entry is not None:
            entry["last_used"] = time.monotonic()
        return entry


def _store_connection(client: Any, sftp: Any, host: str) -> str:
    now = time.monotonic()
    with _CONNECTIONS_LOCK:
        _prune_connections(now)
        # 超上限时逐出最旧空闲连接 / evict oldest when above the cap
        while len(_CONNECTIONS) >= MAX_CONNECTIONS:
            oldest = min(_CONNECTIONS.items(), key=lambda kv: kv[1]["last_used"])[0]
            _close_quietly(_CONNECTIONS.pop(oldest))
        conn_id = uuid.uuid4().hex
        _CONNECTIONS[conn_id] = {
            "client": client,
            "sftp": sftp,
            "host": host,
            "last_used": now,
        }
        return conn_id


def drop_connection(conn_id: str) -> None:
    """Close + forget a cached connection. / 关闭并移除缓存连接。"""
    with _CONNECTIONS_LOCK:
        entry = _CONNECTIONS.pop(conn_id, None)
    if entry is not None:
        _close_quietly(entry)


# ---------------------------------------------------------------------------
# Blocking connect worker / 阻塞式连接工作函数
# ---------------------------------------------------------------------------

def _connect_ssh(
    host: str,
    port: int,
    username: str,
    password: str | None,
    key_path: str | None,
    key_passphrase: str | None,
    expected_fingerprint: str | None,
) -> Any:
    """Open an SSHClient with the pinned-fingerprint policy.

    建立连接（测试可 monkeypatch 本函数）；主机密钥由 _PinnedHostKeyPolicy
    在握手层校验（见安全模型），绝不盲目接受未知密钥。
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(_PinnedHostKeyPolicy(expected_fingerprint))
    kwargs: Dict[str, Any] = {
        "hostname": host,
        "port": port,
        "username": username,
        "timeout": CONNECT_TIMEOUT_S,
        "banner_timeout": CONNECT_TIMEOUT_S,
        "auth_timeout": CONNECT_TIMEOUT_S,
        "allow_agent": False,
        "look_for_keys": False,
    }
    if key_path:
        kwargs["key_filename"] = key_path
        if key_passphrase:
            kwargs["passphrase"] = key_passphrase
    else:
        kwargs["password"] = password
    client.connect(**kwargs)
    return client


def _server_fingerprint(client: Any) -> str:
    key = client.get_transport().get_remote_server_key()
    return fingerprint_from_key_bytes(key.asbytes())


class _ReadOnlySFTPClient(paramiko.SFTPClient):
    """Hard read-only view of the remote filesystem.

    远端强制只读（结构性保证，而非仅靠调用纪律）：本服务对远端服务器
    的文件**只允许读取**——不得写入、上传、复制到远端、粘贴、删除、
    改名或修改元数据；数据处理一律先把字节下载到本地（mkstemp →
    本地路径）后进行。所有修改类 SFTP 操作在此被硬拒（EACCES），
    ``open`` 仅接受只读模式（"r"/"rb"），即使未来有人误用
    ``put``/``remove`` 等也不会对远端产生任何影响。
    """

    _READ_ONLY_ERR = "remote filesystem is read-only / 远端为只读：禁止写入、删除、改名或修改"

    def open(self, filename, mode="r", bufsize=-1):  # noqa: A003
        if set(mode) - set("rb"):
            raise IOError(13, self._READ_ONLY_ERR)  # EACCES
        return super().open(filename, mode, bufsize)

    def put(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def putfo(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def mkdir(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def rmdir(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def remove(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def rename(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def posix_rename(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def symlink(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def setstat(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def truncate(self, path, size):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def chown(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def chmod(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)

    def utime(self, *args, **kwargs):  # noqa: A002
        raise IOError(13, self._READ_ONLY_ERR)


def _open_sftp(client: Any) -> Any:
    """Open a hard read-only SFTP channel (see _ReadOnlySFTPClient).

    打开强制只读的 SFTP 通道——本服务对远端的一切访问都经此包装。
    """
    sftp = _ReadOnlySFTPClient.from_transport(client.get_transport())
    channel = sftp.get_channel()
    if channel is not None:
        channel.settimeout(IO_TIMEOUT_S)
    return sftp


class _TransferCancelled(Exception):
    """Raised inside the transfer loop on user cancel. / 用户取消时中断传输。"""


class _ProgressBridge:
    """Thread-safe, throttled progress forwarder (~10 Hz).

    把工作线程里的进度经 run_coroutine_threadsafe 转发回 asyncio 循环，
    0.1s 节流；fraction 夹到 [0,1]。
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        send_progress: Callable[[float, str], Awaitable[None]],
    ) -> None:
        self._loop = loop
        self._send = send_progress
        self._last = 0.0

    def report(self, fraction: float, message: str) -> None:
        now = time.monotonic()
        if now - self._last < 0.1 and fraction < 1.0:
            return
        self._last = now
        clamped = max(0.0, min(1.0, fraction))
        asyncio.run_coroutine_threadsafe(self._send(clamped, message), self._loop)


def _human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} B" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


# ---------------------------------------------------------------------------
# Actions / 动作处理
# ---------------------------------------------------------------------------

def _validate_host_port(payload: Dict[str, Any]) -> Tuple[str, int]:
    host = payload.get("host")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host is required / 请填写主机地址")
    host = host.strip()
    if len(host) > 253 or any(ch.isspace() for ch in host) or "\x00" in host:
        raise ValueError(f"invalid host: {host!r} / 主机地址非法")
    port_raw = payload.get("port", 22)
    try:
        port = int(port_raw)
    except (TypeError, ValueError):
        raise ValueError(f"invalid port: {port_raw!r} / 端口非法") from None
    if not 1 <= port <= 65535:
        raise ValueError(f"invalid port: {port} / 端口须在 1-65535")
    return host, port


async def _action_connect(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        host, port = _validate_host_port(payload)
        username = payload.get("username")
        if not isinstance(username, str) or not username.strip() or len(username) > 64:
            raise ValueError("username is required / 请填写用户名")
        username = username.strip()
        password = payload.get("password")
        key_path = payload.get("keyPath")
        key_passphrase = payload.get("keyPassphrase")
        expected_fp = payload.get("hostFingerprint")
        if isinstance(expected_fp, str) and not expected_fp.strip():
            # 空字符串视为未提供（首次连接）/ empty string means "not pinned"
            expected_fp = None
        if key_path is not None and not isinstance(key_path, str):
            raise ValueError("invalid keyPath / 私钥路径非法")
        if password is not None and not isinstance(password, str):
            raise ValueError("invalid password / 密码非法")
        if expected_fp is not None and (
            not isinstance(expected_fp, str) or not expected_fp.startswith("SHA256:")
        ):
            raise ValueError("invalid hostFingerprint / 主机指纹格式非法")
        has_key = isinstance(key_path, str) and key_path.strip()
        if not has_key and not (isinstance(password, str) and password):
            raise ValueError("password or key file required / 请填写密码或选择私钥文件")
    except ValueError as exc:
        return _err(str(exc))

    def work() -> Dict[str, Any]:
        try:
            client = _connect_ssh(
                host,
                port,
                username,
                password if not has_key else None,
                key_path.strip() if has_key else None,
                key_passphrase if isinstance(key_passphrase, str) and key_passphrase else None,
                expected_fp if isinstance(expected_fp, str) else None,
            )
        except Exception as exc:  # noqa: BLE001 — classified below
            return _classify_connect_error(exc)
        try:
            fingerprint = _server_fingerprint(client)
            sftp = _open_sftp(client)
        except Exception as exc:  # noqa: BLE001
            try:
                client.close()
            except Exception:  # noqa: BLE001
                pass
            return _classify_connect_error(exc)
        conn_id = _store_connection(client, sftp, host)
        try:
            root_path = sftp.normalize(".")
        except Exception:  # noqa: BLE001 — best effort
            root_path = "/"
        return {
            "status": "ok",
            "action": "connect",
            "connId": conn_id,
            "host": host,
            "hostFingerprint": fingerprint,
            "rootPath": root_path,
        }

    return await asyncio.to_thread(work)


def _classify_connect_error(exc: Exception) -> Dict[str, str]:
    if isinstance(exc, _HostKeyMismatchError):
        return _err(
            f"{exc} — possible MITM, connection refused",
            f"主机指纹不匹配，疑似中间人攻击，已拒绝连接（{exc}）。"
            f"若服务器确已更换密钥，请在记忆档案中清除指纹后重连",
        )
    if isinstance(exc, paramiko.AuthenticationException):
        return _err(
            f"Authentication failed: {exc}",
            f"认证失败：{exc}（请检查用户名/密码或私钥口令）",
        )
    if isinstance(exc, paramiko.SSHException):
        return _err(
            f"SSH error: {exc}",
            f"SSH 错误：{exc}（请确认主机与端口提供的是 SSH/SFTP 服务）",
        )
    if isinstance(exc, (OSError, EOFError, socket.gaierror, socket.timeout)):
        return _err(
            f"Cannot reach host: {exc}",
            f"无法连接主机：{exc}（请检查地址/端口与防火墙）",
        )
    return _err(f"Connect failed: {exc}", f"连接失败：{exc}")


async def _action_list(payload: Dict[str, Any]) -> Dict[str, Any]:
    conn_id = payload.get("connId")
    entry = _get_connection(conn_id)
    if entry is None:
        return _err(
            "Connection not found or expired, please reconnect",
            "连接不存在或已超时，请重新连接",
        )
    path_raw = payload.get("path") or entry.get("rootPath") or "/"

    def work() -> Dict[str, Any]:
        # 远端目录就地收口：PurePosixPath 拒 .. → normpath → 绝对路径
        try:
            if not isinstance(path_raw, str) or not path_raw.strip():
                raise ValueError("missing path / 缺少 path")
            if "\x00" in path_raw or "\\" in path_raw:
                raise ValueError("invalid path / path 非法")
            if ".." in PurePosixPath(path_raw).parts:
                raise ValueError("path contains '..' / path 含 .. 段，已拒绝")
            path = posixpath.normpath(path_raw)
            if not path.startswith("/"):
                raise ValueError("path must be absolute / path 必须是绝对路径")
            attrs = entry["sftp"].listdir_attr(path)
        except ValueError as exc:
            return _err(str(exc))
        except Exception as exc:  # noqa: BLE001
            return _classify_io_error(exc)
        decorated = []
        for a in attrs:
            is_dir = bool(a.st_mode is not None and stat_mod.S_ISDIR(a.st_mode))
            decorated.append((0 if is_dir else 1, (a.filename or "").lower(), a.filename, is_dir, a))
        decorated.sort(key=lambda item: (item[0], item[1]))
        entries: List[Dict[str, Any]] = []
        truncated = False
        for _, _, name, is_dir, a in decorated:
            if len(entries) >= MAX_LIST_ENTRIES:
                truncated = True
                break
            if name in {"."}:
                continue
            entries.append(
                {
                    "name": name,
                    "isDir": is_dir,
                    "size": int(getattr(a, "st_size", 0) or 0),
                    "mtime": int(getattr(a, "st_mtime", 0) or 0),
                }
            )
        return {
            "status": "ok",
            "action": "list",
            "path": path,
            "entries": entries,
            "truncated": truncated,
        }

    return await asyncio.to_thread(work)


def _classify_io_error(exc: Exception) -> Dict[str, str]:
    if isinstance(exc, FileNotFoundError):
        return _err("Remote path not found", "远端路径不存在")
    if isinstance(exc, PermissionError):
        return _err("Permission denied on remote path", "远端路径无权限")
    if isinstance(exc, (paramiko.SSHException, ConnectionError, OSError, EOFError)):
        # 通道已死（服务器断开/超时）——提示重连而不是笼统失败
        return _err(
            f"SFTP connection lost: {exc}",
            f"SFTP 连接已断开：{exc}，请重新连接",
        )
    return _err(f"Remote operation failed: {exc}", f"远端操作失败：{exc}")


def _cancelled_result(
    downloaded: List[str],
    skipped: int,
    failed: List[Dict[str, str]],
    dest_dir: str,
    total: int,
    total_bytes: int,
) -> Dict[str, Any]:
    return {
        "status": "cancelled",
        "action": "download",
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "fileCount": total,
        "totalBytes": total_bytes,
        "outputDir": dest_dir,
        "message": (
            f"Download cancelled: {len(downloaded)} files completed / "
            f"下载已取消：已完成 {len(downloaded)} 个文件"
        ),
    }


# ---------------------------------------------------------------------------
# Compressed download cache pool / 下载无损压缩缓存池（v0.5.0）
# ---------------------------------------------------------------------------

#: 默认缓存池根目录（系统临时目录下）/ default pool root (under system temp)
CACHE_POOL_DEFAULT_DIRNAME = "xfais-cache-pool"
#: 无损压缩引擎支持的扩展名 / extensions the lossless engine supports
_CACHE_COMPRESSIBLE_EXTS = (".tif", ".tiff", ".h5", ".hdf5")
#: 缓存保留时长钳制（分钟）：1 分钟 ～ 30 天 / TTL clamp: 1 min .. 30 days
_CACHE_TTL_MIN, _CACHE_TTL_MAX = 1, 30 * 24 * 60


def _cache_pool_root(payload: Dict[str, Any]) -> str:
    """缓存池根目录：载荷 ``cacheDir`` 优先（就地拒 ``..`` 后 realpath 归一），
    否则默认系统临时目录下 ``xfais-cache-pool``。只归一化，不建目录。
    Cache pool root from the payload or the default; normalization only."""
    raw = payload.get("cacheDir")
    if isinstance(raw, str) and raw.strip():
        if "\x00" in raw or ".." in PurePosixPath(raw.replace("\\", "/")).parts:
            raise ValueError("invalid cache dir / 缓存目录非法（含 .. 或非法字符）")
        return os.path.realpath(os.path.abspath(os.path.expanduser(raw)))
    return os.path.realpath(
        os.path.join(tempfile.gettempdir(), CACHE_POOL_DEFAULT_DIRNAME)
    )


def _cache_ttl_minutes(payload: Dict[str, Any]) -> float:
    raw = payload.get("cacheTtlMinutes")
    try:
        value = float(raw) if raw is not None else 1440.0
    except (TypeError, ValueError):
        value = 1440.0
    return min(_CACHE_TTL_MAX, max(_CACHE_TTL_MIN, value))


def _sanitize_server_key(raw: Any) -> str:
    """服务器标识白名单（``[A-Za-z0-9-]``，与 sftpSecret 键同规）；
    不合规一律回落 ``default``。Server-key allowlist with a safe fallback."""
    if isinstance(raw, str) and re.fullmatch(r"[A-Za-z0-9-]{1,64}", raw):
        return raw
    return "default"


def _prune_cache_pool(pool_root: str, ttl_minutes: float) -> int:
    """惰性回收：删除 mtime 超过 TTL 的缓存文件并自底向上清空空目录
    （根目录不删）。返回删除的文件数。Lazy TTL reclamation of the pool."""
    if ttl_minutes <= 0 or not os.path.isdir(pool_root):
        return 0
    cutoff = time.time() - ttl_minutes * 60.0
    removed = 0
    for dirpath, _dirnames, filenames in os.walk(pool_root, topdown=False):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue
        if os.path.realpath(dirpath) != os.path.realpath(pool_root):
            try:
                os.rmdir(dirpath)  # 仅当目录已空才成功 / succeeds only when empty
            except OSError:
                pass
    return removed


async def _compress_into_pool(
    files: List[str],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> int:
    """缓存池文件就地无损压缩（TIFF/HDF5）：逐个压到系统临时目录后
    ``os.replace`` 原子替换原文件；单文件失败保留原文件不中断。
    返回压缩成功的数量。Compress pool files in place; failures keep the raw
    file. Returns the compressed count."""
    from services.compressor import compress_files_for_staging

    compressed = 0
    total = len(files)
    for idx, path in enumerate(files, start=1):
        if cancel_event.is_set():
            break
        await send_progress(
            (idx - 1) / max(1, total),
            f"压缩入缓存池 {idx}/{total} / Compressing into cache pool {idx}/{total}",
        )
        tmp_dir = tempfile.mkdtemp(prefix="xfais-pool-comp-")
        try:
            report = await compress_files_for_staging(
                [path], tmp_dir, send_progress, cancel_event
            )
            if report.get("status") == "ok":
                produced = [
                    item.get("outputPath")
                    for item in report.get("files", [])
                    if item.get("status") == "ok" and item.get("outputPath")
                ]
                if produced and os.path.isfile(produced[0]):
                    os.replace(produced[0], path)
                    compressed += 1
        except Exception:  # noqa: BLE001 — 单文件失败保留原文件
            pass
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
    return compressed


async def _action_download(
    payload: Dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> Dict[str, Any]:
    entry = _get_connection(payload.get("connId"))
    if entry is None:
        return _err(
            "Connection not found or expired, please reconnect",
            "连接不存在或已超时，请重新连接",
        )
    # 缓存池模式：下载到 <cacheDir>/<serverKey>/<相对路径>，随后就地无损压缩
    # （TIFF/HDF5），TTL 惰性回收；命中（池内同名文件已存在，可能是压缩副本，
    # 体积与远端不等）直接跳过传输——「下次选择云端数据直接用缓存」。
    # Cache-pool mode: download into the pool, compress in place, lazy TTL
    # pruning; an existing pool entry short-circuits the transfer.
    pool_mode = bool(payload.get("cachePool"))
    cache_ttl = _cache_ttl_minutes(payload)
    pool_root = ""
    server_root_real = ""
    if pool_mode:
        try:
            pool_root = _cache_pool_root(payload)
        except ValueError as exc:
            return _err(str(exc))
        # v0.5.0 缓存池 v2：按「操作时间」分文件夹——每次下载操作独立一个
        # <serverKey>/<操作时间戳>/ 目录；池内文件按「远端绝对路径」存放
        # （模块无关），同一远端文件换模块再选时跨操作目录查重命中，
        # 不重复缓存、对服务器零读取。
        # Cache pool v2: one folder per download operation, files stored by
        # REMOTE ABSOLUTE PATH (module-independent) — the same remote file
        # picked from any module dedupes across operation folders.
        server_key = _sanitize_server_key(payload.get("serverKey"))
        server_root = os.path.join(pool_root, server_key)
        op_stamp = time.strftime("%Y%m%d-%H%M%S")
        dest_raw = os.path.join(server_root, op_stamp)
        try:
            os.makedirs(dest_raw, exist_ok=True)
        except OSError as exc:
            return _err(f"cannot create cache pool dir: {exc} / 无法创建缓存池目录：{exc}")
        server_root_real = os.path.realpath(os.path.abspath(server_root))
        _prune_cache_pool(pool_root, cache_ttl)
    elif bool(payload.get("useTempDir")):
        dest_raw = os.path.join(tempfile.gettempdir(), "xfais-remote-cache")
        try:
            os.makedirs(dest_raw, exist_ok=True)
        except OSError as exc:
            return _err(f"cannot create temp cache dir: {exc} / 无法创建临时缓存目录：{exc}")
    else:
        dest_raw = payload.get("destDir", "")
    if not isinstance(dest_raw, str) or not dest_raw.strip():
        return _err("destination directory is required / 请选择本地保存目录")
    try:
        validated_output_path_optional(dest_raw, field="dest dir")
    except ValueError as exc:
        return _err(str(exc))
    if not os.path.isabs(dest_raw):
        return _err(
            "dest dir must be absolute / 目标目录必须是绝对路径（请用对话框选择）"
        )
    paths_raw = payload.get("paths")
    if not isinstance(paths_raw, list) or not paths_raw:
        return _err("paths is required / 请选择要下载的内容")
    if len(paths_raw) > 2000:
        return _err("too many selections / 单次选择过多（>2000）")
    base_raw = payload.get("basePath")
    try:
        [_require_abs_remote(p, "path") for p in paths_raw]
        _require_abs_remote(base_raw, "basePath")
    except ValueError as exc:
        return _err(str(exc))
    skip_existing = bool(payload.get("skipExisting", True))

    loop = asyncio.get_running_loop()
    bridge = _ProgressBridge(loop, send_progress)
    cancelled = cancel_event.is_set

    # 单一 work() 闭包内完成：扫描（栈式遍历，远端路径就地三连校验）→
    # 本地目标构造（段净化 → 拒 .. → normpath 拼接 → commonpath 圈定）→
    # mkstemp fd 流式写入 → 原子改名 / 取消清理。载荷派生路径不跨函数传递。
    def work() -> Dict[str, Any]:
        sftp = entry["sftp"]
        downloaded: List[str] = []
        transferred: List[str] = []
        skipped = 0
        failed: List[Dict[str, str]] = []

        # ---- 阶段 1：栈式扫描远端选中项 ----
        files: List[Tuple[str, Tuple[str, ...], int]] = []
        try:
            base_norm = posixpath.normpath(base_raw)
            stack: List[Tuple[str, Tuple[str, ...], int]] = []
            for p in paths_raw:
                if not isinstance(p, str) or not p.strip():
                    raise ValueError("invalid path / 路径非法")
                if "\x00" in p or "\\" in p:
                    raise ValueError(f"invalid path: {p!r} / 路径非法")
                if ".." in PurePosixPath(p).parts:
                    raise ValueError(f"path contains '..' / 路径含 .. 段，已拒绝：{p!r}")
                start = posixpath.normpath(p)
                if not start.startswith("/"):
                    raise ValueError(f"path must be absolute / 路径必须是绝对路径：{p!r}")
                segs = remote_rel_segments(base_norm, start)
                stack.append((start, segs, 0))
            while stack:
                remote_raw, segs, depth = stack.pop(0)
                if len(files) >= MAX_FILES_PER_TASK:
                    raise ValueError(
                        f"too many files (>{MAX_FILES_PER_TASK}) / "
                        f"文件数超过上限 {MAX_FILES_PER_TASK}"
                    )
                if depth > MAX_WALK_DEPTH:
                    raise ValueError(
                        f"remote directory too deep (>{MAX_WALK_DEPTH}) / 远端目录层级过深"
                    )
                if ".." in PurePosixPath(remote_raw).parts:
                    raise ValueError("remote path contains '..' / 远端路径含 .. 段，已拒绝")
                remote = posixpath.normpath(remote_raw)
                if not remote.startswith("/"):
                    raise ValueError("remote path must be absolute / 远端路径必须是绝对路径")
                st = sftp.stat(remote)
                if st.st_mode is not None and stat_mod.S_ISDIR(st.st_mode):
                    for attr in sorted(
                        sftp.listdir_attr(remote), key=lambda a: a.filename
                    ):
                        child_raw = remote + "/" + attr.filename
                        if ".." in PurePosixPath(child_raw).parts:
                            raise ValueError(
                                "remote child contains '..' / 远端子路径含 .. 段，已拒绝"
                            )
                        stack.append((child_raw, segs + (attr.filename,), depth + 1))
                else:
                    files.append((remote, segs, int(st.st_size or 0)))
        except ValueError as exc:
            return _err(str(exc))
        except Exception as exc:  # noqa: BLE001
            return _classify_io_error(exc)

        total = len(files)
        total_bytes = sum(size for _, _, size in files)
        if total == 0:
            return {
                "status": "ok",
                "action": "download",
                "downloaded": [],
                "skipped": 0,
                "failed": [],
                "fileCount": 0,
                "totalBytes": 0,
                "outputDir": dest_raw,
            }
        bridge.report(
            0.0,
            f"扫描完成：{total} 个文件，共 {_human_bytes(total_bytes)} / "
            f"Scanned {total} files, {_human_bytes(total_bytes)} total",
        )

        # ---- 本地目标根：就地「拒 .. → realpath(abspath())」 ----
        if "\x00" in dest_raw or ".." in dest_raw.replace("\\", "/").split("/"):
            return _err("invalid dest dir / 目标目录非法（含 .. 或非法字符）")
        root_real = os.path.realpath(os.path.abspath(dest_raw))

        # ---- 阶段 2：逐文件下载（全部就地收口） ----
        done_bytes = 0
        for idx, (remote_abs, segs, size) in enumerate(files, start=1):
            if cancelled():
                return _cancelled_result(downloaded, skipped, failed, dest_raw, total, total_bytes)
            name = segs[-1] if segs else remote_abs
            # 段净化 → 拒 .. → normpath 拼接 → commonpath 圈定。
            # 缓存池模式：rel 取「远端绝对路径」段（模块无关）——同一远端
            # 文件在任何模块的 basePath 下都得到同一池内路径。
            # Per-file rel: base-relative normally; for the cache pool, the
            # REMOTE ABSOLUTE path segments (module-independent dedupe key).
            try:
                if pool_mode:
                    parts = [sanitize_remote_segment(part) for part in remote_abs.strip("/").split("/")]
                else:
                    parts = [sanitize_remote_segment(s) for s in segs]
            except ValueError as exc:
                failed.append({"path": remote_abs, "reason": str(exc)})
                continue
            rel_raw = "/".join(parts)
            if ".." in PurePosixPath(rel_raw).parts:
                failed.append(
                    {"path": remote_abs, "reason": "local target contains '..' / 目标含 ..，已拒绝"}
                )
                continue
            rel_norm = posixpath.normpath(rel_raw)
            target = os.path.normpath(root_real + os.sep + rel_norm)
            if os.path.commonpath([root_real, target]) != root_real:
                failed.append(
                    {
                        "path": remote_abs,
                        "reason": "local target escapes destination / 目标逃出目录，已拒绝",
                    }
                )
                continue
            parent_rel = posixpath.dirname(rel_norm)
            parent_dir = os.path.normpath(root_real + os.sep + parent_rel)
            os.makedirs(parent_dir, exist_ok=True)
            # 缓存池跨操作查重：同一远端文件在「任何历史操作文件夹」中已缓存
            # （可能为无损压缩副本，体积与远端不等，故不做尺寸比对）→ 直接取用，
            # 不重复下载/缓存，对服务器零读取；新鲜度由 TTL 回收保证。
            # Cache-pool cross-operation dedupe: an existing copy of the same
            # remote file in ANY previous operation folder short-circuits the
            # transfer and its path is returned to the caller.
            if pool_mode:
                hit_path: str | None = None
                try:
                    for op_name in os.listdir(server_root_real):
                        candidate = os.path.join(server_root_real, op_name, rel_norm)
                        if os.path.isfile(candidate):
                            hit_path = candidate
                            break
                except OSError:
                    hit_path = None
                if hit_path is not None:
                    skipped += 1
                    downloaded.append(os.path.realpath(hit_path))
                    done_bytes += size
                    bridge.report(
                        done_bytes / total_bytes if total_bytes else 1.0,
                        f"缓存命中：{name}（{idx}/{total}）/ Cache hit: {name} ({idx}/{total})",
                    )
                    continue
            if (pool_mode and os.path.isfile(target)) or (
                skip_existing and os.path.isfile(target) and os.path.getsize(target) == size
            ):
                # 本操作文件夹内命中（极少数：同秒二次操作）→ 直接取用。
                # Same-folder hit (rare: a second op within the same second).
                skipped += 1
                if pool_mode:
                    downloaded.append(os.path.realpath(target))
                done_bytes += size
                bridge.report(
                    done_bytes / total_bytes if total_bytes else 1.0,
                    f"跳过已存在：{name}（{idx}/{total}）/ Skipped existing: {name} ({idx}/{total})",
                )
                continue

            file_start = done_bytes

            def on_chunk(received: int, _start: int = file_start, _idx: int = idx,
                         _name: str = name) -> bool:
                nonlocal done_bytes
                done_bytes = _start + received
                bridge.report(
                    done_bytes / total_bytes if total_bytes else 1.0,
                    f"下载中 {_idx}/{total}：{_name} / Downloading {_idx}/{total}: {_name}",
                )
                return not cancelled()

            # 传输（就地：远端三连校验 → mkstemp fd 写入 → 原子改名）
            try:
                if ".." in PurePosixPath(remote_abs).parts:
                    raise ValueError("remote file contains '..' / 远端文件路径含 .. 段，已拒绝")
                remote_file = posixpath.normpath(remote_abs)
                if not remote_file.startswith("/"):
                    raise ValueError("remote file must be absolute / 远端文件路径必须是绝对路径")
                final_path = os.path.realpath(os.path.abspath(target))
                fd, tmp_path = tempfile.mkstemp(
                    prefix=".xfais-part-", dir=parent_dir
                )
                try:
                    received = 0
                    with os.fdopen(fd, "wb") as out:
                        with sftp.open(remote_file, "rb") as src:
                            while True:
                                buf = src.read(CHUNK_SIZE)
                                if not buf:
                                    break
                                out.write(buf)
                                received += len(buf)
                                if not on_chunk(received):
                                    raise _TransferCancelled()
                    os.replace(tmp_path, final_path)
                except BaseException:
                    # 失败/取消都清理系统生成的临时文件
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                    raise
                downloaded.append(final_path)
                transferred.append(final_path)
                done_bytes = file_start + size
                bridge.report(
                    done_bytes / total_bytes if total_bytes else 1.0,
                    f"已下载 {idx}/{total}：{name} / Downloaded {idx}/{total}: {name}",
                )
            except _TransferCancelled:
                return _cancelled_result(downloaded, skipped, failed, dest_raw, total, total_bytes)
            except ValueError as exc:
                failed.append({"path": remote_abs, "reason": str(exc)})
                done_bytes = file_start + size
                continue
            except Exception as exc:  # noqa: BLE001 — per-file failure, keep going
                failed.append({"path": remote_abs, "reason": f"{type(exc).__name__}: {exc}"})
                done_bytes = file_start + size
                continue
        bridge.report(1.0, f"完成：{len(downloaded)} 个文件 / Done: {len(downloaded)} files")
        return {
            "status": "ok",
            "action": "download",
            "downloaded": downloaded,
            "skipped": skipped,
            "failed": failed,
            "fileCount": total,
            "totalBytes": total_bytes,
            "outputDir": dest_raw,
            # 仅本操作真正传输的文件（缓存命中不重复压缩）/ newly transferred
            # only — cache hits are already compressed, never recompressed.
            "transferred": transferred,
        }

    result = await asyncio.to_thread(work)
    if result.get("status") == "ok" and pool_mode and bool(payload.get("cacheCompress", True)):
        compressible = [
            p
            for p in result.get("transferred") or []
            if p.lower().endswith(_CACHE_COMPRESSIBLE_EXTS)
        ]
        if compressible and not cancel_event.is_set():
            result["compressedCount"] = await _compress_into_pool(
                compressible, send_progress, cancel_event
            )
        result["cachePool"] = True
        result["outputDir"] = dest_raw
    return result


async def _action_cache_pool_list(payload: Dict[str, Any]) -> Dict[str, Any]:
    """列出缓存池内容（先做 TTL 惰性回收）：供远端选择器「从缓存池选择」与
    远程数据同步页的缓存池卡片使用。仅本地文件系统操作，远端零接触。
    List pool contents (lazy TTL pruning first); local FS only."""
    try:
        pool_root = _cache_pool_root(payload)
    except ValueError as exc:
        return _err(str(exc))
    if not os.path.isdir(pool_root):
        return {"status": "ok", "entries": [], "pruned": 0, "poolRoot": pool_root}
    pruned = _prune_cache_pool(pool_root, _cache_ttl_minutes(payload))
    entries: List[Dict[str, Any]] = []
    for dirpath, _dirnames, filenames in os.walk(pool_root):
        for name in filenames:
            path = os.path.join(dirpath, name)
            try:
                rel = os.path.relpath(path, pool_root).replace(os.sep, "/")
                entries.append(
                    {
                        "path": os.path.realpath(path),
                        "relPath": rel,
                        "serverKey": rel.split("/", 1)[0] if "/" in rel else "",
                        "name": name,
                        "size": os.path.getsize(path),
                        "mtime": int(os.path.getmtime(path)),
                    }
                )
            except OSError:
                continue
    entries.sort(key=lambda item: item["mtime"], reverse=True)
    return {"status": "ok", "entries": entries[:2000], "pruned": pruned, "poolRoot": pool_root}


async def _action_cache_pool_export(
    payload: Dict[str, Any],
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> Dict[str, Any]:
    """缓存池 → 本地：把勾选的池内文件复制到用户指定目录（保留文件名，
    重名加后缀）。所选路径必须落在缓存池根内（commonpath 圈定）。
    Export pool entries to a user directory; paths must stay inside the pool."""
    try:
        pool_root = _cache_pool_root(payload)
    except ValueError as exc:
        return _err(str(exc))
    if not os.path.isdir(pool_root):
        return _err("cache pool is empty / 缓存池为空")
    dest_raw = payload.get("destDir", "")
    if not isinstance(dest_raw, str) or not dest_raw.strip():
        return _err("destination directory is required / 请选择本地保存目录")
    try:
        validated_output_path_optional(dest_raw, field="dest dir")
    except ValueError as exc:
        return _err(str(exc))
    if not os.path.isabs(dest_raw):
        return _err("dest dir must be absolute / 目标目录必须是绝对路径（请用对话框选择）")
    paths_raw = payload.get("paths")
    if not isinstance(paths_raw, list) or not paths_raw:
        return _err("paths is required / 请选择要转化的缓存文件")
    if len(paths_raw) > 2000:
        return _err("too many selections / 单次选择过多（>2000）")
    pool_real = os.path.realpath(pool_root)
    selected: List[str] = []
    for raw in paths_raw:
        if not isinstance(raw, str) or not raw.strip() or "\x00" in raw:
            return _err("invalid path / 路径非法")
        real = os.path.realpath(os.path.abspath(raw))
        try:
            inside = os.path.commonpath([pool_real, real]) == pool_real
        except ValueError:
            inside = False
        if not inside:
            return _err("path escapes the cache pool / 路径在缓存池之外，已拒绝")
        if not os.path.isfile(real):
            return _err(f"not a file in the cache pool: {os.path.basename(real)} / 缓存池中不存在该文件")
        selected.append(real)
    dest_real = os.path.realpath(os.path.abspath(dest_raw))
    os.makedirs(dest_real, exist_ok=True)

    loop = asyncio.get_running_loop()
    bridge = _ProgressBridge(loop, send_progress)

    def work() -> Dict[str, Any]:
        exported: List[Dict[str, Any]] = []
        failed: List[Dict[str, str]] = []
        used: set = set()
        for idx, src in enumerate(selected, start=1):
            if cancel_event.is_set():
                return {
                    "status": "ok",
                    "action": "cache_pool_export",
                    "exported": exported,
                    "failed": failed,
                    "outputDir": dest_raw,
                    "cancelled": True,
                }
            base = os.path.basename(src)
            stem, suffix = os.path.splitext(base)
            dest = os.path.join(dest_real, base)
            counter = 1
            while dest in used or os.path.exists(dest):
                dest = os.path.join(dest_real, f"{stem}_{counter}{suffix}")
                counter += 1
            used.add(dest)
            try:
                fd, tmp_path = tempfile.mkstemp(prefix=".xfais-export-", dir=dest_real)
                try:
                    with os.fdopen(fd, "wb") as out, open(src, "rb") as src_fh:
                        while True:
                            buf = src_fh.read(CHUNK_SIZE)
                            if not buf:
                                break
                            out.write(buf)
                    os.replace(tmp_path, dest)
                except BaseException:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
                    raise
                exported.append(
                    {
                        "path": dest,
                        "filename": os.path.basename(dest),
                        "size": os.path.getsize(dest),
                    }
                )
            except OSError as exc:
                failed.append({"path": src, "reason": f"{type(exc).__name__}: {exc}"})
            bridge.report(
                idx / len(selected),
                f"转化中 {idx}/{len(selected)} / Exporting {idx}/{len(selected)}",
            )
        return {
            "status": "ok",
            "action": "cache_pool_export",
            "exported": exported,
            "failed": failed,
            "outputDir": dest_raw,
        }

    return await asyncio.to_thread(work)


def _action_disconnect(payload: Dict[str, Any]) -> Dict[str, Any]:
    conn_id = payload.get("connId")
    if isinstance(conn_id, str) and conn_id:
        drop_connection(conn_id)
    return {"status": "ok", "action": "disconnect"}


# ---------------------------------------------------------------------------
# Entry point / 唯一入口
# ---------------------------------------------------------------------------

async def handle_remote_data(
    payload: dict,
    send_progress: Callable[[float, str], Awaitable[None]],
    cancel_event: asyncio.Event,
) -> dict:
    """Single entry point of the remote-data (SFTP) service.

    远程数据（SFTP）服务的唯一入口。所有动作都要求桌面载荷
    （``_is_desktop``，由 Electron 主进程在回环 WS 上注入——本服务是后端
    首个出站连接能力，web 客户端一律拒绝，见模块 docstring 安全模型）。
    """
    action = payload.get("action")

    if not bool(payload.get("_is_desktop", False)):
        return _err(
            "Remote data access is desktop-only.",
            "远程数据功能仅桌面版可用。",
        )

    if action == "connect":
        return await _action_connect(payload)
    if action == "list":
        return await _action_list(payload)
    if action == "download":
        return await _action_download(payload, send_progress, cancel_event)
    if action == "cache_pool_list":
        return await _action_cache_pool_list(payload)
    if action == "cache_pool_export":
        return await _action_cache_pool_export(payload, send_progress, cancel_event)
    if action == "disconnect":
        return _action_disconnect(payload)
    return _err(f"Unknown action: {action!r}", f"未知操作：{action!r}")
