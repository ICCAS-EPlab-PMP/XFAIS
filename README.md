# X-FAIS

[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-green?style=flat-square&logo=vue.js)](https://vuejs.org/)
[![Electron](https://img.shields.io/badge/Electron-35-lightgrey?style=flat-square&logo=electron)](https://www.electronjs.org/)

**本程序基于 [pyFAI](https://github.com/silx-kit/pyFAI) 和 [fabIO](https://github.com/silx-kit/fabIO) 构建**

X-FAIS (X-ray FAI (pyFAI) Scattering & Diffraction Suite) - 用于 X 射线纤维衍射数据分析和集成的桌面应用程序。

本程序基于pyFAI和FabIO两个主要项目中常见功能项进行基础构建。主要是将原本需要编程的过程改编为常用GUI界面，以节省用户学习成本，更快上手WAXS/SAXS/GIWAXS的构建。

程序由ai-agent进行全栈开发。人工进行数据测试。感谢AI-Agent 制作： opencode、 oh-my-openagent、 Reasonix

使用编程模型： GLM-5.1 / DeepSeek V4 / MiniMax 2.7 / Qwen 3.6 Plus / MiMo V2.5

## 当前功能特性

常用积分模块
- 1D 积分 (Integrate 1D)
- 方位角积分 (Integrate Azimuth)
- CAKE积分 (Integrate Cake)
- 纤维积分 (Integrate Fiber)
- H5 文件转换 (H5 Convert)
- H5 文件提取 (H5 Extract)
- PNG 图像生成 (PNG Generate)
- 校准器生成 (Calibrant Generator)
- 可视化查看器 (Viewer)

## 技术栈

- **前端**: Vue 3 + TypeScript + Vite
- **桌面框架**: Electron
- **后端**: Python 3.11
- **图表**: Plotly.js
- **国际化**: Vue I18n

## 开发环境

### 前置要求

- Node.js >= 18
- Python 3.11
- npm 或 yarn

### 安装依赖

```bash
# 安装 Node.js 依赖
npm install

# 安装 Python 依赖
pip install -r python/requirements.txt
```

### 开发模式

```bash
npm run dev
```

### 构建

```bash
# 构建应用程序
npm run build

# 打包为可执行文件
npm run build:pack
```

### 测试

```bash
# 单元测试
npm run test:unit

# E2E 测试
npm run e2e

# Python 测试
npm run test:python
```

## 项目结构

```
├── electron/          # Electron 主进程
├── src/               # Vue 前端源码
│   ├── components/    # 组件
│   ├── views/         # 页面视图
│   ├── lib/           # 工具库
│   └── router/        # 路由配置
├── python/            # Python 后端服务
│   ├── services/      # 业务服务
│   └── tests/         # 测试文件
├── deploy/            # 部署配置
└── resources/         # 构建资源
```

## 许可证

Private - ICCAS EPlab PMP
