# Zeabur 部署 Python 3.12.7 配置指南

## 問題

Zeabur 自動檢測並使用 Python 3.13，但專案需要使用 Python 3.12.7。

## 解決方案

已創建以下配置文件來強制 Zeabur 使用 Python 3.12.7：

### 1. `runtime.txt` ⭐ (最重要)

```
python-3.12.7
```

這是 Zeabur 和多數 PaaS 平台識別 Python 版本的標準方式。

### 2. `.python-version`

```
3.12.7
```

pyenv 和其他工具使用的版本文件。

### 3. `Dockerfile` (可選，但推薦)

如果 Zeabur 支援自定義 Docker 構建，這會覆蓋所有自動檢測：

```dockerfile
FROM python:3.12.7-slim
...
```

### 4. `zbpack.json` (Zeabur 專用)

```json
{
  "environment": {
    "PYTHON_VERSION": "3.12.7"
  }
}
```

## 部署步驟

### 方法 1: 使用 runtime.txt (推薦)

1. **提交新文件到 Git:**
   ```bash
   git add runtime.txt .python-version
   git commit -m "Fix: Specify Python 3.12.7 for deployment"
   git push
   ```

2. **重新部署 Zeabur:**
   - Zeabur 會自動檢測到 `runtime.txt`
   - 使用 Python 3.12.7 構建

### 方法 2: 使用 Dockerfile

如果 runtime.txt 不生效，使用 Dockerfile：

1. **提交 Dockerfile:**
   ```bash
   git add Dockerfile
   git commit -m "Add Dockerfile with Python 3.12.7"
   git push
   ```

2. **Zeabur 設置:**
   - 進入 Zeabur 控制台
   - 選擇您的服務
   - 設置 > Build Configuration
   - 選擇 "Dockerfile" 構建方式

### 方法 3: Zeabur 環境變數

如果以上方法都不行，在 Zeabur 控制台手動設置：

1. 進入服務設置
2. Environment Variables
3. 添加: `PYTHON_VERSION=3.12.7`

## 驗證

部署後檢查日誌應該看到：

```
Building with Python 3.12.7...
```

而不是：

```
Building with Python 3.13.x...
```

## 為什麼需要 Python 3.12.7？

- **依賴兼容性**: 某些套件可能尚未完全支援 Python 3.13
- **測試穩定性**: 開發環境使用 3.12.7，生產環境應保持一致
- **LTS 版本**: Python 3.12 是長期支援版本，更穩定

## 相關文件

- `requirements.txt` - 已更新 numpy==2.2.6 以兼容 Python 3.12.7
- `api_server.py` - 主應用入口

## Zeabur 文檔參考

- [Zeabur Python 部署](https://zeabur.com/docs/deploy/python)
- [Zeabur 環境變數](https://zeabur.com/docs/deploy/variables)
- [Zeabur Dockerfile 支援](https://zeabur.com/docs/deploy/dockerfile)

---

**狀態**: ✅ 配置完成  
**Python 版本**: 3.12.7  
**下次部署**: Zeabur 將使用正確版本
