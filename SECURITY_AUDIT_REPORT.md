# 系統安全審查報告

**審查日期**: 2026-02-07
**審查範圍**: 貼文刪除功能及整體系統安全
**審查員**: Claude Sonnet 4.5

## 執行摘要

本次審查發現了多個安全問題，包括：
- ✅ 已正確實現的安全措施
- ⚠️ 需要改進的中等風險問題
- ❌ 需要立即修復的高風險問題

## 一、認證與授權

### 1.1 JWT Token 安全 ✅ **已實現**
- 使用 JWT 進行用戶認證
- Token 有效期設置為 7 天
- 使用 HS256 算法簽名

**建議改進**:
```python
# ⚠️ SECRET_KEY 使用環境變數，但 fallback 值過於簡單
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev_secret_key_change_in_production_7382")

# 建議: 在生產環境強制要求設置 SECRET_KEY
if not os.getenv("JWT_SECRET_KEY"):
    raise ValueError("JWT_SECRET_KEY must be set in production")
```

### 1.2 用戶授權檢查 ✅ **已正確實現**
**檔案**: `api/routers/forum/posts.py:244-267`

```python
async def delete_post_by_id(
    post_id: int,
    user_id: str = Query(..., description="用戶 ID"),
    current_user: dict = Depends(get_current_user)
):
    if current_user["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
```

**優點**:
- 使用 `Depends(get_current_user)` 確保用戶已認證
- 檢查 `current_user["user_id"]` 與 `user_id` 參數是否匹配
- 後端在 `delete_post` 函數中再次驗證 user_id

### 1.3 IDOR 防護 ✅ **已實現**
**檔案**: `core/database/forum.py:400-409`

```python
def delete_post(post_id: int, user_id: str) -> bool:
    """刪除文章（軟刪除，設為隱藏）"""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE posts SET is_hidden = 1 WHERE id = %s AND user_id = %s',
                  (post_id, user_id))
        conn.commit()
        return c.rowcount > 0
```

**優點**:
- 使用 `WHERE id = %s AND user_id = %s` 確保只有作者可以刪除
- 參數化查詢防止 SQL 注入

## 二、SQL 注入防護

### 2.1 參數化查詢 ✅ **全面實現**
**檔案**: `core/database/forum.py`

所有數據庫查詢都使用參數化查詢，例如：
```python
# ✅ 正確示例
c.execute('SELECT * FROM posts WHERE id = %s', (post_id,))
c.execute('UPDATE posts SET is_hidden = 1 WHERE id = %s AND user_id = %s',
          (post_id, user_id))
```

**未發現任何 SQL 注入漏洞**。

## 三、XSS (跨站腳本攻擊) 防護

### 3.1 前端內容渲染 ⚠️ **需要改進**
**檔案**: `web/js/forum.js:609-610`

```javascript
// ⚠️ 使用 markdown-it 渲染用戶輸入
const md = window.markdownit ? window.markdownit() : { render: t => t };
document.getElementById('post-content').innerHTML = md.render(post.content);
```

**問題**:
- `markdown-it` 默認允許 HTML 標籤
- 可能允許惡意腳本注入

**修復方案**:
```javascript
// ✅ 使用 DOMPurify 清理 HTML
const md = window.markdownit ? window.markdownit() : { render: t => t };
const rawHTML = md.render(post.content);
const clean = DOMPurify.sanitize(rawHTML);
document.getElementById('post-content').innerHTML = clean;
```

### 3.2 用戶名顯示 ⚠️ **需要改進**
**檔案**: `web/js/forum.js:605`

```javascript
// ⚠️ 直接插入用戶名到 innerHTML
document.getElementById('post-author').innerHTML =
  `<a href="/static/forum/profile.html?id=${post.user_id}">${post.username || post.user_id}</a>`;
```

**修復方案**:
```javascript
// ✅ 使用 textContent 或 HTML 轉義
const escapeHTML = (str) => {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
};

const authorLink = document.createElement('a');
authorLink.href = `/static/forum/profile.html?id=${encodeURIComponent(post.user_id)}`;
authorLink.textContent = post.username || post.user_id;
authorLink.className = 'hover:text-primary transition';
document.getElementById('post-author').innerHTML = '';
document.getElementById('post-author').appendChild(authorLink);
```

## 四、CSRF (跨站請求偽造) 防護

### 4.1 當前狀態 ⚠️ **缺少 CSRF 保護**

**問題**:
- API 使用 Bearer Token 認證，但沒有 CSRF Token
- 如果 Token 存儲在 localStorage，容易受到 XSS 攻擊

**修復建議**:
1. 使用 HttpOnly Cookie 存儲 JWT Token
2. 添加 CSRF Token 保護
3. 或使用 SameSite Cookie 屬性

**方案一：添加 CSRF Token**
```python
# api/deps.py
from fastapi import Header, HTTPException

async def verify_csrf_token(x_csrf_token: str = Header(None)):
    if not x_csrf_token:
        raise HTTPException(status_code=403, detail="CSRF token missing")
    # 驗證 CSRF token
    ...
```

**方案二：使用 SameSite Cookie**
```python
# 在設置 Cookie 時添加 SameSite 屬性
response.set_cookie(
    key="access_token",
    value=token,
    httponly=True,
    secure=True,
    samesite="Lax"
)
```

## 五、輸入驗證

### 5.1 後端驗證 ✅ **已實現**
**檔案**: `core/database/forum.py:105-163`

```python
# ✅ 標題長度驗證
MAX_TITLE_LENGTH = 200
if len(title) > MAX_TITLE_LENGTH:
    return {"success": False, "error": "title_too_long"}

# ✅ 內容長度驗證
MAX_CONTENT_LENGTH = 10000
if len(content) > MAX_CONTENT_LENGTH:
    return {"success": False, "error": "content_too_long"}

# ✅ 標籤數量驗證
MAX_TAGS_PER_POST = 5
if tags and len(tags) > MAX_TAGS_PER_POST:
    return {"success": False, "error": "too_many_tags"}
```

**優點**: 完整的服務端驗證

### 5.2 前端驗證 ✅ **已實現**
**檔案**: `web/js/forum.js:976-1044`

- 字數統計和限制提示
- 與後端限制一致

## 六、業務邏輯安全

### 6.1 軟刪除機制 ✅ **已正確實現**
**檔案**: `core/database/forum.py:400-409`

```python
# ✅ 使用 is_hidden 標記而非物理刪除
c.execute('UPDATE posts SET is_hidden = 1 WHERE id = %s AND user_id = %s',
          (post_id, user_id))
```

**優點**:
- 數據可恢復
- 保持外鍵完整性

### 6.2 查詢時過濾隱藏內容 ✅ **已實現**
**檔案**: `core/database/forum.py:220-290`

```python
# ✅ 默認不包含隱藏文章
def get_posts(..., include_hidden: bool = False):
    if not include_hidden:
        query += ' AND p.is_hidden = 0'
```

### 6.3 訪問刪除文章時的處理 ✅ **已實現**
**檔案**: `api/routers/forum/posts.py:190-191`

```python
if post["is_hidden"]:
    raise HTTPException(status_code=404, detail="文章已被刪除")
```

## 七、敏感信息洩露

### 7.1 錯誤訊息 ⚠️ **需要改進**
**檔案**: `api/routers/forum/posts.py:72`

```python
# ⚠️ 直接返回錯誤詳情
except Exception as e:
    raise HTTPException(status_code=500, detail=f"獲取文章列表失敗: {str(e)}")
```

**問題**: 可能洩露系統內部信息（如資料庫結構）

**修復方案**:
```python
except Exception as e:
    logger.error(f"獲取文章列表失敗: {str(e)}")  # 記錄詳細錯誤
    raise HTTPException(status_code=500, detail="獲取文章列表失敗")  # 返回通用訊息
```

## 八、Rate Limiting (速率限制)

### 8.1 當前狀態 ❌ **未實現**

**風險**:
- 暴力破解攻擊
- API 濫用
- DoS 攻擊

**修復建議**:
```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@router.delete("/{post_id}", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def delete_post_by_id(...):
    ...
```

## 九、密碼安全

### 9.1 TEST_MODE 安全 ⚠️ **需要改進**
**檔案**: `api/deps.py:96-120`

```python
# ⚠️ TEST_MODE 繞過所有認證
if TEST_MODE:
    return {
        "user_id": test_user_id,
        "username": f"TestUser_{test_user_id[-3:]}",
        ...
    }
```

**風險**: 如果 TEST_MODE 在生產環境被意外啟用，將完全繞過認證

**修復建議**:
```python
# 確保 TEST_MODE 只在開發環境啟用
if TEST_MODE:
    if os.getenv("ENVIRONMENT") == "production":
        raise ValueError("TEST_MODE must not be enabled in production")
    ...
```

## 十、審計日誌

### 10.1 當前狀態 ⚠️ **部分實現**
**檔案**: `core/database/connection.py:719-756`

- ✅ 已創建 `audit_logs` 表
- ❌ 未在刪除操作中記錄審計日誌

**修復建議**: 在刪除操作中添加審計日誌
```python
def delete_post(post_id: int, user_id: str) -> bool:
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('UPDATE posts SET is_hidden = 1 WHERE id = %s AND user_id = %s',
                  (post_id, user_id))

        # 添加審計日誌
        if c.rowcount > 0:
            c.execute('''
                INSERT INTO audit_logs (user_id, action, resource_type, resource_id, success)
                VALUES (%s, 'DELETE_POST', 'post', %s, TRUE)
            ''', (user_id, str(post_id)))

        conn.commit()
        return c.rowcount > 0
```

## 十一、修復優先級

### 🔴 高優先級（立即修復）
1. ✅ **添加刪除功能的前端UI** - 已完成
2. ⚠️ **XSS 防護**: 添加 DOMPurify 清理 HTML
3. ⚠️ **禁止 TEST_MODE 在生產環境啟用**
4. ⚠️ **添加 Rate Limiting**

### 🟡 中優先級（2週內修復）
5. ⚠️ **添加 CSRF 保護**
6. ⚠️ **改進錯誤訊息處理**
7. ⚠️ **添加刪除操作的審計日誌**

### 🟢 低優先級（持續改進）
8. ⚠️ **考慮使用更強的 JWT 算法（RS256）**
9. ⚠️ **實現完整的內容安全政策（CSP）**

## 十二、結論

整體而言，系統的安全基礎良好：
- ✅ 認證和授權機制完善
- ✅ SQL 注入防護完整
- ✅ 業務邏輯安全
- ⚠️ 需要改進 XSS 防護和 CSRF 保護
- ⚠️ 需要添加 Rate Limiting

建議按照優先級順序進行修復。
