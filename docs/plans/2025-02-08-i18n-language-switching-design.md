# 國際化（i18n）語系切換功能設計文件

**日期：** 2025-02-08
**設計者：** Claude Code
**專案：** Pi Crypto Insight

---

## 1. 概述

### 1.1 需求背景

目前 Pi Crypto Insight 平台的介面文字是中英夾雜，沒有專業的語系區分機制。本設計旨在實作完整的國際化（i18n）系統，讓使用者可以自由切換語言。

### 1.2 功能目標

- 支援繁體中文（zh-TW）與英文（en）兩種語言
- 提供語系切換器，讓使用者自行選擇
- 使用者偏好儲存在 LocalStorage
- 頁面載入時自動偵測瀏覽器語言作為預設值
- 切換語言時，整個網頁介面即時更新

---

## 2. 整體架構

### 2.1 技術選型

| 項目 | 選擇 | 說明 |
|-----|------|------|
| i18n 框架 | i18next | 業界標準，vanilla JS 支援良好 |
| 儲存方式 | LocalStorage | 無需後端支援，簡單快速 |
| 預設語言 | 瀏覽器偵測 | zh-TW/zh-HK → 繁中，其他 → 英文 |

### 2.2 檔案結構

```
web/
├── js/
│   ├── i18n/
│   │   ├── index.js          # i18next 初始化設定
│   │   ├── zh-TW.json        # 繁體中文翻譯檔
│   │   └── en.json           # 英文翻譯檔
│   ├── components/
│   │   └── LanguageSwitcher.js  # 語系切換器組件
│   └── app.js                # 主程式入口
└── *.html                     # 各頁面檔案
```

### 2.3 初始化流程

```
1. 頁面載入
   ↓
2. 檢查 LocalStorage 是否有 selectedLanguage
   ↓ (無)
3. 檢查 navigator.language
   ↓
4. 決定預設語言（zh-TW 或 en）
   ↓
5. 初始化 i18next
   ↓
6. 等待 DOM 載入完成
   ↓
7. 更新所有帶 data-i18n 屬性的元素
```

---

## 3. 語系切換器 UI 設計

### 3.1 位置與外觀

- **位置：** 右上角導航列，在使用者頭像/登入按鈕的左側
- **樣式：** 下拉選單（Dropdown）
- **顯示內容：** 國旗圖示 + 語言名稱

```
┌─────────────────────────────────────────────────────┐
│  Logo    市場分析  社群論壇  治理    [🇺🇸 English ▼] [👤] │
└─────────────────────────────────────────────────────┘
                                                   ↑
                                            語系切換器位置
```

### 3.2 互動行為

| 狀態 | 行為 |
|-----|------|
| hover | 下拉選單淡入顯示 |
| 點擊選項 | 切換語言，儲存偏好，關閉選單 |
| 點擊外部 | 關閉選單 |

### 3.3 樣式規格（Tailwind CSS）

```css
.lang-switcher {
  position: relative;
  margin-right: 1rem;
}

.lang-trigger {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border-radius: 0.5rem;
  cursor: pointer;
  transition: background 0.2s;
}

.lang-trigger:hover {
  background: rgba(255, 255, 255, 0.1);
}

.lang-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 0.5rem;
  background: #1a1a2e;
  border: 1px solid #4a4a6a;
  border-radius: 0.5rem;
  overflow: hidden;
  min-width: 150px;
}

.lang-option {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  cursor: pointer;
}

.lang-option:hover {
  background: rgba(255, 255, 255, 0.05);
}
```

---

## 4. 翻譯檔結構

### 4.1 組織原則

- 使用巢狀命名空間結構
- 按功能模組分組（nav, forum, market, governance 等）
- 通用文字放在 common 命名空間

### 4.2 翻譯檔範例

**web/js/i18n/zh-TW.json**
```json
{
  "common": {
    "loading": "載入中...",
    "error": "發生錯誤",
    "save": "儲存",
    "cancel": "取消",
    "confirm": "確認",
    "delete": "刪除"
  },
  "nav": {
    "market": "市場分析",
    "forum": "社群論壇",
    "governance": "治理中心",
    "login": "登入",
    "logout": "登出",
    "profile": "個人資料"
  },
  "market": {
    "title": "加密貨幣市場分析",
    "filter": "篩選",
    "autoBadge": "自動",
    "refresh": "重新整理"
  },
  "forum": {
    "newPost": "發文",
    "categories": {
      "analysis": "分析",
      "question": "提問",
      "tutorial": "教學",
      "news": "新聞",
      "chat": "閒聊",
      "insight": "洞察"
    },
    "scamTracker": "詐騙追蹤",
    "submitReport": "提交檢舉"
  },
  "governance": {
    "title": "社群治理",
    "proposals": "提案",
    "vote": "投票",
    "passed": "已通過",
    "rejected": "已否決"
  }
}
```

**web/js/i18n/en.json**
```json
{
  "common": {
    "loading": "Loading...",
    "error": "Error occurred",
    "save": "Save",
    "cancel": "Cancel",
    "confirm": "Confirm",
    "delete": "Delete"
  },
  "nav": {
    "market": "Market Analysis",
    "forum": "Community Forum",
    "governance": "Governance",
    "login": "Login",
    "logout": "Logout",
    "profile": "Profile"
  },
  "market": {
    "title": "Crypto Market Analysis",
    "filter": "Filter",
    "autoBadge": "Auto",
    "refresh": "Refresh"
  },
  "forum": {
    "newPost": "New Post",
    "categories": {
      "analysis": "Analysis",
      "question": "Question",
      "tutorial": "Tutorial",
      "news": "News",
      "chat": "Chat",
      "insight": "Insight"
    },
    "scamTracker": "Scam Tracker",
    "submitReport": "Submit Report"
  },
  "governance": {
    "title": "Governance",
    "proposals": "Proposals",
    "vote": "Vote",
    "passed": "Passed",
    "rejected": "Rejected"
  }
}
```

---

## 5. HTML 標記方式

### 5.1 靜態文字

```html
<!-- 方式一：data-i18n 屬性（推薦） -->
<button data-i18n="nav.market"></button>

<!-- 方式二：JavaScript 動態插入 -->
<span id="forum-title"></span>
<script>
  document.getElementById('forum-title').textContent = i18next.t('forum.title');
</script>
```

### 5.2 帶變數的文字

```html
<!-- 翻譯檔：{ "greeting": "歡迎, {{name}}!" } -->
<span data-i18n="greeting" data-i18n-args='{"name": "使用者"}'></span>
```

### 5.3 表單 placeholder

```html
<input type="text" data-i18n="placeholder" data-i18n-attr="placeholder">
```

---

## 6. 實作範圍

### 6.1 需要國際化的頁面

| 頁面檔案 | 說明 | 優先級 |
|---------|------|--------|
| `web/market.html` | 市場分析首頁 | P0 |
| `web/forum.html` | 社群論壇首頁 | P0 |
| `web/governance.html` | 治理中心 | P1 |
| `web/safety.html` | 詐騙檢舉/安全頁面 | P1 |
| `web/login.html` | 登入頁面 | P0 |
| 導航列組件 | 各頁面共用的導航 | P0 |

### 6.2 實作步驟

**Phase 1：基礎架構**
1. 安裝 i18next 套件
2. 建立翻譯檔案結構
3. 實作 i18n 初始化模組
4. 建立 LanguageSwitcher 組件

**Phase 2：核心頁面國際化**
1. 更新導航列：加入語系切換器
2. `market.html`：標記所有靜態文字
3. `forum.html`：標記所有靜態文字
4. `login.html`：標記表單與錯誤訊息

**Phase 3：次要頁面與優化**
1. `governance.html`、`safety.html` 國際化
2. 處理動態內容（API 回應的錯誤訊息等）
3. 測試各頁面的語言切換功能
4. 瀏覽器語言偵測測試

**Phase 4：後端 API 訊息（可選）**
1. 評估後端錯誤訊息是否需要多語言
2. 若需要，修改 API 回應格式，依據 Accept-Language 回傳對應語言

### 6.3 依賴套件

```html
<!-- CDN 方式 -->
<script src="https://cdn.jsdelivr.net/npm/i18next@23.7.6/i18next.min.js"></script>
```

或使用 npm：
```bash
npm install i18next
```

---

## 7. 特殊情境處理

### 7.1 動態載入的內容

```javascript
// API 回傳後需要翻譯
async function loadPosts() {
  const posts = await fetch('/api/posts').then(r => r.json());

  posts.forEach(post => {
    post.categoryText = i18next.t(`forum.categories.${post.category}`);
  });

  renderPosts(posts);
}
```

### 7.2 錯誤訊息

```javascript
// 前端產生的錯誤訊息需要多語言
function showError(messageKey) {
  alert(i18next.t(`common.error.${messageKey}`));
}
```

### 7.3 日期與數字格式

```javascript
// 根據語言調整格式顯示
function formatDate(date) {
  const locale = i18next.language === 'zh-TW' ? 'zh-TW' : 'en-US';
  return new Date(date).toLocaleDateString(locale);
}
```

---

## 8. 核心程式碼實作

### 8.1 i18next 初始化

**web/js/i18n/index.js**
```javascript
import i18next from 'i18next';
import zhTW from './zh-TW.json';
import en from './en.json';

const initI18n = async () => {
  await i18next.init({
    lng: getSavedLanguage() || detectBrowserLanguage(),
    fallbackLng: 'en',
    resources: {
      'zh-TW': { translation: zhTW },
      'en': { translation: en }
    },
    interpolation: {
      escapeValue: false
    }
  });

  updatePageContent();

  i18next.on('languageChanged', () => {
    updatePageContent();
  });
};

function getSavedLanguage() {
  return localStorage.getItem('selectedLanguage');
}

function detectBrowserLanguage() {
  const lang = navigator.language || navigator.userLanguage;
  return (lang === 'zh-TW' || lang === 'zh-HK') ? 'zh-TW' : 'en';
}

function updatePageContent() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    const args = el.getAttribute('data-i18n-args');
    const translation = args
      ? i18next.t(key, JSON.parse(args))
      : i18next.t(key);

    if (el.tagName === 'INPUT' && el.getAttribute('placeholder')) {
      el.placeholder = translation;
    } else {
      el.textContent = translation;
    }
  });

  document.documentElement.lang = i18next.language;
}

export { initI18n, i18next };
```

### 8.2 LanguageSwitcher 組件

**web/js/components/LanguageSwitcher.js**
```javascript
import { i18next } from '../i18n/index.js';

class LanguageSwitcher {
  constructor() {
    this.currentLang = this.getSavedLanguage() || this.detectBrowserLanguage();
    this.init();
  }

  getSavedLanguage() {
    return localStorage.getItem('selectedLanguage');
  }

  detectBrowserLanguage() {
    const lang = navigator.language || navigator.userLanguage;
    return (lang === 'zh-TW' || lang === 'zh-HK') ? 'zh-TW' : 'en';
  }

  init() {
    this.render();
    this.attachEvents();
  }

  render() {
    const flags = { 'zh-TW': '🇹🇼', 'en': '🇺🇸' };
    const names = { 'zh-TW': '繁體中文', 'en': 'English' };

    const container = document.querySelector('.lang-switcher-container');
    if (container) {
      container.innerHTML = `
        <div class="lang-switcher">
          <div class="lang-trigger">
            <span>${flags[this.currentLang]}</span>
            <span>${names[this.currentLang]}</span>
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M6 9l6 6 6-6"/>
            </svg>
          </div>
          <div class="lang-dropdown hidden">
            <div class="lang-option" data-lang="zh-TW">
              <span>🇹🇼</span><span>繁體中文</span>
            </div>
            <div class="lang-option" data-lang="en">
              <span>🇺🇸</span><span>English</span>
            </div>
          </div>
        </div>
      `;
    }
  }

  attachEvents() {
    const switcher = document.querySelector('.lang-switcher');
    if (!switcher) return;

    const trigger = switcher.querySelector('.lang-trigger');
    const dropdown = switcher.querySelector('.lang-dropdown');

    // 切換下拉顯示
    trigger?.addEventListener('click', (e) => {
      e.stopPropagation();
      dropdown.classList.toggle('hidden');
    });

    // 點擊選項時切換語言
    switcher.querySelectorAll('.lang-option').forEach(option => {
      option.addEventListener('click', (e) => {
        const lang = e.currentTarget.dataset.lang;
        this.changeLanguage(lang);
        dropdown.classList.add('hidden');
      });
    });

    // 點擊外部關閉
    document.addEventListener('click', () => {
      dropdown.classList.add('hidden');
    });
  }

  changeLanguage(lang) {
    this.currentLang = lang;
    localStorage.setItem('selectedLanguage', lang);
    i18next.changeLanguage(lang);
    this.render();
  }
}

export default LanguageSwitcher;
```

---

## 9. 測試計畫

| 測試項目 | 測試步驟 | 預期結果 |
|---------|---------|---------|
| 語言偵測 | 清除 LocalStorage，用不同語言的瀏覽器開啟 | 自動選擇對應語言 |
| 切換功能 | 點擊切換器選擇不同語言 | 介面立即更新 |
| 偏好儲存 | 切換語言後重新整理網頁 | 維持先前選擇的語言 |
| 各頁面文字 | 檢查各頁面所有文字 | 正確顯示對應語言 |
| 動態內容 | 發文後檢查分類顯示 | 顯示翻譯後的分類名稱 |

---

## 10. 未來擴展

### 10.1 支援更多語言

未來可擴展支援：
- 簡體中文（zh-CN）
- 日文（ja）
- 韓文（ko）

### 10.2 後端 API 多語言

修改 API 接受 `Accept-Language` header，回傳對應語言的錯誤訊息與驗證訊息。

### 10.3 使用者帳號綁定

將語言偏好儲存在使用者資料庫，實現跨裝置同步。

---

## 11. 結論

本設計提供了完整的國際化解決方案，從基礎架構到 UI 實作都有詳細規劃。採用 i18next 框架可確保未來擴展性，LocalStorage 儲存方式簡單可靠，整體實作風險低。
