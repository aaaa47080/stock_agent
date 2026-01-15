"""
表格匹配模組
當 OCR 結果包含表格時，自動匹配 extracted_tables 中的乾淨表格
"""
import os
import re
import glob
from difflib import SequenceMatcher

# 使用集中化配置
from core.config import EXTRACTED_TABLES_DIR


def has_table_format(text: str) -> bool:
    """
    判斷文本中是否包含表格或圖片格式

    表格/圖片特徵：
    - Markdown 表格: | xxx | xxx |
    - 連續的 | 符號
    - 表頭分隔線: |---|---|
    - HTML 表格標籤: <table>
    - HTML 圖片標籤: <img> 或 <div class="image">
    - Markdown 圖片標記: ## image, ## figure, ## chart, ## diagram, ## 表格
    """
    if not text:
        return False

    # 檢查 Markdown 表格格式
    # 至少有 2 行包含 | 符號
    lines_with_pipe = [line for line in text.split('\n') if '|' in line and line.count('|') >= 2]

    if len(lines_with_pipe) >= 2:
        return True

    # 檢查表格分隔線
    if re.search(r'\|[\s\-:]+\|', text):
        return True

    # 檢查 HTML 表格標籤殘留
    if '<table>' in text.lower() or '</table>' in text.lower():
        return True

    # 🆕 檢查 HTML 圖片標籤
    if '<img' in text.lower() or 'class="image"' in text.lower():
        return True

    # 🆕 檢查 Markdown 圖片/表格標記（OCR 處理時添加的）
    # 匹配 ## image, ## figure, ## chart, ## diagram, ## table, ## 表格 等
    if re.search(r'^##\s*(image|figure|chart|diagram|table|表格)', text, re.MULTILINE | re.IGNORECASE):
        return True

    return False


def extract_table_content(text: str) -> list:
    """
    從文本中提取表格內容（用於匹配）

    支援兩種格式：
    1. HTML 表格: <table>...</table>
    2. Markdown 表格: | xxx | xxx |

    Returns:
        list: 表格文本片段列表
    """
    tables = []

    # 優先提取 HTML 表格
    html_table_pattern = r'<table>.*?</table>'
    html_tables = re.findall(html_table_pattern, text, re.DOTALL | re.IGNORECASE)
    if html_tables:
        tables.extend(html_tables)

    # 也嘗試提取 Markdown 表格
    lines = text.split('\n')
    current_table = []
    in_table = False

    for line in lines:
        # 判斷是否為表格行
        if '|' in line and line.count('|') >= 2:
            in_table = True
            current_table.append(line)
        else:
            if in_table and current_table:
                # 表格結束
                tables.append('\n'.join(current_table))
                current_table = []
                in_table = False

    # 處理最後一個表格
    if current_table:
        tables.append('\n'.join(current_table))

    return tables


def normalize_table_text(text: str) -> str:
    """
    正規化表格文本，用於比較
    - 移除空白
    - 移除格式符號
    - 統一小寫
    """
    # 移除 Markdown 表格符號
    text = re.sub(r'\|', ' ', text)
    text = re.sub(r'[-:]+', ' ', text)
    # 移除多餘空白
    text = re.sub(r'\s+', ' ', text)
    # 移除 HTML 標籤
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip().lower()


def calculate_similarity(text1: str, text2: str) -> float:
    norm1 = normalize_table_text(text1)
    norm2 = normalize_table_text(text2)

    # Debug: 看看實際在比什麼
    print(f"[DEBUG] norm1 ({len(norm1)} chars): {norm1[:100]}...")
    print(f"[DEBUG] norm2 ({len(norm2)} chars): {norm2[:100]}...")

    if not norm1 or not norm2:
        return 0.0

    score = SequenceMatcher(None, norm1, norm2).ratio()
    print(f"[DEBUG] similarity: {score}")
    return score


def find_matching_table(ocr_table_content: str, source_file: str = None, page_num: int = None) -> dict:
    """
    根據 OCR 表格內容，找到匹配的乾淨表格

    Args:
        ocr_table_content: OCR 提取的表格文本
        source_file: PDF 檔名（可選，用於縮小搜尋範圍）
        page_num: 頁碼（可選）

    Returns:
        dict: {
            'matched': True/False,
            'table_file': 檔名,
            'table_content': Markdown 內容,
            'image_path': JPG 路徑,
            'similarity': 相似度分數
        }
    """
    best_match = {
        'matched': False,
        'table_content': None,
        'image_path': None,
        'similarity': 0.0,
        'source': 'matching'  # 預設為匹配來源
    }

    # 決定搜尋範圍（統一在 images 資料夾中搜尋）
    images_dir = os.path.join(EXTRACTED_TABLES_DIR, "images")
    search_dirs = [images_dir] if os.path.exists(images_dir) else [EXTRACTED_TABLES_DIR]

    # 🔧 修改：搜尋 JPG 表格檔案（不再依賴 .md）
    for search_dir in search_dirs:
        if not os.path.exists(search_dir):
            continue

        # 如果有頁碼，優先搜尋該頁（支援表格_t和圖片_i）
        if page_num and source_file:
            pdf_name = source_file.replace('.pdf', '')
            # 🔧 修改：同時搜尋 _t（表格）和 _i（圖片）
            patterns = [
                os.path.join(search_dir, f"*_p{page_num}_t*.jpg"),
                os.path.join(search_dir, f"*_p{page_num}_i*.jpg")
            ]
        else:
            patterns = [os.path.join(search_dir, "*.jpg")]

        # 對每個pattern進行搜尋
        all_jpg_files = []
        for pattern in patterns:
            all_jpg_files.extend(glob.glob(pattern))

        for jpg_path in all_jpg_files:
            try:
                # 🔧 讀取對應的 HTML 檔案來計算相似度
                html_path = jpg_path.replace('.jpg', '.html')
                if not os.path.exists(html_path):
                    continue

                with open(html_path, 'r', encoding='utf-8') as f:
                    clean_table_content = f.read()

                # 計算相似度
                similarity = calculate_similarity(ocr_table_content, clean_table_content)

                if similarity > best_match['similarity']:
                    best_match = {
                        'matched': similarity > 0.05,  # 相似度閾值（降低以增加匹配機會）
                        'table_content': clean_table_content,
                        'image_path': jpg_path,
                        'similarity': similarity,
                        'source': 'matching'  # 標記為相似度匹配來源
                    }

            except Exception as e:
                continue

    # 如果沒找到，擴大搜尋到 images 目錄的所有檔案
    if not best_match['matched']:
        images_dir = os.path.join(EXTRACTED_TABLES_DIR, "images")

        if os.path.exists(images_dir):
            # 🔧 修改：搜尋 JPG 檔案
            for jpg_path in glob.glob(os.path.join(images_dir, "*.jpg")):
                try:
                    # 🔧 讀取對應的 HTML 檔案
                    html_path = jpg_path.replace('.jpg', '.html')
                    if not os.path.exists(html_path):
                        continue

                    with open(html_path, 'r', encoding='utf-8') as f:
                        clean_table_content = f.read()

                    similarity = calculate_similarity(ocr_table_content, clean_table_content)

                    if similarity > best_match['similarity']:
                        best_match = {
                            'matched': similarity > 0.05,
                            'table_content': clean_table_content,
                            'image_path': jpg_path,
                            'similarity': similarity,
                            'source': 'matching'  # 標記為相似度匹配來源
                        }

                except Exception:
                    continue

    return best_match


def process_search_result(content: str, source_file: str = None, page_num: int = None, 
                          metadata: dict = None) -> dict:
    """
    處理搜尋結果，自動判斷是否需要匹配表格

    Args:
        content: OCR 搜尋結果內容
        source_file: 來源檔案
        page_num: 頁碼
        metadata: RAG 搜尋結果的 metadata（可能包含 table_images）

    Returns:
        dict: {
            'has_table': bool,
            'matched_tables': list of matched table info
        }
    """
    result = {
        'has_table': False,
        'matched_tables': []
    }

    # ===== 方案 1: 優先從 metadata 取得表格圖片（精確匹配）=====
    if metadata:
        has_table = metadata.get('has_table', False)
        table_images = metadata.get('table_images', [])

        # 如果是字串（JSON），轉換為 list
        if isinstance(table_images, str):
            import json
            try:
                table_images = json.loads(table_images)
            except:
                table_images = []

        # 🔧 修正：只要 table_images 不為空就應該顯示（不管 has_table 的值）
        # 因為圖片類型的文件 has_table 可能是 False，但仍有 table_images
        if table_images:
            result['has_table'] = True
            for img_path in table_images:
                # 讀取對應的 HTML 內容（如果需要）
                html_path = img_path.replace('.jpg', '.html')
                html_content = None
                if os.path.exists(html_path):
                    try:
                        with open(html_path, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                    except:
                        pass
                
                result['matched_tables'].append({
                    'matched': True,
                    'table_content': html_content,
                    'image_path': img_path,
                    'similarity': 1.0,  # metadata 精確匹配
                    'source': 'metadata'  # 標記來源是 metadata
                })
            
            print(f"   ✅ 從 metadata 直接取得 {len(table_images)} 個表格圖片（無需相似度匹配）")
            return result

    # ===== 方案 2: Fallback - 用相似度匹配（當 metadata 沒有時）=====
    # 判斷是否包含表格
    if not has_table_format(content):
        return result

    result['has_table'] = True

    # 提取表格內容
    tables = extract_table_content(content)

    # 對每個表格嘗試匹配
    for table_text in tables:
        match = find_matching_table(table_text, source_file, page_num)
        if match['matched']:
            result['matched_tables'].append(match)

    return result

# 測試
if __name__ == "__main__":
    # 測試文本（模擬 OCR 結果包含表格）
    test_ocr_content = """
    第七版國人膳食營養素參考攝取量建議...

    | 中文名稱 | 英文名稱 | 飽和脂肪酸(g) |
    |---|---|---|
    | 橄欖油 | Olive oil | 16.3 |
    | 椰子油 | Coconut oil | 90.1 |

    以上為常見油脂類的脂肪酸組成。
    """

    print("="*60)
    print("測試表格匹配")
    print("="*60)

    # 檢查是否有表格
    print(f"\n1. 是否包含表格: {has_table_format(test_ocr_content)}")

    # 提取表格
    tables = extract_table_content(test_ocr_content)
    print(f"\n2. 提取到 {len(tables)} 個表格")

    # 匹配
    if tables:
        print("\n3. 嘗試匹配...")
        match = find_matching_table(
            tables[0],
            source_file="「國人膳食營養素參考攝取量」第八版-脂質.pdf"
        )
        print(f"   匹配結果: {match['matched']}")
        print(f"   相似度: {match['similarity']:.4f}")
        print(f"   圖片路徑: {match['image_path']}")
