"""
DuckDuckGo 即時搜尋工具

使用 ddgs 套件，支援地理限制，並使用 Playwright 提取完整內容
"""

from langchain_core.tools import tool
from ddgs import DDGS
from playwright.sync_api import sync_playwright
import time
import re


def get_page_content(url: str) -> str:
    """
    使用 Playwright 從網頁獲取完整內容
    """
    try:
        # 檢查是否為有效網址
        if not url.startswith(('http://', 'https://')):
            return "[無效網址]"
        
        # 檢查是否為 YouTube 或其他特殊網站
        if 'youtube.com' in url or 'youtu.be' in url:
            return "[影片內容，無法提取文字]"
        
        with sync_playwright() as p:
            # 啟動瀏覽器
            browser = p.chromium.launch(headless=True, timeout=30000)
            page = browser.new_page()
            
            # 設置用戶代理以避免被封鎖
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            })
            
            # 訪問頁面
            page.goto(url, timeout=30000, wait_until="domcontentloaded")
            
            # 等待頁面加載完成
            time.sleep(2)
            
            # 嘗試獲取頁面主要內容
            try:
                # 優先獲取文章內容
                content_selectors = [
                    'article',
                    '.content', 
                    '.post', 
                    '.entry-content',
                    'main',
                    '.main-content',
                    '#content',
                    '.article-content',
                    '.post-content'
                ]
                
                content = None
                for selector in content_selectors:
                    try:
                        content = page.query_selector(selector)
                        if content:
                            break
                    except:
                        continue
                
                if content:
                    text = content.inner_text()
                else:
                    # 如果特定選擇器找不到，獲取 body 內容
                    text = page.inner_text('body')
                
                # 清理文本，移除多餘的空白字符
                text = re.sub(r'\s+', ' ', text).strip()
                
            except Exception as e:
                print(f"  ❌ 選擇器獲取失敗: {str(e)}")
                # 如果選擇器失敗，直接獲取 body 文本
                try:
                    text = page.inner_text('body')
                    text = re.sub(r'\s+', ' ', text).strip()
                except:
                    text = "[內容獲取失敗]"
            
            browser.close()
            
            # 限制內容長度並檢查是否為有效內容
            if text and len(text.strip()) > 10:  # 確保有實際內容
                # if len(text) > 2000:
                #     text = text[:2000] + "\n... (內容過長，已截斷)"
                return text
            else:
                return "[內容過短或無法提取有效內容]"
            
    except Exception as e:
        print(f"  ❌ 獲取頁面內容失敗 {url}: {str(e)}")
        return f"[內容獲取失敗: {str(e)}]"


@tool
def search_duckduckgo_realtime(query: str, max_results: int = 5, region: str = "tw-tzh", safe_search: str = "moderate", get_full_content: bool = True) -> str:
    """
    即時搜尋 DuckDuckGo，獲取最新的網路資訊。

    這個工具適合用於查詢：
    - 最新資訊和趨勢
    - 一般網路搜尋結果
    - 隱私保護搜尋（DuckDuckGo 不追蹤用戶）
    - 替代 Google 搜尋的選擇

    Args:
        query: 搜尋關鍵字（如："最新疫情新聞"、"Python教學"）
        max_results: 返回結果數量，預設 5 筆（範圍 1-10）
        region: 地理區域代碼，預設 "tw-tzh"（台灣繁體中文）
                常用代碼：
                - "tw-tzh": 台灣繁體中文
                - "hk-tzh": 香港繁體中文  
                - "cn-zh": 中國簡體中文
                - "wt-wt": 全球（預設）
                - "us-en": 美國英語
        safe_search: 安全搜尋等級，預設 "moderate"
                - "strict": 嚴格
                - "moderate": 中等
                - "off": 關閉
        get_full_content: 是否獲取完整頁面內容，預設 True

    Returns:
        格式化的搜尋結果，包含標題、URL 和描述/完整內容
    """
    try:
        # 限制搜尋結果數量
        max_results = max(1, min(max_results, 10))

        print(f"[DuckDuckGo 即時搜尋] 關鍵字: {query}, 結果數: {max_results}, 區域: {region}, 安全搜尋: {safe_search}")
        print(f"[DuckDuckGo 即時搜尋] 📝 完整查詢字串: 「{query}」（長度: {len(query)} 字元）")

        print(f"[DuckDuckGo 即時搜尋] 🔎 開始搜尋...")
        
        # 使用 duckduckgo_search 套件
        with DDGS() as ddgs:
            # 執行搜尋，指定區域
            results = list(ddgs.text(
                query, 
                max_results=max_results, 
                region=region, 
                safesearch=safe_search
            ))
        
        if not results:
            return f"❌ DuckDuckGo 即時搜尋：未找到關於「{query}」的相關資訊。"

        print(f"[DuckDuckGo 即時搜尋] 找到 {len(results)} 個結果")
        
        # 格式化搜尋結果
        formatted_results = []
        formatted_results.append(f"以下是從 DuckDuckGo 即時搜尋到的相關資訊（關鍵字：「{query}」，區域：{region}）：\n")
        formatted_results.append("**搜尋結果**")

        for i, result in enumerate(results, 1):
            title = result.get('title', 'N/A')
            url = result.get('href', result.get('url', 'N/A'))
            snippet = result.get('body', result.get('snippet', 'N/A'))

            # 🔧 過濾明顯無關的結果
            if url == 'N/A' or not url or url == '':
                print(f"  ⚠️ 結果 {i} 沒有有效 URL，跳過")
                continue

            # 檢查是否為明顯的垃圾結果（Quizlet學習卡片、驗證頁面等）
            low_quality_indicators = ['flashcards', 'flash-cards', 'confirm you are a human', 'not a bot', 'Reference ID']
            title_and_snippet = f"{title} {snippet}".lower()
            if any(indicator.lower() in title_and_snippet for indicator in low_quality_indicators):
                print(f"  ⚠️ 結果 {i} 疑似低質量內容（{title[:50]}...），跳過")
                continue

            # 使用《》格式，與其他工具保持一致
            formatted_results.append(f"\n{i}. 《{url}》")
            formatted_results.append(f"   標題：{title}")

            # 獲取完整內容或使用摘要
            if get_full_content and url and url.startswith(('http://', 'https://')):
                print(f"  → 正在提取結果 {i} 的完整內容...")
                print(f"     [Fetching: {url}]")
                
                # 獲取完整內容
                full_content = get_page_content(url)
                
                if full_content and not full_content.startswith(("[內容獲取失敗", "[無效網址]", "[影片內容", "[內容過短")):
                    print(f"  ✅ 成功提取完整內容！")
                    print(f"     內容長度: {len(full_content)} 字元")
                    formatted_results.append(f"   內容：{full_content}")
                else:
                    print(f"  ⚠️ 內容提取失敗或為特殊內容，使用摘要代替")
                    if snippet and snippet != 'N/A':
                        formatted_results.append(f"   摘要：{snippet}")
                    else:
                        formatted_results.append(f"   （無法提取完整內容：{full_content}）")
            else:
                # 不獲取完整內容，只使用摘要
                if snippet and snippet != 'N/A':
                    formatted_results.append(f"   摘要：{snippet}")
                else:
                    formatted_results.append(f"   （無摘要）")

            formatted_results.append(f"   來源：DuckDuckGo 即時搜尋（區域：{region}）\n")

        return "\n".join(formatted_results)

    except Exception as e:
        error_msg = f"❌ DuckDuckGo 即時搜尋發生錯誤：{str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg


# ==================== 工具註冊 ====================

def register_duckduckgo_tool():
    """註冊 DuckDuckGo 即時搜尋工具到工具註冊表"""
    from tools_config import register_tool, ToolConfig

    duckduckgo_tool_config = ToolConfig(
        id="duckduckgo_realtime_search",
        name="DuckDuckGo 即時搜尋",
        description="即時搜尋 DuckDuckGo，獲取最新網路資訊、新聞、技術問題解答（支援地理限制，保護隱私）",
        tool_func=search_duckduckgo_realtime,
        enabled=True,  # 預設啟用
        support_medical=False,
        support_general=True,
        timeout=60,  # 增加超時時間，因為需要提取完整內容
        retry_on_failure=False,
        metadata={
            "category": "external_search",
            "data_source": "duckduckgo",
            "search_type": "realtime",
            "privacy_focused": True,
            "supports_region_filter": True,
            "extracts_full_content": True
        }
    )

    register_tool(duckduckgo_tool_config)
    print("✅ DuckDuckGo 即時搜尋工具已註冊")


# ==================== 測試程式 ====================

if __name__ == "__main__":
    # 測試工具
    print("🧪 測試 DuckDuckGo 即時搜尋工具\n")

    # 測試 1：搜尋台灣疫情新聞
    print("測試 1：搜尋「預防癌症」（區域：台灣）")
    print("=" * 80)
    
    result = search_duckduckgo_realtime.invoke({
        "query": "預防癌症",
        "max_results": 2,
        "region": "tw-tzh",
        "safe_search": "moderate",
        "get_full_content": True
    })
    print(result)
    print("\n")