"""Output-path policy for task payloads (v0.3.0 security hardening).

Every handler that writes result files to a user-supplied path must pass
the raw payload value through :func:`validated_output_path` — this module
is the single choke point for output-path normalization on the Python side.
任务侧所有"写到用户提供的路径"的入口统一经本模块校验（单一收口点）。

Threat model / 威胁模型:
- Desktop mode: the payload comes from the local renderer only; the user
  legitimately picks any location, so without a configured root the helper
  just normalizes (absolute + symlink-resolved) and rejects clearly
  malformed values.
- Server mode (``serve_web``): the HTTP/WS API is unauthenticated, so the
  operator MUST either front the service with an authenticated reverse
  proxy AND set ``XFAIS_OUTPUT_ROOT`` to confine all result writes to one
  tree (see deploy/deploy.sh hardening notes). With the root set, paths
  that resolve outside it are rejected — ``..`` segments and symlink hops
  are normalized first, so containment is checked on the FINAL location.
"""
from __future__ import annotations

import os
from pathlib import PurePath
from typing import Any

_ROOT_ENV = "XFAIS_OUTPUT_ROOT"


def _configured_root() -> str | None:
    root = os.environ.get(_ROOT_ENV, "").strip()
    return os.path.realpath(root) if root else None


def validated_output_path(raw: Any, *, field: str = "output path") -> str:
    """Validate + normalize a user-supplied output path.

    Accepts ``str`` and ``os.PathLike``; returns an absolute,
    ``~``-expanded, symlink-resolved path string. Raises ``ValueError``
    for anything else, empty values, NUL bytes, or (when
    ``XFAIS_OUTPUT_ROOT`` is set) paths resolving outside the root.
    """
    if isinstance(raw, os.PathLike):
        raw = os.fspath(raw)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid {field}: must be a non-empty string")
    if "\x00" in raw:
        raise ValueError(f"invalid {field}: NUL byte in path")
    # Hard-reject `..` segments in the RAW input (do not silently normalize
    # them away): task payloads should carry dialog-picked absolute paths,
    # so any `..` is treated as hostile. 硬拒绝原始输入中的 .. 段——任务
    # 参数应当是对话框选出的绝对路径，出现 .. 一律视为恶意。
    if ".." in PurePath(raw).parts or (os.altsep and f"..{os.altsep}" in raw):
        raise ValueError(f"invalid {field}: '..' segments are not allowed")
    candidate = os.path.realpath(os.path.abspath(os.path.expanduser(raw)))
    root = _configured_root()
    if root:
        try:
            inside = os.path.commonpath([root, candidate]) == root
        except ValueError:
            # Mixed anchors (e.g. different drives on Windows) — never inside.
            inside = False
        if not inside:
            raise ValueError(
                f"invalid {field}: resolves outside {_ROOT_ENV} ({root})"
            )
    return candidate


def validated_output_path_optional(raw: Any, *, field: str = "output path") -> str:
    """Like :func:`validated_output_path`, but empty/None passes through.

    Handlers use ``""``/``None`` to mean "default location" (e.g. write
    next to the input files); those cases must keep flowing unchanged.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return ""
    return validated_output_path(raw, field=field)


# ---------------------------------------------------------------------------
# Server-mode read gate (v0.5.0) / 服务器模式读取围栏（v0.5.0）
# ---------------------------------------------------------------------------

_INPUT_ROOTS_ENV = "XFAIS_INPUT_ROOTS"


def configured_input_roots() -> list[str]:
    """Admin-opened server folders that server mode may read (read whitelist).

    ``XFAIS_INPUT_ROOTS`` holds ``os.pathsep``-separated absolute paths
    (``;`` on Windows, ``:`` on POSIX). Entries are ``~``-expanded and
    symlink-resolved; empty entries are skipped and duplicates de-duplicated
    (order preserved). An empty result means the admin opened nothing —
    server mode can then only read files inside the session workspace
    (uploads). Desktop mode never consults this list.
    管理员开放给服务器直接读取的目录白名单；未配置时服务器模式只能读
    会话工作区（上传文件）。桌面模式不使用本清单。
    """
    raw = os.environ.get(_INPUT_ROOTS_ENV, "")
    roots: list[str] = []
    seen: set[str] = set()
    for part in raw.split(os.pathsep):
        part = part.strip()
        if not part:
            continue
        resolved = os.path.realpath(os.path.abspath(os.path.expanduser(part)))
        if resolved not in seen:
            seen.add(resolved)
            roots.append(resolved)
    return roots


def _is_inside(candidate: str, root: str) -> bool:
    try:
        return os.path.commonpath([root, candidate]) == root
    except ValueError:
        # Mixed anchors (e.g. different drives on Windows) — never inside.
        return False


def validate_server_read_path(
    raw: Any,
    *,
    session_tmp: str | None = None,
    field: str = "file path",
) -> str:
    """Server-mode read gate: normalize a user-supplied READ path and reject
    anything outside the allowed trees.

    Allowed trees: ``XFAIS_INPUT_ROOTS`` folders (admin-opened), the session
    workspace (uploads), and ``XFAIS_OUTPUT_ROOT`` when configured (so typed
    output flows keep working on hardened deployments). Desktop payloads
    carry ``_is_desktop`` and are allowed wholesale at dispatch — this gate
    only ever sees server-mode requests.
    服务器模式读取围栏：只允许读管理员开放目录、会话工作区（上传文件）与
    输出根（如已配置）；桌面请求在分发层按 ``_is_desktop`` 整体放行。
    """
    if isinstance(raw, os.PathLike):
        raw = os.fspath(raw)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"invalid {field}: must be a non-empty string")
    if "\x00" in raw:
        raise ValueError(f"invalid {field}: NUL byte in path")
    if ".." in PurePath(raw).parts or (os.altsep and f"..{os.altsep}" in raw):
        raise ValueError(f"invalid {field}: '..' segments are not allowed")
    candidate = os.path.realpath(os.path.abspath(os.path.expanduser(raw)))
    allowed = list(configured_input_roots())
    out_root = _configured_root()
    if out_root:
        allowed.append(out_root)
    if session_tmp:
        allowed.insert(0, os.path.realpath(session_tmp))
    for root in allowed:
        if _is_inside(candidate, root):
            return candidate
    raise ValueError(
        f"invalid {field}: server mode can only read files inside "
        f"{_INPUT_ROOTS_ENV} folders or the session workspace "
        f"(got: {candidate}) / 服务器模式只能读取管理员开放目录"
        f"（{_INPUT_ROOTS_ENV}）或本会话上传文件"
    )


# Strings longer than this are treated as embedded content (scripts, JSON
# text, PONI bodies), never as path references. Dialog/picker paths stay
# far below the limit.
# 超过该长度的字符串视为内嵌内容（脚本/JSON/poni 文本）而非路径引用。
_MAX_PATH_VALUE_LEN = 2048


def _looks_like_server_path(value: str) -> bool:
    """Conservative predicate for the payload sweep: absolute, scheme-free,
    content-bounded strings only. Labels, units, scripts and embedded text
    never match.
    保守判定：仅命中"无协议前缀的绝对路径形态短字符串"。
    """
    if not value or len(value) > _MAX_PATH_VALUE_LEN:
        return False
    if "://" in value:
        return False
    return os.path.isabs(value)


def audit_payload_read_paths(payload: Any, *, session_tmp: str | None = None) -> None:
    """Defence-in-depth sweep of a server-mode task payload.

    Recursively walks the payload and rejects any value that looks like an
    absolute server path outside the allowed read trees. Handlers that take
    explicit paths call :func:`validate_server_read_path` for contextual
    errors; this sweep covers every remaining entry point (including future
    ones), so the unauthenticated server API cannot be tricked into reading
    arbitrary files. Raises ``ValueError`` listing the offending values.
    服务器模式载荷纵深防御：递归扫描载荷，任何形似绝对路径且落在允许树
    之外的取值都会使整个任务被拒绝（防止未鉴权 API 被用来读服务器任意
    文件）。需要上下文报错的显式路径入口请调用 validate_server_read_path。
    """
    offenders: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            for value in node.values():
                _walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                _walk(value)
        elif isinstance(node, str):
            if _looks_like_server_path(node):
                try:
                    validate_server_read_path(
                        node, session_tmp=session_tmp, field="payload path"
                    )
                except ValueError:
                    offenders.append(node)

    _walk(payload)
    if offenders:
        shown = "; ".join(offenders[:5])
        more = f" (+{len(offenders) - 5} more)" if len(offenders) > 5 else ""
        raise ValueError(
            "payload references paths outside the server read whitelist: "
            f"{shown}{more} / 载荷引用了服务器读取白名单之外的路径：{shown}{more}"
        )
