# Mask Maker 模块实现汇总

> 基于 `BETA/plan.md` 实现，所有改动均在 `BETA/` 目录下。

---

## 一、新建文件（7 个）

### 1. `src/types/mask.ts`

TypeScript 类型定义，包含：

- `MaskTool` — 绘制工具枚举：`'pan' | 'rectangle' | 'disk' | 'ellipse' | 'polygon' | 'line'`
- `MaskMode` — 绘制模式：`'mask' | 'unmask'`
- `ShapeParams` — 各种形状参数接口（RectangleParams、DiskParams、EllipseParams、PolygonParams、LineParams）
- `ThresholdMode` — 阈值模式：`'below' | 'above' | 'between' | 'not_finite'`
- `MaskExportFormat` — 导出格式：`'edf' | 'tif' | 'npy' | 'h5' | 'msk'`
- `MASK_EXPORT_FORMATS` — 导出格式常量数组
- `MaskStats` — mask 统计信息
- `MaskImageInfo` — 图像信息
- `DrawState` — 绘制交互状态
- `MaskBackendResponse` / `MaskLoadResponse` / `MaskExportResponse` — 后端响应类型

### 2. `src/lib/mask/mask-store.ts`

Mask 状态管理类 `MaskStore`：

- Uint8Array 存储（H × W, row-major）
- undo/redo 历史栈（最多 10 层快照）
- `fillRect()` — 矩形填充（前端直接执行，保持拖拽响应性）
- `commit()` / `undo()` / `redo()` — 历史管理
- `invert()` / `clear()` / `reset()` — 编辑操作
- `getStats()` — mask 统计（遮盖像素数/百分比）
- `loadMask()` — 从外部数据导入（自动 crop/pad）
- `getMaskBase64()` — 序列化为 base64（用于发送后端）

### 3. `src/components/mask/MaskToolbar.vue`

左侧工具栏面板：

- **文件操作：** 打开图像 / 加载 Mask / 导出 Mask
- **绘制工具：** 平移(pan) / 矩形(rectangle) / 圆形(disk) / 椭圆(ellipse) / 多边形(polygon) / 线条(line)，6 个按钮网格
- **绘制模式：** 遮盖 / 擦除，切换按钮
- **编辑操作：** 撤销 / 重做 / 反转 / 清除全部
- 图像未加载时所有工具按钮处于禁用状态
- 当前选中的工具高亮显示

### 4. `src/components/mask/MaskProperties.vue`

右侧属性面板：

- **图像信息：** 文件名、尺寸、格式、最小值、最大值、标准差
- **Mask 统计：** 遮盖像素数、总像素数、遮盖百分比
- **阈值工具：**
  - 下限/上限数值输入
  - 四个操作按钮：遮盖低于下限 / 遮盖高于上限 / 遮盖介于之间 / 遮盖非有限值

### 5. `src/components/mask/MaskCanvas.vue`

核心画布组件，三层叠加：

- **底层：** `<img>` 显示图像（blob URL）
- **中层：** `<canvas>` mask overlay（半透明红色叠加），`pointer-events: none`
- **顶层：** 鼠标事件处理（在 viewport div 上）
- CSS transform 缩放/平移（以光标为中心缩放）
- 绘制交互：
  - 矩形：拖拽释放后前端直接执行
  - 圆形/椭圆/线条：拖拽释放后发送后端
  - 多边形：单击添加顶点，双击闭合
- 绘制预览：虚线轮廓实时跟随鼠标
- 坐标转换：屏幕坐标 ↔ 像素坐标

### 6. `src/components/mask/MaskExportDialog.vue`

导出对话框（模态弹窗）：

- 格式选择网格：EDF (.edf) / TIFF (.tif) / NumPy (.npy) / HDF5 (.h5) / Fit2D Mask (.msk)
- 保存路径选择（调用 Electron 原生文件对话框）
- 导出中状态提示
- 错误信息显示

### 7. `src/views/workspace/MaskMakerView.vue`

主视图，三栏布局：

- **左：** MaskToolbar
- **中：** MaskCanvas
- **右：** MaskProperties
- **弹窗：** MaskExportDialog
- 负责：
  - 通过 `transport.submitTask('mask_maker', ...)` 与后端通信
  - 图像加载（调用 `action: 'load_preview'`）
  - 形状绘制（调用 `action: 'draw_shape'`，矩形除外）
  - 阈值遮盖（调用 `action: 'apply_threshold'`）
  - Mask 导入/导出（调用 `action: 'load_mask'` / `'export_mask'`）
  - undo/redo 响应式更新

---

## 二、修改现有文件（9 个）

### 1. `src/router/index.ts`

新增路由：

```typescript
{
  path: '/workspace/mask-maker',
  name: 'mask-maker',
  component: () => import('@/views/workspace/MaskMakerView.vue'),
  meta: {
    titleKey: 'maskMaker.title',
    sectionKey: 'shell.sections.workspace',
    descriptionKey: 'maskMaker.subtitle'
  }
}
```

### 2. `src/i18n/messages.ts`

新增两处（zh + en 各一处）：

- `home.cards.maskMaker` — 首页卡片标题和描述
- `maskMaker.*` — 完整命名空间（title, subtitle, toolbar, tools, properties, canvas, export, messages, errors）

约 120 行中英文文案。

### 3. `src/views/HomeView.vue`

`imageCards` 数组中新增 Mask Maker 卡片：

```typescript
{
  key: 'maskMaker',
  route: '/workspace/mask-maker',
  icon: '⬛'
}
```

### 4. `python/services/mask_builder.py`

在 `MaskBuilder` 类中新增三个静态方法：

- **`apply_shape(mask, shape_type, params, level, do_mask)`**
  - 委托 `silx.image.shapes.circle_fill()` / `ellipse_fill()` / `polygon_fill_mask()` / `draw_line()`
  - 直接 numpy 切片处理矩形
  - 返回修改后的 mask

- **`apply_threshold(mask, data, mode, threshold, ...)`**
  - numpy 布尔运算实现 below/above/between/not_finite 四种模式
  - 支持遮盖和擦除

- **`export_mask(mask_data, format, save_path, header)`**
  - 使用 `fabio` 库导出 EDF / TIFF / Fit2D MSK
  - 使用 `numpy.save` 导出 NPY
  - 使用 `h5py` 导出 HDF5

- 新增辅助方法 **`_apply_points()`** — 带边界裁剪的坐标点应用

### 5. `python/service_launcher.py`

在 `handle_viewer_config` 函数末尾（default fallback 之前）新增 4 个 action handler：

- **`draw_shape`** — 前端传入几何参数 + 当前 mask base64，后端用 silx 计算后返回更新后的 mask
- **`apply_threshold`** — 前端传入阈值参数 + 当前 mask + 文件路径，后端加载像素数据后执行阈值遮盖
- **`export_mask`** — 前端传入 mask base64 + 格式 + 路径，后端调用 fabio/h5py 写文件
- **`load_mask`** — 前端传入文件路径，后端调用 `MaskBuilder.load_mask_file()` 返回 uint8 mask

### 6. `electron/main.ts`

`COMMAND_ROUTE_MAP` 新增一行：

```typescript
mask_maker: '/api/viewer_config',
```

复用现有 `/api/viewer_config` 路由（与 viewer 共用同一 handler）。

### 7. `electron/python/runtime.ts`

`runProcess()` 函数中 `spawn` 调用修复（2 处改动）：

- **PATH 前置：** `const augmentedPath = \`${exeDir}${path.delimiter}${pathEnv}\`` — 将 Python 运行时目录加入 PATH 最前
- **cwd 修正：** `cwd: options.cwd ?? exeDir` — 默认工作目录设为 exe 所在目录
- **shell 模式：** `shell: true` — 通过 cmd.exe 间接启动，绕过 CreateProcessW 兼容性问题

### 8. `electron/python/manager.ts`

`launch()` 方法中 `spawn` 调用修复（同 runtime.ts 的三项改动）：

- PATH 前置 + cwd 修正 + `shell: true`

### 9. `package.json`

新增脚本：

```json
"build:pack:dir": "npm run build && electron-builder --win --dir"
```

仅构建 win-unpacked 目录（跳过 NSIS 安装包和 portable，打包更快）。

---

## 三、打包命令

```bash
cd BETA

# 完整打包（NSIS + portable）
npm run build:pack

# 仅 win-unpacked 目录（推荐用于快速测试）
npm run build:pack:dir
```

## 四、打包产物

```
BETA/dist-electron-builder/
├── win-unpacked/
│   ├── X-FAIS.exe
│   └── resources/
│       ├── python-runtime/          ← Python 3.11.9 运行时
│       └── python/                  ← 服务脚本（含 MaskBuilder）
├── X-FAIS-0.1.0-setup-x64.exe     ← NSIS 安装包
└── X-FAIS-0.1.0-portable-x64.exe  ← 免安装便携版
```
