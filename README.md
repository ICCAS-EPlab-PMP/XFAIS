# X-FAIS

[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-green?style=flat-square&logo=vue.js)](https://vuejs.org/)
[![Electron](https://img.shields.io/badge/Electron-35-lightgrey?style=flat-square&logo=electron)](https://www.electronjs.org/)
[![English](https://img.shields.io/badge/📖-English-009688?style=flat-square)](./README_EN.md)

**基于 [pyFAI](https://github.com/silx-kit/pyFAI) 和 [fabIO](https://github.com/silx-kit/fabIO) 内核构建的专业 X 射线数据分析 GUI**

X-FAIS (X-ray FAI Scattering & Diffraction Suite) — 一款专为 X 射线散射/衍射数据分析打造的桌面与 Web 应用程序。项目深度整合 **pyFAI** 积分引擎和 **fabIO** 图像读写库，将原本需要编程的数据处理流程转化为直观的图形界面操作。

**核心定位**：部署于服务器供团队共享，或本地自用的专业分析工具。

**开发模式**：AI 全栈开发（前端 + 后端 + 部署脚本均由 AI Agent 完成），人工进行数据验证与测试。

---

## 核心特性

### 基于 pyFAI 内核的积分分析

- **1D 径向积分** — 将 2D 衍射图转换为强度随 q 或 2θ 变化的曲线
- **方位角 χ 积分** — 分析强度随方位角的分布
- **CAKE 扇区积分** — 对 Debye-Scherrer 环的指定扇区做径向积分
- **GIWAXS 纤维积分** — 生成 q_ip × q_oop 二维强度图

### 基于 fabIO 的图像与数据工具

- **图像查看器** — 浏览衍射图像，支持帧导航、对比度调节、PNG 导出
- **H5 格式转换** — HDF5 文件批量转换为 TIFF 或 CSV
- **H5 数据提取** — 从 HDF5 文件中提取指定数据集
- **批量 PNG 生成** — 批量生成衍射图像的 PNG 预览

### 掩膜绘制工具 (Mask Drawer)

- **可视化掩膜编辑** — 在图像上直接绘制矩形、圆形、椭圆、多边形、线条等掩膜区域
- **阈值遮盖** — 支持按值范围（高于/低于/区间）自动创建掩膜
- **掩膜管理** — 加载/保存/合并/擦除掩膜，支持 .npy、.tif、.edf 等格式
- **与 pyFAI 集成** — 生成的掩膜可直接用于积分计算，屏蔽坏像素和无效区域

### 辅助功能

- **标样生成器** — 从 CIF 文件或晶胞参数计算理论衍射峰位
- **晶胞标样生成器** — 基于空间群和晶胞参数的完整标样计算
- **pyFAI 标定检查** — 检查 pyFAI-calib2 的安装状态并可导出启动脚本

**导出格式**：TXT / CSV / HDF5 / XY

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                     X-FAIS 架构                              │
├─────────────────────────────────────────────────────────────┤
│  前端层 (Vue 3 + TypeScript + Vite)                          │
│  ├── 图形界面：表单、图表、可视化                              │
│  ├── 掩膜编辑器：Canvas 交互绘制                              │
│  └── 国际化：中/英文支持                                      │
├─────────────────────────────────────────────────────────────┤
│  桌面层 (Electron 35)                                        │
│  ├── 进程管理：内嵌 Python 运行时                              │
│  ├── 文件对话框：本地文件访问                                  │
│  └── 系统集成：托盘、快捷键                                   │
├─────────────────────────────────────────────────────────────┤
│  后端层 (Python 3.11 + WebSocket)                            │
│  ├── pyFAI：积分计算核心引擎                                  │
│  ├── fabIO：EDF/TIFF/CBF 等格式图像读写                       │
│  ├── h5py：HDF5 数据访问                                      │
│  └── silx：掩膜几何形状绘制                                   │
└─────────────────────────────────────────────────────────────┘
```

**核心依赖**：pyFAI（积分计算）、fabio（图像读写）、h5py（HDF5 访问）、silx（掩膜形状）、numpy、scipy、matplotlib

**技术栈**：Vue 3 + TypeScript + Vite | Electron 35 | Python 3.11 | Plotly.js | Vue I18n

---

## 部署方案

### 方案一：本地桌面应用（Electron）

适用于个人工作站，开箱即用，无需配置 Python 环境。

**支持平台**：

| 平台 | 状态 | 安装包格式 |
|------|------|-----------|
| Windows x64 | 已发布 | NSIS 安装包 |
| macOS (Intel / Apple Silicon) | 代码就绪，待构建 | DMG |

**Windows 安装**：
1. 下载 `X-FAIS-{version}-setup-x64.exe`
2. 双击运行，选择安装路径，等待安装完成
3. 从开始菜单或桌面快捷方式启动

**macOS 安装**（需自行构建，见下方"开发与构建"章节）：
1. 下载 `X-FAIS-{version}-{arch}.dmg`（arch 为 x64 或 arm64）
2. 双击 DMG 文件，将 X-FAIS 拖入"应用程序"文件夹
3. 首次打开时，在"系统设置 > 隐私与安全性"中允许运行

### 方案二：Linux 服务器部署（Web 版）

适用于团队共享场景，部署后通过浏览器访问，支持多用户数据隔离。

**环境要求**：Linux 服务器（Ubuntu 20.04+ / CentOS 7+ / Rocky Linux）、Python 3.8+、Node.js 18+（仅构建时）

**快速部署**：

```bash
# 上传项目文件到服务器
scp -r MAIN/ user@server:~/xfais-source/

# SSH 到服务器
ssh user@server

# 进入部署目录并执行
cd ~/xfais-source/deploy
bash deploy.sh
```

部署脚本会自动：同步源码 → 构建前端 → 创建 Python 虚拟环境 → 启动服务

**部署模式**：
- **模式 0**（nohup）：临时测试，关闭终端后停止
- **模式 1**（systemd --user）：长期运行，开机自启

**命令行参数**：

```bash
bash deploy.sh --mode 1           # 用户级 systemd 长期部署
bash deploy.sh --port 8080        # 自定义端口
bash deploy.sh --install-dir /data/xfais  # 自定义安装目录
bash deploy.sh --uninstall        # 卸载
```

**访问地址**：

| 地址 | 说明 |
|------|------|
| `http://服务器IP:8765/` | Web 前端 |
| `http://服务器IP:8765/health` | 健康检查 |

**Nginx 反向代理**（可选，通过 80 端口访问）：

```nginx
server {
    listen 80;
    server_name _;
    root /home/user/xfais/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
    location /ws {
        proxy_pass http://127.0.0.1:8765;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    location /api/ {
        proxy_pass http://127.0.0.1:8765;
        client_max_body_size 500M;
    }
}
```

**远程部署**（本地构建 + 推送到服务器）：

```bash
bash deploy/deploy-remote.sh --host user@server --port 8765
```

> 更多部署细节请参考 [`deploy/README.md`](./deploy/README.md)

---

## 开发与构建

### 前置要求

- Node.js >= 18
- npm >= 9
- Python 3.11.9（Windows 下会自动下载安装；macOS/Linux 需手动准备运行时）

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
npm run build:pack          # Windows 完整打包（构建 + electron-builder）
npm run build:pack:mac      # macOS 完整打包（需在 macOS 上执行）
npm run build:web           # 构建纯 Web 版本（无 Electron，用于服务器部署）
npm run lint                # ESLint 代码检查
npm run typecheck           # TypeScript 类型检查
npm run test:unit           # 运行单元测试（Vitest）
npm run e2e                 # 端到端测试（Playwright）
npm run test:python         # Python 后端测试
npm run python:health       # 检查 Python 运行时健康状态
```

### 构建发布

**Windows**：

```bash
npm install
npm run build:pack
```

产物位于 `dist-electron-builder/`：`X-FAIS-{version}-setup-x64.exe`

**macOS**（必须在 macOS 机器上执行）：

```bash
# 第一步：准备 Python 运行时（从 python-build-standalone 下载）
# Apple Silicon: .python-runtime/python-3.11.9-macos-arm64/
# Intel Mac: .python-runtime/python-3.11.9-macos-x64/

# 第二步：安装依赖
.python-runtime/python-3.11.9-macos-*/bin/python3 -m pip install -r python/requirements.in

# 第三步：构建
npm install
npm run build:pack:mac
```

---

## 项目结构

```
├── electron/                  # Electron 主进程源码
│   ├── main.ts               # 主进程入口
│   ├── preload.ts            # 预加载脚本
│   └── python/
│       ├── manager.ts        # Python 服务进程管理
│       └── runtime.ts        # Python 运行时检测与安装（跨平台）
├── src/                       # Vue 前端源码
│   ├── views/workspace/       # 各功能工作区页面
│   ├── components/business/   # 业务组件（表单、图表控件等）
│   ├── components/charts/     # 图表组件（Plotly / 折线图 / 热力图）
│   └── i18n/                  # 国际化
├── python/                    # Python 后端
│   ├── service_launcher.py   # 服务入口（HTTP + WebSocket）
│   ├── services/
│   │   ├── integrator.py     # 积分服务（pyFAI 封装）
│   │   ├── mask_builder.py   # 掩膜构建服务（形状绘制 + 阈值遮盖）
│   │   └── ...               # 其他业务服务
│   └── requirements.in       # Python 依赖声明
├── deploy/                    # Linux 部署脚本与配置
│   ├── deploy.sh             # 本地部署脚本
│   ├── deploy-remote.sh      # 远程部署脚本
│   └── nginx.conf            # Nginx 配置示例
└── package.json               # 项目配置与 electron-builder 配置
```

---

## Python 依赖

内嵌的 Python 运行时包含以下核心库：

- **pyFAI** — X 射线积分计算引擎
- **fabio** — EDF/TIFF/CBF 等衍射图像格式读写
- **h5py** — HDF5 数据访问
- **silx** — 掩膜几何形状绘制（circle_fill、ellipse_fill、polygon_fill_mask）
- **numpy / scipy / matplotlib** — 数值计算与可视化
- **pandas / tifffile / Pillow / psutil / websockets** — 数据处理与通信

完整的依赖版本锁定在 `python/requirements.lock.txt` 中。

---

## 致谢

- **核心引擎**：[pyFAI](https://github.com/silx-kit/pyFAI)、[fabIO](https://github.com/silx-kit/fabIO)、[silx](https://github.com/silx-kit/silx)
- **AI 开发工具**：OpenCode、Oh-My-OpenAgent、Reasonix
- **编程模型**：GLM-5.1 / DeepSeek V4 / MiniMax 2.7 / Qwen 3.6 Plus / MiMo V2.5

---

## 许可证

Private - ICCAS EPlab PMP
