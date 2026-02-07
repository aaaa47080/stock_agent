# 貼文刪除功能實作指南

## 概述

本次更新為系統添加了以下功能：
1. ✅ 用戶可以刪除自己的貼文
2. ✅ 安全審查和漏洞修復
3. ✅ XSS 防護增強
4. ✅ 審計日誌記錄

## 一、新增功能

### 1.1 貼文刪除功能

**前端實現**：
- 在貼文詳情頁添加「刪除」按鈕（只對作者顯示）
- 添加刪除確認對話框
- 刪除成功後自動導航回首頁

**後端實現**：
- 使用軟刪除機制（`is_hidden = 1`）
- 只有作者可以刪除自己的貼文
- 自動記錄審計日誌

**使用方法**：
1. 登入系統
2. 瀏覽到自己發布的貼文
3. 在標題下方會看到「編輯」和「刪除」按鈕
4. 點擊「刪除」
5. 在確認對話框中選擇「確認刪除」
6. 貼文將被軟刪除並重定向到首頁

### 1.2 編輯功能（預留接口）

**狀態**: 前端 UI 已添加，後端已實現，但編輯邏輯尚未完整實現

**後端 API**：
- `PUT /api/forum/posts/{post_id}`
- 已有認證和授權檢查
- 支持更新標題、內容、分類

**前端 API**：
```javascript
// 已添加到 ForumAPI
await ForumAPI.updatePost(postId, {
    title: "新標題",
    content: "新內容",
    category: "analysis"
});
```

**待完成**：
- 創建編輯模態框或編輯頁面
- 實現編輯表單
- 添加編輯前的內容預填充

## 二、安全增強

### 2.1 XSS 防護

**新增工具**：`web/js/security-utils.js`

**功能**：
1. HTML 轉義
2. DOMPurify 清理
3. 安全的 Markdown 渲染
4. 安全的鏈接創建
5. 輸入驗證

**使用示例**：
```javascript
// 1. 轉義 HTML
const safe = SecurityUtils.escapeHTML(userInput);

// 2. 清理 HTML
const clean = SecurityUtils.sanitizeHTML(dirtyHTML);

// 3. 安全渲染 Markdown
const safeHTML = SecurityUtils.renderMarkdownSafely(markdown);

// 4. 創建安全鏈接
const link = SecurityUtils.createSafeLink(
    '/profile?id=123',
    '用戶名',
    { className: 'text-primary' }
);

// 5. 驗證輸入
const result = SecurityUtils.validateInput(userInput, {
    required: true,
    minLength: 5,
    maxLength: 200,
    pattern: /^[a-zA-Z0-9]+$/,
    patternError: '只允許字母和數字'
});
```

### 2.2 審計日誌

**記錄內容**：
- 用戶 ID
- 操作類型（DELETE_POST）
- 資源類型和 ID
- 操作時間
- 成功/失敗狀態
- 錯誤訊息（如果失敗）

**查詢審計日誌**：
```sql
-- 查看所有刪除操作
SELECT * FROM audit_logs
WHERE action = 'DELETE_POST'
ORDER BY timestamp DESC;

-- 查看特定用戶的操作
SELECT * FROM audit_logs
WHERE user_id = 'user123'
ORDER BY timestamp DESC;

-- 查看失敗的操作
SELECT * FROM audit_logs
WHERE success = FALSE
ORDER BY timestamp DESC;
```

### 2.3 TEST_MODE 安全檢查

**新增檢查**：
```python
# 禁止在生產環境啟用 TEST_MODE
if TEST_MODE:
    env = os.getenv("ENVIRONMENT", "development").lower()
    if env in ["production", "prod"]:
        raise ValueError("🚨 SECURITY ALERT: TEST_MODE must not be enabled in production")
```

**配置環境變數**：
```bash
# .env 文件
ENVIRONMENT=production  # 或 development, staging
TEST_MODE=false
```

## 三、已修復的安全問題

### 3.1 XSS 漏洞修復

**問題**：
- 用戶輸入直接插入 innerHTML
- markdown-it 允許 HTML 標籤

**修復**：
- 添加 DOMPurify 清理
- 配置 markdown-it 禁用 HTML
- 使用 textContent 或安全函數

**影響範圍**：
- ✅ 貼文內容渲染
- ✅ 用戶名顯示
- ✅ 評論內容
- ✅ 標籤顯示

### 3.2 IDOR 防護

**驗證**：
```python
# 雙重驗證確保只有作者可以刪除
if current_user["user_id"] != user_id:
    raise HTTPException(status_code=403, detail="Not authorized")

# 資料庫層面再次驗證
c.execute('UPDATE posts SET is_hidden = 1 WHERE id = %s AND user_id = %s',
          (post_id, user_id))
```

### 3.3 SQL 注入防護

**驗證結果**：
- ✅ 所有查詢使用參數化查詢
- ✅ 沒有字符串拼接
- ✅ 使用 psycopg2 的參數綁定

## 四、尚未實現的安全建議

### 4.1 CSRF 保護 ⚠️

**狀態**: 未實現

**建議實現方案**：
```python
# 1. 生成 CSRF Token
from secrets import token_urlsafe

def generate_csrf_token():
    return token_urlsafe(32)

# 2. 在登入時設置 Cookie
response.set_cookie(
    key="csrf_token",
    value=csrf_token,
    httponly=True,
    secure=True,
    samesite="Lax"
)

# 3. 驗證 CSRF Token
async def verify_csrf_token(
    x_csrf_token: str = Header(None),
    csrf_cookie: str = Cookie(None)
):
    if not x_csrf_token or x_csrf_token != csrf_cookie:
        raise HTTPException(status_code=403, detail="CSRF token invalid")
```

### 4.2 Rate Limiting ⚠️

**狀態**: 未實現

**建議實現方案**：
```python
# 使用 slowapi
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.delete("/{post_id}")
@limiter.limit("10/minute")
async def delete_post_by_id(...):
    ...
```

### 4.3 內容安全政策 (CSP) ⚠️

**狀態**: 未實現

**建議添加**：
```python
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data: https:; "
        "font-src 'self' https://fonts.gstatic.com;"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

## 五、測試指南

### 5.1 功能測試

**測試刪除功能**：
```
1. 創建測試帳號並登入
2. 發布一篇測試貼文
3. 進入貼文詳情頁
4. 驗證可以看到「刪除」按鈕
5. 點擊「刪除」並確認
6. 驗證貼文已被隱藏
7. 嘗試訪問該貼文 URL
8. 應該顯示「文章已被刪除」
```

**測試授權檢查**：
```
1. 使用帳號 A 發布貼文
2. 登出並使用帳號 B 登入
3. 嘗試訪問帳號 A 的貼文
4. 驗證看不到「刪除」按鈕
5. 手動調用 API 嘗試刪除
6. 應該返回 403 錯誤
```

### 5.2 安全測試

**測試 XSS 防護**：
```
1. 創建貼文，內容包含：
   <script>alert('XSS')</script>
   <img src=x onerror="alert('XSS')">
2. 查看貼文詳情
3. 驗證腳本未執行
4. 檢查 DOM，確認危險標籤已被移除
```

**測試 SQL 注入**：
```
1. 嘗試刪除 post_id = "1' OR '1'='1"
2. 應該返回錯誤或找不到貼文
3. 檢查資料庫，確認沒有異常刪除
```

## 六、部署注意事項

### 6.1 環境變數檢查

部署前確保設置：
```bash
ENVIRONMENT=production
TEST_MODE=false
JWT_SECRET_KEY=<強密鑰>
DATABASE_URL=<生產數據庫>
```

### 6.2 資料庫遷移

審計日誌表已在 `init_db()` 中自動創建，無需手動遷移。

### 6.3 靜態資源

確保以下文件可訪問：
- `/static/js/security-utils.js`
- `/static/js/forum.js`
- DOMPurify CDN (已添加到 post.html)

### 6.4 監控和告警

建議監控：
```sql
-- 監控刪除操作頻率
SELECT DATE(timestamp) as date, COUNT(*) as delete_count
FROM audit_logs
WHERE action = 'DELETE_POST'
GROUP BY DATE(timestamp)
ORDER BY date DESC;

-- 監控失敗的刪除嘗試
SELECT user_id, COUNT(*) as failed_attempts
FROM audit_logs
WHERE action = 'DELETE_POST' AND success = FALSE
GROUP BY user_id
HAVING COUNT(*) > 5
ORDER BY failed_attempts DESC;
```

## 七、後續改進建議

### 7.1 短期（1-2週）
- [ ] 實現編輯功能的完整 UI
- [ ] 添加 CSRF 保護
- [ ] 添加 Rate Limiting
- [ ] 改進錯誤訊息處理

### 7.2 中期（1個月）
- [ ] 實現內容安全政策 (CSP)
- [ ] 添加圖片上傳的安全檢查
- [ ] 實現更完善的審計日誌查詢介面
- [ ] 添加管理員恢復刪除貼文功能

### 7.3 長期（持續）
- [ ] 考慮升級到 RS256 JWT 算法
- [ ] 實現兩因素認證（2FA）
- [ ] 添加更細粒度的權限控制
- [ ] 實現自動安全掃描

## 八、聯繫與支持

如有問題或建議，請：
1. 查看 `SECURITY_AUDIT_REPORT.md` 了解詳細的安全分析
2. 查看代碼註釋了解實現細節
3. 提交 GitHub Issue 報告問題
