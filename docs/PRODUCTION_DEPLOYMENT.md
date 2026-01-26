# Pi Crypto Insight - 生产环境部署指南

## 📋 目录
- [架构说明](#架构说明)
- [部署前准备](#部署前准备)
- [生产环境部署](#生产环境部署)
- [监控与维护](#监控与维护)
- [故障排查](#故障排查)

---

## 🏗️ 架构说明

### 多进程架构
```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    │   (Nginx 等)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │   Gunicorn      │
                    │   Master        │
                    └────────┬────────┘
                             │
         ┌──────────┬────────┼────────┬──────────┐
         ▼          ▼        ▼        ▼          ▼
    Worker 1   Worker 2  Worker 3  Worker 4  Worker N
    (Uvicorn)  (Uvicorn) (Uvicorn) (Uvicorn) (Uvicorn)
         │          │        │        │          │
         └──────────┴────────┴────────┴──────────┘
                             │
                    ┌────────▼────────┐
                    │   SQLite/PG     │
                    │   Database      │
                    └─────────────────┘
```

### Worker 数量建议
- **公式**: `(2 × CPU核心数) + 1`
- **示例**:
  - 2核CPU → 5 workers
  - 4核CPU → 9 workers
  - 8核CPU → 17 workers

---

## 🔧 部署前准备

### 1. 系统要求
- **OS**: Linux / macOS / Windows (WSL)
- **Python**: 3.10+
- **内存**: 2GB+ (建议 4GB+)
- **CPU**: 2核+ (建议 4核+)

### 2. 安装依赖
```bash
# 克隆项目
git clone <your-repo-url>
cd stock_agent

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖 (已包含 Gunicorn)
pip install -r requirements.txt
```

### 3. 环境变量配置
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
nano .env
```

**关键配置**:
```env
# 生产环境标识
ENVIRONMENT=production

# Worker 数量 (可选，默认自动计算)
WEB_CONCURRENCY=9

# 数据库
DATABASE_URL=sqlite:///user_data.db  # 或 PostgreSQL URL

# 日志级别
LOG_LEVEL=INFO
```

---

## 🚀 生产环境部署

### 方法 1: 使用生产启动脚本 (推荐)

#### Linux/macOS
```bash
# 赋予执行权限
chmod +x start_production.sh

# 启动服务
./start_production.sh start

# 查看状态
./start_production.sh status

# 重启
./start_production.sh restart

# 停止
./start_production.sh stop
```

#### Windows (PowerShell)
```powershell
# 使用 Git Bash 或 WSL
bash start_production.sh start
```

### 方法 2: 手动启动

```bash
# 创建日志目录
mkdir -p logs

# 启动 Gunicorn
gunicorn api_server:app \
    --config gunicorn.conf.py \
    --workers 9 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8111 \
    --daemon

# 查看进程
ps aux | grep gunicorn

# 停止服务
kill -TERM $(cat logs/gunicorn.pid)
```

### 方法 3: Systemd 服务 (Linux)

创建服务文件 `/etc/systemd/system/pi-crypto-insight.service`:

```ini
[Unit]
Description=Pi Crypto Insight API Server
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/path/to/stock_agent
Environment="PATH=/path/to/stock_agent/.venv/bin"
ExecStart=/path/to/stock_agent/.venv/bin/gunicorn api_server:app \
    --config gunicorn.conf.py \
    --workers 9
ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=30
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

**启动服务**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pi-crypto-insight
sudo systemctl start pi-crypto-insight
sudo systemctl status pi-crypto-insight
```

---

## 📊 监控与维护

### 1. 健康检查

访问健康检查端点:
```bash
# 服务存活检查
curl http://localhost:8111/health

# 预期响应 (200 OK):
{
  "status": "healthy",
  "service": "pi_crypto_insight",
  "uptime_seconds": 3600
}

# 就绪检查 (检查组件状态)
curl http://localhost:8111/ready

# 预期响应 (200 OK):
{
  "status": "ready",
  "components": {
    "okx_connector": true,
    "crypto_bot": true,
    "database": true
  },
  "uptime_seconds": 3600
}
```

### 2. 日志监控

```bash
# 实时查看访问日志
tail -f logs/gunicorn_access.log

# 实时查看错误日志
tail -f logs/gunicorn_error.log

# 查看应用日志
tail -f api_server.log
```

### 3. 性能监控

```bash
# 查看 Worker 状态
ps aux | grep gunicorn

# 查看内存使用
free -h

# 查看 CPU 负载
top -p $(cat logs/gunicorn.pid)
```

---

## 🐛 故障排查

### 问题 1: 服务启动失败

**检查日志**:
```bash
cat logs/gunicorn_error.log
cat api_server.log
```

**常见原因**:
- 端口被占用 → 更改 `gunicorn.conf.py` 中的 `bind`
- 缺少依赖 → 重新运行 `pip install -r requirements.txt`
- 权限问题 → 检查日志目录权限

### 问题 2: Workers 频繁重启

**检查**:
```bash
# 查看 Worker 崩溃日志
grep "Worker" logs/gunicorn_error.log
```

**可能原因**:
- 内存不足 → 减少 Worker 数量
- 数据库连接超时 → 优化数据库查询
- LLM API 超时 → 增加超时时间

### 问题 3: 响应缓慢

**诊断步骤**:
1. 检查 Worker 是否饱和
   ```bash
   ps aux | grep "[g]unicorn.*worker" | wc -l
   ```
2. 检查数据库性能
   ```bash
   du -h user_data.db  # 检查数据库大小
   ```
3. 查看慢查询日志

**优化建议**:
- 增加 Worker 数量
- 添加 Redis 缓存
- 优化数据库索引

---

## 🔄 滚动更新 (Zero Downtime)

```bash
# 方法 1: 优雅重启
kill -HUP $(cat logs/gunicorn.pid)

# 方法 2: 使用脚本
./start_production.sh restart
```

---

## 📈 扩展建议

### 水平扩展
1. **部署多个实例**，使用 Nginx 负载均衡
2. **共享数据库**，迁移至 PostgreSQL
3. **Redis 缓存**，减少数据库压力

### 负载均衡配置 (Nginx 示例)
```nginx
upstream pi_crypto_backend {
    server 127.0.0.1:8111;
    server 127.0.0.1:8112;
    server 127.0.0.1:8113;
}

server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://pi_crypto_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        
        # 健康检查
        health_check uri=/health interval=10s;
    }
}
```

---

## 📞 支持

遇到问题？
- 查看 [故障排查](#故障排查)
- 提交 [GitHub Issue](https://github.com/your-repo/issues)
- 联系开发团队: a29015822@gmail.com

---

**上次更新**: 2026-01-23  
**适用版本**: v1.1.0+
