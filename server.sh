#!/bin/bash
# ============================================
# Crypto Trading System API Server 管理腳本
# ============================================

# 配置
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$SCRIPT_DIR/.venv"
PID_FILE="$SCRIPT_DIR/.api_server.pid"
LOG_FILE="$SCRIPT_DIR/api_server.log"
SERVER_SCRIPT="$SCRIPT_DIR/api_server.py"
PORT=8111

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 輸出函數
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 清理 Python 緩存
clean_cache() {
    info "清理 Python 緩存..."
    find "$SCRIPT_DIR" -name "*.pyc" -delete 2>/dev/null
    find "$SCRIPT_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
    success "緩存已清理"
}

# 獲取所有相關進程的 PID
get_all_pids() {
    # 方法 1: 通過端口查找
    local port_pid=$(lsof -ti :$PORT 2>/dev/null | head -1)

    # 方法 2: 通過進程名查找（更精確匹配，排除當前腳本進程）
    local proc_pids=$(pgrep -f "python.*api_server\.py" 2>/dev/null | grep -v "^$$\$")

    # 合併並去重（排除空值和當前 shell 的子進程）
    echo -e "$port_pid\n$proc_pids" | grep -v '^$' | grep -v "^$$\$" | sort -u
}

# 檢查服務器狀態
check_status() {
    local pids=$(get_all_pids)

    if [ -z "$pids" ]; then
        echo -e "${RED}● 服務器未運行${NC}"
        return 1
    else
        local count=$(echo "$pids" | wc -l)
        if [ "$count" -eq 1 ]; then
            echo -e "${GREEN}● 服務器運行中${NC} (PID: $pids)"

            # 檢查端口
            if nc -z localhost $PORT 2>/dev/null; then
                success "端口 $PORT 正在監聽"
            else
                warning "端口 $PORT 未監聽（可能還在啟動中）"
            fi

            # 顯示運行時間
            local start_time=$(ps -o lstart= -p $pids 2>/dev/null)
            if [ -n "$start_time" ]; then
                info "啟動時間: $start_time"
            fi
            return 0
        else
            echo -e "${YELLOW}● 發現多個服務器進程！${NC} (共 $count 個)"
            echo "PIDs: $pids"
            warning "建議執行 'server.sh restart' 來清理"
            return 2
        fi
    fi
}

# 停止服務器
stop_server() {
    info "正在停止服務器..."

    local pids=$(get_all_pids)

    if [ -z "$pids" ]; then
        info "沒有運行中的服務器"
        rm -f "$PID_FILE"
        return 0
    fi

    # 先嘗試優雅停止
    echo "$pids" | xargs kill 2>/dev/null
    sleep 2

    # 檢查是否還有進程
    pids=$(get_all_pids)
    if [ -n "$pids" ]; then
        warning "進程未響應，強制終止..."
        echo "$pids" | xargs kill -9 2>/dev/null
        sleep 1
    fi

    # 最終檢查
    pids=$(get_all_pids)
    if [ -z "$pids" ]; then
        success "服務器已停止"
        rm -f "$PID_FILE"
        return 0
    else
        error "無法停止所有進程"
        return 1
    fi
}

# 啟動服務器
start_server() {
    info "正在啟動服務器..."

    # 檢查是否已經在運行
    local pids=$(get_all_pids)
    if [ -n "$pids" ]; then
        error "服務器已經在運行 (PID: $pids)"
        info "使用 'server.sh restart' 來重啟"
        return 1
    fi

    # 清理緩存（避免舊代碼問題）
    clean_cache

    # 檢查虛擬環境
    if [ ! -f "$VENV_PATH/bin/activate" ]; then
        error "找不到虛擬環境: $VENV_PATH"
        return 1
    fi

    # 啟動服務器
    cd "$SCRIPT_DIR"
    source "$VENV_PATH/bin/activate"

    # Properly detach the process from the terminal
    nohup python "$SERVER_SCRIPT" </dev/null >> "$LOG_FILE" 2>&1 &
    local pid=$!
    echo $pid > "$PID_FILE"

    # 等待啟動
    info "等待服務器啟動..."
    sleep 3

    # 檢查是否成功
    if kill -0 $pid 2>/dev/null; then
        success "服務器已啟動 (PID: $pid)"

        # 等待端口就緒
        for i in {1..10}; do
            if nc -z localhost $PORT 2>/dev/null; then
                success "服務器已就緒: http://localhost:$PORT"
                return 0
            fi
            sleep 1
        done
        warning "服務器已啟動，但端口可能還在初始化"
        return 0
    else
        error "服務器啟動失敗，請查看日誌: $LOG_FILE"
        tail -20 "$LOG_FILE"
        return 1
    fi
}

# 重啟服務器
restart_server() {
    info "正在重啟服務器..."
    stop_server
    sleep 1
    start_server
}

# 查看日誌
view_logs() {
    local lines=${1:-50}
    if [ -f "$LOG_FILE" ]; then
        tail -n "$lines" "$LOG_FILE"
    else
        error "日誌文件不存在: $LOG_FILE"
    fi
}

# 即時查看日誌
follow_logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        error "日誌文件不存在: $LOG_FILE"
    fi
}

# 健康檢查
health_check() {
    info "執行健康檢查..."

    # 1. 進程檢查
    check_status
    local status_code=$?

    if [ $status_code -eq 1 ]; then
        return 1
    fi

    # 2. API 健康檢查
    local response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/health" 2>/dev/null)

    if [ "$response" = "200" ]; then
        success "API 健康檢查通過"
    else
        error "API 健康檢查失敗 (HTTP $response)"
        return 1
    fi

    # 3. 顯示資源使用
    local pid=$(get_all_pids | head -1)
    if [ -n "$pid" ]; then
        local mem=$(ps -o rss= -p $pid 2>/dev/null | awk '{printf "%.1f MB", $1/1024}')
        local cpu=$(ps -o %cpu= -p $pid 2>/dev/null)
        info "資源使用: CPU ${cpu}%, 記憶體 ${mem}"
    fi

    return 0
}

# 顯示幫助
show_help() {
    echo ""
    echo -e "${BLUE}Crypto Trading System API Server 管理腳本${NC}"
    echo ""
    echo "用法: $0 <命令>"
    echo ""
    echo "命令:"
    echo "  start      啟動服務器"
    echo "  stop       停止服務器"
    echo "  restart    重啟服務器（推薦用於更新代碼後）"
    echo "  status     查看服務器狀態"
    echo "  health     健康檢查（包含 API 測試）"
    echo "  logs       查看最近 50 行日誌"
    echo "  logs N     查看最近 N 行日誌"
    echo "  follow     即時追蹤日誌（Ctrl+C 退出）"
    echo "  clean      清理 Python 緩存"
    echo ""
    echo "範例:"
    echo "  $0 restart   # 更新代碼後重啟"
    echo "  $0 logs 100  # 查看最近 100 行日誌"
    echo "  $0 follow    # 即時查看日誌"
    echo ""
}

# 主入口
case "$1" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        restart_server
        ;;
    status)
        check_status
        ;;
    health)
        health_check
        ;;
    logs)
        view_logs "$2"
        ;;
    follow)
        follow_logs
        ;;
    clean)
        clean_cache
        ;;
    *)
        show_help
        ;;
esac
