"""
Google 搜尋工具
提供即時搜尋 Google 的功能,使用 Playwright 模擬真實瀏覽器行為
"""
from langchain_core.tools import tool
from pathlib import Path
import sys
import asyncio

# 添加 crewai 目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

# 導入 Google 搜尋類
from utils.google_search_playwright import GoogleSearchWithPlaywright


@tool
async def search_google_realtime(query: str, max_results: int = 5, show_browser: bool = False) -> str:
    """
    即時搜尋 Google,獲取最新的網路資訊。

    這個工具適合用於查詢:
    - 最新新聞和時事
    - 即時資訊和趨勢
    - 一般網路搜尋結果
    - 技術問題和解決方案

    注意:本工具使用 Playwright 模擬真實瀏覽器,包含反偵測機制,
    搜尋速度較慢但成功率較高。

    Args:
        query: 搜尋關鍵字(如:"最新疫情新聞"、"Python教學")
        max_results: 返回結果數量,預設 5 筆(範圍 1-10)
        show_browser: 是否顯示瀏覽器視窗(調試用),預設 False

    Returns:
        格式化的搜尋結果,包含標題、URL 和描述
    """
    try:
        # 限制搜尋結果數量
        max_results = max(1, min(max_results, 10))

        print(f"[Google 即時搜尋] 關鍵字: {query}, 結果數: {max_results}")

        # 創建搜尋器實例
        searcher = GoogleSearchWithPlaywright(show_browser=show_browser)

        # 執行搜尋(異步函數直接 await)
        print(f"[Google 即時搜尋] 🔎 開始搜尋...")

        # 直接 await 異步函數（不使用 asyncio.run）
        results = await searcher.search(query, max_results=max_results)

        if not results:
            return f"❌ Google 即時搜尋:未找到關於「{query}」的相關資訊。可能被 CAPTCHA 封鎖或網路問題。"

        # 格式化搜尋結果
        formatted_results = []
        formatted_results.append(f"以下是從 Google 即時搜尋到的相關資訊(關鍵字:「{query}」):\n")
        formatted_results.append("**搜尋結果**")

        for i, result in enumerate(results, 1):
            rank = result.get('rank', i)
            title = result.get('title', 'N/A')
            url = result.get('url', 'N/A')
            description = result.get('description', '')

            # 使用《》格式,與其他工具保持一致
            formatted_results.append(f"\n{rank}. 《{url}》")
            formatted_results.append(f"   標題:{title}")

            if description:
                # 限制描述長度
                if len(description) > 300:
                    description = description[:300] + "..."
                formatted_results.append(f"   描述:{description}")

            formatted_results.append(f"   來源:Google 即時搜尋\n")

        return "\n".join(formatted_results)

    except Exception as e:
        error_msg = f"❌ Google 即時搜尋發生錯誤:{str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg


# ==================== 工具註冊 ====================

def register_google_tool():
    """註冊 Google 即時搜尋工具到工具註冊表"""
    from tools_config import register_tool, ToolConfig

    google_tool_config = ToolConfig(
        id="google_realtime_search",
        name="Google 即時搜尋",
        description="即時搜尋 Google,獲取最新網路資訊、新聞、技術問題解答",
        tool_func=search_google_realtime,
        enabled=False,  # 預設停用(因為速度較慢)
        support_medical=False,
        support_general=True,
        timeout=60,  # Google 搜尋可能較慢,設置 60 秒超時
        retry_on_failure=False,
        metadata={
            "category": "external_search",
            "data_source": "google",
            "search_type": "realtime",
            "browser_based": True
        }
    )

    register_tool(google_tool_config)
    print("✅ Google 即時搜尋工具已註冊")


# ==================== 測試程式 ====================

if __name__ == "__main__":
    # 測試工具
    print("🧪 測試 Google 即時搜尋工具\n")

    # 測試 1:搜尋最新新聞
    print("測試 1:搜尋「台灣疫情新聞」")
    print("=" * 80)
    result = asyncio.run(search_google_realtime.ainvoke({
        "query": "台灣疫情新聞",
        "max_results": 3,
        "show_browser": False
    }))
    print(result)
    print("\n")

    # # 測試 2:搜尋技術問題
    # print("測試 2:搜尋「Python 教學」")
    # print("=" * 80)
    # result = asyncio.run(search_google_realtime.ainvoke({
    #     "query": "Python 教學",
    #     "max_results": 2,
    #     "show_browser": False
    # }))
    # print(result)