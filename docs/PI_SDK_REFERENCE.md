# Pi Network SDK 開發參考手冊

> 最後更新：2026-01-21
> 官方文檔：https://github.com/pi-apps/pi-platform-docs
> 開發者指南：https://pi-apps.github.io/community-developer-guide/

---

## 目錄

1. [SDK 載入與初始化](#1-sdk-載入與初始化)
2. [環境檢測](#2-環境檢測)
3. [用戶認證](#3-用戶認證-authenticate)
4. [支付功能](#4-支付功能-createpayment)
5. [其他 API](#5-其他-api)
6. [最佳實踐](#6-最佳實踐)
7. [錯誤處理](#7-錯誤處理)
8. [本專案使用範例](#8-本專案使用範例)

---

## 1. SDK 載入與初始化

### 載入 SDK

```html
<script src="https://sdk.minepi.com/pi-sdk.js"></script>
```

SDK 載入後會在 `window` 上建立全域 `Pi` 物件。

### 初始化

```javascript
Pi.init({
    version: "2.0",      // 必填：SDK 版本
    sandbox: false       // 可選：true = 沙盒環境, false = 正式環境
});
```

**參數說明：**

| 參數 | 類型 | 必填 | 說明 |
|------|------|------|------|
| `version` | string | 是 | SDK 版本號，目前使用 "2.0" |
| `sandbox` | boolean | 否 | 是否使用沙盒環境（測試用）|

**沙盒環境：**
- 沙盒網址：`https://sandbox.minepi.com`
- 使用測試 Pi 幣，不涉及真實資產
- 建議開發時設為 `true`，上線時設為 `false`

---

## 2. 環境檢測

### 2.1 同步檢測（基本）

檢查 Pi SDK 是否存在且有必要方法：

```javascript
function isPiBrowser() {
    const hasPiSDK = typeof window.Pi !== 'undefined' &&
                     window.Pi !== null &&
                     typeof window.Pi.authenticate === 'function' &&
                     typeof window.Pi.init === 'function';
    return hasPiSDK;
}
```

### 2.2 異步檢測（推薦）- `Pi.nativeFeaturesList()`

**用途：** 快速驗證 Pi Browser 環境是否有效，比 `authenticate` 更快（不需用戶授權）。

```javascript
Pi.nativeFeaturesList(): Promise<string[]>
```

**返回值：** 當前 Pi Browser 版本支援的原生功能陣列

**可能的功能：**
- `"inline_media"` - 內嵌媒體支援
- `"request_permission"` - 權限請求
- `"ad_network"` - 廣告網路

**使用範例：**

```javascript
async function verifyPiBrowserEnvironment() {
    if (!isPiBrowser()) {
        return { valid: false, reason: 'Pi SDK 不存在' };
    }

    try {
        Pi.init({ version: "2.0", sandbox: false });

        // 使用 nativeFeaturesList 做快速環境檢測（1.5 秒超時）
        const QUICK_TIMEOUT = 1500;

        const featuresPromise = Pi.nativeFeaturesList();
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('TIMEOUT')), QUICK_TIMEOUT);
        });

        const features = await Promise.race([featuresPromise, timeoutPromise]);
        console.log('支援的功能:', features);
        return { valid: true, features };

    } catch (error) {
        return { valid: false, reason: error.message };
    }
}
```

**重要：** 此方法在非有效 Pi Browser 環境中會超時或失敗，可用於快速判斷環境。

---

## 3. 用戶認證 (authenticate)

### 方法簽名

```typescript
Pi.authenticate(
    scopes: Array<Scope>,
    onIncompletePaymentFound: (payment: PaymentDTO) => void
): Promise<AuthResult>
```

### 參數說明

| 參數 | 類型 | 說明 |
|------|------|------|
| `scopes` | string[] | 請求的權限範圍 |
| `onIncompletePaymentFound` | function | 發現未完成支付時的回調函數 |

### 可用的權限範圍 (Scopes)

| Scope | 說明 |
|-------|------|
| `'username'` | 獲取用戶名 |
| `'payments'` | 進行支付操作（必須有此權限才能創建支付）|
| `'wallet_address'` | 獲取用戶錢包地址 |

### 返回值 (AuthResult)

```typescript
{
    accessToken: string;      // 用於後端驗證的 Token
    user: {
        uid: string;          // 用戶唯一 ID
        username?: string;    // 用戶名（需要 'username' scope）
    }
}
```

### 使用範例

```javascript
async function authenticateWithPi() {
    try {
        Pi.init({ version: "2.0", sandbox: false });

        const auth = await Pi.authenticate(
            ['username', 'payments'],  // 權限範圍
            (incompletePayment) => {
                // 處理未完成的支付
                console.log('發現未完成支付:', incompletePayment);
                // 應該呼叫後端 API 完成或取消此支付
            }
        );

        console.log('認證成功:', {
            uid: auth.user.uid,
            username: auth.user.username,
            accessToken: auth.accessToken
        });

        // 將 accessToken 發送到後端驗證
        await syncToBackend(auth);

        return auth;

    } catch (error) {
        console.error('認證失敗:', error);
        throw error;
    }
}
```

### 超時處理

Pi.authenticate 可能因環境問題而無響應，建議加入超時機制：

```javascript
const AUTH_TIMEOUT = 3000; // 3 秒

const authPromise = Pi.authenticate(['username', 'payments'], onIncomplete);
const timeoutPromise = new Promise((_, reject) => {
    setTimeout(() => reject(new Error('認證超時')), AUTH_TIMEOUT);
});

const auth = await Promise.race([authPromise, timeoutPromise]);
```

---

## 4. 支付功能 (createPayment)

### 方法簽名

```typescript
Pi.createPayment(
    paymentData: PaymentData,
    callbacks: PaymentCallbacks
): void
```

### PaymentData 參數

```typescript
{
    amount: number;      // 支付金額（Pi 幣）
    memo: string;        // 支付備註（會顯示給用戶）
    metadata: object;    // 自定義數據（會傳遞給後端）
}
```

### PaymentCallbacks 回調函數

```typescript
{
    onReadyForServerApproval: (paymentId: string) => void;
    onReadyForServerCompletion: (paymentId: string, txid: string) => void;
    onCancel: (paymentId: string) => void;
    onError: (error: Error, payment?: PaymentDTO) => void;
}
```

### 支付流程

```
1. 前端呼叫 Pi.createPayment()
2. 用戶在 Pi Browser 中確認支付
3. 觸發 onReadyForServerApproval(paymentId)
4. 前端呼叫後端 API → 後端呼叫 Pi Platform API /payments/{paymentId}/approve
5. Pi Network 處理區塊鏈交易
6. 觸發 onReadyForServerCompletion(paymentId, txid)
7. 前端呼叫後端 API → 後端呼叫 Pi Platform API /payments/{paymentId}/complete
8. 支付完成
```

### 使用範例

```javascript
async function createPiPayment(amount, memo, metadata) {
    return new Promise((resolve, reject) => {
        Pi.createPayment(
            {
                amount: amount,           // 例如: 1
                memo: memo,               // 例如: "發文費用"
                metadata: metadata        // 例如: { postId: "123", type: "create_post" }
            },
            {
                // 步驟 1: 支付已創建，等待後端批准
                onReadyForServerApproval: async (paymentId) => {
                    console.log('支付待批准:', paymentId);
                    try {
                        // 呼叫後端 API 批准支付
                        await fetch('/api/payment/approve', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ paymentId })
                        });
                    } catch (error) {
                        console.error('批准失敗:', error);
                    }
                },

                // 步驟 2: 區塊鏈交易完成，等待後端確認完成
                onReadyForServerCompletion: async (paymentId, txid) => {
                    console.log('支付待完成:', paymentId, txid);
                    try {
                        // 呼叫後端 API 完成支付
                        const res = await fetch('/api/payment/complete', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ paymentId, txid })
                        });
                        const result = await res.json();
                        resolve(result);
                    } catch (error) {
                        reject(error);
                    }
                },

                // 用戶取消支付
                onCancel: (paymentId) => {
                    console.log('支付已取消:', paymentId);
                    reject(new Error('用戶取消支付'));
                },

                // 發生錯誤
                onError: (error, payment) => {
                    console.error('支付錯誤:', error, payment);
                    reject(error);
                }
            }
        );
    });
}
```

---

## 5. 其他 API

### 5.1 分享對話框

```javascript
Pi.openShareDialog(
    title: string,      // 分享標題
    message: string     // 分享內容
): void
```

### 5.2 在系統瀏覽器開啟 URL

```javascript
Pi.openUrlInSystemBrowser(url: string): void
```

### 5.3 廣告功能

```javascript
// 檢查廣告是否準備好
Pi.Ads.isAdReady(): Promise<boolean>

// 請求新廣告
Pi.Ads.requestAd(): Promise<void>

// 顯示廣告
Pi.Ads.showAd(): Promise<void>
```

---

## 6. 最佳實踐

### 6.1 環境檢測流程

```javascript
async function handlePiLogin() {
    // 第一步：同步檢測 Pi SDK 是否存在
    if (!isPiBrowser()) {
        alert('請在 Pi Browser 中開啟');
        return;
    }

    // 第二步：快速驗證環境（1.5 秒）
    const envCheck = await verifyPiBrowserEnvironment();
    if (!envCheck.valid) {
        alert('Pi Browser 環境異常，請確認已登入 Pi 帳號');
        return;
    }

    // 第三步：進行認證
    const auth = await Pi.authenticate(['username', 'payments'], handleIncomplete);

    // 第四步：同步到後端
    await syncToBackend(auth);
}
```

### 6.2 防重複點擊

```javascript
let isLoginInProgress = false;

async function safePiLogin() {
    if (isLoginInProgress) return;

    try {
        isLoginInProgress = true;
        // 更新 UI 為 loading 狀態
        await handlePiLogin();
    } finally {
        isLoginInProgress = false;
        // 恢復 UI
    }
}
```

### 6.3 後端驗證 Access Token

**重要：** 前端獲取的用戶信息僅用於顯示，後端必須通過 Pi Platform API 驗證 Token！

```
GET https://api.minepi.com/v2/me
Headers:
  Authorization: Bearer <accessToken>
```

---

## 7. 錯誤處理

### 常見錯誤

| 錯誤情況 | 原因 | 解決方案 |
|---------|------|---------|
| `window.Pi` 不存在 | 不在 Pi Browser 中 | 提示用戶使用 Pi Browser |
| `authenticate` 超時 | 環境異常或用戶未登入 Pi | 使用 `nativeFeaturesList` 先檢測環境 |
| 支付失敗 | 餘額不足或網路問題 | 顯示錯誤訊息，引導重試 |
| `onIncompletePaymentFound` 觸發 | 之前有未完成的支付 | 呼叫後端完成或取消該支付 |

### 超時建議值

| 操作 | 建議超時 |
|------|---------|
| `nativeFeaturesList` | 1.5 秒 |
| `authenticate` | 3 秒 |
| `createPayment` 回調 | 視情況，通常不設超時 |

---

## 8. 本專案使用範例

### 檔案位置

- 認證相關：`web/js/auth.js`
- 支付相關：`web/js/forum.js`
- SDK 載入：`web/index.html`

### auth.js 中的關鍵函數

```javascript
// SDK 初始化
AuthManager.initPiSDK()

// 同步環境檢測
AuthManager.isPiBrowser()

// 異步環境驗證（使用 nativeFeaturesList）
AuthManager.verifyPiBrowserEnvironment()

// 用戶認證
AuthManager.authenticateWithPi()

// 綁定錢包
linkPiWallet()
```

### 登入流程時序

```
用戶點擊「Connect Pi Wallet」
         ↓
    safePiLogin()
         ↓
    isPiBrowser() ─── false ──→ 提示使用 Pi Browser
         ↓ true
verifyPiBrowserEnvironment() ─── false ──→ 提示環境異常
         ↓ true (1.5秒內)
authenticateWithPi() ─── 失敗 ──→ 顯示錯誤
         ↓ 成功 (3秒內)
    同步到後端
         ↓
    登入成功，重新載入頁面
```

---

## 附錄：官方資源

- **Pi Platform Docs**: https://github.com/pi-apps/pi-platform-docs
- **Community Developer Guide**: https://pi-apps.github.io/community-developer-guide/
- **SDK 檔案**: https://sdk.minepi.com/pi-sdk.js
- **沙盒環境**: https://sandbox.minepi.com

---

*此文檔由 Claude 協助整理，如有更新請同步修改此檔案。*
