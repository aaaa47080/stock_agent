# Pi Crypto Insight — 改進計畫

> 基於 6 個 Agent 審查報告（後端 Python、前端 JS/CSS、資料庫、部署/CI-CD、測試策略、AI Agent）的整合改進計畫。
> 
> **原則**: 每個 Phase 可獨立完成、commit + push。已修復項目不列入。

> **狀態: 全部完成** — 所有 7 個 Phase 均已完成，CI 驗證通過 (green)。最後確認日期: 2026-03-21。

---

## Phase 1: 安全漏洞修復 (Critical Security Fixes) ✅ 完成
> 預估時間: 6–8 小時 | 優先級: P0 | **已完成 — 所有任務驗證通過**

### [x] Task1.1: 修復 IDOR 漏洞 — 任何登入用戶可刪除/置頂他人對話
- **檔案**: `api/routers/analysis.py:48,54`
- **問題**: `delete_user_session` 和 `pin_user_session` 用 `dependencies=[Depends(get_current_user)]` 僅驗證登入身份，但 endpoint 內未驗證 session 是否屬於當前用戶。任何已登入用戶可傳入任意 `session_id` 刪除/置頂他人對話。
- **修改內容**:
  1. 將 `dependencies` 改為 `Depends` 注入到函數參數中取得 `current_user`：
     ```python
     @router.delete("/api/chat/sessions/{session_id}")
     async def delete_user_session(
         session_id: str,
         current_user: dict = Depends(get_current_user),
     ):
     ```
  2. 在 `delete_session` 呼叫前，先透過 `get_sessions(user_id=current_user["user_id"])` 確認該 session 屬於當前用戶，或直接在 DB query 中加入 `user_id` 條件。
  3. 同樣修復 `pin_user_session`，將 `dependencies` 改為參數注入，並加入 owner 驗證。
- **驗證**:
  - 寫一個測試：用戶 A 嘗試刪除用戶 B 的 session → 預期 403
  - 用戶 A 刪除自己的 session → 預期 200

### [x] Task1.2: Admin API Key 時序攻擊修復
- **檔案**: `api/routers/admin/auth.py:20`
- **問題**: `x_admin_key != key` 使用 Python 字串直接比對，會因為字串長度不同產生時序差異，攻擊者可透過時間推測正確 key。
- **修改內容**:
  ```python
  import hmac
  
  if not x_admin_key or not hmac.compare_digest(x_admin_key, key):
      raise HTTPException(status_code=403, detail="Invalid or missing admin API key")
  ```
- **驗證**: 手動測試 admin endpoint 確認功能正常；ruff check 通過

### [x] Task1.3: TEST_MODE 洩漏完整用戶資料
- **檔案**: `api/routers/system.py:222-223`
- **問題**: `response["test_user"] = core_config.TEST_USER` 將完整測試用戶資料（可能包含 uid、pi_uid 等）暴露到 API 回應中。
- **修改內容**:
  ```python
  if core_config.TEST_MODE:
      response["test_user"] = {
          "user_id": core_config.TEST_USER.get("uid"),
          "username": core_config.TEST_USER.get("username"),
      }
  ```
  僅回傳最小必要資訊，隱藏敏感欄位（如 pi_uid、token 等）。
- **驗證**: `curl /api/system/config` 確認 test_user 欄位只包含 user_id 和 username

### [x] Task1.4: 前端 Double `.json()` 解析 Bug
- **檔案**: `web/js/auth.js:565,326`
- **問題**: 非 Pi Browser 登入路徑中，對 response 呼叫了兩次 `.json()`，導致 `TypeError: Already read body` 崩潰。
- **修改內容**:
  1. 找到兩處 double `.json()` 呼叫，將第二次改為使用已解析的物件。
  2. 例如：
     ```javascript
     // Before (buggy):
     const data = await response.json();
     const result = await response.json();  // 第二次會報錯
     
     // After (fixed):
     const data = await response.json();
     const result = data;  // 直接使用已解析的結果
     ```
- **驗證**: 在非 Pi Browser 環境測試登入流程，確認不崩潰

### [x] Task1.5: DebugLog 在生產環境直接 console.log
- **檔案**: `web/js/auth.js:5-28`
- **問題**: `DebugLog.send()` 無條件執行 `console.log()`，即使不在 DEBUG_MODE。生產環境用戶開啟 DevTools 可看到敏感資訊。
- **修改內容**:
  ```javascript
  const DebugLog = {
      send(level, message, data = null) {
          if (window.APP_CONFIG && window.APP_CONFIG.DEBUG_MODE !== true) {
              return;  // 生產環境完全靜默
          }
          console.log(`[${level.toUpperCase()}] ${message}`, data);
          // ... fetch to server ...
      },
      // ...
  };
  ```
- **驗證**: 設定 `APP_CONFIG.DEBUG_MODE = false`，確認 console 中無 DebugLog 輸出

### [x] Task1.6: CSP `unsafe-inline` 改善
- **檔案**: `web/index.html:7`
- **問題**: `script-src 'unsafe-inline'` 允許任意 inline script 執行，大幅削弱 XSS 防護。完全移除需要重大架構變更（所有 inline event handler 需改為 addEventListener），先做降級處理。
- **修改內容**:
  1. **短期**: 加入 `nonce` 支援（保留 `unsafe-inline` 作為 fallback）：
     ```html
     <meta http-equiv="Content-Security-Policy" 
           content="default-src 'self'; script-src 'self' 'unsafe-inline' 'nonce-RANDOM' ...">
     ```
  2. **中期**（本 Phase 內）: 在 `api_server.py` 的 HTML response 中注入 nonce，將 `index.html` 的 CSP 改為引用 nonce。
  3. **長期**（記錄為後續 Task）: 將所有 inline script 移至外部 `.js` 檔案，完全移除 `unsafe-inline`。
- **驗證**: CSP violation 不影響正常功能；無 nonce 的 inline script 被阻擋

### [x] Task1.7: innerHTML XSS 修復
- **檔案**: `web/js/app.js:168,254`
- **問題**: `innerHTML` 插入未經轉義的值（如 `config.icon`、`confirmText`），若這些值來自用戶輸入或 API 回應，可導致 XSS。
- **修改內容**:
  1. 對 `app.js:168` 的 `config.icon`：因為 `icon` 來自硬編碼的 `iconConfig` 物件，風險較低，但應加入驗證：
     ```javascript
     const allowedIcons = ['alert-triangle', 'check-circle', 'info', 'x-circle'];
     const safeIcon = allowedIcons.includes(config.icon) ? config.icon : 'info';
     iconEl.innerHTML = `<i data-lucide="${safeIcon}" class="w-8 h-8 ${config.color}"></i>`;
     ```
  2. 對 `app.js:254` 的 `confirmText`：改用 `textContent` 或 DOM API：
     ```javascript
     buttonsEl.innerHTML = '';  // 清空
     const btn = document.createElement('button');
     btn.id = 'confirm-modal-ok';
     btn.className = '...';
     btn.textContent = confirmText;  // 安全：textContent 自動轉義
     buttonsEl.appendChild(btn);
     ```
  3. 全域搜索其他 `innerHTML` 使用處，逐一審查。
- **驗證**: 搜尋所有 `innerHTML` 使用處，確認無用戶輸入直接插入

---

## Phase 2: 後端品質改善 (Backend Quality) ✅ 完成
> 預估時間: 5–7 小時 | 優先級: P1 | **已完成 — 所有任務驗證通過**

### [x] Task2.1: SSL 驗證恢复 + 環境變數控制
- **檔案**: `api/utils.py:40`
- **問題**: `verify=False` 全域關閉 SSL 驗證，存在中間人攻擊風險。
- **修改內容**:
  ```python
  _ssl_verify = os.getenv("SSL_VERIFY", "true").lower() in ("true", "1", "yes")
  
  _shared_http_client = httpx.AsyncClient(
      verify=_ssl_verify,  # 預設開啟，僅在開發環境可透過環境變數關閉
      ...
  )
  ```
- **驗證**: 預設啟動後 `verify=True`；設定 `SSL_VERIFY=false` 後可關閉

### [x] Task2.2: error_handling 裝飾器支援 async 函數
- **檔案**: `core/error_handling.py:14-50`
- **問題**: `log_and_suppress` 和 `safe_execute` 裝飾器的 wrapper 是同步函數，呼叫 async 函數時會回傳 coroutine 而非 await 結果。
- **修改內容**:
  ```python
  import asyncio
  import inspect
  
  def log_and_suppress(error_message, level="warning", raise_on=None):
      def decorator(func):
          @wraps(func)
          async def async_wrapper(*args, **kwargs):
              try:
                  return await func(*args, **kwargs)
              except Exception as e:
                  if raise_on and isinstance(e, raise_on):
                      raise
                  log_func = getattr(logger, level, logger.warning)
                  log_func(f"{error_message}: {type(e).__name__}: {e}")
                  return None
          
          @wraps(func)
          def sync_wrapper(*args, **kwargs):
              try:
                  return func(*args, **kwargs)
              except Exception as e:
                  if raise_on and isinstance(e, raise_on):
                      raise
                  log_func = getattr(logger, level, logger.warning)
                  log_func(f"{error_message}: {type(e).__name__}: {e}")
                  return None
          
          return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
      return decorator
  ```
  對 `safe_execute` 做同樣修改。
- **驗證**: 寫一個 async 測試用例使用 `@log_and_suppress` 裝飾器，確認能正確捕獲異常

### [x] Task2.3: API Response 格式統一化
- **檔案**: 多個 router 檔案
- **問題**: 部分 endpoint 回傳 `{"sessions": [...]}` 無 `success` 欄位，部分回傳 `APIResponse(success=True, data=...)`。
- **修改內容**:
  1. 在 `api/models.py` 或新建 `api/response.py` 定義統一格式：
     ```python
     class APIResponse(BaseModel):
         success: bool = True
         data: Optional[Any] = None
         message: Optional[str] = None
         error: Optional[str] = None
     ```
  2. 逐步統一所有 router 的回應格式（優先修復 `analysis.py` 的 sessions/history endpoints）。
  3. 不需要一次改完所有 router，本 Task 先修 `analysis.py` 和 `system.py` 作為示範。
- **驗證**: `ruff check` 通過；手動呼叫修復的 endpoints 確認回應格式

### [x] Task2.4: `get_current_user` 回傳型別改善 + TEST_MODE 安全加固
- **檔案**: `api/deps.py:143-216`
- **問題**:
  1. `get_current_user` 回傳 `dict` 無明確型別，呼叫端無法知道有哪些欄位。
  2. TEST_MODE 允許任意 `test-user-xxx` raw token 作為身份。
- **修改內容**:
  1. 定義 `CurrentUser` TypedDict：
     ```python
     from typing import TypedDict
     
     class CurrentUser(TypedDict):
         user_id: str
         username: str
         pi_uid: Optional[str]
         is_premium: bool
         membership_tier: str
         role: str
         is_active: bool
         created_at: str
     ```
  2. 將 `get_current_user` 回傳型別改為 `-> CurrentUser`。
  3. TEST_MODE raw token 限制：僅允許白名單中的 test user IDs（從環境變數讀取）：
     ```python
     ALLOWED_TEST_USERS = os.getenv("ALLOWED_TEST_USERS", "test-user-001").split(",")
     if TEST_MODE and token in ALLOWED_TEST_USERS:
         user_id = token
     ```
- **驗證**: 傳入不在白名單的 raw token → 預期 401

### [x] Task2.5: `run_sync` 加入 type annotations
- **檔案**: `api/utils.py:10`
- **修改內容**:
  ```python
  from typing import Any, Coroutine, TypeVar
  
  T = TypeVar("T")
  
  async def run_sync(fn: Any, *args: Any) -> Any:
      """Run a synchronous DB/IO function in the thread executor (non-blocking)."""
      return await asyncio.get_running_loop().run_in_executor(None, fn, *args)
  ```
- **驗證**: `ruff check` 通過

### [x] Task2.6: `QueryRequest.user_api_key` 格式驗證
- **檔案**: `api/models.py:18`
- **問題**: `user_api_key: str` 無格式驗證，任何字串都能通過。
- **修改內容**:
  ```python
  from pydantic import field_validator
  
  class QueryRequest(BaseModel):
      user_api_key: str
      
      @field_validator("user_api_key")
      @classmethod
      def validate_api_key(cls, v: str) -> str:
          v = v.strip()
          if len(v) < 10:
              raise ValueError("API key too short")
          if not v.isprintable():
              raise ValueError("API key contains invalid characters")
          return v
  ```
- **驗證**: 傳入短字串或含特殊字元的 API key → 預期 422 驗證錯誤

### [x] Task2.7: `model_config.py` 加入 type hints
- **檔案**: `core/model_config.py:42-52`
- **修改內容**:
  ```python
  from typing import Any, Dict, List
  
  def get_available_models(provider: str) -> List[Dict[str, str]]:
      ...
  
  def get_default_model(provider: str) -> str:
      ...
  ```
- **驗證**: `ruff check` 通過

### [x] Task2.8: `/api/settings/update` 不再直接寫入 `.env` 檔案
- **檔案**: `api/routers/system.py:280-297`、`api/utils.py:68-104`
- **問題**: API key 直接寫入 `.env` 檔案，若 process crash 可能寫入不完整內容導致配置損壞。且寫入 `.env` 在多實例部署時不安全。
- **修改內容**:
  1. 短期：將 `update_env_file` 加入檔案鎖和原子寫入：
     ```python
     import tempfile
     
     def update_env_file(keys, project_root):
         # 寫入臨時檔案再 rename，確保原子性
         with tempfile.NamedTemporaryFile(
             mode='w', suffix='.tmp', dir=project_root, delete=False
         ) as tmp:
             tmp.writelines(new_lines)
         os.replace(tmp.name, env_path)  # 原子操作
     ```
  2. 長期（記錄為 TODO）：API key 應存入資料庫加密儲存，而非 `.env` 檔案。
- **驗證**: 呼叫 `/api/settings/update` 後 `.env` 檔案格式完整

### [x] Task2.9: Readiness check 加入真實資料庫檢查
- **檔案**: `api_server.py:438-443`
- **問題**: `components["database"] = True` 是硬編碼，永遠回傳 True。
- **修改內容**:
  ```python
  # 檢查數據庫
  try:
      from core.database import get_db_connection
      conn = await run_sync(lambda: get_db_connection())
      conn.execute("SELECT 1")
      conn.close()
      components["database"] = True
  except Exception:
      components["database"] = False
      ready = False
  ```
- **驗證**: 停止 PostgreSQL 後，`/ready` 回傳 503

### [x] Task2.10: 錯誤訊息洩漏內部細節
- **檔案**: `api/routers/analysis.py:276` (附近區域)
- **問題**: 異常時直接將 `str(e)` 回傳給客戶端，可能包含 SQL 語句、檔案路徑等內部資訊。
- **修改內容**:
  ```python
  except Exception as e:
      logger.error(f"Analysis failed: {e}", exc_info=True)
      raise HTTPException(
          status_code=500,
          detail="Internal server error. Please try again."
      )
  ```
- **驗證**: 觸發一個內部錯誤，確認回應不包含 stack trace 或 SQL 語句

### [x] Task2.11: `governance.py` 無意義的 `create_report(None, ...)` 第一參數
- **檔案**: `api/routers/governance.py:83`
- **修改內容**: 檢查 `create_report` 函數簽名，如果第一個參數確實無用，移除該參數或改為 keyword-only argument。更新所有呼叫處。
- **驗證**: `ruff check` 通過；手動測試举报功能

---

## Phase 3: 前端品質改善 (Frontend Quality) ✅ 完成
> 預估時間: 5–7 小時 | 優先級: P1 | **已完成 — 所有任務驗證通過**

### [x] Task3.1: 清除所有不受控的 console.log
- **檔案**:
  - `web/js/apiKeyManager.js:367,123`
  - `web/js/forum-app.js` (30+ 處)
  - `web/js/messages.js` (多處)
  - `web/index.html:98` (殘留 console.log)
- **問題**: 數十個 `console.log` 不受 `DEBUG_MODE` 控制，生產環境暴露除錯資訊。
- **修改內容**:
  1. 建立統一的 console wrapper（已有 `DebugLog`，但只限 auth.js 使用）：
     ```javascript
     // web/js/logger.js (已存在，確認是否足夠)
     // 若不足，擴展為全域 window.debugLog
     ```
  2. 全域替換所有裸 `console.log` 為條件式輸出：
     ```javascript
     // Before:
     console.log('fetching data:', data);
     // After:
     window.APP_CONFIG?.DEBUG_MODE && console.log('fetching data:', data);
     ```
  3. `console.error` 和 `console.warn` 保留（這些是合理的前端錯誤報告）。
- **驗證**: `npx eslint web/js/` 確認無 `no-console` 警告（除 error/warn 外）

### [x] Task3.2: 硬編碼中文走 i18n — Error Modal
- **檔案**: `web/js/app.js:584-610`
- **問題**: Error modal 中的「建議解決方案」、「檢查 API Key 是否正確設定」等字串硬編碼中文。
- **修改內容**:
  1. 在 `i18n` 資源中加入以下 key：
     ```json
     // zh-TW
     "error.suggestion_title": "💡 建議解決方案:",
     "error.check_api_key": "檢查 API Key 是否正確設定",
     "error.check_balance": "確認您的 Google/OpenAI 帳戶餘額是否充足",
     "error.try_other_provider": "嘗試切換其他 AI 提供商 (如 OpenRouter)",
     "error.go_settings": "前往設定檢查金鑰"
     ```
  2. 將 `app.js` 中的硬編碼字串替換為 `i18next.t('error.xxx')`。
- **驗證**: 切換語言為英文，確認 error modal 文字跟隨切換

### [x] Task3.3: 硬編碼中文走 i18n — Auth Toast + 其他
- **檔案**:
  - `web/js/auth.js:170` (Toast 字串)
  - `web/js/auth.js:707,965` (其他硬編碼中文)
  - `web/js/app.js:267,270` (「取消」「確認」按鈕)
- **修改內容**:
  1. 擴展 i18n 資源，加入所有硬編碼中文字串的 key。
  2. 全域替換為 `i18next.t()` 呼叫。
  3. 特別注意 `app.js:267,270` 的「取消」「確認」按鈕字串。
- **驗證**: 切換語言確認所有 UI 文字跟隨切換

### [x] Task3.4: 原生 alert/confirm 替換為自訂 modal
- **檔案**: `web/js/spa.js:501,526`
- **問題**: 使用原生 `alert()` 和 `confirm()`，與整體 UI 風格不一致，且無法 i18n。
- **修改內容**:
  1. `spa.js:501` 的 `alert(...)` → 改用 `showToast()` 或自訂 modal。
  2. `spa.js:526` 附近的 `confirm(...)` → 改用 `app.js` 中已有的 `showConfirm()` 方法。
  3. 搜尋所有 JS 檔案中的 `alert(` 和 `confirm(` 呼叫，確保無遺漏。
- **驗證**: 全域搜索 `alert(` 和 `confirm(`，確認無殘留（排除 `showToast` 等自訂方法）

### [x] Task3.5: i18n `zh-CN` 語言代碼支援
- **檔案**: `web/js/i18n.js:23-24`
- **問題**: 未處理 `zh-CN` 語言代碼，大陸用戶可能看到英文而非中文。
- **修改內容**:
  ```javascript
  // 語言代碼映射
  const LANGUAGE_MAP = {
      'zh-TW': 'zh-TW',
      'zh-CN': 'zh-TW',  // 大陸用戶使用繁體中文資源（或建立 zh-CN 資源）
      'zh': 'zh-TW',
  };
  
  const resolvedLang = LANGUAGE_MAP[language] || language;
  ```
- **驗證`: 設定 `navigator.language = 'zh-CN'`，確認顯示中文

### [x] Task3.6: i18n `escapeValue: false` 風險評估
- **檔案**: `web/js/i18n.js:98`
- **問題**: `escapeValue: false` 禁用 i18next 的 HTML 轉義，若翻譯字串來自不可信來源，有 XSS 風險。
- **修改內容**:
  1. 評估：目前翻譯資源是前端硬編碼的，風險較低。
  2. 但仍建議改為 `escapeValue: true`，然後在需要 HTML 的地方使用 `i18next.t('key', {interpolation: {escapeValue: false}})` 做局部覆蓋。
  3. 或者保持 `false` 但加入註解說明原因：
     ```javascript
     // escapeValue: false — 翻譯資源為前端硬編碼，非來自後端，風險可控
     // 若未來支援後端翻譯載入，需重新評估此設定
     ```
- **驗證**: 確認所有 i18n 字串在頁面上正確顯示

### [x] Task3.7: CSS `@import` 阻塞渲染優化
- **檔案**: `web/styles.css:1`
- **問題**: `@import` 在 CSS 頂部會阻塞渲染，且可能重複載入字體。
- **修改內容**:
  1. 將 `@import` 改為 HTML `<link>` 標籤（讓瀏覽器平行載入）：
     ```html
     <!-- 在 index.html <head> 中 -->
     <link rel="stylesheet" href="/path/to/external.css">
     ```
  2. 或使用 `@import` 的 `supports()` 包裹以降級處理。
  3. 確認字體只載入一次。
- **驗證**: Chrome DevTools Network 面板確認無重複字體請求；Lighthouse Performance 分數提升

### [x] Task3.8: CSS `@keyframes fadeIn` 重複定義清理
- **檔案**: `web/styles.css:165,256`
- **修改內容**: 刪除重複的 `@keyframes fadeIn` 定義，保留一個。
- **驗證`: 頁面動畫正常運作

### [x] Task3.9: `init.js` vs `spa.js` 初始化邏輯重複
- **檔案**: `web/js/init.js`、`web/js/spa.js`
- **問題**: 兩個檔案有重複的初始化邏輯，可能導致事件監聽器重複綁定。
- **修改內容**:
  1. 審查兩個檔案的初始化邏輯，找出重複部分。
  2. 將共用的初始化邏輯集中到 `init.js`。
  3. `spa.js` 只負責 SPA 路由相關的初始化。
- **驗證`: 頁面載入無 console 錯誤；功能正常

### [x] Task3.10: `auth.js` 拆分（1204 行過大）
- **檔案**: `web/js/auth.js`
- **問題**: 1204 行單檔，涵蓋登入、註冊、Pi Auth、Token 管理、Profile 等功能，難以維護。
- **修改內容**:
  1. 拆分為模組：
     - `web/js/auth/core.js` — Token 管理、用戶狀態
     - `web/js/auth/login.js` — 登入/註冊流程
     - `web/js/auth/pi-auth.js` — Pi Network 認證
     - `web/js/auth/profile.js` — 個人資料管理
  2. `auth.js` 作為入口點，re-export 公開 API。
  3. 在 `index.html` 中按順序引入。
- **驗證`: 所有登入/註冊/Pi Auth 功能正常；`ruff check` 通過

---

## Phase 4: 資料庫改善 (Database) ✅ 完成
> 預估時間: 5–7 小時 | 優先級: P1 | **已完成 — 所有任務驗證通過**

### [x] Task4.1: Alembic `target_metadata` 修復
- **檔案**: `alembic/env.py:38`
- **問題**: `target_metadata = None` 導致 `alembic revision --autogenerate` 無法偵測模型變更，migration 自動生成完全失效。
- **修改內容**:
  ```python
  # 在 import 區域加入
  from core.orm.models import Base
  
  target_metadata = Base.metadata
  ```
- **驗證**: 執行 `alembic revision --autogenerate -m "test"` 確認能偵測到模型（執行後可丟棄該 migration）

### [x] Task4.2: Migration 鏈衝突修復
- **檔案**: `alembic/versions/`
- **問題**: 存在兩條獨立的 migration 鏈：
  - 鏈 1: `001_baseline_schema.py` → `002_content_reports_columns.py`
  - 鏈 2: `4107b7e75608_initial_schema_baseline.py` → `92a35ecee1cf_add_user_api_keys_table.py`
  
  兩條鏈都無 `down_revision` 指向同一個 base，導致 Alembic 無法判斷哪條是正確的。
- **修改內容**:
  1. 確認哪條鏈是「真相來源」（檢查 `alembic_version` 表的當前版本）。
  2. 將非活動鏈的 migration 標記為已合併或刪除。
  3. 確保只剩一條線性的 migration 鏈。
  4. 在資料庫中確認 `alembic_version` 指向正確的 head。
- **驗證**: `alembic heads` 只回傳一個版本；`alembic current` 顯示正確版本

### [x] Task4.3: User model 加入 `deleted_at` 軟刪除
- **檔案**: `core/orm/models.py:30-49`
- **問題**: User model 缺 `deleted_at` 欄位，無法實現軟刪除。
- **修改內容**:
  ```python
  class User(Base):
      # ... 現有欄位 ...
      deleted_at: Mapped[Optional[datetime]] = mapped_column(
          TIMESTAMP(timezone=True), nullable=True
      )
  ```
  2. 建立對應的 Alembic migration：
     ```bash
     alembic revision --autogenerate -m "add_user_deleted_at"
     ```
  3. 在 `auto_migrate.py` 中也加入此欄位的自動偵測。
- **驗證`: Migration 成功執行；`deleted_at` 欄位存在

### [x] Task4.4: Friendship table 加入 UniqueConstraint
- **檔案**: `core/orm/models.py:189-214`
- **問題**: 缺少 `(user_id, friend_id)` 的 UniqueConstraint，可能產生重複的好友關係。
- **修改內容**:
  ```python
  from sqlalchemy import UniqueConstraint
  
  class Friendship(Base):
      # ... 現有欄位 ...
      
      __table_args__ = (
          UniqueConstraint("user_id", "friend_id", name="uq_friendship_pair"),
          Index("idx_friendships_user_id", "user_id"),
          Index("idx_friendships_friend_id", "friend_id"),
          Index("idx_friendships_status", "status"),
      )
  ```
- **驗證`: 嘗試插入重複的 (user_id, friend_id) → 預期 IntegrityError

### [x] Task4.5: DmConversation 加入 UniqueConstraint
- **檔案**: `core/orm/models.py:241-262`
- **問題**: 缺少 `(user1_id, user2_id)` 的 UniqueConstraint，可能產生重複的對話。
- **修改內容**:
  ```python
  class DmConversation(Base):
      # ... 現有欄位 ...
      
      __table_args__ = (
          UniqueConstraint("user1_id", "user2_id", name="uq_dm_conversation_pair"),
          Index("idx_dm_conversations_user1", "user1_id"),
          Index("idx_dm_conversations_user2", "user2_id"),
      )
  ```
- **驗證`: 嘗試建立重複的 DM conversation → 預期 IntegrityError

### [x] Task4.6: ForumComment.type CHECK constraint 修正
- **檔案**: `core/orm/models.py:143`
- **問題**: ORM model 缺 CHECK constraint，但資料庫可能有 `CHECK (type IN ('comment', 'push', 'boo'))`，ORM 端無驗證。
- **修改內容**:
  ```python
  from sqlalchemy import CheckConstraint
  
  class ForumComment(Base):
      type: Mapped[str] = mapped_column(Text, nullable=False)
      
      __table_args__ = (
          CheckConstraint(
              "type IN ('comment', 'push', 'boo')",
              name="ck_forum_comment_type"
          ),
          # ... 現有 indexes ...
      )
  ```
- **驗證`: 嘗試插入 type='invalid' → 預期 IntegrityError

### [x] Task4.7: Friendship.status CHECK 加入 `rejected`
- **檔案**: `core/orm/models.py:199`
- **問題**: `status` 欄位預設 `pending`，但無 CHECK constraint，且 `rejected` 狀態未被 ORM 保護。
- **修改內容**:
  ```python
  class Friendship(Base):
      status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
      
      __table_args__ = (
          CheckConstraint(
              "status IN ('pending', 'accepted', 'rejected', 'blocked')",
              name="ck_friendship_status"
          ),
          # ... 現有 indexes ...
      )
  ```
- **驗證`: 確認 constraint 建立成功

### [x] Task4.8: PriceAlert.created_at 改為 TIMESTAMP
- **檔案**: `core/orm/models.py:322`
- **問題**: `created_at: Mapped[str] = mapped_column(Text)` 使用 Text 而非 TIMESTAMP，無法進行時間排序和比較。
- **修改內容**:
  ```python
  created_at: Mapped[datetime] = mapped_column(
      TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
  )
  ```
  注意：需檢查現有資料是否都是有效的時間字串，可能需要 data migration。
- **驗證`: Migration 成功執行；時間排序查詢正常

### [x] Task4.9: N+1 查詢修復 — friends_repo
- **檔案**: `core/orm/friends_repo.py:636-663`
- **問題**: `get_user_profile` 對每個 profile 執行 5 次獨立查詢（friendship status、post count、push count、friends count），嚴重 N+1 問題。
- **修改內容**:
  ```python
  # 使用單一查詢取得所有資料
  from sqlalchemy import select, func
  
  # 合併查詢
  profile_query = (
      select(
          User.user_id, User.username, User.pi_username,
          User.membership_tier, User.created_at,
          func.count(Post.id).filter(Post.is_hidden == 0).label("post_count"),
          func.coalesce(func.sum(Post.push_count), 0).label("total_pushes"),
      )
      .outerjoin(Post, Post.user_id == User.user_id)
      .where(User.user_id == target_user_id)
      .group_by(User.user_id)
  )
  ```
  Friendship status 查詢可保留獨立（因為需要 viewer_user_id 條件）。
- **驗證`: 使用 `EXPLAIN ANALYZE` 確認查詢次數從 5 降到 2

### [x] Task4.10: Session 生命週期 bug 修復
- **檔案**: `core/orm/repositories.py:64,71,78`
- **問題**: `async with session or get_async_session() as s:` 語義不正確。當 `session` 為 `None` 時，`None or get_async_session()` 返回一個 context manager，`async with` 會正確處理。但當 `session` 非 None 時，`async with session as s` 會呼叫 session 的 `__aenter__`/`__aexit__`，導致 session 被意外關閉。
- **修改內容**:
  ```python
  async def get_by_id(self, user_id: str, session: AsyncSession | None = None) -> Optional[dict]:
      if session is not None:
          result = await session.execute(select(User).where(User.user_id == user_id))
          user = result.scalar_one_or_none()
          return _user_to_dict(user) if user else None
      
      async with get_async_session() as s:
          result = await s.execute(select(User).where(User.user_id == user_id))
          user = result.scalar_one_or_none()
          return _user_to_dict(user) if user else None
  ```
  對 `get_by_username` 和 `update_last_active` 做同樣修改。
- **驗證`: 寫一個測試：在同一個 session 中連續呼叫兩個 repository 方法，確認不報 "session is closed" 錯誤

### [x] Task4.11: 手動 rollback 修復
- **檔案**: `core/orm/messages_repo.py:429-432`
- **問題**: 在 `async with get_async_session() as s:` context manager 中手動呼叫 `await s.rollback()`。Context manager 的 `__aexit__` 會在異常時自動 rollback，手動 rollback 可能導致狀態不一致。
- **修改內容**:
  ```python
  try:
      # ... DB 操作 ...
      await s.commit()
      return {"success": True, "message": _msg_row_to_dict(msg_row)}
  except Exception as e:
      # 移除手動 rollback，讓 context manager 處理
      # await s.rollback()  ← 刪除此行
      logger.error("send_message error: %s", e, exc_info=True)
      return {"success": False, "error": "Internal error"}  # 不洩漏 str(e)
  ```
- **驗證`: 觸發錯誤情境，確認 session 狀態正常

### [x] Task4.12: `auto_migrate.py` DDL 生成方式改善
- **檔案**: `core/orm/auto_migrate.py:100-106`
- **問題**: 透過字串替換 `"CREATE TABLE "` → `"CREATE TABLE IF NOT EXISTS "` 來生成 DDL，非常脆弱（若 DDL 格式有變化就失效）。
- **修改內容**:
  ```python
  from sqlalchemy.schema import CreateTable
  
  async def _create_table_safe(conn, table):
      """Create a table using IF NOT EXISTS pattern."""
      ddl = CreateTable(table)
      compiled = ddl.compile(dialect=conn.dialect)
      # 使用 SQLAlchemy 的 DDL 物件屬性而非字串操作
      raw_str = str(compiled)
      # 更安全的替換：只替換第一個 CREATE TABLE 關鍵字
      import re
      raw_str = re.sub(
          r'^CREATE\s+TABLE\b',
          'CREATE TABLE IF NOT EXISTS',
          raw_str,
          count=1,
          flags=re.IGNORECASE
      )
      await conn.execute(text(raw_str))
  ```
- **驗證`: 對一個已存在的表執行 auto_migrate，確認不報錯

---

## Phase 5: 部署/CI-CD 改善 (DevOps) ✅ 完成
> 預估時間: 4–5 小時 | 優先級: P2 | **已完成 — 所有任務驗證通過**

### [x] Task5.1: CI 加入 PostgreSQL service
- **檔案**: `.github/workflows/e2e.yml` (及其他 CI workflow)
- **問題**: CI 中無 PostgreSQL service，導致需要 DB 的測試全部失敗。
- **修改內容**:
  ```yaml
  jobs:
    test:
      services:
        postgres:
          image: postgres:16
          env:
            POSTGRES_USER: test
            POSTGRES_PASSWORD: test
            POSTGRES_DB: test
          ports:
            - 5432:5432
          options: >-
            --health-cmd pg_isready
            --health-interval 10s
            --health-timeout 5s
            --health-retries 5
      
      env:
        DATABASE_URL: postgresql://test:test@localhost:5432/test
        TEST_MODE: "true"
        TEST_MODE_CONFIRMATION: "I_UNDERSTAND_THE_RISKS"
  ```
- **驗證`: Push 到 branch 觸發 CI，確認 DB 相關測試通過

### [x] Task5.2: 建立 `.env.example`
- **檔案**: 新建 `.env.example`
- **問題**: 新開發者無法知道需要哪些環境變數。
- **修改內容**:
  ```env
  # === Required ===
  DATABASE_URL=postgresql://user:pass@localhost:5432/cryptomind
  JWT_SECRET_KEY=  # Generate: openssl rand -hex 32
  ADMIN_API_KEY=   # Generate: openssl rand -hex 32
  
  # === LLM Providers (at least one required) ===
  OPENAI_API_KEY=
  GOOGLE_API_KEY=
  OPENROUTER_API_KEY=
  
  # === Optional ===
  ENVIRONMENT=development
  TEST_MODE=false
  REDIS_URL=redis://localhost:6379/0
  SSL_VERIFY=true
  APP_LOG_LEVEL=WARNING
  
  # === Pi Network ===
  PI_API_KEY=
  PI_WALLET_PRIVATE_SEED=
  
  # === OKX (optional) ===
  OKX_API_KEY=
  OKX_SECRET_KEY=
  OKX_PASSPHRASE=
  ```
- **驗證`: 新開發者能根據 `.env.example` 完成環境配置

### [x] Task5.3: 建立 `docker-compose.yml`
- **檔案**: 新建 `docker-compose.yml`
- **問題**: 無 docker-compose，本地開發需要手動啟動各種服務。
- **修改內容**:
  ```yaml
  version: '3.8'
  services:
    app:
      build: .
      ports:
        - "8000:8000"
      env_file: .env
      depends_on:
        db:
          condition: service_healthy
        redis:
          condition: service_healthy
    
    db:
      image: postgres:16
      environment:
        POSTGRES_USER: cryptomind
        POSTGRES_PASSWORD: cryptomind
        POSTGRES_DB: cryptomind
      volumes:
        - pgdata:/var/lib/postgresql/data
      ports:
        - "5432:5432"
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U cryptomind"]
        interval: 5s
        timeout: 3s
        retries: 5
    
    redis:
      image: redis:7-alpine
      ports:
        - "6379:6379"
      healthcheck:
        test: ["CMD", "redis-cli", "ping"]
        interval: 5s
        timeout: 3s
        retries: 5
  
  volumes:
    pgdata:
  ```
- **驗證`: `docker-compose up` 一鍵啟動所有服務

### [x] Task5.4: `/health` endpoint 加入依賴檢查
- **檔案**: `api_server.py` (health check 區域)
- **問題**: `/health` 只檢查 HTTP 可達性，不檢查 DB、Redis 等依賴。
- **修改內容**:
  ```python
  @app.get("/health")
  async def health_check():
      checks = {"app": True}
      
      # DB check
      try:
          from core.database import get_db_connection
          conn = await run_sync(lambda: get_db_connection())
          conn.execute("SELECT 1")
          conn.close()
          checks["database"] = True
      except Exception:
          checks["database"] = False
      
      # Redis check (optional)
      try:
          import redis
          r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
          r.ping()
          checks["redis"] = True
      except Exception:
          checks["redis"] = False
      
      all_ok = all(checks.values())
      return JSONResponse(
          status_code=200 if all_ok else 503,
          content={"status": "healthy" if all_ok else "degraded", "checks": checks}
      )
  ```
- **驗證`: 停止 DB 後 `/health` 回傳 503 + `{"database": false}`

### [x] Task5.5: 結構化 Logging
- **檔案**: 新建 `config/logging_config.py` 或修改 `api_server.py`
- **問題**: 目前使用 Python 預設 logging 格式，難以在生產環境中搜索和分析。
- **修改內容**:
  ```python
  import json
  import logging
  
  class JSONFormatter(logging.Formatter):
      def format(self, record):
          log_entry = {
              "timestamp": self.formatTime(record),
              "level": record.levelname,
              "logger": record.name,
              "message": record.getMessage(),
          }
          if record.exc_info:
              log_entry["exception"] = self.formatException(record.exc_info)
          return json.dumps(log_entry)
  
  # 在 api_server.py 中設定
  handler = logging.StreamHandler()
  handler.setFormatter(JSONFormatter())
  logging.root.addHandler(handler)
  ```
- **驗證`: 啟動 server，確認 log 輸出為 JSON 格式

### [x] Task5.6: 建立 Deploy Workflow
- **檔案**: 新建 `.github/workflows/deploy.yml`
- **問題**: 無自動部署 workflow。
- **修改內容**:
  ```yaml
  name: Deploy
  on:
    push:
      branches: [main]
  jobs:
    deploy:
      runs-on: ubuntu-latest
      needs: [test]  # 依賴 CI 通過
      steps:
        - uses: actions/checkout@v4
        - name: Build and push Docker image
          run: |
            docker build -t cryptomind:$GITHUB_SHA .
            # push to registry...
        - name: Deploy
          run: |
            # SSH to server and pull new image
            # or use kubectl / docker-compose
  ```
- **驗證`: Push 到 main 觸發 deploy workflow

### [x] Task5.7: 備份策略
- **檔案**: 新建 `scripts/backup.sh`、`scripts/restore.sh`
- **問題**: 無資料庫備份策略。
- **修改內容**:
  ```bash
  #!/bin/bash
  # scripts/backup.sh
  BACKUP_DIR="/backups"
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  FILENAME="cryptomind_${TIMESTAMP}.sql.gz"
  
  pg_dump $DATABASE_URL | gzip > "${BACKUP_DIR}/${FILENAME}"
  
  # 保留最近 7 天的備份
  find $BACKUP_DIR -name "*.sql.gz" -mtime +7 -delete
  
  echo "Backup created: ${BACKUP_DIR}/${FILENAME}"
  ```
  加入 crontab 或 CI schedule。
- **驗證`: 手動執行 `./scripts/backup.sh`，確認備份檔案產生

---

## Phase 6: 測試補齊 (Test Coverage) ✅ 完成
> 預估時間: 8–10 小時 | 優先級: P1 | **已完成 — 所有任務驗證通過**

### [x] Task6.1: 擴充 conftest.py — 建立核心 fixtures
- **檔案**: `tests/conftest.py`
- **問題**: 目前只有 27 行，幾乎為空，缺少核心 fixtures。
- **修改內容**:
  ```python
  import pytest
  import asyncio
  from httpx import AsyncClient, ASGITransport
  from unittest.mock import AsyncMock
  
  # --- App fixture ---
  @pytest.fixture
  def app():
      from api_server import app
      return app
  
  @pytest.fixture
  async def client(app):
      transport = ASGITransport(app=app)
      async with AsyncClient(transport=transport, base_url="http://test") as c:
          yield c
  
  # --- Auth fixtures ---
  @pytest.fixture
  def auth_headers():
      from api.deps import create_access_token
      token = create_access_token(data={"sub": "test-user-001"})
      return {"Authorization": f"Bearer {token}"}
  
  @pytest.fixture
  def admin_headers():
      import os
      return {"X-Admin-Key": os.getenv("ADMIN_API_KEY", "test-admin-key")}
  
  # --- DB fixture ---
  @pytest.fixture
  async def db_session():
      from core.orm import get_async_session
      async with get_async_session() as session:
          yield session
          await session.rollback()
  
  # --- Mock fixtures ---
  @pytest.fixture
  def mock_llm_client():
      return AsyncMock()
  ```
- **驗證`: `pytest --collect-only` 確認 fixtures 被正確收集

### [x] Task6.2: 使用 pytest markers 分類現有測試
- **檔案**: 所有 `tests/test_*.py`
- **問題**: `@pytest.mark.unit/integration/slow` 已定義但從未使用。
- **修改內容**:
  1. 為所有現有測試加上適當的 marker：
     - 不依賴 DB/外部服務的 → `@pytest.mark.unit`
     - 需要 DB 連線的 → `@pytest.mark.integration`
     - 執行超過 5 秒的 → `@pytest.mark.slow`
  2. 在 `pytest.ini` 中設定預設行為：
     ```ini
     [pytest]
     markers = 
         unit: Unit tests
         integration: Integration tests
         slow: Slow tests
     addopts = -m "not slow"  # 預設跳過慢測試
     ```
- **驗證`: `pytest -m unit` 只跑單元測試；`pytest -m "not slow"` 跳過慢測試

### [x] Task6.3: 修復被永久 skip 的安全測試
- **檔案**: `tests/` (搜尋 `@pytest.mark.skip` 或 `@pytest.mark.xfail`)
- **問題**: 3 個安全相關測試被永久 skip。
- **修改內容**:
  1. 找到被 skip 的安全測試，分析 skip 原因。
  2. 修復測試環境或測試邏輯，使其能正常執行。
  3. 若測試依賴的漏洞已修復（如 Phase 1 的修復），更新測試以驗證修復效果。
- **驗證`: `pytest -v` 確認無 skip 的安全測試

### [x] Task6.4: 修復 `asyncio.run()` 繞過 pytest 的測試
- **檔案**: `tests/` (搜尋 `asyncio.run(`)
- **問題**: ~30 個測試用 `asyncio.run()` 手動執行 async 函數，繞過 pytest-asyncio 的 event loop 管理，可能導致 event loop 衝突。
- **修改內容**:
  ```python
  # Before:
  def test_something():
      result = asyncio.run(async_function())
      assert result
  
  # After:
  @pytest.mark.asyncio
  async def test_something():
      result = await async_function()
      assert result
  ```
- **驗證`: `pytest -v` 確認所有 async 測試使用 `@pytest.mark.asyncio`

### [x] Task6.5: Router 測試補齊（優先安全相關）
- **檔案**: 新建 `tests/test_routers/`
- **問題**: ~20 個 router 零測試。
- **修改內容**: 按優先級補齊測試：
  1. **`test_analysis.py`** — 驗證 IDOR 修復（Phase 1.1）：
     ```python
     @pytest.mark.asyncio
     async def test_delete_session_requires_ownership(client, auth_headers):
         # 用戶 A 嘗試刪除用戶 B 的 session → 403
         response = await client.delete(
             "/api/chat/sessions/other-users-session",
             headers=auth_headers,
         )
         assert response.status_code == 403
     ```
  2. **`test_admin_auth.py`** — 驗證 admin key 驗證：
     ```python
     async def test_admin_invalid_key(client):
         response = await client.get("/api/admin/...", headers={"X-Admin-Key": "wrong"})
         assert response.status_code == 403
     ```
  3. **`test_system.py`** — 驗證 TEST_MODE 不洩漏資料
  4. **`test_settings.py`** — 驗證 settings update 正確性
- **驗證`: `pytest tests/test_routers/ -v` 全部通過

### [x] Task6.6: Negative path 測試補齊
- **檔案**: `tests/`
- **問題**: 缺少 401/403/422/404 等錯誤路徑測試。
- **修改內容**:
  ```python
  class TestNegativePaths:
      @pytest.mark.asyncio
      async def test_unauthorized_access(self, client):
          response = await client.get("/api/chat/sessions")
          assert response.status_code == 401
      
      @pytest.mark.asyncio
      async def test_invalid_token(self, client):
          response = await client.get(
              "/api/chat/sessions",
              headers={"Authorization": "Bearer invalid-token"}
          )
          assert response.status_code == 401
      
      @pytest.mark.asyncio
      async def test_missing_required_fields(self, client, auth_headers):
          response = await client.post("/api/chat/query", 
              headers=auth_headers,
              json={}  # 缺少必填欄位
          )
          assert response.status_code == 422
      
      @pytest.mark.asyncio
      async def test_not_found(self, client, auth_headers):
          response = await client.get("/api/nonexistent")
          assert response.status_code == 404
  ```
- **驗證`: `pytest tests/ -k "negative" -v` 全部通過

### [x] Task6.7: `utils/encryption.py` 測試補齊
- **檔案**: 新建 `tests/test_encryption.py`
- **問題**: 加密工具零測試，但處理敏感資料。
- **修改內容**:
  ```python
  class TestEncryption:
      def test_encrypt_decrypt_roundtrip(self):
          from utils.encryption import encrypt, decrypt
          plaintext = "sensitive-data-12345"
          encrypted = encrypt(plaintext)
          assert encrypted != plaintext
          assert decrypt(encrypted) == plaintext
      
      def test_encrypt_different_each_time(self):
          from utils.encryption import encrypt
          plaintext = "same-input"
          assert encrypt(plaintext) != encrypt(plaintext)
      
      def test_decrypt_invalid_input(self):
          from utils.encryption import decrypt
          with pytest.raises(Exception):
              decrypt("not-valid-encrypted-data")
  ```
- **驗證`: `pytest tests/test_encryption.py -v` 全部通過

### [x] Task6.8: `data/` 模組測試補齊
- **檔案**: 新建 `tests/test_data/`
- **問題**: `data/` 模組零測試。
- **修改內容**: 審查 `data/` 目錄下的模組，為每個公開函數寫基本測試。優先測試資料解析、轉換、驗證邏輯。
- **驗證`: `pytest tests/test_data/ -v` 全部通過

---

## Phase 7: AI Agent 改善 (Agent System) ✅ 完成
> 預估時間: 6–8 小時 | 優先級: P2 | **已完成 — 所有任務驗證通過**

### [x] Task7.1: Manager cache 加入上限和 TTL
- **檔案**: `core/agents/bootstrap.py:714-715`
- **問題**: `_manager_cache: Dict[str, ManagerAgent] = {}` 無上限無 TTL，長時間運行會導致記憶體洩漏（每個用戶每個 session 都建立一個 Manager 實例）。
- **修改內容**:
  ```python
  import time
  from collections import OrderedDict
  
  MAX_CACHE_SIZE = 100
  CACHE_TTL_SECONDS = 3600  # 1 小時
  
  _manager_cache: OrderedDict[str, tuple[ManagerAgent, float]] = OrderedDict()
  
  def get_cached_manager(user_id: str, session_id: str = "default") -> ManagerAgent:
      cache_key = _manager_cache_key(user_id, session_id)
      now = time.time()
      
      if cache_key in _manager_cache:
          manager, created_at = _manager_cache[cache_key]
          if now - created_at < CACHE_TTL_SECONDS:
              _manager_cache.move_to_end(cache_key)  # LRU
              return manager
          else:
              del _manager_cache[cache_key]  # TTL expired
      
      # 如果超過上限，淘汰最舊的
      while len(_manager_cache) >= MAX_CACHE_SIZE:
          _manager_cache.popitem(last=False)
      
      # 建立新的 manager
      manager = _create_manager(user_id, session_id)
      _manager_cache[cache_key] = (manager, now)
      return manager
  ```
- **驗證`: 模擬 101 個用戶建立 manager，確認 cache 不超過 100 個

### [x] Task7.2: `asyncio.create_task` 保存引用
- **檔案**: `core/agents/manager.py` (多處)
- **問題**: `asyncio.create_task(...)` 未保存返回的 Task 引用，若 task 發生異常，Python 會發出 "Task was destroyed but it is pending!" 警告，且異常被靜默吞掉。
- **修改內容**:
  ```python
  import weakref
  
  _background_tasks: weakref.WeakSet = weakref.WeakSet()
  
  def _run_background(coro):
      """安全地建立背景 task，保存引用防止被 GC。"""
      task = asyncio.create_task(coro)
      _background_tasks.add(task)
      task.add_done_callback(_background_tasks.discard)
      return task
  
  # 替換所有 asyncio.create_task(...) 為 _run_background(...)
  ```
- **驗證`: 啟動 server 後執行多次分析，確認無 "Task was destroyed" 警告

### [x] Task7.3: 模型路由策略（簡易版）
- **檔案**: 新建 `core/agents/model_router.py`，修改 `core/agents/bootstrap.py`
- **問題**: 所有 LLM 呼叫使用同一個昂貴模型（如 GPT-5.2-pro），無路由策略。
- **修改內容**:
  ```python
  class ModelRouter:
      """根據任務複雜度選擇合適的模型。"""
      
      TASK_MODEL_MAP = {
          "simple_qa": "gemini-3.1-flash-preview",     # 快速、便宜
          "market_data": "gpt-5-mini",                  # 中等複雜度
          "deep_analysis": "gpt-5.2-pro",               # 深度分析
          "research": "gpt-5.2-pro",                    # 研究報告
      }
      
      @classmethod
      def get_model(cls, task_type: str, user_preference: str = None) -> str:
          if user_preference:
              return user_preference
          return cls.TASK_MODEL_MAP.get(task_type, "gpt-5-mini")
  ```
  在 Manager Agent 中根據意圖分類結果選擇模型。
- **驗證`: 簡單問題使用 flash model；深度分析使用 pro model；日誌記錄使用的模型

### [x] Task7.4: PromptRegistry 線程安全
- **檔案**: `core/agents/prompt_registry.py:14`
- **問題**: `_prompts: Dict[str, Dict] = {}` 和 `_loaded: bool = False` 是類變數，在多線程/多 worker 環境下可能有競態條件。
- **修改內容**:
  ```python
  import threading
  
  class PromptRegistry:
      _prompts: Dict[str, Dict] = {}
      _loaded: bool = False
      _lock = threading.Lock()
      
      @classmethod
      def load(cls, prompts_dir=None):
          with cls._lock:
              if cls._loaded:
                  return
              if prompts_dir is None:
                  prompts_dir = Path(__file__).parent / "prompts"
              for yaml_file in Path(prompts_dir).glob("*.yaml"):
                  scope = yaml_file.stem
                  with open(yaml_file, "r", encoding="utf-8") as f:
                      cls._prompts[scope] = yaml.safe_load(f) or {}
              cls._loaded = True
  ```
- **驗證`: 多線程並發呼叫 `PromptRegistry.load()`，確認 prompts 只載入一次

### [x] Task7.5: `tool_compactor._local_store` 加入上限
- **檔案**: `core/agents/tool_compactor.py:24`
- **問題**: `_local_store: dict[str, str] = {}` 無界增長，長時間運行會消耗大量記憶體。
- **修改內容**:
  ```python
  from collections import OrderedDict
  
  MAX_LOCAL_STORE_SIZE = 1000
  
  def _store_compacted(key: str, value: str) -> None:
      global _local_store
      if len(_local_store) >= MAX_LOCAL_STORE_SIZE:
          # 淘汰最舊的 20%
          keys_to_remove = list(_local_store.keys())[:MAX_LOCAL_STORE_SIZE // 5]
          for k in keys_to_remove:
              del _local_store[k]
      _local_store[key] = value
  ```
- **驗證`: 模擬大量工具結果壓縮，確認 store 不超過上限

### [x] Task7.6: Watcher 失敗改為 FAIL
- **檔案**: `core/agents/` (watcher 相關)
- **問題**: Watcher（市場數據監控）失敗時預設為 PASS，可能導致基於過時資料做出分析。
- **修改內容**:
  1. 找到 watcher 的錯誤處理邏輯。
  2. 將 `default=True` 改為 `default=False`：
     ```python
     # Before:
     is_valid = watcher.check(data)  # 失敗時回傳 True
     
     # After:
     is_valid = watcher.check(data)  # 失敗時回傳 False
     if not is_valid:
         logger.warning("Watcher check failed, data may be stale")
     ```
  3. 加入重試邏輯（最多 3 次）。
- **驗證`: 模擬 watcher 失敗，確認回傳 False 而非 True

### [x] Task7.7: `_parse_json_response` 靜默失敗改為拋出
- **檔案**: `core/agents/` (JSON 解析相關)
- **問題**: `_parse_json_response` 解析失敗時靜默返回空 dict `{}`，導致下游邏輯收到無意義的空資料卻不自知。
- **修改內容**:
  ```python
  def _parse_json_response(response_text: str) -> dict:
      """解析 LLM 回應中的 JSON，失敗時拋出明確異常。"""
      try:
          return json.loads(response_text)
      except json.JSONDecodeError as e:
          logger.error(f"Failed to parse JSON response: {e}\nResponse: {response_text[:500]}")
          raise ValueError(f"LLM returned invalid JSON: {e}") from e
  ```
- **驗證`: 模擬 LLM 回傳非 JSON 字串，確認拋出 ValueError 而非返回空 dict

### [x] Task7.8: Token 追蹤 / 預算管理（基礎版）
- **檔案**: 新建 `core/agents/token_tracker.py`
- **問題**: 無 token 追蹤，無法知道每次分析的 LLM 成本。
- **修改內容**:
  ```python
  import time
  from dataclasses import dataclass, field
  
  @dataclass
  class TokenUsage:
      model: str
      prompt_tokens: int
      completion_tokens: int
      total_tokens: int
      timestamp: float = field(default_factory=time.time)
      
      @property
      def estimated_cost_usd(self) -> float:
          # 簡化的成本估算
          COST_PER_1K = {
              "gpt-5-mini": 0.00015,
              "gpt-5.2-pro": 0.015,
              "gemini-3.1-flash-preview": 0.000075,
          }
          rate = COST_PER_1K.get(self.model, 0.001)
          return (self.total_tokens / 1000) * rate
  
  class TokenTracker:
      def __init__(self, max_budget_usd: float = 10.0):
          self._usage_history: list[TokenUsage] = []
          self._max_budget = max_budget_usd
      
      def record(self, usage: TokenUsage):
          self._usage_history.append(usage)
      
      def total_cost(self) -> float:
          return sum(u.estimated_cost_usd for u in self._usage_history)
      
      def is_over_budget(self) -> bool:
          return self.total_cost() >= self._max_budget
  ```
  在 LLM client 回調中記錄 token usage。
- **驗證`: 執行一次分析後，檢查 token usage 記錄是否正確

### [x] Task7.9: Agent 實例快取（避免每次 execute 重建）
- **檔案**: `core/agents/` (agent 建立相關)
- **問題**: 每次 `execute` 都重建 agent 實例（含工具註冊、prompt 載入等），造成不必要的開銷。
- **修改內容**:
  1. 在 `bootstrap.py` 中加入 agent 類型層級的快取：
     ```python
     _agent_class_cache: Dict[str, type] = {}
     
     def get_agent_class(agent_type: str):
         if agent_type not in _agent_class_cache:
             _agent_class_cache[agent_type] = _create_agent_class(agent_type)
         return _agent_class_cache[agent_type]
     ```
  2. 每次 execute 只需建立新的 state，復用 agent class。
- **驗證`: 確認連續兩次分析使用相同的 agent class 實例

### [x] Task7.10: 任務截斷警告
- **檔案**: `core/agents/` (task 執行相關)
- **問題**: 當 LLM 回應超過 context budget 被截斷時，用戶和系統都無法得知。
- **修改內容**:
  ```python
  from core.agents.context_budget import CONTEXT_CHAR_BUDGET
  
  def _check_truncation(response: str, original_prompt: str) -> bool:
      """檢查回應是否被截斷。"""
      if len(response) >= CONTEXT_CHAR_BUDGET * 0.95:
          logger.warning(
              f"Response may be truncated: {len(response)} chars "
              f"(budget: {CONTEXT_CHAR_BUDGET})"
          )
          return True
      return False
  ```
  在回應中加入 `[...truncated]` 標記或通知用戶。
- **驗證`: 模擬長回應，確認日誌有 truncation 警告

---

## 執行優先級總覽

| Phase | 名稱 | 優先級 | 預估時間 | 前置依賴 | 狀態 |
|-------|------|--------|----------|----------|------|
| **1** | 安全漏洞修復 | **P0** | 6–8h | 無 | ✅ 完成 |
| **2** | 後端品質改善 | P1 | 5–7h | Phase 1 | ✅ 完成 |
| **3** | 前端品質改善 | P1 | 5–7h | Phase 1 | ✅ 完成 |
| **4** | 資料庫改善 | P1 | 5–7h | 無（可與 Phase 1-3 並行） | ✅ 完成 |
| **5** | 部署/CI-CD 改善 | P2 | 4–5h | Phase 4 | ✅ 完成 |
| **6** | 測試補齊 | P1 | 8–10h | Phase 1-4 | ✅ 完成 |
| **7** | AI Agent 改善 | P2 | 6–8h | Phase 2 | ✅ 完成 |

**建議執行順序**: 1 → 4 → 2 → 3 → 6 → 5 → 7

- **Phase 1** 必須最先完成（安全問題不可拖延）
- **Phase 4** 可與 Phase 2-3 並行（DB 改善與後端/前端改善相互獨立）
- **Phase 6** 在 Phase 1-4 之後進行（需要穩定的 API 才能寫測試）
- **Phase 7** 最後進行（AI Agent 改善是效能優化，非阻塞性問題）

---

## 統計

| 類別 | Critical | High | Medium | 總計 |
|------|----------|------|--------|------|
| 安全 | 12 | 5 | 0 | 17 |
| 後端品質 | 1 | 10 | 2 | 13 |
| 前端品質 | 1 | 8 | 5 | 14 |
| 資料庫 | 5 | 5 | 2 | 12 |
| 部署/CI-CD | 2 | 6 | 1 | 9 |
| 測試 | 5 | 4 | 0 | 9 |
| AI Agent | 5 | 6 | 0 | 11 |
| **總計** | **31** | **44** | **10** | **85** |

---

> 最後更新: 2026-03-21 | PM: DANNY Team | **所有 7 個 Phase 已全部完成**
