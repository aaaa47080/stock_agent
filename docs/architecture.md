# CryptoMind Pi — 專案架構說明

> 快速導覽用。每次修改功能前先查這份文件，找到正確的進刀點。
> 最後更新：2026-04-06

---

## 後端（Python / FastAPI）

```
api_server.py                  # 入口：掛載所有 router、middleware、靜態檔案
api/
  deps.py                      # JWT 認證 get_current_user / get_optional_current_user
                               # Token 黑名單（file-persisted: data/revoked_tokens.json）
  utils.py                     # run_sync()、logger — 全站共用
  user_llm.py                  # resolve_user_llm_credentials() — 從 DB 拿解密 API Key
  pi_verification.py           # PI_API_BASE、PI_API_KEY 常數
  middleware/
    rate_limit.py              # slowapi 限流，Redis 優先 / 降級 memory://
  routers/
    user.py                    # 登入(/pi-sync, /dev-login)、API Key CRUD、client log
    premium.py                 # Premium 升級、Pi 付款驗證 + replay 防護
    analysis.py                # AI 分析主路由（/api/analyze）
    twstock.py                 # 台股資料
    usstock.py                 # 美股資料
    market/rest.py             # 加密貨幣市場資料
    commodity.py               # 商品資料
    forex.py                   # 外匯資料
    forum/
      posts.py                 # 論壇貼文 CRUD
      tips.py                  # 打賞功能（Pi 付款 + replay 防護）
      models.py                # 論壇相關 Pydantic models
    friends.py                 # 好友系統
    messages.py                # 私訊/對話
    notifications.py           # 推播通知
    scam_tracker/
      reports.py               # 詐騙錢包舉報（GET 公開, POST 需登入）
    admin.py                   # 管理員功能（需 require_admin）
    system.py                  # 系統設定 /api/config

core/
  database/
    user.py                    # 用戶 CRUD（upgrade_to_pro 等）
    user_api_keys.py           # API Key 加密存取（encrypt/decrypt/mask）
    connection.py              # get_connection() psycopg2
  orm/
    repositories.py            # user_repo — ORM 層用戶操作
    forum_repo.py              # 論壇 ORM
    scam_tracker_repo.py       # Scam Tracker ORM
    user_api_keys_repo.py      # API Key ORM（async）
  config.py                    # TEST_MODE、環境設定
  redis_url.py                 # resolve_redis_url()

utils/
  encryption.py                # Fernet 加密/解密 API Key、金鑰輪換（90天）
```

---

## 前端（Vanilla JS / ES Modules）

```
web/
  index.html                   # 單頁 SPA 入口，所有 tab 的容器 div
  js/
    main.js                    # ES Module 根入口，import 順序很重要
    auth.js                    # AuthManager — Pi 認證、JWT、session 管理
                               # 登入成功 dispatch: pi-auth-success
                               # 頁面恢復登入 dispatch: auth:ready
    pi-auth.js                 # Pi SDK 整合（window.Pi）
    apiKeyManager.js           # APIKeyManager — API Key 增刪改查
                               # 監聽 pi-auth-success / auth:ready → 自動刷新狀態
                               # 所有 Key 只存伺服器，GET 只回傳 masked
    nav-config.js              # NAV_ITEMS 陣列、NavPreferences（localStorage）
                               # PREFERENCES_VERSION 版本控制 migration
                               # Phase 1 起：friends/forum defaultEnabled:false
    components.js              # 動態 Tab 內容 HTML 模板 + inject 系統
    app.js                     # 全域 App 狀態、板塊選擇、UI 協調

    # Chat 模組（chat-*.js 相互依賴，不能單獨修改）
    chat-init.js               # initChat() — tab 進入點、session 清理
    chat-sessions.js           # showWelcomeScreen（含 onboarding banner）
                               # loadSessions、switchSession
    chat-analysis.js           # sendMessage() — 呼叫 /api/analyze
    chat-history.js            # 歷史記錄載入
    chat-ui.js / chat-stream.js # UI 渲染、streaming 處理

    # 板塊模組
    forum-app.js               # 論壇 UI（Phase 2）
    forum-config.js            # 論壇設定、loadPiPrices()
    friends.js                 # 好友系統 UI（Phase 2）
    premium.js                 # Premium 升級 UI
    safetyTab.js               # Scam Tracker UI

    # 工具
    llmSettings.js             # LLM 設定 UI（Key 輸入、模型選擇）
    security.js                # SecurityUtils.escapeHTML / encodeURL / createSafeLink
```

---

## 資料流：AI 分析

```
用戶在 Chat 輸入問題
  → chat-analysis.js sendMessage()
  → POST /api/analyze { message, user_provider, user_model, ... }
    ⚠️  API Key 本身不在 request body
  → analysis.py
  → user_llm.resolve_user_llm_credentials(current_user)
  → core/orm/user_api_keys_repo.get_user_api_key(user_id, provider)
  → utils/encryption.decrypt_api_key(encrypted_key)
  → 後端用解密後的 Key 呼叫 OpenAI/Gemini/etc.
  → Streaming 回傳結果給前端
```

---

## 資料流：Pi 付款

```
前端 Pi.createPayment()
  → onReadyForServerApproval(paymentId)
  → POST /api/premium/upgrade { payment_id }
  → premium.py _verify_pi_payment() → GET api.minepi.com/v2/payments/{id}
  → _record_tip_payment() / _record_used_payment()
    INSERT INTO used_payments ON CONFLICT DO NOTHING
    rowcount==0 → 409 replay 防護
  → POST api.minepi.com/v2/payments/{id}/approve (Key 認證)
  → onReadyForServerCompletion(paymentId, txid)
  → POST api.minepi.com/v2/payments/{id}/complete { txid }
```

---

## 新增 Tab 的步驟

1. `nav-config.js` — NAV_ITEMS 加新項目
2. `web/index.html` — 加 `<div id="X-tab">`
3. `components.js` — 加 HTML 模板 + injection list
4. `main.js` — 加 executeTabSwitch case + init 呼叫
5. 若有新 NAV_ITEMS：bump `PREFERENCES_VERSION`

---

## 環境設定（.env 關鍵項目）

```
JWT_SECRET_KEY          # 必填，≥32 chars
PI_API_KEY              # Pi Server API Key
API_KEY_ENCRYPTION_SECRET  # 向後兼容，推薦改用 config/api_key_encryption.json
REDIS_URL               # 選填，限流用；無 Redis 降級 memory://
TEST_MODE               # true = 跳過 Pi 付款驗證（開發用）
```

---

## Phase 規劃

```
Phase 1（目前）
  ✅ AI 分析核心（Chat + 股票 + 幣圈 + 商品 + 外匯）
  ✅ API Key 伺服器存儲 + 登入自動刷新狀態
  ✅ Onboarding banner（無 Key 時引導設定）
  ✅ friends/forum 預設隱藏（可從 Customize 手動開啟）

Phase 2（下一步）
  ○ 商品/外匯可自選標的
  ○ AI Chat 觸發跨板塊分析
  ○ 對話歷史持久化
  ○ 社群功能（論壇 + 好友）獨立品牌或開放
```
