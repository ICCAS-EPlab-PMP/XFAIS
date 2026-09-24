#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_method_parity.py — splitpixel vs csr numerical parity guard (v0.3.0)
积分算法数值对拍测试（v0.3.0）

Guards against silent spectral drift when pyFAI is upgraded or the runtime is
rebuilt: on a synthetic Poisson image, integrate1d with splitpixel and csr must
agree within tolerance on well-populated bins. csr is only an OPT-IN speed
option (default stays splitpixel) — this test pins the contract that opting in
does not change results materially.
防止 pyFAI 升级或运行时重建带来的静默谱漂移：在合成泊松图像上，
splitpixel 与 csr 的 integrate1d 在计数充足的 bin 上必须落在容差内。
csr 仅为可选提速项（默认仍是 splitpixel）——本测试钉住"切换不实质性
改变结果"这一契约。
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

pyFAI = pytest.importorskip("pyFAI")
from pyFAI.integrator.azimuthal import AzimuthalIntegrator  # noqa: E402


def _make_integrator() -> AzimuthalIntegrator:
    return AzimuthalIntegrator(
        dist=0.2,
        poni1=0.09,
        poni2=0.09,
        pixel1=172e-6,
        pixel2=172e-6,
        wavelength=1.5418e-10,
    )


def _synthetic_image(rng: np.random.Generator, shape=(1043, 981)) -> np.ndarray:
    """Poisson background + a smooth ring — realistic counting statistics.
    泊松背景 + 一条平滑环——贴近真实计数统计。"""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    r = np.hypot(yy - shape[0] / 2, xx - shape[1] / 2)
    ring = 800.0 * np.exp(-((r - 260.0) ** 2) / (2 * 30.0 ** 2))
    lam = 50.0 + ring
    return rng.poisson(lam).astype(np.float64)


def test_splitpixel_vs_csr_parity():
    ai = _make_integrator()
    img = _synthetic_image(np.random.default_rng(42))
    npt = 800

    r_split = ai.integrate1d(img, npt, method="splitpixel", unit="q_nm^-1")
    r_csr = ai.integrate1d(img, npt, method="csr", unit="q_nm^-1")

    # NOTE (measured 2026-09-22): the two splitting schemes produce slightly
    # DIFFERENT bin-center positions (splitpixel = full pixel split, csr = bbox
    # split; at low q the pixel size is comparable to the bin width), so the
    # x-axes cannot be compared bin-by-bin — interpolate csr onto the splitpixel
    # axis and compare intensities there.
    # 实测（2026-09-22）：两种分裂方式的 bin 中心位置本身略有不同
    # （splitpixel=完全分裂，csr=bbox 分裂；低 q 处像素尺寸与 bin 宽同量级），
    # 横轴不能逐 bin 比较——把 csr 插值到 splitpixel 轴上再比强度。
    csr_on_split_axis = np.interp(r_split.radial, r_csr.radial, r_csr.intensity)

    # Intensity: compare only well-populated bins (the ring region carries
    # most counts; both methods average identically there).
    # 强度：只比较计数充足的 bin（环区计数高，两法平均应一致）。
    strong = r_split.intensity > 60.0
    assert strong.sum() > 50, "synthetic image lost its ring — fixture broken"
    rel = np.abs(
        r_split.intensity[strong] - csr_on_split_axis[strong]
    ) / r_split.intensity[strong]
    # Pixel-splitting (splitpixel = full split, csr = bbox split) legitimately
    # differs at bin edges; the median must stay far below 1%.
    # splitpixel 为完全分裂、csr 为 bbox 分裂，bin 边缘本就存在合法差异；
    # 中位相对误差须远低于 1%。
    assert float(np.median(rel)) < 1e-2, f"median rel diff too large: {np.median(rel):.3e}"
    assert float(np.percentile(rel, 95)) < 5e-2, f"p95 rel diff too large: {np.percentile(rel, 95):.3e}"


def test_azimuthal_consistency_csr():
    """Same method twice → bit-identical (engine cache sanity). / 同法两次应逐位一致。"""
    ai = _make_integrator()
    img = _synthetic_image(np.random.default_rng(7))
    a = ai.integrate1d(img, 300, method="csr")
    b = ai.integrate1d(img, 300, method="csr")
    np.testing.assert_array_equal(a.intensity, b.intensity)
