#!/bin/bash

# ==============================================================================
# Pi Crypto Insight - 生产环境启动脚本
# ==============================================================================
# 功能：
# - 多进程 Gunicorn + Uvicorn Workers
# - 自动创建日志目录
# - 环境检查
# - 优雅关闭处理
# ==============================================================================

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 配置
APP_NAME="Pi Crypto Insight"
APP_MODULE="api_server:app"
CONFIG_FILE="gunicorn.conf.py"
LOG_DIR="logs"
PID_FILE="${LOG_DIR}/gunicorn.pid"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 创建日志目录
create_log_dir() {
    if [ ! -d "$LOG_DIR" ]; then
        mkdir -p "$LOG_DIR"
        print_success "日志目录已创建: $LOG_DIR"
    fi
}

# 检查环境
check_environment() {
    print_info "检查运行环境..."
    
    # 检查 Python
    if ! command -v python &> /dev/null; then
        print_error "Python 未安装"
        exit 1
    fi
    
    # 检查虚拟环境
    if [ -z "$VIRTUAL_ENV" ]; then
        print_warning "未检测到虚拟环境，建议使用 venv"
        read -p "是否继续？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # 检查依赖
    if ! python -c "import gunicorn" 2>/dev/null; then
        print_error "Gunicorn 未安装，请运行: pip install -r requirements.txt"
        exit 1
    fi
    
    print_success "环境检查通过"
}

# 检查是否已在运行
check_running() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_warning "服务已在运行 (PID: $PID)"
            read -p "是否重启？(y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                stop_server
            else
                exit 0
            fi
        else
            print_warning "发现过期的 PID 文件，正在清理..."
            rm -f "$PID_FILE"
        fi
    fi
}

# 停止服务器
stop_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        print_info "正在停止服务 (PID: $PID)..."
        kill -TERM "$PID" 2>/dev/null || true
        
        # 等待优雅关闭
        for i in {1..30}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                print_success "服务已停止"
                rm -f "$PID_FILE"
                return 0
            fi
            sleep 1
        done
        
        # 强制关闭
        print_warning "优雅关闭超时，强制停止..."
        kill -9 "$PID" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
}

# 启动服务器
start_server() {
    print_info "🚀 启动 $APP_NAME..."
    print_info "配置文件: $CONFIG_FILE"
    
    # 默认 Worker 数量 (可通过环境变量覆盖)
    WORKERS=${WEB_CONCURRENCY:-$(python -c "import multiprocessing; print(multiprocessing.cpu_count() * 2 + 1)")}
    print_info "Workers: $WORKERS"
    
    # 启动 Gunicorn
    gunicorn "$APP_MODULE" \
        --config "$CONFIG_FILE" \
        --workers "$WORKERS" \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8080 \
        --daemon
    
    sleep 2
    
    # 检查是否成功启动
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_success "✅ 服务已启动 (PID: $PID)"
            print_success "🏠 本地网址: http://localhost:8080"
            print_success "📊 访问日志: ${LOG_DIR}/gunicorn_access.log"
            print_success "❌ 错误日志: ${LOG_DIR}/gunicorn_error.log"
            return 0
        fi
    fi
    
    print_error "服务启动失败，请查看错误日志"
    return 1
}

# 显示状态
show_status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_success "服务正在运行 (PID: $PID)"
            
            # 显示 Worker 信息
            print_info "Workers:"
            ps aux | grep "[g]unicorn.*$APP_MODULE" | awk '{print "  - PID: "$2" | CPU: "$3"% | MEM: "$4"%"}'
            
            return 0
        fi
    fi
    
    print_warning "服务未运行"
    return 1
}

# 主函数
main() {
    case "${1:-start}" in
        start)
            create_log_dir
            check_environment
            check_running
            start_server
            ;;
        stop)
            stop_server
            ;;
        restart)
            stop_server
            sleep 2
            create_log_dir
            start_server
            ;;
        status)
            show_status
            ;;
        *)
            echo "用法: $0 {start|stop|restart|status}"
            exit 1
            ;;
    esac
}

# 捕获退出信号
trap stop_server EXIT INT TERM

main "$@"
