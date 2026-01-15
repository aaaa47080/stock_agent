"""
rag_files.py - PDF 檔案處理與格式化
Markdown 版本 - 為 LLM 優化
✅ v2.0: 使用統一 Metadata 標準
"""

from typing import List, Tuple, Dict, Any
from langchain_core.documents import Document

# 🆕 使用統一 Metadata 標準
from unified_metadata import (
    normalize_metadata,
    format_unified_citation,
    create_unified_doc_data
)


# ========================================
# 統一的來源標註函數（已移至 unified_metadata.py）
# ========================================

def format_source_citation(doc_type: str, metadata: dict) -> str:
    """
    統一的來源標註格式（向後兼容版本）

    ⚠️ 已廢棄：建議使用 unified_metadata.format_unified_citation()
    此函數保留以向後兼容，內部調用新的統一標準

    Args:
        doc_type: 'pdf' 或 'jsonl'
        metadata: 文檔的 metadata 字典

    Returns:
        統一格式的來源標註
    """
    # 使用新的統一標準處理
    normalized = normalize_metadata(metadata)
    return format_unified_citation(normalized)


# ========================================
# PDF 結果格式化 - Markdown 版本
# ========================================

def get_structured_pdf_results(
    results: List[Tuple],
    query: str,
    show_scores: bool = False,
    format_type: str = "markdown"
) -> Tuple[Dict[str, Any], str]:
    """
    將 PDF 檢索結果格式化為結構化數據 + Markdown 文本
    ✅ v2.0: 使用統一 Metadata 標準
    ✅ 自動支援所有 PDF 類型（標準 PDF, OCR PDF）

    Args:
        results: LangChain 檢索結果 [(Document, score), ...]
        query: 用戶問題
        show_scores: 是否顯示相似度分數
        format_type: "markdown" 或 "json"

    Returns:
        Tuple[Dict, str]: (結構化數據字典, 格式化顯示字符串)
    """
    if not results:
        empty_dict = {
            'query': query,
            'total_results': 0,
            'documents': []
        }
        return empty_dict, "未找到相關資料。"

    # 按相似度分數排序（分數越小越相似）
    sorted_results = sorted(results, key=lambda x: x[1])

    # 1️⃣ 構建結構化數據字典（使用統一標準）
    structured_data = {
        'query': query,
        'total_results': len(sorted_results),
        'documents': []
    }

    for i, (doc, score) in enumerate(sorted_results, 1):
        # 🆕 使用統一標準處理所有格式
        doc_data = create_unified_doc_data(doc, score, i)
        structured_data['documents'].append(doc_data)

    # 2️⃣ 生成格式化文本
    if format_type == "json":
        import json
        display_text = json.dumps(structured_data, ensure_ascii=False, indent=2)
    else:
        display_text = _format_pdf_markdown(sorted_results, query, show_scores)

    return structured_data, display_text


def _format_pdf_markdown(
    results: List[Tuple],
    query: str,
    show_scores: bool = False
) -> str:
    """
    將 PDF 檢索結果格式化為 Markdown 格式
    
    Args:
        results: [(Document, score), ...]
        query: 用戶查詢
        show_scores: 是否顯示分數
    
    Returns:
        Markdown 格式的文本
    """
    output = []
    output.append(f"# 檢索結果\n")
    output.append(f"**查詢**：{query}\n")
    output.append(f"**結果數量**：{len(results)}\n")
    output.append("---\n")
    
    for i, (doc, score) in enumerate(results, 1):
        metadata = doc.metadata
        page_content = doc.page_content.strip()
        
        category = metadata.get('category', '')
        title = metadata.get('title', '')
        
        # 文檔標題
        output.append(f"## 資料 {i}")
        
        # 類別
        if category and category != 'N/A':
            output.append(f"\n**類別**：{category}")
        
        # 標題
        if title:
            output.append(f"\n**標題**：{title}")
        
        # 內容
        output.append(f"\n**內容**：\n\n{page_content}")
        
        # 來源
        citation = format_source_citation('pdf', metadata)
        output.append(f"\n**來源**：{citation}")
        
        # 分數（可選）
        if show_scores:
            output.append(f"\n**相似度分數**：{score:.4f}")
        
        output.append("\n---\n")
    
    return "\n".join(output)


# ========================================
# 測試代碼
# ========================================

if __name__ == "__main__":
    """測試格式化函數"""
    
    # 模擬測試資料
    test_results = [
        (
            Document(
                page_content='施行針灸治療時，應採無菌技術操作，以75%酒精消毒皮膚時，等待其乾燥後，方可進行下一步驟；毫針使用後，應直接丟空針收集桶，不得重複使用。',
                metadata={
                    'pdf_file': '中醫藥部門感染管制作業要點.pdf',
                    'page': 9,
                    'page_label': '9',
                    'category': '針灸感染管制',
                    'title': '針灸治療無菌操作'
                }
            ),
            0.364
        ),
        (
            Document(
                page_content='診療床經傳染性病人使用過應以5,000ppm漂白水擦拭，每日診療結束後則以75%酒精或1,000ppm漂白水予以清潔消毒。',
                metadata={
                    'pdf_file': '中醫藥部門感染管制作業要點.pdf',
                    'page': 8,
                    'page_label': '8',
                    'category': '環境消毒',
                    'title': '診療床消毒規範'
                }
            ),
            0.367
        )
    ]
    
    print("=" * 80)
    print("Markdown 格式輸出:")
    print("=" * 80)
    
    structured_data, markdown_output = get_structured_pdf_results(
        test_results, 
        "針灸前應該用幾%濃度酒精消毒皮膚?", 
        show_scores=False,
        format_type="markdown"
    )
    
    print(markdown_output)
    
    print("\n" + "=" * 80)
    print("結構化數據:")
    print("=" * 80)
    import json
    print(json.dumps(structured_data, ensure_ascii=False, indent=2))
    
    print("\n" + "=" * 80)
    print("這種格式 LLM 更容易理解和引用!")
    print("=" * 80)