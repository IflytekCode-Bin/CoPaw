#!/bin/bash
# CoPaw 开发版启动脚本
# 使用 /Data/CodeBase/iflycode/CoPaw 源码启动服务
# 默认端口 8085

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 源码目录
COPAW_SRC="/Data/CodeBase/iflycode/CoPaw"
DEFAULT_PORT=8085

check_port() {
    pgrep -f "copaw.*app.*$1" > /dev/null 2>&1
}

stop_port() {
    local port=$1
    local pid=$(pgrep -f "copaw.*app.*$port" 2>/dev/null)
    if [ -n "$pid" ]; then
        log_info "停止端口 $port (PID: $pid)..."
        kill $pid 2>/dev/null || true
        sleep 2
        check_port $port && kill -9 $(pgrep -f "copaw.*app.*$port") 2>/dev/null
        log_info "端口 $port 已停止"
    else
        log_warn "端口 $port 未运行"
    fi
}

start_server() {
    local port=${1:-$DEFAULT_PORT}
    local workdir="$HOME/.copaw_dev_server_$port"
    
    if check_port $port; then
        log_warn "端口 $port 已在运行，PID: $(pgrep -f "copaw.*app.*$port")"
        return 0
    fi
    
    log_info "启动 CoPaw 开发版 (端口 $port)..."
    log_info "源码目录: $COPAW_SRC"
    log_info "工作目录: $workdir"
    
    mkdir -p "$workdir"
    
    cd "$workdir"
    PYTHONPATH="$COPAW_SRC/src" \
    COPAW_WORKING_DIR="$workdir" \
    nohup copaw app --host 127.0.0.1 --port $port --log-level info > copaw.log 2>&1 &
    
    sleep 3
    if check_port $port; then
        log_info "已启动，PID: $(pgrep -f "copaw.*app.*$port")"
    else
        log_error "启动失败，查看日志: $workdir/copaw.log"
        tail -20 "$workdir/copaw.log"
        return 1
    fi
}

wait_for_service() {
    local port=$1
    local count=0
    log_info "等待端口 $port 服务就绪..."
    while [ $count -lt 30 ]; do
        curl -s "http://127.0.0.1:$port/api/agents" > /dev/null 2>&1 && return 0
        sleep 1
        count=$((count + 1))
    done
    log_error "端口 $port 服务启动超时"
    return 1
}

show_info() {
    local port=$1
    local workdir="$HOME/.copaw_dev_server_$port"
    
    if check_port $port; then
        local pid=$(pgrep -f "copaw.*app.*$port")
        local workspace=$(curl -s "http://127.0.0.1:$port/api/agents" 2>/dev/null | \
            python3 -c "import sys,json; d=json.load(sys.stdin); print(d['agents'][0]['workspace_dir'])" 2>/dev/null)
        local model=$(curl -s "http://127.0.0.1:$port/api/models/active?scope=effective" 2>/dev/null | \
            python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('active_llm',{}); print(f\"{m.get('provider_id','N/A')}/{m.get('model','N/A')}\")" 2>/dev/null)
        
        echo ""
        log_info "=== CoPaw 开发版 (端口 $port) ==="
        echo "  PID:        $pid"
        echo "  源码目录:   $COPAW_SRC"
        echo "  工作目录:   $workdir"
        echo "  Workspace:  $workspace"
        echo "  模型:       $model"
    else
        log_warn "端口 $port: 未运行"
    fi
}

show_help() {
    echo "用法: $0 [命令] [端口]"
    echo ""
    echo "使用 /Data/CodeBase/iflycode/CoPaw 源码启动 CoPaw 开发版服务"
    echo ""
    echo "命令:"
    echo "  start [端口]   启动服务 (默认端口 8085)"
    echo "  stop [端口]    停止服务"
    echo "  restart [端口] 重启服务"
    echo "  status [端口]  查看状态"
    echo "  log [端口]     查看日志"
    echo ""
    echo "示例:"
    echo "  $0              # 启动 8085"
    echo "  $0 start 8086   # 启动 8086"
    echo "  $0 stop         # 停止 8085"
}

main() {
    local action=${1:-start}
    local port=${2:-$DEFAULT_PORT}
    
    case "$action" in
        -h|--help|help) show_help; exit 0 ;;
        start)
            start_server $port
            sleep 5
            wait_for_service $port && show_info $port
            ;;
        stop) stop_port $port ;;
        restart)
            stop_port $port
            sleep 2
            start_server $port
            sleep 5
            wait_for_service $port && show_info $port
            ;;
        status) show_info $port ;;
        log)
            local workdir="$HOME/.copaw_dev_server_$port"
            [ -f "$workdir/copaw.log" ] && tail -100 "$workdir/copaw.log" || log_error "日志不存在: $workdir/copaw.log"
            ;;
        *) log_error "未知命令: $action"; show_help; exit 1 ;;
    esac
}

main "$@"