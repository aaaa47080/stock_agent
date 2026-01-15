"""
文獻線索提取模組
針對子問題從檢索到的文獻中提取真正有用的線索，而非直接使用整個文獻內容
"""

from typing import List, Dict, Tuple, Any
from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langgraph.store.base import BaseStore
import json
import hashlib
from core.config import llm, CLUE_EXTRACTION_CONFIG
from core.prompt_config import CLUE_EXTRACTION_PROMPT, CLUE_SUMMARY_PROMPT
from rag_system.unified_metadata import normalize_source_filename
import asyncio
import re
from bs4 import BeautifulSoup


# ==================== 參考文獻過濾 ====================

def is_references_section(text: str) -> Tuple[bool, int]:
    """
    檢測文本是否包含參考文獻區塊

    Returns:
        tuple: (is_references: bool, references_start_pos: int or None)
    """
    if not text:
        return False, None

    # 參考文獻標題模式
    ref_title_patterns = [
        r'(^|\n)\s*#{0,3}\s*參考文[獻献]',
        r'(^|\n)\s*#{0,3}\s*References?\s*\n',
        r'(^|\n)\s*#{0,3}\s*參考資料',
        r'(^|\n)\s*#{0,3}\s*引用文[獻献]',
        r'(^|\n)\s*#{0,3}\s*Bibliography',
        r'(^|\n)\s*#{0,3}\s*文[獻献]\s*\n',
    ]

    for pattern in ref_title_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return True, match.start()

    # 檢測是否大部分內容都是引用格式
    lines = text.strip().split('\n')
    citation_count = 0
    total_lines = 0

    citation_patterns = [
        r'^\d+\.\s*[A-Z][a-z]+\s+[A-Z]{1,2}',  # 1. Smith AB...
        r'^\d+\.\s*[A-Z]{2,}[\.\s]',  # 1. WHO...
        r'^\[\d+\]',  # [1]
        r'\d{4}[;:]\d+[-–]\d+',  # 年份;頁碼
    ]

    for line in lines:
        line = line.strip()
        if len(line) < 5:
            continue
        total_lines += 1
        for pattern in citation_patterns:
            if re.search(pattern, line):
                citation_count += 1
                break

    # 如果超過 60% 的行是引用格式，判定為參考文獻
    if total_lines > 5 and citation_count / total_lines > 0.6:
        return True, 0

    return False, None


def remove_references_from_content(text: str) -> str:
    """
    從文本中移除參考文獻區塊

    Returns:
        str: 移除參考文獻後的文本
    """
    if not text:
        return text

    is_ref, start_pos = is_references_section(text)

    if is_ref and start_pos is not None:
        if start_pos == 0:
            # 整段都是參考文獻，返回空
            return ""
        # 只保留參考文獻之前的內容
        return text[:start_pos].strip()

    return text


# ==================== 核心函數 ====================

async def extract_clues_from_document(
    sub_question: str,
    document: Document,
    score: float,
    main_question: str = None,
    llm_model: BaseChatModel = None
) -> Dict[str, Any]:
    """
    從單個文獻中提取針對主問題的有用線索

    Args:
        sub_question: 子問題(用於輔助搜尋)
        document: LangChain Document 物件
        score: 檢索相似度分數
        main_question: 用戶的主問題(用於判斷相關性,預設與sub_question相同)
        llm_model: 使用的 LLM 模型（預設使用 config.llm）

    Returns:
        {
            'document_name': str,
            'is_relevant': bool,
            'clues': List[str],
            'score': float,
            'metadata': dict,
            'original_content': str,
            'has_table': bool,        # 🆕 新增
            'table_images': list      # 🆕 新增
        }
    """
    if llm_model is None:
        llm_model = llm

    if main_question is None:
        main_question = sub_question

    metadata = document.metadata

    # 🆕 提取表格資訊（無論線索提取是否成功都要保留）
    has_table = metadata.get('has_table', False)
    table_images = metadata.get('table_images', [])
    
    # 處理 table_images 可能是字串的情況
    if isinstance(table_images, str):
        try:
            table_images = json.loads(table_images)
        except:
            table_images = []

    # CDC 資料特殊處理
    if metadata.get('source_url') and metadata.get('data_source') == 'taiwan_cdc':
        document_name = metadata['source_url']
    else:
        document_name = (
            metadata.get('pdf_file') or
            metadata.get('source_file') or
            metadata.get('source') or
            metadata.get('disease_name') or
            'Unknown'
        )
        document_name = normalize_source_filename(document_name)
    
    original_full_content = metadata.get('original_full_text', metadata.get('original_text', document.page_content))

    # 🆕 預處理：移除參考文獻區塊
    content = remove_references_from_content(original_full_content)

    # 如果移除參考文獻後內容為空，標記為不相關
    if not content or len(content.strip()) < 20:
        return {
            'document_name': document_name,
            'is_relevant': False,
            'clues': [],
            'score': score,
            'metadata': metadata,
            'original_content': "",  # 不保留參考文獻內容
            'has_table': has_table,
            'table_images': table_images
        }

    # 同時更新 original_full_content（用於後續顯示）
    original_full_content = content

    max_content_length = CLUE_EXTRACTION_CONFIG['max_content_length']
    if len(content) > max_content_length:
        content = content[:max_content_length] + "\n...[內容過長已截斷]"

    try:
        prompt = CLUE_EXTRACTION_PROMPT.format(
            main_question=main_question,
            sub_question=sub_question,
            document_name=document_name,
            document_content=content
        )

        response = await llm_model.ainvoke(prompt)
        result_text = response.content.strip()

        if result_text.startswith('```'):
            result_text = result_text.split('```')[1]
            if result_text.startswith('json'):
                result_text = result_text[4:]

        result = json.loads(result_text)

        is_relevant = result.get('is_relevant', False)
        clues = result.get('clues', [])
        
        return {
            'document_name': document_name,
            'is_relevant': is_relevant,
            'clues': clues,
            'score': score,
            'metadata': metadata,
            'original_content': original_full_content,
            'has_table': has_table,          # 🆕 保留表格資訊
            'table_images': table_images     # 🆕 保留表格圖片路徑
        }

    except Exception as e:
        print(f"⚠️ 線索提取失敗 ({document_name}): {e}")
        fallback_clue = content[:200] + "..." if len(content) > 200 else content
        return {
            'document_name': document_name,
            'is_relevant': False,
            'clues': [fallback_clue],
            'score': score,
            'metadata': metadata,
            'original_content': original_full_content,
            'has_table': has_table,          # 🆕 即使失敗也保留
            'table_images': table_images     # 🆕 即使失敗也保留
        }

async def extract_clues_from_multiple_documents(
    sub_question: str,
    documents_with_scores: List[Tuple[Document, float]],
    main_question: str = None,
    llm_model: BaseChatModel = None
) -> List[Dict[str, Any]]:
    """
    從多個文獻中並行提取線索

    修改：只保留相關的文獻，不因為有表格就保留不相關文獻
    """

    tasks = [
        extract_clues_from_document(sub_question, doc, score, main_question, llm_model)
        for doc, score in documents_with_scores
    ]

    all_results = await asyncio.gather(*tasks)

    # 只保留相關的文獻
    relevant_results = [
        r for r in all_results
        if r['is_relevant']
    ]

    return relevant_results

def format_clues_to_markdown(clue_results: List[Dict[str, Any]]) -> Tuple[str, List[str], Dict[str, Any]]:
    """
    將提取的線索格式化為 Markdown，但【參考依據】顯示原始文獻內容（而非線索）

    Returns:
        Tuple[str, List[str], Dict[str, Any]]:
            - formatted_text: 格式化的 Markdown 文本
            - sources: 來源文件列表
            - docs_dict: {文件名: {'content': str, 'score': float, 'has_table': bool, 'table_images': list}}
    """
    if not clue_results:
        return "", [], {}

    sources = list(set(r['document_name'] for r in clue_results))
    docs_dict: Dict[str, Dict[str, Any]] = {}

    for result in clue_results:
        doc_name = result['document_name']
        original_content = result.get('original_content', '').strip()
        score = result.get('score', 999.0)
        
        # 🆕 優先從 result 直接取得表格資訊（更可靠）
        has_table = result.get('has_table', False)
        table_images = result.get('table_images', [])
        
        # 🆕 如果 result 沒有，再從 metadata 取得（備用）
        if not has_table and not table_images:
            metadata = result.get('metadata', {})
            has_table = metadata.get('has_table', False)
            table_images = metadata.get('table_images', [])

        if not original_content:
            continue

        if doc_name not in docs_dict:
            docs_dict[doc_name] = {
                'content': original_content,
                'score': score,
                'has_table': has_table,
                'table_images': table_images
            }
        else:
            # 合併內容
            existing_content = docs_dict[doc_name]['content']
            if original_content not in existing_content:
                docs_dict[doc_name]['content'] = existing_content + "\n" + original_content
            
            # 保留最小分數
            docs_dict[doc_name]['score'] = min(docs_dict[doc_name]['score'], score)

            # 🆕 合併表格圖片（去重）
            if table_images:
                existing_images = set(docs_dict[doc_name].get('table_images', []))
                new_images = set(table_images)
                docs_dict[doc_name]['table_images'] = list(existing_images | new_images)

            # 🆕 更新 has_table
            if has_table:
                docs_dict[doc_name]['has_table'] = True

    # 格式化為 Markdown
    formatted_parts = ["**參考依據**"]
    for doc_name, doc_info in docs_dict.items():
        formatted_parts.append(f"《{doc_name}》")
        formatted_parts.append(f"{doc_info['content']}")
        formatted_parts.append("")

    formatted_text = "\n".join(formatted_parts).strip()
    return formatted_text, sources, docs_dict



def convert_html_tables_to_markdown(content: str) -> str:
    """
    將 HTML 表格轉換為 Markdown 格式，大幅減少 token 數
    """
    def html_table_to_markdown(table_html: str) -> str:
        try:
            soup = BeautifulSoup(table_html, 'html.parser')
            rows = soup.find_all('tr')
            if not rows:
                return table_html
            
            markdown_rows = []
            for i, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                cell_texts = [cell.get_text(strip=True).replace('|', '｜') for cell in cells]
                markdown_rows.append('| ' + ' | '.join(cell_texts) + ' |')
                
                # 在第一行後加入分隔線
                if i == 0:
                    markdown_rows.append('|' + '---|' * len(cells))
            
            return '\n'.join(markdown_rows)
        except Exception as e:
            print(f"⚠️ 表格轉換失敗: {e}")
            return table_html
    
    # 找出所有 <table>...</table>
    table_pattern = re.compile(r'<table[^>]*>.*?</table>', re.DOTALL | re.IGNORECASE)
    
    def replacer(match):
        return html_table_to_markdown(match.group(0))
    
    return table_pattern.sub(replacer, content)

async def summarize_clues_if_needed(
    question: str,
    formatted_clues: str,
    max_length: int = None,
    llm_model: BaseChatModel = None
) -> str:
    """
    如果線索內容過長，使用 LLM 進行摘要
    """
    
    # 🆕 預處理：轉換 HTML 表格
    original_length = len(formatted_clues)
    formatted_clues = convert_html_tables_to_markdown(formatted_clues)  # 或用 to_text
    if len(formatted_clues) < original_length:
        print(f"📊 表格轉換: {original_length} → {len(formatted_clues)} 字元 (減少 {original_length - len(formatted_clues)})")
    
    # 從配置讀取最大長度
    if max_length is None:
        from core.config import RETRIEVAL_CONFIG
        max_length = RETRIEVAL_CONFIG.get('clue_max_length', 3000)

    if len(formatted_clues) <= max_length:
        return formatted_clues

    print(f"⚠️ 線索內容過長 ({len(formatted_clues)} 字元)，進行摘要...")

    if llm_model is None:
        llm_model = llm

    try:
        prompt = CLUE_SUMMARY_PROMPT.format(
            question=question,
            all_clues=formatted_clues
        )
        # 🆕 加入超時控制（60 秒）
        response = await asyncio.wait_for(
            llm_model.ainvoke(prompt),
            timeout=300
        )

        summarized = response.content.strip()
        print(f"✅ 摘要完成 - 摘要後長度: {len(summarized)} 字元")
        return summarized

    except asyncio.TimeoutError:
        print(f"⚠️ 摘要超時（60秒），使用截斷")
        return formatted_clues[:max_length] + "\n\n[... 內容過長已截斷 ...]"
    except Exception as e:
        print(f"⚠️ 摘要失敗: {e}，使用截斷")
        return formatted_clues[:max_length] + "\n\n[... 內容過長已截斷 ...]"


# ==================== InMemoryStore 快取 ====================

def generate_cache_key(question: str, document_ids: List[str]) -> str:
    """
    生成快取鍵值（基於問題和文獻ID的雜湊）

    Args:
        question: 問題文本
        document_ids: 文獻ID列表（排序後）

    Returns:
        快取鍵值（SHA256 雜湊）
    """
    sorted_ids = sorted(document_ids)
    content = f"{question}||{'|'.join(sorted_ids)}"
    return hashlib.sha256(content.encode()).hexdigest()


async def get_cached_clues(
    store: BaseStore,
    namespace: Tuple[str, str],
    cache_key: str
) -> Dict[str, Any] | None:
    """
    從 InMemoryStore 讀取快取的線索

    Args:
        store: LangGraph BaseStore 實例
        namespace: 命名空間（如 ("clue_cache", "user_123")）
        cache_key: 快取鍵值

    Returns:
        快取的資料或 None
    """
    try:
        # InMemoryStore.aget() 返回 Item 物件（而非列表）
        item = await store.aget(namespace, cache_key)
        if item:
            return item.value
        return None
    except Exception as e:
        print(f"⚠️ 讀取快取失敗: {e}")
        return None


async def save_cached_clues(
    store: BaseStore,
    namespace: Tuple[str, str],
    cache_key: str,
    data: Dict[str, Any]
) -> None:
    """
    將線索保存到 InMemoryStore

    Args:
        store: LangGraph BaseStore 實例
        namespace: 命名空間
        cache_key: 快取鍵值
        data: 要快取的資料
    """
    try:
        await store.aput(namespace, cache_key, data)
        #print(f"💾 已快取線索 (key: {cache_key[:16]}...)")
    except Exception as e:
        print(f"⚠️ 保存快取失敗: {e}")


# ==================== 整合函數 ====================

async def process_retrieval_with_clue_extraction(
    sub_question: str,
    documents_with_scores: List[Tuple[Document, float]],
    main_question: str = None,
    store: BaseStore = None,
    user_id: str = "default",
    llm_model: BaseChatModel = None
) -> Tuple[str, List[str], Dict[str, str]]:
    """
    完整的檢索處理流程（帶線索提取）

    工作流程：
    1. 檢查快取
    2. 提取線索（如果沒有快取）
    3. 格式化
    4. 摘要（如果需要）
    5. 快取結果

    Args:
        sub_question: 子問題(用於輔助搜尋)
        documents_with_scores: 檢索到的文獻列表
        main_question: 用戶的主問題(用於判斷相關性,預設與sub_question相同)
        store: LangGraph BaseStore（可選，用於快取）
        user_id: 用戶ID（用於命名空間）
        llm_model: 使用的 LLM 模型

    Returns:
        (formatted_knowledge, list_of_sources, dict_of_used_sources_with_original_content)
        - formatted_knowledge: 格式化的檢索結果（線索摘要）
        - list_of_sources: 來源文件列表
        - dict_of_used_sources_with_original_content: {文件名: 原始完整內容}
    """
    if not documents_with_scores:
        return "", [], {}

    # 如果沒有提供主問題,則使用子問題作為主問題
    if main_question is None:
        main_question = sub_question

    # 生成快取鍵值(包含主問題和子問題)
    doc_ids = [
        f"{doc.metadata.get('pdf_file', doc.metadata.get('source', 'unknown'))}_p{doc.metadata.get('page', 0)}"
        for doc, _ in documents_with_scores
    ]
    cache_key = generate_cache_key(f"{main_question}|{sub_question}", doc_ids)
    
    # 嘗試讀取快取
    cached_data = None
    if store:
        namespace = ("clue_cache", user_id)
        cached_data = await get_cached_clues(store, namespace, cache_key)

        if cached_data:
            # print(f"✅ 使用快取的線索 (key: {cache_key[:16]}...)")
            return cached_data['knowledge'], cached_data['sources'], cached_data.get('used_sources_dict', {})

    # 無快取，進行提取
    # print(f"🔍 開始提取線索（主問題：{main_question[:40]}...，子問題：{sub_question[:40]}...）")

    # 1. 提取線索
    clue_results = await extract_clues_from_multiple_documents(
        sub_question, documents_with_scores, main_question, llm_model
    )
    if not clue_results:
        print("⚠️ 沒有找到相關線索")
        return "", [], {}

    # print(f"✅ 提取到 {len(clue_results)} 個相關文獻的線索")

    # 2. 格式化（現在返回三個值）
    formatted_knowledge, sources, used_sources_dict = format_clues_to_markdown(clue_results)
    # 3. 摘要（如果需要）
    formatted_knowledge = await summarize_clues_if_needed(
        sub_question, formatted_knowledge, max_length=4096, llm_model=llm_model
    )
    # print(f"✅ 最終格式化知識長度: {len(formatted_knowledge)} 字元")  # 🔧 修復：應該是 len()
    # 4. 快取結果
    if store:
        cache_data = {
            'knowledge': formatted_knowledge,
            'sources': sources,
            'used_sources_dict': used_sources_dict,  # 新增：保存使用的參考文獻字典
            'timestamp': None  # 可以加上時間戳
        }
        await save_cached_clues(store, namespace, cache_key, cache_data)

    for doc_name, doc_info in used_sources_dict.items():
        # doc_info 是 {'content': str, 'score': float} 格式
        content_text = doc_info['content'] if isinstance(doc_info, dict) else doc_info
        print(f"      📄 {doc_name}: {len(content_text)} 字元")

    return formatted_knowledge, sources, used_sources_dict
