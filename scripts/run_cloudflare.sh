#!/bin/bash
# ========================================
# Cloudflare Tunnel 啟動腳本
# 將本地 8080 端口暴露到公網
# ========================================

PORT=8080
TUNNEL_NAME="pi-crypto"

echo "=========================================="
echo "  Cloudflare Tunnel 啟動器"
echo "=========================================="
echo ""

# 檢查 cloudflared 是否安裝
if ! command -v cloudflared &> /dev/null; then
    echo "❌ cloudflared 未安裝"
    echo ""
    echo "請先安裝 cloudflared:"
    echo "  Ubuntu/Debian: sudo apt install cloudflared"
    echo "  macOS: brew install cloudflared"
    echo "  或從 https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ 下載"
    exit 1
fi

echo "✅ cloudflared 已安裝: $(cloudflared --version)"
echo ""

# 檢查本地服務是否運行
if ! curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
    echo "⚠️  警告: 本地服務 (port $PORT) 可能未運行"
    echo "   請確認已執行: ./start_production.sh 或 python api_server.py"
    echo ""
fi

# 檢查是否有配置文件
CONFIG_FILE="$HOME/.cloudflared/config.yml"
if [ -f "$CONFIG_FILE" ]; then
    echo "📁 使用配置文件: $CONFIG_FILE"
    echo ""
    echo "啟動已配置的 Tunnel..."
    cloudflared tunnel run $TUNNEL_NAME
else
    echo "📁 未找到配置文件，使用快速模式"
    echo ""
    echo "啟動臨時 Tunnel (會生成隨機 URL)..."
    echo ""
    cloudflared tunnel --url http://localhost:$PORT
fi
