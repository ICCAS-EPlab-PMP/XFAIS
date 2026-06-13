#!/usr/bin/env bash
# ==============================================================================
# X-FAIS Web - 用户级部署脚本
# 支持普通用户部署，无需 root 权限
# 使用方式:
#   bash deploy.sh                    # 交互式选择部署模式
#   bash deploy.sh --mode 0           # nohup 普通部署
#   bash deploy.sh --mode 1           # 用户级 systemd 长期部署
#   bash deploy.sh --port 8080        # 自定义端口
#   bash deploy.sh --uninstall        # 卸载
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 安装目录（用户级）
APP_INSTALL_DIR="${APP_INSTALL_DIR:-$HOME/xfais}"
PROJECT_ROOT="$APP_INSTALL_DIR"
DIST_DIR="$PROJECT_ROOT/dist"
PYTHON_DIR="$PROJECT_ROOT/python"
VENV_DIR="$APP_INSTALL_DIR/venv"
LOG_DIR="$APP_INSTALL_DIR/logs"
STD_LOG_FILE="$LOG_DIR/xfais.out"
PID_FILE="$LOG_DIR/xfais.pid"
SERVICE_NAME="${SERVICE_NAME:-xfais}"
USER_SYSTEMD_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
USER_UNIT_FILE="$USER_SYSTEMD_DIR/${SERVICE_NAME}.service"

# 源码目录
SOURCE_DIST_DIR="$SOURCE_ROOT/dist"
SOURCE_PYTHON_DIR="$SOURCE_ROOT/python"

# 配置
APP_HOST="${APP_HOST:-0.0.0.0}"
APP_PORT="${APP_PORT:-8765}"
DEPLOY_MODE="${DEPLOY_MODE:-}"
FORCE_REBUILD="${FORCE_REBUILD:-false}"

# ------------------------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------------------------
log() {
  printf '\n\033[0;34m━━━ %s ━━━\033[0m\n' "$1"
}

info() {
  printf '\033[0;32m[INFO]\033[0m  %s\n' "$1"
}

warn() {
  printf '\033[1;33m[WARN]\033[0m  %s\n' "$1" >&2
}

success() {
  printf '\033[0;32m✓\033[0m %s\n' "$1"
}

die() {
  printf '\033[0;31m[ERROR]\033[0m %s\n' "$1" >&2
  exit 1
}

need_file() {
  local path="$1"
  [ -e "$path" ] || die "缺少必需文件或目录: $path"
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

# ------------------------------------------------------------------------------
# 参数解析
# ------------------------------------------------------------------------------
usage() {
  cat <<EOF
用法: $(basename "$0") [选项]

选项:
  --mode MODE       部署模式: 0=nohup, 1=用户级systemd（默认: 交互选择）
  --port PORT       后端端口（默认: 8765）
  --install-dir DIR 安装目录（默认: ~/xfais）
  --force           强制重建（清除旧 dist、重建 venv、清理 __pycache__）
  --uninstall       卸载服务
  --help, -h        显示帮助信息

示例:
  bash deploy.sh                    # 交互式部署
  bash deploy.sh --mode 0           # nohup 部署
  bash deploy.sh --mode 1 --port 8080  # systemd 部署，自定义端口
  bash deploy.sh --force            # 强制重建所有产物
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      DEPLOY_MODE="$2"
      shift 2
      ;;
    --port)
      APP_PORT="$2"
      shift 2
      ;;
    --install-dir)
      APP_INSTALL_DIR="$2"
      # 重新计算路径
      PROJECT_ROOT="$APP_INSTALL_DIR"
      DIST_DIR="$PROJECT_ROOT/dist"
      PYTHON_DIR="$PROJECT_ROOT/python"
      VENV_DIR="$APP_INSTALL_DIR/venv"
      LOG_DIR="$APP_INSTALL_DIR/logs"
      STD_LOG_FILE="$LOG_DIR/xfais.out"
      PID_FILE="$LOG_DIR/xfais.pid"
      shift 2
      ;;
    --force)
      FORCE_REBUILD=true
      shift 1
      ;;
    --uninstall)
      do_uninstall
      ;;
    --help|-h)
      usage
      ;;
    *)
      die "未知选项: $1"
      ;;
  esac
done

# ------------------------------------------------------------------------------
# 卸载
# ------------------------------------------------------------------------------
do_uninstall() {
  log "卸载 X-FAIS"

  # 停止用户级 systemd 服务
  if systemctl --user is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    info "停止用户服务..."
    systemctl --user stop "$SERVICE_NAME"
    success "服务已停止"
  fi

  if systemctl --user is-enabled --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl --user disable "$SERVICE_NAME"
    success "服务已禁用"
  fi

  if [[ -f "$USER_UNIT_FILE" ]]; then
    rm -f "$USER_UNIT_FILE"
    systemctl --user daemon-reload
    success "systemd unit 文件已删除"
  fi

  # 停止 nohup 进程
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
      success "进程已停止"
    fi
    rm -f "$PID_FILE"
  fi

  # 删除安装目录
  if [[ -d "$APP_INSTALL_DIR" ]]; then
    rm -rf "$APP_INSTALL_DIR"
    success "安装目录已删除: $APP_INSTALL_DIR"
  fi

  info "卸载完成"
  exit 0
}

# ------------------------------------------------------------------------------
# 选择部署模式
# ------------------------------------------------------------------------------
prompt_deploy_mode() {
  if [[ -n "$DEPLOY_MODE" ]]; then
    case "$DEPLOY_MODE" in
      0|1) return ;;
      *) die "DEPLOY_MODE 必须是 0 或 1" ;;
    esac
  fi

  printf '\n请选择部署模式:\n'
  printf '  0 = 普通部署（nohup，关闭终端后停止）\n'
  printf '  1 = 长期部署（systemctl --user，开机自启）\n'
  printf '请输入 0 或 1: '
  read -r DEPLOY_MODE

  case "$DEPLOY_MODE" in
    0|1) ;;
    *) die "无效选择，只能是 0 或 1" ;;
  esac
}

# ------------------------------------------------------------------------------
# 前置检查
# ------------------------------------------------------------------------------
preflight_checks() {
  log "1/8 检查环境"

  # 检查非 root
  [[ "$(id -u)" -ne 0 ]] || die "请不要使用 root 或 sudo 运行此脚本"

  # 检查 Python
  has_command python3 || die "python3 不可用"
  local py_ver
  py_ver="$(python3 --version 2>&1 | awk '{print $2}')"
  success "Python: $py_ver"

  # 检查 pip
  if ! python3 -m pip --version &>/dev/null; then
    warn "pip 不可用，将尝试引导安装"
  fi

  # 检查 Node.js（仅构建时需要）
  if [[ ! -d "$SOURCE_DIST_DIR" ]]; then
    has_command node || die "node 不可用，请先安装 Node.js 18+"
    has_command npm || die "npm 不可用"
    success "Node.js: $(node --version)"
  fi

  # 检查 curl
  has_command curl || die "curl 不可用"

  # systemctl 检查（仅模式1需要）
  if [[ "$DEPLOY_MODE" == "1" ]]; then
    has_command systemctl || die "用户级部署需要 systemctl"
  fi

  success "环境检查通过"
}

# ------------------------------------------------------------------------------
# 同步源码到安装目录
# ------------------------------------------------------------------------------
sync_source() {
  log "2/8 同步源码到安装目录"

  # 如果源码目录就是安装目录，跳过
  local source_resolved target_resolved
  source_resolved="$(cd "$SOURCE_ROOT" && pwd)"
  if [[ -d "$APP_INSTALL_DIR" ]]; then
    target_resolved="$(cd "$APP_INSTALL_DIR" && pwd)"
    if [[ "$source_resolved" == "$target_resolved" ]]; then
      info "源码目录已是安装目录，跳过同步"
      return
    fi
  fi

  mkdir -p "$APP_INSTALL_DIR"

  # 强制重建时清理安装目录中的旧构建产物
  if [[ "$FORCE_REBUILD" == "true" ]]; then
    if [[ -d "$APP_INSTALL_DIR/dist" ]]; then
      chmod -R u+w "$APP_INSTALL_DIR/dist" 2>/dev/null || true
      if ! rm -rf "$APP_INSTALL_DIR/dist" 2>/dev/null; then
        die "无法删除 $APP_INSTALL_DIR/dist — 请检查文件所有权。
  可能原因：之前用 sudo 或其他用户部署过。
  修复方法：
    sudo chown -R $(id -un):$(id -gn) '$APP_INSTALL_DIR'
  然后重新运行: bash deploy.sh --force"
      fi
    fi
  fi

  # 使用 rsync 同步（排除不需要的文件）
  if has_command rsync; then
    rsync -a --delete \
      --exclude='.git' \
      --exclude='node_modules' \
      --exclude='dist-electron' \
      --exclude='dist-electron-builder' \
      --exclude='.python-runtime' \
      --exclude='.sisyphus' \
      --exclude='.omo' \
      --exclude='.gitnexus' \
      --exclude='tests' \
      --exclude='*.zip' \
      --exclude='*.tsbuildinfo' \
      --exclude='__pycache__' \
      "$SOURCE_ROOT/" "$APP_INSTALL_DIR/"
  else
    # 降级到 tar
    tar --exclude='.git' \
        --exclude='node_modules' \
        --exclude='dist-electron' \
        --exclude='dist-electron-builder' \
        --exclude='.python-runtime' \
        --exclude='tests' \
        --exclude='__pycache__' \
        -C "$SOURCE_ROOT" -cf - . | tar -C "$APP_INSTALL_DIR" -xf -
  fi

  success "源码已同步到 $APP_INSTALL_DIR"
}

# ------------------------------------------------------------------------------
# 构建前端
# ------------------------------------------------------------------------------
build_frontend() {
  log "3/8 构建前端"

  if [[ "$FORCE_REBUILD" == "true" ]] && [[ -d "$SOURCE_DIST_DIR" ]]; then
    chmod -R u+w "$SOURCE_DIST_DIR" 2>/dev/null || true
    rm -rf "$SOURCE_DIST_DIR" 2>/dev/null || warn "无法删除 $SOURCE_DIST_DIR，尝试覆盖构建"
  fi

  # 如果已有构建产物，跳过
  if [[ -d "$SOURCE_DIST_DIR" ]] && [[ -f "$SOURCE_DIST_DIR/index.html" ]]; then
    info "检测到已有构建产物，跳过构建"
    return
  fi

  cd "$SOURCE_ROOT"
  
  if [[ -f package-lock.json ]]; then
    info "使用 npm ci..."
    npm ci --no-audit 2>/dev/null || npm install --no-audit
  else
    info "使用 npm install..."
    npm install --no-audit
  fi

  info "执行 npm run build:web..."
  npm run build:web
  success "前端构建完成"
}

# ------------------------------------------------------------------------------
# 创建虚拟环境并安装依赖
# ------------------------------------------------------------------------------
setup_python_env() {
  log "4/8 配置 Python 环境"

  local PYTHON_CMD
  PYTHON_CMD="$(command -v python3)"
  info "Python 路径: $PYTHON_CMD"

  # 删除可能损坏的 venv
  if [[ -d "$VENV_DIR" ]] && [[ ! -f "$VENV_DIR/bin/python" ]]; then
    warn "检测到损坏的虚拟环境，删除重建..."
    rm -rf "$VENV_DIR"
  fi

  # 强制重建时删除旧 venv
  if [[ "$FORCE_REBUILD" == "true" ]] && [[ -d "$VENV_DIR" ]]; then
    chmod -R u+w "$VENV_DIR" 2>/dev/null || true
    if ! rm -rf "$VENV_DIR" 2>/dev/null; then
      die "无法删除 $VENV_DIR — 请检查文件所有权。
  修复方法:
    sudo chown -R $(id -un):$(id -gn) '$APP_INSTALL_DIR'
  然后重新运行: bash deploy.sh --force"
    fi
  fi

  # 强制重建时清理 __pycache__
  if [[ "$FORCE_REBUILD" == "true" ]] && [[ -d "$PYTHON_DIR" ]]; then
    info "强制重建：清理 __pycache__ ..."
    find "$PYTHON_DIR" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
  fi

  # 创建虚拟环境
  if [[ ! -d "$VENV_DIR" ]]; then
    info "创建虚拟环境..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"

    # 验证 venv 创建成功
    if [[ ! -f "$VENV_DIR/bin/python" ]]; then
      warn "venv 创建失败，尝试诊断..."
      echo ""
      echo "可能原因："
      echo "  1. 缺少 venv 模块，尝试安装: sudo dnf install python3-venv (或 apt install python3-venv)"
      echo "  2. Python 是软链接但目标不存在"
      echo ""
      echo "诊断信息:"
      ls -la "$PYTHON_CMD"
      "$PYTHON_CMD" -c "import sys; print(sys.executable); print(sys.prefix)"
      echo ""

      # 尝试备用方案：使用 --without-pip 然后手动引导
      info "尝试备用方案: --without-pip..."
      "$PYTHON_CMD" -m venv --without-pip "$VENV_DIR"

      if [[ ! -f "$VENV_DIR/bin/python" ]]; then
        die "虚拟环境创建失败，请检查 Python 安装"
      fi

      info "使用 get-pip.py 引导 pip..."
      curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
      "$VENV_DIR/bin/python" /tmp/get-pip.py
      rm -f /tmp/get-pip.py
    fi
  fi

  # 验证 venv 可用
  if [[ ! -f "$VENV_DIR/bin/python" ]]; then
    die "虚拟环境不完整: $VENV_DIR/bin/python 不存在"
  fi

  success "虚拟环境就绪: $VENV_DIR"

  # 确保 pip 可用
  if ! "$VENV_DIR/bin/python" -m pip --version &>/dev/null; then
    info "引导安装 pip..."
    curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
    "$VENV_DIR/bin/python" /tmp/get-pip.py
    rm -f /tmp/get-pip.py
  fi

  # 升级 pip
  "$VENV_DIR/bin/python" -m pip install --upgrade pip -q

  # 检查 Python 版本，选择依赖安装策略
  local py_major py_minor
  py_major="$("$VENV_DIR/bin/python" -c 'import sys; print(sys.version_info.major)')"
  py_minor="$("$VENV_DIR/bin/python" -c 'import sys; print(sys.version_info.minor)')"
  info "venv Python 版本: $py_major.$py_minor"

  local requirements_lock="$PROJECT_ROOT/python/requirements.lock.txt"
  local requirements_min="$PROJECT_ROOT/python/requirements.in"

  if [[ "$py_major" -ge 3 && "$py_minor" -ge 10 ]]; then
    # Python >= 3.10: 安装完整锁定依赖
    info "Python $py_major.$py_minor >= 3.10，安装完整依赖..."
    if [[ -f "$requirements_lock" ]]; then
      "$VENV_DIR/bin/pip" install -r "$requirements_lock" -q
    else
      "$VENV_DIR/bin/pip" install -r "$requirements_min" -q
    fi
  else
    # Python < 3.10: 只安装核心依赖（altair/streamlit/pandas>=3.0 需要 3.10+）
    info "Python $py_major.$py_minor < 3.10，安装核心依赖..."
    if [[ -f "$requirements_min" ]]; then
      "$VENV_DIR/bin/pip" install -r "$requirements_min" -q
    else
      "$VENV_DIR/bin/pip" install pyfai numpy scipy fabio h5py Pillow pandas -q
    fi
  fi

  success "Python 环境配置完成"
}

# ------------------------------------------------------------------------------
# 创建启动/停止脚本
# ------------------------------------------------------------------------------
create_scripts() {
  log "5/8 创建管理脚本"

  mkdir -p "$LOG_DIR"

  # 启动脚本
  cat > "$APP_INSTALL_DIR/start.sh" <<'START_EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 停止旧进程
if [[ -f xfais.pid ]]; then
    old_pid=$(cat xfais.pid)
    if kill -0 "$old_pid" 2>/dev/null; then
        kill "$old_pid"
        sleep 2
    fi
    rm -f xfais.pid
fi

# 启动服务
echo "Starting X-FAIS Web Service..."
nohup venv/bin/python python/service_launcher.py serve_web --port PORT_PLACEHOLDER > logs/xfais.out 2>&1 &
echo $! > xfais.pid
echo "X-FAIS started with PID: $(cat xfais.pid)"
echo "Log file: $SCRIPT_DIR/logs/xfais.out"
START_EOF

  # 停止脚本
  cat > "$APP_INSTALL_DIR/stop.sh" <<'STOP_EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f xfais.pid ]]; then
    pid=$(cat xfais.pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "Stopping X-FAIS (PID: $pid)..."
        kill "$pid"
        echo "Stopped."
    else
        echo "Process $pid not running."
    fi
    rm -f xfais.pid
else
    echo "No PID file found. X-FAIS may not be running."
fi
STOP_EOF

  # 状态检查脚本
  cat > "$APP_INSTALL_DIR/status.sh" <<'STATUS_EOF'
#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== X-FAIS Service Status ==="

if [[ -f xfais.pid ]]; then
    pid=$(cat xfais.pid)
    if kill -0 "$pid" 2>/dev/null; then
        echo "Status: RUNNING (PID: $pid)"
    else
        echo "Status: STOPPED (stale PID file)"
    fi
else
    echo "Status: STOPPED"
fi

echo ""
echo "Health check:"
curl -sf http://localhost:PORT_PLACEHOLDER/health 2>/dev/null && echo "" || echo "FAILED"
STATUS_EOF

  # 替换端口
  sed -i "s/PORT_PLACEHOLDER/$APP_PORT/g" "$APP_INSTALL_DIR/start.sh"
  sed -i "s/PORT_PLACEHOLDER/$APP_PORT/g" "$APP_INSTALL_DIR/status.sh"
  
  chmod +x "$APP_INSTALL_DIR/start.sh" "$APP_INSTALL_DIR/stop.sh" "$APP_INSTALL_DIR/status.sh"

  success "管理脚本已创建"
}

# ------------------------------------------------------------------------------
# 启动 nohup 模式
# ------------------------------------------------------------------------------
start_nohup() {
  log "6/8 启动服务 (nohup)"

  cd "$APP_INSTALL_DIR"
  bash start.sh
  sleep 3

  # 检查进程
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      success "服务已启动 (PID: $pid)"
    else
      die "服务启动失败，请查看日志: $STD_LOG_FILE"
    fi
  fi
}

# ------------------------------------------------------------------------------
# 安装用户级 systemd 服务
# ------------------------------------------------------------------------------
install_user_systemd() {
  log "6/8 安装用户级 systemd 服务"

  mkdir -p "$USER_SYSTEMD_DIR"

  cat > "$USER_UNIT_FILE" <<EOF
[Unit]
Description=X-FAIS Web Service (User)
After=default.target

[Service]
Type=simple
WorkingDirectory=$APP_INSTALL_DIR
ExecStart=$VENV_DIR/bin/python $PYTHON_DIR/service_launcher.py serve_web --port $APP_PORT
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF

  systemctl --user daemon-reload
  systemctl --user enable "$SERVICE_NAME"
  systemctl --user restart "$SERVICE_NAME"

  sleep 3

  if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    success "用户服务已启动"
    info "如需终端退出后继续运行，执行: loginctl enable-linger $USER"
  else
    die "服务启动失败，执行: journalctl --user -u $SERVICE_NAME -n 50"
  fi
}

# ------------------------------------------------------------------------------
# 健康检查
# ------------------------------------------------------------------------------
health_check() {
  log "7/8 健康检查"

  local url="http://localhost:$APP_PORT/health"
  local attempt
  local max_attempts=10

  info "等待服务启动..."
  for attempt in $(seq 1 $max_attempts); do
    if curl -sf "$url" >/dev/null 2>&1; then
      success "健康检查通过"
      return
    fi
    sleep 2
  done

  # 失败诊断
  warn "健康检查未通过"
  printf '\n诊断信息:\n'
  printf '  安装目录: %s\n' "$APP_INSTALL_DIR"
  printf '  健康检查: %s\n' "$url"

  if [[ "$DEPLOY_MODE" == "1" ]]; then
    printf '  用户服务: %s\n' "$SERVICE_NAME"
    systemctl --user status "$SERVICE_NAME" --no-pager 2>/dev/null || true
    journalctl --user -u "$SERVICE_NAME" -n 30 --no-pager 2>/dev/null || true
  else
    printf '  PID 文件: %s\n' "$PID_FILE"
    if [[ -f "$STD_LOG_FILE" ]]; then
      printf '  最近日志:\n'
      tail -n 30 "$STD_LOG_FILE"
    fi
  fi

  die "健康检查失败"
}

# ------------------------------------------------------------------------------
# 打印摘要
# ------------------------------------------------------------------------------
print_summary() {
  log "8/8 部署完成"

  local server_ip
  server_ip="$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")"

  printf '\n'
  printf '  \033[0;32m✓ X-FAIS Web 已成功部署!\033[0m\n'
  printf '\n'
  printf '  模式:       %s\n' "$( [[ "$DEPLOY_MODE" == "1" ]] && echo '用户级systemd' || echo 'nohup' )"
  printf '  访问地址:   http://%s:%s/\n' "$server_ip" "$APP_PORT"
  printf '  健康检查:   http://%s:%s/health\n' "$server_ip" "$APP_PORT"
  printf '  安装目录:   %s\n' "$APP_INSTALL_DIR"
  printf '\n'
  printf '  \033[1;33m常用命令:\033[0m\n'

  if [[ "$DEPLOY_MODE" == "1" ]]; then
    printf '    查看状态:  systemctl --user status %s\n' "$SERVICE_NAME"
    printf '    查看日志:  journalctl --user -u %s -f\n' "$SERVICE_NAME"
    printf '    重启服务:  systemctl --user restart %s\n' "$SERVICE_NAME"
    printf '    停止服务:  systemctl --user stop %s\n' "$SERVICE_NAME"
    printf '\n'
    printf '  \033[1;33m提示:\033[0m 如需退出终端后服务继续运行，执行:\n'
    printf '    loginctl enable-linger %s\n' "$USER"
  else
    printf '    启动服务:  bash %s/start.sh\n' "$APP_INSTALL_DIR"
    printf '    停止服务:  bash %s/stop.sh\n' "$APP_INSTALL_DIR"
    printf '    查看状态:  bash %s/status.sh\n' "$APP_INSTALL_DIR"
    printf '    查看日志:  tail -f %s\n' "$STD_LOG_FILE"
  fi

  printf '\n'
  printf '  \033[1;33m卸载:\033[0m\n'
  printf '    bash %s/deploy.sh --uninstall\n' "$SCRIPT_DIR"
  printf '\n'
}

# ==============================================================================
# 主流程
# ==============================================================================
main() {
  [[ "$(uname -s)" == "Linux" ]] || die "该脚本仅支持 Linux"

  prompt_deploy_mode
  preflight_checks
  sync_source
  build_frontend
  setup_python_env
  create_scripts

  if [[ "$DEPLOY_MODE" == "1" ]]; then
    install_user_systemd
  else
    start_nohup
  fi

  health_check
  print_summary
}

main
