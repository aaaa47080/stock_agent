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
# 默認 2 workers（適用於 Zeabur 等雲平台的免費/基礎方案）
# AI 库（LangChain、LangGraph）非常耗内存，过多 workers 会导致 OOM
# 可通过环境变量 WEB_CONCURRENCY 覆盖
workers = int(os.getenv("WEB_CONCURRENCY", 2))

# Uvicorn worker 以支持异步
worker_class = "uvicorn.workers.UvicornWorker"

# Worker 连接数限制
worker_connections = 1000

# Worker 最大请求数（防止内存泄漏）- 降低以更频繁地重启 workers
max_requests = 500
max_requests_jitter = 50

# Worker 超时时间（秒）
timeout = 120
graceful_timeout = 30
keepalive = 5

# 预加载应用代码（节省内存）
preload_app = True


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
    """Fork worker 后 - 重置數據庫連接池避免連接衝突"""
    print(f"👷 Worker {worker.pid} 已启动")

    # 重置連接池，讓每個 worker 創建自己的連接
    # 這是解決 preload_app=True 導致連接共享問題的關鍵
    try:
        from core.database.connection import reset_connection_pool
        reset_connection_pool()
    except Exception as e:
        print(f"⚠️ Worker {worker.pid} 連接池重置失敗: {e}")

def worker_exit(server, worker):
    """Worker 退出时"""
    print(f"👋 Worker {worker.pid} 已退出")

def on_exit(server):
    """服务器关闭时"""
    print("🛑 服务器已关闭")
