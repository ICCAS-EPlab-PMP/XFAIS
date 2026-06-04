#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mask_builder.py — MaskBuilder: value range masks, dead pixel masks, custom masks
掩膜构建器 — 值范围掩膜、死像素掩膜、自定义掩膜
"""

from __future__ import annotations

from typing import Optional

import numpy as np


class MaskBuilder:
    """Combine multiple mask sources into a single boolean mask for pyFAI.
    将多个掩膜来源合并为pyFAI使用的单一布尔掩膜。

    Convention: True = masked (excluded) / True = 被屏蔽（排除）
    """

    # 支持的掩膜文件格式
    SUPPORTED_EXTENSIONS = frozenset({".npy", ".npz", ".tif", ".tiff", ".edf"})
    _FABIO_EXTENSIONS = frozenset({".tif", ".tiff", ".edf"})

    @staticmethod
    def build(
        data: np.ndarray,
        valid_min: float,
        valid_max: float,
        dead_mask: Optional[np.ndarray] = None,
        custom_mask: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Build the combined boolean mask.
        构建合并布尔掩膜。Returns bool array where True = masked pixel."""
        mask = np.zeros(data.shape, dtype=bool)
        mask |= (data < valid_min) | (data > valid_max)
        mask |= data == -1.0
        if dead_mask is not None and dead_mask.shape == data.shape:
            mask |= dead_mask
        if custom_mask is not None:
            if custom_mask.shape == data.shape:
                mask |= custom_mask.astype(bool)
            else:
                raise ValueError(
                    f"掩膜尺寸与数据不匹配：\n"
                    f"  数据尺寸: {data.shape}\n"
                    f"  掩膜尺寸: {custom_mask.shape}\n"
                    f"请检查掩膜文件是否与当前数据对应。"
                )
        return mask

    @staticmethod
    def load_mask_file(file_path: str) -> np.ndarray:
        """Load a mask file (.npy / .npz / .tif / .tiff / .edf) and return boolean mask.
        加载掩膜文件并返回布尔掩膜。

        安全性：
        - .npy/.npz 使用 allow_pickle=False 防止任意代码执行
        - 加载前验证文件是否存在
        """
        from pathlib import Path

        import fabio

        path = Path(file_path).resolve()  # 规范化路径，防止路径遍历（如 ../../etc/passwd）
        ext = path.suffix.lower()

        # ── 0. 文件存在性检查 ──
        if not path.is_file():
            raise FileNotFoundError(
                f"掩膜文件不存在：\n"
                f"  {path}\n"
                f"请确认文件路径是否正确，或重新选择掩膜文件。"
            )

        # ── 1. 格式校验 ──
        if ext not in MaskBuilder.SUPPORTED_EXTENSIONS:
            supported = "、".join(
                sorted(MaskBuilder.SUPPORTED_EXTENSIONS)
            )
            raise ValueError(
                f"不支持的掩膜文件格式：{ext}\n"
                f"支持的格式：{supported}\n"
                f"请选择 .npy / .npz（NumPy数组）或 .tif / .tiff / .edf（图像文件）。"
            )

        # ── 2. 按格式加载 ──
        try:
            if ext in (".npy", ".npz"):
                # allow_pickle=False 防止恶意 .npy/.npz 执行任意代码
                try:
                    loaded = np.load(str(path), allow_pickle=False)
                except ValueError as pickle_err:
                    # allow_pickle=False 失败时提供明确提示
                    if "allow_pickle" in str(pickle_err).lower() or "pickle" in str(pickle_err).lower():
                        raise ValueError(
                            f"无法读取掩膜文件 {path.name}：该文件包含需要 pickle 反序列化的对象。\n"
                            f"请使用以下命令重新保存掩膜数组：\n"
                            f"  import numpy as np; m = np.load('{path}', allow_pickle=True); "
                            f"np.save('{path.stem}_safe.npy', m)\n"
                            f"然后用新生成的 .npy 文件作为掩膜。"
                        ) from pickle_err
                    raise
                if ext == ".npz":
                    keys = list(loaded.keys())
                    if not keys:
                        raise ValueError(
                            f"掩膜文件 {path.name} 是空的 .npz 归档，不包含任何数组。"
                        )
                    # 优先选择名为 "mask" 的数组，否则取第一个
                    preferred = [k for k in keys if k.lower() in ("mask", "arr_0")]
                    chosen = preferred[0] if preferred else keys[0]
                    arr = loaded[chosen]
                else:
                    arr = loaded
                if arr.ndim == 0:
                    raise ValueError(
                        f"掩膜文件 {path.name} 包含的是标量（0维），不是二维数组。\n"
                        f"请确保掩膜是二维 NumPy 数组（高度 × 宽度）。"
                    )
                if arr.size == 0:
                    raise ValueError(
                        f"掩膜文件 {path.name} 包含的是空数组（尺寸为 0）。\n"
                        f"请确保掩膜是二维 NumPy 数组（高度 × 宽度）。"
                    )
            elif ext in MaskBuilder._FABIO_EXTENSIONS:
                try:
                    with fabio.open(str(path)) as img:
                        arr = img.data
                except Exception as fabio_err:
                    raise ValueError(
                        f"无法用 fabio 读取图像文件 {path.name}：{fabio_err}\n"
                        f"请确认文件是有效的 {ext} 格式且未损坏。\n"
                        f"如果是 TIFF 文件，请确保不是 BigTIFF 或多页 TIFF 格式。"
                    ) from fabio_err
            else:
                # 防御性分支 — 理论上不会到达（已通过格式校验）
                raise ValueError(f"不支持的掩膜文件格式：{ext}")
        except FileNotFoundError:
            raise  # 已在入口处检查，防御性保留
        except ValueError as e:
            # 保留已包含上下文信息的 ValueError
            msg = str(e)
            if "掩膜文件" in msg or "不支持的" in msg or "无法" in msg or "标量" in msg or "空数组" in msg or "pickle" in msg or "二维" in msg:
                raise
            raise ValueError(
                f"无法读取掩膜文件 {path.name}：{e}\n"
                f"请确认文件内容与扩展名一致，且文件未损坏。"
            ) from e
        except Exception as e:
            raise RuntimeError(
                f"读取掩膜文件 {path.name} 时发生错误：{e}\n"
                f"请检查文件是否完整且未被其他程序占用。"
            ) from e

        # ── 3. 转换为布尔掩膜 ──
        # 非零像素 = True（被屏蔽）
        return arr != 0

    # ── Mask Maker 新增方法 ─────────────────────────────────────────────────

    @staticmethod
    def apply_shape(
        mask: np.ndarray,
        shape_type: str,
        params: dict,
        level: int = 1,
        do_mask: bool = True,
    ) -> np.ndarray:
        """
        在现有 mask 上应用形状操作。
        委托给 silx.image.shapes 的非 GUI 函数。

        Args:
            mask: uint8 2D array (H, W)
            shape_type: 'rectangle' | 'disk' | 'ellipse' | 'polygon' | 'line'
            params: 形状参数
            level: mask 级别 (1-255)，single 模式下为 1
            do_mask: True=遮盖, False=擦除
        Returns:
            修改后的 mask (modified in place)
        """
        H, W = mask.shape

        if shape_type == "rectangle":
            row = int(params["row"])
            col = int(params["col"])
            h = int(params["height"])
            w = int(params["width"])
            r0, r1 = max(0, row), min(H, row + h)
            c0, c1 = max(0, col), min(W, col + w)
            selection = mask[r0:r1, c0:c1]
            if do_mask:
                selection[:, :] = level
            else:
                selection[selection == level] = 0

        elif shape_type == "disk":
            from silx.image.shapes import circle_fill

            crow, ccol = int(params["crow"]), int(params["ccol"])
            radius = float(params["radius"])
            rows, cols = circle_fill(crow, ccol, radius)
            MaskBuilder._apply_points(mask, rows, cols, level, do_mask)

        elif shape_type == "ellipse":
            from silx.image.shapes import ellipse_fill

            crow, ccol = int(params["crow"]), int(params["ccol"])
            radius_r = float(params["radius_r"])
            radius_c = float(params["radius_c"])
            rows, cols = ellipse_fill(crow, ccol, radius_r, radius_c)
            MaskBuilder._apply_points(mask, rows, cols, level, do_mask)

        elif shape_type == "polygon":
            from silx.image.shapes import polygon_fill_mask

            vertices = np.array(params["vertices"], dtype=np.float64)
            # vertices: Nx2 array of [row, col]
            fill = polygon_fill_mask(vertices, (H, W))
            if do_mask:
                mask[fill != 0] = level
            else:
                mask[np.logical_and(fill != 0, mask == level)] = 0

        elif shape_type == "line":
            from silx.image.shapes import draw_line

            r0, c0 = int(params["row0"]), int(params["col0"])
            r1, c1 = int(params["row1"]), int(params["col1"])
            width = int(params.get("width", 1))
            rows, cols = draw_line(r0, c0, r1, c1, width)
            MaskBuilder._apply_points(mask, rows, cols, level, do_mask)

        else:
            raise ValueError(f"Unknown shape type: {shape_type}")

        return mask

    @staticmethod
    def _apply_points(
        mask: np.ndarray,
        rows: np.ndarray,
        cols: np.ndarray,
        level: int,
        do_mask: bool,
    ) -> None:
        """将坐标点应用到 mask 上（带边界裁剪）。"""
        H, W = mask.shape
        valid = (rows >= 0) & (cols >= 0) & (rows < H) & (cols < W)
        rows, cols = rows[valid], cols[valid]
        if do_mask:
            mask[rows, cols] = level
        else:
            in_mask = mask[rows, cols] == level
            mask[rows[in_mask], cols[in_mask]] = 0

    @staticmethod
    def apply_threshold(
        mask: np.ndarray,
        data: np.ndarray,
        mode: str,
        threshold: float = None,
        threshold_min: float = None,
        threshold_max: float = None,
        level: int = 1,
        do_mask: bool = True,
    ) -> np.ndarray:
        """阈值遮盖。直接 numpy 布尔运算。

        Args:
            mode: 'below' | 'above' | 'between' | 'not_finite'
        """
        if mode == "below":
            stencil = data < threshold
        elif mode == "above":
            stencil = data > threshold
        elif mode == "between":
            stencil = (data >= threshold_min) & (data <= threshold_max)
        elif mode == "not_finite":
            stencil = ~np.isfinite(data)
        else:
            raise ValueError(f"Unknown threshold mode: {mode}")

        if do_mask:
            mask[stencil] = level
        else:
            mask[np.logical_and(stencil, mask == level)] = 0

        return mask

    @staticmethod
    def export_mask(
        mask_data: np.ndarray,
        format: str,
        save_path: str,
        header: dict = None,
    ) -> dict:
        """导出 mask 到文件。使用 fabio（已在项目依赖中）。

        Args:
            mask_data: uint8 2D array
            format: 'edf' | 'tif' | 'npy' | 'h5' | 'msk'
            save_path: 目标文件路径
            header: 可选的元数据字典
        Returns:
            dict with status, path, shape, dtype, masked_pixels
        """
        import fabio

        header = header or {}

        if format == "edf":
            hdr = {"program_name": "X-FAIS-mask", "masked_value": "nonzero"}
            hdr.update(header)
            img = fabio.edfimage.edfimage(data=mask_data, header=hdr)
            img.write(save_path)
        elif format == "tif":
            from fabio import TiffIO

            tiff = TiffIO.TiffIO(save_path, mode="w")
            tiff.writeImage(mask_data, software="X-FAIS")
        elif format == "npy":
            np.save(save_path, mask_data)
        elif format in ("h5", "hdf5", "nxs"):
            import h5py

            ds_path = header.get("dataset_path", "/mask")
            with h5py.File(save_path, "w") as f:
                f.create_dataset(ds_path, data=mask_data)
        elif format == "msk":
            img = fabio.fit2dmaskimage.fit2dmaskimage(data=mask_data)
            img.write(save_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

        return {
            "status": "ok",
            "path": save_path,
            "shape": list(mask_data.shape),
            "dtype": str(mask_data.dtype),
            "masked_pixels": int(np.count_nonzero(mask_data)),
        }
