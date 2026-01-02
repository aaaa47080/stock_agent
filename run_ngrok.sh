#!/bin/bash
pkill ngrok
# 設定 Port 號
PORT=8111

echo "=========================================="
echo "🚀 正在啟動 ngrok 隧道 (Port: $PORT)..."
echo "📱 啟動後請複製 https:// 開頭的網址到 Pi Browser"
echo "=========================================="

# 檢查 ngrok 是否安裝
if ! command -v ngrok &> /dev/null
then
    echo "❌ 錯誤: 找不到 ngrok 指令。"
    echo "請先安裝 ngrok (例如: curl -s https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null && echo \"deb https://ngrok-agent.s3.amazonaws.com buster main\" | sudo tee /etc/apt/sources.list.d/ngrok.list && sudo apt update && sudo apt install ngrok)"
    exit 1
fi

# 執行 ngrok
ngrok http $PORT
