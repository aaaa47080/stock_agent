#!/bin/bash
# Pi SDK 載入檢查腳本
# 用於驗證所有 HTML 頁面是否正確載入 Pi SDK

set -e

echo "=========================================="
echo "  Pi SDK 載入檢查"
echo "=========================================="
echo ""

# 不需要 Pi SDK 的頁面（靜態內容）
EXCLUDE_PAGES=(
    "web/legal/terms-of-service.html"
    "web/legal/privacy-policy.html"
    "web/legal/community-guidelines.html"
)

# 收集所有 HTML 檔案
HTML_FILES=$(find web -name "*.html" | sort)

# 檢查需要 Pi SDK 的頁面
echo "📋 檢查需要 Pi SDK 的頁面..."
echo ""

MISSING_SDK=()
FOUND_SDK=()

for html_file in $HTML_FILES; do
    # 跳過排除的頁面
    skip=false
    for exclude in "${EXCLUDE_PAGES[@]}"; do
        if [[ "$html_file" == "$exclude" ]]; then
            skip=true
            break
        fi
    done
    
    if $skip; then
        echo "⏭️  $html_file (靜態頁面，跳過)"
        continue
    fi
    
    if grep -q "sdk.minepi.com/pi-sdk.js" "$html_file" 2>/dev/null; then
        echo "✅ $html_file"
        FOUND_SDK+=("$html_file")
    else
        echo "❌ $html_file - 缺少 Pi SDK!"
        MISSING_SDK+=("$html_file")
    fi
done

echo ""
echo "=========================================="
echo "  檢查結果"
echo "=========================================="
echo "✅ 已載入 Pi SDK: ${#FOUND_SDK[@]} 個頁面"
echo "❌ 缺少 Pi SDK: ${#MISSING_SDK[@]} 個頁面"

if [ ${#MISSING_SDK[@]} -gt 0 ]; then
    echo ""
    echo "⚠️  發現缺少 Pi SDK 的頁面！請在這些頁面的 <head> 中加入："
    echo "   <script src=\"https://sdk.minepi.com/pi-sdk.js\"></script>"
    exit 1
else
    echo ""
    echo "🎉 所有頁面都已正確載入 Pi SDK！"
    exit 0
fi
