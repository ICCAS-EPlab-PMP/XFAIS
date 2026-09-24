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
