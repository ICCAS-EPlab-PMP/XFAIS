#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bench_integration.py — integration method / thread-scaling benchmark (v0.3.0)
积分算法与线程扩展基准（v0.3.0）

Usage (from BETA/, with the embedded runtime) / 用法（在 BETA/ 下，用内嵌运行时）:
    .python-runtime/python-3.11.9-win32-x64/python.exe python/tools/bench_integration.py \
        [--sizes 2048 4096] [--methods splitpixel csr bbox] [--omp 1 4 0]

Outputs a markdown table comparing per-frame integrate1d wall time per method
and OMP thread count. ``--omp 0`` means "leave the environment untouched"
(the default pyFAI behavior). Use it to pick the Settings → OpenMP threads
recommendation for the hardware you run it on.
输出各算法 × OMP 线程数的单帧积分耗时 markdown 表。--omp 0 表示不改动
环境（pyFAI 默认行为）。用于为设置页的 OpenMP 线程数选择推荐值。
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time


def run_child(size: int, method: str, omp: int, frames: int = 5) -> float:
    """Spawn a fresh interpreter (so OMP env applies) and time steady-state frames.
    拉起全新解释器（使 OMP 环境变量生效）并计时稳态帧。"""
    code = f"""
import numpy as np, time
from pyFAI.integrator.azimuthal import AzimuthalIntegrator
ai = AzimuthalIntegrator(dist=0.25, poni1={size}//2*1e-4, poni2={size}//2*1e-4,
                         pixel1=100e-6, pixel2=100e-6, wavelength=1.54e-10)
rng = np.random.default_rng(0)
img = rng.poisson(100, ({size}, {size})).astype(np.float64)
ai.integrate1d(img, 1000, method="{method}")  # warm-up (engine + CSR build)
t0 = time.perf_counter()
for _ in range({frames}):
    ai.integrate1d(img, 1000, method="{method}")
print((time.perf_counter() - t0) / {frames})
"""
    env = dict(os.environ)
    if omp > 0:
        env["OMP_NUM_THREADS"] = str(omp)
    else:
        env.pop("OMP_NUM_THREADS", None)
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, env=env, check=True,
    )
    return float(out.stdout.strip().splitlines()[-1])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[2048])
    parser.add_argument("--methods", nargs="+", default=["splitpixel", "csr", "bbox"])
    parser.add_argument("--omp", type=int, nargs="+", default=[0])
    parser.add_argument("--frames", type=int, default=5)
    args = parser.parse_args()

    print(f"| size | method | omp | ms/frame |")
    print(f"|---|---|---|---|")
    for size in args.sizes:
        for method in args.methods:
            for omp in args.omp:
                ms = run_child(size, method, omp, args.frames) * 1000.0
                omp_label = "auto" if omp == 0 else str(omp)
                print(f"| {size}² | {method} | {omp_label} | {ms:.0f} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
