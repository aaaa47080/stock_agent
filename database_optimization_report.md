# 資料庫流量優化報告

## 📋 問題總結

### 核心問題
**寫入流量過高**：一個小時100MB的資料庫寫入，主要來自審計日誌中間件記錄所有API請求。

### 根本原因
審計中間件沒有過濾規則，記錄了：
- ❌ 健康檢查（每3-5秒一次）
- ❌ 靜態資源請求（每次頁面載入數十個）
- ❌ WebSocket 連接
- ❌ 高頻市場數據查詢（每秒可能多次）

---

## ✅ 已實施的修復

### 1. 審計日誌過濾優化
**檔案**：`api/middleware/audit.py`

**修改內容**：
- 添加 `SKIP_PATHS` 白名單，跳過健康檢查和靜態資源
- 添加 `READ_ONLY_MARKET_ENDPOINTS` 白名單，跳過高頻市場數據查詢
- 只記錄安全敏感操作（登入、支付、發文、刪文等）

**預期效果**：
- 寫入量從 **100MB/小時** 降至 **5-10MB/小時**
- 減少 **90%+** 的資料庫寫入

---

## 📊 後續監控建議

### 1. 檢查實際改善效果

連接到資料庫，執行以下查詢：

```sql
-- 查看最近1小時的審計日誌數量
SELECT COUNT(*) as total_logs,
       MIN(created_at) as earliest,
       MAX(created_at) as latest
FROM audit_logs
WHERE created_at > NOW() - INTERVAL '1 hour';

-- 查看最常被記錄的操作
SELECT action, COUNT(*) as count
FROM audit_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY action
ORDER BY count DESC
LIMIT 20;

-- 查看資料庫大小
SELECT pg_size_pretty(pg_database_size(current_database())) as db_size;

-- 查看各表大小
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
```

### 2. 設置自動清理機制

資料庫中已有清理函數，建議啟用定期清理：

```sql
-- 清理90天前的審計日誌（已在資料庫中定義）
SELECT archive_old_audit_logs();

-- 或手動刪除舊資料
DELETE FROM audit_logs WHERE created_at < NOW() - INTERVAL '90 days';
```

**建議**：使用 PostgreSQL 的 `pg_cron` 或外部排程工具，每週自動清理一次。

---

## 🔧 進階優化方案

### 方案1：使用批次寫入（Batch Insert）

**目的**：將多個審計日誌累積後一次寫入，減少資料庫連接開銷。

**實作方式**：
```python
# 在 core/audit.py 中添加
import queue
import threading

class BatchAuditLogger:
    def __init__(self, batch_size=10, flush_interval=5):
        self.queue = queue.Queue()
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._start_worker()
    
    def log(self, **kwargs):
        self.queue.put(kwargs)
        if self.queue.qsize() >= self.batch_size:
            self._flush()
    
    def _flush(self):
        # 批次寫入資料庫
        pass
```

### 方案2：改用檔案日誌 + 定期批次導入

**目的**：先寫入本地檔案（極快），再定期批次導入資料庫。

**優點**：
- ✅ 寫入速度極快（無資料庫等待）
- ✅ 減少資料庫連接池壓力
- ✅ 可離線分析日誌

**缺點**：
- ❌ 即時查詢延遲（需等待導入）

### 方案3：審計日誌分表（Partitioning）

**目的**：將審計日誌按月份分表，提升查詢和清理效率。

```sql
-- 為 audit_logs 建立分區表
CREATE TABLE audit_logs_2026_01 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

CREATE TABLE audit_logs_2026_02 PARTITION OF audit_logs
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
```

**優點**：
- ✅ 查詢速度更快（只掃描相關分區）
- ✅ 清理舊資料更簡單（直接刪除舊分區）
- ✅ 資料庫維護更靈活

---

## 🎯 推薦行動計畫

### 立即執行（已完成）
- [x] 添加審計日誌過濾規則
- [x] 排除高頻非敏感請求

### 短期優化（1-2週內）
- [ ] 監控實際改善效果
- [ ] 設置自動清理排程
- [ ] 檢查各表大小，確認是否有其他高頻寫入

### 中期優化（1個月內）
- [ ] 評估是否需要批次寫入
- [ ] 考慮審計日誌分表策略

### 長期規劃
- [ ] 如用戶量增長，考慮獨立審計日誌服務
- [ ] 使用專門的日誌分析工具（如 ELK Stack）

---

## 📝 其他可能的高頻寫入來源

根據代碼分析，以下功能也可能產生較多寫入：

### 1. 私訊功能
**檔案**：`core/database/messages.py`

每次發送訊息會寫入：
- `dm_messages` 表（訊息本身）
- `dm_conversations` 表（更新最後訊息時間和未讀數）
- `user_message_limits` 表（計數器）

**優化建議**：
- 未讀數可改為緩存，定期同步資料庫
- 訊息計數器可使用 Redis

### 2. 論壇功能
**檔案**：`core/database/forum.py`

每次發文/評論會寫入：
- `posts` / `forum_comments` 表
- `user_daily_posts` / `user_daily_comments` 表（計數器）
- `tags` 表（更新標籤統計）

**優化建議**：
- 計數器改用 Redis
- 標籤統計改為非同步批次更新

### 3. 用戶登入記錄
**檔案**：`core/database/user.py`

每次登入嘗試都會寫入 `login_attempts` 表。

**優化建議**：
- 只記錄失敗的嘗試
- 或改為記錄到日誌檔案

---

## 🔍 監控指標

建議持續監控以下指標：

### 資料庫層面
- **寫入速率**：MB/小時
- **連接池使用率**：活躍連接數 / 最大連接數
- **慢查詢**：執行時間 > 1秒的查詢

### 應用層面
- **API 回應時間**：P50, P95, P99
- **錯誤率**：5xx 錯誤百分比
- **請求量**：每分鐘請求數

### 資料表大小
- `audit_logs`：最大的表，需定期清理
- `dm_messages`：隨用戶增長而增長
- `posts`、`forum_comments`：隨內容增長而增長

---

## 📞 聯繫與支援

如發現其他效能問題，請：
1. 檢查 `api_server.log` 和 `frontend_debug.log`
2. 使用上述 SQL 查詢分析資料庫狀態
3. 監控伺服器資源使用（CPU、記憶體、磁碟 I/O）

---

> **總結**：透過智能過濾審計日誌，預期可將資料庫寫入流量從 100MB/小時 降至 5-10MB/小時，大幅改善系統效能。後續可根據實際監控數據，進一步優化其他高頻寫入操作。
