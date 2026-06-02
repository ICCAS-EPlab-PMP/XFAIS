#!/usr/bin/env bash
# ==============================================================================
# X-FAIS Web - 本地构建 + 远程部署脚本
# 在本地开发机（WSL / macOS / Linux）运行，自动构建并推送到远程服务器部署
# 使用方式:
#   bash deploy-remote.sh --host user@server
#   bash deploy-remote.sh --host user@server --port 8765
#   bash deploy-remote.sh --host user@server --remote-dir /opt/xfais
# ==============================================================================
set -euo pipefail

# ------------------------------------------------------------------------------
# 颜色定义
# ------------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }
header()  { echo -e "\n${BLUE}━━━ $* ━━━${NC}"; }
success() { echo -e "${GREEN}✓${NC} $*"; }

# ------------------------------------------------------------------------------
# 默认值
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"   # BETA/
REMOTE_DIR="/opt/xfais"
HTTP_PORT=8765
HOST=""

# ------------------------------------------------------------------------------
# 参数解析
# ------------------------------------------------------------------------------
usage() {
    cat <<EOF
用法: $(basename "$0") --host user@server [选项]

必需:
  --host HOST       SSH 远程主机地址（如: root@192.168.1.100）

选项:
  --port PORT       后端 HTTP 端口（默认: 8765）
  --remote-dir DIR  远程服务器安装目录（默认: /opt/xfais）
  --help, -h        显示帮助信息
EOF
    exit 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            HTTP_PORT="$2"
            shift 2
            ;;
        --remote-dir)
            REMOTE_DIR="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            error "未知选项: $1"
            usage
            ;;
    esac
done

# ------------------------------------------------------------------------------
# 前置验证
# ------------------------------------------------------------------------------
preflight_check() {
    header "前置检查"

    local has_error=false

    # 检查必需参数
    if [[ -z "$HOST" ]]; then
        error "必须指定 --host（如: --host root@192.168.1.100）"
        has_error=true
    else
        success "远程主机: $HOST"
    fi

    # 检查本地工具
    if command -v rsync &>/dev/null; then
        success "rsync: $(rsync --version 2>&1 | head -1)"
    else
        error "未找到 rsync，请先安装"
        has_error=true
    fi

    if command -v ssh &>/dev/null; then
        success "ssh: $(ssh -V 2>&1)"
    else
        error "未找到 ssh，请先安装"
        has_error=true
    fi

    if command -v node &>/dev/null; then
        local node_ver
        node_ver="$(node --version 2>&1 | sed 's/^v//')"
        local node_major
        node_major="$(echo "$node_ver" | cut -d. -f1)"
        if [[ "$node_major" -ge 18 ]]; then
            success "Node.js: v$node_ver"
        else
            error "需要 Node.js 18+，当前: v$node_ver"
            has_error=true
        fi
    else
        error "未找到 node，请先安装 Node.js 18+"
        has_error=true
    fi

    if command -v npm &>/dev/null; then
        success "npm: $(npm --version 2>&1)"
    else
        error "未找到 npm"
        has_error=true
    fi

    # 检查项目目录结构
    if [[ ! -d "$PROJECT_DIR" ]]; then
        error "项目目录不存在: $PROJECT_DIR"
        has_error=true
    else
        success "项目目录: $PROJECT_DIR"
    fi

    if [[ ! -d "$PROJECT_DIR/python" ]]; then
        error "Python 后端目录不存在: $PROJECT_DIR/python"
        has_error=true
    fi

    if [[ ! -f "$PROJECT_DIR/package.json" ]]; then
        error "package.json 不存在: $PROJECT_DIR/package.json"
        has_error=true
    fi

    # 检查 SSH 连接
    info "测试 SSH 连接..."
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$HOST" "echo OK" 2>/dev/null; then
        success "SSH 连接正常"
    else
        error "SSH 连接失败，请检查:"
        error "  1. 主机地址是否正确: $HOST"
        error "  2. SSH 密钥是否已配置: ssh-copy-id $HOST"
        error "  3. 服务器是否可达"
        has_error=true
    fi

    if [[ "$has_error" == true ]]; then
        exit 1
    fi
}

# ------------------------------------------------------------------------------
# 本地构建
# ------------------------------------------------------------------------------
build_local() {
    header "本地构建前端"

    local npm_cache_dir="$PROJECT_DIR/node_modules"

    if [[ -d "$npm_cache_dir" ]]; then
        info "node_modules 已存在，跳过 npm install"
    else
        info "执行 npm install..."
        cd "$PROJECT_DIR"
        npm install
        success "npm install 完成"
    fi

    info "执行 npm run build:web..."
    cd "$PROJECT_DIR"
    npm run build:web
    success "前端构建完成"
}

# ------------------------------------------------------------------------------
# 远程同步与部署
# ------------------------------------------------------------------------------
sync_and_deploy() {
    header "同步文件到远程服务器"

    # 远程创建目录
    info "在远程服务器创建目录..."
    ssh "$HOST" "mkdir -p '$REMOTE_DIR/dist' '$REMOTE_DIR/python' '$REMOTE_DIR/deploy'"
    success "远程目录已创建"

    # rsync 前端产物
    info "同步 dist/ ..."
    rsync -avz --delete "$PROJECT_DIR/dist/" "$HOST:$REMOTE_DIR/dist/"
    success "前端文件已同步"

    # rsync Python 后端
    info "同步 python/ ..."
    rsync -avz "$PROJECT_DIR/python/" "$HOST:$REMOTE_DIR/python/"
    success "Python 后端已同步"

    # rsync deploy 目录（包含 nginx.conf 和 deploy.sh）
    info "同步 deploy/ ..."
    rsync -avz "$PROJECT_DIR/deploy/" "$HOST:$REMOTE_DIR/deploy/"
    success "部署脚本和配置已同步"

    # 远程执行部署
    header "远程执行部署"

    info "在远程服务器上运行 deploy.sh ..."
    # shellcheck disable=SC2029
    ssh "$HOST" "bash '$REMOTE_DIR/deploy/deploy.sh' --install-dir '$REMOTE_DIR' --port $HTTP_PORT --mode 0"

    success "远程部署执行完成"
}

# ------------------------------------------------------------------------------
# 清理
# ------------------------------------------------------------------------------
cleanup() {
    # 不需要清理本地文件，deploy-remote.sh 不留临时文件
    # 远程临时文件由 deploy.sh 自行管理
    :
}

# ==============================================================================
# 主流程
# ==============================================================================
main() {
    # 解析绝对路径
    PROJECT_DIR="$(cd "$PROJECT_DIR" 2>/dev/null && pwd || echo "$PROJECT_DIR")"

    info "X-FAIS Web 远程部署工具"
    info "项目目录: $PROJECT_DIR"
    info "远程主机: ${HOST:-<未指定>}"
    info "远程目录: $REMOTE_DIR"
    info "后端端口: $HTTP_PORT"
    echo ""

    preflight_check
    build_local
    sync_and_deploy

    header "部署完成"
    echo ""
    echo -e "  ${GREEN}X-FAIS Web 已成功部署到 $HOST !${NC}"
    echo ""
    echo -e "  ${BLUE}访问地址:${NC}        http://$(echo "$HOST" | cut -d@ -f2)/"
    echo -e "  ${BLUE}远程安装目录:${NC}     $REMOTE_DIR"
    echo ""
    echo -e "  ${YELLOW}远程常用命令:${NC}"
    echo -e "    查看日志:  ssh $HOST 'journalctl -u xfais -f'"
    echo -e "    重启服务:  ssh $HOST 'systemctl restart xfais'"
    echo -e "    状态检查:  ssh $HOST 'systemctl status xfais'"
    echo -e "    卸载:      ssh $HOST 'bash $REMOTE_DIR/deploy/deploy.sh --uninstall'"
    echo ""
}

main
