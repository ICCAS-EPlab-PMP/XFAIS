#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Background subtraction service for X-FAIS.
X-FAIS 背景扣除服务模块。

Implements reference-based 2D background subtraction with ionchamber
transmission correction and HDF5 multi-frame stack processing.

Also includes 2D background estimation methods:
- Rolling Ball (classic / smooth)
- Polynomial fitting
- Morphological operations

Core formula / 核心公式:
    result = sample / T - background

Where T is the transmission factor (decimal ratio, 0-1).

Usage / 用法::

    from python.services.bg_subtractor import (
        subtract_with_reference,
        parse_ionchamber_file,
        calc_transmission,
        match_ionchamber,
        subtract_h5_stack,
        find_h5_transmissions,
        estimate_background_2d,
        rolling_ball_subtract,
        polynomial_subtract,
    )

    # Single image subtraction / 单张图像扣除
    result = subtract_with_reference(sample, background, transmission=0.85)

    # 2D background estimation / 2D背景估计
    background, subtracted = estimate_background_2d(data, method='rolling_ball')
"""

from __future__ import annotations

import os
import re
import logging
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import h5py
import numpy as np
import pandas as pd
from scipy import ndimage
from scipy.ndimage import minimum_filter

logger = logging.getLogger(__name__)

# Dead pixel threshold (same as BGsub / 与 BGsub 一致)
H5_DEAD_PIXEL_THRESHOLD: float = 4.25e9

# HDF5 transmission dataset search keys / HDF5 透射率数据集搜索键名
H5_TRANSMISSION_KEYS: Tuple[str, ...] = (
    "transmission",
    "Transmission",
    "T",
    "trans",
    "Trans",
    "transmittance",
    "Transmittance",
    "t_percent",
    "T_percent",
)


# ---------------------------------------------------------------------------
# Function 1: Core 2D background subtraction / 核心 2D 背景扣除
# ---------------------------------------------------------------------------

def subtract_with_reference(
    sample: np.ndarray,
    background: np.ndarray,
    transmission: float = 1.0,
) -> np.ndarray:
    """
    Subtract reference background with transmission correction.
    使用参考背景进行扣除，支持透射率校正。

    Formula / 公式: result = sample / T - background

    Parameters
    ----------
    sample : np.ndarray
        Sample image (2D or higher, last 2 dims used).
        样品图像（2D 或更高维，使用最后两个维度）。
    background : np.ndarray
        Reference background image.
        参考背景图像。
    transmission : float
        Transmission factor as decimal ratio (0, 1]. Must be > 0.
        透射率因子，小数比率 (0, 1]，必须大于 0。

    Returns
    -------
    result : np.ndarray
        Background-subtracted result, float32.
        扣除背景后的结果，float32 类型。

    Raises
    ------
    ValueError
        If transmission <= 0.
    """
    if transmission <= 0:
        raise ValueError(
            f"Transmission must be > 0, got {transmission}. "
            f"透射率必须大于 0，当前值为 {transmission}。"
        )

    sr, sc = sample.shape[-2:]
    rr, rc = background.shape[-2:]
    cr, cc = min(sr, rr), min(sc, rc)

    result = np.zeros_like(sample, dtype=np.float32)
    result[..., :cr, :cc] = (
        sample[..., :cr, :cc].astype(np.float32) / transmission
        - background[..., :cr, :cc].astype(np.float32)
    )

    # Detect NaN/Inf / 检测 NaN/Inf
    n_bad = np.count_nonzero(~np.isfinite(result))
    if n_bad > 0:
        logger.warning(
            "subtract_with_reference: %d non-finite values in result "
            "(T=%.4f, sample_shape=%s, bg_shape=%s). "
            "结果中存在 %d 个非有限值。",
            n_bad, transmission, sample.shape, background.shape, n_bad,
        )

    return result


# ---------------------------------------------------------------------------
# Function 2: Ionchamber file parsing / 电离室文件解析
# ---------------------------------------------------------------------------

def parse_ionchamber_file(path: str) -> Optional[pd.DataFrame]:
    """
    Parse an SSRF ionchamber text file into a DataFrame.
    解析 SSRF 电离室文本文件为 DataFrame。

    File format / 文件格式::

        # Time  Ionchamber0  Ionchamber1  Ionchamber2
        2026-01-19 12:34:34.130671238  2.807135e-7  2.388761e-8  9.71103e-10

    Parameters
    ----------
    path : str
        Path to ionchamber file (.Ionchamber or .txt).
        电离室文件路径。

    Returns
    -------
    pd.DataFrame or None
        DataFrame with columns ["Time", "Ionchamber0", "Ionchamber1", "Ionchamber2"],
        or None on failure.
    """
    content: Optional[str] = None
    # utf-8-sig first: a BOM (common in Windows-created files) would otherwise
    # hide the leading '#' and make the whole file unparsable.
    # 优先 utf-8-sig：Windows 生成的 BOM 会遮住行首 '#'，导致整份文件解析失败。
    for encoding in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            with open(path, "r", encoding=encoding) as handle:
                content = handle.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as exc:
            logger.error("parse_ionchamber_file: failed to read %s: %s", path, exc)
            return None

    if content is None:
        logger.error("parse_ionchamber_file: all encodings failed for %s", path)
        return None

    try:
        lines = [
            line for line in content.strip().splitlines()
            if line and not line.startswith("#")
        ]
        rows: List[List[Any]] = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 5:
                rows.append(
                    [" ".join(parts[:2])] + [float(v) for v in parts[2:5]]
                )

        if not rows:
            logger.warning("parse_ionchamber_file: no data rows in %s", path)
            return None

        return pd.DataFrame.from_records(
            rows,
            columns=pd.Index(["Time", "Ionchamber0", "Ionchamber1", "Ionchamber2"]),
        )
    except Exception as exc:
        logger.error("parse_ionchamber_file: parse error for %s: %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Function 3: Transmission calculation / 透射率计算
# ---------------------------------------------------------------------------

def calc_transmission(
    sample_ion_df: pd.DataFrame,
    bg_ion_df: pd.DataFrame,
    channel: str = "Ionchamber0",
    method: str = "median",
) -> float:
    """
    Calculate transmission ratio from ionchamber DataFrames.
    从电离室 DataFrame 计算透射率比率。

    Returns sample_intensity / bg_intensity as a decimal ratio (NOT percentage).
    返回 sample_intensity / bg_intensity 的小数比率（非百分比）。

    Parameters
    ----------
    sample_ion_df : pd.DataFrame
        Sample ionchamber DataFrame (from parse_ionchamber_file).
    bg_ion_df : pd.DataFrame
        Background ionchamber DataFrame.
    channel : str
        Column name to use ("Ionchamber0", "Ionchamber1", "Ionchamber2").
    method : str
        Statistical method: "median", "mean", or "trimmed_mean".

    Returns
    -------
    float
        Transmission ratio (decimal, typically 0-1).

    Raises
    ------
    ValueError
        If bg_intensity is zero or channel not found.
    """
    sample_intensity = _calc_ion_intensity(sample_ion_df, channel, method)
    bg_intensity = _calc_ion_intensity(bg_ion_df, channel, method)

    if sample_intensity is None:
        raise ValueError(
            f"Cannot compute sample intensity for channel '{channel}' "
            f"with method '{method}'."
        )
    if bg_intensity is None or bg_intensity == 0.0:
        raise ValueError(
            f"Background intensity is zero or unavailable for channel "
            f"'{channel}' — cannot compute transmission."
        )

    return float(sample_intensity / bg_intensity)


def calc_transmission_dual(
    sample_ion_df: pd.DataFrame,
    bg_ion_df: pd.DataFrame,
    sample_before: str = "Ionchamber0",
    sample_after: str = "Ionchamber1",
    bg_before: str = "Ionchamber0",
    bg_after: str = "Ionchamber1",
    method: str = "median",
) -> float:
    """
    Calculate transmission from upstream/downstream ionchamber pairs.
    由前后（上游/下游）电离室通道对计算透射率。

    Formula / 公式::

        T = (sample_after / sample_before) * (bg_before / bg_after)

    2026-11-06 用户指正后修正（2026-11-04 首版公式恰为其倒数）：样品后通道/
    样品前通道 × 背景前通道/背景后通道。前=上游束路电离室（测入射），后=下游
    电离室（测透射）；背景（空束路）运行的两通道比给出下游/上游响应比，用它
    归一化样品运行的前后比即消除束流漂移。物理上透过率一般 <100%——若结果
    >100%，请检查前后通道是否选反。
    T is generally below 100%; a result above 100% means the before/after
    channels were probably swapped.

    Parameters
    ----------
    sample_ion_df : pd.DataFrame
        Sample ionchamber DataFrame (from parse_ionchamber_file).
        样品电离室 DataFrame。
    bg_ion_df : pd.DataFrame
        Background ionchamber DataFrame.
        背景电离室 DataFrame。
    sample_before : str
        Upstream channel of the sample run ("Ionchamber0/1/2").
        样品测量的前（上游）通道。
    sample_after : str
        Downstream channel of the sample run.
        样品测量的后（下游）通道。
    bg_before : str
        Upstream channel of the background run.
        背景测量的前（上游）通道。
    bg_after : str
        Downstream channel of the background run.
        背景测量的后（下游）通道。
    method : str
        Statistical method: "median", "mean", or "trimmed_mean".

    Returns
    -------
    float
        Transmission ratio (decimal).

    Raises
    ------
    ValueError
        If before/after channels coincide, a channel is missing, or a
        denominator is zero.
        前后通道相同、通道不存在或分母为零时抛出。
    """
    if sample_before == sample_after:
        raise ValueError(
            f"Sample before/after channels must differ, got '{sample_before}' "
            f"for both — the formula would always be 1. "
            f"/ 样品前后通道必须不同（当前均为 '{sample_before}'），否则公式恒为 1。"
        )
    if bg_before == bg_after:
        raise ValueError(
            f"Background before/after channels must differ, got '{bg_before}' "
            f"for both — the formula would always be 1. "
            f"/ 背景前后通道必须不同（当前均为 '{bg_before}'），否则公式恒为 1。"
        )

    bg_before_i = _calc_ion_intensity(bg_ion_df, bg_before, method)
    bg_after_i = _calc_ion_intensity(bg_ion_df, bg_after, method)
    sample_before_i = _calc_ion_intensity(sample_ion_df, sample_before, method)
    sample_after_i = _calc_ion_intensity(sample_ion_df, sample_after, method)

    missing = [
        name for name, value in (
            (f"bg.{bg_before}", bg_before_i),
            (f"bg.{bg_after}", bg_after_i),
            (f"sample.{sample_before}", sample_before_i),
            (f"sample.{sample_after}", sample_after_i),
        ) if value is None
    ]
    if missing:
        raise ValueError(
            f"Cannot compute ion intensity for channel(s): {', '.join(missing)} "
            f"with method '{method}'. / 以下通道无法计算强度：{', '.join(missing)}。"
        )
    for name, value in (
        (f"sample.{sample_before}", sample_before_i),
        (f"bg.{bg_after}", bg_after_i),
    ):
        if value == 0.0:
            raise ValueError(
                f"Denominator {name} is zero — cannot compute transmission. "
                f"/ 分母 {name} 为零，无法计算透射率。"
            )

    return float(
        (sample_after_i / sample_before_i) * (bg_before_i / bg_after_i)
    )


def _reject_warmup(values: np.ndarray) -> np.ndarray:
    """
    Drop a leading warm-up segment from one ionchamber channel.
    剔除电离室单通道开头的预热段（如 shutter 未开时的读数）。

    Continuous scans often start recording before the shutter opens, leaving
    a few rows near the detector floor (orders of magnitude below the median,
    e.g. 3e-11 vs 1e-5). The median is robust to them, but mean /
    trimmed_mean are visibly biased. Only a *leading* contiguous run far
    below the channel median is dropped, and never more than half the rows.

    连续扫描常在 shutter 开启前就开始记录，留下几行贴底的读数（比中位数低
    几个数量级，如 3e-11 对 1e-5）。中位数对它们稳健，但 mean / trimmed_mean
    会被明显拉偏。只剔除「位于开头、连续、远低于通道中位数」的行段，且绝不
    超过总行数的一半。
    """
    if values.size < 4:
        return values
    med = float(np.median(values))
    if not np.isfinite(med) or med <= 0.0:
        return values
    threshold = 0.05 * med
    n = 0
    while n < values.size and values[n] < threshold:
        n += 1
    if 0 < n < values.size // 2:
        logger.info(
            "_reject_warmup: dropped %d leading warm-up rows "
            "(threshold=%.3g, median=%.3g). 剔除 %d 行预热段。",
            n, threshold, med, n,
        )
        return values[n:]
    return values


def _calc_ion_intensity(
    df: pd.DataFrame, channel: str, method: str
) -> Optional[float]:
    """
    Calculate a summary intensity from one ionchamber channel.
    计算电离室单通道的统计强度值。
    """
    try:
        values = _reject_warmup(df[channel].to_numpy(dtype=float))
        if method == "median":
            return float(np.median(values))
        if method == "trimmed_mean":
            sorted_values = np.sort(values)
            if len(sorted_values) > 2:
                return float(np.mean(sorted_values[1:-1]))
            return float(np.mean(sorted_values))
        # Default: mean
        return float(np.mean(values))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Function 4: Ionchamber file matching / 电离室文件匹配
# ---------------------------------------------------------------------------

def _split_name(stem: str) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Parse a filename stem into (base, state, number) components.
    解析文件名主干为 (基础名, 状态段, 末尾编号)。

    Examples / 示例:
        "wkf-G1-Q-30-2-waxs-11.9s_00001" → ("wkf", "g1-q-30-2-waxs-11.9s", 1)
        "wkf-G1-W-30-1-BG-waxs_00001"    → ("wkf", "g1-w-30-1-bg-waxs", 1)
    """
    normalized = stem.replace("_", "-")
    parts = [p for p in normalized.split("-") if p]
    if not parts:
        return stem.lower(), None, None

    base = parts[0].lower()
    if len(parts) >= 2 and re.fullmatch(r"\d+", parts[-1]):
        number = int(parts[-1])
        middle = parts[1:-1]
    else:
        number = None
        middle = parts[1:]
    state = "-".join(p.lower() for p in middle) if middle else None
    return base, state, number


_DETECTOR_TOKENS = frozenset({"waxs", "saxs", "maxs", "gisaxs", "pdf", "edxd"})


def _normalize_state(state: Optional[str]) -> Optional[str]:
    """
    Token-normalize a state fragment for matching.
    对状态片段做 token 归一化，供匹配比较。

    Continuous-scan naming often omits or reorders the detector segment
    between the data file and its ionchamber file (e.g. data
    "DADT-...-TEST-waxs-9.9s_00001" vs ion "DADT-...-TEST-9.9s_1"), so the
    raw strings never compare equal. Dropping known detector tokens makes
    the two fragments identical without loosening anything else.

    连续扫描命名中，数据文件与电离室文件常缺失或改排探测器段（如数据
    "DADT-...-TEST-waxs-9.9s_00001" 对 电离室 "DADT-...-TEST-9.9s_1"），
    原串永不相等。剔除已知探测器 token 后两者即相同，其余部分不受影响。
    """
    if state is None:
        return None
    tokens = [t for t in state.split("-") if t and t not in _DETECTOR_TOKENS]
    return "-".join(tokens) if tokens else None


def _state_similarity(left: Optional[str], right: Optional[str]) -> float:
    """Calculate similarity between state fragments. 计算状态片段相似度。

    Comparison runs on detector-token-normalized fragments, so a missing
    "waxs"/"saxs" segment no longer lowers the score.
    比较在剔除探测器 token 后的片段上进行，缺失 "waxs"/"saxs" 段不再拉低分数。
    """
    left_n = _normalize_state(left)
    right_n = _normalize_state(right)
    if left_n is None and right_n is None:
        return 1.0
    if left_n is None or right_n is None:
        return 0.0
    return SequenceMatcher(None, left_n, right_n).ratio()


# ---------------------------------------------------------------------------
# Time-window matching helpers / 时间窗匹配辅助
# ---------------------------------------------------------------------------

# Pilatus TVX TIFF headers carry the acquisition time as plain ASCII
# "YYYY:MM:DD HH:MM:SS" within the first bytes of the file.
# Pilatus TVX TIFF 头部前若干字节内有纯文本采集时间 "YYYY:MM:DD HH:MM:SS"。
_TIFF_ACQ_TIME_RE = re.compile(r"(\d{4}):(\d{2}):(\d{2}) (\d{2}):(\d{2}):(\d{2})")

# Time-window matching constants / 时间窗匹配常量
TIME_WINDOW_MIN_NAME_SCORE = 0.90   # name pairs trusted for clock calibration / 用于时钟校准的高置信命名对
TIME_WINDOW_RETRY_BELOW = 0.85      # name results below this are retried by time / 低于此分数的命名结果重试时间窗
TIME_WINDOW_SCORE = 0.85            # score reported for a time-window match / 时间窗匹配的报告分数
TIME_WINDOW_MARGIN = timedelta(seconds=60)  # window half-width allowance / 时间窗半宽余量


def _read_tiff_acq_time(path: str) -> Optional[datetime]:
    """
    Read the acquisition time from a Pilatus TVX TIFF header.
    从 Pilatus TVX TIFF 头部读取采集时间。

    Scans the first 8 KB for the ASCII pattern ``YYYY:MM:DD HH:MM:SS``.
    Returns None for unreadable files, other formats (EDF/HDF5), or missing
    timestamps — the caller then simply keeps the name-based result.
    扫描前 8 KB 内的 ASCII 模式 ``YYYY:MM:DD HH:MM:SS``。文件不可读、其他
    格式（EDF/HDF5）或无时间戳时返回 None——调用方保留按命名匹配的结果。
    """
    try:
        with open(path, "rb") as handle:
            head = handle.read(8192)
    except OSError:
        return None
    match = _TIFF_ACQ_TIME_RE.search(head.decode("latin-1", errors="replace"))
    if match is None:
        return None
    try:
        return datetime(
            int(match.group(1)), int(match.group(2)), int(match.group(3)),
            int(match.group(4)), int(match.group(5)), int(match.group(6)),
        )
    except ValueError:
        return None


def _parse_ion_timestamp(line: str) -> Optional[datetime]:
    """
    Parse the leading timestamp of an ionchamber data row.
    解析电离室数据行开头的纳秒时间戳（截到秒）。
    """
    try:
        return datetime.strptime(line[:19], "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _ion_file_time_range(path: str) -> Optional[Tuple[datetime, datetime]]:
    """
    Parse the [first, last] recording timestamps of an ionchamber file.
    解析电离室文件 [首行, 末行] 的记录时间窗。

    Returns None when the file cannot be read or contains no parseable
    timestamps (e.g. a stray report .txt caught by the extension fallback).
    文件不可读或没有可解析时间戳（如扩展名兜底混入的报告 txt）时返回 None。
    """
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as handle:
            lines = [
                line.strip() for line in handle
                if line.strip() and not line.startswith("#")
            ]
    except OSError:
        return None
    if not lines:
        return None
    start = _parse_ion_timestamp(lines[0])
    end = _parse_ion_timestamp(lines[-1])
    if start is None or end is None:
        return None
    if end < start:
        start, end = end, start
    return start, end


def match_ionchamber(
    tiff_files: List[str],
    ionchamber_files: List[str],
) -> List[Dict[str, Any]]:
    """
    Match each data file to its best ionchamber file.
    将每个数据文件匹配到最佳电离室文件。

    Matching priority / 匹配优先级:
        1. Exact match (base + state + number)
        2. Base + state match (detector-token-normalized, closest number)
        3. Base + number match (best state similarity)
        3b. Base + nearest number (continuous-scan fallback)
        4. Base only (best state similarity)
        5. Fuzzy (SequenceMatcher score >= 0.4)
        6. Time-window match (continuous scans): high-confidence name pairs
           (score >= 0.90) calibrate the constant clock offset between the
           ionchamber software and the detector; files whose name score is
           below 0.85 are then matched by which ionchamber recording window
           contains their calibrated acquisition time.
        6. 时间窗匹配（连续扫描）：用高置信命名对（分数 ≥ 0.90）校准电离室
           软件与探测器之间的恒定时钟偏移；命名分数低于 0.85 的文件改按
           「校准后采集时间落入哪个电离室记录时间窗」匹配。

    Parameters
    ----------
    tiff_files : list of str
        Paths to data files (TIFF/EDF).
    ionchamber_files : list of str
        Paths to ionchamber files.

    Returns
    -------
    list of dict
        Each dict: {"data_file": str, "matched_ion": str|None,
                     "score": float, "method": str}
    """
    results: List[Dict[str, Any]] = []
    for data_path in tiff_files:
        data_name = os.path.basename(data_path)
        matched_path, method, score, _sim = _match_single(
            data_name, ionchamber_files
        )
        results.append({
            "data_file": data_path,
            "matched_ion": matched_path,
            "score": score,
            "method": method,
        })

    # --- Time-window pass (continuous scans) / 时间窗兜底（连续扫描） ---
    # The ionchamber recorder and the detector run on different machines with
    # a constant clock offset. Name pairs we already trust (exact / same
    # state / same base+number with a matching state) reveal that offset;
    # files the naming could not place then match by time instead of being
    # guessed by state-tie order.
    # 电离室记录软件与探测器分属两台机器，存在恒定时钟偏移。已被命名信任的
    # 对（exact / 同状态 / 同基础名同编号且状态相符）可揭示该偏移；命名放
    # 不准的文件随后改按时间落位，而不是靠状态平局顺序猜。
    ion_ranges: Dict[str, Optional[Tuple[datetime, datetime]]] = {}

    def _range_for(path: str) -> Optional[Tuple[datetime, datetime]]:
        if path not in ion_ranges:
            ion_ranges[path] = _ion_file_time_range(path)
        return ion_ranges[path]

    acq_times: Dict[str, Optional[datetime]] = {}

    def _acq_for(path: str) -> Optional[datetime]:
        if path not in acq_times:
            acq_times[path] = _read_tiff_acq_time(path)
        return acq_times[path]

    offsets: List[timedelta] = []
    for result in results:
        if result["score"] < TIME_WINDOW_MIN_NAME_SCORE:
            continue
        ion_path = result.get("matched_ion")
        if not ion_path:
            continue
        ion_range = _range_for(ion_path)
        acq_time = _acq_for(result["data_file"])
        if ion_range is not None and acq_time is not None:
            offsets.append(ion_range[0] - acq_time)

    if offsets:
        offsets.sort()
        median_offset = offsets[len(offsets) // 2]
        for result in results:
            if result["score"] >= TIME_WINDOW_RETRY_BELOW:
                continue
            acq_time = _acq_for(result["data_file"])
            if acq_time is None:
                continue
            guess = acq_time + median_offset
            best_path: Optional[str] = None
            best_dist: Optional[float] = None
            for ion_path in ionchamber_files:
                ion_range = _range_for(ion_path)
                if ion_range is None:
                    continue
                window_start, window_end = ion_range
                if not (window_start - TIME_WINDOW_MARGIN
                        <= guess
                        <= window_end + TIME_WINDOW_MARGIN):
                    continue
                center = window_start + (window_end - window_start) / 2
                dist = abs((guess - center).total_seconds())
                if best_dist is None or dist < best_dist:
                    best_path, best_dist = ion_path, dist
            if best_path is not None:
                result["matched_ion"] = best_path
                result["method"] = "time_window"
                result["score"] = TIME_WINDOW_SCORE

    return results


def _match_single(
    data_name: str,
    ion_paths: List[str],
) -> Tuple[Optional[str], str, float, float]:
    """
    Find the best matching ionchamber file for a single data file.
    为单个数据文件查找最佳匹配的电离室文件。
    """
    data_stem = re.sub(r"\.[^.]+$", "", data_name)
    data_base, data_state, data_number = _split_name(data_stem)

    ion_info: List[Tuple[str, str, Optional[str], Optional[int]]] = []
    for path in ion_paths:
        ion_stem = re.sub(
            r"\.[^.]+$", "",
            path.replace("\\", "/").split("/")[-1],
        )
        ion_info.append((path, *_split_name(ion_stem)))

    # Priority 1: Exact match / 精确匹配
    for path, ion_base, ion_state, ion_number in ion_info:
        if (ion_base == data_base
                and ion_state == data_state
                and ion_number == data_number):
            return path, "exact", 1.0, _state_similarity(data_state, ion_state)

    # Priority 2: Base + state match / 基础名+状态匹配
    # (state equality is compared on detector-token-normalized fragments —
    # continuous-scan ionchamber names often omit the "waxs"/"saxs" segment)
    # (状态相等按归一化片段比较——连续扫描的电离室文件名常缺 "waxs"/"saxs" 段)
    norm_data_state = _normalize_state(data_state)
    same_base_state = [
        (path, ion_state, ion_number)
        for path, ion_base, ion_state, ion_number in ion_info
        if ion_base == data_base and _normalize_state(ion_state) == norm_data_state
    ]
    if data_state is not None and norm_data_state is not None and same_base_state:
        # Prefer the ion file whose number is CLOSEST to the data file's own
        # number — the lowest number is simply the oldest scan and pairs the
        # wrong background with the wrong image (silently wrong transmission).
        # 选编号与数据文件「最接近」的电离室文件——取最小编号等于配到最早的
        # 扫描，背景与图像张冠李戴（透射率静默出错）。
        numbered = [item for item in same_base_state if item[2] is not None]
        if data_number is not None and numbered:
            chosen = min(numbered, key=lambda item: abs(item[2] - data_number))
        else:
            chosen = min(
                same_base_state,
                key=lambda item: item[2] if item[2] is not None else float("inf"),
            )
        score = 1.0 if len(same_base_state) == 1 else 0.95
        return chosen[0], "base_state", score, _state_similarity(
            data_state, chosen[1]
        )

    # Priority 3: Base + number, best state / 基础名+编号，最佳状态
    if data_number is not None:
        same_base_number = [
            (path, ion_state, ion_number)
            for path, ion_base, ion_state, ion_number in ion_info
            if ion_base == data_base and ion_number == data_number
        ]
        if same_base_number:
            chosen = max(
                same_base_number,
                key=lambda item: _state_similarity(data_state, item[1]),
            )
            similarity = _state_similarity(data_state, chosen[1])
            return chosen[0], "base_num_best_state", 0.80 + similarity * 0.2, similarity

    # Priority 3b: Base + nearest number / 基础名+最近编号（连续扫描兜底）。
    # A continuous scan produces more data files than ionchamber files (e.g.
    # 6 images, 3 ionchambers). For files whose number has no same-number
    # donor, the closest-numbered ionchamber of the same base is the most
    # plausible donor — closer in time than an arbitrary pick by state-tie
    # order (the old behaviour silently chose the first same-state file).
    # 连续扫描的数据文件数常多于电离室文件数（如 6 图 3 电离室）。编号没有
    # 同号候选时，同基础名下编号最近的电离室是时间上最合理的供体——比按
    # state 平局顺序任选（旧行为：静默选中列表里第一个）更接近真实。
    if data_number is not None:
        same_base_numbered = [
            (path, ion_state, ion_number)
            for path, ion_base, ion_state, ion_number in ion_info
            if ion_base == data_base and ion_number is not None
        ]
        if same_base_numbered:
            chosen = min(
                same_base_numbered,
                key=lambda item: (
                    abs(item[2] - data_number),
                    -_state_similarity(data_state, item[1]),
                ),
            )
            similarity = _state_similarity(data_state, chosen[1])
            return chosen[0], "base_num_nearest", 0.70 + similarity * 0.1, similarity

    # Priority 4: Base only, best state / 仅基础名，最佳状态
    same_base = [
        (path, ion_state)
        for path, ion_base, ion_state, ion_number in ion_info
        if ion_base == data_base
    ]
    if same_base:
        chosen = max(
            same_base,
            key=lambda item: _state_similarity(data_state, item[1]),
        )
        similarity = _state_similarity(data_state, chosen[1])
        return chosen[0], "base_only_best_state", 0.65 + similarity * 0.1, similarity

    # Priority 5: Fuzzy match / 模糊匹配
    best_path: Optional[str] = None
    best_score = 0.0
    best_similarity = 0.0
    for path, ion_base, ion_state, ion_number in ion_info:
        score = SequenceMatcher(None, data_base, ion_base).ratio()
        if (ion_state is not None and data_state is not None
                and ion_state == data_state):
            score += 0.25
        if (ion_number is not None and data_number is not None
                and ion_number == data_number):
            score += 0.25
        if ion_base.startswith(data_base) or data_base.startswith(ion_base):
            score += 0.10
        if score > best_score:
            best_path = path
            best_score = score
            best_similarity = _state_similarity(data_state, ion_state)

    if best_path is not None and best_score >= 0.4:
        return best_path, "fuzzy", best_score, best_similarity

    return None, "none", 0.0, 0.0


# ---------------------------------------------------------------------------
# Function 5: HDF5 multi-frame subtraction / HDF5 多帧扣除
# ---------------------------------------------------------------------------

def subtract_h5_stack(
    h5_path: str,
    dataset_path: str,
    bg_data: np.ndarray,
    transmissions: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Subtract background from an HDF5 multi-frame dataset with per-frame
    transmission correction.
    对 HDF5 多帧数据集进行背景扣除，支持逐帧透射率校正。

    Parameters
    ----------
    h5_path : str
        Path to HDF5 file.
    dataset_path : str
        Internal dataset path (e.g. "/entry/data/data").
    bg_data : np.ndarray
        Background data, broadcastable to frame shape.
    transmissions : np.ndarray or None
        Per-frame transmission values (length N). If None, T=1.0 for all.

    Returns
    -------
    result : np.ndarray
        Background-subtracted stack, shape (N, H, W), float32.

    Raises
    ------
    FileNotFoundError
        If h5_path does not exist.
    KeyError
        If dataset_path not found in HDF5 file.
    ValueError
        If transmissions length doesn't match frame count.
    """
    if not os.path.isfile(h5_path):
        raise FileNotFoundError(f"HDF5 file not found: {h5_path}")

    with h5py.File(h5_path, "r") as fh:
        if dataset_path not in fh:
            raise KeyError(
                f"Dataset '{dataset_path}' not found in {h5_path}"
            )
        dataset = fh[dataset_path]
        if not isinstance(dataset, h5py.Dataset):
            raise KeyError(
                f"'{dataset_path}' is not a dataset in {h5_path}"
            )
        raw = np.asarray(dataset[...], dtype=np.float32)

    # Normalize shape / 规范化形状
    ndim = raw.ndim
    if ndim == 2:
        raw = raw[np.newaxis, :, :]
    elif ndim == 4:
        # (N, C, H, W) → use first channel or flatten
        # Keep as-is for per-frame processing
        pass
    elif ndim != 3:
        raise ValueError(
            f"Unexpected dataset ndim={ndim}, expected 2/3/4."
        )

    n_frames = raw.shape[0]

    # Validate transmissions / 验证透射率
    if transmissions is not None:
        trans_arr = np.asarray(transmissions, dtype=np.float32).ravel()
        if len(trans_arr) != n_frames:
            raise ValueError(
                f"transmissions length ({len(trans_arr)}) != "
                f"frame count ({n_frames})"
            )
    else:
        trans_arr = np.ones(n_frames, dtype=np.float32)

    # Prepare background / 准备背景
    bg = np.asarray(bg_data, dtype=np.float32)

    # Compute result / 计算结果
    if raw.ndim == 4:
        # (N, C, H, W): subtract per-frame across all channels
        result = np.zeros_like(raw, dtype=np.float32)
        for n in range(n_frames):
            t = trans_arr[n]
            if t <= 0:
                logger.warning(
                    "Frame %d: transmission=%.6f <= 0, using T=1.0", n, t
                )
                t = 1.0
            sr, sc = raw.shape[-2:]
            rr, rc = bg.shape[-2:]
            cr, cc = min(sr, rr), min(sc, rc)
            result[n, ..., :cr, :cc] = (
                raw[n, ..., :cr, :cc] / t - bg[..., :cr, :cc]
            )
    else:
        # (N, H, W)
        result = np.zeros_like(raw, dtype=np.float32)
        for n in range(n_frames):
            t = trans_arr[n]
            if t <= 0:
                logger.warning(
                    "Frame %d: transmission=%.6f <= 0, using T=1.0", n, t
                )
                t = 1.0
            sr, sc = raw.shape[-2:]
            rr, rc = bg.shape[-2:]
            cr, cc = min(sr, rr), min(sc, rc)
            result[n, :cr, :cc] = (
                raw[n, :cr, :cc] / t - bg[:cr, :cc]
            )

    n_bad = np.count_nonzero(~np.isfinite(result))
    if n_bad > 0:
        logger.warning(
            "subtract_h5_stack: %d non-finite values in result stack.", n_bad
        )

    return result


# ---------------------------------------------------------------------------
# Function 6: Find transmissions in HDF5 / 在 HDF5 中查找透射率
# ---------------------------------------------------------------------------

def find_h5_transmissions(h5_path: str) -> Optional[np.ndarray]:
    """
    Search an HDF5 file for per-frame transmission values.
    在 HDF5 文件中搜索逐帧透射率数据。

    Searches root-level datasets, nested datasets (by name), and root
    attributes for known transmission key names.
    搜索根级数据集、嵌套数据集（按名称）和根属性中的已知透射率键名。

    Parameters
    ----------
    h5_path : str
        Path to HDF5 file.

    Returns
    -------
    np.ndarray or None
        Transmission values as float32 array, or None if not found.
    """
    keys_lower = {k.lower() for k in H5_TRANSMISSION_KEYS}
    try:
        with h5py.File(h5_path, "r") as fh:
            # Check root-level datasets first / 优先检查根级数据集
            for key in H5_TRANSMISSION_KEYS:
                if key in fh:
                    obj = fh[key]
                    if isinstance(obj, h5py.Dataset):
                        return np.asarray(obj[...], dtype=np.float32)

            # Search nested datasets by name / 按名称搜索嵌套数据集
            found: List[Tuple[str, np.ndarray]] = []

            def _visit(name: str, obj: Any) -> None:
                leaf = name.split("/")[-1].lower()
                if isinstance(obj, h5py.Dataset) and leaf in keys_lower:
                    found.append(
                        (name, np.asarray(obj[...], dtype=np.float32))
                    )

            fh.visititems(_visit)
            if found:
                return found[0][1]

            # Check root attributes / 检查根属性
            for key in H5_TRANSMISSION_KEYS:
                if key in fh.attrs:
                    return np.atleast_1d(
                        np.asarray(fh.attrs[key], dtype=np.float32)
                    )

    except Exception as exc:
        logger.debug("find_h5_transmissions: error reading %s: %s", h5_path, exc)

    return None


# ---------------------------------------------------------------------------
# 2D Background Estimation Methods / 2D 背景估计方法
# ---------------------------------------------------------------------------


class BgMethod(Enum):
    """Background estimation methods / 背景估计方法"""
    ROLLING_BALL_CLASSIC = "rolling_ball_classic"
    ROLLING_BALL_SMOOTH = "rolling_ball_smooth"
    POLYNOMIAL = "polynomial"
    MORPHOLOGICAL = "morphological"


def apply_mask(
    data: np.ndarray,
    mask_min: Optional[float] = None,
    mask_max: Optional[float] = None,
    fill_value: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Apply threshold mask to data.
    对数据应用阈值掩膜。

    Parameters
    ----------
    data : np.ndarray
        Input data / 输入数据
    mask_min : float, optional
        Minimum threshold, values below this will be masked
        最小阈值，低于此值的数据将被掩膜
    mask_max : float, optional
        Maximum threshold, values above this will be masked
        最大阈值，高于此值的数据将被掩膜
    fill_value : float
        Fill value for masked regions / 掩膜区域的填充值

    Returns
    -------
    masked_data : np.ndarray
        Data with masked regions filled / 应用掩膜后的数据
    mask_array : np.ndarray
        Boolean mask array (True = masked region)
        布尔掩膜数组 (True = 被掩膜的区域)
    """
    data = data.astype(np.float32)
    mask_array = np.zeros_like(data, dtype=bool)

    if mask_min is not None:
        mask_array |= (data < mask_min)

    if mask_max is not None:
        mask_array |= (data > mask_max)

    mask_array |= ~np.isfinite(data)

    masked_data = data.copy()
    masked_data[mask_array] = fill_value

    return masked_data, mask_array


def auto_detect_mask_thresholds(
    data: np.ndarray,
    low_percentile: float = 0.1,
    high_percentile: float = 99.9,
) -> Tuple[float, float]:
    """
    Auto-detect mask thresholds based on percentiles.
    基于百分位数自动检测掩膜阈值。

    Parameters
    ----------
    data : np.ndarray
        Input data / 输入数据
    low_percentile : float
        Lower percentile for threshold / 下百分位数阈值
    high_percentile : float
        Upper percentile for threshold / 上百分位数阈值

    Returns
    -------
    mask_min : float
        Minimum threshold / 最小阈值
    mask_max : float
        Maximum threshold / 最大阈值
    """
    flat_data = data.ravel()
    flat_data = flat_data[np.isfinite(flat_data)]

    if len(flat_data) == 0:
        return 0.0, 100.0

    mask_min = float(np.percentile(flat_data, low_percentile))
    mask_max = float(np.percentile(flat_data, high_percentile))

    return mask_min, mask_max


def rolling_ball_subtract(
    data: np.ndarray,
    radius: float = 20.0,
    rolling_ball_type: str = "classic",
    mask_array: Optional[np.ndarray] = None,
    fill_value: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Rolling ball background subtraction.
    滚球法背景扣除。

    Parameters
    ----------
    data : np.ndarray
        Input image data / 输入图像数据
    radius : float
        Radius of rolling ball in pixels / 滚球半径（像素单位）
    rolling_ball_type : str
        'classic' or 'smooth' / 'classic'（经典）或 'smooth'（平滑）
    mask_array : np.ndarray, optional
        Boolean mask (True = masked region) / 布尔掩膜
    fill_value : float
        Fill value for masked regions / 掩膜区域填充值

    Returns
    -------
    background : np.ndarray
        Estimated background / 估计的背景
    subtracted : np.ndarray
        Background-subtracted signal / 扣除背景后的信号
    """
    data = data.astype(np.float32)

    if mask_array is not None and mask_array.any():
        data_for_rolling = data.copy()
        data_for_rolling[mask_array] = np.nan

        valid_mask = ~np.isnan(data_for_rolling)
        if valid_mask.any():
            valid_coords = np.argwhere(valid_mask)
            valid_values = data_for_rolling[valid_mask]
            all_coords = np.argwhere(np.ones_like(data_for_rolling, dtype=bool))

            from scipy.spatial import KDTree
            tree = KDTree(valid_coords)
            distances, indices = tree.query(all_coords, k=1)
            interpolated_values = valid_values[indices]
            data_for_rolling = interpolated_values.reshape(data.shape)
        else:
            data_for_rolling = np.zeros_like(data)
    else:
        data_for_rolling = data.copy()

    if rolling_ball_type == "classic":
        if radius > 0:
            size = 2 * int(radius) + 1
            y, x = np.ogrid[-int(radius):int(radius) + 1, -int(radius):int(radius) + 1]
            kernel = x * x + y * y <= radius * radius
            kernel = kernel.astype(np.float32)
        else:
            kernel = np.ones((1, 1), dtype=np.float32)

        try:
            background = minimum_filter(
                data_for_rolling, footprint=kernel, mode="nearest"
            )
            if radius > 2:
                background = ndimage.gaussian_filter(
                    background, sigma=max(1, radius / 4.0)
                )
        except Exception:
            background = ndimage.median_filter(
                data_for_rolling, size=max(3, int(radius))
            )

    elif rolling_ball_type == "smooth":
        if radius > 0:
            y, x = np.ogrid[-int(radius):int(radius) + 1, -int(radius):int(radius) + 1]
            kernel = np.sqrt(x * x + y * y) <= radius
            kernel = kernel.astype(np.float32)
        else:
            kernel = np.ones((1, 1), dtype=np.float32)

        try:
            eroded = ndimage.grey_erosion(data_for_rolling, footprint=kernel, mode="nearest")
            background = ndimage.grey_dilation(eroded, footprint=kernel, mode="nearest")
        except Exception:
            background = minimum_filter(
                data_for_rolling, footprint=kernel, mode="nearest"
            )
    else:
        raise ValueError("rolling_ball_type must be 'classic' or 'smooth'")

    background = np.minimum(background, data)

    if mask_array is not None and mask_array.any():
        background[mask_array] = fill_value

    subtracted = data - background
    subtracted = np.maximum(subtracted, 0)

    if mask_array is not None:
        subtracted[mask_array] = fill_value

    return background, subtracted


def polynomial_background(
    data: np.ndarray,
    degree: int = 2,
    axis: int = 0,
) -> np.ndarray:
    """
    Fit polynomial to each row/column and estimate background.
    对每行/列拟合多项式并估计背景。

    Parameters
    ----------
    data : np.ndarray
        Input 2D data / 输入2D数据
    degree : int
        Polynomial degree / 多项式阶数
    axis : int
        Axis along which to fit (0: rows, 1: columns) / 拟合轴 (0: 行, 1: 列)

    Returns
    -------
    background : np.ndarray
        Polynomial-fitted background / 多项式拟合背景
    """
    if axis == 0:
        background = np.zeros_like(data)
        for i in range(data.shape[0]):
            y = data[i, :]
            x = np.arange(len(y))
            coeffs = np.polyfit(x, y, degree)
            background[i, :] = np.polyval(coeffs, x)
    else:
        background = np.zeros_like(data)
        for i in range(data.shape[1]):
            y = data[:, i]
            x = np.arange(len(y))
            coeffs = np.polyfit(x, y, degree)
            background[:, i] = np.polyval(coeffs, x)

    return background


def polynomial_subtract(
    data: np.ndarray,
    degree: int = 2,
    axis: int = 0,
    mask_array: Optional[np.ndarray] = None,
    fill_value: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Polynomial background subtraction.
    多项式背景扣除。

    Parameters
    ----------
    data : np.ndarray
        Input 2D data / 输入2D数据
    degree : int
        Polynomial degree / 多项式阶数
    axis : int
        Fit axis (0: rows, 1: columns) / 拟合轴
    mask_array : np.ndarray, optional
        Boolean mask / 布尔掩膜
    fill_value : float
        Fill value for masked regions / 掩膜区域填充值

    Returns
    -------
    background : np.ndarray
        Estimated background / 估计的背景
    subtracted : np.ndarray
        Background-subtracted result / 扣除背景后的结果
    """
    background = polynomial_background(data, degree=degree, axis=axis)
    background = np.minimum(background, data)
    subtracted = data - background
    subtracted = np.maximum(subtracted, 0)

    if mask_array is not None:
        subtracted[mask_array] = fill_value
        background[mask_array] = fill_value

    return background, subtracted


def morphological_background(
    data: np.ndarray,
    radius: int = 10,
    operation: str = "opening",
) -> np.ndarray:
    """
    Estimate background using morphological operations.
    使用形态学操作估计背景。

    Parameters
    ----------
    data : np.ndarray
        Input data / 输入数据
    radius : int
        Structure element radius / 结构元素半径
    operation : str
        'opening' or 'closing' / 'opening'（开运算）或 'closing'（闭运算）

    Returns
    -------
    background : np.ndarray
        Morphological background estimate / 形态学背景估计
    """
    y, x = np.ogrid[-radius:radius + 1, -radius:radius + 1]
    kernel = x * x + y * y <= radius * radius
    kernel = kernel.astype(np.float32)

    if operation == "opening":
        eroded = ndimage.grey_erosion(data, footprint=kernel, mode="nearest")
        background = ndimage.grey_dilation(eroded, footprint=kernel, mode="nearest")
    else:
        dilated = ndimage.grey_dilation(data, footprint=kernel, mode="nearest")
        background = ndimage.grey_erosion(dilated, footprint=kernel, mode="nearest")

    return background


def morphological_subtract(
    data: np.ndarray,
    radius: int = 10,
    operation: str = "opening",
    mask_array: Optional[np.ndarray] = None,
    fill_value: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Morphological background subtraction.
    形态学背景扣除。

    Parameters
    ----------
    data : np.ndarray
        Input data / 输入数据
    radius : int
        Structure element radius / 结构元素半径
    operation : str
        'opening' or 'closing' / 'opening'（开运算）或 'closing'（闭运算）
    mask_array : np.ndarray, optional
        Boolean mask / 布尔掩膜
    fill_value : float
        Fill value for masked regions / 掩膜区域填充值

    Returns
    -------
    background : np.ndarray
        Estimated background / 估计的背景
    subtracted : np.ndarray
        Background-subtracted result / 扣除背景后的结果
    """
    background = morphological_background(data, radius=int(radius), operation=operation)
    background = np.minimum(background, data)
    subtracted = data - background
    subtracted = np.maximum(subtracted, 0)

    if mask_array is not None:
        subtracted[mask_array] = fill_value
        background[mask_array] = fill_value

    return background, subtracted


def estimate_background_2d(
    data: np.ndarray,
    method: str = "rolling_ball_classic",
    radius: float = 20.0,
    degree: int = 2,
    mask_min: Optional[float] = None,
    mask_max: Optional[float] = None,
    fill_value: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Estimate and subtract 2D background from image data.
    从图像数据估计并扣除2D背景。

    Parameters
    ----------
    data : np.ndarray
        Input 2D image data / 输入2D图像数据
    method : str
        Background estimation method / 背景估计方法
        - 'rolling_ball_classic': Classic rolling ball
        - 'rolling_ball_smooth': Smooth rolling ball
        - 'polynomial': Polynomial fitting
        - 'morphological': Morphological opening
    radius : float
        Radius for rolling ball / morphological methods / 滚球/形态学半径
    degree : int
        Polynomial degree (for polynomial method) / 多项式阶数
    mask_min : float, optional
        Minimum threshold for masking / 最小阈值
    mask_max : float, optional
        Maximum threshold for masking / 最大阈值
    fill_value : float
        Fill value for masked regions / 掩膜区域填充值

    Returns
    -------
    background : np.ndarray
        Estimated background / 估计的背景
    subtracted : np.ndarray
        Background-subtracted result / 扣除背景后的结果
    mask : np.ndarray
        Applied mask (boolean) / 应用的掩膜（布尔值）
    """
    # Auto-detect mask thresholds if not provided / 自动检测掩膜阈值
    if mask_min is None or mask_max is None:
        mask_min, mask_max = auto_detect_mask_thresholds(data)

    # Apply mask / 应用掩膜
    masked_data, mask = apply_mask(data, mask_min, mask_max, fill_value)

    # Estimate background based on method / 根据方法估计背景
    if method in ("rolling_ball_classic", "rolling_ball"):
        background, subtracted = rolling_ball_subtract(
            masked_data, radius=radius, rolling_ball_type="classic",
            mask_array=mask, fill_value=fill_value
        )
    elif method == "rolling_ball_smooth":
        background, subtracted = rolling_ball_subtract(
            masked_data, radius=radius, rolling_ball_type="smooth",
            mask_array=mask, fill_value=fill_value
        )
    elif method == "polynomial":
        background, subtracted = polynomial_subtract(
            masked_data, degree=degree, mask_array=mask, fill_value=fill_value
        )
    elif method == "morphological":
        background, subtracted = morphological_subtract(
            masked_data, radius=int(radius), operation="opening",
            mask_array=mask, fill_value=fill_value
        )
    else:
        raise ValueError(f"Unknown method: {method}")

    return background, subtracted, mask
