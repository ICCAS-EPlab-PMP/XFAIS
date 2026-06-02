#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h5_extractor.py — H5 filter by suffix, copy, rename (no GUI dependencies)
H5提取器 — 按后缀过滤、复制、重命名H5文件（无GUI依赖）
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

log = logging.getLogger(__name__)


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
        """Find all .h5 files in source_dir. 查找源目录所有H5文件。"""
        if recursive:
            return glob.glob(os.path.join(self.source_dir, "**", "*.h5"), recursive=True)
        files = []
        for f in sorted(os.listdir(self.source_dir)):
            full = os.path.join(self.source_dir, f)
            if os.path.isfile(full) and f.lower().endswith(".h5"):
                files.append(full)
        return files

    def filter_files(self, all_files: list[str]) -> list[str]:
        """Filter H5 files by suffix. 按后缀过滤H5文件。"""
        if not self.suffix_filter:
            return all_files
        target_ext = f"{self.suffix_filter}.h5" if not self.suffix_filter.endswith(".h5") else self.suffix_filter
        return [f for f in all_files if os.path.basename(f).lower().endswith(target_ext)]

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
            _log("No matching .h5 files found.")
            return {"success_count": 0, "total_files": 0, "errors": 0}

        _log(f"Found {total} files to extract")
        success_count = 0
        errors = 0

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

            if progress_fn:
                progress_fn((i + 1) / total)

        _log(f"Done: {success_count}/{total} extracted, {errors} errors")
        return {"success_count": success_count, "total_files": total, "errors": errors}
