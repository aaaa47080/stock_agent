# Zeabur 部署配置
# 使用 Python 3.13 運行時以匹配 Zeabur 要求

FROM python:3.13-slim

LABEL "language"="python"
LABEL "framework"="fastapi"

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .

# 安裝 Python 依賴 (gunicorn 已在 requirements.txt 中)
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用代碼
COPY . .

# 創建日誌目錄並設置權限（備用，主要日誌已輸出到 stdout/stderr）
RUN mkdir -p /app/logs && chmod 777 /app/logs

# 暴露端口
EXPOSE 8111

# 使用 Gunicorn 啟動 (生產環境)
CMD ["gunicorn", "--config", "gunicorn.conf.py", "api_server:app"]
