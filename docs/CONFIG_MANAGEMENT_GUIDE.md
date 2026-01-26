# 配置管理架構指南

## 當前實現（方案二：Redis + SQLite + 審計日誌）

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   API 請求   │ --> │ 進程內快取   │ --> │ Redis 快取  │ --> │  SQLite DB  │
└─────────────┘     │   (10秒)    │     │  (5分鐘)    │     └─────────────┘
                    └─────────────┘     └──────┬──────┘
                                               │
                                        Pub/Sub 失效通知
                                               │
                                        ┌──────▼──────┐
                                        │  其他進程    │
                                        └─────────────┘
```

**特點：**
- 多層快取：進程內(10秒) → Redis(5分鐘) → SQLite
- Redis Pub/Sub 跨進程快取失效通知
- 配置變更審計日誌
- **向下兼容**：未設置 Redis 時自動降級為純記憶體快取

---

## 快速開始

### 1. 安裝 Redis（可選但推薦）

```bash
# Docker 方式（推薦）
docker run -d --name redis -p 6379:6379 redis:alpine

# 或使用系統包管理器
# Ubuntu: sudo apt install redis-server
# macOS: brew install redis
```

### 2. 設置環境變數

```bash
# .env 文件
REDIS_URL=redis://localhost:6379/0
ADMIN_API_KEY=your_secure_admin_key_here
```

### 3. 安裝 Python 依賴

```bash
pip install redis==5.0.0
```

---

## 運行模式

| 模式 | 條件 | 特點 |
|------|------|------|
| **完整模式** | `REDIS_URL` 已設置且 Redis 可連接 | 多進程同步、Pub/Sub 通知 |
| **降級模式** | Redis 未安裝或未設置 | 純記憶體快取（單進程） |

系統會自動檢測並選擇適當的模式，無需額外配置。

---

## 方案比較

| 場景 | 推薦配置 |
|------|----------|
| 開發/測試 | 不需要 Redis（自動降級） |
| 單機生產 | 可選 Redis |
| 多進程/多機器 | **必須** Redis |
| Kubernetes | **必須** Redis

---

## 使用指南

### 修改價格配置

**方式一：透過管理 API（推薦）**

```bash
# 修改發文價格為 2 Pi
curl -X PUT "http://localhost:8000/api/admin/config/price" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your_admin_key" \
  -d '{"key": "create_post", "value": 2.0}'

# 修改打賞價格為 0.5 Pi
curl -X PUT "http://localhost:8000/api/admin/config/price" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your_admin_key" \
  -d '{"key": "tip", "value": 0.5}'
```

**方式二：透過 Python 代碼**

```python
from core.database import update_price, update_limit

# 修改價格
update_price('create_post', 2.0)
update_price('tip', 0.5)
update_price('premium', 10.0)

# 修改限制
update_limit('daily_post_free', 5)      # 改為每日 5 篇
update_limit('daily_post_premium', None) # PRO 無限制
```

### 修改限制配置

```bash
# 修改免費會員每日發文上限為 5
curl -X PUT "http://localhost:8000/api/admin/config/limit" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your_admin_key" \
  -d '{"key": "daily_post_free", "value": 5}'

# 設置 PRO 會員無限制（value = null）
curl -X PUT "http://localhost:8000/api/admin/config/limit" \
  -H "Content-Type: application/json" \
  -H "X-Admin-Key: your_admin_key" \
  -d '{"key": "daily_post_premium", "value": null}'
```

### 查看所有配置

```bash
curl "http://localhost:8000/api/admin/config" \
  -H "X-Admin-Key: your_admin_key"
```

### 查看配置變更歷史（需要 V2 模組）

```bash
curl "http://localhost:8000/api/admin/config/audit/price_create_post" \
  -H "X-Admin-Key: your_admin_key"
```

---

## 環境變數設置

```bash
# .env 文件

# 管理員 API Key（生產環境務必更改）
ADMIN_API_KEY=your_secure_admin_key_here

# Redis URL（可選，啟用方案二）
REDIS_URL=redis://localhost:6379/0
```

---

## 前端自動同步

前端會自動從以下 API 獲取最新配置：

- `GET /api/config/prices` - 價格配置
- `GET /api/config/limits` - 限制配置

所有帶 `data-price="xxx"` 屬性的元素會自動更新：

```html
<!-- 這些會自動顯示最新價格 -->
<span data-price="create_post"></span>
<span data-price="tip"></span>
<span data-price="premium"></span>
```

---

## 配置項目說明

### 價格配置 (pricing)

| Key | 說明 | 默認值 |
|-----|------|--------|
| `price_create_post` | 發文費用 | 1.0 Pi |
| `price_tip` | 打賞費用 | 1.0 Pi |
| `price_premium` | 高級會員費用 | 1.0 Pi |

### 限制配置 (limits)

| Key | 說明 | 默認值 |
|-----|------|--------|
| `limit_daily_post_free` | 免費會員每日發文上限 | 3 |
| `limit_daily_post_premium` | PRO 會員每日發文上限 | null (無限) |
| `limit_daily_comment_free` | 免費會員每日回覆上限 | 20 |
| `limit_daily_comment_premium` | PRO 會員每日回覆上限 | null (無限) |
