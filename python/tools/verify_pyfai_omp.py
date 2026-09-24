#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify_pyfai_omp.py — assert the installed pyFAI wheel is OpenMP-enabled (v0.3.0)
校验已安装的 pyFAI wheel 是否带 OpenMP（v0.3.0）

Background / 背景:
The pre-0.3.0 embedded runtime shipped a custom pyFAI build with NO OpenMP
symbols in any extension (verified 2026-09-22: official PyPI wheel has vcomp
in 13 of 31 .pyd files; our runtime had 0). Without OpenMP the csr multi-core
speedup silently does not exist. Run this after ANY runtime rebuild:
    .python-runtime/python-3.11.9-win32-x64/python.exe python/tools/verify_pyfai_omp.py
Exit code 0 = healthy, 1 = OpenMP missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pyFAI

EXPECTED_MIN = 10  # official 2026.3.0 win64 wheel: 13 / official wheels vary slightly


def main() -> int:
    ext_dir = Path(pyFAI.__file__).resolve().parent / "ext"
    pyds = sorted(ext_dir.glob("*.pyd" if sys.platform == "win32" else "*.so"))
    if not pyds:
        print(f"FAIL: no extension modules under {ext_dir}")
        return 1
    with_omp = [p.name for p in pyds if b"vcomp" in p.read_bytes() or b"gomp" in p.read_bytes()]
    print(f"pyFAI {pyFAI.version}: {len(pyds)} extensions, {len(with_omp)} with OpenMP symbols")
    for name in with_omp:
        print(f"  [omp] {name}")
    if len(with_omp) < EXPECTED_MIN:
        print(
            "FAIL: pyFAI extensions lack OpenMP — csr multithreading will NOT work. "
            "Reinstall from the official PyPI wheel: "
            "python -m pip install --force-reinstall --no-deps pyfai==<version>"
        )
        return 1
    print("OK: OpenMP-enabled pyFAI detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
