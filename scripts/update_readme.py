def update_readme(filename, is_cn):
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()
        
    status_cn = """
## 🚀 最新開發進度 (Current Development Status)

本專案已從概念驗證 (PoC) 邁向具備完整後端基礎設施的實作階段，目前已上線並穩定運作的核心模組包含：

- ✅ **多市場 AI 代理與智能路由 (Multi-Market AI Routing)**：支援**加密貨幣 (Crypto)**、**台股 (TW Stock)**、**美股 (US Stock)**。內建意圖分類模型與「單一市場快速通道 (Fast-Path)」，提供毫秒級市場判斷。
- ✅ **V4 ManagerAgent 架構**：多 Agent 協作系統，支援 Crypto、台股、美股分析，自動路由至對應專業 Agent。
- ✅ **全功能社群後端 (Forum API)**：完整建構類似 PTT 的論壇機制，包含文章發布、分頁加載、推/噓文、與 Pi 幣打賞介面。
- ✅ **平台治理與防詐追蹤 (Governance & Scam Tracker)**：已實作社群檢舉、治理投票與完整的後端管理員 API (Admin Panel)。
- ✅ **自動化端到端測試 (E2E Testing)**：整合 Playwright 進行網頁端到端測試與系統健康度監控，確保 AI 多代理人互動流程穩定。

---
"""

    status_en = """
## 🚀 Current Development Status

This project has evolved from a Proof of Concept (PoC) into a fully implemented backend infrastructure. The following core modules are currently live and stable:

- ✅ **Multi-Market AI Routing**: Full support for **Crypto**, **Taiwan Stocks (TW Stock)**, and **US Stocks (US Stock)**. Features built-in intent classification models and a "Single-Market Fast-Path" for millisecond-level market routing.
- ✅ **V4 ManagerAgent Architecture**: Multi-agent collaboration system supporting Crypto, Taiwan Stock, and US Stock analysis, with automatic routing to the corresponding specialized Agent.
- ✅ **Full-Featured Forum Backend**: A complete PTT-style forum mechanism, including post publishing, pagination, upvote/downvote, and Pi coin tipping interfaces.
- ✅ **Platform Governance & Scam Tracker**: Implemented community reporting, governance voting, and comprehensive backend Admin Panel APIs.
- ✅ **Automated E2E Testing**: Integrated Playwright for web end-to-end testing and system health monitoring to ensure stable AI multi-agent interactions.

---
"""

    insert_text = status_cn if is_cn else status_en
    
    # We want to insert it right before "## 市場機會" or "## Market Opportunity"
    marker_cn = "## 市場機會"
    marker_en = "## Market Opportunity"
    marker = marker_cn if is_cn else marker_en
    
    if marker in content:
        new_content = content.replace(marker, insert_text + "\n" + marker)
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Successfully updated {filename}")
    else:
        print(f"Failed to find insertion point '{marker}' in {filename}")

update_readme('README_CN.md', True)
update_readme('README.md', False)
