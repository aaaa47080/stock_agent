# CLAUDE.md — CryptoMind Pi DApp

**專案負責人：DANNY**｜所有重大決策由 DANNY 確認。

---

## 專案簡介

**Pi Crypto Insight** — AI 驅動的加密貨幣分析 × 社群生態系統。

| 層次 | 技術 |
|------|------|
| Backend | FastAPI + SQLAlchemy + PostgreSQL |
| Frontend | Vanilla JS (ES Modules) |
| AI | LangGraph + OpenAI |
| Testing | pytest + Playwright |

---

## 重要原則：簡單問題用簡單解法

> 不要為了看起來「工程感強」而過度設計。一件簡單的事情就用最直接的方式做。
> - 加一個欄位？直接加，不要抽象成 factory。
> - 改一段文字？直接改，不要建 config 系統。
> - 修一個 bug？找到根因，最小改動修掉。

---

## 自動執行（不需詢問）

以下類型的修改，Claude 可直接動手：

- 語法錯誤、明顯 bug 的修正
- 加 `try-catch`、null check 等防禦性處理
- API endpoint 的小修正（不改行為）
- 前端錯誤訊息改善
- JS `import` 語句補齊（ES Modules）
- CSS / UI 調整（不影響功能）
- SQLAlchemy subquery 修正
- 測試模式 / sandbox 設定修正

## 必須先問（不可自行決定）

- 認證 / 授權邏輯
- 資料庫 Schema 異動
- 任何付款 / 金流相關程式碼
- 使用者資料處理方式
- 新增套件依賴
- Pi SDK 整合修改
- Pi 付款流程調整

---

## 常用指令

```bash
# 啟動後端
cd D:/okx/stock_agent && python api_server.py

# 確認 8080 port 狀態
netstat -ano | grep 8080

# 終止指定 PID
python -c "import os,signal; os.kill(<PID>, signal.SIGTERM)"

# 檢查 JS 語法
node --check web/js/<file>.js

# 執行測試
pytest                              # 全部
pytest tests/<file>.py              # 單一檔案
pytest -m unit                      # 只跑 unit tests
pytest -m e2e                       # E2E browser tests

# Python linting
ruff check .
ruff format .

# Dev 登入（測試用）
# POST /api/user/dev-login
# body: {"test_mode_confirmation": "I_UNDERSTAND_THE_RISKS"}
```

---

## 重要路徑

```
api_server.py              # 後端入口
api/routers/               # API 路由層
  user.py / forum/ / friends.py / premium.py ...

web/index.html             # 前端入口
web/js/main.js             # ES Modules 入口
web/js/
  auth.js                  # 認證
  pi-auth.js               # Pi SDK 整合
  forum-app.js             # 論壇
  friends.js               # 好友
  premium.js               # 付費功能（依賴 forum-config.js 的 loadPiPrices）
  forum-config.js          # 論壇設定 & Pi 價格

tests/                     # pytest 測試
pw_test/                   # Playwright E2E 測試
```

---

## Browser 測試流程

1. 啟動伺服器：`python api_server.py`
2. 用 Playwright MCP 自動化瀏覽器
3. Dev 登入：`POST /api/user/dev-login`
4. 測試各 tab：`#friends`、`#forum`、`#settings`
5. 發現問題 → 確認是否在「自動執行」範圍 → 直接修或先問

---

## 回答風格

- **直接給解法**，不要先寫一大段背景說明
- **先修再說**（符合自動執行規則時），不要問「你確定嗎？」
- 如果有多種做法，**先推薦最簡單的**，再提其他選項
- 程式碼修改盡量給 diff，不要貼整個檔案
