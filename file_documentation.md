# Python 檔案功能說明

## 核心系統檔案 (Core)

1. **main.py** - 系統入口點，處理命令行參數，啟動雙市場分析流程
2. **graph.py** - LangGraph 工作流程定義，連接所有代理節點
3. **agents.py** - 定義所有 AI 代理（分析師、研究員、交易員、風險經理、基金經理）
4. **models.py** - Pydantic 數據模型定義（分析報告、辯論、交易決策等）
5. **config.py** - 系統配置和 AI 模型設置

## 數據處理檔案 (Data)

6. **data_fetcher.py** - 交易所數據獲取器（Binance/OKX）
7. **data_processor.py** - 數據處理和市場結構分析
8. **indicator_calculator.py** - 技術指標計算

## 交易功能檔案 (Trading)

9. **okx_api_connector.py** - OKX 交易所 API 連接器
10. **okx_auto_trader.py** - 自動交易執行器（如果存在）

## 介面層檔案 (Interfaces)

11. **chat_interface.py** - Gradio 聊天介面
12. **run_chat.py** - 運行聊天介面的腳本
13. **batch_analyzer_app.py** - 批量分析應用介面

## 分析工具檔案 (Analysis)

14. **crypto_screener.py** - 加密貨幣篩選器
15. **backend_analyzer.py** - 後台分析引擎（生成 JSON 格式決策）
16. **batch_analyzer.py** - 批量分析器（多幣種同時分析）

## 工具與輔助檔案 (Utils)

17. **utils.py** - 通用工具函數
18. **retry_utils.py** - 重試機制工具
19. **llm_client.py** - LLM 客戶端管理（OpenAI/OpenRouter/Google Gemini）
20. **llm_cache.py** - LLM 緩存機制
21. **settings.py** - 系統設置參數

## 測試與開發檔案 (Testing/Development)

22. **test_backend_analyzer.py** - 後台分析器測試
23. **validate_backend_json.py** - JSON 驗證工具
24. **list_gemini_models.py** - 列出可用的 Gemini 模型

## 其他檔案 (Others)

25. **NEWS_SOURCES_GUIDE.md** - 新聞源指南（非 Python 檔案）
26. **record.txt** - 系統記錄文本
27. **record_fix_log.txt** - 修復日誌
28. **trading_decisions_*.json** - 交易決策存檔（非 Python 檔案）

# 功能分類與建議的資料夾結構

## 建議的資料夾結構：

```
stock_agent/
├── core/                     # 核心系統檔案
│   ├── main.py
│   ├── graph.py
│   ├── agents.py
│   ├── models.py
│   └── config.py
├── data/                     # 數據處理相關
│   ├── data_fetcher.py
│   ├── data_processor.py
│   └── indicator_calculator.py
├── trading/                  # 交易相關功能
│   ├── okx_api_connector.py
│   └── okx_auto_trader.py
├── interfaces/               # 介面相關
│   ├── chat_interface.py
│   ├── run_chat.py
│   └── batch_analyzer_app.py
├── analysis/                 # 分析工具
│   ├── crypto_screener.py
│   ├── backend_analyzer.py
│   └── batch_analyzer.py
├── utils/                    # 工具函數
│   ├── utils.py
│   ├── retry_utils.py
│   ├── llm_client.py
│   ├── llm_cache.py
│   └── settings.py
├── tests/                    # 測試檔案
│   ├── test_backend_analyzer.py
│   ├── validate_backend_json.py
│   └── other_test_files.py
└── development/              # 開發工具
    ├── list_gemini_models.py
    ├── record.txt
    └── record_fix_log.txt
```