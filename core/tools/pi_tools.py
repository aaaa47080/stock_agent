# -*- coding: utf-8 -*-
"""
Pi Network 工具模組

提供 Pi Network 相關的 LangChain 工具，用於：
- 查詢用戶資訊
- 查詢 Pi 幣價格
- 查詢支付狀態

所有工具均使用免費的 Pi Network API，無需付費。
"""
import os
import httpx
from langchain_core.tools import tool


PI_API_KEY = os.getenv("PI_API_KEY", "")
PI_API_BASE = "https://api.minepi.com/v2"


@tool
def get_pi_price() -> str:
    """
    查詢 Pi Network (PI) 的即時價格。

    ⚠️ 重要：PI (Pi Network) 不在 Binance 等主流交易所上市，
    因此無法使用通用的 get_crypto_price 工具。
    查詢 PI 價格時必須使用此專用工具。

    此工具從 CoinGecko API 獲取 PI 的即時價格資訊。

    適用情境：
    - 用戶詢問「PI 現在多少錢」「Pi Network 價格」
    - 用戶想了解 PI (Pi Network) 的市場表現
    """
    import httpx
    try:
        # CoinGecko PI 價格查詢
        resp = httpx.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=pi-network&vs_currencies=usd,twd&include_24hr_change=true&include_market_cap=true",
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json()
            pi_data = data.get("pi-network", {})

            if pi_data:
                usd_price = pi_data.get("usd", 0)
                twd_price = pi_data.get("twd", 0)
                change_24h = pi_data.get("usd_24h_change", 0)
                market_cap = pi_data.get("usd_market_cap", 0)

                trend = "📈" if change_24h and change_24h > 0 else "📉" if change_24h and change_24h < 0 else "➡️"

                # 格式化市值
                if market_cap > 1_000_000_000:
                    mc_str = f"${market_cap / 1_000_000_000:.2f}B"
                else:
                    mc_str = f"${market_cap / 1_000_000:.2f}M"

                return f"""## 🥧 Pi Network (PI) 即時價格

| 項目 | 數值 |
|------|------|
| **當前價格 (USD)** | **${usd_price:.4f}** |
| 價格 (TWD) | NT${twd_price:.2f} |
| 24h 變化 | {trend} {change_24h:+.2f}% |
| 市值 | {mc_str} |

### 📱 關於 Pi Network
- Pi Network 專為手機用戶設計
- 可透過 Pi Browser 進行挖礦和交易
- 主網已於 2024 年開放

*(資料來源: CoinGecko)*"""

        return "目前無法取得 Pi 幣價格，請稍後再試。"

    except Exception as e:
        return f"取得 Pi 幣價格時發生錯誤: {str(e)}"


@tool
def get_pi_network_info() -> str:
    """
    獲取 Pi Network 的最新資訊和市場概況。

    包含：
    - Pi Network 項目簡介
    - 當前市場表現
    - 相關鏈上數據

    適用情境：
    - 用戶詢問「Pi Network 是什麼」
    - 用戶想了解 Pi 的基本資訊
    """
    try:
        # 獲取價格和市值數據
        resp = httpx.get(
            "https://api.coingecko.com/api/v3/coins/pi-network?localization=false&tickers=false&market_data=true&community_data=false&developer_data=false",
            timeout=10
        )

        if resp.status_code == 200:
            data = resp.json()
            market_data = data.get("market_data", {})

            current_price = market_data.get("current_price", {}).get("usd", 0)
            ath = market_data.get("ath", {}).get("usd", 0)
            atl = market_data.get("atl", {}).get("usd", 0)
            market_cap_rank = market_data.get("market_cap_rank", "N/A")
            total_supply = market_data.get("total_supply", 0)
            circulating_supply = market_data.get("circulating_supply", 0)

            def format_supply(val):
                if val and val > 1_000_000_000:
                    return f"{val / 1_000_000_000:.2f}B"
                elif val:
                    return f"{val / 1_000_000:.2f}M"
                return "N/A"

            return f"""## 🥧 Pi Network 資訊總覽

### 基本資料
- **名稱**: Pi Network (PI)
- **市值排名**: #{market_cap_rank}

### 價格資訊
| 項目 | 數值 |
|------|------|
| 當前價格 | ${current_price:.4f} |
| 歷史最高 (ATH) | ${ath:.4f} |
| 歷史最低 (ATL) | ${atl:.6f} |

### 供應量
| 項目 | 數值 |
|------|------|
| 流通量 | {format_supply(circulating_supply)} PI |
| 總供應量 | {format_supply(total_supply)} PI |

### 🎯 項目特色
- 📱 **手機優先**: 專為移動設備設計的加密貨幣
- 🌍 **全民參與**: 超過 4000 萬活躍用戶
- ⛏️ **輕鬆挖礦**: 每日點擊即可挖礦
- 🔄 **生態系統**: 包含錢包、瀏覽器、DApp 平台

*(資料來源: CoinGecko)*"""

        return "目前無法取得 Pi Network 資訊。"

    except Exception as e:
        return f"取得 Pi Network 資訊時發生錯誤: {str(e)}"


@tool
def get_pi_ecosystem() -> str:
    """
    獲取 Pi Network 生態系統的最新動態。

    包含：
    - Pi 生態應用介紹
    - 主網進展
    - 社群活動

    適用情境：
    - 用戶詢問「Pi 有什麼應用」
    - 用戶想了解 Pi 生態發展
    """
    # Pi 生態系統靜態資訊（因為沒有專門的 API）
    return """## 🥧 Pi Network 生態系統

### 📱 Pi 應用程式
| 應用 | 功能 | 狀態 |
|------|------|------|
| Pi Browser | Pi 專用瀏覽器 | ✅ 運行中 |
| Pi Wallet | 官方錢包 | ✅ 運行中 |
| Pi Mining App | 挖礦應用 | ✅ 運行中 |

### 🔧 核心 DApp 類別
1. **金融服務** - 支付、轉帳、DeFi
2. **社交娛樂** - 遊戲、社交平台
3. **電子商務** - 購物、NFT 市場
4. **工具應用** - 實用工具、資訊服務

### 🛠️ 開發者資源
- Pi Platform: 開發者可以構建 Pi 應用
- Pi SDK: JavaScript SDK 用於整合 Pi 功能
- Pi Apps Labs: 測試和部署環境

### ⚠️ 重要提醒
- 目前 Pi 主網已開放封閉式交易
- 用戶需完成 KYC 才能遷移到主網
- 請警惕 Pi 相關的詐騙項目

### 📊 數據查詢
- 使用 `get_pi_price` 查詢即時價格
- 使用 `get_pi_network_info` 查詢項目資訊

*(資訊更新: 2024 年)*"""


@tool
def get_pi_tools_guide() -> str:
    """
    獲取 Pi Network 相關工具的使用指南。

    當用戶不確定要使用哪個 Pi 工具時，此工具會列出所有可用的 Pi 功能。
    """
    return """## 🥧 Pi Network 工具指南

### 可用工具

| 工具名稱 | 功能說明 | 使用範例 |
|---------|---------|---------|
| `get_pi_price` | 查詢 PI 即時價格 | 「PI 現在多少錢？」 |
| `get_pi_network_info` | 查詢 Pi Network 詳細資訊 | 「Pi Network 是什麼？」 |
| `get_pi_ecosystem` | 查詢 Pi 生態系統 | 「Pi 有什麼應用？」 |
| `get_pi_tools_guide` | 顯示此工具指南 | 「Pi 有什麼功能？」 |

### 💡 快速查詢範例

**查詢價格：**
```
PI 現在多少錢？
```

**了解項目：**
```
跟我介紹一下 Pi Network
```

**生態應用：**
```
Pi 生態有什麼 DApp？
```

### ⚠️ 注意事項
- 所有 Pi 相關資訊來自公開 API
- Pi 價格可能會有波動，請謹慎投資
- 如需進行 Pi 支付，請使用 Pi Browser 完成操作
"""


# ============================================
# 工具註冊資訊（供 ToolRegistry 使用）
# ============================================

PI_TOOLS = [
    get_pi_price,
    get_pi_network_info,
    get_pi_ecosystem,
    get_pi_tools_guide,
]

# 工具元數據
PI_TOOLS_METADATA = {
    "get_pi_price": {
        "name": "get_pi_price",
        "description": "獲取 Pi Network (PI) 幣的即時價格",
        "category": "crypto",
        "tags": ["pi", "price", "crypto"],
        "allowed_agents": ["chat", "crypto", "full_analysis"],
    },
    "get_pi_network_info": {
        "name": "get_pi_network_info",
        "description": "獲取 Pi Network 的專案資訊和市場數據",
        "category": "crypto",
        "tags": ["pi", "info", "crypto"],
        "allowed_agents": ["chat", "crypto", "full_analysis"],
    },
    "get_pi_ecosystem": {
        "name": "get_pi_ecosystem",
        "description": "獲取 Pi Network 生態系統資訊",
        "category": "crypto",
        "tags": ["pi", "ecosystem", "dapp"],
        "allowed_agents": ["chat", "crypto"],
    },
    "get_pi_tools_guide": {
        "name": "get_pi_tools_guide",
        "description": "顯示 Pi Network 工具使用指南",
        "category": "utility",
        "tags": ["pi", "guide", "help"],
        "allowed_agents": ["chat"],
    },
}
