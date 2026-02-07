# 社群治理系統 - 設計文檔

**創建日期**: 2026-02-07
**狀態**: 設計完成，待實施
**優先級**: 高 - Phase 3 核心功能

---

## 一、功能概述

### 目標
建立一個**去中心化的社群治理系統**，讓 PRO 用戶作為「審核節點」共同維護社群健康，實現類似區塊鏈的多方決策機制。

### 核心特性
- 🛡️ **用戶檢舉系統** - 檢舉不當文章/評論，維護內容品質
- ⚖️ **PRO 審核隊列** - PRO 用戶投票判定違規，累積審核聲望
- 📊 **違規統計與停權** - 點數制度，累積違規自動停權（PRO 優待）
- 📋 **活動日誌** - 用戶可查看所有操作記錄，增加透明度
- 🔍 **透明監督** - 所有審核記錄公開，任何人可查核

### 去中心化設計理念

| 區塊鏈概念 | 對應到系統 |
|-----------|-----------|
| **Node 驗證** | PRO 用戶作為審核節點 |
| **共識機制** | 多數投票決定結果（70% 閾值） |
| **激勵模型** | 聲望值代替代幣獎勵 |
| **透明度** | 活動日誌公開可查 |
| **抗作弊** | 分散決策防單點操控 |

---

## 二、違規與停權機制

### 2.1 違規等級定義

| 違規等級 | 類型 | 範例 | 免費用戶 | PRO 用戶 |
|----------|------|------|----------|----------|
| **輕微** | 垃圾內容、輕微引戰 | 重複貼文、無意義留言 | 記點 1 次 | 記點 1 次 |
| **中等** | 人身攻擊、散布謠言 | 謾罵、造謠、誤導投資 | 記點 3 次 | 記點 2 次 |
| **嚴重** | 詐騙、惡意破壞 | 詐騙錢財、假冒身份 | 直接停權 30 天 | 記點 5 次 |
| **極嚴重** | 違法、駭客行為 | 洗錢、系統入侵 | 永久停權 | 永久停權 |

### 2.2 停權門檻

| 累積點數 | 處罰 | PRO 用戶 |
|----------|------|----------|
| 5 點 | 禁言 3 天（可看不可發言） | 相同 |
| 10 點 | 停權 7 天 | 相同 |
| 20 點 | 停權 30 天 | 相同 |
| 30 點 | 永久停權 | 相同 |

### 2.3 點數遞減機制

- 每連續 **30 天**無違規，點數 **-1**
- 鼓勵用戶改善行為，自動恢復

### 2.4 資料庫表結構

```sql
-- 用戶違規點數表
CREATE TABLE user_violation_points (
    user_id TEXT PRIMARY KEY,
    points INTEGER DEFAULT 0,
    last_violation_at TIMESTAMP,
    last_decrement_at TIMESTAMP,

    -- 統計
    total_violations INTEGER DEFAULT 0,
    suspension_count INTEGER DEFAULT 0,

    updated_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_violation_points ON user_violation_points(points DESC);

-- 違規記錄表
CREATE TABLE user_violations (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    violation_level TEXT NOT NULL,  -- mild/medium/severe/critical
    violation_type TEXT NOT NULL,
    points INTEGER DEFAULT 0,

    -- 觸發來源
    source_type TEXT NOT NULL,      -- 'report', 'admin_action'
    source_id INTEGER,

    -- 處罰結果
    action_taken TEXT,              -- 'warning', 'suspend_3d', 'suspend_7d', etc.
    suspended_until TIMESTAMP,

    processed_by TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_violations_user ON user_violations(user_id, created_at DESC);
CREATE INDEX idx_violations_level ON user_violations(violation_level);
```

---

## 三、用戶檢舉系統

### 3.1 檢舉類型定義

| 類型 ID | 名稱 | 嚴重等級 | 說明 |
|---------|------|----------|------|
| `spam` | 垃圾內容 | 輕微 | 重複貼文、無意義留言 |
| `harassment` | 騷擾攻擊 | 中等 | 人身攻擊、惡意標籤 |
| `misinformation` | 錯誤資訊 | 中等 | 散布虛假消息、誤導投資 |
| `scam` | 詐騙行為 | 嚴重 | 詐騙錢財、假冒身份 |
| `illegal` | 非法內容 | 極嚴重 | 違法內容、洗錢 |
| `other` | 其他 | 依情況 | 其他違規行為 |

### 3.2 檢舉流程

```
用戶點擊檢舉 → 選擇檢舉類型 → 填寫說明（選填）→ 提交
                      ↓
              進入待審核隊列
                      ↓
         PRO 審核員投票處理
                      ↓
              違規/不違規判定
                      ↓
        違規：執行處罰 + 通知檢舉者
        不違規：關閉案件
```

### 3.3 檢舉限制（防止濫用）

- 每人每天最多 **10 次** 檢舉
- 同一內容只能被檢舉 **1 次**
- 惡意檢舉（超過 50% 被駁回）會降低檢舉權重
- 檢舉者資訊對被檢舉者隱藏

### 3.4 資料庫表結構

```sql
CREATE TABLE content_reports (
    id SERIAL PRIMARY KEY,

    -- 被檢舉內容
    content_type TEXT NOT NULL,      -- 'post' 或 'comment'
    content_id INTEGER NOT NULL,

    -- 檢舉者
    reporter_user_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    description TEXT,

    -- 審核狀態
    review_status TEXT DEFAULT 'pending',  -- pending/approved/rejected
    violation_level TEXT,                   -- mild/medium/severe/critical

    -- 處理結果
    action_taken TEXT,                      -- 警告/刪除/停權
    points_assigned INTEGER DEFAULT 0,
    processed_by TEXT,                      -- 審核員 user_id

    -- 投票統計（類似 scam_tracker）
    approve_count INTEGER DEFAULT 0,        -- 認為違規
    reject_count INTEGER DEFAULT 0,         -- 認為不違規

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(reporter_user_id, content_type, content_id),
    FOREIGN KEY (reporter_user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_report_content ON content_reports(content_type, content_id);
CREATE INDEX idx_report_status ON content_reports(review_status);
CREATE INDEX idx_report_created ON content_reports(created_at DESC);

-- 審核投票表（複用 scam_tracker 概念）
CREATE TABLE report_review_votes (
    id SERIAL PRIMARY KEY,
    report_id INTEGER NOT NULL,
    reviewer_user_id TEXT NOT NULL,
    vote_type TEXT NOT NULL,                -- 'approve' (違規) / 'reject' (不違規)
    vote_weight FLOAT DEFAULT 1.0,          -- 權重（基於聲望）
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(report_id, reviewer_user_id),
    FOREIGN KEY (report_id) REFERENCES content_reports(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_user_id) REFERENCES users(user_id)
);

CREATE INDEX idx_review_report ON report_review_votes(report_id);
CREATE INDEX idx_review_user ON report_review_votes(reviewer_user_id);
```

---

## 四、PRO 審核隊列

### 4.1 審核機制

```
待審核案件池
      ↓
PRO 用戶進入審核介面
      ↓
查看案件詳情（隱私已遮罩）
      ↓
投票：違規 / 不違規
      ↓
達到門檻後自動結案
      ↓
執行處罰（若違規）
```

### 4.2 審核門檻

| 條件 | 閾值 |
|------|------|
| 最低投票數 | **3 位** PRO 用戶 |
| 違規判定 | **≥70%** 投「違規」 |
| 不違規判定 | **≤30%** 投「違規」 |
| 中間區段 | 需要更多投票達到門檻 |

### 4.3 PRO 用戶參與誘因（非金流）

| 獎勵類型 | 說明 |
|----------|------|
| **審核聲望值** | 每次有效審核 +1，與一般聲望分開 |
| **專屬徽章** | 累積 100/500/1000 次解鎖徽章 |
| **特殊權限** | 高聲望者可查看未公開的統計數據 |
| **排行榜** | 每月審核排行榜，前 10 名特殊標示 |

### 4.4 權重投票制（溫和設計）

```javascript
// 權重計算（溫和，避免寡頭）
function getVoteWeight(user) {
    baseWeight = 1.0
    reputationBonus = Math.min(user.auditReputation / 1000, 0.1)  // 最多 +10%
    accuracyBonus = (user.accuracyRate - 0.9) * 0.5  // 準確率 >90% 才有加成

    return baseWeight + reputationBonus + accuracyBonus
}

// 結果：新手 1.0 票，高聲望者 1.1 票（差異不大）
```

### 4.5 防作弊機制

- 不能審核自己檢舉的案件
- 不能審核自己發表的內容
- 連續 **5 次**與多數意見相反 → 暫停審核權限 24 小時
- 惡意投票（被駁回的案件）會扣除審核聲望

### 4.6 前端介面設計

```
┌─────────────────────────────────────┐
│  🛡️ 內容審核隊列 (PRO 專用)         │
├─────────────────────────────────────┤
│                                      │
│  📊 你的統計                         │
│  • 審核次數: 127                    │
│  • 準確率: 94%                      │
│  • 聲望排名: #15                    │
│  • 投票權重: 1.08x                  │
│                                      │
│  ┌─────────────────────────────────┐ │
│  │ 📝 案件 #4523                   │ │
│  │ 檢舉類型: 騷擾攻擊               │ │
│  │                                │ │
│  │ [隱私遮罩內容]                  │ │
│  │ 「用戶 A 在評論中...」           │ │
│  │                                │ │
│  │ 投票你的判斷:                  │ │
│  │ [🚫 違規]  [✅ 不違規]         │ │
│  └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

---

## 五、活動日誌系統

### 5.1 日誌記錄的活動類型

| 類別 | 記錄項目 |
|------|----------|
| **內容** | 發文、評論、編輯、刪除、被檢舉 |
| **社群** | 好友申請、私訊、檢舉他人 |
| **審核** | 投票、審核案件 |
| **違規** | 被檢舉、被處罰、點數變動 |
| **系統** | 登入、登出、設定變更 |

### 5.2 資料庫表結構

```sql
CREATE TABLE user_activity_logs (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,

    -- 活動詳情
    activity_type TEXT NOT NULL,      -- 'post_created', 'comment_liked', etc.
    resource_type TEXT,               -- 'post', 'comment', 'user'
    resource_id INTEGER,

    -- 額外資料（JSON 格式）
    metadata JSONB,                   -- 靈活存儲各種資訊

    -- 結果
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,

    -- 時間與 IP
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT NOW(),

    INDEX idx_user_activity (user_id, created_at DESC),
    INDEX idx_activity_type (activity_type)
);
```

### 5.3 隱私保護

- 用戶只能查看**自己的**日誌
- 敏感資訊（密碼、API Key）從不記錄
- 日誌保留 **90 天**後自動歸檔/刪除

### 5.4 前端介面設計

```
┌─────────────────────────────────────┐
│  📋 我的活動日誌                    │
├─────────────────────────────────────┤
│  🔍 [搜尋] 📅 [日期篩選] 🏷️ [類型]   │
│                                      │
│  📊 統計摘要                         │
│  • 本月發文: 12 篇                   │
│  • 獲得讚: 156 個                    │
│  • 審核案件: 23 件                   │
│  • 當前違規點數: 2                  │
│                                      │
│  時間軸:                             │
│  │                                  │
│  ├─ 今天 14:30                       │
│  │  ✅ 審核案件 #4521                │
│  │                                  │
│  ├─ 今天 11:20                       │
│  │  📝 發表文章「BTC 技術分析」       │
│  │  💬 獲得 3 個新留言               │
│  │                                  │
│  ├─ 昨天 18:45                       │
│  │  ⚠️ 收到違規警告 (點數+1)         │
│  │  原因: 垃圾留言                   │
│  │                                  │
│  └─ ...                             │
└─────────────────────────────────────┘
```

---

## 六、透明監督機制

### 6.1 公開審核記錄

所有審核案件（除隱私資訊外）皆公開，任何人可查核：

```
/api/governance/review-records?report_id=4523

{
  "report_id": 4523,
  "status": "approved",
  "violation_level": "medium",
  "votes": {
    "approve": 5,
    "reject": 2,
    "total": 7
  },
  "decision": "違規 - 騷擾攻擊",
  "action": "刪除內容 + 記點 3",
  "reviewers": [
    {"user_id": "***123", "vote": "approve", "weight": 1.0},
    {"user_id": "***456", "vote": "reject", "weight": 1.05},
    ...
  ]
}
```

### 6.2 審核統計公開

- 每月審核案件統計
- 審核員準確率排行
- 檢舉成功率統計

---

## 七、API 路由設計

### 7.1 檢舉管理 API

| 方法 | 路徑 | 權限 | 功能 |
|------|------|------|------|
| POST | `/api/governance/reports` | 登入用戶 | 提交檢舉 |
| GET | `/api/governance/reports` | PRO | 待審核案件列表 |
| GET | `/api/governance/reports/{id}` | PRO | 案件詳情 |

### 7.2 審核投票 API

| 方法 | 路徑 | 權限 | 功能 |
|------|------|------|------|
| POST | `/api/governance/votes/{report_id}` | PRO | 投票（Toggle） |
| GET | `/api/governance/my-votes` | PRO | 我的投票記錄 |

### 7.3 違規與日誌 API

| 方法 | 路徑 | 權限 | 功能 |
|------|------|------|------|
| GET | `/api/governance/my-points` | 登入用戶 | 我的違規點數 |
| GET | `/api/governance/my-logs` | 登入用戶 | 我的活動日誌 |
| GET | `/api/governance/review-records` | 公開 | 審核記錄（透明監督） |

---

## 八、前端頁面設計

### 8.1 頁面結構

```
web/governance/
├── index.html          # 治理儀表板
├── review.html         # 審核介面 (PRO 專用)
├── report.html         # 檢舉表單
├── logs.html           # 活動日誌
└── js/
    └── governance.js    # 核心邏輯
```

---

## 九、安全機制

### 9.1 防範檢舉攻擊

- 速率限制：每用戶每天最多 10 次檢舉
- 重複檢舉防護：同一內容只能檢舉一次
- 惡意檢舉懲罰：被駁回率 > 50% 降低權重

### 9.2 防範審核作弊

- 自我審核防護：不能審核自己的內容
- 串通檢測：連續與多數意識相反會暫停權限
- 隱私保護：被檢舉者看不到檢舉者身份

### 9.3 Rate Limiting

```python
@limiter.limit("10/minute")   # 提交檢舉
@limiter.limit("30/minute")   # 審核投票
```

---

## 十、成功標準

### 功能完整性
- ✅ 用戶可檢舉不當內容
- ✅ PRO 用戶可參與審核投票
- ✅ 違規點數自動累積
- ✅ 達到門檻自動停權
- ✅ 活動日誌完整記錄
- ✅ 審核記錄公開透明

### 性能指標
- ⚡ 檢舉提交 < 200ms
- ⚡ 審核頁面載入 < 300ms
- ⚡ 投票響應 < 200ms
- ⚡ 活動日誌查詢 < 500ms

### 社群健康指標
- 📉 不當內容處理率 > 80%
- 📉 重複違規率下降
- 📈 審核參與率上升

---

## 十一、參考資料

- 現有詐騙追蹤系統：`docs/plans/2026-02-07-scam-wallet-tracker-design.md`
- 論壇系統：`api/routers/forum/`
- 會員系統：`api/routers/premium.py`
- 審計日誌：`api/routers/audit.py`

---

**設計完成日期**: 2026-02-07
**預計開發時間**: 5-7 個工作日
**下一步**: 創建詳細實施計劃
