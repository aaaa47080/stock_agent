"""
Graph 節點函數模組（優化版）
包含所有 LangGraph 節點的實現
"""

from typing import Dict, List, Tuple, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
import opencc
import asyncio
import os
import re
import json
import traceback

# 導入配置
from core.config import llm, mem0_config, remove_think_tags, WORKFLOW_LIMITS
from core.prompt_config import (
    MEMORY_SEARCH_LIMIT, QUESTION_TYPE_CHECK_PROMPT,
    ANSWER_VALIDATION_PROMPT, ANSWER_REGENERATE_PROMPT, GREET_PROMPTTEMPLATE,
    SHORT_TERM_MEMORY_CHECK_PROMPT, QUERY_PLANNING_PROMPT
)
from utils.prompt_function import (
    get_query_classification_prompt, get_rag_response_prompt,
    get_rag_response_prompt_with_history
)
from core.dataclass import ValidationResult, QueryPlanningResult
from mem0 import Memory
from utils.response_utils import (
    parse_memory_results, post_process_response,
    smart_truncate_knowledge
)
from retrieval.retrieval_utils import (
    generate_sub_questions, retrieve_single_query,
    merge_documents_intelligently, is_reference_citation, is_figure_description,
    get_paragraph_signature
)
from graph.graph_routing import FullState
from langgraph.store.memory import InMemoryStore
from core.config import RETRIEVAL_CONFIG, TOOLS_CONFIG
from tools_config import get_tool
from retrieval.image_retriever import retrieve_relevant_images, get_image_mapper

# 🆕 Langfuse 3.0 匯入 (可選依賴)
try:
    from langfuse import observe, get_client as get_langfuse_client
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    get_langfuse_client = None
    # 創建空的裝飾器以避免錯誤
    def observe(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])
    print("ℹ️ Langfuse 未安裝，子問題追蹤功能將被停用")

# ===== 初始化 =====
converter = opencc.OpenCC('s2tw.json')
memory_client = Memory.from_config(mem0_config)

# 🆕 初始化快取管理器（全局單例）
from utils.cache_manager import get_cache_manager

# 初始化 InMemoryStore
clue_store = None
if RETRIEVAL_CONFIG.get('clue_cache_enabled', True):
    clue_store = InMemoryStore()
    print("✅ InMemoryStore 已初始化（用於線索快取）")
else:
    print("⚠️ InMemoryStore 未啟用（clue_cache_enabled=False）")


# ===== 輔助函數 =====

class LogHelper:
    """統一的日誌輸出輔助類"""
    
    @staticmethod
    def section(title: str, char: str = "=", width: int = 80):
        print(f"\n{char * width}")
        print(f"{title}")
        print(f"{char * width}")
    
    @staticmethod
    def subsection(title: str, char: str = "-", width: int = 80):
        print(f"{title}")
        print(f"{char * width}")
    
    @staticmethod
    def iteration_info(current: int, max_count: int, action: str):
        print(f"🔍 {action} - 當前迭代次數: {current}/{max_count}")


def is_short_term_memory_enabled(state: FullState) -> bool:
    """檢查短期記憶是否啟用"""
    from core.config import SHORT_TERM_MEMORY_CONFIG
    if hasattr(state, 'enable_short_term_memory') and state.enable_short_term_memory is not None:
        return state.enable_short_term_memory
    return SHORT_TERM_MEMORY_CONFIG.get('enabled', True)


def build_conversation_context(messages: List, include_current: bool = False) -> str:
    """構建對話上下文字串"""
    context_parts = []
    msg_list = messages if include_current else messages[:-1] if messages else []
    
    for msg in msg_list:
        if isinstance(msg, HumanMessage):
            context_parts.append(f"用戶: {msg.content}")
        elif isinstance(msg, AIMessage):
            context_parts.append(f"助手: {msg.content}")
    
    return "\n".join(context_parts)


def merge_document_content_smart(existing_content: str, new_content: str) -> str:
    """智能合併文檔內容，避免重複的QA對"""
    if new_content in existing_content:
        return existing_content

    # 提取問題+答案組合作為去重標識
    existing_qa_pairs = set()
    for match in re.finditer(r'問題:(.*?)答案:(.*?)(?=關鍵字:|參考:|問題:|$)', existing_content, re.DOTALL):
        existing_qa_pairs.add((match.group(1).strip(), match.group(2).strip()))

    if not existing_qa_pairs:
        return existing_content + "\n\n" + new_content

    # 過濾新內容中的重複QA對
    new_paragraphs = []
    for para in new_content.split('\n'):
        para = para.strip()
        if not para:
            continue

        qa_match = re.search(r'問題:(.*?)答案:(.*?)(?=關鍵字:|參考:|問題:|$)', para, re.DOTALL)
        if qa_match:
            qa_key = (qa_match.group(1).strip(), qa_match.group(2).strip())
            if qa_key not in existing_qa_pairs:
                existing_qa_pairs.add(qa_key)
                new_paragraphs.append(para)
        else:
            new_paragraphs.append(para)

    return existing_content + "\n\n" + "\n".join(new_paragraphs) if new_paragraphs else existing_content


def merge_used_sources(combined: dict, new_dict: dict) -> dict:
    """合併使用的參考文獻字典"""
    for source, doc_info in new_dict.items():
        content = doc_info.get('content', '') if isinstance(doc_info, dict) else doc_info
        score = doc_info.get('score', 999.0) if isinstance(doc_info, dict) else 999.0
        
        if source not in combined:
            combined[source] = {'content': content, 'score': score}
        else:
            existing = combined[source]
            existing_content = existing.get('content', '') if isinstance(existing, dict) else existing
            existing_score = existing.get('score', 999.0) if isinstance(existing, dict) else 999.0
            
            if content:
                combined[source] = {
                    'content': merge_document_content_smart(existing_content, content),
                    'score': min(existing_score, score)
                }
    return combined


async def stream_llm_response(message_stream) -> str:
    """流式接收 LLM 回應"""
    full_response = ""
    async for chunk in message_stream:
        if hasattr(chunk, 'content'):
            full_response += chunk.content
    return full_response


def extract_disease_name(user_message: str) -> str:
    """提取疾病名稱"""
    from core.prompt_config import DISEASE_EXTRACTION_PROMPT
    try:
        response = llm.invoke(DISEASE_EXTRACTION_PROMPT.format(user_message=user_message))
        disease_name = response.content.strip()
        return disease_name if disease_name != "未知疾病" else ""
    except:
        return ""


# ===== 檢索相關輔助函數 =====

@observe(name="retrieve_multiple_queries")
async def retrieve_multiple_queries(
    queries: List[str],
    main_question: str,
    user_id: str,
    datasource_ids: Optional[List[str]] = None,
    existing_sources: Optional[dict] = None
) -> Tuple[str, dict, List]:
    """並行檢索多個查詢並合併結果"""

    # 🆕 使用 @observe 裝飾器後，會自動創建 span
    # 手動更新 metadata 以提供更多上下文
    if LANGFUSE_AVAILABLE and get_langfuse_client:
        try:
            get_langfuse_client().update_current_trace(
                metadata={
                    "total_sub_questions": len(queries),
                    "main_question": main_question,
                    "sub_questions": queries
                }
            )
        except Exception as e:
            print(f"⚠️ 更新 Langfuse trace metadata 失敗: {e}")

    tasks = [
        retrieve_single_query(
            q, main_question=main_question, store=clue_store,
            user_id=user_id, datasource_ids=datasource_ids,
            sub_question_index=idx + 1,  # 🆕 傳遞子問題編號
            is_main_question=(q == main_question)  # 🔒 標記主問題（主問題不快取）
        )
        for idx, q in enumerate(queries)
    ]
    results = await asyncio.gather(*tasks)

    all_knowledge_parts = []
    combined_sources = existing_sources.copy() if existing_sources else {}
    combined_tables = []

    # 🆕 統計資訊
    total_sources = 0
    successful_retrievals = 0

    for idx, (knowledge, sources, used_dict, matched_tables) in enumerate(results):
        if knowledge:
            all_knowledge_parts.append(knowledge)
            combined_sources = merge_used_sources(combined_sources, used_dict)
            if matched_tables:
                combined_tables.extend(matched_tables)
            successful_retrievals += 1
            total_sources += len(sources)
        else:
            print(f"   ⚠️ 子問題 {idx+1} 無線索: {queries[idx]}")
            all_knowledge_parts.append(f"[子問題：{queries[idx]}]\n無線索")

    # 🆕 記錄整體檢索統計（@observe 會自動記錄 return，這裡額外記錄統計）
    if LANGFUSE_AVAILABLE and get_langfuse_client:
        try:
            get_langfuse_client().update_current_span(
                metadata={
                    "successful_retrievals": successful_retrievals,
                    "total_sub_questions": len(queries),
                    "total_sources_retrieved": total_sources,
                    "total_unique_sources": len(combined_sources)
                }
            )
        except Exception as e:
            print(f"⚠️ 更新 Langfuse observation metadata 失敗: {e}")

    combined_knowledge = "\n\n---\n\n".join(all_knowledge_parts) if all_knowledge_parts else ""
    return combined_knowledge, combined_sources, combined_tables


def ensure_main_query_first(sub_questions: List[str], main_query: str) -> List[str]:
    """確保主問題在子問題列表的第一位"""
    if main_query not in sub_questions:
        sub_questions.insert(0, main_query)
        print(f"   ✅ 已將原始主問題加入子問題列表第一位")
    return sub_questions


# ===== 參考文獻處理 =====




def rebuild_references_from_used_sources(used_sources_dict: dict) -> str:
    """重建參考文獻 (僅保留有效的 PDF 或網頁來源)"""
    if not used_sources_dict:
        return ""

    # 標準化文件名並收集內容
    normalized_docs = {}

    for doc_name, doc_info in used_sources_dict.items():
        clean_name = doc_name.strip() if doc_name else ""
        
        # 🆕 過濾無效或內部的來源名稱
        if not clean_name or clean_name.lower() in ['unknown', 'educational_vlm_analysis', 'none', 'async_pipeline_v2']:
            continue
            
        # 🆕 確保只保留 PDF 或 URL (或您定義的其他有效來源)
        is_url = clean_name.startswith(('http://', 'https://'))
        is_pdf = clean_name.lower().endswith('.pdf')
        
        if not (is_url or is_pdf):
            # 如果不是 PDF 也不是 URL，檢查是否為我們已知的 PDF 來源格式 (無副檔名但符合 PDF 命名規律)
            if not any(char.isdigit() for char in clean_name) and len(clean_name) < 5:
                continue

        clean_name = clean_name.replace('《', '').replace('》', '').strip()
        if not (is_url or is_pdf):
            clean_name = os.path.basename(clean_name)

        content = doc_info.get('content', '') if isinstance(doc_info, dict) else doc_info
        score = doc_info.get('score', 999.0) if isinstance(doc_info, dict) else 999.0

        if not content:
            continue

        if clean_name in normalized_docs:
            existing = normalized_docs[clean_name]
            merged_content = merge_documents_intelligently(clean_name, existing['content'], content)
            normalized_docs[clean_name] = {'content': merged_content, 'score': min(existing['score'], score)}
        else:
            normalized_docs[clean_name] = {
                'content': merge_documents_intelligently(clean_name, "", content),
                'score': score
            }

    if not normalized_docs:
        return ""

    # 按分數排序並格式化輸出
    sorted_docs = sorted(normalized_docs.items(), key=lambda x: x[1]['score'])
    output = ["**參考依據**\n"]

    # 🆕 全局段落去重（跨文檔）
    global_seen_signatures = set()
    has_valid_content = False  # 標記是否有有效內容

    for doc_name, doc_data in sorted_docs:
        content = doc_data['content']
        if not content.strip():
            continue
        
        # 暫存當前文檔的顯示內容
        doc_display_output = []
        
        # 分離 QA 和 PDF 部分
        if '【原始PDF段落】' in content:
            parts = content.split('【原始PDF段落】', 1)
            qa_part, pdf_part = parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
        else:
            qa_part = content if '問題:' in content and '答案:' in content else ""
            pdf_part = "" if qa_part else content
        
        # 處理 QA 部分
        if qa_part:
            idx = 1
            for line in qa_part.split('\n'):
                line = line.strip()
                if line.startswith('問題:'):
                    doc_display_output.append(f"{idx}. {line}")
                    idx += 1
                elif line.startswith('答案:'):
                    doc_display_output.append(f"   {line}\n")
        
        # 處理 PDF 部分
        if pdf_part:
            # 判斷是否為 CDC 內容
            is_cdc = '標題：' in pdf_part or '發布日期：' in pdf_part or 'CDC 官網即時搜尋' in pdf_part

            # 只對非 CDC 的 PDF 內容移除 <table> 標籤(因為已經顯示圖片)
            if not is_cdc:
                pdf_part = re.sub(r'<table>.*?</table>', '', pdf_part, flags=re.DOTALL | re.IGNORECASE)

            pdf_part = pdf_part.strip()

            if pdf_part:  # 只有在移除 table 後還有內容時才輸出
                pdf_paragraphs_to_output = []

                if is_cdc:
                    pdf_paragraphs_to_output.append(pdf_part.strip())
                else:
                    # 先按段落分割，再進一步處理單行內容
                    paragraphs = pdf_part.split('\n\n')
                    for para in paragraphs:
                        para = para.strip()

                        # 對於可能跨行的內容，先合併成單行處理
                        para = para.replace('\n', ' ').strip()

                        # 🆕 預處理：移除 [來源文件:...] 標籤
                        para = re.sub(r'\[來源文件:.*?\]', '', para).strip()

                        # 🆕 句首清理：移除開頭的標點符號（如因切割導致的逗號開頭）
                        para = re.sub(r'^[，、：；,:]+', '', para).strip()

                        # 🆕 過濾：移除明顯的頁眉/頁腳/版權聲明/目錄
                        # 增加對目錄特徵的識別 (目錄, ...., 壹、貳、參、)
                        is_toc = "目錄" in para or ".........." in para or (re.search(r'[壹貳參肆伍陸柒捌]、', para) and re.search(r'\.\.\.', para))
                        
                        if any(kw in para for kw in ["本著作非經著作權人同意", "長庚醫療財團法人", "http://", "編印", "著作權人"]) or is_toc:
                            # 進一步檢查是否為短雜訊行
                            if len(para) < 100 or "http" in para or "cm" in para or is_toc:
                                continue

                        if len(para) < 10 or ('問題:' in para and '答案:' in para):
                            continue

                        # 🆕 跳過引用文獻和圖片描述
                        if is_reference_citation(para) or is_figure_description(para):
                            continue

                        # 🆕 全局去重檢查
                        sig = get_paragraph_signature(para)
                        if sig in global_seen_signatures:
                            continue
                        global_seen_signatures.add(sig)

                        # 🆕 提取所有完整句子 (以標點結尾，包含後續括號)
                        # 規則：匹配非標點字元 + 標點符號 + 選用的閉合符號
                        sentence_pattern = r'[^。！？!?\.]+[。！？!?\.]+[」』》）\)]*'
                        complete_sentences = re.findall(sentence_pattern, para)
                        
                        if not complete_sentences:
                            continue
                        
                        # 過濾掉可能是小數點誤判或過短的句子
                        valid_sentences = []
                        for s in complete_sentences:
                            s = s.strip()
                            # 再次排除英文句號作為小數點的殘留
                            if s.endswith('.') and re.search(r'\d\.$', s):
                                continue
                            if len(s) > 5:
                                valid_sentences.append(s)

                        if not valid_sentences:
                            continue

                        # 組合所有完整句子
                        para = " ".join(valid_sentences)

                        # 再次檢查長度，確保內容具有實質意義
                        if len(para) > 15:
                            pdf_paragraphs_to_output.append(para)

                # 只有當有段落要輸出時才添加標題
                if pdf_paragraphs_to_output:
                    doc_display_output.extend(["─" * 80, "【原始PDF段落】\n"])
                    for para in pdf_paragraphs_to_output:
                        doc_display_output.extend([para, ""])

        # 重要：只有當 doc_display_output 有內容時，才輸出文件標題
        if doc_display_output:
            has_valid_content = True
            output.append(f"《{doc_name}》")
            output.extend(doc_display_output)
            output.append("─" * 80)
            output.append("")

    # 如果沒有任何有效內容，直接返回空字串
    if not has_valid_content:
        return ""

    # 🆕 在參考依據最後加上聯絡提示（不額外加分隔線，使用上一個文件的分隔線）
    if output:  # 確保有內容才加入聯絡提示
        output.extend(["💡 如有相關問題，請洽院區感管護師", ""])

    return "\n".join(output)


# ===== 表格處理 =====

def extract_tables_from_metadata(original_docs_dict: dict) -> List[dict]:
    """從 metadata 中提取表格圖片"""
    from core.config import EXTRACTED_TABLES_DIR
    tables = []

    print(f"\n🔍 [DEBUG] extract_tables_from_metadata: 檢查 {len(original_docs_dict)} 個文檔")

    for doc_name, doc_info in original_docs_dict.items():
        print(f"   📄 doc_name: {doc_name}")
        print(f"      類型: {type(doc_info)}")

        if isinstance(doc_info, dict):
            has_table = doc_info.get('has_table', False)
            table_images = doc_info.get('table_images', [])
            print(f"      has_table: {has_table}")
            print(f"      table_images: {table_images}")

            if doc_info.get('has_table') and doc_info.get('table_images'):
                # 從 doc_name 提取 PDF 名稱（去掉 .pdf 副檔名和頁碼）
                # 例如：「xxx.pdf」或「xxx_pXX」-> 「xxx」
                if '.pdf' in doc_name:
                    pdf_name = doc_name.split('.pdf')[0]
                else:
                    # 處理可能的頁碼格式 xxx_pXX
                    pdf_name = re.sub(r'_p\d+.*$', '', doc_name)

                print(f"      ✅ 提取的 pdf_name: {pdf_name}")

                # 組合完整路徑：EXTRACTED_TABLES_DIR / images / 檔案名稱
                for img_filename in doc_info['table_images']:
                    # 兼容新舊格式：如果是完整路徑，則提取檔案名稱
                    if os.path.sep in img_filename or '/' in img_filename:
                        img_filename = os.path.basename(img_filename)

                    full_path = os.path.join(EXTRACTED_TABLES_DIR, "images", img_filename)
                    print(f"         🔍 檢查路徑: {full_path}")
                    print(f"         存在: {os.path.exists(full_path)}")

                    if os.path.exists(full_path):
                        tables.append({
                            'image_path': full_path,
                            'similarity': 1.0,
                            'source': 'metadata'
                        })
                        print(f"         ✅ 成功添加表格圖片")
                    else:
                        print(f"         ❌ 路徑不存在")

    print(f"\n✅ [DEBUG] extract_tables_from_metadata: 共提取 {len(tables)} 個表格圖片\n")
    return tables


def extract_table_numbers_from_answer(answer: str) -> set:
    """從回答中提取表格編號"""
    table_numbers = set()
    chinese_to_arabic = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'
    }
    
    patterns = [
        r'表格\s*([0-9一二三四五六七八九十]+)',
        r'表\s*([0-9一二三四五六七八九十]+)',
        r'表\s*([0-9]+[-\s]*[0-9]+)',
        r'附表\s*([0-9一二三四五六七八九十]+)',
    ]
    
    for pattern in patterns:
        for match in re.finditer(pattern, answer):
            num = match.group(1)
            table_numbers.add(num)
            if num in chinese_to_arabic:
                table_numbers.add(chinese_to_arabic[num])
            arabic_to_chinese = {v: k for k, v in chinese_to_arabic.items()}
            if num in arabic_to_chinese:
                table_numbers.add(arabic_to_chinese[num])
    
    # 從 HTML 表格提取
    for html_match in re.finditer(r'<table[^>]*>(.*?)</table>', answer, re.DOTALL | re.IGNORECASE):
        table_content = html_match.group(1)
        caption_match = re.search(r'<caption[^>]*>(.*?)</caption>', table_content, re.IGNORECASE)
        if caption_match:
            table_numbers.add(re.sub(r'<.*?>', '', caption_match.group(1)).strip())
        for th_match in re.findall(r'<th[^>]*>(.*?)</th>', table_content, re.IGNORECASE):
            table_numbers.add(re.sub(r'<.*?>', '', th_match).strip())
    
    return table_numbers


async def match_tables_for_answer(answer: str, docs_dict: dict) -> List[dict]:
    """為回答匹配表格圖片"""
    import sys
    
    has_table_ref = "<table>" in answer or "<TABLE>" in answer or "|" in answer or "表" in answer
    if not has_table_ref:
        return []
    
    try:
        ocr_model_path = os.path.join(os.path.dirname(__file__), 'ocr_model')
        if ocr_model_path not in sys.path:
            sys.path.insert(0, ocr_model_path)
        from retrieval.table_matcher import has_table_format, process_search_result
        
        if not has_table_format(answer):
            return []
        
        print(f"\n🖼️  回答中偵測到表格，嘗試匹配圖片...")
        matched_tables = []
        
        for doc_name, doc_info in docs_dict.items():
            doc_content = doc_info.get('content', '') if isinstance(doc_info, dict) else str(doc_info)
            if has_table_format(doc_content):
                page_match = re.match(r'.*_p(\d+)_', doc_name)
                page_num = int(page_match.group(1)) if page_match else None
                match_result = process_search_result(content=doc_content, source_file=doc_name, page_num=page_num)
                if match_result.get('matched_tables'):
                    matched_tables.extend(match_result['matched_tables'])
        
        # 去重和過濾
        seen = set()
        unique_tables = []
        for t in matched_tables:
            img_path = t.get('image_path', '')
            if img_path and img_path not in seen:
                seen.add(img_path)
                unique_tables.append(t)
        
        filtered = [t for t in unique_tables if t.get('similarity', 0) > 0.3]
        filtered.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        
        if filtered:
            return filtered[:5]
        
        # 後備方案：從 extracted_tables 目錄搜尋
        return await fallback_table_search(answer, docs_dict)
        
    except Exception as e:
        print(f"   ⚠️ 表格匹配失敗: {e}")
        return []


async def fallback_table_search(answer: str, docs_dict: dict) -> List[dict]:
    """後備方案：從 extracted_tables 目錄搜尋表格"""
    import glob
    from core.config import EXTRACTED_TABLES_DIR

    table_numbers = extract_table_numbers_from_answer(answer)
    
    source_files = set()
    for doc_name in docs_dict.keys():
        if '.pdf' in doc_name:
            pdf_name = doc_name.split('.pdf')[0].replace('《', '').replace('》', '')
            source_files.add(pdf_name)
    
    chinese_to_arabic = {
        '一': '1', '二': '2', '三': '3', '四': '4', '五': '5',
        '六': '6', '七': '7', '八': '8', '九': '9', '十': '10'
    }
    
    fallback_tables = []
    for source_file in source_files:
        subdir = os.path.join(EXTRACTED_TABLES_DIR, source_file)
        if not os.path.exists(subdir):
            continue
        
        for jpg_file in glob.glob(os.path.join(subdir, "*_t*.jpg")):
            html_file = jpg_file.replace('.jpg', '.html')
            if not os.path.exists(html_file):
                continue
            
            try:
                filename_match = re.search(r'_t(\d+)\.jpg$', jpg_file)
                filename_table_num = filename_match.group(1) if filename_match else None
                
                with open(html_file, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                
                h2_match = re.search(r'<h2>(.*?)</h2>', html_content)
                header_content = h2_match.group(1) if h2_match else html_content.split('<table>')[0] if '<table>' in html_content else html_content[:200]
                
                # 提取標題中的表格編號
                title_table_nums = set()
                for pattern in [r'表格\s*([0-9一二三四五六七八九十]+)', r'表\s*([0-9一二三四五六七八九十]+)']:
                    for match in re.finditer(pattern, header_content):
                        num = match.group(1)
                        title_table_nums.add(num)
                        if num in chinese_to_arabic:
                            title_table_nums.add(chinese_to_arabic[num])
                
                if filename_table_num:
                    title_table_nums.add(filename_table_num)
                
                # 判斷是否匹配
                is_matched = bool(table_numbers & title_table_nums) if table_numbers else True
                
                if is_matched:
                    fallback_tables.append({
                        'table_title': header_content.strip() or os.path.basename(jpg_file),
                        'table_content': '',
                        'image_path': jpg_file,
                        'similarity': 0.9 if (table_numbers & title_table_nums) else 0.5,
                        'source': 'matching'
                    })
            except Exception as e:
                print(f"         ⚠️ 讀取 {jpg_file} 失敗: {e}")
    
    if fallback_tables:
        fallback_tables.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        return fallback_tables[:5]
    
    return []


def format_table_section(matched_tables: List[dict]) -> str:
    """格式化表格圖片區塊"""
    if not matched_tables:
        return ""
    
    section = "\n\n**📊 相關表格圖片**\n"
    for idx, table_info in enumerate(matched_tables, 1):
        image_path = table_info.get('image_path', '')
        similarity = table_info.get('similarity', 0.0)
        source = table_info.get('source', 'matching')

        # 從 image_path 獲取文件名
        table_file = os.path.basename(image_path) if image_path else '未知檔案'

        # 提取表格標題
        title_match = re.match(r'(.+?)_p(\d+)_t(\d+)', table_file.replace('.jpg', ''))
        if title_match:
            table_title = f"{title_match.group(1)} 第{title_match.group(2)}頁 表格{title_match.group(3)}"
        else:
            table_title = table_file

        if source == 'metadata':
            section += f"\n{idx}. **{table_title}**"
        else:
            section += f"\n{idx}. **{table_title}** (相似度: {similarity:.2%})"

        if image_path:
            section += f"\n   - 圖片: `{table_file}`"
    
    return section


def format_educational_image_section(matched_images: List[dict]) -> str:
    """格式化衛教圖片區塊"""
    if not matched_images:
        return ""
    
    section = "\n\n**🖼️ 相關衛教圖片**\n"
    for idx, img_info in enumerate(matched_images, 1):
        filename = img_info.get('filename', '未知檔案')
        topic = img_info.get('health_topic', '未知主題')
        score = img_info.get('score', 0.0)
        
        section += f"\n{idx}. **{topic}**"
        section += f"\n   - 圖片: `{filename}`"
    
    return section


# ===== 搜尋工具相關 =====

def should_use_cdc_realtime(query: str, query_type: str = "") -> bool:
    """判斷是否需要使用 CDC 即時搜尋"""
    time_keywords = ["最新", "近期", "今年", "本月", "本週", "現在", "目前", "當前"]
    realtime_keywords = ["疫情", "統計", "數據", "趨勢", "通報", "案例數", "病例數"]
    
    has_time = any(kw in query for kw in time_keywords)
    has_realtime = any(kw in query for kw in realtime_keywords)
    is_medical = query_type in ["medical", "disease", "symptom", ""]
    
    return (has_time and is_medical) or has_realtime


def is_regulatory_content(content: str, url: str = "") -> bool:
    """
    判斷內容是否為法規條文類文件（不相關的行政文件）

    Args:
        content: 文件內容
        url: 文件 URL（可選）

    Returns:
        True 表示是法規類文件，應該被過濾掉
    """
    # 檢查 URL 是否為法規網站
    if 'law.moj.gov.tw' in url or 'lawbank.com.tw' in url:
        return True

    # 檢查內容中是否包含大量法規特徵詞彙
    regulatory_keywords = [
        '主管機關：',
        '依本法',
        '第一條',
        '第二條',
        '第三條',
        '應配合及協助辦理',
        '中華民國',
        '總統令',
        '行政院',
    ]

    # 計算法規關鍵詞出現次數
    keyword_count = sum(1 for keyword in regulatory_keywords if keyword in content)

    # 如果出現 3 個以上法規關鍵詞，判定為法規文件
    if keyword_count >= 3:
        return True

    # 檢查是否為條文列舉格式（一、二、三...）
    # 且內容是部門職責而非醫療指引
    if '一、' in content and '二、' in content and '三、' in content:
        # 檢查是否為部門職責列舉
        department_keywords = ['主管機關', '協助辦理', '政策協調', '管制等事項']
        if any(keyword in content for keyword in department_keywords):
            return True

    return False


def extract_search_sources_with_content(realtime_info: str, tool_name: str = "搜尋工具") -> dict:
    """從搜尋工具結果中提取來源 URL 和內容，並過濾法規類文件"""
    sources_dict = {}
    # 修改正則:匹配從《URL》到下一個《或字符串結尾的所有內容
    pattern = r'《([^》]+)》(.*?)(?=\n《|$)'

    for url, content in re.findall(pattern, realtime_info, re.DOTALL):
        url, content = url.strip(), content.strip()
        if url.startswith(('http://', 'https://')) and content:
            # 檢查是否為法規類文件
            if is_regulatory_content(content, url):
                print(f"   [過濾] 已過濾法規類文件: {url[:80]}...")
                continue

            sources_dict[url] = content
            print(f"   [提取] {tool_name} 來源: {url[:80]}... (內容長度: {len(content)} 字元)")
            # 調試輸出前100字元
            if tool_name == "CDC":
                print(f"      內容預覽: {content[:150]}...")

    return sources_dict


def extract_cdc_sources_with_content(realtime_info: str) -> dict:
    """從 CDC 即時搜尋結果中提取來源"""
    return extract_search_sources_with_content(realtime_info, "CDC")


# ===== 節點函數 =====

def extract_current_query(state: FullState):
    """提取當前查詢"""
    current_query = state.messages[-1].content if state.messages else ""
    LogHelper.section(f"❓ 當前問題: {current_query}")
    
    return {
        "current_query": current_query,
        "knowledge": "",
        "query_type": "",
        "memory_summary": "",
        "memory_response": "",
        "memory_source": "",
        "knowledge_retrieval_count": 0,
        "validation_need_supplement_info": "",
        "suggested_sub_questions": [],
        "iteration_count": 0
    }


async def retrieve_memory(state: FullState):
    """從 mem0 檢索記憶（優化版：使用當前問題作為查詢）"""
    from core.config import LONG_TERM_MEMORY_CONFIG

    use_memory = (
        state.enable_long_term_memory
        if hasattr(state, 'enable_long_term_memory') and state.enable_long_term_memory is not None
        else LONG_TERM_MEMORY_CONFIG.get('enabled', False)
    )

    if not use_memory:
        print("⚠️ 長期記憶已停用")
        return {"memory_summary": ""}

    try:
        # 🔧 優化：使用當前問題作為查詢，提高檢索精準度
        query_text = state.current_query if state.current_query else "目前還有的個人病史、健康狀況、生活習慣等相關資訊"

        print("\n" + "="*80)
        print("🔍 【長期記憶檢索】開始")
        print("="*80)
        print(f"📝 查詢內容: {query_text}")
        print(f"👤 用戶 ID: {state.user_id}")
        print(f"🔢 檢索數量限制: {MEMORY_SEARCH_LIMIT}")
        print("-"*80)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: memory_client.search(
                query=query_text,
                user_id=state.user_id,
                limit=MEMORY_SEARCH_LIMIT
            )
        )

        # 🔧 調試：打印原始檢索結果
        print("\n📦 原始檢索結果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("-"*80)

        memory_texts = parse_memory_results(result)
        memory_summary = "\n".join(f"- {m}" for m in memory_texts) if memory_texts else ""

        if memory_texts:
            print(f"\n✅ 成功找到 {len(memory_texts)} 條相關記憶")
            print("="*80)
            print("📋 解析後的記憶列表:")
            print("="*80)
            for i, mem in enumerate(memory_texts, 1):
                print(f"【記憶 #{i}】 {mem}")
            print("="*80)

            print("\n📄 最終 memory_summary:")
            print("-"*80)
            print(memory_summary)
            print("-"*80)
        else:
            print("\nℹ️ 未找到相關的長期記憶")
            print("="*80)

        return {"memory_summary": memory_summary}
    except Exception as e:
        print(f"\n❌ 記憶檢索失敗: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        print("="*80)
        return {"memory_summary": ""}


async def answer_from_memory(state: FullState):
    """檢查當前問題是否需要精確化"""
    if not is_short_term_memory_enabled(state):
        print("⏭️ 短期記憶已停用，跳過問題精確化")
        return {"memory_response": "No_Answer", "memory_source": ""}

    print("🔍 檢查是否需要精確化問題...")

    # 🔧 修正：只保留最近的 3 輪對話（6 條消息），避免過長的對話歷史導致誤判
    # 排除當前問題（最後一條消息），只看之前的對話
    recent_messages = state.messages[-7:-1] if len(state.messages) > 1 else []
    conversation_history = build_conversation_context(recent_messages, include_current=False)

    if state.memory_summary:
        conversation_history += f"\n【個人病史】\n{state.memory_summary}\n"

    prompt = SHORT_TERM_MEMORY_CHECK_PROMPT.format(
        conversation_history=conversation_history or "（目前沒有對話歷史和個人病史）",
        current_query=state.current_query
    )
    
    try:
        messages = [SystemMessage(content=prompt), HumanMessage(content=state.current_query)]
        response = await llm.ainvoke(messages)
        result = remove_think_tags(response.content.strip())

        # 不需要精確化
        if result == "No_Answer":
            return {"memory_response": "No_Answer", "memory_source": ""}

        # 精確化後的問題
        print(f"✅ 問題已精確化: {result}\n")
        return {"current_query": result, "memory_response": "No_Answer", "memory_source": ""}
        
    except Exception as e:
        print(f"⚠️ 問題精確化失敗: {e}")
        return {"memory_response": "No_Answer", "memory_source": ""}




async def planning_node(state: FullState) -> Dict:
    """
    規劃節點：分析問題是否需要分步檢索

    主動判斷問題複雜度,生成流程性的檢索步驟。
    這比在驗證階段被動生成子問題更高效。
    """
    print("\n" + "="*80)
    print("🎯 Planning 階段：分析問題複雜度")
    print("="*80)

    # 構建對話上下文
    conversation_context = ""
    if is_short_term_memory_enabled(state) and state.messages:
        conversation_context = build_conversation_context(state.messages, include_current=False)

    # 🆕 檢查快取（🔒 加入 user_id 防止隱私洩漏）
    cache_manager = get_cache_manager()
    if cache_manager:
        cached_result = cache_manager.get_planning_cache(
            state.current_query,
            conversation_context,
            user_id=state.user_id  # 🔒 隔離不同用戶的快取
        )
        if cached_result:
            print("✅ 使用快取的 Planning 結果")
            return cached_result

    # 調用 LLM 進行規劃
    prompt = QUERY_PLANNING_PROMPT.format(
        user_query=state.current_query,
        conversation_context=conversation_context or "（無對話歷史）"
    )

    try:
        parser = PydanticOutputParser(pydantic_object=QueryPlanningResult)
        chain = llm | parser
        result: QueryPlanningResult = await chain.ainvoke(prompt)

        if result.needs_planning:
            print(f"\n✅ 需要分步檢索")
            print(f"📝 理由: {result.reasoning}")
            print(f"\n📋 檢索計劃（共 {len(result.retrieval_steps)} 步）:")
            for step in result.retrieval_steps:
                print(f"  步驟 {step.step}: {step.query}")
                print(f"    目的: {step.purpose}")
            print()

            output = {
                "planning_result": result.model_dump(),
                "retrieval_steps": [step.model_dump() for step in result.retrieval_steps]
            }
        else:
            print(f"\n⏭️  不需要分步檢索")
            print(f"📝 理由: {result.reasoning}\n")
            output = {
                "planning_result": result.model_dump(),
                "retrieval_steps": []
            }

        # 🆕 儲存到快取（🔒 加入 user_id）
        if cache_manager:
            cache_manager.set_planning_cache(
                state.current_query,
                output,
                conversation_context,
                user_id=state.user_id  # 🔒 隔離不同用戶的快取
            )

        return output

    except Exception as e:
        print(f"⚠️ Planning 失敗，回退到直接檢索: {e}")
        traceback.print_exc()
        fallback_result = {
            "planning_result": {
                "needs_planning": False,
                "reasoning": f"Planning 失敗: {str(e)}",
                "retrieval_steps": []
            },
            "retrieval_steps": []
        }

        # 🆕 也快取失敗結果（避免重複嘗試，🔒 加入 user_id）
        if cache_manager:
            cache_manager.set_planning_cache(
                state.current_query,
                fallback_result,
                conversation_context,
                user_id=state.user_id  # 🔒 隔離不同用戶的快取
            )

        return fallback_result


async def classify_query_type(state: FullState):
    """分類查詢類型"""
    if state.query_type:
        print(f"🎯 使用預設的查詢類型: {state.query_type}\n")
        return {"query_type": state.query_type}
    
    current_query = state.current_query
    context = ""
    
    if is_short_term_memory_enabled(state):
        if state.memory_summary:
            context += f"\n【記憶】\n{state.memory_summary}\n"
        conversation = build_conversation_context(state.messages[:-1] if len(state.messages) > 1 else [])
        if conversation:
            context += f"\n【對話歷史】\n{conversation}"
        
        # 上下文補全
        try:
            from core.prompt_config import CONTEXT_COMPLETION_PROMPT
            if context.strip():
                prompt = CONTEXT_COMPLETION_PROMPT.format(history_context=context, current_query=current_query)
                response = await llm.ainvoke([HumanMessage(content=prompt)])
                data = json.loads(remove_think_tags(response.content.strip()))
                if data.get("needs_completion"):
                    current_query = data.get("completed_query", current_query)
        except Exception as e:
            print(f"⚠️ 上下文補全失敗: {e}")
        
        # 症狀檢測
        try:
            from core.prompt_config import SYMPTOM_EXTRACTION_PROMPT
            prompt = SYMPTOM_EXTRACTION_PROMPT.format(user_query=current_query, history_context=context or "無")
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            data = json.loads(remove_think_tags(response.content.strip()))
            
            if data.get("has_new_symptom") and data.get("current_symptoms") and data.get("historical_symptoms"):
                return {
                    "query_type": "rag_needed",
                    "current_query": f"{current_query}\n[系統註記：用戶之前還提到過：{', '.join(data['historical_symptoms'])}]"
                }
        except Exception as e:
            print(f"⚠️ 症狀檢測失敗: {e}")
    
    # 正常分類
    prompt = get_query_classification_prompt(query=current_query, history_summary=context or "無歷史記錄")
    
    try:
        response = await llm.ainvoke(prompt)
        query_type = remove_think_tags(response.content.strip()).lower()
        valid_types = ["out_of_scope", "short_term", "rag_needed", "greet"]
        query_type = query_type if query_type in valid_types else "rag_needed"
        return {"query_type": query_type, "current_query": current_query}
    except:
        return {"query_type": "rag_needed", "current_query": current_query}


async def retrieve_knowledge(state: FullState):
    """檢檢索知識 - 支援 Planning 多步驟檢索"""
    LogHelper.section(f"🔍 開始知識檢索 - 當前迭代次數: {state.iteration_count}/{WORKFLOW_LIMITS['max_iteration_count']}")

    # 安全檢查
    if state.iteration_count >= WORKFLOW_LIMITS['retrieval_iteration_threshold']:
        print(f"⚠️ 迭代次數已達閾值，跳過檢索")
        return {
            "knowledge": "", "used_sources_dict": {}, "knowledge_retrieval_count": state.knowledge_retrieval_count,
            "iteration_count": state.iteration_count + 1
        }

    current_query = state.current_query
    user_id = state.user_id

    # 🆕 檢索相關衛教圖片（僅當使用者選擇該資料源時執行）
    # 預設情況下（datasource_ids 為 None），我們保持開啟以維持原有功能
    should_retrieve_images = True
    if state.datasource_ids is not None:
        should_retrieve_images = "educational_images" in state.datasource_ids

    educational_images = []
    if should_retrieve_images:
        # 根據使用者選擇的文字資料源，轉換為對應的圖片資料源過濾
        image_mapper = get_image_mapper()
        image_datasource_ids = image_mapper.convert_text_datasources_to_image_datasources(
            state.datasource_ids
        )
        if image_datasource_ids:
            print(f"🖼️  圖片資料源過濾: {image_datasource_ids}")

        educational_images = await retrieve_relevant_images(
            current_query,
            image_datasource_ids=image_datasource_ids
        )
        if educational_images:
            print(f"🖼️  檢索到 {len(educational_images)} 張相關衛教圖片")
        else:
            print("🖼️  未檢索到相關衛教圖片")
    else:
        print("🖼️  衛教圖片檢索已停用")

    # ===== 優先使用 Planning 步驟 =====
    if state.retrieval_steps and len(state.retrieval_steps) > 0:
        print(f"\n🎯 使用 Planning 規劃的檢索步驟（共 {len(state.retrieval_steps)} 步）")

        # 提取所有步驟的查詢
        planned_queries = [step['query'] for step in state.retrieval_steps]

        # 🆕 確保原始主問題也被包含在檢索中
        planned_queries = ensure_main_query_first(planned_queries, current_query)

        # 依序執行多步驟檢索
        combined_knowledge, combined_sources, combined_tables = await retrieve_multiple_queries(
            planned_queries, current_query, user_id, state.datasource_ids, state.used_sources_dict
        )

        # 如果之前已有知識，則合併
        if state.knowledge:
            combined_knowledge = state.knowledge + "\n\n---\n\n" + combined_knowledge

        actual_queries = planned_queries

    # ===== 回退: 使用舊的子問題方式（驗證階段生成） =====
    elif state.suggested_sub_questions:
        sub_questions = ensure_main_query_first(state.suggested_sub_questions.copy(), current_query)
        print(f"🔄 使用驗證階段建議的子問題（共 {len(sub_questions)} 個）")

        combined_knowledge, combined_sources, combined_tables = await retrieve_multiple_queries(
            sub_questions, current_query, user_id, state.datasource_ids, state.used_sources_dict
        )

        if state.knowledge:
            combined_knowledge = state.knowledge + "\n\n---\n\n" + combined_knowledge

        actual_queries = sub_questions

    elif state.validation_need_supplement_info:
        sub_questions = await generate_sub_questions(
            current_query, state.validation_need_supplement_info, reasoning=state.question_type_reasoning
        )
        sub_questions = ensure_main_query_first(sub_questions, current_query)
        print(f"🔄 根據驗證反饋生成子問題（共 {len(sub_questions)} 個）")

        combined_knowledge, combined_sources, combined_tables = await retrieve_multiple_queries(
            sub_questions, current_query, user_id, state.datasource_ids, state.used_sources_dict
        )

        if state.knowledge:
            combined_knowledge = state.knowledge + "\n\n---\n\n" + combined_knowledge

        actual_queries = sub_questions

    # ===== 直接檢索（簡單問題） =====
    else:
        print("⏩ 直接檢索（無 Planning 步驟）")
        combined_knowledge, _, combined_sources, combined_tables = await retrieve_single_query(
            current_query, store=clue_store, user_id=user_id, datasource_ids=state.datasource_ids,
            is_main_question=True  # 🔒 直接檢索時就是主問題，不快取
        )
        actual_queries = [current_query]

    # 檢查檢索結果 (文字 + 圖片)
    has_information = bool(combined_sources) or bool(educational_images)

    if not has_information:
        print("⚠️ 所有檢索（包含文字與圖片）都沒有找到有效參考內容")
        return {
            "knowledge": "", "used_sources_dict": {}, "original_docs_dict": {},
            "knowledge_retrieval_count": state.knowledge_retrieval_count + 1,
            "query_type": "out_of_scope", "actual_search_queries": [],
            "iteration_count": state.iteration_count + 1,
            "matched_educational_images": []
        }

    # 🆕 強制注入圖片分析內容：無論是否有文字來源，只要有衛教圖片，就將其描述加入知識庫
    if educational_images:
        print(f"🖼️  將 {len(educational_images)} 張衛教圖片的分析內容注入為知識線索")
        image_clues = []
        for img in educational_images:
            # 格式化圖片內容，明確告知 LLM 這是圖片資訊
            topic = img.get('health_topic', '未命名圖片')
            desc = img.get('detailed_description', '無詳細描述')
            filename = img.get('filename', '')
            
            # 🆕 去重檢查：避免重複注入相同的圖片資訊
            clue_signature = f"【衛教圖片資訊 - {topic}】\n(檔名: {filename})"
            if clue_signature in combined_knowledge:
                continue

            image_clues.append(f"{clue_signature}\n圖片內容分析: {desc}")
        
        # 組合圖片補充資訊（如果有新內容）
        if image_clues:
            image_knowledge_block = (
                "【系統註記：以下是檢索到的衛教圖片詳細內容分析。請充分利用這些資訊來回答使用者的問題，"
                "這通常包含具體的照護步驟或圖示說明。若回答內容源自此處，請自然地融入回答中。】\n\n" 
                + "\n\n".join(image_clues)
            )

            # 將圖片資訊附加到現有知識中 (如果已有知識則用分隔線隔開)
            if combined_knowledge:
                combined_knowledge = combined_knowledge + "\n\n---\n\n" + image_knowledge_block
            else:
                combined_knowledge = image_knowledge_block

    return {
        "knowledge": combined_knowledge,
        "used_sources_dict": combined_sources,
        "original_docs_dict": combined_sources,
        "matched_table_images": combined_tables,
        "matched_educational_images": educational_images,
        "knowledge_retrieval_count": state.knowledge_retrieval_count + 1,
        "actual_search_queries": actual_queries,
        "validation_need_supplement_info": "",
        "suggested_sub_questions": [],
        "iteration_count": state.iteration_count + 1
    }


async def generate_response(state: FullState):
    """生成回答"""
    LogHelper.section(f"💬 開始生成回答 - 當前迭代次數: {state.iteration_count}/{WORKFLOW_LIMITS['max_iteration_count']}")
    
    # 处理特殊类型
    if state.query_type == "greet":
        try:
            response = await llm.ainvoke(f"{GREET_PROMPTTEMPLATE}\n\n當前問題：{state.current_query}")
            greeting = response.content.strip()
        except:
            greeting = "您好，我是長庚醫院小幫手，我會在我所知的範圍內回答您的問題。"
        return {"final_answer": greeting, "messages": [AIMessage(content=greeting)]}
    
    if state.query_type == "out_of_scope":
        msg = "抱歉，這個問題超出了我的專業範圍。"
        return {"final_answer": msg, "messages": [AIMessage(content=msg)]}
    
    # 检查知识有效性
    knowledge = state.knowledge
    if not knowledge or not knowledge.strip():
        return {"final_answer": "抱歉，資料庫中未找到可回答此問題的醫療資訊。請諮詢專業醫療人員或相關科室。"}
    
    # 检查是否所有子问题都无线索
    parts = knowledge.split("\n\n---\n\n")
    if all("無線索" in p and "[子問題：" in p for p in parts):
        return {"final_answer": "抱歉，資料庫中未找到可回答此問題的醫療資訊。請諮詢專業醫療人員或相關科室。"}
    
    # 构建历史对话
    history_messages = []
    if is_short_term_memory_enabled(state) and len(state.messages) > 1:
        history_messages = state.messages[-6:-1]
    
    # 选择 prompt
    if history_messages:
        conversation_context = build_conversation_context(history_messages)
        prompt = get_rag_response_prompt_with_history(
            knowledge=knowledge, question=state.current_query,
            memory_summary=state.memory_summary, conversation_context=conversation_context,
            question_reasoning=state.question_type_reasoning
        )
    else:
        prompt = get_rag_response_prompt(
            knowledge=knowledge, question=state.current_query,
            question_reasoning=state.question_type_reasoning
        )
    
    try:
        message_stream = llm.astream(prompt)
        full_response = await stream_llm_response(message_stream)
        
        # 后处理
        processed_response = await post_process_response(full_response, list(state.used_sources_dict.keys()))
        final_answer = converter.convert(remove_think_tags(processed_response))

        # 处理表格图片
        matched_tables = state.matched_table_images or []
        
        # 从 metadata 提取
        if not matched_tables and state.original_docs_dict:
            matched_tables = extract_tables_from_metadata(state.original_docs_dict)
        
        # 匹配表格
        if not matched_tables:
            matched_tables = await match_tables_for_answer(final_answer, state.used_sources_dict or {})
        
        # ✅ 去重表格图片（基于 image_path）
        if matched_tables:
            seen_paths = set()
            unique_tables = []
            for table in matched_tables:
                img_path = table.get('image_path', '')
                if img_path and img_path not in seen_paths:
                    seen_paths.add(img_path)
                    unique_tables.append(table)

            # 按相似度排序（高到低）
            unique_tables.sort(key=lambda x: x.get('similarity', 0.0), reverse=True)
            matched_tables = unique_tables

            print(f"✅ 去重後剩餘 {len(matched_tables)} 個唯一表格圖片")

        # ✅ 修改：同時顯示文字參考資料、表格圖片和衛教圖片
        
        # 定義無效回答的列表，避免在無效回答後附加參考資料
        NO_ANSWER_MESSAGES = [
            "抱歉，這個問題超出了我的專業範圍。",
            "抱歉，資料庫中未找到可回答此問題的醫療資訊。請諮詢專業醫療人員或相關科室。",
            "抱歉，無法生成回答",
            "抱歉，生成回答時發生錯誤。"
        ]
        
        is_no_answer = any(msg in final_answer for msg in NO_ANSWER_MESSAGES)

        # 初始化變數，避免 UnboundLocalError
        matched_edu_images = []
        
        if is_no_answer:
            print("⚠️ 檢測到無效回答，跳過附加參考資料和圖片")
        else:
            # 1. 準備文字參考資料
            docs_dict = state.used_sources_dict
            new_refs = ""
            if docs_dict:
                # 移除 LLM 生成的參考依據區塊
                if "**參考依據**" in final_answer:
                    final_answer = final_answer[:final_answer.find("**參考依據**")].rstrip()
                new_refs = rebuild_references_from_used_sources(docs_dict)

            # 2. 準備與去重衛教圖片
            matched_edu_images = state.matched_educational_images or []
            if matched_edu_images:
                # ✅ 去重衛教圖片（基於 filename 與 主題）
                seen_filenames = set()
                seen_topics = set()
                unique_edu_images = []
                for img in matched_edu_images:
                    fname = img.get('filename', '')
                    topic = img.get('health_topic', '')
                    
                    if fname and fname not in seen_filenames and topic not in seen_topics:
                        seen_filenames.add(fname)
                        seen_topics.add(topic)
                        unique_edu_images.append(img)
                matched_edu_images = unique_edu_images

            # 3. 準備表格圖片 (已在上方去重過，這裡直接使用)
            # matched_tables 已在前面處理過

            # 🆕 嚴格檢查：必須要有有效的文字參考資料才能生成回答
            # 即使有圖片，如果沒有文字參考依據，也不應該給出綜合建議（避免幻覺或無根據的建議）
            has_valid_refs = bool(new_refs.strip())
            
            if not has_valid_refs:
                print("⚠️ 經過嚴格過濾後無有效文字參考資料（即使有圖片），視為無效，回退至罐頭訊息")
                return {"final_answer": "抱歉，資料庫中未找到可回答此問題的醫療資訊。請諮詢專業醫療人員或相關科室。"}

            # 4. 組合最終回答
            if new_refs:
                final_answer = final_answer + "\n\n" + new_refs
                print(f"✅ 已添加文字參考資料")

            if matched_edu_images:
                print(f"✅ 檢測到 {len(matched_edu_images)} 個衛教圖片（已去重），一併顯示")
                final_answer += format_educational_image_section(matched_edu_images)

            if matched_tables:
                print(f"✅ 檢測到 {len(matched_tables)} 個表格圖片，一併顯示")
                final_answer += format_table_section(matched_tables)
        
        return {
            "final_answer": final_answer,
            "iteration_count": state.iteration_count + 1,
            "matched_table_images": matched_tables,
            "matched_educational_images": matched_edu_images
        }
        
    except Exception as e:
        print(f"❌ 生成失敗: {e}")
        return {"final_answer": "抱歉，生成回答時發生錯誤。"}

async def validate_answer(state: FullState) -> Dict:
    """驗證回答品質"""
    LogHelper.section(f"🔍 開始驗證回答 - 當前迭代次數: {state.iteration_count}/{WORKFLOW_LIMITS['max_iteration_count']}")
    
    # 檢查知識為空但有參考引用
    if (not state.knowledge or not state.knowledge.strip()) and \
       any(kw in state.final_answer for kw in ["根據該文件", "《", "參考依據"]):
        return {
            "validation_result": "need_more_knowledge",
            "validation_feedback": "回答包含參考資料引用但沒有實際檢索結果",
            "iteration_count": state.iteration_count + 1
        }
    
    # 迭代次數檢查
    if state.iteration_count >= WORKFLOW_LIMITS['validation_iteration_threshold']:
        return {"validation_result": "out_of_scope"}
    
    if state.knowledge_retrieval_count >= WORKFLOW_LIMITS['validation_retrieval_threshold']:
        return {"validation_result": "out_of_scope"}
    
    # 準備驗證
    validate_output = PydanticOutputParser(pydantic_object=ValidationResult)
    truncated_knowledge = smart_truncate_knowledge(state.knowledge, max_chars=8192)
    
    conversation_context = ""
    if is_short_term_memory_enabled(state) and state.messages:
        conversation_context = build_conversation_context(state.messages[:-1])
    
    full_prompt = ANSWER_VALIDATION_PROMPT.format(
        user_query=state.current_query,
        assistant_answer=state.final_answer,
        knowledge_used=truncated_knowledge or "（無檢索知識）",
        conversation_context=conversation_context or "（無對話歷史）",
        format_instructions=validate_output.get_format_instructions()
    )
    
    try:
        chain = llm | validate_output
        result: ValidationResult = await chain.ainvoke(full_prompt)
        
        output = {"validation_result": result.validation_type}
        
        if result.validation_type == "need_more_knowledge":
            output["iteration_count"] = state.iteration_count + 1
            if result.missing_info:
                output["validation_need_supplement_info"] = result.missing_info
            if result.suggested_sub_questions:
                output["suggested_sub_questions"] = result.suggested_sub_questions
        elif result.validation_type == "regenerate":
            output["iteration_count"] = state.iteration_count + 1
        
        return output
        
    except Exception as e:
        print(f"❌ 驗證失敗: {e}")
        return {"validation_result": "pass"}


async def refine_answer(state: FullState):
    """精煉回答（保留參考文獻和圖片）"""
    conversation_context = ""
    if is_short_term_memory_enabled(state) and state.messages:
        conversation_context = build_conversation_context(state.messages[:-1])

    refine_prompt = ANSWER_REGENERATE_PROMPT.format(
        current_query=state.current_query,
        conversation_context=conversation_context or "（無對話歷史）",
        validation_feedback=state.validation_feedback or "需要改進回答品質"
    )

    try:
        response = await llm.ainvoke(refine_prompt)
        refined = converter.convert(remove_think_tags(response.content))

        # 🆕 重新添加參考文獻（如果原本有的話）
        docs_dict = state.used_sources_dict
        if docs_dict:
            # 移除 LLM 可能生成的參考依據區塊
            if "**參考依據**" in refined:
                refined = refined[:refined.find("**參考依據**")].rstrip()
            new_refs = rebuild_references_from_used_sources(docs_dict)
            if new_refs:
                refined = refined + "\n\n" + new_refs

        # 🆕 重新添加衛教圖片（如果原本有的話）
        matched_edu_images = state.matched_educational_images or []
        if matched_edu_images:
            refined += format_educational_image_section(matched_edu_images)

        # 🆕 重新添加表格圖片（如果原本有的話）
        matched_tables = state.matched_table_images or []
        if matched_tables:
            refined += format_table_section(matched_tables)

        return {"final_answer": refined, "retry_count": state.retry_count + 1, "iteration_count": state.iteration_count + 1}
    except:
        return {"retry_count": state.retry_count + 1}


async def check_question_type(state: FullState):
    """檢查問題類別並提取 reasoning"""
    print(f"\n🔍 檢查問題類別 - 當前迭代次數: {state.iteration_count}/{WORKFLOW_LIMITS['max_iteration_count']}")
    
    conversation_history = ""
    if is_short_term_memory_enabled(state) and state.messages:
        conversation_history = build_conversation_context(state.messages, include_current=True)
    
    prompt = QUESTION_TYPE_CHECK_PROMPT.format(
        current_query=state.current_query,
        conversation_history=conversation_history or "（無對話歷史）"
    )
    
    try:
        response = await llm.ainvoke(prompt)
        content = remove_think_tags(response.content.strip())
        
        # 清理 JSON
        for prefix in ["```json", "```"]:
            if content.startswith(prefix):
                content = content[len(prefix):]
        if content.endswith("```"):
            content = content[:-3]
        
        parsed = json.loads(content.strip())
        return {
            "question_category": parsed.get("question_type", "medical"),
            "question_type_reasoning": parsed.get("reasoning", "")
        }
    except:
        return {"question_category": "medical", "question_type_reasoning": ""}


async def supplement_with_realtime_info(state: FullState):
    """
    用即時搜尋工具補充知識檢索結果

    只要使用者透過 enabled_tool_ids 選擇了外部搜尋工具，就會執行搜尋
    不做額外的智能判斷（已簡化）
    """
    enabled_tool_ids = state.enabled_tool_ids if state.enabled_tool_ids is not None else TOOLS_CONFIG.get('default_tools', [])

    # 如果工具系統停用且使用者沒有指定工具，則跳過
    if not TOOLS_CONFIG.get('enabled', True) and state.enabled_tool_ids is None:
        return {}

    # 獲取搜索工具
    search_tools = []
    for tool_id in enabled_tool_ids:
        tool_config = get_tool(tool_id)
        if tool_config and tool_config.metadata.get('category') == 'external_search':
            search_tools.append((tool_id, tool_config))

    # 如果沒有搜索工具，則跳過（使用者未選擇任何外部搜尋工具）
    if not search_tools:
        return {}

    # 確定搜索查詢
    search_queries = state.actual_search_queries if hasattr(state, 'actual_search_queries') and state.actual_search_queries else [state.current_query]
    
    all_realtime_info = []
    all_sources_dict = {}
    
    for query in search_queries:
        if not query or len(query.strip()) < 2:
            continue
        
        for tool_id, tool_config in search_tools:
            try:
                tool_func = tool_config.tool_func
                
                # 根據工具類型調用
                if tool_id == "cdc_realtime_search":
                    result = tool_func.invoke({"keyword": query, "num_results": 2})
                elif tool_id == "google_realtime_search":
                    result = await tool_func.ainvoke({"query": query, "max_results": 3})
                elif tool_id == "duckduckgo_realtime_search":
                    result = await tool_func.ainvoke({
                        "query": query, "max_results": 3, "region": "tw-tzh",
                        "safe_search": "moderate", "get_full_content": True
                    })
                else:
                    result = await tool_func.ainvoke({"query": query, "max_results": 3})
                
                if result and not str(result).startswith("❌"):
                    all_realtime_info.append(f"\n【{tool_config.name}】\n{'='*80}\n{result}")
                    
                    sources = extract_cdc_sources_with_content(result) if tool_id == "cdc_realtime_search" else extract_search_sources_with_content(result, tool_config.name)
                    all_sources_dict.update(sources)
                    
            except Exception as e:
                print(f"❌ {tool_config.name} 錯誤: {e}")
    
    if all_realtime_info:
        combined_realtime = "\n".join(all_realtime_info)
        knowledge = state.knowledge or ""
        
        combined_knowledge = (
            f"{knowledge}\n{'*'*3}\n【即時搜尋資訊】\n{'*'*3}\n{combined_realtime}"
            if knowledge else f"【即時搜尋資訊】\n{'*'*3}\n{combined_realtime}"
        )
        
        updated_sources = (state.used_sources_dict.copy() if state.used_sources_dict else {})
        updated_sources.update(all_sources_dict)
        
        return {
            "knowledge": combined_knowledge,
            "used_sources_dict": updated_sources,
            "original_docs_dict": updated_sources
        }
    
    return {}


async def set_out_of_scope_message(_state: FullState):
    """設置超出範圍訊息"""
    from core.prompt_config import ERROR_RESPONSES
    return {"final_answer": ERROR_RESPONSES["out_of_scope"]}