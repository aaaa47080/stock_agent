# Zeabur 部署配置
# 指定 Python 3.12.7 運行時

FROM python:3.12.7-slim

# 設置工作目錄
WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# 複製依賴文件
COPY requirements.txt .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 複製應用代碼
COPY . .

# 暴露端口（根據您的應用需求調整）
EXPOSE 8111

# 啟動命令
CMD ["python", "api_server.py"]
