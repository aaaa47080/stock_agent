"""
rag_jsonl.py - JSONL 檔案處理與格式化
Markdown 版本 - 為 LLM 優化
完整修正版 - 支援 Excel 和 PDF 的來源格式化
✅ v2.0: 使用統一 Metadata 標準
"""

import os
import sys
import json
import threading
from langchain_core.documents import Document
from langchain_postgres import PGVector
from typing import List, Dict, Any, Tuple
from dotenv import load_dotenv

# 添加父目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 添加當前目錄以便導入同級模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.config import embeddings

# 🆕 導入統一 Metadata 標準
from unified_metadata import (
    normalize_metadata,
    format_unified_citation,
    create_unified_doc_data
)

load_dotenv()

# 🔒 全局鎖：保護 PGVector 初始化（避免並行時的 SQLAlchemy 表定義衝突）
_vectorstore_init_lock = threading.Lock()

# 🗃️ 向量資料庫緩存：避免重複初始化同一個 collection
_vectorstore_cache: Dict[str, PGVector] = {}


# ========================================
# 檔名正規化函數（已移至 unified_metadata.py）
# ========================================
# normalize_source_filename() 已從 unified_metadata 導入

# ========================================
# 統一的來源標註函數（已移至 unified_metadata.py）
# ========================================

def format_source_citation(doc_type: str, metadata: dict) -> str:
    """
    統一的來源標註格式（向後兼容版本）

    ⚠️ 已廢棄：建議使用 unified_metadata.format_unified_citation()
    此函數保留以向後兼容，內部調用新的統一標準

    Args:
        doc_type: 'pdf', 'jsonl', 或 'auto'（自動檢測）
        metadata: 文檔的 metadata 字典

    Returns:
        統一格式的來源標註
    """
    # 使用新的統一標準處理
    normalized = normalize_metadata(metadata)
    return format_unified_citation(normalized)


# ========================================
# 文件載入與轉換
# ========================================

def load_json_files_from_folder(folder_path: str) -> List[Dict[Any, Any]]:
    """從資料夾載入所有JSONL檔案"""
    json_data = []
    
    if not os.path.exists(folder_path):
        print(f"資料夾不存在: {folder_path}")
        return json_data
    
    for filename in os.listdir(folder_path):
        if filename.endswith('.jsonl'):
            file_path = os.path.join(folder_path, filename)
            line_count = 0
            try:
                with open(file_path, 'r', encoding='utf-8') as file:
                    for line in file:
                        line = line.strip()
                        if line:
                            data = json.loads(line)
                            json_data.append(data)
                            line_count += 1
                print(f"成功載入: {filename}, 包含 {line_count} 筆資料")
            except Exception as e:
                print(f"載入檔案 {filename} 時發生錯誤: {e}")
    
    return json_data


def json_to_documents(json_data_list: List[Dict[Any, Any]]) -> List[Document]:
    """將JSON資料轉換為Document對象"""
    documents = []
    
    for json_data in json_data_list:
        content_parts = []
        
        if 'text' in json_data:
            content_parts.append(json_data['text'])
        
        metadata = json_data.get('metadata', {})
        
        if metadata.get('title'):
            content_parts.append(f"標題: {metadata['title']}")
        
        if metadata.get('keywords'):
            content_parts.append(f"關鍵字: {metadata['keywords']}")
            
        if metadata.get('reference'):
            content_parts.append(f"參考資料: {metadata['reference']}")
            
        if metadata.get('source_file'):
            content_parts.append(f"檔案名稱: {metadata['source_file']}")
        
        page_content = "\n".join(content_parts)
        
        document = Document(
            page_content=page_content,
            metadata={
                "id": json_data.get('id', ''),
                "source_file": metadata.get('source_file', ''),
                "sheet_name": metadata.get('sheet_name', ''),
                "title": metadata.get('title', ''),
                "keywords": metadata.get('keywords', ''),
                "reference": metadata.get('reference', ''),
                "original_text": json_data.get('text', '')
            }
        )
        documents.append(document)
    
    return documents


# ========================================
# 向量資料庫操作
# ========================================

def load_existing_vectordb(db_connection_string: str, collection_name: str = "medical_knowledge") -> PGVector:
    """
    載入現有的PostgreSQL向量資料庫（線程安全版本）

    使用緩存和鎖機制避免並行初始化時的 SQLAlchemy 表定義衝突
    """
    # 檢查緩存
    cache_key = f"{db_connection_string}::{collection_name}"

    if cache_key in _vectorstore_cache:
        return _vectorstore_cache[cache_key]

    # 使用鎖保護初始化過程
    with _vectorstore_init_lock:
        # 雙重檢查：可能在等待鎖的過程中，其他線程已經初始化了
        if cache_key in _vectorstore_cache:
            return _vectorstore_cache[cache_key]

        # 初始化向量資料庫
        vectorstore = PGVector(
            embeddings=embeddings,
            connection=db_connection_string,
            collection_name=collection_name,
        )

        # 存入緩存
        _vectorstore_cache[cache_key] = vectorstore

        return vectorstore


def search_vectordb_with_scores(vectorstore: PGVector, query: str, k: int = 5) -> List[Tuple[Document, float]]:
    """搜索PostgreSQL向量資料庫並返回相似度分數"""
    try:
        if vectorstore is None:
            print("向量資料庫為空")
            return []

        results = vectorstore.similarity_search_with_score(query, k=k)
        return results
    except Exception as e:
        print(f"向量資料庫搜尋失敗: {e}")
        return []


def clear_vectorstore_cache():
    """
    清除向量資料庫緩存

    在以下情況使用：
    - 資料庫連接參數改變
    - 需要強制重新初始化
    - 記憶體清理
    """
    global _vectorstore_cache
    with _vectorstore_init_lock:
        _vectorstore_cache.clear()
        print("✅ 向量資料庫緩存已清除")


# ========================================
# 結果格式化 - Markdown 版本（統一版）
# ========================================

def get_structured_search_results(
    results: List[Tuple],
    query: str,
    top_n: int = 5,
    show_scores: bool = False,
    format_type: str = "markdown"
) -> Tuple[Dict[str, Any], str]:
    """
    將檢索結果格式化為結構化數據 + Markdown 文本（統一版）
    ✅ v2.0: 使用統一 Metadata 標準
    ✅ 自動支援所有資料源格式（Excel, PDF, OCR PDF）

    Args:
        results: LangChain 檢索結果 [(Document, score), ...]
        query: 用戶問題
        top_n: 返回前 N 筆結果
        show_scores: 是否顯示相似度分數
        format_type: "markdown" 或 "json"

    Returns:
        Tuple[Dict, str]: (結構化數據字典, 格式化顯示字符串)
    """
    # 只取前 top_n 筆
    limited_results = results[:top_n] if len(results) > top_n else results

    if not limited_results:
        empty_dict = {
            'query': query,
            'total_results': 0,
            'documents': []
        }
        return empty_dict, "未找到相關資料。"

    # 按相似度分數排序（分數越小越相似）
    sorted_results = sorted(limited_results, key=lambda x: x[1])

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
        display_text = _format_jsonl_markdown(sorted_results, query, show_scores)

    return structured_data, display_text


def _format_jsonl_markdown(
    results: List[Tuple],
    query: str,
    show_scores: bool = False
) -> str:
    """
    將檢索結果格式化為 Markdown 格式（統一版）
    ✅ 自動支援 Excel 和 PDF 格式
    ✅ 自動將 xlsx 檔名還原為 pdf 檔名
    
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
        title = metadata.get('title', '')
        keywords = metadata.get('keywords', '')
        # 優先讀取 original_full_text（包含問題+答案），否則使用 original_text
        original_text = metadata.get('original_full_text', metadata.get('original_text', doc.page_content))
        
        # 文檔標題
        output.append(f"## 資料 {i}")
        
        # 只顯示有效的標題（過濾預設值）
        if title and title != 'CGMH(All Right Reserved)':
            output.append(f"\n**問題**：{title}")
        
        # 內容
        if original_text and original_text.strip():
            output.append(f"\n**內容**：\n\n{original_text.strip()}")
        
        # 只顯示有效的關鍵字（過濾預設值）
        if keywords and keywords != 'CGMH(All Right Reserved)':
            output.append(f"\n**關鍵字**：{keywords}")
        
        # ✅ 使用 'auto' 自動檢測並格式化來源 (已包含檔名正規化)
        citation = format_source_citation('auto', metadata)
        output.append(f"\n**來源**：{citation}")
        
        # 分數（可選）
        if show_scores:
            output.append(f"\n**相似度分數**：{score:.4f}")
        
        output.append("\n---\n")
    
    return "\n".join(output)


# ========================================
# 測試代碼
# ========================================

# ========================================
# 簡短測試 search_vectordb_with_scores
# ========================================

if __name__ == "__main__":
    DB_HOST = "172.23.37.2"
    DB_PORT = "5432"
    DB_NAME = "infection_rag"
    #DB_USER = "a1031737"
    DB_USER = "langchain"
    DB_PASSWORD = "langchain"
    # DB_PASSWORD = "a156277323"
    DB_CONNECTION = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    if not DB_CONNECTION:
        print("錯誤：未設定 DATABASE_URL 環境變數")
        exit(1)

    try:
        # 載入現有向量資料庫 - 使用正確的 collection 名稱
        # "medical_knowledge" 是空的，應該使用 "medical_knowledge_base"
        vectorstore = load_existing_vectordb(DB_CONNECTION, collection_name="medical_knowledge_base")

        # 執行搜尋
        query = "非接觸性皮膚炎或接觸性皮膚炎發癢性皮疹"
        results = search_vectordb_with_scores(vectorstore, query, k=5)

        print(f"\n搜尋查詢: 「{query}」")
        print(f"找到 {len(results)} 筆結果\n")

        if results:
            for i, (doc, score) in enumerate(results, 1):
                print(f"--- 結果 {i} (分數: {score:.4f}) ---")

                # 顯示問題
                title = doc.metadata.get('title', '')
                if title:
                    print(f"問題: {title}")

                # 顯示答案（這是關鍵！）
                answer = doc.metadata.get('original_text', '')
                if answer:
                    print(f"答案: {answer}")

                # 顯示關鍵字
                keywords = doc.metadata.get('keywords', '')
                if keywords:
                    print(f"關鍵字: {keywords}")

                # 顯示來源
                citation = format_source_citation('auto', doc.metadata)
                print(f"來源: {citation}")
                print()
        else:
            print("❌ 沒有找到任何結果")
            print("\n提示：請檢查：")
            print("1. collection_name 是否正確")
            print("2. embedding 模型是否與建立向量庫時使用的相同")
            print("3. 資料庫中是否有資料")

    except Exception as e:
        print(f"測試失敗: {e}")
        import traceback
        traceback.print_exc()