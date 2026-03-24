"""
Gunicorn 生產環境配置文件
用於多進程部署 Pi Crypto Insight API Server
"""

import os

# ========================================
# Server Socket
# ========================================
bind = "0.0.0.0:8080"
backlog = 2048

# ========================================
# Worker Processes
# ========================================
# 默認 1 worker（雲端小資源環境較穩定，避免啟動期被 OOM/探針誤殺）
# 可再透過 WEB_CONCURRENCY 調整
# 可通過環境變量 WEB_CONCURRENCY 覆蓋
workers = int(os.getenv("WEB_CONCURRENCY", 1))

# Uvicorn worker 以支持異步
worker_class = "uvicorn.workers.UvicornWorker"

# Worker 連接數限制
worker_connections = 1000

# Worker 最大請求數（防止內存泄漏）- 降低以更頻繁地重啟 workers
max_requests = 500
max_requests_jitter = 50

# Worker 超時時間（秒）
timeout = 120
graceful_timeout = 30
keepalive = 5

# 禁用 preload，降低啟動期共享狀態/連線池問題風險
preload_app = False


# ========================================
# Logging
# ========================================
# 訪問日志 - 預設關閉，避免高流量時大量佔用容器 ephemeral storage
# 若需臨時開啟，可設定 GUNICORN_ACCESSLOG=-
accesslog = os.getenv("GUNICORN_ACCESSLOG")
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 錯誤日志 - 輸出到 stderr（容器友好）
errorlog = "-"
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "warning").lower()

# ========================================
# Process Naming
# ========================================
proc_name = "pi_crypto_insight"

# ========================================
# Server Mechanics
# ========================================
# 守護進程模式（生產環境建議使用 systemd 或 supervisor）
daemon = False

# PID 文件 - 使用 /tmp 以避免權限問題
pidfile = "/tmp/gunicorn.pid"

# 用戶/組（可選，生產環境建議使用非 root 用戶）
# user = "www-data"
# group = "www-data"

# 臨時目錄
tmp_upload_dir = None


# ========================================
# Server Hooks
# ========================================
def on_starting(server):
    """服務器啟動時"""
    print("🚀 Pi Crypto Insight API Server 啟動中...")
    print(f"📊 Workers: {workers}")
    print(f"🔗 Bind: {bind}")


def on_reload(server):
    """重新加載配置時"""
    print("🔄 重新加載配置...")


def when_ready(server):
    """服務器準備就緒時"""
    print("✅ 服務器已就緒，等待請求...")


def pre_fork(server, worker):
    """Fork worker 前"""
    pass


def post_fork(server, worker):
    """Fork worker 後 - 重置數據庫連接池避免連接衝突"""
    print(f"👷 Worker {worker.pid} 已啟動")

    # 重置連接池，讓每個 worker 創建自己的連接
    # 這是解決 preload_app=True 導致連接共享問題的關鍵
    try:
        from core.database.connection import reset_connection_pool
        from core.orm.session import close_async_engine_sync

        reset_connection_pool()
        close_async_engine_sync()
    except Exception as e:
        print(f"⚠️ Worker {worker.pid} 連接池重置失敗: {e}")


def worker_exit(server, worker):
    """Worker 退出時"""
    print(f"👋 Worker {worker.pid} 已退出")


def on_exit(server):
    """服務器關閉時"""
    print("🛑 服務器已關閉")
