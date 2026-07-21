#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Image Math service for X-FAIS.
X-FAIS 图像运算服务模块。

Performs arithmetic operations on two images:
对两张图像执行算术运算：

Core formula / 核心公式:
    result = image1 * factor1 ± image2 * factor2

Where ± is either addition or subtraction.
其中 ± 为加法或减法。

Usage / 用法::

    from python.services.image_math import image_arithmetic

    # Subtract / 减法
    result = image_arithmetic(img1, img2, factor1=1.0, factor2=1.0, operation="subtract")

    # Add / 加法
    result = image_arithmetic(img1, img2, factor1=0.5, factor2=0.5, operation="add")
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core image arithmetic / 核心图像运算
# ---------------------------------------------------------------------------

def image_arithmetic(
    image1: np.ndarray,
    image2: np.ndarray,
    factor1: float = 1.0,
    factor2: float = 1.0,
    operation: str = "subtract",
) -> np.ndarray:
    """
    Perform arithmetic operation on two images.
    对两张图像执行算术运算。

    Formula / 公式:
        subtract: result = image1 * factor1 - image2 * factor2
        add:      result = image1 * factor1 + image2 * factor2

    Parameters
    ----------
    image1 : np.ndarray
        First input image (2D or higher, last 2 dims used).
        第一张输入图像（2D 或更高维，使用最后两个维度）。
    image2 : np.ndarray
        Second input image.
        第二张输入图像。
    factor1 : float
        Multiplication factor for image1. Default 1.0.
        图像1的乘法因子，默认 1.0。
    factor2 : float
        Multiplication factor for image2. Default 1.0.
        图像2的乘法因子，默认 1.0。
    operation : str
        Arithmetic operation: "add" or "subtract". Default "subtract".
        算术运算类型："add"（加法）或 "subtract"（减法），默认 "subtract"。

    Returns
    -------
    result : np.ndarray
        Arithmetic result, float32.
        运算结果，float32 类型。

    Raises
    ------
    ValueError
        If operation is not "add" or "subtract".
        如果 operation 不是 "add" 或 "subtract"。
    """
    if operation not in ("add", "subtract"):
        raise ValueError(
            f"operation must be 'add' or 'subtract', got '{operation}'. "
            f"operation 必须为 'add' 或 'subtract'，当前值为 '{operation}'。"
        )

    # Use overlapping region for shape mismatch / 形状不匹配时使用重叠区域
    sr, sc = image1.shape[-2:]
    rr, rc = image2.shape[-2:]
    cr, cc = min(sr, rr), min(sc, rc)

    if sr != rr or sc != cc:
        logger.warning(
            "image_arithmetic: shape mismatch — image1=%s, image2=%s, "
            "using overlapping region (%d, %d). "
            "图像形状不匹配，使用重叠区域 (%d, %d)。",
            image1.shape, image2.shape, cr, cc, cr, cc,
        )

    # Compute result / 计算结果
    img1_part = image1[..., :cr, :cc].astype(np.float32) * float(factor1)
    img2_part = image2[..., :cr, :cc].astype(np.float32) * float(factor2)

    if operation == "subtract":
        result = img1_part - img2_part
    else:
        result = img1_part + img2_part

    # Detect NaN/Inf / 检测 NaN/Inf
    n_bad = np.count_nonzero(~np.isfinite(result))
    if n_bad > 0:
        logger.warning(
            "image_arithmetic: %d non-finite values in result "
            "(op=%s, f1=%.4f, f2=%.4f, img1_shape=%s, img2_shape=%s). "
            "结果中存在 %d 个非有限值。",
            n_bad, operation, factor1, factor2,
            image1.shape, image2.shape, n_bad,
        )

    return result
