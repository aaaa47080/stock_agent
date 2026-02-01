#!/bin/bash
PORT=8080

# 找出佔用 Port 的 PID
PID=$(lsof -t -i:$PORT)

if [ -z "$PID" ]; then
    echo "✅ Port $PORT 目前沒有被佔用。"
else
    echo "⚠️  發現 Port $PORT 被進程 $PID 佔用"
    echo "🔪 正在強制關閉..."
    kill -9 $PID
    
    # 二次確認
    sleep 1
    CHECK=$(lsof -t -i:$PORT)
    if [ -z "$CHECK" ]; then
        echo "✅ 成功關閉！Port $PORT 現在是自由的。"
    else
        echo "❌ 關閉失敗，請手動檢查。"
    fi
fi
