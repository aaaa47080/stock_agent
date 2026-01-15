"""
檢索工具模組
包含知識檢索、查詢擴展、複雜度檢查等功能
使用 LangGraph 的節點和條件邊來組織檢索流程
"""
import json
import os
import re
import asyncio
# 🔧 修復循環導入：移除頂層導入，改為在函數內部導入 get_cache_manager
from typing import List, Tuple, Dict, Optional, TypedDict, Literal, Set
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from retrieval.clue_extraction import process_retrieval_with_clue_extraction
from core.config import llm, remove_think_tags, DB_CONNECTION_STRING, RETRIEVAL_CONFIG
from core.prompt_config import (
    ENTITY_QUERY_EXPANSION_PROMPT,
    QUERY_COMPLEXITY_CHECK_PROMPT_V2,
    SUB_QUESTIONS_GENERATION_PROMPT,
    DISEASE_EXTRACTION_PROMPT,
    MEDICAL_PROCEDURE_CHECK_PROMPT
)
from rag_system.rag_jsonl import (
    search_vectordb_with_scores,
    get_structured_search_results,
    load_existing_vectordb
)
from rag_system.rag_files import get_structured_pdf_results
from core.config import get_reference_mapping
from core.dataclass import QueryComplexityResult
from core.datasource_config import get_registry, DataSource

# 🆕 Langfuse 3.0 匯入 (可選依賴)
try:
    from langfuse import observe, get_client as get_langfuse_client
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    get_langfuse_client = None
    # 創建空的裝飾器以避免錯誤
    def observe(*args, **_):  # noqa: F841
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])


# 🚨 疾病名稱互斥組定義（用於嚴格過濾）
DISEASE_EXCLUSION_GROUPS = [
    # 第一組：流感相關疾病（互斥）
    ["流感", "新型A型流感"],
    # 第二組：M痘相關疾病（互斥）
    # ["M痘", "馬堡病毒出血熱"],
    # 可以繼續添加其他互斥組...
]


def filter_documents_by_disease_name(
    documents_with_scores: List[Tuple],
    user_disease: str
) -> List[Tuple]:
    """
    根據用戶查詢的疾病名稱，嚴格過濾檢索結果

    目的：防止語義相似但實際不同的疾病文件被檢索出來
    例如：查詢「流感」時，不應返回「新型A型流感」的文件

    Args:
        documents_with_scores: 檢索結果 [(Document, score), ...]
        user_disease: 用戶查詢中的疾病名稱（例如："流感"、"新型A型流感"）

    Returns:
        過濾後的檢索結果
    """
    if not user_disease or not documents_with_scores:
        return documents_with_scores

    # 找到用戶疾病所屬的互斥組
    exclusion_group = None
    for group in DISEASE_EXCLUSION_GROUPS:
        if user_disease in group:
            exclusion_group = group
            break

    # 如果用戶疾病不在任何互斥組中，不進行過濾
    if not exclusion_group:
        return documents_with_scores

    # 過濾邏輯
    filtered_results = []
    excluded_diseases = [d for d in exclusion_group if d != user_disease]

    for doc, score in documents_with_scores:
        # 提取文件內容和 metadata
        content = doc.page_content if hasattr(doc, 'page_content') else str(doc)
        metadata = doc.metadata if hasattr(doc, 'metadata') else {}

        # 檢查來源文件名或內容是否包含其他互斥疾病
        source = metadata.get('source', '')

        # 判斷是否應該過濾掉
        should_exclude = False
        for excluded_disease in excluded_diseases:
            # 檢查來源文件名
            if excluded_disease in source:
                should_exclude = True
                print(f"   🚫 過濾文件（來源包含互斥疾病）: {source} (包含「{excluded_disease}」，但用戶查詢「{user_disease}」)")
                break

            # 檢查內容標題（前200字元，通常包含標題）
            if excluded_disease in content[:200]:
                should_exclude = True
                print(f"   🚫 過濾文件（內容包含互斥疾病）: {source[:50]}... (包含「{excluded_disease}」，但用戶查詢「{user_disease}」)")
                break

        if not should_exclude:
            filtered_results.append((doc, score))

    if len(filtered_results) < len(documents_with_scores):
        filtered_count = len(documents_with_scores) - len(filtered_results)
        print(f"   ✅ 疾病名稱嚴格過濾：已過濾掉 {filtered_count} 個不匹配的文件（互斥疾病）")

    return filtered_results


# 🔧 定義智能合併函數（從 graph_nodes.py 移植）
def merge_document_content_smart(existing_content: str, new_content: str) -> str:
    """
    智能合併文檔內容，避免重複的QA對

    Args:
        existing_content: 已存在的文檔內容
        new_content: 新的文檔內容

    Returns:
        合併後的內容（去除重複QA對）
    """
    import re

    # 如果完全相同，直接返回
    if new_content in existing_content:
        return existing_content

    # 🔧 修復：提取問題+答案組合作為去重標識，避免誤刪不同答案
    existing_qa_pairs = set()
    # 匹配完整的 "問題:...答案:..." 格式（不包含關鍵字和參考）
    for match in re.finditer(r'問題:(.*?)答案:(.*?)(?=關鍵字:|參考:|問題:|$)', existing_content, re.DOTALL):
        question_text = match.group(1).strip()
        answer_text = match.group(2).strip()
        existing_qa_pairs.add((question_text, answer_text))

    # 如果沒有QA對格式，直接追加
    if not existing_qa_pairs:
        return existing_content + "\n\n" + new_content

    # 過濾新內容中的重複QA對
    new_paragraphs = []
    for para in new_content.split('\n'):
        para = para.strip()
        if not para:
            continue

        # 檢查是否為QA對（不包含關鍵字和參考）
        qa_match = re.search(r'問題:(.*?)答案:(.*?)(?=關鍵字:|參考:|問題:|$)', para, re.DOTALL)
        if qa_match:
            question_text = qa_match.group(1).strip()
            answer_text = qa_match.group(2).strip()
            qa_key = (question_text, answer_text)
            # 🔧 如果問題+答案組合已存在，跳過
            if qa_key in existing_qa_pairs:
                continue
            else:
                # 新的QA對，添加到集合並保留
                existing_qa_pairs.add(qa_key)
                new_paragraphs.append(para)
        else:
            # 非QA對格式，直接保留
            new_paragraphs.append(para)

    # 如果有新的非重複內容，追加
    if new_paragraphs:
        return existing_content + "\n\n" + "\n".join(new_paragraphs)
    else:
        return existing_content


# ==================== 檢索狀態定義 ====================

class RetrievalState(TypedDict):
    """檢索流程的狀態

    注意: store 對象不能放在狀態中,因為無法序列化
    需要通過 config['configurable']['store'] 傳遞
    """
    # 輸入參數
    query: str
    main_question: Optional[str]
    use_clue_extraction: Optional[bool]
    user_id: str

    # 資料源選擇
    datasource_ids: Optional[List[str]]  # 要使用的資料源 ID 列表，None=自動選擇

    # 中間狀態
    actual_query: str
    matched_disease: str
    is_medical: bool
    is_procedure: bool
    retrieval_strategy: Literal["multi_source", "procedure", "none"]  # 改為 multi_source

    # 檢索結果
    knowledge: str
    original_sources: List[str]
    original_docs_dict: Dict[str, str]
    matched_table_images: Optional[List[Dict]]  # 🆕 表格圖片匹配結果

    # 中間結果(用於組合)
    retrieval_summaries: Dict[str, str]  # {datasource_id: summary}
    json_results: Dict
    pdf_results: Dict


# 文件緩存
def _load_dataset_files() -> set[str]:
    """預載 DataSet 文件列表"""
    dataset_path = os.getenv("DATASET_PATH", "/home/danny/AI-agent/DataSet") + "/"
    actual_files = set()
    try:
        for _, _, files in os.walk(dataset_path):
            for file in files:
                if file.endswith(('.pdf', '.xlsx', '.xls')):
                    actual_files.add(file)
        print(f"✅ 已預載 {len(actual_files)} 個文件到記憶體")
    except Exception as e:
        print(f"⚠️ 無法預載 DataSet 文件列表: {e}")
    return actual_files

DATASET_FILES_CACHE = _load_dataset_files()


# ==================== 輔助函數 ====================

def convert_references_to_english(chinese_ref):
    """將中文參考文獻名稱轉換為英文 collection name

    支持模糊匹配，處理以下情況:
    - 忽略編號前綴（如 "1_", "2_" 等）
    - 忽略文件擴展名（如 ".pdf"）
    - 處理前後空格
    """
    reference_mapping = get_reference_mapping()

    # 清理輸入：移除 .pdf 擴展名和前後空格
    cleaned_ref = chinese_ref.strip()
    if cleaned_ref.endswith('.pdf'):
        cleaned_ref = cleaned_ref[:-4]

    # 1. 直接匹配完整名稱
    if cleaned_ref in reference_mapping:
        return reference_mapping[cleaned_ref]

    # 2. 移除輸入的編號前綴（如果有的話）
    cleaned_ref_without_prefix = cleaned_ref.split('_', 1)[-1] if '_' in cleaned_ref else cleaned_ref

    # 3. 模糊匹配：移除 mapping 中鍵的編號前綴後比對
    for key, value in reference_mapping.items():
        # 移除 mapping 鍵的 "數字_" 前綴
        key_without_prefix = key.split('_', 1)[-1] if '_' in key else key

        # 比對清理後的參考名稱
        if cleaned_ref_without_prefix == key_without_prefix:
            return value

    # 4. 部分匹配：檢查是否包含關鍵詞（容錯機制）
    for key, value in reference_mapping.items():
        key_without_prefix = key.split('_', 1)[-1] if '_' in key else key
        if cleaned_ref_without_prefix in key_without_prefix or key_without_prefix in cleaned_ref_without_prefix:
            print(f"⚠️ 使用部分匹配: '{chinese_ref}' → '{key}' → '{value}'")
            return value

    # 5. 🆕 附件智能匹配：如果是附件文檔，提取疾病名稱並匹配主文檔的 collection
    if cleaned_ref.startswith('附件'):
        # 提取附件中的疾病關鍵字
        import re
        # 策略1：提取「因應XXX」中的疾病名稱（處理「因應發熱伴血小板減少綜合症，...」）
        disease_match = re.search(r'因應([^，,、]+)', cleaned_ref)
        if disease_match:
            disease_keyword = disease_match.group(1).strip()
            # 在 mapping 中尋找包含此疾病名稱的主文檔
            for key, value in reference_mapping.items():
                if disease_keyword in key:
                    print(f"✅ 附件智能匹配: '{chinese_ref}' → 疾病關鍵字 '{disease_keyword}' → '{key}' → '{value}'")
                    return value

        # 策略2：提取「附件X_」之後的內容，直到遇到「，」或「個人防護」
        disease_match = re.search(r'附件[一二三四五六七八九十]+[_、]([^，,]+?)(?:，|個人防護|醫療照護)', cleaned_ref)
        if disease_match:
            disease_keyword = disease_match.group(1).strip()
            # 在 mapping 中尋找包含此疾病名稱的主文檔
            for key, value in reference_mapping.items():
                if disease_keyword in key:
                    print(f"✅ 附件智能匹配: '{chinese_ref}' → 疾病關鍵字 '{disease_keyword}' → '{key}' → '{value}'")
                    return value

    # 找不到則返回預設值
    print(f"⚠️ 無法匹配參考文獻: '{chinese_ref}' → 使用預設值 'medical_knowledge_base'")
    return "medical_knowledge_base"


def extract_sources_from_knowledge(knowledge: str) -> list[str]:
    """從知識文本中提取《文件名》格式的來源"""
    sources = set()
    pattern = r'《([^》]+)》'
    matches = re.findall(pattern, knowledge)
    for match in matches:
        sources.add(match.strip())
    return list(sources)


def extract_disease_name(user_message: str) -> str:
    """提取疾病名稱"""
    messages = [
        SystemMessage(content=DISEASE_EXTRACTION_PROMPT),
        HumanMessage(content=user_message)
    ]
    try:
        disease = llm.invoke(messages).content.strip()
        disease = remove_think_tags(disease)
        return disease
    except Exception:
        return "No_Answer"


# ==================== LangGraph 節點函數 ====================

async def initialize_retrieval_node(state: RetrievalState) -> RetrievalState:
    """初始化節點：處理配置和清理查詢"""
    from core.config import RETRIEVAL_CONFIG

    # 設置預設值
    if state.get("main_question") is None:
        state["main_question"] = state["query"]

    if state.get("use_clue_extraction") is None:
        state["use_clue_extraction"] = RETRIEVAL_CONFIG.get('enable_clue_extraction', False)

    if state.get("user_id") is None:
        state["user_id"] = "default"

    # 清理查詢文本
    query = state["query"]
    actual_query = query.split("\n[系統註記：")[0] if "[系統註記：" in query else query
    state["actual_query"] = actual_query

    # 初始化結果字段
    state["knowledge"] = ""
    state["original_sources"] = []
    state["original_docs_dict"] = {}
    state["rag_summary"] = ""
    state["pdf_summary"] = ""
    state["json_results"] = {}
    state["pdf_results"] = {}
    state["matched_disease"] = ""
    state["is_medical"] = True
    state["is_procedure"] = False

    #print(f"🔧 [INIT] 查詢: {actual_query}")
    #print(f"🔧 [INIT] 配置: clue={state['use_clue_extraction']}, datasource_ids={state.get('datasource_ids')}")

    return state


def route_retrieval_strategy(state: RetrievalState) -> Literal["multi_source", "check_procedure"]:
    """
    路由節點：決定使用哪種檢索策略

    所有問題都使用多資料源架構進行檢索
    """
    datasource_ids = state.get("datasource_ids")

    # 如果使用者指定了資料源，使用指定的資料源
    if datasource_ids:
        print(f"🔀 [ROUTE] 使用者指定資料源 → 多資料源檢索")
        print(f"   指定資料源: {', '.join(datasource_ids)}")
    else:
        print("🔀 [ROUTE] 使用多資料源檢索（自動選擇資料源）")

    return "multi_source"

def extract_qa_pairs_from_text(text: str) -> Set[Tuple[str, str]]:
    """
    從文本中提取所有 QA 對
    返回: {(問題, 答案), ...}
    """
    qa_set = set()
    
    # 匹配 "問題: xxx 答案: yyy" 格式
    pattern = r'問題:\s*(.*?)\s*答案:\s*(.*?)(?=\n問題:|\n關鍵字:|\n參考:|\n【|$)'
    
    for match in re.finditer(pattern, text, re.DOTALL):
        question = match.group(1).strip()
        answer = match.group(2).strip()
        
        # 清理空格
        question = re.sub(r'\s+', ' ', question)
        answer = re.sub(r'\s+', ' ', answer)
        
        if question and answer and len(question) > 3 and len(answer) > 5:
            qa_set.add((question, answer))
    
    return qa_set

def clean_incomplete_sentences(text: str) -> str:
    """
    移除文本末尾不完整的句子

    策略：從文本末尾開始，移除看起來不完整的句子片段
    （例如單個字母後跟句號，如 "G." 或 " K."）

    Args:
        text: 原始文本

    Returns:
        截取到最後一個完整句子的文本
    """
    if not text or len(text.strip()) < 10:
        return text

    text = text.strip()

    # 定義句子結束標點
    sentence_endings = ['。', '！', '？', '.', '!', '?', '」', '』', '》', '）', ')']

    # 持續從末尾移除不完整的句子，直到找到完整的為止
    while True:
        # 找到最後一個句子結束標點
        last_pos = -1
        last_char = None

        for ending in sentence_endings:
            pos = text.rfind(ending)
            if pos > last_pos:
                last_pos = pos
                last_char = ending

        # 如果沒有找到句子結束標點，返回原文
        if last_pos == -1:
            return text

        # 跳過數字中的小數點（如38.5）
        if last_char == '.' and last_pos < len(text) - 1 and text[last_pos + 1].isdigit():
            # 從這個小數點之前繼續找
            text = text[:last_pos]
            if len(text.strip()) < 10:
                return text  # 太短了，返回原文
            continue

        # 檢查這個句號後面是否還有內容
        after_punctuation = text[last_pos + 1:].strip()

        if after_punctuation:
            # 提取後面的純文本（去除標點和空格）
            pure_after = ''.join(c for c in after_punctuation if c.isalnum() or '\u4e00' <= c <= '\u9fff')

            # 如果後面的內容很短（<=3個字符），認為是不完整的句子
            if len(pure_after) <= 3:
                # 移除這個不完整的部分，繼續檢查
                text = text[:last_pos + 1]
                continue

        # 到這裡，說明句號後面沒有內容，或者後面的內容足夠長
        # 檢查這個句子本身的內容是否足夠長
        # 找到上一個句號
        prev_pos = -1
        for ending in sentence_endings:
            pos = text[:last_pos].rfind(ending)
            if pos > prev_pos:
                prev_pos = pos

        # 提取當前句子內容（兩個句號之間）
        if prev_pos >= 0:
            sentence_content = text[prev_pos + 1:last_pos].strip()
        else:
            sentence_content = text[:last_pos].strip()

        # 提取純文本
        pure_content = ''.join(c for c in sentence_content if c.isalnum() or '\u4e00' <= c <= '\u9fff')

        # 如果句子內容太短（<=3個字符），認為是不完整的
        if len(pure_content) <= 3:
            # 移除到上一個句號，繼續檢查
            if prev_pos >= 0:
                text = text[:prev_pos + 1]
                if len(text.strip()) < 10:
                    return text  # 太短了，返回原文
                continue
            else:
                # 沒有上一個句號了，返回原文
                return text

        # 找到了完整的句子，返回結果
        return text


def extract_pdf_paragraphs_from_text(text: str) -> Set[str]:
    """
    從文本中提取 PDF 段落（排除 QA 對）
    返回: {段落1, 段落2, ...}
    """
    # 步驟1: 先移除所有 QA 格式的內容（更嚴格的匹配）
    # 匹配完整的 "問題: ... 答案: ..." 格式
    text_clean = re.sub(
        r'問題:\s*.*?\s*答案:\s*.*?(?=\n\s*問題:|\n\s*關鍵字:|\n\s*參考:|\n\s*【|\n\s*$|$)',
        '',
        text,
        flags=re.DOTALL
    )

    # 步驟2: 額外移除單獨出現的 "問題:" 或 "答案:" 行
    text_clean = re.sub(r'\n\s*問題:.*', '', text_clean)
    text_clean = re.sub(r'\n\s*答案:.*', '', text_clean)

    # 步驟3: 移除標記和分隔線
    text_clean = re.sub(r'【原始PDF段落】', '', text_clean)
    text_clean = re.sub(r'\[來源文件:.*?\]', '', text_clean)
    text_clean = re.sub(r'[─=]{10,}', '', text_clean)

    # 步驟4: 按段落分割
    paragraphs = re.split(r'\n\s*\n+', text_clean)

    pdf_set = set()
    for para in paragraphs:
        para = para.strip()

        # 過濾太短或空的段落
        if len(para) < 20:
            continue

        # 🔧 額外檢查：如果段落中還包含 "問題:" 或 "答案:"，跳過
        if '問題:' in para or '答案:' in para:
            continue

        # 清理空格
        para = re.sub(r'\s+', ' ', para)
        para = re.sub(r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2', para)

        # 🆕 移除不完整的句子
        para = clean_incomplete_sentences(para)

        pdf_set.add(para)

    return pdf_set


# ==================== 段落處理輔助函數 ====================

def get_paragraph_signature(text: str) -> str:
    """獲取段落簽名，用於快速去重（取前 50 個字元）"""
    clean = re.sub(r'\s+', '', text)
    return clean[:50] if len(clean) >= 50 else clean


def is_reference_citation(text: str) -> bool:
    """判斷是否為引用文獻格式"""
    patterns = [
        r'^\d+\.\s*[A-Z][a-z]+\s+[A-Z]{1,2}',  # 38. Fisher DA...
        r'^[A-Z][a-z]+\s+[A-Z]{1,2},',  # Fisher DA,
        r'^\d+\.\s*[\u4e00-\u9fff]',  # 38. 行政院...
    ]
    return any(re.match(p, text.strip()) for p in patterns)


def is_figure_description(text: str) -> bool:
    """判斷是否為圖片描述"""
    return bool(re.match(r'^(圖|圖片|Figure|Fig\.?)\s*\d+', text.strip()))


def extract_qa_and_pdf(content: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    """提取 QA 對和 PDF 段落"""
    qa_pairs = []
    pdf_paragraphs = []

    if '【原始PDF段落】' in content:
        parts = content.split('【原始PDF段落】', 1)
        qa_part, pdf_part = parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    else:
        qa_part, pdf_part = content, ""

    # 提取 QA 對
    qa_pattern = r'問題:\s*(.*?)\s*答案:\s*(.*?)(?=\n問題:|\n關鍵字:|\n參考:|\n【|$)'
    for match in re.finditer(qa_pattern, qa_part, re.DOTALL):
        q, a = match.group(1).strip(), match.group(2).strip()
        if q and a:
            qa_pairs.append((q, a))

    # 如果沒有 QA 對，處理為 PDF 段落
    if not qa_pairs:
        if '【疾病名稱】' in qa_part or '參考資料來源' in qa_part:
            if qa_part.strip():
                pdf_paragraphs.append(qa_part.strip())
        else:
            for p in re.split(r'\n\s*\n', qa_part):
                p = p.strip()
                if p and len(p) > 10:
                    pdf_paragraphs.append(p)

    # 處理 PDF 段落
    if pdf_part:
        pdf_part = re.sub(r'\[來源文件:.*?\]', '', pdf_part)
        pdf_part = re.sub(r'─+', '', pdf_part)
        for p in re.split(r'\n\s*\n', pdf_part):
            p = p.strip()
            if p and len(p) > 10:
                pdf_paragraphs.append(p)

    return qa_pairs, pdf_paragraphs


def merge_documents_intelligently(_doc_name: str, existing_content: str, new_content: str) -> str:
    """
    智能合併同一文檔的 QA 和 PDF 內容，加強去重

    Args:
        _doc_name: 文檔名稱（保留供未來擴展，目前未使用）
        existing_content: 已存在的內容
        new_content: 新內容

    策略：
    1. 分別提取 QA 對和 PDF 段落
    2. QA 使用 dict 去重
    3. PDF 使用簽名去重，並跳過引用文獻和圖片描述
    4. 重新組裝：QA 在前，PDF 在後
    """
    existing_qa, existing_pdf = extract_qa_and_pdf(existing_content)
    new_qa, new_pdf = extract_qa_and_pdf(new_content)

    # 合併並去重 QA
    all_qa = {(q, a): True for q, a in existing_qa + new_qa}

    # 智能去重 PDF 段落
    seen_signatures = set()
    unique_pdf = []

    for p in existing_pdf + new_pdf:
        p = p.strip()
        if len(p) < 10:
            continue

        # 跳過引用文獻和圖片描述（這些容易重複且資訊價值低）
        if is_reference_citation(p) or is_figure_description(p):
            continue

        # 使用簽名去重
        sig = get_paragraph_signature(p)
        if sig and sig not in seen_signatures:
            seen_signatures.add(sig)
            unique_pdf.append(p)

    # 重建內容
    result = []

    if all_qa:
        for q, a in all_qa.keys():
            result.extend([f"問題: {q}", f"答案: {a}", ""])

    if unique_pdf:
        if all_qa:
            result.extend(["─" * 80, "【原始PDF段落】", ""])
        for p in unique_pdf:
            result.extend([p, ""])

    return "\n".join(result).strip()


async def retrieve_multi_source_node(state: RetrievalState, config: Optional[RunnableConfig] = None) -> RetrievalState:
    """
    🆕 多資料源檢索節點
    根據使用者指定或自動選擇的資料源進行檢索
    
    修改點：
    - 保留 metadata 中的 has_table 和 table_images
    - 表格匹配優先從 metadata 取得，fallback 到相似度匹配
    """
    query = state["query"]
    main_question = state["main_question"]
    use_clue_extraction = state["use_clue_extraction"]
    user_id = state["user_id"]
    datasource_ids = state.get("datasource_ids")

    # 從 config 中獲取 store
    store = None
    if config and "configurable" in config:
        store = config["configurable"].get("store")

    # 🔹 步驟 1: 選擇資料源
    registry = get_registry()
    selected_sources: List[DataSource] = []

    if datasource_ids:
        for ds_id in datasource_ids:
            ds = registry.get(ds_id)
            if ds and ds.enabled:
                selected_sources.append(ds)
            elif ds and not ds.enabled:
                print(f"   ⚠️ 資料源 {ds_id} 已停用，跳過")
            else:
                print(f"   ⚠️ 找不到資料源 {ds_id}")
    else:
        selected_sources = registry.get_by_scenario(is_medical=True)

    if not selected_sources:
        print(f"   ❌ 沒有可用的資料源")
        return state

    loop = asyncio.get_running_loop()
    retrieval_results = {}  # {datasource_id: (summary, docs_dict, results)}
    raw_results = {}  # 🆕 保存原始檢索結果，用於提取 reference

    # 🔹 步驟 2: 對每個資料源進行檢索
    for datasource in selected_sources:
        try:
            # 載入向量資料庫
            vectorstore = await loop.run_in_executor(
                None, load_existing_vectordb, DB_CONNECTION_STRING, datasource.collection_name
            )
            results_with_scores = search_vectordb_with_scores(
                vectorstore, query, k=datasource.default_k
            )

            # 🚨 疾病名稱嚴格過濾（防止語義相似但不同的疾病文件被檢索）
            disease_name = extract_disease_name(main_question)
            if disease_name and disease_name not in ["No_Answer", "未知疾病", "無", "none", "null", ""]:
                print(f"   🔍 檢測到疾病名稱：{disease_name}，啟用嚴格過濾")
                results_with_scores = filter_documents_by_disease_name(results_with_scores, disease_name)

            # 🆕 保存原始檢索結果（用於後續 reference 提取）
            raw_results[datasource.id] = results_with_scores

            # 處理結果
            summary = ""
            docs_dict = {}
            results = None

            if use_clue_extraction and store:
                try:
                    summary, _, docs_dict = await process_retrieval_with_clue_extraction(
                        sub_question=query,
                        documents_with_scores=results_with_scores,
                        main_question=main_question,
                        store=store,
                        user_id=user_id
                    )
                    # 格式轉換：{doc: {'content': str, 'score': float}} → 保留完整資訊
                    new_docs_dict = {}
                    for k, v in docs_dict.items():
                        if isinstance(v, dict):
                            content = v.get('content', '')
                            # 🆕 只對PDF內容清理（不包含QA對格式的內容）
                            if not ('問題:' in content and '答案:' in content):
                                content = clean_incomplete_sentences(content)
                            new_docs_dict[k] = {
                                'content': content,
                                'score': v.get('score', 999.0),
                                'has_table': v.get('has_table', False),
                                'table_images': v.get('table_images', [])
                            }
                        else:
                            content = str(v)
                            # 🆕 只對PDF內容清理（不包含QA對格式的內容）
                            if not ('問題:' in content and '答案:' in content):
                                content = clean_incomplete_sentences(content)
                            new_docs_dict[k] = {'content': content, 'score': 999.0, 'has_table': False, 'table_images': []}
                    docs_dict = new_docs_dict
                    
                except Exception as e:
                    print(f"   ⚠️ 線索提取失敗: {e}，使用原始格式")
                    if datasource.source_type == "jsonl":
                        results, summary = get_structured_search_results(
                            results_with_scores, query, top_n=datasource.default_k,
                            show_scores=False, format_type="markdown"
                        )
                    else:
                        results, summary = get_structured_pdf_results(
                            results_with_scores, query,
                            show_scores=False, format_type="markdown"
                        )
            else:
                if datasource.source_type == "jsonl":
                    results, summary = get_structured_search_results(
                        results_with_scores, query, top_n=datasource.default_k,
                        show_scores=False, format_type="markdown"
                    )
                else:
                    results, summary = get_structured_pdf_results(
                        results_with_scores, query,
                        show_scores=False, format_type="markdown"
                    )
                
                # 🆕 修改：處理結果時保留 metadata 中的表格資訊
                if results and 'documents' in results:
                    for doc_data in results['documents']:
                        source_info = doc_data.get('source', {})
                        source_file = source_info.get('file', '')

                        if source_file:
                            content = doc_data.get('content', '')
                            
                            # 🆕 從 metadata 提取表格資訊
                            metadata = doc_data.get('metadata', {})
                            has_table = metadata.get('has_table', False)
                            table_images = metadata.get('table_images', [])
                            
                            # 如果 metadata 沒有，檢查 source_info
                            if not has_table:
                                has_table = source_info.get('has_table', False)
                            if not table_images:
                                table_images = source_info.get('table_images', [])

                            if datasource.source_type == "jsonl":
                                # JSONL 數據處理（不清理，保持原樣）
                                if content and '問題:' in content and '答案:' in content:
                                    docs_dict[source_file] = {
                                        'content': content,
                                        'has_table': has_table,
                                        'table_images': table_images
                                    }
                                else:
                                    title = doc_data.get('title', '')
                                    keywords = doc_data.get('keywords', '')
                                    reference = source_info.get('reference', '')

                                    qa_text = ""
                                    if title:
                                        qa_text += f"問題: {title}\n"
                                    if content:
                                        qa_text += f"答案: {content}\n"
                                    if keywords:
                                        qa_text += f"關鍵字: {keywords}\n"
                                    if reference:
                                        qa_text += f"參考: {reference}\n"

                                    if qa_text:
                                        docs_dict[source_file] = {
                                            'content': qa_text.strip(),
                                            'has_table': has_table,
                                            'table_images': table_images
                                        }
                            else:
                                # PDF 數據處理 - 🆕 只有 PDF 需要清理不完整的句子
                                if content:
                                    # 🆕 清理不完整的句子
                                    content = clean_incomplete_sentences(content)
                                    docs_dict[source_file] = {
                                        'content': content,
                                        'has_table': has_table,
                                        'table_images': table_images
                                    }

            retrieval_results[datasource.id] = (summary, docs_dict, results)
            
        except Exception as e:
            import traceback
            traceback.print_exc()

    # 🔹 步驟 2.5: 動態 PDF 檢索（如果 medical_kb_jsonl 有 reference 欄位）
    # 🆕 改進：從原始檢索結果提取 reference，不依賴線索提取結果
    if "medical_kb_jsonl" in raw_results:
        try:
            unique_references = set()

            # 🆕 從原始檢索結果（results_with_scores）提取 reference
            raw_jsonl_results = raw_results["medical_kb_jsonl"]
            if raw_jsonl_results:
                for doc, _ in raw_jsonl_results:
                    metadata = doc.metadata if hasattr(doc, 'metadata') else {}
                    ref = metadata.get('reference', '')
                    if ref:
                        unique_references.add(ref)
                        print(f"   📌 從原始 JSONL 檢索結果提取 reference: {ref}")

            # 🆕 回退：如果原始結果沒有 reference，嘗試從線索提取後的結果中提取
            if not unique_references and "medical_kb_jsonl" in retrieval_results:
                jsonl_summary, _, jsonl_results = retrieval_results["medical_kb_jsonl"]
                if jsonl_results and 'documents' in jsonl_results:
                    for doc in jsonl_results['documents']:
                        source = doc.get('source', {})
                        ref = source.get('reference', '')
                        if ref:
                            unique_references.add(ref)

                # 再從摘要中提取
                if not unique_references and jsonl_summary:
                    ref_matches = re.findall(r'《([^》]+)》', jsonl_summary)
                    unique_references.update(ref_matches)

            print(f"   📋 從 JSONL 結果提取到 {len(unique_references)} 個不同的 reference")
            
            for selected_reference in unique_references:
                try:
                    pdf_collection_name = convert_references_to_english(selected_reference)
                    pdf_k = RETRIEVAL_CONFIG.get("pdf_k", 3)
                    
                    # print(f"   🔄 動態檢索 PDF: {selected_reference} → {pdf_collection_name} (k={pdf_k})")
                    
                    pdf_vectorstore = await loop.run_in_executor(
                        None, load_existing_vectordb, DB_CONNECTION_STRING, pdf_collection_name
                    )
                    
                    if pdf_vectorstore:
                        pdf_results_with_scores = search_vectordb_with_scores(
                            pdf_vectorstore, query, k=pdf_k
                        )
                        
                        if pdf_results_with_scores:
                            pdf_summary = ""
                            pdf_docs_dict = {}
                            
                            if use_clue_extraction and store:
                                try:
                                    print(f"      🔍 對 PDF 進行線索提取判斷相關性...")
                                    pdf_summary, _, pdf_docs_dict = await process_retrieval_with_clue_extraction(
                                        sub_question=query,
                                        documents_with_scores=pdf_results_with_scores,
                                        main_question=main_question,
                                        store=store,
                                        user_id=user_id
                                    )

                                    # 🆕 檢查是否有相關結果
                                    if pdf_docs_dict:
                                        print(f"      ✅ PDF 線索提取成功，找到 {len(pdf_docs_dict)} 個相關文檔")
                                    else:
                                        print(f"      ⚠️ PDF 線索提取判斷：無相關文檔")

                                    # 🆕 格式轉換並保留表格資訊
                                    new_pdf_docs = {}
                                    for k, v in pdf_docs_dict.items():
                                        if isinstance(v, dict):
                                            content = v.get('content', '')
                                            # 🆕 清理PDF內容中的不完整句子
                                            content = clean_incomplete_sentences(content)
                                            new_pdf_docs[k] = {
                                                'content': content,
                                                'has_table': v.get('has_table', False),
                                                'table_images': v.get('table_images', [])
                                            }
                                        else:
                                            # 🆕 清理PDF內容中的不完整句子
                                            content = clean_incomplete_sentences(str(v))
                                            new_pdf_docs[k] = {'content': content, 'has_table': False, 'table_images': []}
                                    pdf_docs_dict = new_pdf_docs
                                    
                                except Exception as e:
                                    print(f"      ⚠️ PDF 線索提取失敗: {e}，使用原始格式")
                                    pdf_results, pdf_summary = get_structured_pdf_results(
                                        pdf_results_with_scores, query,
                                        show_scores=False, format_type="markdown"
                                    )
                                    if pdf_results and 'documents' in pdf_results:
                                        for doc_data in pdf_results['documents']:
                                            source_info = doc_data.get('source', {})
                                            source_file = source_info.get('file', '')
                                            content = doc_data.get('content', '')
                                            metadata = doc_data.get('metadata', {})

                                            if source_file and content:
                                                # 🆕 清理不完整的句子
                                                content = clean_incomplete_sentences(content)
                                                pdf_docs_dict[source_file] = {
                                                    'content': content,
                                                    'has_table': metadata.get('has_table', False),
                                                    'table_images': metadata.get('table_images', [])
                                                }
                            else:
                                pdf_results, pdf_summary = get_structured_pdf_results(
                                    pdf_results_with_scores, query,
                                    show_scores=False, format_type="markdown"
                                )
                                if pdf_results and 'documents' in pdf_results:
                                    for doc_data in pdf_results['documents']:
                                        source_info = doc_data.get('source', {})
                                        source_file = source_info.get('file', '')
                                        content = doc_data.get('content', '')
                                        metadata = doc_data.get('metadata', {})

                                        # 🔍 DEBUG: 顯示檢索到的 metadata
                                        print(f"\n🔍 [DEBUG] 檢索到文檔: {source_file}")
                                        print(f"   metadata keys: {list(metadata.keys())}")
                                        print(f"   has_table: {metadata.get('has_table', 'NOT_FOUND')}")
                                        print(f"   table_images: {metadata.get('table_images', 'NOT_FOUND')}")

                                        if source_file and content:
                                            # 🆕 清理不完整的句子
                                            content = clean_incomplete_sentences(content)
                                            pdf_docs_dict[source_file] = {
                                                'content': content,
                                                'has_table': metadata.get('has_table', False),
                                                'table_images': metadata.get('table_images', [])
                                            }

                                            print(f"   ✅ 儲存到 pdf_docs_dict:")
                                            print(f"      has_table: {pdf_docs_dict[source_file]['has_table']}")
                                            print(f"      table_images: {pdf_docs_dict[source_file]['table_images']}")
                            
                            retrieval_results[f"dynamic_pdf_{pdf_collection_name}"] = (pdf_summary, pdf_docs_dict, None)
                            print(f"      ✅ 動態 PDF 檢索完成: {len(pdf_results_with_scores)} 筆結果")
                    else:
                        print(f"      ⚠️ 找不到 PDF 向量資料庫: {pdf_collection_name}")
                        
                except Exception as e:
                    print(f"   ⚠️ 動態 PDF 檢索失敗 ({selected_reference}): {e}")
                    
        except Exception as e:
            print(f"   ⚠️ 動態 PDF 檢索整體失敗: {e}")

    # 🔹 步驟 3: 合併結果
    if not retrieval_results:
        return state

    all_summaries = [summary for summary, _, _ in retrieval_results.values() if summary]
    all_docs = {}

    for ds_id, (summary, docs, _) in retrieval_results.items():
        
        for doc_name, doc_info in docs.items():
            # 🆕 處理新的字典格式
            if isinstance(doc_info, dict):
                doc_content = doc_info.get('content', '')
                has_table = doc_info.get('has_table', False)
                table_images = doc_info.get('table_images', [])
            else:
                doc_content = str(doc_info)
                has_table = False
                table_images = []
            
            if doc_name in all_docs:
                # 合併內容
                existing = all_docs[doc_name]
                existing_content = existing.get('content', '') if isinstance(existing, dict) else str(existing)
                merged_content = merge_documents_intelligently(doc_name, existing_content, doc_content)
                
                # 合併表格資訊（取聯集）
                existing_tables = existing.get('table_images', []) if isinstance(existing, dict) else []
                merged_tables = list(set(existing_tables + table_images))
                
                all_docs[doc_name] = {
                    'content': merged_content,
                    'has_table': has_table or existing.get('has_table', False),
                    'table_images': merged_tables
                }
            else:
                normalized_content = merge_documents_intelligently(doc_name, "", doc_content)
                all_docs[doc_name] = {
                    'content': normalized_content,
                    'has_table': has_table,
                    'table_images': table_images
                }

    combined_knowledge = "\n\n---\n\n".join(all_summaries) if all_summaries else ""
    original_sources = extract_sources_from_knowledge(combined_knowledge)

    # 更新狀態
    state["knowledge"] = combined_knowledge
    state["original_sources"] = original_sources
    state["original_docs_dict"].update(all_docs)

    # 合併完成

    # 🆕 步驟 4: 表格圖片匹配（優先從 metadata，fallback 到相似度匹配）
    try:
        import sys
        import os
        ocr_model_path = os.path.join(os.path.dirname(__file__), 'ocr_model')
        if ocr_model_path not in sys.path:
            sys.path.insert(0, ocr_model_path)

        from retrieval.table_matcher import has_table_format, process_search_result

        matched_tables = []
        metadata_match_count = 0
        similarity_match_count = 0

        # 檢查合併後的文檔是否包含表格
        for doc_name, doc_info in all_docs.items():
            if isinstance(doc_info, dict):
                doc_content = doc_info.get('content', '')
                doc_metadata = {
                    'has_table': doc_info.get('has_table', False),
                    'table_images': doc_info.get('table_images', [])
                }
            else:
                doc_content = str(doc_info)
                doc_metadata = None

            # 🆕 優先檢查 metadata 中是否有表格
            if doc_metadata and doc_metadata.get('has_table') and doc_metadata.get('table_images'):
                print(f"      📄 文檔 {doc_name}: 從 metadata 取得表格")

                from core.config import EXTRACTED_TABLES_DIR

                for img_filename in doc_metadata['table_images']:
                    # 兼容新舊格式：如果是完整路徑，則提取檔案名稱
                    if os.path.sep in img_filename or '/' in img_filename:
                        # 舊格式：完整路徑，提取檔案名稱
                        img_filename = os.path.basename(img_filename)

                    # 組合完整路徑：EXTRACTED_TABLES_DIR / images / 檔案名稱
                    full_path = os.path.join(EXTRACTED_TABLES_DIR, "images", img_filename)

                    if os.path.exists(full_path):
                        matched_tables.append({
                            'matched': True,
                            'table_content': None,
                            'image_path': full_path,
                            'similarity': 1.0,
                            'source': 'metadata'
                        })
                        metadata_match_count += 1
                        print(f"         ✅ metadata 匹配: {img_filename}")
                    else:
                        print(f"         ⚠️ 圖片不存在: {full_path}")
                        
            # 🆕 Fallback: 如果 metadata 沒有但內容包含表格，用相似度匹配
            elif has_table_format(doc_content):
                print(f"      📄 文檔 {doc_name}: metadata 無表格資訊，使用相似度匹配")

                page_num = None
                page_match = re.search(r'_p(\d+)_', doc_name)
                if page_match:
                    page_num = int(page_match.group(1))

                match_result = process_search_result(
                    content=doc_content,
                    source_file=doc_name,
                    page_num=page_num,
                    metadata=None  # 明確傳入 None，觸發相似度匹配
                )

                if match_result.get('matched_tables'):
                    for table in match_result['matched_tables']:
                        img_path = table.get('image_path', '')
                        table_filename = os.path.basename(img_path) if img_path else '未知檔案'
                        print(f"         ✅ 相似度匹配: {table_filename} ({table['similarity']:.2%})")
                        matched_tables.append(table)
                        similarity_match_count += 1

        if matched_tables:
            # 去重（根據 image_path）
            seen_paths = set()
            unique_tables = []
            for table in matched_tables:
                img_path = table.get('image_path', '')
                if img_path and img_path not in seen_paths:
                    seen_paths.add(img_path)
                    unique_tables.append(table)

            state["matched_table_images"] = unique_tables
            print(f"   🎉 總共匹配到 {len(unique_tables)} 個表格圖片")
            print(f"      - metadata 匹配: {metadata_match_count} 個")
            print(f"      - 相似度匹配: {similarity_match_count} 個")
        else:
            print(f"   ℹ️  檢索結果中無表格內容或未匹配到表格")

    except Exception as e:
        print(f"   ⚠️  表格匹配失敗: {e}")
        import traceback
        traceback.print_exc()

    return state

async def retrieve_public_rag_node(state: RetrievalState, config: Optional[RunnableConfig] = None) -> RetrievalState:
    """衛教園地檢索節點"""
    query = state["query"]
    main_question = state["main_question"]
    use_clue_extraction = state["use_clue_extraction"]
    user_id = state["user_id"]

    # 從 config 中獲取 store (非序列化對象)
    store = None
    if config and "configurable" in config:
        store = config["configurable"].get("store")

    loop = asyncio.get_running_loop()

    try:
        vectorstore = await loop.run_in_executor(
            None, load_existing_vectordb, DB_CONNECTION_STRING, "public_health_information_of_education_sites"
        )

        if vectorstore:
            # 使用配置中的檢索數量
            from core.config import RETRIEVAL_CONFIG
            k_value = RETRIEVAL_CONFIG.get("public_rag_k", 3)
            results_with_scores = search_vectordb_with_scores(vectorstore, query, k=k_value)

            if results_with_scores:
                # 線索提取
                if use_clue_extraction and store:
                    try:
                        knowledge, _, original_docs_dict = await process_retrieval_with_clue_extraction(
                            sub_question=query,
                            documents_with_scores=results_with_scores,
                            main_question=main_question,
                            store=store,
                            user_id=user_id
                        )
                        state["knowledge"] = knowledge
                        state["original_docs_dict"] = original_docs_dict
                        print("✅ 衛教園地線索提取成功")
                    except Exception as e:
                        print(f"⚠️ 衛教園地線索提取失敗: {e}，使用原始格式")
                        results, _ = get_structured_pdf_results(
                            results_with_scores,
                            query,
                            show_scores=False,
                            format_type="llm_friendly"
                        )
                        if results and isinstance(results, dict):
                            state["knowledge"] = json.dumps(results, ensure_ascii=False, indent=2)
                else:
                    # 未啟用線索提取
                    results, _ = get_structured_pdf_results(
                        results_with_scores,
                        query,
                        show_scores=False,
                        format_type="llm_friendly"
                    )
                    if results and isinstance(results, dict):
                        state["knowledge"] = json.dumps(results, ensure_ascii=False, indent=2)

                # 提取來源
                state["original_sources"] = extract_sources_from_knowledge(state["knowledge"])

    except Exception as e:
        print(f"⚠️ 衛教園地檢索失敗: {e}")
        state["knowledge"] = ""

    return state


async def check_procedure_node(state: RetrievalState) -> RetrievalState:
    """檢查是否為醫療程序"""
    query = state["query"]

    try:
        msg = [
            SystemMessage(content=MEDICAL_PROCEDURE_CHECK_PROMPT),
            HumanMessage(content=f"問題：{query}")
        ]
        resp = await llm.ainvoke(msg)
        is_procedure = remove_think_tags(resp.content.strip()).lower() == "true"
        state["is_procedure"] = is_procedure
        print(f"🔧 [CHECK] 是否醫療程序: {is_procedure}")
    except:
        state["is_procedure"] = False

    return state


def route_after_procedure_check(state: RetrievalState) -> Literal["procedure", "none"]:
    """醫療程序檢查後的路由"""
    if state["is_procedure"]:
        print("🔀 [ROUTE] 是醫療程序 → 程序檢索")
        return "procedure"
    else:
        print("🔀 [ROUTE] 非醫療程序 → 結束檢索")
        return "none"


async def retrieve_procedure_node(state: RetrievalState) -> RetrievalState:
    """醫療程序檢索節點 - 使用 medical_kb_jsonl 資料源"""
    query = state["query"]

    print(f"🔍 [PROCEDURE] 檢索醫療程序: {query}")

    try:
        # 使用 medical_kb_jsonl 資料源檢索
        from medical_knowledge_fetcher import get_final_answer_from_query_async

        knowledge = (await get_final_answer_from_query_async(query)).strip()

        state["knowledge"] = knowledge
        state["original_sources"] = extract_sources_from_knowledge(knowledge)

        # 提取原始文檔內容
        if not state["original_docs_dict"]:
            if "**參考依據**" in knowledge or "《" in knowledge:
                for source in state["original_sources"]:
                    pattern = rf'《{re.escape(source)}》(.*?)(?=《|來源：|---|\Z)'
                    matches = re.findall(pattern, knowledge, re.DOTALL)
                    if matches:
                        all_content = []
                        seen_content = set()
                        for match_content in matches:
                            content = match_content.strip()
                            if content and content not in seen_content:
                                all_content.append(content)
                                seen_content.add(content)

                        if all_content:
                            state["original_docs_dict"][source] = '\n'.join(all_content)

    except Exception as e:
        print(f"⚠️ 醫療程序檢索失敗: {e}")
        import traceback
        traceback.print_exc()
        state["knowledge"] = ""

    return state


async def no_retrieval_node(state: RetrievalState) -> RetrievalState:
    """無檢索節點：返回空結果"""
    print("🔚 [END] 非醫療相關問題，不進行檢索")
    return state


def extract_sources_from_retrieval_summaries(pdf_summary: str, rag_summary: str, knowledge: str) -> List[str]:
    """從檢索摘要和生成的知識文本中提取來源"""
    sources_from_retrieval = []

    # 從 pdf_summary 提取
    if pdf_summary:
        try:
            pdf_data = json.loads(pdf_summary)
            if isinstance(pdf_data, dict) and 'documents' in pdf_data:
                for doc in pdf_data['documents']:
                    if 'source' in doc and 'pdf_file' in doc['source']:
                        sources_from_retrieval.append(doc['source']['pdf_file'])
        except:
            sources_from_pdf = extract_sources_from_knowledge(pdf_summary)
            sources_from_retrieval.extend(sources_from_pdf)

    # 從 rag_summary 提取
    if rag_summary:
        try:
            rag_data = json.loads(rag_summary)
            if isinstance(rag_data, dict) and 'documents' in rag_data:
                for doc in rag_data['documents']:
                    if 'source' in doc and 'reference' in doc['source']:
                        sources_from_retrieval.append(doc['source']['reference'])
        except:
            sources_from_rag = extract_sources_from_knowledge(rag_summary)
            sources_from_retrieval.extend(sources_from_rag)

    # 從生成的 knowledge 文本中提取
    sources_from_text = extract_sources_from_knowledge(knowledge)

    # 合併並去重
    return list(set(sources_from_retrieval + sources_from_text))


# ==================== 構建檢索圖 ====================

def create_retrieval_graph() -> StateGraph:
    """
    創建檢索流程圖
    🆕 新版本：使用多資料源架構
    """
    workflow = StateGraph(RetrievalState)

    # 添加節點
    workflow.add_node("initialize", initialize_retrieval_node)
    workflow.add_node("multi_source", retrieve_multi_source_node)  # 🆕 新的多資料源節點
    workflow.add_node("check_procedure", check_procedure_node)
    workflow.add_node("retrieve_procedure", retrieve_procedure_node)
    workflow.add_node("no_retrieval", no_retrieval_node)

    # 向後兼容：保留舊節點（但不再使用）
    # workflow.add_node("retrieve_medical_kb", retrieve_medical_kb_node)
    # workflow.add_node("retrieve_public_rag", retrieve_public_rag_node)

    # 設置入口點
    workflow.set_entry_point("initialize")

    # 🆕 新的條件邊：使用多資料源架構
    workflow.add_conditional_edges(
        "initialize",
        route_retrieval_strategy,
        {
            "multi_source": "multi_source",      # 🆕 醫療問題 → 多資料源檢索
            "check_procedure": "check_procedure"  # 非醫療 → 檢查程序
        }
    )

    # 多資料源檢索後結束
    workflow.add_edge("multi_source", END)

    # 程序檢查後的條件路由
    workflow.add_conditional_edges(
        "check_procedure",
        route_after_procedure_check,
        {
            "procedure": "retrieve_procedure",
            "none": "no_retrieval"
        }
    )

    # 程序檢索後結束
    workflow.add_edge("retrieve_procedure", END)

    # 無檢索後結束
    workflow.add_edge("no_retrieval", END)

    return workflow.compile()


# 創建全局檢索圖實例
_retrieval_graph = create_retrieval_graph()


# ==================== 主要檢索函數 ====================

@observe(as_type="retriever")
async def retrieve_single_query(
    query: str,
    main_question: str = None,
    use_clue_extraction: bool = None,
    store = None,
    user_id: str = "default",
    datasource_ids: Optional[List[str]] = None,  # 指定要使用的資料源 ID 列表
    _langfuse_handler = None,  # 保留以兼容舊版調用（目前未使用）
    sub_question_index: int = None,  # 🆕 子問題編號（用於追蹤）
    is_main_question: bool = False  # 🔒 標記是否為主問題（主問題不快取，避免個人信息泄露）
) -> tuple[str, list[str], dict]:
    """
    單一查詢檢索（使用 LangGraph 多資料源架構）
    可選擇性地使用線索提取來優化檢索結果

    Args:
        query: 查詢問題(可能是子問題)
        main_question: 用戶的主問題(用於判斷相關性,預設與query相同)
        use_clue_extraction: 是否使用線索提取（None=使用配置檔設定）
        store: LangGraph BaseStore 用於快取（可選）
        user_id: 用戶ID（用於快取命名空間）
        datasource_ids: 指定要使用的資料源 ID 列表，如 ["medical_kb_jsonl", "public_health"]
                       None = 自動根據問題類型選擇
        langfuse_handler: Langfuse CallbackHandler（保留以兼容）
        sub_question_index: 子問題編號（用於追蹤）

    Returns:
        (knowledge_text, source_list, used_sources_dict, matched_tables)

    範例:
        # 自動選擇資料源
        knowledge, sources, docs, tables = await retrieve_single_query("糖尿病的症狀")

        # 指定使用特定資料源
        knowledge, sources, docs, tables = await retrieve_single_query(
            "糖尿病的症狀",
            datasource_ids=["medical_kb_jsonl", "diabetes_education"]
        )

        # 僅使用衛教園地
        knowledge, sources, docs, tables = await retrieve_single_query(
            "高血壓預防",
            datasource_ids=["public_health"]
        )
    """

    # 🆕 使用 @observe 裝飾器後，自動創建 observation
    # 手動設置 name 和 metadata
    if LANGFUSE_AVAILABLE and get_langfuse_client:
        span_name = f"sub_question_{sub_question_index}_retrieval" if sub_question_index else "single_query_retrieval"
        try:
            get_langfuse_client().update_current_span(
                name=span_name,
                metadata={
                    "query": query,
                    "main_question": main_question,
                    "datasource_ids": datasource_ids,
                    "sub_question_index": sub_question_index
                }
            )
        except Exception as e:
            print(f"⚠️ 更新 Langfuse observation 失敗: {e}")

    # 🆕 Step 1: 嘗試從 Retrieval Cache 獲取
    # 🔧 局部導入以避免循環導入
    from graph.graph_nodes import get_cache_manager

    cache_manager = get_cache_manager()
    # cache_manager.print_stats()

    # 🔒 主問題不使用 Retrieval Cache（避免個人信息泄露）
    if not is_main_question and cache_manager:
        cached_result = cache_manager.get_retrieval_cache(
            query,
            datasource_ids=datasource_ids
        )

        if cached_result:
            print(f"✅ Retrieval Cache Hit: {query[:50]}...")

            # 🆕 更新 Langfuse metadata（標記為快取命中）
            if LANGFUSE_AVAILABLE and get_langfuse_client:
                try:
                    get_langfuse_client().update_current_span(
                        metadata={
                            "cache_hit": True,
                            "sources_count": len(cached_result[1]) if len(cached_result) > 1 else 0,
                            "has_knowledge": bool(cached_result[0]) if cached_result else False
                        }
                    )
                except Exception as e:
                    print(f"⚠️ 更新 Langfuse observation metadata 失敗: {e}")

            # 直接返回快取結果 (knowledge, sources, docs_dict, tables)
            return cached_result
    elif is_main_question:
        print(f"🔒 主問題跳過 Retrieval Cache（隱私保護）: {query[:50]}...")

    # 構建初始狀態 (注意: store 不能放在狀態中,因為無法序列化)
    initial_state: RetrievalState = {
        "query": query,
        "main_question": main_question,
        "use_clue_extraction": use_clue_extraction,
        "user_id": user_id or "default",
        "datasource_ids": datasource_ids,
        # 以下字段將由節點填充
        "actual_query": "",
        "matched_disease": "",
        "is_medical": False,
        "is_procedure": False,
        "retrieval_strategy": "none",
        "knowledge": "",
        "original_sources": [],
        "original_docs_dict": {},
        "matched_table_images": [],  # 🆕 表格圖片匹配結果初始化
        "retrieval_summaries": {},  # 🆕 改為字典
        "json_results": {},
        "pdf_results": {}
    }

    # 構建配置 (通過 config 傳遞不可序列化的對象,如 store)
    run_config = {
        "configurable": {
            "store": store
        }
    }

    # 執行檢索圖
    final_state = await _retrieval_graph.ainvoke(initial_state, run_config)

    # 🆕 Step 2: 儲存到 Retrieval Cache
    result = (
        final_state["knowledge"],
        final_state["original_sources"],
        final_state["original_docs_dict"],
        final_state.get("matched_table_images", [])  # 🆕 返回表格圖片匹配結果
    )

    # 🔒 主問題不寫入 Retrieval Cache（避免個人信息泄露）
    if not is_main_question and cache_manager:
        cache_manager.set_retrieval_cache(
            query,
            result,
            datasource_ids=datasource_ids
        )

    # 🆕 記錄檢索結果統計到 Langfuse metadata（@observe 會自動記錄 return）
    if LANGFUSE_AVAILABLE and get_langfuse_client:
        try:
            get_langfuse_client().update_current_span(
                metadata={
                    "cache_hit": False,  # 🆕 標記為快取未命中（執行了檢索）
                    "sources_count": len(final_state["original_sources"]),
                    "sources": final_state["original_sources"],
                    "has_knowledge": bool(final_state["knowledge"]),
                    "knowledge_length": len(final_state["knowledge"]) if final_state["knowledge"] else 0,
                    "matched_tables_count": len(final_state.get("matched_table_images", []))
                }
            )
        except Exception as e:
            print(f"⚠️ 更新 Langfuse observation metadata 失敗: {e}")

    # 返回結果（包含表格圖片匹配結果）
    return result

# ==================== 查詢處理函數 ====================

async def expand_entity_to_query(user_query: str, entity: str) -> str:
    """實體擴展為查詢"""
    prompt = ENTITY_QUERY_EXPANSION_PROMPT.format(user_query=user_query, entity=entity)
    try:
        response = await llm.ainvoke(prompt)
        expanded_query = response.content.strip()
        print(f"🔍 實體擴展: '{entity}' → '{expanded_query}'")
        return expanded_query
    except Exception as e:
        print(f"⚠️ 實體擴展失敗: {e}，使用原始實體")
        return entity


async def check_query_complexity(user_query: str, history_context: str = "") -> dict:
    """檢查查詢複雜度，回傳標準化結果"""
    # 使用正確的 Pydantic 模型解析器
    parser = PydanticOutputParser(pydantic_object=QueryComplexityResult)
    
    # 在 prompt 末尾加入格式指示（強烈建議）
    full_prompt = (
        QUERY_COMPLEXITY_CHECK_PROMPT_V2
        + "\n\n{format_instructions}"
    ).format(
        user_query=user_query,
        history_context=history_context,
        format_instructions=parser.get_format_instructions()
    )

    try:
        response = await llm.ainvoke(full_prompt)
        result_text = response.content.strip()
        # 嘗試用 Pydantic 解析（自動處理 JSON、驗證、轉型）
        try:
            parsed: QueryComplexityResult = parser.parse(result_text)
            return {
                "is_complex": parsed.is_complex,
                "search_strategy": parsed.search_strategy,
                "extracted_entities": parsed.extracted_entities,
                "reasoning": parsed.reasoning,
                "analysis": result_text  # 原始文字備查
            }
        except Exception as parse_err:
            print(f"⚠️ Pydantic 解析失敗: {parse_err}")
            # 回退：嘗試手動 JSON 解析（保守做法）
            try:
                raw_dict = json.loads(result_text.strip('` \n'))
                return {
                    "is_complex": bool(raw_dict.get("is_complex", False)),
                    "search_strategy": raw_dict.get("search_strategy", "simple"),
                    "extracted_entities": raw_dict.get("extracted_entities", []),
                    "reasoning": raw_dict.get("reasoning", "無法解析 reasoning"),
                    "analysis": result_text
                }
            except Exception as json_err:
                print(f"⚠️ JSON 回退也失敗: {json_err}")
                # 最終回退：一律當簡單查詢
                return {
                    "is_complex": False,
                    "search_strategy": "simple",
                    "extracted_entities": [],
                    "reasoning": "LLM 回應無法解析，預設使用 simple 策略",
                    "analysis": result_text
                }

    except Exception as e:
        print(f"⚠️ 查詢複雜度檢查異常: {e}")
        return {
            "is_complex": False,
            "search_strategy": "simple",
            "extracted_entities": [],
            "reasoning": f"系統錯誤，預設 simple: {str(e)}",
            "analysis": str(e)
        }

async def generate_sub_questions(user_query: str, missing_info: str, reasoning: str = "") -> list[str]:
    """
    生成子問題用於多次檢索

    Args:
        user_query: 用戶的原始問題
        missing_info: 缺失的資訊描述
        reasoning: 問題意圖分析（來自 QUESTION_TYPE_CHECK_PROMPT 的 reasoning 欄位）

    Returns:
        子問題列表
    """
    try:
        # 如果沒有提供 reasoning，使用預設值
        if not reasoning:
            reasoning = "無問題意圖分析"

        prompt_text = SUB_QUESTIONS_GENERATION_PROMPT.format(
            user_query=user_query,
            missing_info=missing_info,
            reasoning=reasoning
        )
        response = await llm.ainvoke(prompt_text)

        # 解析 JSON 響應
        content = remove_think_tags(response.content.strip())

        # 移除可能的 markdown 代碼塊標記
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        # 解析 JSON
        parsed = json.loads(content)
        sub_questions = parsed.get("sub_questions", [])

        if not sub_questions:
            # 如果解析失敗，回退到簡單拆分
            print(f"⚠️ 未能從 JSON 中提取子問題，使用原查詢")
            return [f"{user_query} {missing_info}"]

        print(f"📝 生成了 {len(sub_questions)} 個子問題:")
        for i, q in enumerate(sub_questions, 1):
            print(f"   {i}. {q}")

        return sub_questions

    except json.JSONDecodeError as e:
        print(f"⚠️ JSON 解析失敗: {e}，使用原查詢")
        return [f"{user_query} {missing_info}"]
    except Exception as e:
        print(f"⚠️ 子問題生成失敗: {e}，使用原查詢")
        return [f"{user_query} {missing_info}"]
