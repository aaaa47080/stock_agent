"""
統一進階載入器 - 整合版
功能：
1. 支援 JSONL 問答資料載入
2. 支援多資料夾 PDF 批次處理
3. 強大的 OCR + 表格/圖片擷取（來自 update_pdf_to_db_v2.py）
4. 自動建立多個 collection（依資料夾命名）
"""
import os
import sys
import json
from pathlib import Path
import tempfile
import time
import re
import gc
from io import StringIO, BytesIO

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import fitz
from PIL import Image
from transformers import AutoModel, AutoTokenizer

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from core.config import (
    DB_HOST, DB_NAME, DB_PORT, DB_PASSWORD, DB_USER,
    embeddings, get_reference_mapping
)


# ==================== 配置 ====================
os.environ["CUDA_VISIBLE_DEVICES"] = '0'
os.environ["CUDA_LAUNCH_BLOCKING"] = '1'

OCR_MODEL_PATH = '/home/danny/AI-agent/deepseek_ocr'
from core.config import EXTRACTED_TABLES_DIR
EXTRACTED_TABLES_BASE_DIR = EXTRACTED_TABLES_DIR

# OCR 參數
OCR_IMAGE_SIZE = 1024
HIGH_RES_DPI = 100
MIN_IMAGE_SIZE = 100
SKIP_FIRST_PAGE_IMAGES = False


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


# ==================== 統一進階載入器類別 ====================
class UnifiedAdvancedLoader:
    def __init__(self, db_connection_string, pdf_base_path, jsonl_folder_path=None):
        self.db_connection_string = db_connection_string
        self.pdf_base_path = Path(pdf_base_path)
        self.jsonl_folder_path = Path(jsonl_folder_path) if jsonl_folder_path else None
        self.embeddings = embeddings

        # 文字分割器
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=1200,
            chunk_overlap=200
        )

        # 資料夾映射
        self.folder_mapping = get_reference_mapping()

        # OCR 模型
        self.ocr_model = None
        self.ocr_tokenizer = None

        # 統計資料
        self.processing_stats = {
            'pdf_processed': [],
            'pdf_failed': [],
            'ocr_stats': []
        }

        print("✅ 統一進階載入器初始化完成")

    def _load_ocr_model(self):
        """載入 OCR 模型"""
        if self.ocr_model is None:
            print("\n📥 載入 OCR 模型...")
            try:
                self.ocr_tokenizer = AutoTokenizer.from_pretrained(
                    OCR_MODEL_PATH,
                    trust_remote_code=True
                )
                self.ocr_model = AutoModel.from_pretrained(
                    OCR_MODEL_PATH,
                    trust_remote_code=True,
                    use_safetensors=True,
                    torch_dtype=torch.bfloat16
                ).eval().cuda()
                print("✅ OCR 模型載入完成\n")
            except Exception as e:
                print(f"❌ OCR 模型載入失敗: {e}")
                raise

    def get_english_collection_name(self, folder_name):
        """取得英文 collection 名稱"""
        return self.folder_mapping.get(
            folder_name,
            f"unknown_{folder_name.lower().replace(' ', '_')}"
        )

    # ==================== OCR PDF 處理（進階版）====================
    def ocr_pdf_advanced(self, pdf_path, folder_name, table_output_dir):
        """
        使用進階 OCR 處理 PDF，包含表格/圖片擷取
        來自 update_pdf_to_db_v2.py 的完整功能
        """
        pdf_name = Path(pdf_path).stem
        print(f"\n{'='*70}")
        print(f"📄 OCR 處理: {pdf_name}.pdf")
        print(f"{'='*70}")

        start_time = time.time()
        page_results = []
        tables_extracted = []

        # 🆕 狀態追踪：是否已進入參考文獻區塊
        in_references_section = False

        try:
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            print(f"共 {total_pages} 頁")

            with tempfile.TemporaryDirectory() as tmp_dir:
                for page_num in range(1, total_pages + 1):
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

                        # 執行 OCR 模型
                        old_stdout, captured_output = capture_model_output()
                        self.ocr_model.infer(
                            self.ocr_tokenizer,
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
                                    # 如果整頁都是參考文獻，不處理
                                else:
                                    cleaned = clean_ocr_output(raw_text)
                                    if cleaned.strip():
                                        page_text_content = cleaned

                        # 處理表格與圖片
                        object_count = 0
                        tables_text_content = []

                        # 🆕 如果已進入參考文獻區塊，也跳過表格處理
                        if not in_references_section:
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

                                        # 儲存圖片到全局統一的 images 資料夾
                                        # 結構: EXTRACTED_TABLES_BASE_DIR/images/
                                        global_images_dir = os.path.join(EXTRACTED_TABLES_BASE_DIR, "images")
                                        os.makedirs(global_images_dir, exist_ok=True)

                                        jpg_filename = f"{pdf_name}_p{page_num}_{abbr}{idx}.jpg"
                                        jpg_path = os.path.join(global_images_dir, jpg_filename)
                                        obj_img.save(jpg_path, "JPEG", quality=100)

                                        # 對圖片進行 OCR
                                        image_ocr_text = ""
                                        if obj_type in ['image', 'figure', 'chart', 'diagram']:
                                            try:
                                                import io as io_module
                                                old_img_stdout = sys.stdout
                                                sys.stdout = io_module.StringIO()
                                                self.ocr_model.infer(
                                                    self.ocr_tokenizer,
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
                                                    latest_result = max([os.path.join(tmp_dir, f) for f in result_files],
                                                                      key=os.path.getmtime)
                                                    with open(latest_result, 'r', encoding='utf-8') as rf:
                                                        image_ocr_text = clean_ocr_output(rf.read())
                                                    os.remove(latest_result)
                                            except Exception:
                                                pass

                                        # 準備 HTML (放在與 images 相同的目錄)
                                        html_filename = f"{pdf_name}_p{page_num}_{abbr}{idx}.html"
                                        html_path = os.path.join(global_images_dir, html_filename)

                                        ocr_text_content = ""
                                        if obj_type == 'table' and obj.get('html'):
                                            ocr_text_content = extract_text_from_html_table(obj['html'])
                                        elif image_ocr_text:
                                            ocr_text_content = image_ocr_text

                                        # 在 OCR 文字前加入檔案名稱，提升檢索準確度
                                        if ocr_text_content:
                                            ocr_text_content_with_filename = f"檔案: {jpg_filename}\n\n{ocr_text_content}"
                                        else:
                                            ocr_text_content_with_filename = f"檔案: {jpg_filename}"

                                        with open(html_path, 'w', encoding='utf-8') as f:
                                            if title:
                                                f.write(f"<h2>{title}</h2>\n")
                                            f.write(f'<div class="{obj_type}">\n')
                                            f.write(f'    <img src="{jpg_filename}" alt="{title or obj_type}" style="max-width: 100%;">\n')
                                            if ocr_text_content_with_filename:
                                                f.write(f'    <p class="ocr-text">{ocr_text_content_with_filename}</p>\n')
                                            f.write(f'</div>\n')

                                        # 構建向量資料庫內容（使用包含檔案名稱的版本）
                                        section_title = title if title else f"{obj_type} #{idx}"
                                        db_content_block = f"\n## {section_title}\n"

                                        if ocr_text_content:
                                            # 使用包含檔案名稱的 OCR 文字
                                            db_content_block += ocr_text_content_with_filename
                                        else:
                                            db_content_block += f"檔案: {jpg_filename}\n\n(此區塊包含圖片/圖表資料，請參考附件)"

                                        tables_text_content.append(db_content_block)

                                        tables_extracted.append({
                                            'page': page_num,
                                            'object_idx': idx,
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
            print(f"✅ 完成！耗時 {elapsed:.1f} 秒")

            # 記錄統計
            self.processing_stats['ocr_stats'].append({
                'file': pdf_path.name,
                'folder': folder_name,
                'pages': len(page_results),
                'objects': len(tables_extracted),
                'time': elapsed
            })

            return page_results, tables_extracted

        except Exception as e:
            print(f"✗ OCR 失敗: {e}")
            import traceback
            traceback.print_exc()
            return [], []

    # ==================== JSONL 處理 ====================
    def load_jsonl_files(self):
        """載入 JSONL 問答資料（不分割）"""
        if not self.jsonl_folder_path or not self.jsonl_folder_path.exists():
            print("⚠️ JSONL 資料夾未設定或不存在")
            return []

        jsonl_files = list(self.jsonl_folder_path.glob("*.jsonl"))
        if not jsonl_files:
            print("⚠️ 沒有找到 JSONL 檔案")
            return []

        documents = []
        seen_contents = set()

        for file_path in jsonl_files:
            print(f"載入 JSONL: {file_path.name}")
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        question_text = data.get('question', '').strip()
                        answer_text = data.get('text', '').strip()
                        original_full_text = data.get('text', '').strip()

                        # 解析格式
                        if not question_text and answer_text:
                            if '問題:' in answer_text and '答案:' in answer_text:
                                parts = answer_text.split('\n')
                                for part in parts:
                                    if part.strip().startswith('問題:'):
                                        question_text = part.replace('問題:', '').strip()
                                    elif part.strip().startswith('答案:'):
                                        answer_text = part.replace('答案:', '').strip()
                        elif question_text and not ('問題:' in original_full_text):
                            original_full_text = f"問題: {question_text}\n答案: {answer_text}"

                        if not question_text or not answer_text:
                            continue

                        # 去重
                        content_key = answer_text[:200]
                        if content_key in seen_contents:
                            continue
                        seen_contents.add(content_key)

                        # 建立文檔（只嵌入問題）
                        metadata = data.get('metadata', {})
                        content_parts = [question_text]
                        if metadata.get('keywords'):
                            content_parts.append(f"關鍵字: {metadata['keywords']}")
                        if metadata.get('reference'):
                            content_parts.append(f"參考: {metadata['reference']}")

                        page_content = "\n".join(content_parts)
                        doc = Document(
                            page_content=page_content,
                            metadata={
                                "id": data.get('id', f"{file_path.stem}_{line_num}"),
                                "source_file": metadata.get('source_file', file_path.name),
                                "sheet_name": metadata.get('sheet_name', ''),
                                "title": question_text,
                                "keywords": metadata.get('keywords', ''),
                                "reference": metadata.get('reference', ''),
                                "original_text": answer_text,
                                "original_full_text": original_full_text,
                                "source_type": "jsonl"
                            }
                        )
                        documents.append(doc)

                    except Exception as e:
                        print(f"  JSONL {file_path.name} 第 {line_num} 行錯誤: {e}")
                        continue

        print(f"✅ 總共載入 {len(documents)} 筆 JSONL 資料")
        return documents

    # ==================== PDF 資料夾處理 ====================
    def load_pdf_folder(self, folder_path):
        """處理單一 PDF 資料夾（使用進階 OCR）"""
        pdf_files = list(folder_path.glob("*.pdf"))
        if not pdf_files:
            return []

        print(f"\n找到 {len(pdf_files)} 個 PDF 檔案")
        all_docs = []

        for pdf_file in pdf_files:
            try:
                print(f"\n正在處理: {pdf_file.name}")

                # 使用進階 OCR 處理（不需要建立個別資料夾，圖片統一存在 images 資料夾）
                page_results, tables_extracted = self.ocr_pdf_advanced(
                    pdf_file,
                    folder_path.name,
                    EXTRACTED_TABLES_BASE_DIR  # 只傳遞基礎路徑
                )

                if not page_results:
                    print(f"  ⚠️ 無有效內容")
                    self.processing_stats['pdf_failed'].append({
                        'file': pdf_file.name,
                        'folder': folder_path.name,
                        'error': '無有效內容'
                    })
                    continue

                # 建立映射
                page_table_map = {}
                for table_info in tables_extracted:
                    page_num = table_info['page']
                    if page_num not in page_table_map:
                        page_table_map[page_num] = []
                    page_table_map[page_num].append(os.path.basename(table_info['jpg_path']))

                # 建立文檔
                for page_num, page_content in page_results:
                    table_images = page_table_map.get(page_num, [])
                    has_table = (len(table_images) > 0) or ('<table>' in page_content or '|' in page_content)

                    doc = Document(
                        page_content=page_content,
                        metadata={
                            'source_file': pdf_file.name,
                            'source_type': 'ocr_pdf_advanced',
                            'page': page_num,
                            'original_text': page_content,
                            'folder': folder_path.name,
                            'page_label': str(page_num),
                            'has_table': has_table,
                            'table_images': table_images,
                            'pdf_file': pdf_file.name
                        }
                    )
                    all_docs.append(doc)

                print(f"  ✅ 成功處理 {len(page_results)} 頁，{len(tables_extracted)} 個物件")
                self.processing_stats['pdf_processed'].append({
                    'file': pdf_file.name,
                    'folder': folder_path.name,
                    'pages': len(page_results),
                    'objects': len(tables_extracted)
                })

            except Exception as e:
                print(f"  ❌ 處理失敗: {pdf_file.name}")
                print(f"     錯誤: {str(e)[:200]}")
                self.processing_stats['pdf_failed'].append({
                    'file': pdf_file.name,
                    'folder': folder_path.name,
                    'error': str(e)[:200]
                })
                continue

        return all_docs

    # ==================== 統一載入 ====================
    def load_all_data_unified(self, pdf_batch_size=20, jsonl_batch_size=50):
        """統一載入所有資料（PDF + JSONL）"""
        # 重置統計
        self.processing_stats = {
            'pdf_processed': [],
            'pdf_failed': [],
            'ocr_stats': []
        }

        print(f"\n{'='*80}")
        print("🚀 統一進階載入開始")
        print(f"{'='*80}")

        # 載入 OCR 模型（PDF 需要）
        self._load_ocr_model()

        total_collections = 0

        # === 1. 載入 JSONL ===
        jsonl_docs = self.load_jsonl_files()
        if jsonl_docs:
            cleaned_jsonl = [self._validate_and_clean_document(doc) for doc in jsonl_docs]
            cleaned_jsonl = [d for d in cleaned_jsonl if d is not None]

            if cleaned_jsonl:
                saved = self._batch_save_to_vectordb(
                    cleaned_jsonl,
                    "medical_knowledge_base",
                    jsonl_batch_size
                )
                if saved > 0:
                    total_collections += 1
                    print(f"✅ JSONL 已儲存至 'medical_knowledge_base' ({saved} 筆)")
        else:
            print("⏭️ 跳過 JSONL 載入")

        # === 2. 載入 PDF 資料夾（進階模式）===
        pdf_folders = [d for d in self.pdf_base_path.iterdir() if d.is_dir()]
        if pdf_folders:
            print(f"\n📁 找到 {len(pdf_folders)} 個 PDF 資料夾")

            for i, folder in enumerate(sorted(pdf_folders), 1):
                print(f"\n{'='*70}")
                print(f"處理資料夾 {i}/{len(pdf_folders)}: {folder.name}")
                print(f"{'='*70}")

                pdf_docs = self.load_pdf_folder(folder)
                if not pdf_docs:
                    print(f"  ⏭️ 跳過（無有效內容）")
                    continue

                # 分割文檔
                final_docs = []
                for doc in pdf_docs:
                    splits = self.text_splitter.split_documents([doc])
                    final_docs.extend(splits)

                # 儲存到資料庫
                collection_name = self.get_english_collection_name(folder.name)
                saved = self._batch_save_to_vectordb(
                    final_docs,
                    collection_name,
                    pdf_batch_size
                )

                if saved > 0:
                    total_collections += 1
                    print(f"  ✅ 已儲存 {saved} 個片段至 '{collection_name}'")

                cleanup_gpu()
        else:
            print("⏭️ 無 PDF 資料夾")

        print(f"\n{'='*80}")
        print(f"🎉 統一載入完成！總共建立 {total_collections} 個 collections")
        print(f"{'='*80}")

        # 顯示報告
        self.print_processing_report()

    # ==================== 輔助方法 ====================
    def _validate_and_clean_document(self, doc):
        """驗證並清理文檔"""
        try:
            if not isinstance(doc.page_content, str):
                doc.page_content = str(doc.page_content) if doc.page_content else ""

            doc.page_content = doc.page_content.strip()
            if not doc.page_content or len(doc.page_content) < 10:
                return None

            # 清理 metadata
            if doc.metadata:
                cleaned_meta = {}
                for k, v in doc.metadata.items():
                    if v is None:
                        cleaned_meta[k] = ""
                    elif isinstance(v, (str, int, float, bool, list)):
                        cleaned_meta[k] = v
                    else:
                        cleaned_meta[k] = str(v)
                doc.metadata = cleaned_meta

            return doc
        except Exception as e:
            print(f"清理文檔錯誤: {e}")
            return None

    def _batch_save_to_vectordb(self, documents, collection_name, batch_size):
        """批次儲存到向量資料庫"""
        print(f"\n💾 儲存 {len(documents)} 筆至 '{collection_name}'...")

        cleaned = [self._validate_and_clean_document(d) for d in documents]
        cleaned = [d for d in cleaned if d is not None]

        if not cleaned:
            print("⚠️ 無有效文檔")
            return 0

        total_saved = 0
        for i in range(0, len(cleaned), batch_size):
            batch = cleaned[i:i+batch_size]
            try:
                if i == 0:
                    PGVector.from_documents(
                        documents=batch,
                        embedding=self.embeddings,
                        connection=self.db_connection_string,
                        collection_name=collection_name,
                        pre_delete_collection=True,
                    )
                else:
                    vs = PGVector(
                        embeddings=self.embeddings,
                        connection=self.db_connection_string,
                        collection_name=collection_name,
                    )
                    vs.add_documents(batch)
                total_saved += len(batch)
                print(f"  批次 {i//batch_size + 1}: ✓ ({len(batch)} 筆)")
            except Exception as e:
                print(f"  批次 {i//batch_size + 1}: ✗ 錯誤: {str(e)[:100]}")
                continue

        return total_saved

    def print_processing_report(self):
        """顯示處理報告"""
        print(f"\n{'='*80}")
        print("📊 處理報告")
        print(f"{'='*80}")

        # OCR 統計
        if self.processing_stats['ocr_stats']:
            total_time = sum(s['time'] for s in self.processing_stats['ocr_stats'])
            total_pages = sum(s['pages'] for s in self.processing_stats['ocr_stats'])
            total_objects = sum(s['objects'] for s in self.processing_stats['ocr_stats'])

            print(f"\n🔍 OCR 統計 ({len(self.processing_stats['ocr_stats'])} 個 PDF):")
            print("-" * 80)
            for item in self.processing_stats['ocr_stats']:
                print(f"  📄 {item['folder']}/{item['file']}")
                print(f"     頁數: {item['pages']}, 物件: {item['objects']}, 耗時: {item['time']:.1f}秒")
            print(f"\n  總計: {total_pages} 頁, {total_objects} 物件, {total_time:.1f} 秒")

        # 成功處理
        if self.processing_stats['pdf_processed']:
            print(f"\n✅ 成功處理 ({len(self.processing_stats['pdf_processed'])} 個 PDF):")
            print("-" * 80)
            for item in self.processing_stats['pdf_processed']:
                print(f"  {item['folder']}/{item['file']}: {item['pages']}頁, {item['objects']}物件")

        # 失敗記錄
        if self.processing_stats['pdf_failed']:
            print(f"\n❌ 處理失敗 ({len(self.processing_stats['pdf_failed'])} 個 PDF):")
            print("-" * 80)
            for item in self.processing_stats['pdf_failed']:
                print(f"  {item['folder']}/{item['file']}")
                print(f"     錯誤: {item['error']}")

        print(f"\n{'='*80}\n")

    # ==================== 資料庫管理 ====================
    def list_collections(self):
        """列出所有 collections"""
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM langchain_pg_collection ORDER BY name;")
            collections = [row[0] for row in cursor.fetchall()]
            print(f"\n已建立的 Collections ({len(collections)} 個):")
            for i, name in enumerate(collections, 1):
                print(f"{i:2d}. {name}")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"列出 collections 失敗: {e}")

    def reset_database(self):
        """重置資料庫"""
        try:
            conn = psycopg2.connect(self.db_connection_string)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            confirm = input("⚠️ 輸入 'DELETE' 確認重置資料庫: ").strip()
            if confirm == 'DELETE':
                for table in ['langchain_pg_embedding', 'langchain_pg_collection']:
                    cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                    print(f"已刪除 {table}")
                print("✅ 資料庫重置完成")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"重置失敗: {e}")


# ==================== 主程式 ====================
def main():
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    db_connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    PDF_DATA_PATH = "/home/danny/AI-agent/DataSet"
    JSONL_DATA_PATH = "/home/danny/AI-agent/RAG_JSONL"

    print("\n" + "="*80)
    print("🚀 統一進階載入器 (整合版)")
    print("="*80)
    print("\n功能特色:")
    print("  ✅ JSONL 問答資料載入")
    print("  ✅ 進階 OCR + 表格/圖片擷取")
    print("  ✅ 自動建立多個 collection")
    print("  ✅ 完整的處理報告")
    print("="*80)

    loader = UnifiedAdvancedLoader(
        db_connection_string,
        PDF_DATA_PATH,
        JSONL_DATA_PATH
    )

    while True:
        print("\n選項:")
        print("1. 🚀 統一載入所有資料（PDF + JSONL）")
        print("2. 📋 列出所有 Collections")
        print("3. 🧹 重置資料庫")
        print("4. ⛔ 退出")

        choice = input("\n請選擇 (1-4): ").strip()

        if choice == '1':
            pdf_batch = int(input("PDF 批次大小 (預設 20): ") or "20")
            jsonl_batch = int(input("JSONL 批次大小 (預設 50): ") or "50")
            confirm = input("\n⚠️ 確定開始載入？這將覆蓋現有資料 (y/N): ").strip().lower()
            if confirm == 'y':
                loader.load_all_data_unified(pdf_batch, jsonl_batch)

        elif choice == '2':
            loader.list_collections()

        elif choice == '3':
            loader.reset_database()

        elif choice == '4':
            print("👋 結束")
            break

        else:
            print("❌ 無效選項")


if __name__ == "__main__":
    main()
