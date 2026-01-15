"""
CDC 即時搜尋工具
提供即時搜尋台灣 CDC 網站的功能
"""
from langchain_core.tools import tool
from pathlib import Path
import sys
from datetime import datetime

# 添加父目錄到 Python 路徑
sys.path.append(str(Path(__file__).parent.parent))

# 導入 CDC 搜尋函數
from cdc_websearch.scraper_cdc_search import (
    search_cdc_keywords,
    get_article_content
)

# 導入 LLM 和配置
from core.config import llm, remove_think_tags, DISEASE_FORMAT_COMBINED

# CDC 搜尋專用的疾病名稱提取 Prompt（獨立於系統其他部分）
CDC_DISEASE_EXTRACTION_PROMPT = f"""
你是一位臺灣防疫專家，請嚴格根據以下疾病列表提取名稱：
{DISEASE_FORMAT_COMBINED}

規則：
1. 只能回傳列表中的疾病名稱。
2. 🚨 **優先匹配完整的疾病名稱**（極度重要）：
   -當有多個可能匹配時，必須選擇**最長、最具體**的疾病名稱
   - 範例：「新型A型流感」✅ 正確（不可簡化為「流感」❌）
   - 範例：「流感併發重症」✅ 正確（不可簡化為「流感」❌）
   - 範例：「M痘」✅ 正確（不可混淆為「馬堡病毒出血熱」❌）
3. 如果用戶提到「XXX病毒」「XXX病原體」「XXX桿菌」「XXX感染」等後綴詞，提取完整的疾病名稱：
   - 範例：「屈公病毒」→ 提取「屈公病」
   - 範例：「登革熱病毒」→ 提取「登革熱」
   - 範例：「新型A型流感病毒」→ 提取「新型A型流感」（不是「流感」❌）
4. 若無匹配，回覆：「No_Answer」
5. 禁止推測、禁止創造、禁止解釋、禁止簡化。
6. 直接輸出結果。

用戶問題：{{user_message}}

提取到的疾病名稱：
"""

# CDC 內容相關性守門員 Prompt
CDC_RELEVANCE_GATEKEEPER_PROMPT = """
你是一位內容相關性判斷專家。請判斷以下從 CDC 網站爬取的內容是否與用戶的原始問題相關。

## 用戶原始問題：
{user_question}

## CDC 爬取的內容：
{content}

## 判斷規則：
1. 如果內容直接回答或部分回答用戶的問題 → 相關
2. 如果內容包含與問題相關的疾病資訊、症狀、預防措施、疫情數據等 → 相關
3. 如果內容與問題提到的疾病/主題完全無關 → 不相關
4. 如果內容是一般性公告、與問題無關的新聞 → 不相關
5. 如果內容主要是網站導航、版權聲明、無意義文字 → 不相關

## 輸出格式：
只輸出一個詞：「相關」或「不相關」
"""


def extract_disease_from_query(query: str) -> str:
    """
    從用戶查詢中提取疾病名稱（CDC 搜尋工具專用）

    注意：此函數使用 DISEASE_FORMAT_COMBINED（130+ 種疾病），
    獨立於系統其他部分的疾病提取功能。

    Args:
        query: 用戶的完整查詢

    Returns:
        疾病名稱（如果提取失敗則返回 ""）
    """
    try:
        print(f"  🔍 正在從查詢中提取疾病名稱...")
        print(f"     原始查詢: {query}")

        response = llm.invoke(CDC_DISEASE_EXTRACTION_PROMPT.format(user_message=query))
        disease_name = response.content.strip()
        disease_name = remove_think_tags(disease_name)

        # 判斷是否提取成功
        if disease_name and disease_name not in ["未知疾病", "No_Answer", "", "無", "none", "null"]:
            print(f"  ✅ 成功提取疾病名稱: {disease_name}")
            return disease_name
        else:
            print(f"  ⚠️ 未能提取疾病名稱（返回: {disease_name}）")
            return ""
    except Exception as e:
        print(f"  ❌ 疾病名稱提取失敗: {e}")
        return ""

def check_content_relevance(user_question: str, content: str) -> bool:
    """
    使用 LLM 判斷爬取的內容是否與用戶問題相關
    """
    try:
        # 如果內容太短，可能無法判斷，但為了安全起見，如果不是極短則預設檢查
        if len(content) < 50:
            # 內容過短，可能是雜訊
             return False

        # 截斷過長的內容以節省 Token，但保留足夠資訊供判斷 (前 2000 字)
        content_preview = content[:2000] 
        
        prompt = CDC_RELEVANCE_GATEKEEPER_PROMPT.format(
            user_question=user_question,
            content=content_preview
        )
        
        response = llm.invoke(prompt).content.strip()
        response = remove_think_tags(response)
        
        # 寬鬆判斷：只要不包含"不相關"就視為相關，或者明確包含"相關"
        # 考慮到 LLM 可能輸出 "相關。" 或 "結果：相關"，我們檢查關鍵字
        is_relevant = "不相關" not in response
        
        if is_relevant:
            print(f"  ✅ [守門員] 內容判定為相關")
        else:
            print(f"  🛑 [守門員] 內容判定為不相關，已攔截")
            
        return is_relevant
    except Exception as e:
        print(f"  ⚠️ [守門員] 判斷發生錯誤，預設為相關: {e}")
        return True


@tool
def search_cdc_realtime(keyword: str, num_results: int = 2) -> str:
    """
    即時搜尋台灣疾病管制署 (CDC) 網站，獲取最新的疫情資訊、防疫政策、統計數據等。

    這個工具適合用於查詢：
    - 最新疫情通報和趨勢
    - 防疫政策更新和公告
    - 疫情統計數據
    - 疾病監測報告
    - 旅遊疫情建議

    注意：本工具查詢的是 CDC 官網的即時資訊，如果需要查詢法定傳染病的基本定義、
    症狀、傳播途徑等靜態知識，建議使用向量資料庫檢索（cdc_infectious_diseases）。

    Args:
        keyword: 搜尋關鍵字（如：「登革熱疫情」、「流感統計」、「COVID-19」）
        num_results: 返回結果數量，預設 2 筆（範圍 1-5）

    Returns:
        格式化的搜尋結果，包含標題、內容摘要和來源連結
    """
    try:
        # 限制搜尋結果數量
        num_results = max(1, min(num_results, 5))

        print(f"[CDC 即時搜尋] 原始關鍵字: {keyword}, 結果數: {num_results}")

        # 步驟 0: 從查詢中提取疾病名稱（改善搜尋效果）
        disease_name = extract_disease_from_query(keyword)

        # 決定使用哪個搜尋關鍵字
        if disease_name:
            # 使用提取的疾病名稱搜尋（更精準）
            search_keyword = disease_name
            print(f"[CDC 即時搜尋] ✅ 使用提取的疾病名稱搜尋: {search_keyword}")
        else:
            # 回退到原始關鍵字
            search_keyword = keyword
            print(f"[CDC 即時搜尋] ⚠️ 未提取到疾病名稱，使用原始關鍵字: {search_keyword}")

        # 步驟 1: 如果提取到疾病名稱,優先獲取疾病介紹頁面
        disease_page_content = None
        disease_page_url = None
        if disease_name:
            try:
                from cdc_websearch.scraper_cdc_website import scrape_disease_description, get_disease_name
                disease_page_url = get_disease_name(disease_name)
                if disease_page_url:
                    disease_page_content = scrape_disease_description(disease_name)
                    print(f"[CDC 即時搜尋] ✅ 成功獲取疾病介紹頁面: {disease_page_url}")
            except Exception as e:
                print(f"[CDC 即時搜尋] ⚠️ 無法獲取疾病介紹頁面: {e}")

        # 步驟 2: 搜尋 CDC 網站(新聞/公告/Q&A等)
        search_results = search_cdc_keywords(search_keyword, k_value=num_results)

        # 如果沒有疾病頁面且搜尋也沒結果,返回錯誤
        if not disease_page_content and not search_results:
            return f"❌ CDC 即時搜尋：未找到關於「{keyword}」的相關資訊。建議嘗試不同的關鍵字。"

        # 步驟 3: 格式化結果
        formatted_results = []
        formatted_results.append(f"以下是從 CDC 官網即時搜尋到的相關資訊（關鍵字：「{keyword}」）：\n")
        formatted_results.append("**參考依據**")

        # 優先添加疾病介紹頁面（但要過濾掉錯誤訊息）
        if disease_page_content and disease_page_url:
            # 檢查是否為錯誤訊息（不應該被添加到參考資料中）
            error_indicators = ["網路請求錯誤：", "錯誤：", "Error:", "timeout", "Timeout"]
            is_error = any(indicator in disease_page_content for indicator in error_indicators)

            if is_error:
                print(f"  ⚠️ 疾病介紹頁面包含錯誤訊息，已過濾不添加到結果中")
                print(f"     錯誤內容: {disease_page_content[:100]}")
            else:
                formatted_results.append(f"\n《{disease_page_url}》")
                formatted_results.append(f"   標題：{disease_name}疾病介紹")
                formatted_results.append(f"   發布日期：{datetime.now().strftime('%Y-%m-%d')}")
                formatted_results.append(f"   來源：CDC 官網疾病介紹頁面\n")
                # 🚨 醫療信息應完整顯示，不截斷
                formatted_results.append(f"   {disease_page_content}\n")
                print(f"  ✅ 已添加疾病介紹頁面到結果中（完整內容）")

        for i, result in enumerate(search_results, 1):
            title = result.get('title', 'N/A')
            link = result.get('link', 'N/A')
            date = result.get('date', 'N/A')
            summary = result.get('summary', 'N/A')

            # 嘗試獲取完整內容
            print(f"  → 正在提取結果 {i} 的完整內容...")
            print(f"     [Fetching: {link}]")
            content = get_article_content(link)

            # 列印提取結果（用於調試）
            print(f"  ✅ 提取完成！")
            print(f"     內容長度: {len(content) if content else 0} 字元")
            if content:
                print(f"     內容類型: {'成功' if not content.startswith(('[Fallback]', '[trafilatura]', 'Unable')) else '失敗/回退'}")
                print(f"     內容預覽 (前 200 字元):")
                print(f"     {'-'*60}")
                print(f"     {content[:200]}")
                print(f"     {'-'*60}")

            # 判斷內容提取是否成功（同時過濾錯誤訊息）
            error_indicators = ["網路請求錯誤：", "錯誤：", "Error:", "timeout", "Timeout"]
            has_error = content and any(indicator in content for indicator in error_indicators)

            # 🚨 只有在有有效內容時才添加結果（避免返回空內容）
            has_valid_content = False
            result_content = None

            if content and not content.startswith(("[Fallback]", "[trafilatura]", "Unable")) and not has_error:
                # 🚨 醫療信息應完整顯示，不截斷
                print(f"  ✅ 成功提取完整內容，將添加到結果中（完整內容）")
                result_content = content
                has_valid_content = True
            else:
                # 內容提取失敗或包含錯誤訊息，嘗試使用摘要
                if has_error:
                    print(f"  ⚠️ 內容包含錯誤訊息，已過濾，嘗試使用摘要")
                else:
                    print(f"  ⚠️ 內容提取失敗或為空，嘗試使用摘要")

                if summary and summary != 'N/A' and summary.strip():
                    result_content = f"摘要：{summary}"
                    has_valid_content = True
                else:
                    print(f"  ❌ 摘要也為空，跳過此結果")

            # 只有在有有效內容時，才添加到結果中
            if has_valid_content and result_content:
                # 🆕 加入相關性判斷守門員
                print(f"  🔍 [守門員] 正在判斷內容相關性...")
                # 使用原始 keyword 或 disease_name 進行判斷？
                # 這裡使用用戶的原始輸入 keyword 進行判斷可能更準確，或者使用 disease_name
                check_query = keyword
                if disease_name:
                    check_query = f"{keyword} (疾病: {disease_name})"

                if check_content_relevance(check_query, result_content):
                    formatted_results.append(f"\n《{link}》")
                    formatted_results.append(f"   標題：{title}")
                    formatted_results.append(f"   發布日期：{date}")
                    formatted_results.append(f"   來源：CDC 官網即時搜尋\n")
                    formatted_results.append(f"   {result_content}")
                else:
                    print(f"  🗑️ [守門員] 已過濾不相關內容: {title}")

        return "\n".join(formatted_results)

    except Exception as e:
        error_msg = f"❌ CDC 即時搜尋發生錯誤：{str(e)}"
        print(error_msg)
        return error_msg


# ==================== 工具註冊 ====================

def register_cdc_tool():
    """註冊 CDC 即時搜尋工具到工具註冊表"""
    from tools_config import register_tool, ToolConfig

    cdc_tool_config = ToolConfig(
        id="cdc_realtime_search",
        name="CDC 即時搜尋",
        description="即時搜尋台灣 CDC 網站，獲取最新疫情資訊、防疫政策、統計數據",
        tool_func=search_cdc_realtime,
        enabled=True,  # 預設啟用
        support_medical=True,
        support_general=False,
        timeout=30,
        retry_on_failure=False,
        metadata={
            "category": "external_search",
            "data_source": "taiwan_cdc",
            "search_type": "realtime"
        }
    )

    register_tool(cdc_tool_config)
    print("✅ CDC 即時搜尋工具已註冊")


# ==================== 測試程式 ====================

if __name__ == "__main__":
    # 測試工具
    print("🧪 測試 CDC 即時搜尋工具\n")

    # 測試 1: 搜尋登革熱
    print("測試 1: 搜尋「登革熱疫情」")
    print("=" * 80)
    result = search_cdc_realtime.invoke({"keyword": "登革熱疫情", "num_results": 2})
    print(result)
    print("\n")

    # 測試 2: 搜尋流感
    print("測試 2: 搜尋「流感」")
    print("=" * 80)
    result = search_cdc_realtime.invoke({"keyword": "流感", "num_results": 1})
    print(result)