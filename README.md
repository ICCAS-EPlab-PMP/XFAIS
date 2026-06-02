# X-FAIS

[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-green?style=flat-square&logo=vue.js)](https://vuejs.org/)
[![Electron](https://img.shields.io/badge/Electron-35-lightgrey?style=flat-square&logo=electron)](https://www.electronjs.org/)

**本程序基于 [pyFAI](https://github.com/silx-kit/pyFAI) 和 [fabIO](https://github.com/silx-kit/fabIO) 构建**

X-FAIS (X-ray FAI (pyFAI) Scattering & Diffraction Suite) - 用于 X 射线纤维衍射数据分析和集成的桌面应用程序。

本程序基于pyFAI和FabIO两个主要项目中常见功能项进行基础构建。主要是将原本需要编程的过程改编为常用GUI界面，以节省用户学习成本，更快上手WAXS/SAXS/GIWAXS的构建。

程序由ai-agent进行全栈开发。人工进行数据测试。感谢AI-Agent 制作： opencode、 oh-my-openagent、 Reasonix

使用编程模型： GLM-5.1 / DeepSeek V4 / MiniMax 2.7 / Qwen 3.6 Plus / MiMo V2.5

## 支持平台

| 平台 | 状态 | 安装包格式 |
|------|------|-----------|
| Windows x64 | 已发布 | NSIS 安装包 / 便携版 |
| macOS (Intel / Apple Silicon) | 代码就绪，待构建 | DMG |

## 当前功能特性

**积分分析**

- 1D 径向积分 — 将 2D 衍射图转换为强度随 q 或 2θ 变化的曲线
- 方位角 χ 积分 — 分析强度随方位角的分布
- CAKE 扇区积分 — 对 Debye-Scherrer 环的指定扇区做径向积分
- GIWAXS 纤维积分 — 生成 q_ip × q_oop 二维强度图

**图像与数据工具**

- 图像查看器 — 浏览衍射图像，支持帧导航、对比度调节、PNG 导出
- H5 格式转换 — HDF5 文件批量转换为 TIFF 或 CSV
- H5 数据提取 — 从 HDF5 文件中提取指定数据集
- 批量 PNG 生成 — 批量生成衍射图像的 PNG 预览

**辅助功能**

- 标样生成器 — 从 CIF 文件或晶胞参数计算理论衍射峰位
- 晶胞标样生成器 — 基于空间群和晶胞参数的完整标样计算
- pyFAI 标定检查 — 检查 pyFAI-calib2 的安装状态并可导出启动脚本

**导出格式**：TXT / CSV / HDF5 / XY

## 技术栈

- **前端**: Vue 3 + TypeScript + Vite
- **桌面框架**: Electron 35
- **后端**: Python 3.11（内嵌运行时，WebSocket 通信）
- **图表**: Plotly.js
- **国际化**: Vue I18n
- **核心引擎**: pyFAI（积分计算）、fabio（图像读写）、h5py（HDF5 访问）

```
┌──────────────┐     WebSocket      ┌──────────────────┐
│   前端界面    │ ◄──────────────► │   Python 后端     │
│   Vue 3      │     HTTP/WS       │   pyFAI / fabio   │
│   Vite       │                   │   h5py / scipy    │
└──────┬───────┘                   └──────────────────┘
       │
   Electron 主进程
   (进程管理 / 文件对话框 / 系统集成)
```

用户无需自行安装 Python 或任何依赖，软件开箱即用。

---

## 用户安装与使用

### Windows

1. 下载 `X-FAIS-{version}-setup-x64.exe`（NSIS 安装包）或 `X-FAIS-{version}-portable-x64.exe`（便携版）
2. **安装包**：双击运行，选择安装路径，等待安装完成。可从开始菜单或桌面快捷方式启动
3. **便携版**：直接双击运行，无需安装，适合 U 盘携带使用

### macOS

> macOS 版本代码已就绪，需要在 Mac 上执行构建（见下方"构建发布"章节）。

1. 下载 `X-FAIS-{version}-{arch}.dmg`（arch 为 x64 或 arm64）
2. 双击 DMG 文件，将 X-FAIS 拖入"应用程序"文件夹
3. 首次打开时，在"系统设置 > 隐私与安全性"中允许运行（因为未签名）

---

## 开发环境

### 前置要求

- Node.js >= 18
- npm >= 9
- Python 3.11.9（Windows 下会自动下载安装；macOS 需手动准备运行时）

### 快速开始

```bash
# 安装 Node.js 依赖
npm install

# 启动开发模式（前端热更新 + Electron 窗口）
npm run dev
```

开发模式会同时启动 Vite 开发服务器（`http://127.0.0.1:5173`）和 Electron 窗口，Python 后端会自动启动。

### 常用命令

```bash
npm run dev                 # 开发模式
npm run build               # 仅构建（前端 + Electron 主进程），不打包
npm run build:renderer      # 仅构建前端
npm run build:electron      # 仅构建 Electron 主进程和预加载脚本
npm run build:pack          # Windows 完整打包（构建 + electron-builder）
npm run build:pack:mac      # macOS 完整打包（需在 macOS 上执行）
npm run build:pack:all      # 全平台打包（需在 macOS 上执行）
npm run build:web           # 构建纯 Web 版本（无 Electron）
npm run lint                # ESLint 代码检查
npm run typecheck           # TypeScript 类型检查
npm run test:unit           # 运行单元测试（Vitest）
npm run e2e                 # 端到端测试（Playwright）
npm run test:python         # Python 后端测试
npm run python:health       # 检查 Python 运行时健康状态
```

---

## 构建发布

### Windows

```bash
npm install          # 首次或依赖变更后
npm run build:pack
```

产物位于 `dist-electron-builder/`：

| 文件 | 说明 |
|------|------|
| `X-FAIS-{version}-setup-x64.exe` | NSIS 安装包（支持自定义安装路径） |
| `X-FAIS-{version}-portable-x64.exe` | 免安装便携版 |

### macOS

macOS 打包**必须在 macOS 机器上执行**（electron-builder 不支持从 Windows 跨平台构建 macOS 包）。

**第一步：准备 macOS Python 运行时**

推荐从 [python-build-standalone](https://github.com/indygreg/python-build-standalone) 下载预编译的 Python 3.11.9 独立版本，解压到对应目录：

```bash
# Apple Silicon (arm64)
.python-runtime/python-3.11.9-macos-arm64/

# Intel Mac (x64)
.python-runtime/python-3.11.9-macos-x64/
```

目录结构应包含 `bin/python3` 可执行文件。

**第二步：安装依赖并生成 requirements.lock.txt**

```bash
.python-runtime/python-3.11.9-macos-*/bin/python3 -m pip install -r python/requirements.in
.python-runtime/python-3.11.9-macos-*/bin/python3 -m pip freeze > python/requirements.lock.txt
```

**第三步：执行构建**

```bash
npm install
npm run build:pack:mac
```

产物位于 `dist-electron-builder/`：

| 文件 | 说明 |
|------|------|
| `X-FAIS-{version}-arm64.dmg` | Apple Silicon DMG |
| `X-FAIS-{version}-x64.dmg` | Intel Mac DMG |

---

## 项目结构

```
├── electron/                  # Electron 主进程源码
│   ├── main.ts               # 主进程入口
│   ├── preload.ts            # 预加载脚本
│   ├── constants.ts          # 常量定义（IPC 通道等）
│   └── python/
│       ├── manager.ts        # Python 服务进程管理
│       └── runtime.ts        # Python 运行时检测与安装（跨平台）
├── src/                       # Vue 前端源码
│   ├── views/                # 页面视图
│   │   └── workspace/        # 各功能工作区页面
│   ├── components/           # 组件
│   │   ├── business/         # 业务组件（表单、图表控件等）
│   │   └── charts/           # 图表组件（Plotly / 折线图 / 热力图）
│   ├── lib/                  # 工具函数
│   ├── i18n/                 # 国际化
│   └── types/                # TypeScript 类型定义
├── python/                    # Python 后端
│   ├── service_launcher.py   # 服务入口（HTTP + WebSocket）
│   ├── services/             # 各功能服务模块
│   ├── requirements.in       # Python 依赖声明
│   └── requirements.lock.txt # 锁定版本（构建时自动生成）
├── public/                    # 静态资源
├── ICON/                      # 应用图标（.ico / .icns / .png）
├── resources/                 # electron-builder 构建资源
├── deploy/                    # Web 版本部署配置
├── package.json               # 项目配置与 electron-builder 配置
├── vite.config.ts             # Vite 前端构建配置
├── vite.electron.main.config.ts    # Electron 主进程构建配置
└── vite.electron.preload.config.ts # Electron 预加载脚本构建配置
```

## Python 依赖

内嵌的 Python 运行时包含以下核心库：numpy, matplotlib, pyFAI, fabio, h5py, Pillow, pandas, scipy, tifffile, psutil, websockets

完整的依赖版本锁定在 `python/requirements.lock.txt` 中。

## 许可证

Private - ICCAS EPlab PMP
