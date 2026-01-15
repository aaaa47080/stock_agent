"""
統一 Metadata 標準
為所有資料源提供統一的 metadata 結構和處理函數
"""
from typing import Dict, Any
import re


# ==================== 統一標準定義 ====================

class UnifiedMetadata:
    """
    統一的 Metadata 標準結構

    所有資料源都應該轉換為這個標準格式
    """

    # 核心必填欄位
    source_file: str          # 檔案名稱（統一使用 .pdf 後綴）
    source_type: str          # 'excel', 'pdf', 'ocr_pdf'
    page: int                 # 頁碼/位置
    content: str              # 文本內容

    # 分類與標籤
    category: str             # 分類
    title: str                # 標題
    keywords: str             # 關鍵字

    # 來源資訊
    reference: str            # 參考文獻/準則名稱
    collection_name: str      # 所屬 collection

    # 可選欄位
    sheet_name: str           # Excel 工作表名稱（僅 excel 類型）
    folder: str               # 資料夾
    page_label: str           # PDF 內部頁碼標籤


# ==================== 檔名正規化 ====================

def normalize_source_filename(filename: str) -> str:
    """
    將 xlsx 檔名還原為原始 PDF 檔名

    Examples:
        發燒、咳嗽及腹瀉監測與自主健康管理作業準則_關鍵字詞.xlsx
        → 發燒、咳嗽及腹瀉監測與自主健康管理作業準則.pdf
    """
    if not isinstance(filename, str):
        return filename

    # 移除 _關鍵字詞 後綴
    filename = re.sub(r'[_﹍]關鍵字詞', '', filename)

    # 將 .xlsx 替換為 .pdf
    if filename.lower().endswith('.xlsx'):
        filename = filename[:-5] + '.pdf'

    return filename


# ==================== Metadata 轉換函數 ====================

def normalize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    將任意格式的 metadata 轉換為統一標準格式

    Args:
        metadata: 原始 metadata 字典

    Returns:
        統一格式的 metadata 字典
    """
    # 自動檢測原始格式
    source_type = _detect_source_type(metadata)

    # 根據類型進行轉換
    if source_type == 'excel':
        return _normalize_excel_metadata(metadata)
    elif source_type == 'pdf':
        return _normalize_pdf_metadata(metadata)
    elif source_type == 'ocr_pdf':
        return _normalize_ocr_metadata(metadata)
    else:
        # 未知格式，返回基本結構
        return _normalize_unknown_metadata(metadata)


def _detect_source_type(metadata: Dict[str, Any]) -> str:
    """自動檢測資料源類型"""
    # 檢查是否有明確的 source_type 標記
    if 'source_type' in metadata:
        source_type = metadata['source_type']
        # 將 'jsonl' 轉換為 'excel'（兼容舊標記）
        if source_type == 'jsonl':
            return 'excel'
        return source_type

    # 根據欄位特徵判斷
    if 'pdf_file' in metadata:
        return 'pdf'
    elif 'source_file' in metadata and metadata.get('source_file', '').endswith('.xlsx'):
        return 'excel'
    elif 'source_file' in metadata and 'category' in metadata:
        # 洗腎衛教特徵：有 source_file 和 category
        return 'ocr_pdf'
    elif 'sheet_name' in metadata:
        # 有 sheet_name 的一定是 Excel
        return 'excel'
    else:
        return 'unknown'


def _normalize_excel_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    轉換 Excel (JSONL) 格式的 metadata

    原始格式:
        {
            'source_file': '...xlsx',
            'sheet_name': '...',
            'title': '...',
            'keywords': '...',
            'reference': '...',
            'source_type': 'jsonl'
        }
    """
    source_file = metadata.get('source_file', '')
    normalized_file = normalize_source_filename(source_file)

    # 🔧 優先使用 original_full_text（完整的問題+答案）
    content = metadata.get('original_full_text', '')

    # 🔧 回退：如果沒有 original_full_text，從 title + original_text 構建完整 QA 格式
    if not content:
        title = metadata.get('title', '')
        original_text = metadata.get('original_text', '')
        if title and original_text:
            # 構建完整的 QA 格式
            content = f"問題: {title}\n答案: {original_text}"
        elif original_text:
            # 只有答案，沒有問題
            content = original_text
        elif title:
            # 只有問題，沒有答案
            content = title

    return {
        # 核心欄位
        'source_file': normalized_file,
        'source_type': 'excel',
        'page': 0,  # Excel 沒有頁碼概念
        'content': content,

        # 分類與標籤
        'category': metadata.get('reference', ''),  # 使用 reference 作為分類
        'title': metadata.get('title', ''),
        'keywords': metadata.get('keywords', ''),

        # 來源資訊
        'reference': metadata.get('reference', ''),
        'collection_name': metadata.get('collection_name', ''),

        # Excel 特有欄位
        'sheet_name': metadata.get('sheet_name', ''),
        'folder': '',
        'page_label': '',
    }


def _normalize_pdf_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    轉換標準 PDF 格式的 metadata

    原始格式:
        {
            'pdf_file': '...pdf',
            'page': 16,
            'page_label': '17',
            'title': '...',
            'folder': '...',
            'keywords': '...',
            'source_type': 'pdf'
        }
    """
    pdf_file = metadata.get('pdf_file', '')
    normalized_file = normalize_source_filename(pdf_file)

    # 提取分類（從 folder 或 title）
    category = metadata.get('folder', '')
    if not category or category == 'N/A':
        title = metadata.get('title', '')
        if title and title != 'CGMH(All Right Reserved)':
            category = title

    return {
        # 核心欄位
        'source_file': normalized_file,
        'source_type': 'pdf',
        'page': metadata.get('page', 0),
        'content': metadata.get('original_text', ''),

        # 分類與標籤
        'category': category,
        'title': metadata.get('title', ''),
        'keywords': metadata.get('keywords', ''),

        # 來源資訊
        'reference': normalized_file,  # PDF 使用檔名作為 reference
        'collection_name': metadata.get('collection_name', ''),

        # PDF 特有欄位
        'sheet_name': '',
        'folder': metadata.get('folder', ''),
        'page_label': metadata.get('page_label', str(metadata.get('page', ''))),
    }


def _normalize_ocr_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    轉換 OCR PDF 格式的 metadata

    原始格式:
        {
            'source_file': '...pdf',
            'page': 2,
            'category': '洗腎衛教',
            'source_type': 'ocr_pdf',
            'collection_name': '...'
        }
    """
    source_file = metadata.get('source_file', '')
    normalized_file = normalize_source_filename(source_file)

    return {
        # 核心欄位
        'source_file': normalized_file,
        'source_type': 'ocr_pdf',
        'page': metadata.get('page', 0),
        'content': metadata.get('original_text', ''),

        # 分類與標籤
        'category': metadata.get('category', ''),
        'title': metadata.get('title', ''),
        'keywords': metadata.get('keywords', ''),

        # 來源資訊
        'reference': normalized_file,  # OCR PDF 使用檔名作為 reference
        'collection_name': metadata.get('collection_name', ''),

        # OCR 特有欄位
        'sheet_name': '',
        'folder': '',
        'page_label': str(metadata.get('page', '')),
    }


def _normalize_unknown_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """處理未知格式的 metadata（保守做法）"""
    return {
        'source_file': metadata.get('source_file', metadata.get('pdf_file', 'Unknown')),
        'source_type': 'unknown',
        'page': metadata.get('page', 0),
        'content': metadata.get('original_text', ''),
        'category': metadata.get('category', ''),
        'title': metadata.get('title', ''),
        'keywords': metadata.get('keywords', ''),
        'reference': metadata.get('reference', ''),
        'collection_name': metadata.get('collection_name', ''),
        'sheet_name': metadata.get('sheet_name', ''),
        'folder': metadata.get('folder', ''),
        'page_label': metadata.get('page_label', ''),
    }


# ==================== 統一來源標註 ====================

def format_unified_citation(normalized_metadata: Dict[str, Any]) -> str:
    """
    根據統一格式的 metadata 生成來源標註

    Args:
        normalized_metadata: 經過 normalize_metadata() 處理的統一格式 metadata

    Returns:
        統一格式的來源標註字符串

    Examples:
        **[發燒、咳嗽及腹瀉監測與自主健康管理作業準則.pdf]**
        **[嬰兒出院護理指導.pdf (第 17 頁)]**
        **[洗腎衛教 - 國人膳食營養素參考攝取量第八版-鐵.pdf (第 2 頁)]**
    """
    source_file = normalized_metadata.get('source_file', 'Unknown')
    source_type = normalized_metadata.get('source_type', '')
    page = normalized_metadata.get('page', 0)
    page_label = normalized_metadata.get('page_label', '')
    category = normalized_metadata.get('category', '')

    # 構建基本標註
    parts = []

    # 添加分類（如果有意義）
    if category and category not in ['N/A', 'Unknown', '']:
        # 避免重複：如果 category 已經包含在檔名中，就不顯示
        if category not in source_file:
            parts.append(category)

    # 添加檔名
    parts.append(source_file)

    # 組合基本字串
    base_str = ' - '.join(parts) if len(parts) > 1 else parts[0]

    # 添加頁碼（如果有）
    if source_type in ['pdf', 'ocr_pdf'] and (page or page_label):
        display_page = page_label if page_label else str(page)
        if display_page and display_page != '0':
            return f"**[{base_str} (第 {display_page} 頁)]**"

    return f"**[{base_str}]**"


# ==================== 輸出結構生成 ====================

def create_unified_doc_data(doc, score: float, rank: int) -> Dict[str, Any]:
    """
    根據 LangChain Document 創建統一格式的輸出結構

    Args:
        doc: LangChain Document 對象
        score: 相似度分數
        rank: 排名

    Returns:
        統一格式的文檔數據字典
    """
    # 轉換為統一格式
    normalized = normalize_metadata(doc.metadata)

    # 🔧 提取原始 metadata 中的表格相關欄位
    original_metadata = doc.metadata
    has_table = original_metadata.get('has_table', False)
    table_images = original_metadata.get('table_images', [])

    # 🔧 處理 table_images 可能是 JSON 字符串的情況
    if isinstance(table_images, str):
        import json
        try:
            table_images = json.loads(table_images)
        except:
            table_images = []

    # 構建輸出結構
    return {
        'rank': rank,
        'score': float(score),
        'title': normalized['title'],
        'keywords': normalized['keywords'],
        'category': normalized['category'],
        'content': normalized['content'] or doc.page_content,
        'source': {
            'type': normalized['source_type'],
            'file': normalized['source_file'],
            'page': normalized['page'],
            'page_label': normalized['page_label'],
            'reference': normalized['reference'],
            'collection': normalized['collection_name'],
            # 可選欄位
            'sheet': normalized['sheet_name'],
            'folder': normalized['folder'],
        },
        'citation': format_unified_citation(normalized),
        # 🆕 添加表格/圖片相關元數據
        'metadata': {
            'has_table': has_table,
            'table_images': table_images
        }
    }


# ==================== 測試代碼 ====================

if __name__ == "__main__":
    """測試統一轉換功能"""

    # 測試 1: Excel 格式
    print("=" * 80)
    print("測試 1: Excel (JSONL) 格式")
    print("=" * 80)
    excel_metadata = {
        'id': 'test_1',
        'source_file': '發燒、咳嗽及腹瀉監測與自主健康管理作業準則_關鍵字詞.xlsx',
        'sheet_name': '發燒、咳嗽及腹瀉監測與自主健康管理作業準則_文字',
        'title': '發燒定義',
        'keywords': '發燒',
        'reference': '發燒、咳嗽及腹瀉監測與自主健康管理作業準則',
        'source_type': 'jsonl',
        'original_text': '係指耳溫≧38℃者'
    }

    normalized = normalize_metadata(excel_metadata)
    print(f"原始檔名: {excel_metadata['source_file']}")
    print(f"統一檔名: {normalized['source_file']}")
    print(f"來源標註: {format_unified_citation(normalized)}")
    print()

    # 測試 2: PDF 格式
    print("=" * 80)
    print("測試 2: 標準 PDF 格式")
    print("=" * 80)
    pdf_metadata = {
        'pdf_file': '嬰兒出院護理指導.pdf',
        'page': 16,
        'page_label': '17',
        'title': 'CGMH(All Right Reserved)',
        'folder': '衛教園地綜合資訊',
        'keywords': 'CGMH(All Right Reserved)',
        'source_type': 'pdf'
    }

    normalized = normalize_metadata(pdf_metadata)
    print(f"原始檔名: {pdf_metadata['pdf_file']}")
    print(f"統一檔名: {normalized['source_file']}")
    print(f"來源標註: {format_unified_citation(normalized)}")
    print()

    # 測試 3: OCR PDF 格式
    print("=" * 80)
    print("測試 3: OCR PDF 格式")
    print("=" * 80)
    ocr_metadata = {
        'source_file': '「國人膳食營養素參考攝取量」第八版-鐵.pdf',
        'page': 2,
        'category': '洗腎衛教',
        'source_type': 'ocr_pdf',
        'collection_name': 'dialysis_education_materials'
    }

    normalized = normalize_metadata(ocr_metadata)
    print(f"原始檔名: {ocr_metadata['source_file']}")
    print(f"統一檔名: {normalized['source_file']}")
    print(f"來源標註: {format_unified_citation(normalized)}")
    print()

    print("=" * 80)
    print("✅ 所有測試完成！")
    print("=" * 80)
