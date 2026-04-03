#!/bin/bash
# CoPaw Worker 重启脚本
# 支持重启 pip 安装版（8088-8091）和源码版（8085）
# 自动设置 COPAW_INSTANCE_ID 用于备份系统

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_debug() { echo -e "${BLUE}[DEBUG]${NC} $1"; }

# 配置
COPAW_SRC="/Data/CodeBase/iflycode/CoPaw"
DEFAULT_PORT=8085

# 端口类型映射
# 8085: 源码版（开发）
# 8088: pip 安装版（Manager）
# 8089: pip 安装版（Dev Worker）
# 8090: pip 安装版（Ops Worker）
# 8091: pip 安装版（Test Worker）
get_port_type() {
    local port=$1
    case $port in
        8085) echo "source" ;;
        8088|8089|8090|8091) echo "pip" ;;
        *) echo "unknown" ;;
    esac
}

get_workdir() {
    local port=$1
    local type=$(get_port_type $port)
    
    case $type in
        source) echo "$HOME/.copaw_dev_server_$port" ;;
        pip)
            case $port in
                8088) echo "$HOME/.copaw" ;;
                8089) echo "$HOME/.copaw_dev" ;;
                8090) echo "$HOME/.copaw_ops" ;;
                8091) echo "$HOME/.copaw_test" ;;
                *) echo "$HOME/.copaw" ;;
            esac
            ;;
        *) echo "$HOME/.copaw" ;;
    esac
}

get_agent_name() {
    local port=$1
    case $port in
        8088) echo "Manager" ;;
        8089) echo "Dev" ;;
        8090) echo "Ops" ;;
        8091) echo "Test" ;;
        8085) echo "Dev-Source" ;;
        *) echo "Unknown" ;;
    esac
}

check_port() {
    pgrep -f "copaw.*app.*--port.*$1" > /dev/null 2>&1 || \
    pgrep -f "copaw.*app.*$1" > /dev/null 2>&1
}

get_pid() {
    pgrep -f "copaw.*app.*--port.*$1" 2>/dev/null || \
    pgrep -f "copaw.*app.*$1" 2>/dev/null || \
    echo ""
}

stop_port() {
    local port=$1
    local pid=$(get_pid $port)
    
    if [ -n "$pid" ]; then
        log_info "停止端口 $port ($(get_agent_name $port), PID: $pid)..."
        kill $pid 2>/dev/null || true
        sleep 3
        
        # 检查是否还在运行，强制杀死
        if check_port $port; then
            log_warn "进程未响应，强制终止..."
            kill -9 $(get_pid $port) 2>/dev/null || true
            sleep 1
        fi
        
        if check_port $port; then
            log_error "无法停止端口 $port"
            return 1
        fi
        log_info "端口 $port 已停止"
    else
        log_warn "端口 $port 未运行"
    fi
}

start_server() {
    local port=${1:-$DEFAULT_PORT}
    local type=$(get_port_type $port)
    local workdir=$(get_workdir $port)
    local agent_name=$(get_agent_name $port)
    
    if check_port $port; then
        log_warn "端口 $port 已在运行，PID: $(get_pid $port)"
        return 0
    fi
    
    log_info "启动 $agent_name (端口 $port, 类型: $type)..."
    log_debug "工作目录: $workdir"
    
    mkdir -p "$workdir"
    
    # 设置 COPAW_INSTANCE_ID 用于备份系统
    export COPAW_INSTANCE_ID="127.0.0.1:$port"
    
    cd "$workdir"
    
    if [ "$type" = "source" ]; then
        # 源码版启动
        log_debug "启动模式: 源码 ($COPAW_SRC)"
        PYTHONPATH="$COPAW_SRC/src" \
        COPAW_WORKING_DIR="$workdir" \
        nohup copaw app --host 127.0.0.1 --port $port --log-level info > copaw.log 2>&1 &
    else
        # pip 安装版启动
        log_debug "启动模式: pip 安装"
        COPAW_WORKING_DIR="$workdir" \
        nohup copaw app --host 127.0.0.1 --port $port --log-level info > copaw.log 2>&1 &
    fi
    
    sleep 3
    
    if check_port $port; then
        log_info "已启动，PID: $(get_pid $port)"
    else
        log_error "启动失败，查看日志: $workdir/copaw.log"
        tail -30 "$workdir/copaw.log"
        return 1
    fi
}

wait_for_service() {
    local port=$1
    local count=0
    log_info "等待服务就绪..."
    
    while [ $count -lt 30 ]; do
        if curl -s "http://127.0.0.1:$port/api/agents" > /dev/null 2>&1; then
            log_info "服务已就绪 ✓"
            return 0
        fi
        sleep 1
        count=$((count + 1))
        echo -n "."
    done
    echo ""
    log_error "服务启动超时 (30s)"
    return 1
}

show_status() {
    local port=$1
    local workdir=$(get_workdir $port)
    local agent_name=$(get_agent_name $port)
    
    echo ""
    log_info "=== $agent_name (端口 $port) ==="
    
    if check_port $port; then
        local pid=$(get_pid $port)
        echo "  状态:       运行中 ✓"
        echo "  PID:        $pid"
        echo "  工作目录:   $workdir"
        echo "  Instance:   127.0.0.1:$port"
        
        # 获取 agent 信息
        local agents=$(curl -s "http://127.0.0.1:$port/api/agents" 2>/dev/null)
        if [ -n "$agents" ]; then
            local workspace=$(echo "$agents" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['agents'][0]['workspace_dir'])" 2>/dev/null)
            local active_model=$(curl -s "http://127.0.0.1:$port/api/models/active?scope=effective" 2>/dev/null | \
                python3 -c "import sys,json; d=json.load(sys.stdin); m=d.get('active_llm',{}); print(f\"{m.get('provider_id','N/A')}/{m.get('model','N/A')}\")" 2>/dev/null)
            echo "  Workspace:  $workspace"
            echo "  模型:       $active_model"
        fi
        
        # 检查 MinIO 备份状态
        local buckets=$(cd "$COPAW_SRC" && python3 scripts/show_minio.py 2>/dev/null | grep "copaw-127-0-0-1-$port" | head -5)
        if [ -n "$buckets" ]; then
            echo "  MinIO 备份:"
            echo "$buckets" | while read line; do echo "    $line"; done
        fi
    else
        echo "  状态:       未运行"
        echo "  工作目录:   $workdir"
    fi
}

show_log() {
    local port=$1
    local workdir=$(get_workdir $port)
    local lines=${2:-50}
    
    if [ -f "$workdir/copaw.log" ]; then
        log_info "日志 (最后 $lines 行):"
        tail -$lines "$workdir/copaw.log"
    else
        log_error "日志不存在: $workdir/copaw.log"
    fi
}

show_help() {
    echo "用法: $0 [命令] [端口]"
    echo ""
    echo "CoPaw Worker 服务管理脚本"
    echo "自动设置 COPAW_INSTANCE_ID 用于 MinIO 备份系统"
    echo ""
    echo "端口类型:"
    echo "  8085  源码版（开发测试）"
    echo "  8088  pip 版（Manager）- 注意：需要手动重启"
    echo "  8089  pip 版（Dev Worker）"
    echo "  8090  pip 版（Ops Worker）"
    echo "  8091  pip 版（Test Worker）"
    echo ""
    echo "命令:"
    echo "  start [端口]    启动服务"
    echo "  stop [端口]     停止服务"
    echo "  restart [端口]  重启服务"
    echo "  status [端口]   查看状态"
    echo "  log [端口] [行] 查看日志"
    echo "  all             显示所有端口状态"
    echo ""
    echo "示例:"
    echo "  $0 restart 8085    # 重启源码版"
    echo "  $0 restart 8089    # 重启 Dev Worker"
    echo "  $0 status all      # 显示所有状态"
}

show_all_status() {
    log_info "=== 所有 CoPaw 服务状态 ==="
    for port in 8085 8088 8089 8090 8091; do
        show_status $port
    done
}

main() {
    local action=${1:-status}
    local port=${2:-$DEFAULT_PORT}
    
    case "$action" in
        -h|--help|help) show_help; exit 0 ;;
        start)
            start_server $port
            sleep 5
            wait_for_service $port && show_status $port
            ;;
        stop) stop_port $port ;;
        restart)
            log_info "重启端口 $port..."
            stop_port $port
            sleep 2
            start_server $port
            sleep 5
            wait_for_service $port && show_status $port
            ;;
        status)
            if [ "$port" = "all" ]; then
                show_all_status
            else
                show_status $port
            fi
            ;;
        log)
            local lines=${3:-50}
            show_log $port $lines
            ;;
        all) show_all_status ;;
        *) log_error "未知命令: $action"; show_help; exit 1 ;;
    esac
}

main "$@"