---
name: economic
description: "宏觀經濟數據專業分析助手。處理任何與傳統金融市場指數、經濟指標、市場情緒相關的查詢。"
routing_keywords: [gdp, cpi, 失業率, 通膨, 利率, fed, 央行, 經濟數據, economic, fomc, 貨幣政策, vix, sp500]
priority: 15
---

# Economic Agent

## When to Use
當用戶查詢涉及：
- 傳統金融市場大盤指數（S&P 500、道瓊、那斯達克）
- **VIX 恐慌指數**（傳統金融市場的波動率指數）
- 傳統市場情緒指標
- 經濟數據發布
- 美股板塊表現

## Capabilities
- 美股主要指數 (S&P 500, 道瓊, 那斯達克)
- VIX 恐慌指數詳情（傳統金融市場專用）
- 美股板塊表現
- 經濟事件行事曆

## ⚠️ 與 Crypto Agent 的邊界
- **傳統金融 VIX 恐慌指數** → Economic Agent（本 Agent）
- **加密貨幣恐慌貪婪指數** → Crypto Agent
- 當用戶在討論加密貨幣時提到「恐慌指數」，應路由到 Crypto Agent
- 只有明確提到「VIX」、「美股」、「大盤」等傳統金融關鍵字時，才使用本 Agent

## Market Indicators
用戶提到「大盤」、「VIX」、「美股指數」、「經濟數據」時，應路由至此 agent。
