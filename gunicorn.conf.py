"""
Gunicorn 生产环境配置文件
用于多进程部署 Pi Crypto Insight API Server
"""
import multiprocessing
import os

# ========================================
# Server Socket
# ========================================
bind = "0.0.0.0:8111"
backlog = 2048

# ========================================
# Worker Processes
# ========================================
# 推荐配置：(2 * CPU核心数) + 1
# 可通过环境变量 WEB_CONCURRENCY 覆盖
workers = int(os.getenv("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))

# Uvicorn worker 以支持异步
worker_class = "uvicorn.workers.UvicornWorker"

# Worker 连接数限制
worker_connections = 1000

# Worker 最大请求数（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 50

# Worker 超时时间（秒）
timeout = 120
graceful_timeout = 30
keepalive = 5

# ========================================
# Logging
# ========================================
# 访问日志 - 输出到 stdout（容器友好）
accesslog = "-"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 错误日志 - 输出到 stderr（容器友好）
errorlog = "-"
loglevel = "info"

# ========================================
# Process Naming
# ========================================
proc_name = "pi_crypto_insight"

# ========================================
# Server Mechanics
# ========================================
# 守护进程模式（生产环境建议使用 systemd 或 supervisor）
daemon = False

# PID 文件 - 使用 /tmp 以避免权限问题
pidfile = "/tmp/gunicorn.pid"

# 用户/组（可选，生产环境建议使用非 root 用户）
# user = "www-data"
# group = "www-data"

# 临时目录
tmp_upload_dir = None

# ========================================
# Server Hooks
# ========================================
def on_starting(server):
    """服务器启动时"""
    print("🚀 Pi Crypto Insight API Server 启动中...")
    print(f"📊 Workers: {workers}")
    print(f"🔗 Bind: {bind}")

def on_reload(server):
    """重新加载配置时"""
    print("🔄 重新加载配置...")

def when_ready(server):
    """服务器准备就绪时"""
    print("✅ 服务器已就绪，等待请求...")

def pre_fork(server, worker):
    """Fork worker 前"""
    pass

def post_fork(server, worker):
    """Fork worker 后"""
    print(f"👷 Worker {worker.pid} 已启动")

def worker_exit(server, worker):
    """Worker 退出时"""
    print(f"👋 Worker {worker.pid} 已退出")

def on_exit(server):
    """服务器关闭时"""
    print("🛑 服务器已关闭")
