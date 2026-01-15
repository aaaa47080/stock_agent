import os
import json
from pathlib import Path
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 添加當前目錄以便導入同級模組
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.config import embeddings

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector
from langchain_community.document_loaders import PyPDFLoader
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from core.config import DB_HOST, DB_NAME, DB_PORT, DB_PASSWORD, DB_USER, embeddings, get_reference_mapping

# OCR 相關導入
import tempfile
import time
import re
from PIL import Image
import io
try:
    import fitz  # PyMuPDF
    from transformers import AutoModel, AutoTokenizer
    import torch
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️ OCR 模組未安裝，將跳過掃描版 PDF 處理")

class UnifiedVectorDBLoader:
    def __init__(self, db_connection_string, pdf_base_path, jsonl_folder_path=None, enable_ocr=False, force_ocr_all=False, ocr_model_path=None):
        self.db_connection_string = db_connection_string
        self.pdf_base_path = Path(pdf_base_path)
        self.jsonl_folder_path = Path(jsonl_folder_path) if jsonl_folder_path else None
        self.embeddings = embeddings

        # PDF 使用自定義句子分割器（以句號為分割點，保持句子完整性）
        # 🔧 增加 chunk_size 和 overlap 避免跨頁內容被切散
        self.pdf_text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=1024,  # 👈 從 512 增加到 1024
            chunk_overlap=256,  # 👈 從 50 增加到 200 避免跨頁內容被切散
            separators=[
                "\n\n",   # 段落分隔（優先）
                "。\n",   # 句號+換行
                "。 ",    # 句號+空格
                "！\n",   # 驚嘆號+換行
                "！ ",    # 驚嘆號+空格
                "？\n",   # 問號+換行
                "？ ",    # 問號+空格
                "\n",     # 換行
                " ",      # 空格
                ""        # 字符（最後手段）
            ],
            keep_separator=True  # 保留分隔符，句號會留在前一個chunk末尾
        )

        self.folder_mapping = get_reference_mapping()

        # 用於記錄處理狀態
        self.empty_pdfs = []  # 記錄空白PDF
        self.failed_pdfs = []  # 記錄處理失敗的PDF
        self.ocr_processed_pdfs = []  # 記錄經過OCR處理的PDF

        # OCR 設定
        self.enable_ocr = enable_ocr and OCR_AVAILABLE
        self.force_ocr_all = force_ocr_all and OCR_AVAILABLE  # 強制所有 PDF 使用 OCR
        self.ocr_model = None
        self.ocr_tokenizer = None
        self.ocr_model_path = ocr_model_path or '/home/danny/AI-agent/deepseek_ocr'

        if self.force_ocr_all:
            if not OCR_AVAILABLE:
                print("⚠️ OCR 模組未安裝，無法使用強制 OCR 模式")
                self.force_ocr_all = False
                self.enable_ocr = False
            else:
                print("✓ 強制 OCR 模式：所有 PDF 都將使用 OCR 處理")
                self.enable_ocr = True
        elif self.enable_ocr:
            if not OCR_AVAILABLE:
                print("⚠️ OCR 功能已啟用但缺少必要模組，OCR 將被停用")
                self.enable_ocr = False
            else:
                print("✓ OCR 功能已啟用，將自動處理掃描版 PDF")

        print("初始化完成")

    def get_english_collection_name(self, folder_name):
        return self.folder_mapping.get(folder_name, f"unknown_{folder_name.lower().replace(' ', '_')}")

    # === OCR 輔助函數 ===
    def _load_ocr_model(self):
        """延遲加載 OCR 模型（只在需要時加載）"""
        if self.ocr_model is None and self.enable_ocr:
            print("\n正在加載 OCR 模型...")
            os.environ["CUDA_VISIBLE_DEVICES"] = '0'
            try:
                self.ocr_tokenizer = AutoTokenizer.from_pretrained(
                    self.ocr_model_path,
                    trust_remote_code=True
                )
                self.ocr_model = AutoModel.from_pretrained(
                    self.ocr_model_path,
                    trust_remote_code=True,
                    use_safetensors=True,
                    torch_dtype=torch.bfloat16
                ).eval().cuda()
                print("✓ OCR 模型加載完成\n")
            except Exception as e:
                print(f"❌ OCR 模型加載失敗: {e}")
                self.enable_ocr = False

    def _pdf_to_images(self, pdf_path, dpi=200, max_dimension=2000):
        """將 PDF 轉換為圖片"""
        doc = fitz.open(str(pdf_path))
        images = []
        mat = fitz.Matrix(dpi / 72.0, dpi / 72.0)

        for page in doc:
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

            width, height = img.size
            max_size = max(width, height)

            if max_size > max_dimension:
                scale = max_dimension / max_size
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = img.resize((new_width, new_height), Image.LANCZOS)

            images.append(img)

        doc.close()
        return images

    def _clean_ocr_output(self, text):
        """清理 OCR 輸出"""
        if not text:
            return ""

        lines = []
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped.startswith(('<|ref|>', '<|det|>', '<|grounding|>')):
                lines.append(line)

        result = '\n'.join(lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()

    def _ocr_pdf(self, pdf_path, folder_name):
        """使用 OCR 處理掃描版 PDF"""
        if not self.enable_ocr:
            return []

        self._load_ocr_model()
        if self.ocr_model is None:
            return []

        print(f"  🔍 使用 OCR 處理掃描版 PDF: {pdf_path.name}")
        start_time = time.time()
        all_docs = []

        try:
            images = self._pdf_to_images(pdf_path)
            print(f"     共 {len(images)} 頁")

            with tempfile.TemporaryDirectory() as tmp_dir:
                for i, img in enumerate(images):
                    page_num = i + 1
                    print(f"     第 {page_num}/{len(images)} 頁...", end=' ', flush=True)

                    try:
                        img_path = os.path.join(tmp_dir, f"page_{page_num}.png")
                        img.save(img_path, "PNG")

                        result_file = os.path.join(tmp_dir, "result.mmd")
                        if os.path.exists(result_file):
                            os.remove(result_file)

                        # OCR 推論
                        self.ocr_model.infer(
                            self.ocr_tokenizer,
                            prompt="<image>\n<|grounding|>Convert the document to markdown.",
                            image_file=img_path,
                            output_path=tmp_dir,
                            base_size=1024,
                            image_size=640,
                            crop_mode=True,
                            save_results=True,
                            test_compress=True
                        )

                        if os.path.exists(result_file):
                            with open(result_file, 'r', encoding='utf-8') as f:
                                content = f.read()
                                cleaned = self._clean_ocr_output(content)

                                if cleaned.strip() and len(cleaned.strip()) >= 10:
                                    prefixed_content = f"[來源文件: {pdf_path.name}]\n{cleaned}"
                                    all_docs.append(Document(
                                        page_content=prefixed_content,
                                        metadata={
                                            'pdf_file': pdf_path.name,
                                            'folder': folder_name,
                                            'source_type': 'ocr_pdf',
                                            'page': page_num,
                                            'original_text': cleaned
                                        }
                                    ))
                                    print(f"✓ ({len(cleaned)} 字元)", flush=True)
                                else:
                                    print("⚠ 內容為空", flush=True)
                        else:
                            print("⚠ 未產生結果", flush=True)

                    except Exception as e:
                        print(f"✗ 錯誤: {str(e)[:50]}", flush=True)
                        continue

            elapsed = time.time() - start_time
            if all_docs:
                print(f"     ✅ OCR 完成！耗時 {elapsed:.1f} 秒，處理 {len(all_docs)} 頁")
                self.ocr_processed_pdfs.append({
                    'file': pdf_path.name,
                    'folder': folder_name,
                    'pages': len(all_docs),
                    'time': elapsed
                })
            else:
                print(f"     ⚠️ OCR 完成但無有效內容")

        except Exception as e:
            print(f"     ❌ OCR 失敗: {str(e)[:100]}")

        return all_docs

    # === PDF 處理 ===
    def load_pdf_documents(self, folder_path):
        all_docs = []
        pdf_files = list(folder_path.glob("*.pdf"))
        if not pdf_files:
            return all_docs

        print(f"找到 {len(pdf_files)} 個PDF文件")
        for pdf_file in pdf_files:
            try:
                # 如果強制使用 OCR，直接跳過文字提取
                if self.force_ocr_all:
                    print(f"正在加載: {pdf_file.name} [強制 OCR 模式]")
                    ocr_docs = self._ocr_pdf(pdf_file, folder_path.name)
                    if ocr_docs:
                        all_docs.extend(ocr_docs)
                    else:
                        print(f"  ⚠️ OCR 處理失敗或無內容")
                        self.failed_pdfs.append({
                            'file': pdf_file.name,
                            'folder': folder_path.name,
                            'error': 'OCR 處理失敗或無有效內容'
                        })
                    continue

                # 智能模式：先嘗試提取文字
                print(f"正在加載: {pdf_file.name}")
                loader = PyPDFLoader(str(pdf_file))
                docs = loader.load()

                # 驗證是否有有效內容
                valid_docs = []
                total_text_length = 0

                for doc in docs:
                    # 清理並檢查內容
                    cleaned_content = self._clean_text(doc.page_content).strip()
                    content_without_whitespace = ''.join(cleaned_content.split())

                    # 檢查是否有實質內容（至少10個非空白字符）
                    if len(content_without_whitespace) >= 10:
                        total_text_length += len(content_without_whitespace)
                        prefixed_content = f"[來源文件: {pdf_file.name}]\n{cleaned_content}"
                        valid_docs.append(Document(
                            page_content=prefixed_content,
                            metadata={
                                **doc.metadata,
                                'pdf_file': pdf_file.name,
                                'folder': folder_path.name,
                                'source_type': 'pdf'
                            }
                        ))

                # 檢查整個PDF是否有效
                if not valid_docs or total_text_length < 50:
                    print(f"  ⚠️ 警告: {pdf_file.name} 內容為空或過少（可能是掃描版PDF）")

                    # 如果啟用 OCR，嘗試使用 OCR 處理
                    if self.enable_ocr:
                        ocr_docs = self._ocr_pdf(pdf_file, folder_path.name)
                        if ocr_docs:
                            all_docs.extend(ocr_docs)
                            # 從 empty_pdfs 記錄中移除，因為已經成功用 OCR 處理
                            continue
                        else:
                            print(f"     ⚠️ OCR 處理後仍無有效內容")

                    # 記錄空白PDF
                    self.empty_pdfs.append({
                        'file': pdf_file.name,
                        'folder': folder_path.name,
                        'pages': len(docs),
                        'total_chars': total_text_length,
                        'reason': '內容為空或過少' + ('（OCR 處理失敗）' if self.enable_ocr else '（可能需要OCR處理）')
                    })
                else:
                    all_docs.extend(valid_docs)
                    print(f"  ✅ 成功加載 {len(valid_docs)} 頁（總字符數: {total_text_length}）")

            except Exception as e:
                error_msg = str(e)[:200]
                print(f"  ❌ 處理失敗: {pdf_file.name}")
                print(f"     錯誤: {error_msg}")
                self.failed_pdfs.append({
                    'file': pdf_file.name,
                    'folder': folder_path.name,
                    'error': error_msg
                })
                continue

        return all_docs

    # === JSONL 處理（不切割）===
    def load_jsonl_files(self):
        if not self.jsonl_folder_path or not self.jsonl_folder_path.exists():
            print("⚠️ JSONL 資料夾未設定或不存在，跳過 JSONL 載入")
            return []
        
        jsonl_files = list(self.jsonl_folder_path.glob("*.jsonl"))
        if not jsonl_files:
            print("⚠️ 沒有找到 JSONL 檔案，跳過 JSONL 載入")
            return []
        
        documents = []
        seen_answer_contents = set()  # 👈 新增：用來記錄已見過的答案內容
        
        for file_path in jsonl_files:
            print(f"載入 JSONL: {file_path.name}")
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)

                        # 處理兩種格式:
                        # 格式1: 有 question 和 text 分開的欄位
                        # 格式2: text 欄位包含 "問題: xxx\n答案: xxx"
                        question_text = data.get('question', '').strip()
                        answer_text = data.get('text', '').strip()

                        # 👉 保存原始的完整文本（用於後續返回原始格式）
                        original_full_text = data.get('text', '').strip()

                        # 如果沒有 question 欄位，嘗試從 text 欄位解析
                        if not question_text and answer_text:
                            # 檢查是否為 "問題: xxx\n答案: xxx" 格式
                            if '問題:' in answer_text and '答案:' in answer_text:
                                parts = answer_text.split('\n')
                                for part in parts:
                                    if part.strip().startswith('問題:'):
                                        question_text = part.replace('問題:', '').strip()
                                    elif part.strip().startswith('答案:'):
                                        answer_text = part.replace('答案:', '').strip()
                        elif question_text and not ('問題:' in original_full_text):
                            # 格式1：如果 question 和 text 是分開的，重建原始格式
                            original_full_text = f"問題: {question_text}\n答案: {answer_text}"

                        # ===== 新增：內容去重邏輯 =====
                        if not question_text or not answer_text:
                            continue

                        # 使用答案內容的雜湊值或前200字元作為去重鍵（避免記憶體爆炸）
                        content_key = answer_text[:200]  # 或使用 hash(answer_text)
                        # if content_key in seen_answer_contents:
                        #     print(f"  跳過重複內容 (第 {line_num} 行)")
                        #     continue
                        seen_answer_contents.add(content_key)
                        # ==============================

                        # 關鍵：只嵌入問題 (Q)，答案 (A) 放在 metadata["original_text"]
                        content_parts = [question_text]
                        metadata = data.get('metadata', {})
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
                                "title": question_text,  # 👈 標題也存問題
                                "keywords": metadata.get('keywords', ''),
                                "reference": metadata.get('reference', ''),
                                "original_text": answer_text,  # 👈 答案存在 original_text
                                "original_full_text": original_full_text,  # 👈 完整的原始文本 "問題: xxx\n答案: xxx"
                                "source_type": "jsonl"
                            }
                        )
                        documents.append(doc)
                    except Exception as e:
                        print(f"  JSONL {file_path.name} 第 {line_num} 行解析錯誤: {e}")
                        continue
        print(f"✅ 總共載入 {len(documents)} 筆 JSONL 資料（已去重）")
        return documents

    # === 只載入 JSONL ===
    def load_jsonl_only(self, batch_size=50):
        """只載入 JSONL 資料到 medical_knowledge_base（會先刪除舊資料）"""
        print(f"\n{'='*80}")
        print("🔄 只載入 JSONL 資料")
        print(f"{'='*80}")

        jsonl_docs = self.load_jsonl_files()
        if not jsonl_docs:
            print("⚠️ 沒有 JSONL 資料可載入")
            return 0

        cleaned_jsonl = []
        for doc in jsonl_docs:
            cleaned = self._validate_and_clean_document(doc)
            if cleaned:
                cleaned_jsonl.append(cleaned)

        if not cleaned_jsonl:
            print("⚠️ JSONL 無有效資料")
            return 0

        saved = self._batch_save_to_vectordb(
            cleaned_jsonl,
            "medical_knowledge_base",
            batch_size
        )
        print(f"\n{'='*80}")
        print(f"✅ JSONL 載入完成！儲存 {saved} 筆至 'medical_knowledge_base'")
        print(f"{'='*80}")
        return saved

    # === 只載入 PDF ===
    def load_pdf_only(self, batch_size=20):
        """只載入 PDF 資料（會先刪除各資料夾對應的舊 collection）"""
        self.empty_pdfs = []
        self.failed_pdfs = []
        self.ocr_processed_pdfs = []

        print(f"\n{'='*80}")
        print("🔄 只載入 PDF 資料")
        print(f"{'='*80}")

        pdf_folders = [d for d in self.pdf_base_path.iterdir() if d.is_dir()]
        if not pdf_folders:
            print("⚠️ 無 PDF 資料夾")
            return 0

        total_collections = 0
        print(f"📁 找到 {len(pdf_folders)} 個 PDF 資料夾")

        for i, folder in enumerate(sorted(pdf_folders), 1):
            print(f"\n處理資料夾 {i}/{len(pdf_folders)}: {folder.name}")
            pdf_docs = self.load_pdf_documents(folder)
            if not pdf_docs:
                print(f"  跳過（無有效 PDF 內容）")
                continue

            collection_name = self.get_english_collection_name(folder.name)
            final_docs = []
            for doc in pdf_docs:
                splits = self.pdf_text_splitter.split_documents([doc])
                for split in splits:
                    split.page_content = self._clean_chunk_start(split.page_content)
                final_docs.extend(splits)

            saved = self._batch_save_to_vectordb(final_docs, collection_name, batch_size)
            if saved > 0:
                total_collections += 1
                print(f"  ✅ 儲存 {saved} 筆至 '{collection_name}'")

        print(f"\n{'='*80}")
        print(f"✅ PDF 載入完成！總共建立 {total_collections} 個 collections")
        print(f"{'='*80}")

        self.print_processing_report()
        return total_collections

    # === 統一載入：PDF + JSONL ===
    def load_all_data_unified(self, pdf_batch_size=20, jsonl_batch_size=50):
        # 重置記錄
        self.empty_pdfs = []
        self.failed_pdfs = []

        print(f"\n{'='*80}")
        print("🔄 統一載入所有資料（PDF + JSONL）")
        print(f"{'='*80}")
        total_collections = 0

        # === 1. 載入 JSONL 到 medical_knowledge_base ===
        jsonl_docs = self.load_jsonl_files()
        if jsonl_docs:
            cleaned_jsonl = []
            for doc in jsonl_docs:
                cleaned = self._validate_and_clean_document(doc)
                if cleaned:
                    cleaned_jsonl.append(cleaned)

            if cleaned_jsonl:
                saved = self._batch_save_to_vectordb(
                    cleaned_jsonl,
                    "medical_knowledge_base",
                    jsonl_batch_size
                )
                if saved > 0:
                    total_collections += 1
                    print(f"✅ JSONL 資料已儲存至 'medical_knowledge_base' ({saved} 筆)")
            else:
                print("⚠️ JSONL 無有效資料")
        else:
            print("⏭️ 跳過 JSONL 載入")

        # === 2. 載入 PDF（按資料夾）===
        pdf_folders = [d for d in self.pdf_base_path.iterdir() if d.is_dir()]
        if pdf_folders:
            print(f"\n📁 找到 {len(pdf_folders)} 個 PDF 資料夾")
            for i, folder in enumerate(sorted(pdf_folders), 1):
                print(f"\n處理資料夾 {i}/{len(pdf_folders)}: {folder.name}")
                pdf_docs = self.load_pdf_documents(folder)
                if not pdf_docs:
                    print(f"  跳過（無有效 PDF 內容）")
                    continue

                collection_name = self.get_english_collection_name(folder.name)
                final_docs = []
                for doc in pdf_docs:
                    splits = self.pdf_text_splitter.split_documents([doc])
                    # 清理分割後的文本，移除開頭的標點符號和空格
                    for split in splits:
                        split.page_content = self._clean_chunk_start(split.page_content)
                    final_docs.extend(splits)

                saved = self._batch_save_to_vectordb(final_docs, collection_name, pdf_batch_size)
                if saved > 0:
                    total_collections += 1
                    print(f"  ✅ 儲存 {saved} 筆至 '{collection_name}'")
        else:
            print("⏭️ 無 PDF 資料夾")

        print(f"\n{'='*80}")
        print(f"🎉 統一載入完成！總共建立 {total_collections} 個 collections")
        print(f"{'='*80}")

        # 顯示處理報告
        self.print_processing_report()

    # === 生成處理報告 ===
    def print_processing_report(self):
        """顯示PDF處理報告，列出空白和失敗的文件"""
        print(f"\n{'='*80}")
        print("📊 PDF 處理報告")
        print(f"{'='*80}")

        # OCR 處理統計
        if self.ocr_processed_pdfs:
            total_time = sum(item['time'] for item in self.ocr_processed_pdfs)
            total_pages = sum(item['pages'] for item in self.ocr_processed_pdfs)
            print(f"\n🔍 OCR 處理統計 ({len(self.ocr_processed_pdfs)} 個 PDF):")
            print("-" * 80)
            for idx, item in enumerate(self.ocr_processed_pdfs, 1):
                print(f"{idx}. 檔案: {item['folder']}/{item['file']}")
                print(f"   頁數: {item['pages']}, 耗時: {item['time']:.1f} 秒")
            print(f"\n   總計: {total_pages} 頁, {total_time:.1f} 秒")

        if self.empty_pdfs:
            print(f"\n⚠️ 空白或內容過少的 PDF ({len(self.empty_pdfs)} 個):")
            if not self.enable_ocr:
                print("提示：啟用 OCR 功能可以處理掃描版 PDF")
            print("-" * 80)
            for idx, item in enumerate(self.empty_pdfs, 1):
                print(f"{idx}. 檔案: {item['folder']}/{item['file']}")
                print(f"   頁數: {item['pages']}, 字符數: {item['total_chars']}")
                print(f"   原因: {item['reason']}")
        else:
            print("\n✅ 所有 PDF 都有有效內容")

        if self.failed_pdfs:
            print(f"\n❌ 處理失敗的 PDF ({len(self.failed_pdfs)} 個):")
            print("-" * 80)
            for idx, item in enumerate(self.failed_pdfs, 1):
                print(f"{idx}. 檔案: {item['folder']}/{item['file']}")
                print(f"   錯誤: {item['error']}")
        else:
            print("\n✅ 所有 PDF 處理成功")

        # 保存報告到文件
        if self.empty_pdfs or self.failed_pdfs or self.ocr_processed_pdfs:
            # 使用相對路徑
            report_path = Path("./pdf_processing_report.txt")
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("PDF 處理報告\n")
                f.write("=" * 80 + "\n\n")

                if self.ocr_processed_pdfs:
                    total_time = sum(item['time'] for item in self.ocr_processed_pdfs)
                    total_pages = sum(item['pages'] for item in self.ocr_processed_pdfs)
                    f.write(f"OCR 處理統計 ({len(self.ocr_processed_pdfs)} 個 PDF):\n")
                    f.write("-" * 80 + "\n")
                    for item in self.ocr_processed_pdfs:
                        f.write(f"檔案: {item['folder']}/{item['file']}\n")
                        f.write(f"頁數: {item['pages']}, 耗時: {item['time']:.1f} 秒\n\n")
                    f.write(f"總計: {total_pages} 頁, {total_time:.1f} 秒\n\n")

                if self.empty_pdfs:
                    f.write(f"空白或內容過少的 PDF ({len(self.empty_pdfs)} 個):\n")
                    f.write("-" * 80 + "\n")
                    for item in self.empty_pdfs:
                        f.write(f"檔案: {item['folder']}/{item['file']}\n")
                        f.write(f"頁數: {item['pages']}, 字符數: {item['total_chars']}\n")
                        f.write(f"原因: {item['reason']}\n\n")

                if self.failed_pdfs:
                    f.write(f"\n處理失敗的 PDF ({len(self.failed_pdfs)} 個):\n")
                    f.write("-" * 80 + "\n")
                    for item in self.failed_pdfs:
                        f.write(f"檔案: {item['folder']}/{item['file']}\n")
                        f.write(f"錯誤: {item['error']}\n\n")

            print(f"\n📄 詳細報告已保存至: {report_path}")

        print(f"{'='*80}\n")

    # === 其他必要方法（保持不變）===
    def list_collections(self):
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cursor = conn.cursor()
            cursor.execute("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name='langchain_pg_collection');")
            if not cursor.fetchone()[0]:
                print("langchain_pg_collection 表不存在")
                return
            cursor.execute("SELECT name FROM langchain_pg_collection ORDER BY name;")
            collections = [row[0] for row in cursor.fetchall()]
            print(f"\n已建立的 Collections ({len(collections)} 個):")
            for i, name in enumerate(collections, 1):
                print(f"{i:2d}. {name}")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"列出 collections 失敗: {e}")

    def search_test(self, query, collection_name=None):
        try:
            if not collection_name:
                conn = psycopg2.connect(self.db_connection_string)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM langchain_pg_collection LIMIT 1;")
                result = cursor.fetchone()
                cursor.close()
                conn.close()
                if not result:
                    print("無可用 collection")
                    return
                collection_name = result[0]
            
            print(f"\n在 collection '{collection_name}' 中搜尋: '{query}'")
            vectorstore = PGVector(
                embeddings=self.embeddings,
                connection=self.db_connection_string,
                collection_name=collection_name,
            )
            results = vectorstore.similarity_search_with_score(query, k=5)
            print(f"找到 {len(results)} 個結果:")
            for i, (doc, score) in enumerate(results, 1):
                source_type = doc.metadata.get('source_type', 'unknown')
                print(f"\n結果 {i} (相似度: {score:.4f}, 來源: {source_type})")

                if source_type == 'pdf':
                    preview = doc.page_content[:].replace('\n', ' ')
                    print(f"  內容: {preview}...")
                    print(f"  PDF: {doc.metadata.get('pdf_file', 'N/A')}")
                elif source_type == 'jsonl':
                    # 顯示完整的問題和答案
                    question = doc.metadata.get('title', 'N/A')
                    answer = doc.metadata.get('original_text', 'N/A')
                    print(f"  問題: {question}")
                    print(f"  答案: {answer[:]}{'...' if len(answer) > 300 else ''}")
                    print(f"  來源檔案: {doc.metadata.get('source_file', 'N/A')}")
                    print(f"  關鍵字: {doc.metadata.get('keywords', 'N/A')}")
                else:
                    preview = doc.page_content[:].replace('\n', ' ')
                    print(f"  內容: {preview}...")
        except Exception as e:
            print(f"搜尋失敗: {e}")

    def reset_database(self):
        """⚠️ 危險：刪除所有 collections（包括 mem0、educational_images 等）"""
        try:
            conn = psycopg2.connect(self.db_connection_string)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            print("\n⚠️  警告：這會刪除所有資料，包括 mem0、educational_images 等！")
            print("    建議使用選項 5/6/7 來單獨刪除 JSONL 或 PDF 資料。")
            confirm = input("\n輸入 'DELETE ALL' 確認刪除所有資料: ").strip()
            if confirm == 'DELETE ALL':
                for table in ['langchain_pg_embedding', 'langchain_pg_collection']:
                    cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                    print(f"已刪除 {table}")
                print("資料庫重置完成")
            else:
                print("已取消")
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"重置失敗: {e}")

    def delete_collection(self, collection_name):
        """刪除指定的 collection"""
        try:
            conn = psycopg2.connect(self.db_connection_string)
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()

            # 先取得 collection 的 uuid
            cursor.execute(
                "SELECT uuid FROM langchain_pg_collection WHERE name = %s;",
                (collection_name,)
            )
            result = cursor.fetchone()

            if not result:
                print(f"❌ Collection '{collection_name}' 不存在")
                cursor.close()
                conn.close()
                return False

            collection_uuid = result[0]

            # 刪除該 collection 的所有 embeddings
            cursor.execute(
                "DELETE FROM langchain_pg_embedding WHERE collection_id = %s;",
                (collection_uuid,)
            )
            deleted_embeddings = cursor.rowcount

            # 刪除 collection 記錄
            cursor.execute(
                "DELETE FROM langchain_pg_collection WHERE uuid = %s;",
                (collection_uuid,)
            )

            print(f"✅ 已刪除 collection '{collection_name}' ({deleted_embeddings} 筆資料)")
            cursor.close()
            conn.close()
            return True

        except Exception as e:
            print(f"❌ 刪除失敗: {e}")
            return False

    def delete_jsonl_collection(self):
        """刪除 JSONL 資料（medical_knowledge_base）"""
        print("\n🗑️  刪除 JSONL 資料 (medical_knowledge_base)")
        confirm = input("確定刪除 medical_knowledge_base? (y/N): ").strip().lower()
        if confirm == 'y':
            return self.delete_collection("medical_knowledge_base")
        else:
            print("已取消")
            return False

    def delete_pdf_collections(self):
        """刪除所有 PDF collections（根據 folder_mapping）"""
        print("\n🗑️  刪除 PDF 資料")
        print("將刪除以下 collections:")

        # 列出所有 PDF collections
        pdf_collections = list(self.folder_mapping.values())
        for i, name in enumerate(pdf_collections, 1):
            print(f"  {i}. {name}")

        confirm = input(f"\n確定刪除以上 {len(pdf_collections)} 個 PDF collections? (y/N): ").strip().lower()
        if confirm == 'y':
            success_count = 0
            for coll_name in pdf_collections:
                if self.delete_collection(coll_name):
                    success_count += 1
            print(f"\n✅ 成功刪除 {success_count}/{len(pdf_collections)} 個 PDF collections")
            return True
        else:
            print("已取消")
            return False

    def delete_specific_collection_interactive(self):
        """互動式刪除指定 collection"""
        self.list_collections()
        coll_name = input("\n請輸入要刪除的 collection 名稱: ").strip()
        if not coll_name:
            print("已取消")
            return False

        # 安全檢查：警告刪除重要的 collections
        protected_collections = ['memory_agent_chinese_v2', 'educational_images']
        if coll_name in protected_collections:
            print(f"\n⚠️  警告：'{coll_name}' 是重要的系統資料！")
            confirm = input(f"確定要刪除 '{coll_name}'? 輸入 'YES' 確認: ").strip()
            if confirm != 'YES':
                print("已取消")
                return False
        else:
            confirm = input(f"確定刪除 '{coll_name}'? (y/N): ").strip().lower()
            if confirm != 'y':
                print("已取消")
                return False

        return self.delete_collection(coll_name)

    def _clean_text(self, text):
        if not text: return ""
        cleaned = ""
        for char in text:
            cp = ord(char)
            if 0xD800 <= cp <= 0xDFFF: continue
            if cp < 32 and char not in '\n\r\t': continue
            cleaned += char
        return cleaned

    def _clean_chunk_start(self, text):
        """清理文本開頭的標點符號和空格，保持句子完整性"""
        if not text:
            return text

        # 移除開頭的標點符號（句號、驚嘆號、問號）和空格
        cleaned = text.lstrip()
        while cleaned and cleaned[0] in '。！？.,!? \t\n':
            cleaned = cleaned[1:].lstrip()

        return cleaned

    def _validate_and_clean_document(self, doc):
        try:
            if not isinstance(doc.page_content, str):
                doc.page_content = str(doc.page_content) if doc.page_content else ""
            doc.page_content = self._clean_text(doc.page_content).strip()
            if not doc.page_content or len(doc.page_content) < 10:
                return None
            try:
                doc.page_content.encode('utf-8', errors='strict')
            except UnicodeEncodeError:
                doc.page_content = doc.page_content.encode('utf-8', errors='replace').decode('utf-8')
            if doc.metadata:
                cleaned_meta = {}
                for k, v in doc.metadata.items():
                    if v is None: cleaned_meta[k] = ""
                    elif isinstance(v, (str, int, float, bool)):
                        cleaned_meta[k] = self._clean_text(v) if isinstance(v, str) else v
                    else:
                        cleaned_meta[k] = self._clean_text(str(v))
                doc.metadata = cleaned_meta
            return doc
        except Exception as e:
            print(f"清理文檔錯誤: {e}")
            return None

    def _batch_save_to_vectordb(self, documents, collection_name, batch_size):
        print(f"\n儲存 {len(documents)} 筆至 '{collection_name}'...")
        cleaned = [self._validate_and_clean_document(d) for d in documents]
        cleaned = [d for d in cleaned if d is not None]
        if not cleaned:
            print("無有效文檔")
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
            except Exception as e:
                print(f"批次 {i//batch_size + 1} 錯誤: {str(e)[:100]}")
                continue
        return total_saved


# ===== 主程式 =====
def main():
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    db_connection_string = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    PDF_DATA_PATH = "/home/danny/AI-agent/DataSet"
    JSONL_DATA_PATH = "/home/danny/AI-agent/RAG_JSONL"  # 請確認路徑正確

    print("向量資料庫載入工具（統一載入 PDF + JSONL）")
    print("="*60)

    # 詢問是否啟用 OCR
    enable_ocr = False
    force_ocr_all = False

    if OCR_AVAILABLE:
        print("\nOCR 處理模式:")
        print("1. 智能模式（推薦）- 只對掃描版 PDF 使用 OCR")
        print("2. 強制模式 - 所有 PDF 都使用 OCR（更完整但較慢）")
        print("3. 不使用 OCR")

        ocr_choice = input("\n請選擇 (1-3, 預設 1): ").strip() or "1"

        if ocr_choice == "1":
            enable_ocr = True
            ocr_mode_text = "智能 OCR"
        elif ocr_choice == "2":
            force_ocr_all = True
            ocr_mode_text = "強制 OCR (所有PDF)"
        else:
            ocr_mode_text = "不使用 OCR"
    else:
        ocr_mode_text = "OCR 未安裝"
        print("\n⚠️ OCR 模組未安裝，將跳過掃描版 PDF 處理")

    loader = UnifiedVectorDBLoader(
        db_connection_string,
        PDF_DATA_PATH,
        JSONL_DATA_PATH,
        enable_ocr=enable_ocr,
        force_ocr_all=force_ocr_all
    )

    while True:
        print("\n" + "="*60)
        print("選項:")
        print("="*60)
        print("【載入資料】")
        print(f"1. 🚀 統一載入所有資料（PDF + JSONL） [{ocr_mode_text}]")
        print("2. 📄 只載入 JSONL 資料 (重寫 medical_knowledge_base)")
        print(f"3. 📁 只載入 PDF 資料 (重寫各 PDF collections) [{ocr_mode_text}]")
        print("-" * 60)
        print("【查詢】")
        print("4. 📋 列出所有 Collections")
        print("5. 🔍 測試搜尋功能")
        print("-" * 60)
        print("【刪除資料】")
        print("6. 🗑️  只刪除 JSONL 資料 (medical_knowledge_base)")
        print("7. 🗑️  只刪除 PDF 資料 (所有 PDF collections)")
        print("8. 🗑️  刪除指定 Collection")
        print("-" * 60)
        print("9. ⚠️  重置整個資料庫（危險！刪除所有資料）")
        print("0. ⛔ 退出")

        choice = input("\n請選擇 (0-9): ").strip()

        if choice == '1':
            pdf_batch = int(input("PDF 批次大小 (預設 20): ") or "20")
            jsonl_batch = int(input("JSONL 批次大小 (預設 50): ") or "50")
            confirm = input("⚠️ 確定統一載入所有資料？(y/N): ").strip().lower()
            if confirm == 'y':
                loader.load_all_data_unified(pdf_batch, jsonl_batch)

        elif choice == '2':
            jsonl_batch = int(input("JSONL 批次大小 (預設 50): ") or "50")
            confirm = input("⚠️ 確定重寫 JSONL 資料？(會覆蓋 medical_knowledge_base) (y/N): ").strip().lower()
            if confirm == 'y':
                loader.load_jsonl_only(jsonl_batch)

        elif choice == '3':
            pdf_batch = int(input("PDF 批次大小 (預設 20): ") or "20")
            confirm = input("⚠️ 確定重寫 PDF 資料？(會覆蓋各 PDF collections) (y/N): ").strip().lower()
            if confirm == 'y':
                loader.load_pdf_only(pdf_batch)

        elif choice == '4':
            loader.list_collections()

        elif choice == '5':
            query = input("搜尋關鍵字: ").strip() or "狂犬病個人防護裝備"
            coll = input("Collection (留空自動): ").strip() or None
            loader.search_test(query, coll)

        elif choice == '6':
            loader.delete_jsonl_collection()

        elif choice == '7':
            loader.delete_pdf_collections()

        elif choice == '8':
            loader.delete_specific_collection_interactive()

        elif choice == '9':
            loader.reset_database()

        elif choice == '0':
            print("結束")
            break
        else:
            print("無效選項")

if __name__ == "__main__":
    main()