"""
通用工具
非加密貨幣特定的通用功能工具
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from langchain_core.tools import tool

from .schemas import CurrentTimeInput

@tool
def introduction_tool(_query: str = "") -> str:
    """
    介紹本平台系統和開發者資訊。

    適用情境：
    - 用戶詢問「誰是開發者？」「這個平台是誰做的？」
    - 用戶詢問「開發者是誰？」「誰開發了這個系統？」
    - 用戶詢問「本平台開發者」「作者是誰？」
    - 用戶想了解系統背景或開發團隊資訊
    """
    with open("/home/danny/AI-agent/crypto_trading_system/data/data/introduction.txt", "r", encoding="utf-8") as f:
        content = "平台開發者詳細資訊:"+ f.read()
        return content


@tool(args_schema=CurrentTimeInput)
def get_current_time_tool(timezone: str = "Asia/Taipei") -> str:
    """
    獲取當前的日期和時間。

    這個工具可以查詢不同時區的當前時間，預設為台北時間 (UTC+8)。

    適用情境：
    - 用戶詢問「現在幾點？」
    - 用戶詢問「今天是幾號？」
    - 用戶詢問「現在是什麼時間？」
    - 用戶需要知道當前日期或時間
    - 用戶詢問特定時區的時間
    """
    try:
        # 嘗試使用指定的時區
        try:
            tz = ZoneInfo(timezone)
        except Exception:
            # 如果時區無效，使用台北時間
            tz = ZoneInfo("Asia/Taipei")
            timezone = "Asia/Taipei"

        now = datetime.now(tz)

        # 格式化時間
        date_str = now.strftime("%Y年%m月%d日")
        time_str = now.strftime("%H:%M:%S")
        weekday_map = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        weekday = weekday_map[now.weekday()]

        # 判斷是上午還是下午
        period = "上午" if now.hour < 12 else "下午"
        hour_12 = now.hour if now.hour <= 12 else now.hour - 12
        if hour_12 == 0:
            hour_12 = 12
        time_12_str = f"{period} {hour_12}:{now.strftime('%M')}"

        return f"""## 🕐 當前時間

| 項目 | 內容 |
|------|------|
| **日期** | {date_str} ({weekday}) |
| **時間** | {time_str} ({time_12_str}) |
| **時區** | {timezone} |
| **UTC 時間** | {now.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%d %H:%M:%S')} |
"""

    except Exception as e:
        return f"獲取時間時發生錯誤: {str(e)}"
