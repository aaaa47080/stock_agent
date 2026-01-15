"""
回答處理工具模組
包含參考文獻驗證、合併、格式化等功能
"""

import os
import re
from typing import List, Tuple
from difflib import SequenceMatcher
from core.config import llm, get_reference_mapping
from retrieval.retrieval_utils import DATASET_FILES_CACHE


def convert_references_to_english(chinese_ref: str) -> str:
    """將中文參考文獻轉換為英文路徑"""
    reference_mapping = get_reference_mapping()
    return reference_mapping.get(chinese_ref, "medical_knowledge_base")


def extract_sources_from_knowledge(knowledge: str) -> list[str]:
    """從知識文本中提取參考來源"""
    sources = set()
    pattern = r'《([^》]+)》'
    matches = re.findall(pattern, knowledge)
    for match in matches:
        sources.add(match.strip())
    return list(sources)


def verify_document_references(response_content: str, original_sources: list[str] = None) -> tuple[bool, list[str]]:
    """
    驗證回答中引用的文件是否有效
    優先檢查是否在 original_sources（本次檢索實際返回的文件）中
    支援有/無副檔名的比對
    """
    pattern = r'《([^》]+)》'
    referenced_docs = re.findall(pattern, response_content)
    if not referenced_docs:
        return True, []

    # 優先使用本次檢索實際返回的文件列表
    if original_sources:
        invalid_docs = []

        # 準備標準化的來源列表（去除副檔名和路徑）
        normalized_sources = set()
        for s in original_sources:
            # 取得基本檔名
            basename = os.path.basename(s)
            # 移除副檔名
            name_without_ext = os.path.splitext(basename)[0]
            # 加入兩種形式
            normalized_sources.add(basename)
            normalized_sources.add(name_without_ext)
            normalized_sources.add(s)  # 也加入原始形式

        for doc in referenced_docs:
            # 標準化引用的文件名
            doc_basename = os.path.basename(doc)
            doc_without_ext = os.path.splitext(doc_basename)[0]

            # 檢查是否匹配（完整名稱、basename、或無副檔名版本）
            if doc not in normalized_sources and \
               doc_basename not in normalized_sources and \
               doc_without_ext not in normalized_sources:
                invalid_docs.append(doc)

        return len(invalid_docs) == 0, invalid_docs

    # 退回使用全局文件緩存
    actual_files = DATASET_FILES_CACHE
    if not actual_files:
        return False, referenced_docs
    invalid_docs = []
    for doc in referenced_docs:
        doc_name = os.path.basename(doc)
        doc_without_ext = os.path.splitext(doc_name)[0]

        # 檢查帶有或不帶副檔名的版本
        if doc_name not in actual_files and doc_without_ext not in actual_files:
            invalid_docs.append(doc)
    return len(invalid_docs) == 0, invalid_docs


def correct_document_names(response_content: str, original_sources: list[str]) -> str:
    """
    只糾正明顯的拼寫錯誤（相似度 ≥ 0.95）
    """
    if not original_sources or not response_content:
        return response_content

    pattern = r'《([^》]+)》'
    referenced_docs = re.findall(pattern, response_content)
    if not referenced_docs:
        return response_content

    corrected_content = response_content
    corrections_made = []

    for ref_doc in referenced_docs:
        if ref_doc in original_sources:
            continue

        best_match = None
        best_ratio = 0.0
        for orig_source in original_sources:
            ratio = SequenceMatcher(None, ref_doc.lower(), orig_source.lower()).ratio()
            if ratio > best_ratio and ratio >= 0.95:
                best_ratio = ratio
                best_match = orig_source

        if best_match:
            corrected_content = corrected_content.replace(f'《{ref_doc}》', f'《{best_match}》')
            corrections_made.append(f"{ref_doc} → {best_match} (相似度: {best_ratio:.2f})")

    if corrections_made:
        print(f"📝 自動糾正了 {len(corrections_made)} 個文件名稱拼寫錯誤:")
        for correction in corrections_made:
            print(f"   - {correction}")

    return corrected_content


def merge_duplicate_references(content: str) -> str:
    """快速合併重複的參考文獻（基於規則）"""
    if '**參考依據' not in content:
        return content

    ref_section_match = re.search(r'(\*\*參考依據[：:]*\*\*.*?)$', content, re.DOTALL)
    if not ref_section_match:
        return content

    ref_section = ref_section_match.group(1)
    file_pattern = r'《([^》]+)》'
    content_lines = ref_section.split('\n')

    # 儲存每個文件對應的內容
    file_contents = {}
    current_file = None

    for line in content_lines:
        stripped = line.strip()

        # 檢測文件名
        file_match = re.search(file_pattern, stripped)
        if file_match:
            current_file = file_match.group(1)
            if current_file not in file_contents:
                file_contents[current_file] = []
            continue

        # 內容行
        if current_file and stripped and stripped.startswith('-'):
            content_text = stripped.lstrip('- ').strip()
            if content_text and content_text not in file_contents[current_file]:
                file_contents[current_file] = []

                file_contents[current_file].append(content_text)

    # 重建參考依據區塊
    merged_lines = ['**參考依據**']
    for filename, contents in file_contents.items():
        if filename and filename.strip() and filename not in ['Unknown', '   ']:
            merged_lines.append(f'《{filename}》')
            for content in contents:
                if content:
                    merged_lines.append(f'   - {content}')
            merged_lines.append('')

    merged_ref_section = '\n'.join(merged_lines).strip()
    main_content = content[:ref_section_match.start()]

    return main_content.rstrip() + '\n\n' + merged_ref_section


async def merge_duplicate_references_with_llm(content: str) -> str:
    """使用 LLM 智能合併參考文獻"""
    if '**參考依據' not in content:
        return content

    ref_section_match = re.search(r'(\*\*參考依據[：:]*\*\*.*?)$', content, re.DOTALL)
    if not ref_section_match:
        return content

    ref_section = ref_section_match.group(1)
    file_pattern = r'《([^》]+)》'
    filenames = re.findall(file_pattern, ref_section)

    # 如果沒有重複，直接返回
    if len(filenames) == len(set(filenames)):
        return content

    # 使用 prompt_config.py 中的 REFERENCE_MERGE_PROMPT
    from core.prompt_config import REFERENCE_MERGE_PROMPT
    merge_prompt = REFERENCE_MERGE_PROMPT.format(ref_section=ref_section)

    try:
        response = await llm.ainvoke(merge_prompt)
        merged_ref_section = response.content.strip()

        if not merged_ref_section.startswith('**參考依據'):
            merged_ref_section = '**參考依據**\n' + merged_ref_section

        main_content = content[:ref_section_match.start()]
        return main_content.rstrip() + '\n\n' + merged_ref_section

    except Exception as e:
        print(f"⚠️ LLM 合併失敗: {e}，使用規則合併")
        return merge_duplicate_references(content)


async def post_process_response(content: str, original_sources: list[str]) -> str:
    """後處理回答：消毒、驗證、糾正、合併參考文獻"""
    # print("\n" + "="*80)
    # print("🔍 開始後處理回答...")
    # print("="*80)

    # 調試：打印 original_sources
    # print(f"📋 original_sources ({len(original_sources)} 個):")
    # for src in original_sources[:10]:  # 只顯示前10個
    #     print(f"   - {src}")
    # if len(original_sources) > 10:
    #     print(f"   ... 還有 {len(original_sources) - 10} 個")

    # 🛡️ 0. 首要步驟：消毒輸出，移除洩漏的 Prompt 指令
    sanitized_content,_ = sanitize_llm_output(content)
    # if was_sanitized:
    #     print("   ⚠️ 已移除潛在的 Prompt Leakage")

    # 1. 糾正拼寫錯誤
    corrected_content = correct_document_names(sanitized_content, original_sources)

    # 2. 驗證文件引用
    is_valid, invalid_docs = verify_document_references(corrected_content, original_sources)
    if not is_valid:
        # print(f"\n⚠️ 發現 {len(invalid_docs)} 個無效文件引用:")
        for doc in invalid_docs:
            print(f"   - 《{doc}》")

        # 移除無效引用
        for doc in invalid_docs:
            pattern = rf'《{re.escape(doc)}》[^\n]*\n?'
            corrected_content = re.sub(pattern, '', corrected_content)
        # print("✅ 已移除無效引用")

    # 3. 合併重複參考
    final_content = await merge_duplicate_references_with_llm(corrected_content)

    # print("="*80)
    # print("✅ 後處理完成")
    # print("="*80 + "\n")

    return final_content

def parse_memory_results(result) -> list:
    """解析 mem0 記憶結果"""
    results = result.get("results", []) if isinstance(result, dict) else (
        result if isinstance(result, list) else []
    )
    memory_texts = []
    for item in results:
        if isinstance(item, dict):
            mem_content = item.get("memory", "").strip()
            if mem_content:
                memory_texts.append(mem_content)
        elif isinstance(item, str) and item.strip():
            memory_texts.append(item.strip())
    return memory_texts

def deduplicate_references(knowledge: str) -> str:
    """
    提取所有《文件名》下的內容，根據（文件名, 標準化內容）去重，
    最後統一用單一「**參考依據**」標題彙整。
    """
    # 匹配每一個「**參考依據**」區塊內的所有《...》段落
    # 注意：有些段落可能包含多個《文件》，但根據你的資料，通常一區塊一文件
    ref_blocks = re.findall(r'\*\*參考依據\*\*\s*\n((?:\s{0,4}《[^》]+》.*?)(?=\n\s*\*\*參考依據\*\*|\Z))', knowledge, re.DOTALL)

    seen = set()
    unique_contents: List[str] = []

    for block in ref_blocks:
        # 在每個 block 中找出所有《文件名》及其對應內容
        # 假設每個 block 只有一個《...》段落（符合你的資料結構）
        file_matches = re.findall(r'(《[^》]+》.*?)(?=《|\Z)', block, re.DOTALL)
        for fm in file_matches:
            fm = fm.strip()
            if not fm:
                continue
            filename_match = re.search(r'《([^》]+)》', fm)
            if not filename_match:
                continue
            filename = filename_match.group(1)
            normalized = re.sub(r'\s+', ' ', fm)
            key = (filename, normalized)
            if key not in seen:
                seen.add(key)
                unique_contents.append(fm)

    # 提取非「參考依據」的前導內容（如「以下是檢索到的相關參考資料：」）
    first_ref_pos = knowledge.find('**參考依據**')
    if first_ref_pos == -1:
        prefix = knowledge
    else:
        prefix = knowledge[:first_ref_pos].rstrip()

    # 組合結果：前導內容 + 單一「**參考依據**」標題 + 去重後的文件內容
    if unique_contents:
        ref_section = "**參考依據**\n\n" + "\n\n".join(unique_contents)
        return prefix + "\n\n" + ref_section
    else:
        return prefix

def smart_truncate_knowledge(knowledge: str, max_chars: int = 7000) -> str:
    deduped = deduplicate_references(knowledge)

    if len(deduped) <= max_chars:
        return deduped

    # print(f"⚠️ 知識過長 ({len(deduped)} 字元)，截斷至 {max_chars} 字元")

    ref_match = re.search(r'\*\*參考依據\*\*.*$', deduped, re.DOTALL)
    if ref_match:
        ref_section = ref_match.group(0)
        main_content = deduped[:ref_match.start()].rstrip()

        available_chars = max_chars - len(ref_section)
        if available_chars > 50:
            truncated_main = main_content[:available_chars - 50] + "\n\n[... 內容過長，已截斷 ...]"
            return truncated_main + "\n\n" + ref_section
        else:
            return ref_section[:max_chars] + "\n\n[... 內容過長，已截斷 ...]"
    else:
        return deduped[:max_chars] + "\n\n[... 內容過長，已截斷 ...]"


def sanitize_llm_output(content: str) -> Tuple[str, bool]:
    """
    🛡️ 輸出消毒函數：移除可能洩漏的 Prompt 指令

    防止 Prompt Leakage 攻擊，根據配置文件中的規則移除：
    1. 【格式指示...】、【指示...】等元指令標記
    2. "不要輸出"、"禁止"、"注意事項" 等內部規則
    3. 系統指令片段

    規則配置位於 config.OUTPUT_SANITIZATION_CONFIG

    Args:
        content: LLM 生成的原始內容

    Returns:
        (sanitized_content, was_sanitized): 消毒後的內容和是否進行了修改
    """
    from core.config import OUTPUT_SANITIZATION_CONFIG

    # 檢查是否啟用
    if not OUTPUT_SANITIZATION_CONFIG.get('enabled', True):
        return content, False

    original_content = content

    # 🔧 規則 1: 移除精確匹配的短語
    exact_phrases = OUTPUT_SANITIZATION_CONFIG.get('exact_phrases_to_remove', [])
    for phrase in exact_phrases:
        content = content.replace(phrase, '')

    # 🔧 規則 2: 移除標記模式（正則表達式）
    marker_patterns = OUTPUT_SANITIZATION_CONFIG.get('marker_patterns', [])
    for pattern in marker_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)

    # 🔧 規則 3: 移除包含敏感關鍵字的整行
    sensitive_patterns = OUTPUT_SANITIZATION_CONFIG.get('sensitive_line_patterns', [])
    if sensitive_patterns:
        lines = content.split('\n')
        filtered_lines = []
        for line in lines:
            is_sensitive = False
            for keyword_pattern in sensitive_patterns:
                if re.search(keyword_pattern, line, re.IGNORECASE):
                    is_sensitive = True
                    break
            if not is_sensitive:
                filtered_lines.append(line)
        content = '\n'.join(filtered_lines)

    # 🔧 規則 4: 清理殘留（移除連續空行）
    content = re.sub(r'\n{3,}', '\n\n', content)

    # 🔧 規則 5: 移除開頭和結尾的空白
    content = content.strip()

    # 檢查是否進行了修改
    was_modified = (content != original_content)

    if was_modified:
        print("🛡️ 檢測到潛在的 Prompt Leakage，已自動移除")

    return content, was_modified

