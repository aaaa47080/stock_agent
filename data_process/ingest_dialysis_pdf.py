"""
更新 PDF 到資料庫 V2.1 (修復版)-處理洗腎科相關資料庫

整合改進版表格擷取方法：
- 全寬度裁切策略
- 自動合併重疊表格
- 支援表格、圖片、圖表等多種物件類型
- 🆕 修復：純圖片/圖表強制寫入向量索引與 Metadata，確保可被檢索
"""
import os
import sys
from pathlib import Path
import tempfile
import time
import argparse
import gc
from io import StringIO, BytesIO

sys.path.append(str(Path(__file__).parent.parent))

from transformers import AutoModel, AutoTokenizer
import torch
import fitz
from PIL import Image
import re

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from core.config import DB_HOST, DB_NAME, DB_PORT, DB_PASSWORD, DB_USER, embeddings


# ==================== 配置 ====================
os.environ["CUDA_VISIBLE_DEVICES"] = '0'
os.environ["CUDA_LAUNCH_BLOCKING"] = '1'

MODEL_PATH = '/home/danny/AI-agent/deepseek_ocr'
INPUT_DIR = '/home/danny/AI-agent/洗腎衛教'
COLLECTION_NAME = "dialysis_education_materials"
db_connection = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# 表格擷取輸出目錄
from core.config import EXTRACTED_TABLES_DIR

# ==================== 參數設置 ====================
OCR_IMAGE_SIZE = 1024      # OCR 處理尺寸
HIGH_RES_DPI = 100         # 高解析度表格輸出 DPI
MIN_IMAGE_SIZE = 100       # 最小圖片尺寸過濾
SKIP_FIRST_PAGE_IMAGES = False  # 是否跳過第一頁的圖片

text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=1200,
    chunk_overlap=200
)


# ==================== GPU 清理 ====================
def cleanup_gpu():
    """清理 GPU 記憶體"""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


# ==================== OCR 輔助函數 ====================

def capture_model_output():
    """捕獲模型的標準輸出"""
    old_stdout = sys.stdout
    sys.stdout = captured_output = StringIO()
    return old_stdout, captured_output


def restore_stdout(old_stdout):
    """恢復標準輸出"""
    sys.stdout = old_stdout


def extract_from_stdout(captured_text):
    """從捕獲的輸出中提取表格標記"""
    start_marker = '<|ref|>'
    if start_marker not in captured_text:
        return None

    start_pos = captured_text.find(start_marker)
    end_marker = '===============save results:==============='
    end_pos = captured_text.find(end_marker)

    if end_pos == -1:
        relevant_text = captured_text[start_pos:]
    else:
        relevant_text = captured_text[start_pos:end_pos]

    return relevant_text.strip()


def extract_tables_and_images_from_result(result_text):
    """從 OCR 結果中提取表格和圖片區域"""
    all_objects = []

    # 通用模式:匹配 <|ref|>TYPE<|/ref|><|det|>[[x1, y1, x2, y2]]<|/det|>
    object_pattern = r'<\|ref\|>(\w+)<\|/ref\|><\|det\|>\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]<\|/det\|>'
    object_matches = re.findall(object_pattern, result_text)

    for match in object_matches:
        obj_type = match[0]
        x1, y1, x2, y2 = int(match[1]), int(match[2]), int(match[3]), int(match[4])

        # 只處理表格和圖片相關類型
        if obj_type in ['table', 'image', 'figure', 'chart', 'diagram']:
            obj_data = {
                'bbox': (x1, y1, x2, y2),
                'type': obj_type,
                'html': None
            }

            # 如果是表格,嘗試提取 HTML
            if obj_type == 'table':
                search_str = f'[[{x1}, {y1}, {x2}, {y2}]]'
                search_start = result_text.find(search_str)
                if search_start != -1:
                    table_start = result_text.find('<table>', search_start)
                    if table_start != -1:
                        table_end = result_text.find('</table>', table_start)
                        if table_end != -1:
                            obj_data['html'] = result_text[table_start:table_end + 8]

            all_objects.append(obj_data)

    # 提取標題(table_caption, figure_caption 等)
    caption_pattern = r'<\|ref\|>(\w+_caption)<\|/ref\|><\|det\|>\[\[(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\]\]<\|/det\|>\s*\n?(.*?)(?=\n\n|\n<\||$)'
    caption_matches = re.findall(caption_pattern, result_text, re.DOTALL)

    captions = []
    for match in caption_matches:
        captions.append({
            'bbox': (int(match[1]), int(match[2]), int(match[3]), int(match[4])),
            'text': match[5].strip(),
            'type': match[0]
        })

    return all_objects, captions


def calculate_bbox_overlap(bbox1, bbox2):
    """計算兩個 bbox 的重疊比例"""
    x1_1, y1_1, x2_1, y2_1 = bbox1
    x1_2, y1_2, x2_2, y2_2 = bbox2

    intersect_x1 = max(x1_1, x1_2)
    intersect_y1 = max(y1_1, y1_2)
    intersect_x2 = min(x2_1, x2_2)
    intersect_y2 = min(y2_1, y2_2)

    if intersect_x1 >= intersect_x2 or intersect_y1 >= intersect_y2:
        return 0.0

    intersect_area = (intersect_x2 - intersect_x1) * (intersect_y2 - intersect_y1)
    area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
    area2 = (x2_2 - x1_2) * (y2_2 - y1_2)

    smaller_area = min(area1, area2)
    return intersect_area / smaller_area if smaller_area > 0 else 0.0


def merge_overlapping_objects(objects_data, overlap_threshold=0.3):
    """合併重疊的表格物件"""
    if not objects_data:
        return objects_data

    tables = [obj for obj in objects_data if obj['type'] == 'table']
    other_objects = [obj for obj in objects_data if obj['type'] != 'table']

    if len(tables) <= 1:
        return objects_data

    tables.sort(key=lambda obj: obj['bbox'][1])

    merged_tables = []
    skip_indices = set()

    for i, table1 in enumerate(tables):
        if i in skip_indices:
            continue

        bbox1 = table1['bbox']
        x1_1, y1_1, x2_1, y2_1 = bbox1

        for j in range(i + 1, len(tables)):
            if j in skip_indices:
                continue

            table2 = tables[j]
            bbox2 = table2['bbox']
            x1_2, y1_2, x2_2, y2_2 = bbox2

            y_overlap_start = max(y1_1, y1_2)
            y_overlap_end = min(y2_1, y2_2)
            y_overlap = max(0, y_overlap_end - y_overlap_start)

            height1 = y2_1 - y1_1
            height2 = y2_2 - y1_2
            smaller_height = min(height1, height2)

            vertical_overlap_ratio = y_overlap / smaller_height if smaller_height > 0 else 0
            horizontal_gap = min(abs(x2_1 - x1_2), abs(x2_2 - x1_1))

            if vertical_overlap_ratio > overlap_threshold and horizontal_gap < 100:
                merged_bbox = (
                    min(x1_1, x1_2),
                    min(y1_1, y1_2),
                    max(x2_1, x2_2),
                    max(y2_1, y2_2)
                )

                table1['bbox'] = merged_bbox
                skip_indices.add(j)

        merged_tables.append(table1)

    return merged_tables + other_objects


def find_related_caption(object_bbox, object_type, captions, max_distance=100):
    """尋找物件對應的標題"""
    object_y1 = object_bbox[1]
    best_caption = None
    min_distance = max_distance

    caption_type_map = {
        'table': 'table_caption',
        'figure': 'figure_caption',
        'image': 'figure_caption',
        'chart': 'figure_caption',
        'diagram': 'figure_caption',
    }
    target_caption_type = caption_type_map.get(object_type, f'{object_type}_caption')

    for caption in captions:
        if caption['type'] != target_caption_type:
            continue

        caption_y2 = caption['bbox'][3]
        if caption_y2 < object_y1:
            distance = object_y1 - caption_y2
            if distance < min_distance:
                min_distance = distance
                best_caption = caption['text']

    return best_caption


def is_references_section(text):
    """
    檢測文本是否為參考文獻區塊

    Returns:
        tuple: (is_references: bool, references_start_pos: int or None)
               如果是參考文獻區塊，返回 (True, 開始位置)
               如果不是，返回 (False, None)
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
        r'(^|\n)\s*#{0,3}\s*文[獻献]',
    ]

    for pattern in ref_title_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return True, match.start()

    # 檢測是否整頁都是引用格式（沒有標題但內容是引用）
    lines = text.strip().split('\n')
    citation_count = 0
    total_lines = 0

    citation_patterns = [
        r'^\d+\.\s*[A-Z][a-z]+\s+[A-Z]{1,2}',  # 1. Smith AB...
        r'^\d+\.\s*[A-Z]{2,}[\.\s]',  # 1. WHO...
        r'^\[\d+\]',  # [1]
        r'J\s+(Clin\s+)?Endocrinol',  # Journal names
        r'\d{4}[;:]\d+[-–]\d+',  # 年份;頁碼 如 2004;35:241-249
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

    # 如果超過 60% 的行是引用格式，判定為參考文獻頁
    if total_lines > 5 and citation_count / total_lines > 0.6:
        return True, 0

    return False, None


def remove_references_section(text):
    """
    從文本中移除參考文獻區塊

    Returns:
        str: 移除參考文獻後的文本
    """
    is_ref, start_pos = is_references_section(text)

    if is_ref and start_pos is not None:
        # 如果整頁都是參考文獻（start_pos == 0），返回空
        if start_pos == 0:
            return ""
        # 否則只保留參考文獻之前的內容
        return text[:start_pos].strip()

    return text


def clean_ocr_output(text):
    """清理 OCR 輸出"""
    if not text:
        return ""

    text = re.sub(r'\\\(([^)]*)\\\)', r'\1', text)
    text = re.sub(r'\\mathrm\s*\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\text\s*\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\textbf\s*\{([^}]*)\}', r'\1', text)
    text = re.sub(r'\\sim', '~', text)
    text = re.sub(r'\\times', '×', text)
    text = re.sub(r'\\pm', '±', text)
    text = re.sub(r'\\leq', '≤', text)
    text = re.sub(r'\\geq', '≥', text)

    greek_letters = {
        r'\\alpha': 'α', r'\\beta': 'β', r'\\gamma': 'γ', r'\\delta': 'δ',
        r'\\mu': 'μ', r'\\sigma': 'σ', r'\\omega': 'ω', r'\\pi': 'π',
    }
    for latex, char in greek_letters.items():
        text = re.sub(latex, char, text)
    text = re.sub(r'\\([a-zA-Z]+)', r'\1', text)

    text = re.sub(r'<sup>([^<]*)</sup>', r'^\1', text)
    text = re.sub(r'<sub>([^<]*)</sub>', r'_\1', text)

    # 移除 HTML 標籤
    text = re.sub(r'<table>.*?</table>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)

    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    # 🆕 移除參考文獻區塊
    text = remove_references_section(text)

    return text.strip()


def extract_text_from_html_table(html_content):
    """從 HTML 表格中提取純文字"""
    if not html_content:
        return ""

    import re
    from html import unescape

    text = re.sub(r'<br\s*/?>', ' ', html_content)
    text = re.sub(r'<sup>([^<]*)</sup>', r'^\1', text)
    text = re.sub(r'<sub>([^<]*)</sub>', r'_\1', text)
    text = re.sub(r'</tr>', '\n', text)
    text = re.sub(r'</td>|</th>', ' | ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = unescape(text)

    lines = [line.strip() for line in text.split('\n') if line.strip()]
    text = '\n'.join(lines)

    return text.strip()


def merge_short_pages(page_results, min_length=30):
    """將字數過短的頁面與前後頁面合併"""
    if not page_results:
        return []

    merged = []
    i = 0
    while i < len(page_results):
        page_num, content = page_results[i]
        content_len = len(content.strip())

        if content_len >= min_length:
            merged.append((page_num, content))
            i += 1
            continue

        if i + 1 < len(page_results):
            next_page_num, next_content = page_results[i + 1]
            combined = f"{content}\n\n{next_content}"
            merged.append((page_num, combined))
            i += 2
        elif merged:
            prev_page_num, prev_content = merged[-1]
            combined = f"{prev_content}\n\n{content}"
            merged[-1] = (prev_page_num, combined)
            i += 1
        else:
            merged.append((page_num, content))
            i += 1
    return merged


# ==================== 核心 OCR 與處理邏輯 ====================

def ocr_pdf_by_page(model, tokenizer, pdf_path, selected_pages=None,
                     extract_tables=False, table_output_dir=None):
    """對單個 PDF 進行 OCR，並處理表格/圖片"""
    pdf_name = Path(pdf_path).stem
    print(f"\n{'='*70}")
    print(f"OCR: {pdf_name}.pdf")
    if extract_tables:
        print(f"（同時擷取表格和圖片）")
    print(f"{'='*70}")

    start_time = time.time()
    page_results = []
    tables_extracted = []

    # 🆕 狀態追踪：是否已進入參考文獻區塊
    in_references_section = False

    try:
        doc = fitz.open(pdf_path)
        total_pages = len(doc)

        if selected_pages:
            valid_pages = [p for p in selected_pages if 1 <= p <= total_pages]
            pages_to_process = valid_pages
            print(f"共 {total_pages} 頁，選擇處理: {pages_to_process}")
        else:
            pages_to_process = list(range(1, total_pages + 1))
            print(f"共 {total_pages} 頁")

        with tempfile.TemporaryDirectory() as tmp_dir:
            for page_num in pages_to_process:
                i = page_num - 1
                print(f"  第 {page_num}/{total_pages} 頁...", end=' ', flush=True)

                try:
                    page = doc[i]
                    page_width = page.rect.width
                    page_height = page.rect.height

                    # OCR 預覽圖
                    ocr_scale = OCR_IMAGE_SIZE / max(page_width, page_height)
                    ocr_mat = fitz.Matrix(ocr_scale, ocr_scale)
                    ocr_pix = page.get_pixmap(matrix=ocr_mat)
                    ocr_width = ocr_pix.width
                    ocr_height = ocr_pix.height

                    img_path = os.path.join(tmp_dir, f"page_{page_num}.png")
                    ocr_pix.save(img_path)

                    result_file = os.path.join(tmp_dir, "result.mmd")
                    if os.path.exists(result_file):
                        os.remove(result_file)

                    # 執行模型
                    old_stdout, captured_output = capture_model_output()
                    model.infer(
                        tokenizer,
                        prompt="<image>\n<|grounding|>Convert the document to markdown.",
                        image_file=img_path,
                        output_path=tmp_dir,
                        base_size=OCR_IMAGE_SIZE,
                        image_size=OCR_IMAGE_SIZE,
                        crop_mode=False,
                        save_results=True,
                        test_compress=True
                    )
                    restore_stdout(old_stdout)
                    captured_text = captured_output.getvalue()

                    # 處理文字
                    text_ok = False
                    page_text_content = ""

                    # 🆕 如果已進入參考文獻區塊，跳過後續頁面的文字處理
                    if in_references_section:
                        print(f"⏭️ 跳過（參考文獻區塊）", end=' ', flush=True)
                    elif os.path.exists(result_file):
                        with open(result_file, 'r', encoding='utf-8') as f:
                            raw_text = f.read()

                            # 🆕 先檢查是否進入參考文獻區塊（在清理之前）
                            is_ref, ref_start = is_references_section(raw_text)
                            if is_ref:
                                in_references_section = True
                                print(f"📚 檢測到參考文獻區塊", end=' ', flush=True)

                                # 如果參考文獻從頁面中間開始，保留之前的內容
                                if ref_start and ref_start > 0:
                                    partial_text = raw_text[:ref_start]
                                    cleaned = clean_ocr_output(partial_text)
                                    if cleaned.strip():
                                        page_text_content = cleaned
                                        text_ok = True
                                # 如果整頁都是參考文獻，不處理
                            else:
                                cleaned = clean_ocr_output(raw_text)
                                if cleaned.strip():
                                    page_text_content = cleaned
                                    text_ok = True

                    # 處理表格與圖片
                    object_count = 0
                    tables_text_content = []

                    # 🆕 如果已進入參考文獻區塊，也跳過表格處理
                    if extract_tables and table_output_dir and not in_references_section:
                        raw_result = extract_from_stdout(captured_text)
                        if raw_result:
                            objects_data, captions = extract_tables_and_images_from_result(raw_result)
                            
                            # 合併重疊
                            if objects_data:
                                objects_data = merge_overlapping_objects(objects_data, overlap_threshold=0.3)

                            if objects_data:
                                # 生成高解析度圖片
                                high_res_scale = HIGH_RES_DPI / 72.0
                                high_res_mat = fitz.Matrix(high_res_scale, high_res_scale)
                                high_res_pix = page.get_pixmap(matrix=high_res_mat)
                                high_res_width = high_res_pix.width
                                high_res_height = high_res_pix.height
                                high_res_img_data = high_res_pix.tobytes("png")
                                high_res_image = Image.open(BytesIO(high_res_img_data))
                                
                                scale_x = high_res_width / ocr_width
                                scale_y = high_res_height / ocr_height

                                for idx, obj in enumerate(objects_data, 1):
                                    bbox = obj['bbox']
                                    obj_type = obj['type']
                                    title = find_related_caption(bbox, obj_type, captions)

                                    if SKIP_FIRST_PAGE_IMAGES and page_num == 1 and obj_type != 'table':
                                        continue

                                    # 座標換算
                                    x1_hr = int(bbox[0] * scale_x)
                                    y1_hr = int(bbox[1] * scale_y)
                                    x2_hr = int(bbox[2] * scale_x)
                                    y2_hr = int(bbox[3] * scale_y)
                                    obj_width = x2_hr - x1_hr
                                    obj_height = y2_hr - y1_hr

                                    if obj_type != 'table':
                                        if obj_width < MIN_IMAGE_SIZE or obj_height < MIN_IMAGE_SIZE:
                                            continue

                                    # 全寬度裁切
                                    x1_crop = 0
                                    x2_crop = high_res_width
                                    padding_top = max(int(obj_height * 0.25), 50)
                                    padding_bottom = max(int(obj_height * 0.25), 50)
                                    y1_crop = max(0, y1_hr - padding_top)
                                    y2_crop = min(high_res_height, y2_hr + padding_bottom)

                                    obj_img = high_res_image.crop((x1_crop, y1_crop, x2_crop, y2_crop))

                                    type_abbr = {'table': 't', 'image': 'i', 'figure': 'f', 'chart': 'c', 'diagram': 'd'}
                                    abbr = type_abbr.get(obj_type, 'o')

                                    # 儲存圖片
                                    jpg_path = os.path.join(table_output_dir, f"{pdf_name}_p{page_num}_{abbr}{idx}.jpg")
                                    obj_img.save(jpg_path, "JPEG", quality=95)
                                    jpg_filename = os.path.basename(jpg_path)

                                    # 嘗試對圖片進行 OCR
                                    image_ocr_text = ""
                                    if obj_type in ['image', 'figure', 'chart', 'diagram']:
                                        try:
                                            import io as io_module
                                            old_img_stdout = sys.stdout
                                            sys.stdout = io_module.StringIO()
                                            model.infer(
                                                tokenizer,
                                                prompt="<image>\nExtract all text from this image.",
                                                image_file=jpg_path,
                                                output_path=tmp_dir,
                                                base_size=1024,
                                                image_size=1024,
                                                crop_mode=False,
                                                save_results=True,
                                                test_compress=False
                                            )
                                            sys.stdout = old_img_stdout
                                            
                                            result_files = [f for f in os.listdir(tmp_dir) if f.endswith('.mmd')]
                                            if result_files:
                                                latest_result = max([os.path.join(tmp_dir, f) for f in result_files], key=os.path.getmtime)
                                                with open(latest_result, 'r', encoding='utf-8') as rf:
                                                    image_ocr_text = clean_ocr_output(rf.read())
                                                os.remove(latest_result)
                                        except Exception:
                                            pass

                                    # 準備 HTML 和文字內容
                                    html_path = os.path.join(table_output_dir, f"{pdf_name}_p{page_num}_{abbr}{idx}.html")
                                    
                                    ocr_text_content = ""
                                    if obj_type == 'table' and obj.get('html'):
                                        ocr_text_content = extract_text_from_html_table(obj['html'])
                                    elif image_ocr_text:
                                        ocr_text_content = image_ocr_text
                                    
                                    # 確保 HTML 顯示
                                    display_text = ocr_text_content if ocr_text_content else f"[{obj_type} content]"

                                    with open(html_path, 'w', encoding='utf-8') as f:
                                        if title: f.write(f"<h2>{title}</h2>\n")
                                        f.write(f'<div class="{obj_type}">\n')
                                        f.write(f'    <img src="{jpg_filename}" alt="{title or obj_type}" style="max-width: 100%;">\n')
                                        if ocr_text_content:
                                            f.write(f'    <p class="ocr-text">{ocr_text_content}</p>\n')
                                        f.write(f'</div>\n')

                                    # 🆕 構建向量資料庫使用的文字區塊
                                    # 如果沒有文字，我們添加一個佔位符，讓資料庫知道這裡有圖片
                                    section_title = title if title else f"{obj_type} #{idx}"
                                    db_content_block = f"\n## {section_title}\n"
                                    
                                    if ocr_text_content and ocr_text_content != f"[{obj_type} content]":
                                        db_content_block += ocr_text_content
                                    else:
                                        # 🆕 強制寫入：如果沒有 OCR 文字，標記有圖片檔案
                                        db_content_block += f"(此區塊包含圖片/圖表資料，請參考附件: {jpg_filename})"
                                    
                                    tables_text_content.append(db_content_block)

                                    tables_extracted.append({
                                        'page': page_num,
                                        'table_idx': idx,
                                        'object_type': obj_type,
                                        'title': title,
                                        'jpg_path': jpg_path,
                                        'html_path': html_path
                                    })
                                    object_count += 1

                    # 合併頁面內容
                    final_page_content = page_text_content
                    if tables_text_content:
                        final_page_content += "\n" + "\n".join(tables_text_content)

                    if final_page_content.strip():
                        page_results.append((page_num, final_page_content))
                        text_ok = True

                    if text_ok:
                        print(f"✓ ({len(final_page_content)}字 + {object_count}物件)", flush=True)
                    else:
                        print("⚠ 無內容", flush=True)

                    cleanup_gpu()

                except Exception as e:
                    print(f"✗ 錯誤: {e}", flush=True)
                    continue

        doc.close()

        if page_results:
            page_results = merge_short_pages(page_results, min_length=30)

        elapsed = time.time() - start_time
        print(f"✓ 完成！耗時 {elapsed:.1f} 秒")
        return page_results, tables_extracted

    except Exception as e:
        print(f"✗ OCR 失敗: {e}")
        import traceback
        traceback.print_exc()
        return [], []


def process_single_pdf(model, tokenizer, vectorstore, pdf_path, extract_tables=True, target_pages=None):
    """處理單一 PDF 並添加到資料庫"""
    pdf_path = Path(pdf_path)
    pdf_name = pdf_path.stem

    print(f"\n{'='*80}")
    print(f"📄 處理 PDF: {pdf_name}")
    print('='*80)

    table_output_dir = os.path.join(EXTRACTED_TABLES_DIR, pdf_name)
    page_table_map = {}

    if extract_tables:
        os.makedirs(table_output_dir, exist_ok=True)
        import glob
        old_files = glob.glob(os.path.join(table_output_dir, f"{pdf_name}_p*"))
        for f in old_files:
            os.remove(f)

    page_results, tables_extracted = ocr_pdf_by_page(
        model, tokenizer, str(pdf_path),
        selected_pages=target_pages,
        extract_tables=extract_tables,
        table_output_dir=table_output_dir if extract_tables else None
    )

    if not page_results:
        return 0, 0

    # 建立映射
    total_objects = len(tables_extracted) if extract_tables else 0
    for table_info in tables_extracted:
        page_num = table_info['page']
        if page_num not in page_table_map:
            page_table_map[page_num] = []
        page_table_map[page_num].append(os.path.basename(table_info['jpg_path']))

    # 建立文檔
    pdf_documents = []
    for page_num, page_content in page_results:
        table_images = page_table_map.get(page_num, [])
        
        # 🆕 修正 has_table 判斷：只要有圖片或表格文字都算 True
        has_table = (len(table_images) > 0) or ('<table>' in page_content or '|' in page_content)

        doc = Document(
            page_content=page_content,
            metadata={
                'source_file': pdf_path.name,
                'source_type': 'ocr_pdf',
                'page': page_num,
                'original_text': page_content,
                'category': '洗腎衛教',
                'title': '',
                'keywords': '',
                'reference': pdf_path.name,
                'collection_name': COLLECTION_NAME,
                'sheet_name': '',
                'folder': '',
                'page_label': str(page_num),
                'has_table': has_table,
                'table_images': table_images,
            }
        )
        pdf_documents.append(doc)

    print(f"\n  ✅ 建立 {len(page_results)} 個頁面文檔")
    print(f"  分割並寫入資料庫...", end=' ')
    
    split_docs = text_splitter.split_documents(pdf_documents)
    
    try:
        vectorstore.add_documents(split_docs)
        print(f"✓ 已添加 {len(split_docs)} 個片段")
        return len(split_docs), total_objects
    except Exception as e:
        print(f"✗ 添加失敗: {e}")
        return 0, total_objects


def parse_pages(pages_str):
    if not pages_str: return None
    pages = set()
    for part in pages_str.split(','):
        part = part.strip()
        if '-' in part:
            start, end = part.split('-', 1)
            pages.update(range(int(start), int(end) + 1))
        else:
            pages.add(int(part))
    return sorted(pages)


def main():
    parser = argparse.ArgumentParser(description='更新 PDF 到資料庫 V2.1 (修復版)')
    parser.add_argument('--file', type=str, help='指定單一 PDF 檔案')
    parser.add_argument('--all', action='store_true', help='處理所有 PDF 檔案')
    parser.add_argument('--no-extract', action='store_true', help='不擷取表格')
    parser.add_argument('--pages', type=str, help='指定頁面範圍 (例如: 1,3,5-10)')
    parser.add_argument('--dry-run', action='store_true', help='不寫入資料庫')

    args = parser.parse_args()

    if not args.file and not args.all:
        parser.print_help()
        return

    target_pages = parse_pages(args.pages) if args.pages else None

    # 載入模型
    print("\n📥 載入 OCR 模型...")
    try:
        tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            MODEL_PATH,
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=torch.bfloat16
        ).eval().cuda()
        print("✅ 模型載入完成")
    except Exception as e:
        print(f"❌ 模型載入失敗: {e}")
        return

    # 連接資料庫
    vectorstore = None
    if not args.dry_run:
        print("\n📦 連接資料庫...")
        try:
            vectorstore = PGVector(
                embeddings=embeddings,
                connection=db_connection,
                collection_name=COLLECTION_NAME,
            )
            print(f"✅ 已連接 {COLLECTION_NAME}")
        except Exception as e:
            print(f"❌ 連接失敗: {e}")
            return

        # 刪除舊資料 (單一檔案模式)
        if args.file:
            pdf_name = Path(args.file).name
            print(f"\n  刪除 '{pdf_name}' 的舊資料...")
            try:
                from sqlalchemy import create_engine, text
                engine = create_engine(db_connection)
                with engine.connect() as conn:
                    result = conn.execute(
                        text("""
                            DELETE FROM langchain_pg_embedding
                            WHERE cmetadata->>'source_file' = :filename
                            AND collection_id = (
                                SELECT uuid FROM langchain_pg_collection
                                WHERE name = :collection_name
                            )
                        """),
                        {"filename": pdf_name, "collection_name": COLLECTION_NAME}
                    )
                    conn.commit()
            except Exception as e:
                print(f"  ⚠ 刪除失敗: {e}")

    # 執行處理
    if args.file:
        pdf_path = Path(args.file)
        if not pdf_path.exists():
            print(f"❌ 檔案不存在: {pdf_path}")
            return

        chunks, tables = process_single_pdf(
            model, tokenizer, vectorstore, pdf_path,
            extract_tables=not args.no_extract,
            target_pages=target_pages
        )

    elif args.all:
        print("\n⚠️  將清除舊資料並重新處理全部 PDF")
        confirm = input("確定要繼續嗎？(y/N): ").strip().lower()
        if confirm != 'y': return

        pdf_files = sorted(Path(INPUT_DIR).glob("*.pdf"))
        
        for i, pdf_path in enumerate(pdf_files, 1):
            print(f"\n[{i}/{len(pdf_files)}] 處理: {pdf_path.name}")
            
            pdf_name = pdf_path.stem
            table_output_dir = None
            if not args.no_extract:
                table_output_dir = os.path.join(EXTRACTED_TABLES_DIR, pdf_name)
                os.makedirs(table_output_dir, exist_ok=True)
                import glob
                old_files = glob.glob(os.path.join(table_output_dir, f"{pdf_name}_p*"))
                for f in old_files: os.remove(f)

            page_results, tables_extracted = ocr_pdf_by_page(
                model, tokenizer, str(pdf_path),
                extract_tables=not args.no_extract,
                table_output_dir=table_output_dir
            )

            if not page_results: continue

            # 建立映射
            page_table_map = {}
            for table_info in tables_extracted:
                page_num = table_info['page']
                if page_num not in page_table_map:
                    page_table_map[page_num] = []
                page_table_map[page_num].append(os.path.basename(table_info['jpg_path']))

            # 建立文檔
            pdf_documents = []
            for page_num, page_content in page_results:
                table_images = page_table_map.get(page_num, [])
                
                # 🆕 批次處理同樣修正 has_table 判斷
                has_table = (len(table_images) > 0) or ('<table>' in page_content or '|' in page_content)

                doc = Document(
                    page_content=page_content,
                    metadata={
                        'source_file': pdf_path.name,
                        'source_type': 'ocr_pdf',
                        'page': page_num,
                        'original_text': page_content,
                        'category': '洗腎衛教',
                        'title': '',
                        'keywords': '',
                        'reference': pdf_path.name,
                        'collection_name': COLLECTION_NAME,
                        'sheet_name': '',
                        'folder': '',
                        'page_label': str(page_num),
                        'has_table': has_table,
                        'table_images': table_images,
                    }
                )
                pdf_documents.append(doc)

            split_docs = text_splitter.split_documents(pdf_documents)

            if i == 1:
                vectorstore = PGVector.from_documents(
                    documents=split_docs,
                    embedding=embeddings,
                    connection=db_connection,
                    collection_name=COLLECTION_NAME,
                    pre_delete_collection=True,
                )
            else:
                vectorstore.add_documents(split_docs)
            
            print(f"  ✓ 已添加 {len(split_docs)} 個片段")
            cleanup_gpu()

if __name__ == "__main__":
    main()