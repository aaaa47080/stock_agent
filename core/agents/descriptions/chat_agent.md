---
name: chat
description: "一般對話助手。處理閒聊、問候、平台使用說明、以及無法歸類到其他專業 agent 的查詢。"
routing_keywords: [閒聊, 打招呼, 你好, hi, hello, 天氣, 時間]
priority: 99
---

# Chat Agent

## When to Use
當用戶查詢：
- 閒聊、打招呼
- 詢問平台功能
- 一般知識問題
- 無法識別市場類型的模糊查詢
- 需要 HITL（人機互動）澄清時的 fallback

## Capabilities
- 基本對話
- 平台功能說明
- 簡單查詢（如時間、基本價格）
- 網絡搜索

## Priority
此 agent 優先級最低（priority=99），僅在無法匹配其他專業 agent 時使用。
