# X-FAIS

[![Python](https://img.shields.io/badge/Python-3.11-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Vue.js](https://img.shields.io/badge/Vue.js-3-green?style=flat-square&logo=vue.js)](https://vuejs.org/)
[![Electron](https://img.shields.io/badge/Electron-35-lightgrey?style=flat-square&logo=electron)](https://www.electronjs.org/)
[![中文](https://img.shields.io/badge/📖-中文-f44336?style=flat-square)](./README.md)

**Professional X-ray Data Analysis GUI built on [pyFAI](https://github.com/silx-kit/pyFAI) and [fabIO](https://github.com/silx-kit/fabIO) kernels**

X-FAIS (X-ray FAI Scattering & Diffraction Suite) — A desktop and web application designed for X-ray scattering/diffraction data analysis. The project deeply integrates the **pyFAI** integration engine and **fabIO** image I/O library, transforming programming-based data processing workflows into intuitive graphical interface operations.

**Core Purpose**: Deploy on servers for team sharing, or use locally as a professional analysis tool.

**Development Model**: Full-stack AI development (frontend + backend + deployment scripts all completed by AI Agent), with manual data validation and testing.

---

## Core Features

### Integration Analysis (pyFAI Kernel)

- **1D Radial Integration** — Convert 2D diffraction patterns to intensity vs. q or 2θ curves
- **Azimuthal χ Integration** — Analyze intensity distribution along azimuthal angle
- **CAKE Sector Integration** — Radial integration of specified sectors in Debye-Scherrer rings
- **GIWAXS Fiber Integration** — Generate q_ip × q_oop 2D intensity maps

### Image & Data Tools (fabIO Kernel)

- **Image Viewer** — Browse diffraction images with frame navigation, contrast adjustment, PNG export
- **H5 Format Conversion** — Batch convert HDF5 files to TIFF or CSV
- **H5 Data Extraction** — Extract specified datasets from HDF5 files
- **Batch PNG Generation** — Batch generate PNG previews of diffraction images

### Mask Drawer

- **Visual Mask Editing** — Draw rectangles, circles, ellipses, polygons, and lines directly on images
- **Threshold Masking** — Auto-create masks by value range (above/below/between)
- **Mask Management** — Load/save/merge/erase masks in .npy, .tif, .edf formats
- **pyFAI Integration** — Generated masks can be directly used in integration calculations to mask bad pixels and invalid regions

### Auxiliary Tools

- **Calibrant Generator** — Calculate theoretical diffraction peak positions from CIF files or unit cell parameters
- **Unit Cell Calibrant Generator** — Complete calibrant calculation based on space group and unit cell parameters
- **pyFAI Calibration Check** — Check pyFAI-calib2 installation status and export startup scripts

**Export Formats**: TXT / CSV / HDF5 / XY

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     X-FAIS Architecture                      │
├─────────────────────────────────────────────────────────────┤
│  Frontend Layer (Vue 3 + TypeScript + Vite)                  │
│  ├── GUI: Forms, Charts, Visualization                       │
│  ├── Mask Editor: Canvas Interactive Drawing                 │
│  └── Internationalization: Chinese/English Support           │
├─────────────────────────────────────────────────────────────┤
│  Desktop Layer (Electron 35)                                 │
│  ├── Process Management: Embedded Python Runtime             │
│  ├── File Dialogs: Local File Access                         │
│  └── System Integration: Tray, Shortcuts                     │
├─────────────────────────────────────────────────────────────┤
│  Backend Layer (Python 3.11 + WebSocket)                     │
│  ├── pyFAI: Integration Calculation Core Engine              │
│  ├── fabIO: EDF/TIFF/CBF Image I/O                          │
│  ├── h5py: HDF5 Data Access                                 │
│  └── silx: Mask Geometry Shape Drawing                       │
└─────────────────────────────────────────────────────────────┘
```

**Core Dependencies**: pyFAI (integration), fabio (image I/O), h5py (HDF5 access), silx (mask shapes), numpy, scipy, matplotlib

**Tech Stack**: Vue 3 + TypeScript + Vite | Electron 35 | Python 3.11 | Plotly.js | Vue I18n

---

## Deployment Options

### Option 1: Local Desktop Application (Electron)

For individual workstations, ready to use out of the box with no Python environment configuration required.

**Supported Platforms**:

| Platform | Status | Package Format |
|----------|--------|----------------|
| Windows x64 | Released | NSIS Installer |
| macOS (Intel / Apple Silicon) | Code ready, pending build | DMG |

**Windows Installation**:
1. Download `X-FAIS-{version}-setup-x64.exe`
2. Double-click to run, select installation path, wait for completion
3. Launch from Start Menu or desktop shortcut

**macOS Installation** (requires self-building, see "Development & Build" section below):
1. Download `X-FAIS-{version}-{arch}.dmg` (arch: x64 or arm64)
2. Double-click DMG file, drag X-FAIS to "Applications" folder
3. On first launch, allow in "System Settings > Privacy & Security"

### Option 2: Linux Server Deployment (Web Version)

For team sharing scenarios, accessible via browser after deployment with multi-user data isolation.

**Requirements**: Linux server (Ubuntu 20.04+ / CentOS 7+ / Rocky Linux), Python 3.8+, Node.js 18+ (build time only)

**Quick Deployment**:

```bash
# Upload project files to server
scp -r MAIN/ user@server:~/xfais-source/

# SSH to server
ssh user@server

# Enter deploy directory and execute
cd ~/xfais-source/deploy
bash deploy.sh
```

The deploy script automatically: syncs source → builds frontend → creates Python virtual environment → starts service

**Deployment Modes**:
- **Mode 0** (nohup): Temporary testing, stops when terminal closes
- **Mode 1** (systemd --user): Long-running, auto-start on boot

**Command Line Arguments**:

```bash
bash deploy.sh --mode 1           # User-level systemd long-term deployment
bash deploy.sh --port 8080        # Custom port
bash deploy.sh --install-dir /data/xfais  # Custom installation directory
bash deploy.sh --uninstall        # Uninstall
```

**Access Addresses**:

| Address | Description |
|---------|-------------|
| `http://server-ip:8765/` | Web Frontend |
| `http://server-ip:8765/health` | Health Check |

**Nginx Reverse Proxy** (optional, access via port 80):

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

**Remote Deployment** (local build + push to server):

```bash
bash deploy/deploy-remote.sh --host user@server --port 8765
```

> For more deployment details, refer to [`deploy/README.md`](./deploy/README.md)

---

## Development & Build

### Prerequisites

- Node.js >= 18
- npm >= 9
- Python 3.11.9 (auto-downloaded on Windows; manual preparation required on macOS/Linux)

### Quick Start

```bash
# Install Node.js dependencies
npm install

# Start development mode (hot reload + Electron window)
npm run dev
```

Development mode simultaneously starts Vite dev server (`http://127.0.0.1:5173`) and Electron window, with Python backend auto-starting.

### Common Commands

```bash
npm run dev                 # Development mode
npm run build               # Build only (frontend + Electron main process), no packaging
npm run build:pack          # Windows full package (build + electron-builder)
npm run build:pack:mac      # macOS full package (must run on macOS)
npm run build:web           # Build pure Web version (no Electron, for server deployment)
npm run lint                # ESLint code check
npm run typecheck           # TypeScript type check
npm run test:unit           # Run unit tests (Vitest)
npm run e2e                 # End-to-end tests (Playwright)
npm run test:python         # Python backend tests
npm run python:health       # Check Python runtime health
```

### Build & Release

**Windows**:

```bash
npm install
npm run build:pack
```

Artifacts in `dist-electron-builder/`: `X-FAIS-{version}-setup-x64.exe`

**macOS** (must execute on macOS machine):

```bash
# Step 1: Prepare Python runtime (download from python-build-standalone)
# Apple Silicon: .python-runtime/python-3.11.9-macos-arm64/
# Intel Mac: .python-runtime/python-3.11.9-macos-x64/

# Step 2: Install dependencies
.python-runtime/python-3.11.9-macos-*/bin/python3 -m pip install -r python/requirements.in

# Step 3: Build
npm install
npm run build:pack:mac
```

---

## Project Structure

```
├── electron/                  # Electron main process source
│   ├── main.ts               # Main process entry
│   ├── preload.ts            # Preload script
│   └── python/
│       ├── manager.ts        # Python service process management
│       └── runtime.ts        # Python runtime detection & installation (cross-platform)
├── src/                       # Vue frontend source
│   ├── views/workspace/       # Feature workspace pages
│   ├── components/business/   # Business components (forms, chart controls, etc.)
│   ├── components/charts/     # Chart components (Plotly / line / heatmap)
│   └── i18n/                  # Internationalization
├── python/                    # Python backend
│   ├── service_launcher.py   # Service entry (HTTP + WebSocket)
│   ├── services/
│   │   ├── integrator.py     # Integration service (pyFAI wrapper)
│   │   ├── mask_builder.py   # Mask building service (shape drawing + threshold masking)
│   │   └── ...               # Other business services
│   └── requirements.in       # Python dependency declaration
├── deploy/                    # Linux deployment scripts & config
│   ├── deploy.sh             # Local deployment script
│   ├── deploy-remote.sh      # Remote deployment script
│   └── nginx.conf            # Nginx configuration example
└── package.json               # Project config & electron-builder config
```

---

## Python Dependencies

The embedded Python runtime includes the following core libraries:

- **pyFAI** — X-ray integration calculation engine
- **fabio** — EDF/TIFF/CBF diffraction image format I/O
- **h5py** — HDF5 data access
- **silx** — Mask geometry shape drawing (circle_fill, ellipse_fill, polygon_fill_mask)
- **numpy / scipy / matplotlib** — Numerical computation & visualization
- **pandas / tifffile / Pillow / psutil / websockets** — Data processing & communication

Complete dependency versions are locked in `python/requirements.lock.txt`.

---

## Acknowledgements

- **Core Engines**: [pyFAI](https://github.com/silx-kit/pyFAI), [fabIO](https://github.com/silx-kit/fabIO), [silx](https://github.com/silx-kit/silx)
- **AI Development Tools**: OpenCode, Oh-My-OpenAgent, Reasonix
- **Programming Models**: GLM-5.1 / DeepSeek V4 / MiniMax 2.7 / Qwen 3.6 Plus / MiMo V2.5

---

## License

Private - ICCAS EPlab PMP
