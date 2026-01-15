#!/bin/bash

# vLLM 服務管理腳本
# 支持啟動、停止、重啟、查看狀態

LOG_DIR="/home/danny/AI-agent/vllm"
PID_FILE_8080="$LOG_DIR/vllm_8080.pid"
PID_FILE_8081="$LOG_DIR/vllm_8081.pid"

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 檢查服務狀態
check_service() {
    local port=$1
    local pid_file=$2

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} Port $port (PID: $pid) - Running"
            return 0
        else
            echo -e "${RED}✗${NC} Port $port - PID file exists but process not running"
            rm -f "$pid_file"
            return 1
        fi
    else
        echo -e "${YELLOW}○${NC} Port $port - Not running"
        return 1
    fi
}

# 啟動 Qwen3 4B 服務 (端口 8080)
start_qwen3() {
    echo -e "${BLUE}Starting Qwen3 4B on port 8080...${NC}"

    if check_service 8080 "$PID_FILE_8080" > /dev/null 2>&1; then
        echo -e "${YELLOW}Service already running on port 8080${NC}"
        return 1
    fi

    cd "$LOG_DIR"
    CUDA_VISIBLE_DEVICES=6,7 \
    PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    VLLM_WORKER_MULTIPROC_METHOD=spawn \
    VLLM_ATTENTION_BACKEND=XFORMERS \
    VLLM_USE_V1=0 \
    nohup vllm serve /home/danny/AI-agent/Qwen3_4B_2507 \
      --tensor-parallel-size 2 \
      --dtype float16 \
      --gpu-memory-utilization 0.9 \
      --max-model-len 32768 \
      --max-num-seqs 16 \
      --host 0.0.0.0 \
      --port 8080 \
      --trust-remote-code \
      --enable-auto-tool-choice --tool-call-parser hermes \
      --disable-custom-all-reduce > vllm_8080.log 2>&1 &

    echo $! > "$PID_FILE_8080"
    echo -e "${GREEN}Started Qwen3 4B (PID: $(cat $PID_FILE_8080))${NC}"
    echo "Log: $LOG_DIR/vllm_8080.log"
}

# 啟動 Embedding 服務 (端口 8081)
start_embedding() {
    echo -e "${BLUE}Starting Qwen3 Embedding on port 8081...${NC}"

    if check_service 8081 "$PID_FILE_8081" > /dev/null 2>&1; then
        echo -e "${YELLOW}Service already running on port 8081${NC}"
        return 1
    fi

    cd "$LOG_DIR"
    CUDA_VISIBLE_DEVICES=4,5 \
    nohup python -m vllm.entrypoints.openai.api_server \
      --model /home/danny/AI-agent/Qwen3-Embedding-4B \
      --task embed \
      --dtype float16 \
      --port 8081 \
      --tensor-parallel-size 2 \
      --gpu-memory-utilization 0.9 \
      --max-model-len 8192 > vllm_8081.log 2>&1 &

    echo $! > "$PID_FILE_8081"
    echo -e "${GREEN}Started Embedding service (PID: $(cat $PID_FILE_8081))${NC}"
    echo "Log: $LOG_DIR/vllm_8081.log"
}

# 停止服務
stop_service() {
    local port=$1
    local pid_file=$2

    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if ps -p $pid > /dev/null 2>&1; then
            echo -e "${BLUE}Stopping service on port $port (PID: $pid)...${NC}"
            kill $pid
            sleep 2
            if ps -p $pid > /dev/null 2>&1; then
                echo -e "${YELLOW}Force killing...${NC}"
                kill -9 $pid
            fi
            rm -f "$pid_file"
            echo -e "${GREEN}Stopped${NC}"
        else
            echo -e "${YELLOW}Process not running${NC}"
            rm -f "$pid_file"
        fi
    else
        echo -e "${YELLOW}Service not running on port $port${NC}"
    fi
}

# 查看狀態
show_status() {
    echo -e "\n${BLUE}=== vLLM Services Status ===${NC}\n"
    check_service 8080 "$PID_FILE_8080"
    check_service 8081 "$PID_FILE_8081"
    echo ""
}

# 查看日志
show_logs() {
    local port=$1
    local lines=${2:-50}

    echo -e "${BLUE}=== Last $lines lines of port $port ===${NC}"
    if [ -f "$LOG_DIR/vllm_$port.log" ]; then
        tail -n $lines "$LOG_DIR/vllm_$port.log"
    else
        echo -e "${YELLOW}Log file not found${NC}"
    fi
}

# 顯示菜單
show_menu() {
    echo -e "\n${BLUE}╔════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     vLLM Service Manager           ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════╝${NC}\n"
    echo "  1) Start Qwen3 4B (port 8080)"
    echo "  2) Start Embedding (port 8081)"
    echo "  3) Start All Services"
    echo "  4) Stop Qwen3 4B (port 8080)"
    echo "  5) Stop Embedding (port 8081)"
    echo "  6) Stop All Services"
    echo "  7) Restart Qwen3 4B"
    echo "  8) Restart Embedding"
    echo "  9) Restart All"
    echo " 10) Show Status"
    echo " 11) Show Logs (8080)"
    echo " 12) Show Logs (8081)"
    echo "  0) Exit"
    echo ""
}

# 主函數
main() {
    # 如果有命令行參數，直接執行
    if [ $# -gt 0 ]; then
        case "$1" in
            start)
                if [ "$2" = "all" ] || [ -z "$2" ]; then
                    start_qwen3
                    sleep 2
                    start_embedding
                elif [ "$2" = "qwen" ] || [ "$2" = "8080" ]; then
                    start_qwen3
                elif [ "$2" = "embed" ] || [ "$2" = "8081" ]; then
                    start_embedding
                fi
                ;;
            stop)
                if [ "$2" = "all" ] || [ -z "$2" ]; then
                    stop_service 8080 "$PID_FILE_8080"
                    stop_service 8081 "$PID_FILE_8081"
                elif [ "$2" = "qwen" ] || [ "$2" = "8080" ]; then
                    stop_service 8080 "$PID_FILE_8080"
                elif [ "$2" = "embed" ] || [ "$2" = "8081" ]; then
                    stop_service 8081 "$PID_FILE_8081"
                fi
                ;;
            restart)
                if [ "$2" = "all" ] || [ -z "$2" ]; then
                    stop_service 8080 "$PID_FILE_8080"
                    stop_service 8081 "$PID_FILE_8081"
                    sleep 3
                    start_qwen3
                    sleep 2
                    start_embedding
                elif [ "$2" = "qwen" ] || [ "$2" = "8080" ]; then
                    stop_service 8080 "$PID_FILE_8080"
                    sleep 3
                    start_qwen3
                elif [ "$2" = "embed" ] || [ "$2" = "8081" ]; then
                    stop_service 8081 "$PID_FILE_8081"
                    sleep 3
                    start_embedding
                fi
                ;;
            status)
                show_status
                ;;
            logs)
                if [ "$2" = "8080" ] || [ "$2" = "qwen" ]; then
                    show_logs 8080 ${3:-50}
                elif [ "$2" = "8081" ] || [ "$2" = "embed" ]; then
                    show_logs 8081 ${3:-50}
                else
                    echo "Usage: $0 logs [8080|8081] [lines]"
                fi
                ;;
            *)
                echo "Usage: $0 {start|stop|restart|status|logs} [all|qwen|embed|8080|8081]"
                echo "Examples:"
                echo "  $0 start all      - Start all services"
                echo "  $0 stop 8080      - Stop Qwen3 service"
                echo "  $0 restart embed  - Restart embedding service"
                echo "  $0 status         - Show status"
                echo "  $0 logs 8080 100  - Show last 100 lines of 8080 log"
                exit 1
                ;;
        esac
        exit 0
    fi

    # 交互模式
    while true; do
        show_menu
        read -p "Enter your choice [0-12]: " choice

        case $choice in
            1)
                start_qwen3
                read -p "Press Enter to continue..."
                ;;
            2)
                start_embedding
                read -p "Press Enter to continue..."
                ;;
            3)
                start_qwen3
                sleep 2
                start_embedding
                read -p "Press Enter to continue..."
                ;;
            4)
                stop_service 8080 "$PID_FILE_8080"
                read -p "Press Enter to continue..."
                ;;
            5)
                stop_service 8081 "$PID_FILE_8081"
                read -p "Press Enter to continue..."
                ;;
            6)
                stop_service 8080 "$PID_FILE_8080"
                stop_service 8081 "$PID_FILE_8081"
                read -p "Press Enter to continue..."
                ;;
            7)
                stop_service 8080 "$PID_FILE_8080"
                sleep 3
                start_qwen3
                read -p "Press Enter to continue..."
                ;;
            8)
                stop_service 8081 "$PID_FILE_8081"
                sleep 3
                start_embedding
                read -p "Press Enter to continue..."
                ;;
            9)
                stop_service 8080 "$PID_FILE_8080"
                stop_service 8081 "$PID_FILE_8081"
                sleep 3
                start_qwen3
                sleep 2
                start_embedding
                read -p "Press Enter to continue..."
                ;;
            10)
                show_status
                read -p "Press Enter to continue..."
                ;;
            11)
                show_logs 8080
                read -p "Press Enter to continue..."
                ;;
            12)
                show_logs 8081
                read -p "Press Enter to continue..."
                ;;
            0)
                echo -e "${GREEN}Goodbye!${NC}"
                exit 0
                ;;
            *)
                echo -e "${RED}Invalid option${NC}"
                read -p "Press Enter to continue..."
                ;;
        esac

        clear
    done
}

# 運行主函數
main "$@"
