# X-FAIS

[![GitHub stars](https://img.shields.io/github/stars/ICCAS-EPlab-PMP/XFAIS?style=flat-square)](https://github.com/ICCAS-EPlab-PMP/XFAIS/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/ICCAS-EPlab-PMP/XFAIS?style=flat-square)](https://github.com/ICCAS-EPlab-PMP/XFAIS/network/members)
[![GitHub issues](https://img.shields.io/github/issues/ICCAS-EPlab-PMP/XFAIS?style=flat-square)](https://github.com/ICCAS-EPlab-PMP/XFAIS/issues)
[![GitHub license](https://img.shields.io/github/license/ICCAS-EPlab-PMP/XFAIS?style=flat-square)](https://github.com/ICCAS-EPlab-PMP/XFAIS/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-green?style=flat-square&logo=vue.js)](https://vuejs.org/)
[![Electron](https://img.shields.io/badge/Electron-35-lightgrey?style=flat-square&logo=electron)](https://www.electronjs.org/)

**基于 [pyFAI](https://github.com/silx-kit/pyFAI) 和 [fabIO](https://github.com/silx-kit/fabIO) 构建**

X-FAIS (X-ray Fiber Analysis and Integration Software) - 用于 X 射线纤维衍射数据分析和集成的桌面应用程序。

## 功能特性

- 1D 积分 (Integrate 1D)
- 方位角积分 (Integrate Azimuth)
- 蛋糕形积分 (Integrate Cake)
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
