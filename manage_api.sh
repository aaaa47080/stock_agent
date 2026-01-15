#!/bin/bash
# API 管理腳本

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="/home/danny/AI-agent/.venv/bin/python"
API_SCRIPT="$SCRIPT_DIR/fastapi_main.py"
LOG_FILE="$SCRIPT_DIR/api.log"

get_pid() {
    # 只獲取在 Agent_System 目錄下運行的 fastapi_main.py 進程
    ps aux | grep "[f]astapi_main.py" | grep "Agent_System" | awk '{print $2}' | head -1
}

status() {
    PID=$(get_pid)
    if [ -n "$PID" ]; then
        echo "✅ API 運行中 (PID: $PID)"
        echo "📍 地址: http://172.23.37.2:8100"
        return 0
    else
        echo "❌ API 未運行"
        return 1
    fi
}

start() {
    if status > /dev/null 2>&1; then
        echo "⚠️  API 已經在運行中"
        status
        return 1
    fi

    echo "🚀 啟動 API..."
    cd "$SCRIPT_DIR"
    nohup "$VENV_PYTHON" "$API_SCRIPT" > "$LOG_FILE" 2>&1 &
    sleep 3

    if status > /dev/null 2>&1; then
        echo "✅ API 啟動成功"
        status
    else
        echo "❌ API 啟動失敗,請檢查日志: $LOG_FILE"
        return 1
    fi
}

stop() {
    PID=$(get_pid)
    if [ -z "$PID" ]; then
        echo "⚠️  API 未運行"
        return 1
    fi

    echo "🛑 停止 API (PID: $PID)..."
    kill "$PID"
    sleep 2

    # 檢查是否還在運行
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "⚠️  正常關閉失敗,強制關閉..."
        kill -9 "$PID"
        sleep 1
    fi

    if status > /dev/null 2>&1; then
        echo "❌ 停止失敗"
        return 1
    else
        echo "✅ API 已停止"
        return 0
    fi
}

restart() {
    echo "🔄 重啟 API..."
    stop
    sleep 2
    start
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "❌ 日志文件不存在: $LOG_FILE"
        return 1
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "使用方法: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "命令說明:"
        echo "  start   - 啟動 API"
        echo "  stop    - 停止 API"
        echo "  restart - 重啟 API"
        echo "  status  - 查看狀態"
        echo "  logs    - 查看日志 (Ctrl+C 退出)"
        exit 1
        ;;
esac
