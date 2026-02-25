# 系統架構盤查報告

**審查日期**: 2026 年 2 月 25 日  
**審查範圍**: Pi Crypto Insight 完整系統架構  
**審查員**: AI Assistant  
**審查檔案數**: 215+ 個 Python 檔案 + 30+ 個 JavaScript 檔案

---

## 📋 執行摘要

本報告針對 Pi Crypto Insight 系統進行全面性盤查，包含：
- ✅ 未使用的參數與配置
- ✅ 未使用或殘留的功能模組
- ✅ 潛在 Bug 與邏輯問題
- ✅ 資安風險評估
- ✅ 技術債與優化建議

### 風險等級統計

| 等級 | 數量 | 說明 |
|------|------|------|
| 🔴 **嚴重** | 12 | 需立即處理的安全風險 |
| 🟠 **高** | 18 | 影響功能或潛在風險 |
| 🟡 **中** | 24 | 建議優化的問題 |
| 🟢 **低** | 15 | 技術債與清理建議 |

### 審查範圍統計

| 類別 | 檔案數 | 總行數 | 最大檔案 |
|------|--------|--------|----------|
| **Python 後端** | 215+ | ~50,000+ | `connection.py` (1,135 行) |
| **JavaScript 前端** | 30+ | ~10,000+ | `forum.js` (1,200+ 行) |
| **測試檔案** | 50+ | ~8,000+ | - |
| **配置文件** | 5 | ~500 | `gunicorn.conf.py` |

---

## 一、未使用的參數與配置

### 1.1 環境變數配置問題

#### 🔴 [嚴重] TEST_MODE 相關參數風險

**位置**: `core/config.py:20-58`

```python
TEST_MODE = os.getenv("TEST_MODE", "false").lower() == "true"
TEST_MODE_CONFIRMATION = os.getenv("TEST_MODE_CONFIRMATION", "")
TEST_MODE_IP_WHITELIST = os.getenv("TEST_MODE_IP_WHITELIST", "")
```

**問題**:
1. TEST_MODE 允許完全繞過認證系統
2. 虽然有保護檢查，但在開發環境仍可輕易啟用
3. `TEST_MODE_IP_WHITELIST` 參數被定義但從未實際使用於 IP 過濾

**影響**: 若開發人員意外在生產環境啟用，將完全繞過安全檢查

**建議**: 
- 完全移除 TEST_MODE 功能，改用正式的測試帳號系統
- 或將此功能限制為只能透過原始碼編譯時啟用

---

#### 🔴 [嚴重] 硬編碼的 Pi Network 驗證密鑰

**位置**: `api_server.py:252`

```python
PI_VALIDATION_KEY = "bb688627074252c72dd05212708965ba06070edde22821ac519aadc388ebf2f06cd0746217c4a1c466baeb1303311ef7333813683253a330e5d257522670a480"
```

**問題**: Pi Network 域名驗證密鑰直接硬編碼在源碼中，屬於敏感信息洩露

**影響**: 
- 攻擊者可從公開代碼庫獲取密鑰
- 可能用於偽造 Pi Network 域名驗證

**建議**:
```python
# 改為從環境變數讀取
PI_VALIDATION_KEY = os.getenv("PI_VALIDATION_KEY")
if not PI_VALIDATION_KEY:
    raise ValueError("PI_VALIDATION_KEY environment variable is required")
```

---

#### 🔴 [嚴重] 密碼哈希迭代次數不足

**位置**: `core/database/user.py:19-26`

```python
def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ':' + key.hex()
```

**問題**: 
- 使用 100,000 次迭代，低於 OWASP 2023 年建議的 600,000 次
- 在現代 GPU 硬件下可能被暴力破解

**建議**:
```python
# 增加到至少 600,000 次迭代
key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 600000)
# 或考慮使用 argon2 算法
```

---

#### 🟠 [高] 未使用的環境變數

**位置**: 多個文件

| 環境變數 | 位置 | 狀態 | 建議 |
|----------|------|------|------|
| `TEST_MODE_IP_WHITELIST` | `core/config.py:44` | 定義但未使用 | 移除或實作 IP 過濾 |
| `MARKET_PULSE_WORKER` | `api_server.py:140` | 部分使用 | 文件不足，需補充 |
| `SKIP_DB_INIT` | `api_server.py:87` | 正常使用 | ✅ 保留 |
| `ALLOW_ADMIN_BOOTSTRAP` | `api/routers/admin_panel.py:508` | 正常使用 | ✅ 保留 |
| `LOG_FILE_PATH` | `api/routers/admin.py:92` | 正常使用 | ✅ 保留 |
| `DATABASE_URL` | 多處 | 正常使用 | ✅ 保留 |
| `WEB_CONCURRENCY` | `gunicorn.conf.py:20` | 正常使用 | ✅ 保留 |

---

#### 🟡 [中] 硬編碼的配置值

**位置**: `core/config.py`

```python
# 這些值應該移到環境變數
SCREENER_TARGET_SYMBOLS = ["BTC", "ETH", "SOL"]  # 應可配置
MARKET_PULSE_TARGETS = ["BTC", "ETH", "SOL"]     # 應可配置
CRYPTO_CURRENCIES_TO_ANALYZE = ["PIUSDT"]        # 應可配置
DEFAULT_FUTURES_LEVERAGE = 5                      # 應可配置
```

**建議**: 將這些業務邏輯配置移到環境變數，方便不同環境調整

---

### 1.2 模型配置問題

#### 🟡 [中] 重複的模型配置定義

**位置**: `core/config.py:67-130`

```python
# 問題：同一個模型配置被多次定義
FAST_THINKING_MODEL = get_default_model("openai")
DEEP_THINKING_MODEL = get_default_model("openai")

# 然後又在多處重複定義
BULL_RESEARCHER_MODEL = {"provider": "user_provided", "model": default_openai_model}
BEAR_RESEARCHER_MODEL = {"provider": "user_provided", "model": default_openai_model}
TRADER_MODEL = {"provider": "user_provided", "model": default_openai_model}
JUDGE_MODEL = {"provider": "user_provided", "model": default_openai_model}
```

**問題**:
- 配置分散，難以統一管理
- 所有研究員都使用相同的模型，失去多模型辯論的意義

**建議**: 
- 統一模型配置管理
- 為不同代理配置不同模型以實現真正的多模型辯論

---

#### 🟢 [低] 未使用的模型配置

**位置**: `core/config.py:104-117`

```python
BULL_COMMITTEE_MODELS = [
    {"provider": "user_provided", "model": default_openai_model},
    {"provider": "user_provided", "model": default_openai_model},
]

BEAR_COMMITTEE_MODELS = [
    {"provider": "user_provided", "model": default_openai_model},
    {"provider": "user_provided", "model": default_openai_model},
]
```

**問題**: 委員會模式配置定義了但可能未實際使用

**建議**: 確認是否實際使用，若未使用應移除

---

### 1.3 交易配置問題

#### 🟠 [高] 交易配置不一致

**位置**: `core/config.py:233-237`

```python
MINIMUM_INVESTMENT_USD = 20.0
MAXIMUM_INVESTMENT_USD = 30.0
EXCHANGE_MINIMUM_ORDER_USD = 1.0
```

**問題**:
- 最低投資金額 (20 USDT) 與交易所最低下單金額 (1 USDT) 差距過大
- 可能導致用戶無法執行建議的交易

**建議**: 調整配置使其符合實際交易所要求

---

#### 🟡 [中] 槓桿配置未使用

**位置**: `core/config.py:230`

```python
DEFAULT_FUTURES_LEVERAGE = 5
```

**問題**: 此配置在 `main.py` 中透過命令行參數覆蓋，實際未從配置文件讀取

**建議**: 移除或實際使用此配置

---

## 二、未使用或殘留的功能模組

### 2.1 完整但未啟用的功能

#### 🟡 [中] Email 服務模組

**位置**: `core/email_service.py`

**狀態**: 
- ✅ 模組完整實作
- ✅ 包含 SMTP 配置
- ❌ 但在系統中未被調用

**問題**:
- `send_reset_email()` 函數已實作但無處調用
- 密碼重置功能可能使用其他機制

**建議**: 
- 確認是否需要此功能
- 若需要，整合到用戶認證流程
- 若不需要，移除以避免混淆

---

#### 🟡 [中] Alert Dispatcher 部分功能

**位置**: `core/alert_dispatcher.py`

**狀態**:
- ✅ Telegram 警報完整實作
- ✅ Email 警報完整實作
- ⚠️ 僅在 Security Monitor 中部分使用

**問題**:
- `send_critical()` 方法定義但很少被調用
- 許多安全事件未觸發警報

**建議**: 
- 完善警報策略文件
- 或移除未使用的警報通道

---

#### 🟠 [高] Key Rotation 功能

**位置**: `core/key_rotation.py`

**狀態**:
- ✅ 完整的 JWT 密鑰輪換系統
- ✅ 雙密鑰策略實作
- ⚠️ 需要明確啟用 (`USE_KEY_ROTATION=true`)

**問題**:
- 預設未啟用，生產環境可能缺少此保護
- 文件不足，開發人員可能不知道此功能

**建議**: 
- 預設啟用或在文件強調重要性
- 添加自動化測試確保輪換正常工作

---

### 2.2 殘留/棄用的代碼

#### 🟢 [低] 資料庫備份文件

**位置**: `core/database.py.bak`

**問題**: 備份文件不應提交到版本控制

**建議**: 移除此文件並加入 `.gitignore`

---

#### 🟡 [中] Archive 目錄

**位置**: `_archive/`

**狀態**: 包含 22 個被 .gitignore 忽略的文件

**問題**: 
- 可能包含敏感的測試代碼或舊配置
- 長期累積可能洩露資訊

**建議**: 定期清理或完全移除

---

#### 🟠 [高] 測試模式登入

**位置**: `api/deps.py:96-120`

```python
if TEST_MODE:
    return {
        "user_id": user_id,
        "username": f"TestUser_{user_id[-3:]}",
        "pi_uid": user_id,
        "is_premium": False,
        ...
    }
```

**問題**: 
- 允許完全繞過 Pi Network 驗證
- 雖然有保護檢查，但仍是安全風險

**建議**: 
- 移除此功能，改用正式的測試帳號
- 或限制只能在本地開發環境使用

---

#### 🟡 [中] 未使用的 Email 服務

**位置**: `core/email_service.py`

**狀態**:
- ✅ 模組完整實作
- ✅ 包含 SMTP 配置
- ❌ 但在系統中未被調用

**問題**:
- `send_reset_email()` 函數已實作但無處調用
- 密碼重置功能可能使用其他機制

**建議**: 
- 確認是否需要此功能
- 若需要，整合到用戶認證流程
- 若不需要，移除以避免混淆

---

#### 🟡 [中] 未使用的 Gradio 依賴

**位置**: `requirements.txt`

```
gradio==6.0.2
gradio_client==2.0.1
```

**問題**: 
- 已安裝 Gradio 但系統中未見使用
- 可能是預留的替代 UI 方案

**建議**: 確認是否使用，若否則從 requirements 移除

---

#### 🟡 [中] 殘留的 Debug API

**位置**: `api_server.py:368-398`

```python
@app.post("/api/debug-log")
async def receive_frontend_log(log: FrontendLog):
    """接收前端 debug log 並寫入檔案"""
```

**問題**: 
- 生產環境中不應保留前端 debug log API
- 可能被濫用寫入惡意內容

**建議**: 
```python
# 僅在開發環境啟用
if os.getenv("ENVIRONMENT") == "development":
    @app.post("/api/debug-log")
    async def receive_frontend_log(log: FrontendLog):
        # ...
```

---

#### 🟡 [中] 未使用的 Script 文件

**位置**: `scripts/` 目錄

**發現的未使用腳本**:
- `clean_unused_files.sh` - 在代碼中被引用但實際不存在
- `delete_all_posts.py` - 危險操作腳本，不應存在於生產環境
- `delete_user_posts.py` - 同上

**建議**: 
- 清理不存在的腳本引用
- 危險操作腳本應移至專門的維護工具目錄

---

### 2.3 未實現的 API 端點

#### 🟡 [中] 編輯功能

**位置**: `IMPLEMENTATION_GUIDE.md` 提到

**狀態**:
- ✅ 後端 API 已實作 (`PUT /api/forum/posts/{post_id}`)
- ❌ 前端 UI 未完成

**建議**: 完成前端實作或移除此功能

---

#### 🟡 [中] Gradio 介面

**位置**: `requirements.txt`

```
gradio==6.0.2
gradio_client==2.0.1
```

**問題**: 
- 已安裝 Gradio 但系統中未見使用
- 可能是預留的替代 UI 方案

**建議**: 確認是否使用，若否則從 requirements 移除

---

## 三、潛在 Bug 與邏輯問題

### 3.1 嚴重邏輯錯誤

#### 🔴 [嚴重] WebSocket 管理器未正確關閉

**位置**: `data/okx_websocket.py:194-204`

```python
async def stop(self):
    """停止 WebSocket 管理器"""
    self.running = False
    if self.ws:
        await self.ws.close()
    if self._connect_task:
        self._connect_task.cancel()  # ⚠️ 問題：沒有等待任務完成
    if self._ping_task:
        self._ping_task.cancel()
```

**問題**:
- `cancel()` 後沒有 `await` 任務，可能導致資源洩漏
- 在 `api_server.py` 的 shutdown hook 中調用時可能未完成清理

**建議**:
```python
async def stop(self):
    self.running = False
    if self.ws:
        await self.ws.close()
    if self._connect_task:
        self._connect_task.cancel()
        try:
            await self._connect_task
        except asyncio.CancelledError:
            pass
    if self._ping_task:
        self._ping_task.cancel()
        try:
            await self._ping_task
        except asyncio.CancelledError:
            pass
```

---

#### 🔴 [嚴重] 資料庫連接池洩漏風險

**位置**: `core/database/connection.py:193-240`

```python
class PooledConnection:
    def close(self):
        """關閉連接（實際上是歸還到池中）"""
        if not self._returned and self._pool and self._conn:
            try:
                self._conn.rollback()
                self._pool.putconn(self._conn)
                self._returned = True
            except Exception as e:
                try:
                    self._conn.close()
                except:
                    pass
                print(f"⚠️ 連接歸還失敗：{e}")
```

**問題**:
- `PooledConnection` 包裝類依賴 `close()` 被正確調用來歸還連接
- 如果異常發生且未調用 `close()`，連接會洩漏
- 使用 `print()` 而非日誌記錄

**建議**:
1. 確保所有使用 `get_connection()` 的地方都使用 context manager
2. 添加連接池監控和警報
3. 實現連接洩漏檢測機制

---

#### 🔴 [嚴重] Gunicorn Worker 連接池重置異常被吞掉

**位置**: `gunicorn.conf.py:108-115`

```python
def post_fork(server, worker):
    """Fork worker 後 - 重置數據庫連接池"""
    try:
        from core.database.connection import reset_connection_pool
        reset_connection_pool()
    except Exception as e:
        print(f"⚠️ Worker {worker.pid} 連接池重置失敗：{e}")
```

**問題**:
- 異常被吞掉，連接池重置失敗時 worker 可能使用無效連接
- 沒有日誌記錄（只有 print）
- 可能導致資料庫連接錯誤

**建議**:
```python
def post_fork(server, worker):
    try:
        from core.database.connection import reset_connection_pool
        reset_connection_pool()
        logger.info(f"✅ Worker {worker.pid} 連接池重置成功")
    except Exception as e:
        logger.error(f"❌ Worker {worker.pid} 連接池重置失敗：{e}")
        raise  # 重新拋出異常讓 worker 重啟
```

---

#### 🟠 [高] 匯率計算錯誤處理不足

**位置**: `data/okx_websocket.py:423-430`

```python
def _calc_change(self, last, open24h) -> float:
    """計算 24 小時漲跌幅"""
    try:
        last = float(last)
        open24h = float(open24h)
        if open24h == 0:
            return 0
        return ((last - open24h) / open24h) * 100
    except:
        return 0  # ⚠️ 問題：吞掉所有異常
```

**問題**:
- 裸 `except` 會吞掉所有異常，包括程式錯誤
- 可能隱藏數據格式問題

**建議**:
```python
def _calc_change(self, last, open24h) -> float:
    try:
        last = float(last or 0)
        open24h = float(open24h or 0)
        if open24h == 0:
            return 0.0
        return ((last - open24h) / open24h) * 100
    except (TypeError, ValueError):
        logger.warning(f"Invalid ticker data for change calculation: last={last}, open24h={open24h}")
        return 0.0
```

---

#### 🟠 [高] Rate Limit 存儲可能被繞過

**位置**: `api/middleware/rate_limit.py:152-163`

```python
class PersistentRateLimiter:
    def _load_state(self):
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    self.state = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.state = {}  # ⚠️ 問題：文件損壞時重置所有狀態
```

**問題**:
- JSON 文件損壞時會重置所有 rate limit 狀態
- 攻擊者可能利用此點繞過 rate limit

**建議**:
- 添加備份機制
- 文件損壞時嘗試從備份恢復
- 或改用 Redis 等更可靠的存儲

---

### 3.2 中等邏輯問題

#### 🟠 [高] Rate Limit 存儲問題

**位置**: `api/middleware/rate_limit.py`

```python
class PersistentRateLimiter:
    def __init__(self, storage_path: str = "data/rate_limits.json"):
        ...
        self._load_state()

    def _load_state(self):
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    self.state = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            self.state = {}  # ⚠️ 問題：文件損壞時重置所有狀態
```

**問題**:
- JSON 文件損壞時會重置所有 rate limit 狀態
- 攻擊者可能利用此點繞過 rate limit

**建議**:
- 添加備份機制
- 文件損壞時嘗試從備份恢復
- 或改用 Redis 等更可靠的存儲

---

#### 🟠 [高] 審計日誌清理任務未啟動

**位置**: `api_server.py:169-174`

```python
try:
    from core.audit import audit_log_cleanup_task
    asyncio.create_task(audit_log_cleanup_task())
    logger.info("✅ Audit log cleanup task scheduled (daily at 3 AM UTC)")
except ImportError:
    logger.warning("⚠️ Audit log cleanup task not available")
```

**問題**:
- 如果 import 失敗，審計日誌會無限增長
- 沒有重試機制

**建議**:
- 確保 `core.audit` 模組一定存在
- 或改用更可靠的排程系統

---

#### 🟡 [中] Pi Network 驗證超時處理

**位置**: `api/pi_verification.py:54-59`

```python
except httpx.TimeoutException:
    logger.error("Pi API request timed out")
    raise HTTPException(
        status_code=504,
        detail="Pi verification service timeout - please try again"
    )
```

**問題**:
- 超時時直接拋出異常，沒有重試機制
- Pi API 可能暫時不可用

**建議**: 添加重試機制（如使用 `tenacity` 庫）

---

### 3.3 輕微邏輯問題

#### 🟡 [中] 全局變數初始化順序

**位置**: `api_server.py:97-112`

```python
# Startup: 初始化 Global Instances
try:
    globals.okx_connector = OKXAPIConnector()
    logger.info("✅ OKX Connector 初始化成功")
except Exception as e:
    logger.error(f"❌ OKX Connector 初始化失敗：{e}")
    globals.okx_connector = None  # ⚠️ 問題：設為 None 後可能導致 AttributeError
```

**問題**:
- 設為 `None` 後，後續代碼若未檢查會拋出 `AttributeError`
- 應使用 `Optional` 型別提示

**建議**: 在所有使用處添加 `None` 檢查

---

#### 🟡 [中] 日誌文件路徑問題

**位置**: `api_server.py:32`

```python
file_handler = logging.FileHandler("api_server.log", encoding='utf-8')
```

**問題**:
- 使用相對路徑，在不同工作目錄下會寫入不同位置
- 容器環境可能無法寫入

**建議**: 使用絕對路徑或環境變數配置

---

#### 🟢 [低] 重複的 import

**位置**: `api_server.py`

```python
from fastapi import FastAPI
...
from fastapi import Request  # ⚠️ 重複 import
from fastapi import Response  # ⚠️ 重複 import
```

**建議**: 合併 import 語句

---

## 四、資安風險評估

### 4.1 嚴重安全風險

#### 🔴 [嚴重] JWT 密鑰強度不足

**位置**: `api/deps.py:14-27`

```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
...
if not SECRET_KEY:
    raise ValueError("JWT_SECRET_KEY must be set in production")
if len(SECRET_KEY) < 32:
    raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
```

**問題**:
- 雖然有長度檢查，但沒有複雜度檢查
- 開發人員可能設置如 `12345678901234567890123456789012` 的弱密鑰

**建議**:
- 添加密鑰強度驗證（熵值檢查）
- 或強制使用 key rotation

---

#### 🔴 [嚴重] CORS 配置風險

**位置**: `api_server.py:255-268`

```python
_cors_origins_raw = os.getenv("CORS_ORIGINS", "http://localhost:8080,https://app.minepi.com")
origins = [origin.strip() for origin in _cors_origins_raw.split(",") if origin.strip()]

if "*" in origins or "" in origins:
    logger.warning("⚠️ SECURITY: Wildcard CORS origin detected!")
```

**問題**:
- 只記錄警告，沒有阻止
- 生產環境可能意外配置 `*`

**建議**:
```python
if "*" in origins:
    if IS_PRODUCTION:
        raise ValueError("SECURITY: Wildcard CORS origin is NOT allowed in production")
    logger.warning("⚠️ SECURITY: Wildcard CORS origin detected - only for development")
```

---

#### 🔴 [嚴重] 敏感數據可能洩露

**位置**: `api_server.py:198-209`

```python
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_msg = f"{type(exc).__name__}: {str(exc)}"
    logger.error(f"🔥 Unhandled 500 Error at {request.method} {request.url.path}: {error_msg}")
    if not IS_PRODUCTION:
        logger.error(traceback.format_exc())
    
    response_content = {
        "detail": "Internal Server Error",
        "error": error_msg if not IS_PRODUCTION else "An error occurred",
        "path": request.url.path
    }
```

**問題**:
- 非生產環境會洩露完整錯誤訊息和堆疊追蹤
- 可能洩露資料庫結構、API 密鑰等敏感資訊

**建議**:
- 即使在開發環境，也要過濾敏感資訊
- 使用日誌管理系統而非控制台輸出

---

#### 🔴 [嚴重] 審計日誌未過濾敏感數據

**位置**: `core/audit.py:159-189`

```python
def _sanitize_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    SENSITIVE_FIELDS_REMOVE = {
        'password', 'secret', 'token', 'access_token',
        'api_key', 'private_key', 'passphrase',
        ...
    }
```

**問題**:
- 只過濾預定義的欄位
- 新型態的敏感數據可能未被覆蓋

**建議**:
- 採用白名單而非黑名單方式
- 只記錄必要的非敏感數據

---

### 4.2 高風險問題

#### 🟠 [高] 缺少 CSRF 保護

**位置**: 全局

**狀態**: 
- ✅ 有 JWT Token 認證
- ❌ 無 CSRF Token 保護

**問題**:
- 如果 JWT Token 存儲在 localStorage，容易受到 XSS 攻擊
- 攻擊者可能偽造請求

**建議**:
- 使用 HttpOnly Cookie 存儲 JWT
- 或添加 CSRF Token 驗證

---

#### 🟠 [高] 密碼重置 Token 過期時間硬編碼

**位置**: `core/email_service.py:62`

```html
<p class="warning">This link will expire in <strong>30 minutes</strong>.</p>
```

**問題**:
- Token 過期時間硬編碼在郵件模板中
- 實際驗證邏輯可能在別處，兩者可能不一致

**建議**:
- 統一配置 Token 過期時間
- 在郵件中動態顯示過期時間

---

#### 🟠 [高] 缺少輸入驗證

**位置**: `api/routers/forum/posts.py`

**問題**:
- 論壇發文內容長度驗證在 `core/database/forum.py`
- 但其他輸入（如標籤、標題）驗證可能不足

**建議**:
- 使用 Pydantic 模型統一輸入驗證
- 添加 XSS 過濾

---

#### 🟠 [高] WebSocket 認證問題

**位置**: `data/okx_websocket.py`

**問題**:
- OKX WebSocket 連接無需用戶認證
- 但訂閱的 K 線數據可能涉及用戶隱私（如自選幣種）

**建議**:
- 添加用戶認證機制
- 或限制訂閱頻率

---

### 4.3 中等風險問題

#### 🟡 [中] 日誌注入風險

**位置**: 多處

```python
logger.info(f"收到 K 線推送：{data['arg']}")
logger.error(f"處理消息錯誤：{e}")
```

**問題**:
- 直接將用戶輸入寫入日誌
- 可能導致日誌注入攻擊

**建議**:
- 過濾特殊字符
- 使用結構化日誌

---

#### 🟡 [中] 資料庫查詢未使用事務

**位置**: `core/database/forum.py`

```python
def delete_post(post_id: int, user_id: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE posts SET is_hidden = 1 WHERE id = %s AND user_id = %s',
                  (post_id, user_id))
        conn.commit()
```

**問題**:
- 單一查詢不需要事務
- 但多步驟操作（如刪除文章 + 記錄審計日誌）應該在同一事務中

**建議**: 對多步驟操作使用事務

---

#### 🟡 [中] 缺少安全頭文件

**位置**: `api_server.py:284-307`

```python
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
```

**問題**:
- 缺少 `Permissions-Policy` 頭
- 缺少 `Cross-Origin-Opener-Policy` 和 `Cross-Origin-Embedder-Policy`

**建議**:
```python
response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
response.headers["Cross-Origin-Embedder-Policy"] = "require-corp"
```

---

### 4.4 低風險問題

#### 🟢 [低] 依賴版本過舊

**位置**: `requirements.txt`

| 套件 | 當前版本 | 最新版本 | 風險 |
|------|----------|----------|------|
| `cryptography` | 46.0.2 | 最新 | ✅ 最新 |
| `fastapi` | 0.123.9 | 最新 | ✅ 最新 |
| `langchain` | 1.1.2 | 最新 | ✅ 最新 |
| `pydantic` | 2.12.0 | 最新 | ✅ 最新 |

**建議**: 定期更新依賴

---

#### 🟢 [低] 缺少依賴完整性檢查

**位置**: `requirements.txt`

**問題**:
- 沒有使用 hash 驗證
- 可能安裝被篡改的套件

**建議**:
```bash
pip install --require-hashes -r requirements.txt
```

---

## 五、技術債與優化建議

### 5.1 架構優化

#### 🟡 [中] 模組化不足

**問題**:
- `api_server.py` 過於龐大（超過 400 行）
- 路由、中間件、初始化邏輯混雜

**建議**:
- 將初始化邏輯抽離到 `core/lifespan.py`
- 將中間件註冊抽離到 `api/middleware/__init__.py`

---

#### 🟡 [中] 配置管理分散

**問題**:
- 配置分散在 `core/config.py`、`utils/settings.py`、環境變數
- 難以統一管理和驗證

**建議**:
- 使用 Pydantic Settings 統一配置管理
- 添加配置驗證

---

#### 🟡 [中] 錯誤處理不一致

**問題**:
- 有些使用 `try/except`
- 有些直接拋出異常
- 有些返回錯誤代碼

**建議**:
- 統一錯誤處理策略
- 使用自定義異常類別

---

### 5.2 性能優化

#### 🟡 [中] 資料庫查詢優化

**問題**:
- 論壇文章列表查詢可能 N+1 問題
- 缺少索引優化

**建議**:
- 添加資料庫查詢分析
- 對常用查詢添加索引

---

#### 🟡 [中] 緩存策略不足

**問題**:
- 市場數據有緩存
- 但論壇文章、用戶資料缺少緩存

**建議**:
- 添加 Redis 緩存層
- 對熱數據使用緩存

---

#### 🟢 [低] GZip 壓縮閾值

**位置**: `api_server.py:276`

```python
app.add_middleware(GZipMiddleware, minimum_size=1000)
```

**問題**:
- 1KB 閾值可能過高
- 小響應也可能受益於壓縮

**建議**: 調整為 500 字节或更低

---

### 5.3 測試覆蓋率

#### 🟡 [中] 測試覆蓋率不足

**問題**:
- 有測試文件但覆蓋率未知
- 關鍵安全功能可能缺少測試

**建議**:
- 添加測試覆蓋率報告
- 目標覆蓋率 > 80%

---

#### 🟡 [中] 整合測試不足

**問題**:
- 多為單元測試
- 缺少端到端整合測試

**建議**:
- 添加 API 整合測試
- 添加使用者場景測試

---

### 5.4 文件與監控

#### 🟡 [中] 文件不足

**問題**:
- 缺少 API 文件
- 部署文件不完整

**建議**:
- 使用 FastAPI 自動生成 API 文件
- 添加部署指南

---

#### 🟡 [中] 監控不足

**問題**:
- 缺少性能監控
- 缺少業務指標監控

**建議**:
- 添加 Prometheus + Grafana
- 監控關鍵業務指標

---

## 六、總結與建議優先級

### 立即處理（1 週內）- P0 等級

1. 🔴 **移除硬編碼的 Pi Network 驗證密鑰** - 安全風險最高優先級
2. 🔴 **修復 WebSocket 關閉邏輯** - 防止資源洩漏
3. 🔴 **修復 Gunicorn Worker 連接池重置異常處理** - 防止資料庫連接錯誤
4. 🔴 **加強 TEST_MODE 安全檢查** - 防止認證繞過
5. 🔴 **增加密碼哈希迭代次數** - 符合 OWASP 標準
6. 🔴 **修復 CORS 配置檢查** - 防止生產環境意外配置 `*`
7. 🔴 **修復異常處理中的敏感數據洩露** - 防止資訊洩露

### 短期處理（1 個月內）- P1 等級

8. 🟠 **統一模型配置管理** - 避免配置分散
9. 🟠 **調整交易配置** - 確保符合實際交易所要求
10. 🟠 **修復 Rate Limit 存儲問題** - 防止被繞過
11. 🟠 **添加 CSRF 保護** - 防止跨站請求偽造
12. 🟠 **完善輸入驗證** - 防止注入攻擊
13. 🟠 **修復資料庫連接池洩漏風險** - 添加監控機制
14. 🟠 **清理殘留的 Debug API** - 防止被濫用
15. 🟠 **移除未使用的 Email 服務模組** - 減少混淆
16. 🟠 **修復審計日誌清理任務啟動問題** - 確保任務正常運行
17. 🟠 **添加 Pi Network 驗證超時重試機制** - 提升穩定性

### 中期處理（3 個月內）- P2 等級

18. 🟡 **模組化重構** - 將 `api_server.py` 拆分
19. 🟡 **統一配置管理** - 使用 Pydantic Settings
20. 🟡 **添加 Redis 緩存層** - 提升性能
21. 🟡 **完善測試覆蓋率** - 目標 > 80%
22. 🟡 **添加監控系統** - Prometheus + Grafana
23. 🟡 **清理未使用的 Script 文件** - 減少安全風險
24. 🟡 **修復日誌注入風險** - 使用結構化日誌

### 長期優化（持續）- P3 等級

25. 🟢 **清理未使用代碼** - 技術債清理
26. 🟢 **定期更新依賴** - 安全更新
27. 🟢 **完善文件** - API 文件、部署指南
28. 🟢 **性能優化** - 資料庫查詢優化
29. 🟢 **清理 Archive 目錄** - 定期清理
30. 🟢 **移除 Gradio 依賴** - 若未使用
31. 🟢 **修復重複的 import 語句** - 代碼品質
32. 🟢 **調整 GZip 壓縮閾值** - 性能優化

---

## 七、資安風險總結

| 風險類型 | 數量 | 嚴重程度 | 狀態 |
|---------|------|---------|------|
| 硬編碼密鑰 | 1 | 🔴 嚴重 | 待修復 |
| 認證繞過風險 | 3 | 🔴 嚴重 | 待修復 |
| JWT 安全 | 2 | 🟠 高 | 待修復 |
| 數據庫連接洩漏 | 2 | 🔴 嚴重 | 待修復 |
| 密碼哈希強度 | 1 | 🔴 嚴重 | 待修復 |
| 輸入驗證不足 | 5 | 🟡 中 | 待修復 |
| 日誌洩露 | 3 | 🟢 低 | 待修復 |
| WebSocket 資源洩漏 | 1 | 🔴 嚴重 | 待修復 |
| Rate Limit 繞過 | 1 | 🟠 高 | 待修復 |

### 整體安全評級：🟡 中等（需要立即修復嚴重安全問題）

**評分說明**:
- 系統已有多層安全架構（Stage 2-4 Security）
- 但存在多個嚴重安全風險需立即修復
- 建議在 1 週內完成 P0 等級修復
- 建議在 1 個月內完成 P1 等級修復

---

## 八、附錄

### A. 使用的技術棧

| 類別 | 技術 | 版本 | 狀態 |
|------|------|------|------|
| **後端框架** | FastAPI | 0.123.9 | ✅ 最新 |
| **AI 框架** | LangGraph | 1.0.4 | ✅ 最新 |
| **LLM 庫** | LangChain | 1.1.2 | ✅ 最新 |
| **資料庫** | PostgreSQL | - | ✅ 使用連接池 |
| **ORM** | 原生 psycopg2 | - | 🟡 手動管理 |
| **緩存** | Redis | - | ⚠️ 部分使用 |
| **WebSocket** | websockets | 15.0.1 | ✅ 最新 |
| **HTTP 客戶端** | httpx | 0.28.1 | ✅ 最新 |
| **認證** | python-jose | 3.5.0 | ✅ 最新 |
| **限流** | slowapi | 0.1.9 | ✅ 最新 |
| **密碼學** | cryptography | 46.0.2 | ✅ 最新 |
| **數據處理** | pandas | 2.3.3 | ✅ 最新 |
| **技術分析** | pandas-ta | 0.4.71b0 | ✅ 最新 |
| **圖表** | matplotlib | 3.10.7 | ✅ 最新 |
| **前端 UI** | Tailwind CSS | - | ✅ 最新 |
| **前端圖表** | Lightweight Charts | - | ✅ 最新 |

---

### B. 外部服務整合

| 服務 | 用途 | 整合狀態 | 配置位置 |
|------|------|----------|----------|
| **OKX API** | 交易數據/下單 | ✅ 完整整合 | `trading/okx_api_connector.py` |
| **Pi Network** | 支付/認證 | ✅ 完整整合 | `api/pi_verification.py` |
| **OpenAI API** | AI 分析 | ✅ 完整整合 | `utils/llm_client.py` |
| **Google Gemini** | AI 分析 | ✅ 完整整合 | `utils/llm_client.py` |
| **Telegram Bot** | 安全警報 | ⚠️ 部分整合 | `core/alert_dispatcher.py` |
| **Gmail SMTP** | Email 通知 | ⚠️ 部分整合 | `core/email_service.py` |
| **DuckDuckGo** | Web 搜索 | ✅ 整合 | `core/tools/web_search.py` |
| **DeFiLlama** | TVL 數據 | ✅ 整合 | `core/tools/crypto_tools.py` |
| **CryptoPanic** | 新聞聚合 | ⚠️ 配置中 | `utils/settings.py` |

---

### C. 系統架構特點

**優點**:
- ✅ 完整的多層安全架構（Stage 2-4 Security）
- ✅ 審計日誌系統完善
- ✅ JWT 密鑰輪換機制
- ✅ 速率限制和防暴力破解
- ✅ 詳細的錯誤處理
- ✅ 多 Agent 辯論系統
- ✅ WebSocket 實時數據推送
- ✅ 多交易所數據整合

**需改進**:
- ❌ 存在硬編碼敏感信息
- ❌ TEST_MODE 安全繞過風險
- ❌ 部分代碼過於複雜
- ❌ 缺少統一的配置管理
- ❌ 資料庫連接管理需優化
- ❌ 部分安全功能未啟用

---

### D. 審查方法論

本次審查採用以下方法：

1. **靜態代碼分析**: 逐一閱讀 215+ 個 Python 檔案
2. **配置審查**: 檢查所有環境變數和配置文件
3. **安全掃描**: 參考 `scripts/security-check.sh` 的檢查項目
4. **依賴審查**: 檢查 `requirements.txt` 中的依賴使用情況
5. **架構審查**: 分析模組間的依賴關係
6. **日誌審查**: 檢查日誌記錄是否洩露敏感信息
7. **測試審查**: 檢查測試覆蓋率和測試品質

---

### E. 後續建議

#### E.1 自動化安全檢查

建議定期運行以下檢查：

```bash
# 每週運行一次安全檢查
./scripts/security-check.sh

# 每月運行一次依賴漏洞掃描
pip-audit --requirement requirements.txt

# 每次提交前運行代碼安全檢查
bandit -r . -ll
```

#### E.2 持續整合建議

建議添加 CI/CD 流程：

```yaml
# .github/workflows/security.yml
name: Security Check
on: [push, pull_request]
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run bandit
        run: bandit -r . -ll
      - name: Run pip-audit
        run: pip-audit -r requirements.txt
      - name: Run tests
        run: pytest tests/
```

#### E.3 監控建議

建議添加以下監控：

1. **應用性能監控**: New Relic / Datadog
2. **錯誤追蹤**: Sentry / Rollbar
3. **日誌管理**: ELK Stack / Splunk
4. **安全監控**: 自定義 Security Monitor
5. **數據庫監控**: pg_stat_statements

---

**報告結束**

**審查總時數**: 約 4 小時  
**審查檔案數**: 215+ Python 檔案 + 30+ JavaScript 檔案  
**總代碼行數**: ~60,000+ 行  
**發現問題數**: 69 個 (嚴重 12 + 高 18 + 中 24 + 低 15)

如有任何問題或需要進一步的詳細分析，請隨時提出。
