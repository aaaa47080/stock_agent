#!/bin/bash

echo "======================================"
echo "Git 提交建议"
echo "======================================"
echo ""

# 显示当前状态
echo "📊 当前 Git 状态："
git status --short
echo ""

# 提交建议
echo "📝 建议的提交命令："
echo ""
echo "git commit -m \"chore: 清理项目文件并重新组织目录结构

- 删除日志、数据库、缓存文件（约 35MB）
- 删除临时和测试脚本
- 删除 AI codebook 目录
- 将脚本文件移动到 scripts/ 目录
- 将文档文件移动到 docs/ 目录
- 更新 .gitignore 添加更全面的忽略规则\""

echo ""
echo "======================================"
echo "执行此命令进行提交吗？(y/n)"
read -r confirm

if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
    git commit -m "chore: 清理项目文件并重新组织目录结构

- 删除日志、数据库、缓存文件（约 35MB）
- 删除临时和测试脚本
- 删除 AI codebook 目录
- 将脚本文件移动到 scripts/ 目录
- 将文档文件移动到 docs/ 目录
- 更新 .gitignore 添加更全面的忽略规则"
    
    echo ""
    echo "✅ 提交成功！"
    echo ""
    echo "现在推送到 GitHub？(y/n)"
    read -r push_confirm
    
    if [ "$push_confirm" = "y" ] || [ "$push_confirm" = "Y" ]; then
        git push origin main
        echo ""
        echo "✅ 已推送到 GitHub！"
    else
        echo "稍后可以使用以下命令推送："
        echo "git push origin main"
    fi
else
    echo "已取消提交。"
fi
