import asyncio
from core import config
import json
import time
from typing import List, Optional

import opencc
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from rag_system.rag_system_core import convert_references_to_english
from rag_system.rag_jsonl import (
    search_vectordb_with_scores,
    load_existing_vectordb,
)
from core.config import DB_CONNECTION_STRING, _VECTORSTORE_CACHE, RETRIEVAL_CONFIG
from utils.prompt_function import get_criteria_matching_prompt, get_system_prompt_for_multi_source  # 新增：從 prompts 導入
from retrieval.clue_extraction import process_retrieval_with_clue_extraction  # 新增：使用線索提取

# ========================================
# 全局配置
# ========================================

# 繁簡轉換器
convert = opencc.OpenCC('s2tw.json')

# ========================================
# 工具函數
# ========================================

def count_tokens(text: str) -> int:
    """估算 token 數量"""
    if not isinstance(text, str):
        text = str(text)
    return max(1, int(len(text) / 1.3))


def create_text_splitter(chunk_size: int = 3000, chunk_overlap: int = 256) -> RecursiveCharacterTextSplitter:
    """創建文本分割器"""
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "!", "?", ";", ",", " ", ""],
        length_function=count_tokens
    )

# ========================================
# VectorStore 管理
# ========================================

async def get_or_create_vectordb(connection_string: str, collection_name: str):
    """獲取或創建 vectorstore（使用快取避免重複載入）"""
    key = (connection_string, collection_name)
    
    if key not in _VECTORSTORE_CACHE:
        _VECTORSTORE_CACHE[key] = load_existing_vectordb(connection_string, collection_name)
    
    return _VECTORSTORE_CACHE[key]


# ========================================
# LLM 調用
# ========================================

async def safe_llm_invoke(messages: List):
    """安全的 LLM 調用（無並發限制）"""
    try:
        response = await config.llm.ainvoke(messages)
        return response
    except Exception as e:
        print(f"❌ LLM 調用失敗: {e}")
        raise


# ========================================
# 核心異步函數
# ========================================

async def find_best_matching_criteria(query: str) -> str:
    """匹配最佳醫療準則"""
    system_prompt = get_criteria_matching_prompt()  # 修改：從 prompts.py 導入
    
    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"問題: {query}")
        ]
        response = await safe_llm_invoke(messages)
        result = response.content.strip()
        return result if result != "No Answer" else "No Answer"
    except Exception as e:
        print(f"❌ 準則匹配失敗: {e}")
        return "No Answer"


# ========================================
# 摘要處理（修改為支援多來源）
# ========================================
# 刪除原有的 get_system_prompt_for_multi_source 函數
# 現在從 prompts.py 導入

async def _summarize_chunk_multi_source(
    chunk_text: str,
    focus_query: Optional[str] = None,
    data_type: Optional[str] = None,
    system_prompt: Optional[str] = None,
    is_final: bool = False
) -> str:
    """摘要單個文本塊（多來源版本）"""
    if is_final:
        system_prompt += """\n\n【重要】這是最終整理，請確保每個資料來源的答案都獨立呈現，
        並保留所有參考資料來源完整檔案名稱標，輸出格式請依照下方：
        請嚴格遵守使用以下格式，並請注意文件名稱不要重複，否則應該合併內容後表述
        【輸出格式】
        **參考依據**
        《文件名稱1》
            -內文內容1
            -內文內容2
            -內文內容3
        如果還有更多內文內容，依此類推...
        《文件名稱2》-內文內容2
            -內文內容1
            -內文內容2
            -內文內容3
        如果還有更多內文內容，依此類推...
        《文件名稱3》-內文內容3
            -內文內容1
            -內文內容2
            -內文內容3
        如果還有更多內文內容，依此類推...
        《文件名稱4》-內文內容4
            -內文內容1
            -內文內容2
            -內文內容3
        如果還有更多內文內容，依此類推...

        ...依此類推（有參考到的症狀都必須給出他的參考文獻名稱以及內容。
        """
    
    user_content = f"原始資料：\n{chunk_text}"
    if focus_query:
        user_content = f"用戶查詢：「{focus_query}」\n\n" + user_content
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content)
    ]
    
    try:
        response = await safe_llm_invoke(messages)
        cleaned_response = response.content.strip()
        
        if not cleaned_response or len(cleaned_response.replace("(", "").replace(")", "")) < 3:
            return "（無法提取有效摘要）"
        
        return cleaned_response
    except Exception as e:
        print(f"❌ 摘要失敗: {e}")
        return "（整理時發生錯誤）"


async def summarize_with_llm_multi_source(
    raw_content,
    focus_query: Optional[str] = None,
    data_type: Optional[str] = None,
    verbose: bool = False
) -> str:
    """使用 LLM 進行多來源摘要（支援超長內容分塊）"""
    if isinstance(raw_content, (list, dict)):
        try:
            content_str = json.dumps(raw_content, ensure_ascii=False, indent=2)
        except:
            content_str = str(raw_content)
    else:
        content_str = str(raw_content) if raw_content is not None else ""
    
    if not content_str.strip():
        return "（無有效內容）"
    
    system_prompt = get_system_prompt_for_multi_source(data_type)
    total_tokens = count_tokens(content_str + system_prompt + (focus_query or ""))
    
    if verbose:
        print(f"📊 初始內容長度: {total_tokens} tokens")

    # ====== 新增：如果超過安全閾值（例如 7000），就分塊處理 ======
    MAX_SAFE_TOKENS = 8192  # 留空間給 prompt 和輸出
    if total_tokens <= MAX_SAFE_TOKENS:
        # 安全，直接摘要
        return await _summarize_chunk_multi_source(
            chunk_text=content_str,
            focus_query=focus_query,
            data_type=data_type,
            system_prompt=system_prompt,
            is_final=True
        )
    
    # ====== 超長：分塊處理 ======
    if verbose:
        print("⚠️ 內容過長，啟用分塊摘要...")
    
    # 建立 text splitter（使用你已定義的）
    splitter = create_text_splitter(chunk_size=8192, chunk_overlap=200)
    chunks = splitter.split_text(content_str)
    
    if verbose:
        print(f"✂️ 切分為 {len(chunks)} 個文本塊")

    # 並行摘要每塊
    async def summarize_single_chunk(i, chunk):
        summary = await _summarize_chunk_multi_source(
            chunk_text=chunk,
            focus_query=focus_query,
            data_type=data_type,
            system_prompt=system_prompt,
            is_final=False  # 不是最終
        )
        return f"【片段 {i+1}】\n{summary}"

    chunk_summaries = await asyncio.gather(
        *[summarize_single_chunk(i, chunk) for i, chunk in enumerate(chunks)]
    )

    # 合併所有片段摘要，再做一次最終整理（可選）
    combined_summary = "\n\n".join(chunk_summaries)
    
    # 可選：再送一次給 LLM 做最終整合（但要小心長度！）
    # 這裡保守起見，直接返回合併結果
    return combined_summary

# ========================================
# 最終答案合併（修改為不整合，只是排版）
# ========================================

async def combine_multi_source_answers(
    pdf_summary: str,
    rag_summary: str,
    public_rag_summary: str,
    original_query: str
) -> str:
    """合併多來源答案（極簡版本，純為 LLM 優化）"""

    # 檢查摘要是否有效
    invalid_markers = [
        "（內容與問題無關）",
        "（無有效內容）",
        "（任務執行失敗）",
        "（摘要失敗）",
        "（整理時發生錯誤）"
    ]

    def is_valid(summary: str) -> bool:
        has_invalid_marker = any(marker in summary for marker in invalid_markers)
        is_long_enough = len(summary.strip()) >= 10
        result = not has_invalid_marker and is_long_enough

        # 🔧 調試：顯示驗證過程
        if summary:
            print(f"   驗證 '{summary[:30]}...': 有效標記={not has_invalid_marker}, 長度足夠={is_long_enough}, 結果={result}")

        return result

    # 收集有效答案
    valid_answers = []

    if is_valid(pdf_summary):
        #print(f"   ✅ pdf_summary 有效，加入結果")
        valid_answers.append(f"來源：PDF準則\n{pdf_summary}")
    else:
        print(f"   ❌ pdf_summary 無效")

    if is_valid(rag_summary):
        #print(f"   ✅ rag_summary 有效，加入結果")
        valid_answers.append(f"來源：醫療知識庫\n{rag_summary}")
    else:
        print(f"   ❌ rag_summary 無效")

    if is_valid(public_rag_summary):
        #print(f"   ✅ public_rag_summary 有效，加入結果")
        valid_answers.append(f"來源：衛教園地\n{public_rag_summary}")
    else:
        print(f"   ❌ public_rag_summary 無效")

    # 如果沒有有效答案
    if not valid_answers:
        print(f"⚠️ combine_multi_source_answers: 沒有有效答案，返回 'No Answer'")
        return "No Answer"

    # 簡單分隔
    result = "\n---\n".join(valid_answers)
    #print(f"✅ combine_multi_source_answers 返回: {len(result)} 字元, {len(valid_answers)} 個來源")
    return result


# ========================================
# 查詢任務定義（使用多來源摘要）
# ========================================

async def task_pdf_rag(user_query: str, matched_criteria: str) -> str:
    """PDF 準則檢索（使用線索提取）"""
    cname = convert_references_to_english(matched_criteria)
    if cname == "No Answer":
        return "（無有效內容）"

    vectorstore = await get_or_create_vectordb(DB_CONNECTION_STRING, cname)
    results = search_vectordb_with_scores(vectorstore, user_query, k=RETRIEVAL_CONFIG['pdf_rag_k'])
    # 使用線索提取代替原本的摘要（現在返回三個值）
    formatted_knowledge, sources, _ = await process_retrieval_with_clue_extraction(
        sub_question=user_query,
        documents_with_scores=results,
        main_question=user_query,
        store=None,  # 可以選擇性加入 store 進行快取
        user_id="default"
    )

    if not formatted_knowledge:
        return "（無有效內容）"

    return formatted_knowledge


async def task_medical_rag(user_query: str, matched_criteria: str) -> str:
    """醫療知識庫檢索（使用線索提取）"""
    vectorstore = await get_or_create_vectordb(DB_CONNECTION_STRING, "medical_knowledge_base")
    enhance_question = user_query if matched_criteria == "No Answer" else f"{matched_criteria}:{user_query}"
    results = search_vectordb_with_scores(vectorstore, enhance_question, k=RETRIEVAL_CONFIG['medical_rag_k'])
    # 使用線索提取代替原本的摘要（現在返回三個值）
    formatted_knowledge, sources, _ = await process_retrieval_with_clue_extraction(
        sub_question=enhance_question,
        documents_with_scores=results,
        main_question=user_query,
        store=None,
        user_id="default"
    )

    if not formatted_knowledge:
        return "（無有效內容）"

    return formatted_knowledge


async def task_public_rag(user_query: str) -> str:
    """衛教園地資料庫檢索（使用線索提取）"""
    vectorstore = await get_or_create_vectordb(
        DB_CONNECTION_STRING,
        "public_health_information_of_education_sites"
    )
    results = search_vectordb_with_scores(vectorstore, user_query, k=RETRIEVAL_CONFIG.get('public_rag_k', 5))
    # 使用線索提取代替原本的摘要（現在返回三個值）
    formatted_knowledge, sources, _ = await process_retrieval_with_clue_extraction(
        sub_question=user_query,
        documents_with_scores=results,
        main_question=user_query,
        store=None,
        user_id="default"
    )

    if not formatted_knowledge:
        return "（無有效內容）"

    return formatted_knowledge


# ========================================
# 核心：一鍵獲取最終答案
# ========================================

async def get_final_answer_from_query_async(
    user_query: str,
    verbose: bool = False
) -> str:
    """從用戶查詢獲取最終答案（使用 medical_kb_jsonl 資料源）

    Args:
        user_query: 用戶問題
        verbose: 是否顯示詳細資訊

    Returns:
        str: 最終答案（包含所有來源的獨立答案）或 "No Answer"
    """
    start_time = time.time()
    matched_criteria = await find_best_matching_criteria(user_query)

    async def safe_task(coro, task_name: str) -> str:
        """安全執行任務，捕獲異常"""
        try:
            task_start = time.time()
            result = await coro
            task_elapsed = time.time() - task_start
            # if verbose:
            #     print(f"✅ {task_name} 完成 ({task_elapsed:.2f}秒)")
            return result
        except Exception as e:
            print(f"❌ {task_name} 失敗: {e}")
            return "（任務執行失敗）"

    # 並行執行檢索任務（PDF + JSONL 醫療知識庫）
    pdf_summary, rag_summary = await asyncio.gather(
        safe_task(
            task_pdf_rag(user_query, matched_criteria),
            "PDF 準則"
        ),
        safe_task(
            task_medical_rag(user_query, matched_criteria),
            "醫療知識庫"
        )
    )
    public_rag_summary = ""

    final_answer = await combine_multi_source_answers(
        pdf_summary=pdf_summary,
        rag_summary=rag_summary,
        public_rag_summary=public_rag_summary,
        original_query=user_query
    )
    
    elapsed_time = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"✅ 完成！總耗時: {elapsed_time:.2f} 秒")
    print("=" * 80)
    
    return final_answer


# ========================================
# 使用範例
# ========================================

if __name__ == "__main__":
    # 測試問題
    user_query = "我有一點高血壓"
    
    async def main():
        print("\n" + "🏥 " * 40)
        print(f"用戶問題: {user_query}")
        print("🏥 " * 40 + "\n")
        
        answer = await get_final_answer_from_query_async(
            user_query,
            verbose=True
        )
        
        if answer != "No Answer":
            answer = convert.convert(answer)
        
        print("\n" + "=" * 80)
        print("🎯 最終答案:")
        print("=" * 80)
        print(answer)
        print("=" * 80 + "\n")
    
    asyncio.run(main())