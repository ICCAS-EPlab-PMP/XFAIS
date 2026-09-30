#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h5_extractor.py — H5 filter by suffix, copy, rename (no GUI dependencies)
H5提取器 — 按后缀过滤、复制、重命名H5文件（无GUI依赖）
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from .h5convert import is_h5_file, matches_suffix_filter, scan_h5_files

log = logging.getLogger(__name__)


def referenced_h5_files(h5_path: str) -> list[str]:
    """Files referenced by a master HDF5 via external links or virtual-dataset
    sources (Nexus writers store detector frames in sibling `*_data_*.h5`
    files the master points into). Returns raw reference strings; callers
    resolve relative names against the master's directory.
    master HDF5 通过外部链接或虚拟数据集（VDS）引用的文件（Nexus 写入器把
    探测器帧存放在同目录 `*_data_*.h5` 中）。返回原始引用串；相对路径由
    调用方按 master 所在目录解析。"""
    try:
        import h5py
    except ImportError:
        return []

    refs: list[str] = []
    try:
        with h5py.File(h5_path, "r") as f:
            def _walk(group: Any, prefix: str) -> None:
                # Iterate link names only (H5Literate): safe even when external
                # link targets are unreachable — f.visit would dereference and
                # abort there. 只枚举链接名：外链目标不可达时也安全（f.visit
                # 会解引用并在断链处中止遍历）。
                for key in group:
                    path = f"{prefix}/{key}" if prefix else key
                    try:
                        link = group.get(key, getlink=True)
                    except Exception:
                        continue
                    if isinstance(link, h5py.ExternalLink):
                        refs.append(link.filename)
                        continue
                    if not isinstance(link, h5py.HardLink):
                        continue  # soft links are internal aliases / 软链接为内部别名
                    try:
                        obj = group.get(key)
                    except Exception:
                        continue
                    if isinstance(obj, h5py.Group):
                        _walk(obj, path)
                    elif isinstance(obj, h5py.Dataset):
                        try:
                            if obj.is_virtual:
                                sources = obj.virtual_sources
                                if callable(sources):
                                    sources = sources()
                                for vs in sources:
                                    refs.append(vs.file_name)
                        except Exception:
                            pass
            _walk(f["/"], "")
    except Exception:
        pass  # not readable as HDF5 — nothing to collect
    return refs


class H5Extractor:
    """Extract and copy H5 files from a source tree to a flat output directory.
    从源目录树提取和复制H5文件到扁平输出目录。"""

    def __init__(
        self,
        source_dir: str | Path,
        target_dir: str | Path,
        suffix_filter: str = "",
        prepend_folder: bool = True,
        prefix: str = "",
        conflict_policy: str = "rename",
    ):
        self.source_dir = str(source_dir)
        self.target_dir = str(target_dir)
        self.suffix_filter = suffix_filter.strip().lower()
        self.prepend_folder = prepend_folder
        self.prefix = prefix.strip()
        self.conflict_policy = conflict_policy

    def find_h5_files(self, recursive: bool = True) -> list[str]:
        """Find all supported H5/Nexus files in source_dir. 查找源目录所有受支持的 H5/Nexus 文件。"""
        if recursive:
            return scan_h5_files(self.source_dir, recursive=True)
        files = []
        for f in sorted(os.listdir(self.source_dir)):
            full = os.path.join(self.source_dir, f)
            if os.path.isfile(full) and is_h5_file(f):
                files.append(full)
        return files

    def filter_files(self, all_files: list[str]) -> list[str]:
        """Filter H5 files by suffix. 按后缀过滤H5文件。"""
        if not self.suffix_filter:
            return all_files
        return [f for f in all_files if matches_suffix_filter(os.path.basename(f), self.suffix_filter)]

    def extract(
        self,
        log_fn: Optional[Callable[[str], None]] = None,
        progress_fn: Optional[Callable[[float], None]] = None,
        stop_event: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Execute the extraction. 执行提取。

        Returns dict with success_count, total_files, errors.
        """
        def _log(msg: str) -> None:
            log.info(msg)
            if log_fn:
                log_fn(msg)

        os.makedirs(self.target_dir, exist_ok=True)
        all_files = self.find_h5_files()
        files_to_process = self.filter_files(all_files)
        total = len(files_to_process)

        if total == 0:
            _log("No matching H5 files found (supported: .h5, .nxs, .hdf5).")
            return {"success_count": 0, "total_files": 0, "errors": 0}

        _log(f"Found {total} files to extract")
        success_count = 0
        errors = 0
        stats: dict[str, int] = {"linked_files_copied": 0, "linked_files_missing": 0}

        for i, file_path in enumerate(files_to_process):
            if stop_event is not None and stop_event.is_set():
                _log("Stopped by user.")
                break

            original_name = os.path.basename(file_path)
            parent_folder_name = os.path.basename(os.path.dirname(file_path))

            if self.prepend_folder and parent_folder_name:
                new_name = f"{parent_folder_name}_{original_name}"
            else:
                new_name = original_name

            # Apply optional filename prefix / 应用可选文件名前缀
            if self.prefix:
                new_name = f"{self.prefix}{new_name}"

            dest_path = os.path.join(self.target_dir, new_name)

            if os.path.exists(dest_path):
                if self.conflict_policy == "skip":
                    _log(f"[{i + 1}/{total}] Skipped (exists): {new_name}")
                    continue
                elif self.conflict_policy == "overwrite":
                    pass  # dest_path stays the same, will overwrite
                else:
                    # rename: append counter / 重命名：追加序号
                    base, ext = os.path.splitext(new_name)
                    counter = 1
                    while os.path.exists(dest_path):
                        dest_path = os.path.join(self.target_dir, f"{base}_{counter}{ext}")
                        counter += 1

            try:
                shutil.copy2(file_path, dest_path)
                _log(f"[{i + 1}/{total}] Extracted: {os.path.basename(dest_path)}")
                success_count += 1
            except Exception as exc:
                _log(f"[{i + 1}/{total}] Failed: {file_path}: {exc}")
                errors += 1

            # Nexus masters reference sibling data files via external links /
            # VDS; copying the master alone produces an unreadable copy (HDF5
            # silently serves fill values). Carry the referenced files along,
            # under their original names, next to the extracted master so the
            # relative references keep resolving.
            # Nexus master 通过外部链接/VDS 引用同目录数据文件；只复制 master
            # 会得到读不出数据的副本（HDF5 静默返回填充值）。把被引用文件按
            # 原名复制到提取结果旁，相对引用即可继续解析。
            if os.path.exists(dest_path) and is_h5_file(original_name):
                linked_copied, linked_missing = self._copy_referenced_files(file_path, _log)
                stats["linked_files_copied"] = stats.get("linked_files_copied", 0) + linked_copied
                stats["linked_files_missing"] = stats.get("linked_files_missing", 0) + linked_missing

            if progress_fn:
                progress_fn((i + 1) / total)

        _log(f"Done: {success_count}/{total} extracted, {errors} errors")
        return {
            "success_count": success_count,
            "total_files": total,
            "errors": errors,
            **stats,
        }

    def _copy_referenced_files(self, master_path: str, _log: Callable[[str], None]) -> tuple[int, int]:
        """Copy the files a master references (external links / VDS sources)
        into the flat target dir under their original names. Relative
        references then resolve next to the extracted master; absolute ones
        are warned about (a flat copy cannot satisfy them).
        把 master 引用的文件（外部链接/VDS 源）按原名复制到扁平目标目录。
        相对引用在提取结果旁即可解析；绝对路径引用无法通过扁平复制满足，
        记警告。Returns (copied, missing)."""
        copied = 0
        missing = 0
        seen: set[str] = set()
        for ref in referenced_h5_files(master_path):
            if not ref or ref in seen:
                continue
            seen.add(ref)
            if os.path.isabs(ref):
                _log(f"Warning: absolute reference not carried: {ref}")
                continue
            src_ref = os.path.join(os.path.dirname(master_path), ref)
            if not os.path.isfile(src_ref):
                _log(f"Warning: referenced file not found: {src_ref}")
                missing += 1
                continue
            dest_ref = os.path.join(self.target_dir, os.path.basename(ref))
            if os.path.exists(dest_ref):
                continue  # already carried (e.g. shared data file) / 已随其他 master 复制过
            try:
                shutil.copy2(src_ref, dest_ref)
                copied += 1
            except Exception as exc:
                _log(f"Warning: failed to copy referenced file {src_ref}: {exc}")
                missing += 1
        return copied, missing
