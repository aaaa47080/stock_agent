# 管理後台設計方案

## 概述

在現有 SPA 內新增 Admin 管理後台，採用獨立模組架構（方案 B），支援角色制認證。第一版實作廣播通知 + 用戶管理，後續可擴展論壇管理、系統設定、統計儀表板。

## 關鍵決策

| 決策 | 選擇 | 原因 |
|------|------|------|
| 認證方式 | 用戶角色制 | 支援多人管理，前端可根據 role 動態顯示 |
| UI 位置 | SPA 內嵌 Admin Tab | Pi Browser WebView 不適合跳轉，復用現有基礎設施 |
| 代碼架構 | 獨立模組 | admin.js + admin_panel.py 不污染主 app，擴展性好 |

## 架構

```
index.html (主 SPA)
├── 現有 tabs...
└── Admin Tab (role === 'admin' 才顯示)
    ├── 子導覽列 [📢 廣播通知] [👥 用戶管理] [未來擴展...]
    ├── 廣播通知頁
    │   ├── 發送表單（標題、內容、類型選擇）
    │   ├── 預覽區
    │   └── 歷史紀錄列表
    └── 用戶管理頁
        ├── 搜尋欄
        ├── 用戶列表（頭像、名稱、角色、會員狀態、註冊時間）
        └── 用戶操作（設角色 / 設 Pro / 封鎖）
```

## 角色系統

### DB 改動

```sql
ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user';
ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;

CREATE TABLE admin_broadcasts (
    id SERIAL PRIMARY KEY,
    admin_user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    type TEXT DEFAULT 'announcement',
    recipient_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 中間件

```python
# api/deps.py
async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return current_user
```

### 前端判斷

```javascript
// nav-config.js - Admin tab
{ id: 'admin', icon: 'shield', label: 'Admin',
  visible: () => AuthManager.currentUser?.role === 'admin',
  locked: true }
```

## API 端點

### 通知廣播

```
POST /api/admin/notifications/broadcast
  body: { title, body, type: "announcement" | "system_update" }
  → 查所有活躍 user_id → 批量建 notification → WebSocket push
  → 返回 { success, sent_count, online_count }

GET  /api/admin/notifications/history?page=&limit=
  → 廣播歷史紀錄
```

### 用戶管理

```
GET    /api/admin/users?search=&page=&limit=
  → 用戶列表，支援搜尋，分頁

GET    /api/admin/users/{user_id}
  → 單一用戶詳情

PUT    /api/admin/users/{user_id}/role
  body: { role: "admin" | "user" }

PUT    /api/admin/users/{user_id}/membership
  body: { tier: "pro" | "free", months: 3 }

PUT    /api/admin/users/{user_id}/status
  body: { active: true/false, reason: "..." }
```

所有端點統一用 `Depends(require_admin)` 保護。

## 資料流

### 廣播通知

```
Admin 填寫表單 → POST /api/admin/notifications/broadcast
  → 後端查所有活躍 user_id
  → 批量 INSERT INTO notifications
  → 遍歷在線用戶 WebSocket push
  → 寫入 admin_broadcasts 紀錄
  → 返回 { success, sent_count, online_count }
```

### 用戶管理

```
Admin 搜尋 → GET /api/admin/users?search=xxx
  → LIKE 搜尋 username / user_id → 返回分頁列表

Admin 設 Pro → PUT /api/admin/users/{id}/membership
  → 呼叫現有 upgrade_to_pro() → 寫 audit log

Admin 封鎖 → PUT /api/admin/users/{id}/status
  → 設 is_active = false → 寫 audit log → WebSocket 推送強制登出
```

### 審計紀錄

所有 admin 操作寫入 config_audit_log：
```
| changed_by | config_key         | old_value | new_value | changed_at |
|-----------|-------------------|-----------|-----------|------------|
| admin_hao | user_role:user_123 | user      | admin     | 2026-02-13 |
| admin_hao | broadcast          | null      | {title..} | 2026-02-13 |
```

## 前端模組

### 新檔案：web/js/admin.js

```javascript
const AdminPanel = {
    currentSubPage: 'broadcast',

    init() { /* 渲染子導覽 + 預設頁 */ },
    switchSubPage(page) { /* broadcast | users | ... */ },

    BroadcastManager: {
        renderForm() {},
        send() {},
        loadHistory() {}
    },

    UserManager: {
        search() {},
        loadUsers() {},
        setRole() {},
        setMembership() {},
        toggleStatus() {}
    }
};
```

## 檔案結構

### 新增

```
api/routers/admin_panel.py    — Admin 管理 API（廣播 + 用戶管理）
web/js/admin.js               — Admin 前端模組
```

### 修改

```
core/database/connection.py   — 加 role、is_active 欄位 + admin_broadcasts 表
api/deps.py                   — 加 require_admin 中間件
web/js/nav-config.js          — 加 Admin tab（role-gated）
web/js/components.js          — 加 Admin tab 模板
web/index.html                — 加 admin tab div + script 引用
```

## 分階段交付

### P0（本次實作）

1. DB migration：加欄位 + 建表
2. require_admin 中間件
3. Admin API：廣播通知 + 用戶管理
4. 前端 Admin 模組
5. Admin tab 註冊到 SPA
6. 設定管理員帳號

### P1（之後擴展）

- 論壇管理子頁（隱藏/刪文、處理舉報）
- 系統設定子頁（現有 config API 加 UI）

### P2（錦上添花）

- 統計儀表板（用戶增長、活躍度、論壇數據）
- 圖表用 Chart.js CDN

### 擴展模式

每個新功能 = 一個子導覽項 + 一個 Manager 物件 + 對應 API router，不動既有代碼。

---

設計日期：2026-02-13
