#!/usr/bin/env python3
"""
表格/圖片直接查找工具
當用戶輸入檔名時，直接顯示對應的表格或圖片
"""
import os
import re

from core.config import EXTRACTED_TABLES_DIR


def is_table_filename(query: str) -> bool:
    """
    判斷用戶輸入是否為表格/圖片檔名

    支援的格式：
    - xxx_p3_i1.html
    - xxx_p3_i1.jpg
    - xxx_p10_t1.html
    - xxx_p10_t1.jpg
    - p3_i1
    - p10_t1
    """
    # 檢查是否包含 _p數字_t數字 或 _p數字_i數字 的格式
    if re.search(r'_p\d+_[ti]\d+', query):
        return True

    # 檢查是否為簡化格式 p數字_t數字 或 p數字_i數字
    if re.search(r'^p\d+_[ti]\d+', query):
        return True

    # 檢查是否為HTML或JPG檔名
    if query.endswith(('.html', '.jpg', '.jpeg', '.png')):
        return True

    return False


def find_table_image_by_filename(query: str) -> dict:
    """
    根據檔名查找表格/圖片

    Args:
        query: 檔名或部分檔名

    Returns:
        dict: {
            'found': True/False,
            'image_path': 圖片完整路徑,
            'html_path': HTML完整路徑,
            'html_content': HTML內容,
            'filename': 檔名,
            'matches': 所有匹配的檔案列表
        }
    """
    result = {
        'found': False,
        'image_path': None,
        'html_path': None,
        'html_content': None,
        'filename': None,
        'matches': []
    }

    # 清理檔名（移除路徑、只保留檔名部分）
    clean_query = os.path.basename(query)
    clean_query = clean_query.replace('.html', '').replace('.jpg', '').replace('.jpeg', '').replace('.png', '')

    print(f"🔍 搜尋檔名: {clean_query}")

    # 在extracted_tables目錄及其子目錄中搜尋
    for root, dirs, files in os.walk(EXTRACTED_TABLES_DIR):
        for file in files:
            # 檢查是否匹配（支援部分匹配）
            if clean_query.lower() in file.lower():
                file_path = os.path.join(root, file)

                # 判斷是圖片還是HTML
                if file.endswith(('.jpg', '.jpeg', '.png')):
                    image_path = file_path
                    html_path = file_path.replace('.jpg', '.html').replace('.jpeg', '.html').replace('.png', '.html')

                    result['matches'].append({
                        'image_path': image_path,
                        'html_path': html_path if os.path.exists(html_path) else None,
                        'filename': file
                    })

                elif file.endswith('.html'):
                    html_path = file_path
                    # 嘗試找對應的圖片
                    for ext in ['.jpg', '.jpeg', '.png']:
                        image_path = html_path.replace('.html', ext)
                        if os.path.exists(image_path):
                            break
                    else:
                        image_path = None

                    result['matches'].append({
                        'image_path': image_path,
                        'html_path': html_path,
                        'filename': file
                    })

    # 如果找到匹配，選擇第一個
    if result['matches']:
        result['found'] = True
        first_match = result['matches'][0]
        result['image_path'] = first_match['image_path']
        result['html_path'] = first_match['html_path']
        result['filename'] = first_match['filename']

        # 讀取HTML內容
        if result['html_path'] and os.path.exists(result['html_path']):
            try:
                with open(result['html_path'], 'r', encoding='utf-8') as f:
                    result['html_content'] = f.read()
            except Exception as e:
                print(f"⚠️ 讀取HTML失敗: {e}")

        print(f"✅ 找到 {len(result['matches'])} 個匹配檔案")
        print(f"   第一個匹配: {result['filename']}")
        if result['image_path']:
            print(f"   圖片路徑: {result['image_path']}")
        if result['html_path']:
            print(f"   HTML路徑: {result['html_path']}")
    else:
        print(f"❌ 未找到匹配的檔案")

    return result


def format_table_image_response(result: dict) -> str:
    """
    格式化表格/圖片顯示的回應

    Args:
        result: find_table_image_by_filename 的返回結果

    Returns:
        str: 格式化的Markdown回應（包含圖片顯示）
    """
    if not result['found']:
        return "抱歉，未找到您指定的表格或圖片。"

    response_parts = []

    # 顯示檔案資訊
    response_parts.append(f"找到檔案：**{result['filename']}**")

    # 如果有多個匹配，顯示提示
    if len(result['matches']) > 1:
        response_parts.append(f"\n（找到 {len(result['matches'])} 個相關檔案，顯示第一個）")

    # 顯示HTML內容（文字版）
    if result['html_content']:
        # 簡單提取文字內容
        from bs4 import BeautifulSoup
        try:
            soup = BeautifulSoup(result['html_content'], 'html.parser')
            text = soup.get_text(separator='\n', strip=True)
            response_parts.append(f"\n**內容預覽：**\n{text[:500]}")
        except:
            pass

    # 顯示圖片路徑（供前端顯示）
    if result['image_path']:
        response_parts.append(f"\n**圖片路徑：** `{result['image_path']}`")
        response_parts.append("\n---")
        response_parts.append("💡 提示：前端應該根據此路徑顯示圖片")

    return '\n'.join(response_parts)


# 測試
if __name__ == "__main__":
    # 測試案例
    test_queries = [
        "「國人膳食營養素參考攝取量」第八版-+碘_p3_i1.html",
        "p3_i1",
        "碘_p3_i1",
    ]

    print("="*80)
    print("表格/圖片檔名查找測試")
    print("="*80)

    for query in test_queries:
        print(f"\n測試查詢: {query}")
        print("-"*80)

        # 檢查是否為檔名格式
        is_filename = is_table_filename(query)
        print(f"是否為檔名格式: {is_filename}")

        if is_filename:
            # 查找
            result = find_table_image_by_filename(query)

            # 格式化回應
            response = format_table_image_response(result)
            print(f"\n回應:\n{response}")
