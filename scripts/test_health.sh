#!/bin/bash

# ==============================================================================
# 健康检查测试脚本
# 用于验证生产环境部署是否正常
# ==============================================================================

set -e

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 配置
API_URL="${API_URL:-http://localhost:8111}"
TIMEOUT=5

echo "🔍 开始健康检查..."
echo "API URL: $API_URL"
echo ""

# 测试 1: 健康检查
echo -n "1. 健康检查 (/health)... "
HEALTH_RESPONSE=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$API_URL/health" || echo "000")
HTTP_CODE=$(echo "$HEALTH_RESPONSE" | tail -n1)
BODY=$(echo "$HEALTH_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 通过${NC}"
    echo "   响应: $BODY"
else
    echo -e "${RED}✗ 失败 (HTTP $HTTP_CODE)${NC}"
    exit 1
fi
echo ""

# 测试 2: 就绪检查
echo -n "2. 就绪检查 (/ready)... "
READY_RESPONSE=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$API_URL/ready" || echo "000")
HTTP_CODE=$(echo "$READY_RESPONSE" | tail -n1)
BODY=$(echo "$READY_RESPONSE" | head -n-1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 通过${NC}"
    echo "   响应: $BODY"
else
    echo -e "${YELLOW}⚠ 警告 (HTTP $HTTP_CODE)${NC}"
    echo "   部分组件未就绪: $BODY"
fi
echo ""

# 测试 3: Pi 验证端点
echo -n "3. Pi 验证 (/validation-key.txt)... "
PI_RESPONSE=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$API_URL/validation-key.txt" || echo "000")
HTTP_CODE=$(echo "$PI_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 通过${NC}"
else
    echo -e "${RED}✗ 失败 (HTTP $HTTP_CODE)${NC}"
fi
echo ""

# 测试 4: 静态文件
echo -n "4. 静态文件 (/static/index.html)... "
STATIC_RESPONSE=$(curl -s -w "\n%{http_code}" --max-time $TIMEOUT "$API_URL/static/index.html" || echo "000")
HTTP_CODE=$(echo "$STATIC_RESPONSE" | tail -n1)

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✓ 通过${NC}"
else
    echo -e "${YELLOW}⚠ 警告 (HTTP $HTTP_CODE)${NC}"
    echo "   静态文件服务可能未启用"
fi
echo ""

# 测试 5: 进程检查
echo -n "5. 进程检查... "
if [ -f "logs/gunicorn.pid" ]; then
    PID=$(cat logs/gunicorn.pid)
    if ps -p "$PID" > /dev/null 2>&1; then
        WORKER_COUNT=$(ps aux | grep "[g]unicorn.*worker" | wc -l)
        echo -e "${GREEN}✓ 运行中${NC}"
        echo "   Master PID: $PID"
        echo "   Workers: $WORKER_COUNT"
    else
        echo -e "${RED}✗ PID 文件存在但进程不存在${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠ PID 文件不存在 (可能使用开发模式)${NC}"
fi
echo ""

# 总结
echo "================================"
echo -e "${GREEN}✅ 健康检查完成${NC}"
echo "================================"
echo ""
echo "建议："
echo "- 配置 Nginx 定期调用 /health 进行健康检查"
echo "- 使用 /ready 端点进行负载均衡器的就绪检查"
echo "- 监控日志: tail -f logs/gunicorn_access.log"
