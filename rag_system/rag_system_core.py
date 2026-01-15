import os
import sys
import asyncio
import re
from datetime import datetime

# 添加父目錄到 Python 路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 添加當前目錄以便導入同級模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_jsonl import load_existing_vectordb, search_vectordb_with_scores, get_structured_search_results
from rag_files import get_structured_pdf_results
from langchain_core.messages import HumanMessage, SystemMessage
from core.config import get_reference_mapping, llm, DB_NAME, DB_HOST, DB_PASSWORD, DB_PORT, DB_USER

# 全局 LLM 併發限制
# LLM_SEMAPHORE = asyncio.Semaphore(4)

def normalize_source_filename(filename):
    """
    將 xlsx 檔名還原為原始 PDF 檔名
    例如：
    - 發燒、咳嗽及腹瀉監測與自主健康管理作業準則_關鍵字詞.xlsx -> 發燒、咳嗽及腹瀉監測與自主健康管理作業準則.pdf
    - 新型A型流感感染管制照護指引.xlsx -> 新型A型流感感染管制照護指引.pdf
    """
    if not isinstance(filename, str):
        return filename
    
    # 移除 _關鍵字詞 後綴 (支援全形和半形底線)
    filename = re.sub(r'[_﹍]關鍵字詞', '', filename)
    
    # 將 .xlsx 替換為 .pdf
    if filename.endswith('.xlsx'):
        filename = filename[:-5] + '.pdf'
    elif filename.endswith('.XLSX'):
        filename = filename[:-5] + '.pdf'
    
    return filename

def post_process_response(response):
    if not isinstance(response, str):
        return response
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)
    lines = response.split('\n')
    cleaned_lines = []
    skip_think = False
    for line in lines:
        line_stripped = line.strip().lower()
        if line_stripped.startswith('think') or line_stripped.startswith('th'):
            skip_think = True
            continue
        elif line_stripped.endswith('think') or (skip_think and line_stripped == ''):
            skip_think = False
            continue
        elif not skip_think:
            cleaned_lines.append(line)
    result = '\n'.join(cleaned_lines).strip()
    result = re.sub(r'\n\s*\n', '\n', result)
    return result

def convert_references_to_english(chinese_ref):
    try:
        reference_mapping = get_reference_mapping()
        return reference_mapping.get(chinese_ref, "medical_knowledge_base")

    except Exception as e:
        print(f"讀取參考資料對照表時發生`錯誤: {e}")
        return reference_mapping.get(chinese_ref, "medical_knowledge_base")

async def async_generate_comprehensive_answer(json_results, pdf_results, query):
    """
    生成綜合回答 - 適配新的 Markdown 格式
    
    Args:
        json_results: dict - 包含 'documents' 列表的字典
        pdf_results: dict - 包含 'documents' 列表的字典
        query: str - 用戶查詢
    
    Returns:
        str - LLM 生成的回答
    """
    context_parts = []
    
    # 處理 JSON 結果 (新格式)
    if json_results and json_results.get('documents'):
        context_parts.append("=== Excel 結構化資料 ===\n")
        for i, doc in enumerate(json_results['documents'], 1):
            try:
                # 新格式: title, content, source 都在最外層
                title = doc.get('title', 'N/A')
                source = doc.get('source', {})
                raw_content = doc.get('content', 'N/A')
                # 移除以「參考」開頭，後接半形或全形冒號的整行
                content = re.sub(r'^參考[:：].*$', '', raw_content, flags=re.MULTILINE)
                # 清理多餘空行
                content = re.sub(r'\n\s*\n', '\n', content).strip()           
                # 提取來源資訊
                source_file = source.get('file', 'N/A')
                source_file = normalize_source_filename(source_file)  # 新增這行
                sheet_name = source.get('sheet', '')
                # reference = source.get('reference', 'N/A')
                
                context_parts.extend([
                    f"**資料 {i}**",
                    f"標題: {title}",
                    f"內容: {content}",
                    f"來源檔案: {source_file}",
                ])
                
                if sheet_name:
                    context_parts.append(f"工作表: {sheet_name}")
                
                # context_parts.append(f"參考: {reference}")
                context_parts.append("---\n")
                
            except Exception as e:
                print(f"處理 JSON 文檔 {i} 時發生錯誤: {e}")
                continue
    
    # 處理 PDF 結果 (新格式)
    if pdf_results and pdf_results.get('documents'):
        context_parts.append("=== PDF 文檔資料 ===\n")
        for i, doc in enumerate(pdf_results['documents'], 1):
            try:
                # 新格式: title, content, source 都在最外層
                title = doc.get('title', '')
                category = doc.get('category', 'N/A')
                content = doc.get('content', 'N/A')
                source = doc.get('source', {})
                
                # 提取來源資訊
                pdf_file = source.get('file', 'Unknown')
                page = source.get('page', 'N/A')
                
                context_parts.extend([
                    f"**資料 {i}**",
                    f"類別: {category}",
                ])
                
                if title:
                    context_parts.append(f"標題: {title}")
                
                context_parts.extend([
                    f"內容: {content[:500]}...",  # 限制長度避免超出 token
                    f"來源: PDF《{pdf_file}》第 {page} 頁",
                    "---\n"
                ])
                
            except Exception as e:
                print(f"處理 PDF 文檔 {i} 時發生錯誤: {e}")
                continue
    
    context = "\n".join(context_parts)
    
    # 如果沒有找到任何相關資料
    if not context_parts or len(context_parts) == 0:
        return "抱歉，未能在資料庫中找到與您問題相關的資料。"
    
    # 優化後的 System Prompt
    system_prompt = """你正在處理「RAG 向量資料庫檢索結果」，包含多筆來自不同來源的資料。

【核心任務】
將每一筆「與問題相關」的檢索結果分別整理成獨立的答案，不要整合或合併。

【處理規則】
1. **過濾無關資料**：
   - 只處理與用戶問題「明確相關」的資料
   - 完全跳過與問題無關的資料，不要輸出任何內容
   - 不要輸出「此條資料與問題無關」這類標註

2. **逐條處理**：每筆相關的檢索資料都要單獨處理，產生一個獨立的答案段落

3. **禁止整合**：不要將多個來源的資訊合併成一個答案

4. **保留來源標記**：每個答案段落必須保留其原始的【參考資料來源：...】標記

5. **忠實轉述**：僅根據原文內容進行摘要，不添加推論或外部知識

【輸出格式】
只輸出相關來源的答案，格式如下：

【輸出格式】
**參考依據**
《文件名稱1》-答案內容1（僅提取與問題相關的資訊）
《文件名稱2》-答案內容2（僅提取與問題相關的資訊）

【重要】
- 如果所有資料都與問題無關，直接回覆「（內容與問題無關）」
- 不要在開頭或結尾添加任何總結、前言或解釋
- 不要輸出無關資料的任何資訊"""

    user_message = f"""# 用戶問題

{query}

# 檢索到的相關資料

{context}

請根據上述資料回答用戶問題。"""

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ]
        response = await llm.ainvoke(messages)
        return post_process_response(response.content)
    except Exception as e:
        return f"生成回答時發生錯誤：{str(e)}"

async def async_save_results(query, final_answer):
    """Async 版本：保存結果到文件"""
    loop = asyncio.get_running_loop()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
    safe_query = safe_query.replace(' ', '_')[:30]
    filename = f"AI回答_{safe_query}_{timestamp}.txt"
    
    def _save():
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"問題：{query}\n")
                f.write("="*50 + "\n")
                f.write(final_answer)
            return filename
        except Exception as e:
            print(f"保存失敗: {e}")
            return None
    
    return await loop.run_in_executor(None, _save)

async def search_medical_knowledge_async(query, k_value=5):
    """
    非同步版本的主要搜索函數
    
    Args:
        query: 搜索查詢字串
        k_value: 返回結果數量
    
    Returns:
        str: 最終回答
    """
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
    db_connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    try:
        loop = asyncio.get_running_loop()
        
        # 載入 JSON 向量庫
        print("載入 JSON 向量資料庫...")
        vectorstore = await loop.run_in_executor(
            None, load_existing_vectordb, db_connection_string, "medical_knowledge_base"
        )
        
        if not vectorstore:
            return "向量資料庫載入失敗"

        # 搜索 JSON
        print(f"搜索 JSON 資料庫，查詢: {query}")
        results_with_scores = search_vectordb_with_scores(vectorstore, query, k=k_value)
        
        if not results_with_scores:
            return "未找到相關的 JSON 結果"
        
        # 獲取結構化結果 (新格式: tuple of (dict, markdown_str))
        json_results, json_markdown = get_structured_search_results(
            results_with_scores, 
            query, 
            top_n=k_value,
            show_scores=False,  # 不顯示分數,減少噪音
            format_type="markdown"
        )
        
        print(f"✅ JSON 檢索完成，找到 {json_results.get('total_results', 0)} 筆結果")

        # 搜索 PDF
        pdf_results = {}
        if json_results and json_results.get('documents') and len(json_results['documents']) > 0:
            print("搜索 PDF 資料庫...")
            try:
                # 從新格式中獲取 reference
                first_doc = json_results['documents'][0]
                source = first_doc.get('source', {})
                selected_reference = source.get('reference', '')
                if selected_reference:
                    collection_name_pdf = convert_references_to_english(selected_reference)
                    print(f"搜索 PDF 資料庫: {collection_name_pdf}")
                    
                    pdf_vectorstore = await loop.run_in_executor(
                        None, load_existing_vectordb, db_connection_string, collection_name_pdf
                    )
                    
                    if pdf_vectorstore:
                        pdf_results_with_scores = search_vectordb_with_scores(
                            pdf_vectorstore, query, k=k_value
                        )
                        if pdf_results_with_scores:
                            pdf_results, pdf_markdown = get_structured_pdf_results(
                                pdf_results_with_scores, 
                                query,
                                show_scores=False,
                                format_type="markdown"
                            )
                            print(f"✅ PDF 檢索完成，找到 {pdf_results.get('total_results', 0)} 筆結果")
            except Exception as e:
                print(f"搜索 PDF 時發生錯誤: {e}")
                pdf_results = {}

        # 生成回答
        print("生成最終回答...")
        print(json_results)
        final_answer = await async_generate_comprehensive_answer(json_results, pdf_results, query)

        return final_answer

    except Exception as e:
        error_msg = f"搜索過程發生錯誤：{str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        return error_msg

# 向下相容：保留原始同步介面
def search_medical_knowledge(query, k_value=1):
    """同步介面（用於非 async 環境）"""
    return asyncio.run(search_medical_knowledge_async(query, k_value))

# 測試用
if __name__ == "__main__":
    query = "非接觸性皮膚炎或接觸性皮膚炎發癢性皮疹"
    result = asyncio.run(search_medical_knowledge_async(query, k_value=1))
    print("\n" + "="*60)
    print("最終結果:")
    print("="*60)
    print(result)