#!/usr/bin/env python3
"""
🏥 醫療衛教圖片自動化處理流水線 - 單階段嚴格版

改進點：
1. 整合兩階段標準到一個嚴格的 Prompt，省時間
2. 必須同時滿足：醫療相關 + 有實用衛教價值 + 有文字說明
3. 嚴格排除：裝飾性、卡通、純器官圖示、無文字照片
4. 批次處理 + 記憶體優化 + 斷點續傳
"""

import os
import sys
import json
import torch
import hashlib
import io
import re
import fitz
import asyncio
import logging
from pathlib import Path
from tqdm.asyncio import tqdm
from PIL import Image
from concurrent.futures import ThreadPoolExecutor
from transformers import AutoModelForVision2Seq, AutoProcessor
from langchain_core.documents import Document
from langchain_postgres.vectorstores import PGVector

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from core.config import DB_CONNECTION_STRING, embeddings

# ==================== 配置 ====================
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

TEMP_IMAGE_DIR = Path("/home/danny/AI-agent/image_search")
FINAL_IMAGE_DIR = Path("/home/danny/AI-agent/high_value_images")
PIPELINE_DATA_DIR = Path("/home/danny/AI-agent/pipeline_data")
MAPPING_JSON = PIPELINE_DATA_DIR / "image_source_mapping.json"
ANALYSIS_JSON = PIPELINE_DATA_DIR / "final_educational_analysis_strict.json"
PROCESSED_JSON = PIPELINE_DATA_DIR / "all_processed_images_strict.json"
VLM_MODEL_PATH = "/home/danny/AI-agent/Qwen3_4b_VL"

BATCH_SIZE = 2
MIN_SCORE = 4  # 嚴格門檻

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("StrictPipeline")

# 🆕 整合兩階段標準的嚴格 Prompt
STRICT_PROMPT = """請嚴格評估這張圖片是否為「高品質醫療衛教內容，病人/民眾可以直接看懂並實際使用」。

**✓ 必須同時滿足以下所有條件（評分 4-5）：**

1. **醫療相關性**：包含真實的醫療或健康教育內容（疾病、症狀、治療、預防、檢查等）
2. **有文字說明**：圖片包含清晰可讀的文字說明、標註、步驟或數據
3. **民眾可看懂**：普通人不需醫學背景即可理解並使用
4. **實用價值高**：屬於以下類型之一
   - 步驟化操作指導（如：洗手步驟、用藥指南、傷口處理）
   - 症狀對照圖示（如：皮疹分級、姿勢正誤對比）
   - 數據表格圖表（如：血糖紀錄表、用藥時間表）
   - 檢查流程圖（如：篩檢流程、就醫步驟）
   - 注意事項列表（如：術後照護、飲食禁忌）

**✗ 必須嚴格排除以下類型（評分 1-2）：**

1. **裝飾性圖片**：
   - 卡通人物、吉祥物、表情符號
   - 背景圖案、邊框裝飾、分隔線
   - 純美化用途的插圖

2. **缺乏文字說明**：
   - 沒有任何文字標註的照片或插圖
   - 單純的器官圖示、解剖圖（沒有說明文字）
   - 純照片沒有標註或解釋

3. **內容不明確**：
   - 模糊不清、無法閱讀的內容
   - 只有標題沒有具體內容的封面頁
   - 過於抽象、民眾無法理解的示意圖
   - 只有診斷名稱沒有說明的標題頁

4. **非實用性內容**：
   - 純粹的醫院介紹、科室簡介
   - 醫師或護理人員的肖像照
   - 醫療設備的產品照（沒有使用說明）

**輸出格式（必須是有效的 JSON）：**
{
  "is_health_related": true/false,
  "has_text_description": true/false,
  "is_self_explanatory": true/false,
  "is_decorative": true/false,
  "health_topic": "主題（如：糖尿病、洗手衛教、用藥安全）",
  "main_category": "分類（如：慢性病管理/感染控制/用藥指導/檢查流程/術後照護）",
  "content_type": "步驟說明/症狀圖示/注意事項/檢查流程/數據表格/裝飾性/封面頁/其他",
  "core_message": "核心訊息（1句話）",
  "detailed_description": "詳細描述圖片內容和衛教重點（2-3句）",
  "score": 1-5,
  "rejection_reason": "如果評分<4，說明具體原因（如：缺乏文字說明/純裝飾性/內容模糊）"
}

**評分標準：**
- 5分：完美衛教內容，有清晰文字+圖示，民眾可直接使用
- 4分：良好衛教內容，有文字說明，具實用價值
- 3分：有醫療相關性，但缺乏文字說明或不夠實用
- 2分：醫療相關但無實用價值（如：單純器官圖、封面頁）
- 1分：裝飾性圖片或非醫療內容

只輸出 JSON，不要其他文字。"""

class StrictHealthImagePipeline:
    def __init__(self):
        self.mapping = {}
        self.model = None
        self.processor = None
        for d in [TEMP_IMAGE_DIR, FINAL_IMAGE_DIR, PIPELINE_DATA_DIR]:
            d.mkdir(parents=True, exist_ok=True)
        if MAPPING_JSON.exists():
            self.mapping = json.loads(MAPPING_JSON.read_text(encoding='utf-8'))

    def load_vlm(self):
        if self.model is None:
            logger.info("正在載入 VLM 模型並準備批次推理...")
            self.model = AutoModelForVision2Seq.from_pretrained(
                VLM_MODEL_PATH,
                torch_dtype=torch.bfloat16,
                attn_implementation="sdpa",
                device_map="auto",
                max_memory={0: "28GB"},
                low_cpu_mem_usage=True,
            ).eval()
            self.processor = AutoProcessor.from_pretrained(
                VLM_MODEL_PATH,
                min_pixels=256*28*28,
                max_pixels=512*28*28,
            )
            self.processor.tokenizer.padding_side = "left"

    # ---------- 階段 1: 多執行緒提取 (含全域去重) ----------

    def _extract_single_pdf(self, pdf_path: Path):
        local_extracted = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                for img_idx, img_info in enumerate(page.get_images(full=True), 1):
                    xref = img_info[0]
                    base_image = doc.extract_image(xref)
                    img_data = base_image["image"]
                    img_hash = hashlib.md5(img_data).hexdigest()
                    image = Image.open(io.BytesIO(img_data))
                    if image.width < 150 or image.height < 150: continue
                    filename = f"{pdf_path.stem}_p{page_num+1}_img{img_idx}.jpg"
                    local_extracted.append({
                        "hash": img_hash,
                        "filename": filename,
                        "data": img_data,
                        "source": {"source_pdf": pdf_path.name, "page": page_num + 1}
                    })
            doc.close()
        except Exception as e:
            logger.error(f"提取失敗 {pdf_path.name}: {e}")
        return local_extracted

    async def step1_extract_async(self):
        logger.info("--- 階段 1: 多執行緒提取圖片 (含全域指紋去重) ---")
        pdf_files = list(Path("/home/danny/AI-agent/DataSet").rglob("*.pdf"))
        with ThreadPoolExecutor(max_workers=10) as executor:
            loop = asyncio.get_event_loop()
            tasks = [loop.run_in_executor(executor, self._extract_single_pdf, p) for p in pdf_files]
            all_raw_results = await tqdm.gather(*tasks, desc="並行提取 PDF")

        seen_hashes = set()
        for info in self.mapping.values():
            if "hash" in info:
                seen_hashes.add(info["hash"])

        unique_count = 0
        for pdf_result in all_raw_results:
            for item in pdf_result:
                h = item["hash"]
                if h not in seen_hashes:
                    seen_hashes.add(h)
                    fname = item["filename"]
                    save_path = TEMP_IMAGE_DIR / fname
                    with open(save_path, "wb") as f:
                        f.write(item["data"])
                    item["source"]["hash"] = h
                    self.mapping[fname] = item["source"]
                    unique_count += 1

        MAPPING_JSON.write_text(json.dumps(self.mapping, ensure_ascii=False, indent=2))
        logger.info(f"✅ 提取完成！經指紋去重後，本次新增 {unique_count} 張唯一圖片。")

    # ---------- 階段 2 & 3: 嚴格批次推理 ----------

    async def step2_3_strict_analyze(self):
        logger.info("--- 階段 2 & 3: 嚴格 VLM 分析（整合兩階段標準）---")
        self.load_vlm()

        image_files = sorted([f for f in TEMP_IMAGE_DIR.glob("*.jpg")])

        # 載入高分結果
        final_results = {}
        if ANALYSIS_JSON.exists():
            final_results = json.loads(ANALYSIS_JSON.read_text(encoding='utf-8')).get("educational_content", {})

        # 載入已處理列表
        processed_images = set()
        if PROCESSED_JSON.exists():
            processed_images = set(json.loads(PROCESSED_JSON.read_text(encoding='utf-8')).get("processed", []))

        to_process = [f for f in image_files if f.name not in processed_images]

        logger.info(f"圖片總數: {len(image_files)} 張")
        logger.info(f"已處理: {len(processed_images)} 張")
        logger.info(f"待處理: {len(to_process)} 張, 批次大小: {BATCH_SIZE}")

        if len(to_process) == 0:
            logger.info("✅ 所有圖片已處理完成，跳過分析階段")
            return

        pbar = tqdm(total=len(to_process), desc="嚴格 VLM 分析")

        for i in range(0, len(to_process), BATCH_SIZE):
            batch_files = to_process[i : i + BATCH_SIZE]
            batch_results, batch_processed = self._process_batch(batch_files)

            processed_images.update(batch_processed)
            self._save_processed_list(processed_images)

            if batch_results:
                final_results.update(batch_results)
                self._save_results(final_results)

            torch.cuda.empty_cache()
            pbar.update(len(batch_files))

        pbar.close()
        logger.info(f"✅ 嚴格分析完成！高品質圖片: {len(final_results)} 張")

    def _extract_topic_from_filename(self, filename: str) -> str:
        """從檔案名稱提取主題提示（去掉 _p1_img1.jpg 等後綴）"""
        # 移除副檔名和頁碼/圖片編號後綴
        topic = re.sub(r'_p\d+_i(mg)?\d+\.jpg$', '', filename, flags=re.IGNORECASE)
        # 將底線替換為空格，讓提示更自然
        topic = topic.replace('_', ' ')
        return topic

    def _process_batch(self, batch_files):
        batch_results = {}
        batch_processed = set()
        batch_images = []
        inputs = None
        generated_ids = None

        try:
            batch_images = [Image.open(f) for f in batch_files]

            # 為每張圖片建立帶有檔案名稱提示的 prompt
            messages_batch = []
            for idx, img in enumerate(batch_images):
                filename = batch_files[idx].name
                topic_hint = self._extract_topic_from_filename(filename)

                # 將檔案名稱主題加入 prompt，幫助 VLM 產生更精確的描述
                prompt_with_context = f"【參考資訊】這張圖片來自衛教文件「{topic_hint}」，請參考此主題來分析圖片內容。\n\n{STRICT_PROMPT}"

                messages_batch.append([{
                    "role": "user",
                    "content": [
                        {"type": "image", "image": img},
                        {"type": "text", "text": prompt_with_context}
                    ],
                }])

            batch_texts = [
                self.processor.apply_chat_template(m, tokenize=False, add_generation_prompt=True)
                for m in messages_batch
            ]
            del messages_batch

            inputs = self.processor(
                text=batch_texts,
                images=batch_images,
                return_tensors="pt",
                padding=True
            ).to(self.model.device)
            del batch_texts

            with torch.no_grad():
                generated_ids = self.model.generate(**inputs, max_new_tokens=500)

            # 保存 input_ids 長度以便後續 trim
            input_lengths = [len(ids) for ids in inputs.input_ids]

            del inputs
            inputs = None
            torch.cuda.empty_cache()

            generated_ids_cpu = generated_ids.cpu()
            del generated_ids
            generated_ids = None
            torch.cuda.empty_cache()

            # 只解碼新生成的部分（去掉 prompt）
            generated_ids_trimmed = [
                out_ids[input_len:] for out_ids, input_len in zip(generated_ids_cpu, input_lengths)
            ]
            output_texts = self.processor.batch_decode(
                generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
            )
            del generated_ids_cpu, generated_ids_trimmed

            for idx, text_res in enumerate(output_texts):
                img_name = batch_files[idx].name
                batch_processed.add(img_name)

                json_res = self._parse_json(text_res)

                # 🔧 嚴格過濾條件：
                # 1. 醫療相關 (is_health_related = true)
                # 2. 有文字說明 (has_text_description = true)
                # 3. 非裝飾性 (is_decorative = false)
                # 4. 高分 (score >= MIN_SCORE)
                if (json_res and
                    json_res.get("is_health_related") and
                    json_res.get("has_text_description") and
                    not json_res.get("is_decorative", False) and
                    json_res.get("score", 0) >= MIN_SCORE):

                    source = self.mapping.get(img_name, {})
                    json_res.update({
                        "source_pdf": source.get("source_pdf", "Unknown"),
                        "page": source.get("page", 0),
                        "filename": img_name
                    })
                    batch_results[img_name] = json_res

                    # 歸檔高品質圖片
                    try:
                        img_to_save = batch_images[idx]
                        if img_to_save.mode != 'RGB':
                            img_to_save = img_to_save.convert('RGB')
                        img_to_save.save(FINAL_IMAGE_DIR / img_name, 'JPEG', quality=95)
                    except Exception as save_err:
                        logger.error(f"存檔失敗 {img_name}: {save_err}")

                    logger.info(f"✓ {img_name} (分數:{json_res.get('score')}) {json_res.get('content_type')}")
                else:
                    # 記錄拒絕原因 - 顯示詳細的檢查結果
                    if json_res:
                        score = json_res.get("score", 0)
                        is_health = json_res.get("is_health_related", False)
                        has_text = json_res.get("has_text_description", False)
                        is_deco = json_res.get("is_decorative", False)
                        rejection = json_res.get("rejection_reason", "未達標準")

                        logger.warning(
                            f"✗ {img_name} - 評分:{score} | "
                            f"醫療相關:{is_health} | 有文字:{has_text} | "
                            f"裝飾性:{is_deco} | 原因:{rejection}"
                        )
                    else:
                        logger.error(f"✗ {img_name} - JSON 解析失敗")
                        logger.error(f"   VLM 輸出: {text_res[:200]}...")

        except Exception as e:
            logger.error(f"批次處理出錯: {e}")
            import traceback
            logger.error(f"錯誤詳情:\n{traceback.format_exc()}")
        finally:
            if inputs is not None:
                del inputs
            if generated_ids is not None:
                del generated_ids
            for img in batch_images:
                try: img.close()
                except: pass
            torch.cuda.empty_cache()

        return batch_results, batch_processed

    def _parse_json(self, text):
        try:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                json_str = match.group(0)
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 解析錯誤: {e}")
                    logger.error(f"JSON 內容: {json_str[:300]}...")
                    return None
            else:
                logger.error(f"未找到 JSON 格式")
                logger.error(f"VLM 輸出: {text[:300]}...")
                return None
        except Exception as e:
            logger.error(f"_parse_json 發生錯誤: {e}")
            return None

    def _save_results(self, results):
        ANALYSIS_JSON.write_text(json.dumps({"count": len(results), "educational_content": results}, ensure_ascii=False, indent=2))

    def _save_processed_list(self, processed_set):
        PROCESSED_JSON.write_text(json.dumps({"count": len(processed_set), "processed": sorted(list(processed_set))}, ensure_ascii=False, indent=2))

    # ---------- 階段 4: 同步資料庫 ----------

    async def step4_sync_db_async(self, chunk_size: int = 500):
        logger.info("--- 階段 4: 分批次寫入向量資料庫 ---")
        if not ANALYSIS_JSON.exists():
            logger.warning("找不到分析結果，跳過同步。")
            return

        data = json.loads(ANALYSIS_JSON.read_text(encoding='utf-8'))
        contents = data.get("educational_content", {})
        all_docs = []

        for filename, info in contents.items():
            page_content = f"主題: {info.get('health_topic')}\n分類: {info.get('main_category')}\n核心訊息: {info.get('core_message')}\n詳細描述: {info.get('detailed_description')}\n來源文件: {info.get('source_pdf')}"
            metadata = {
                "filename": filename,
                "image_path": filename,
                "health_topic": info.get("health_topic"),
                "main_category": info.get("main_category"),
                "content_type": info.get("content_type"),
                "has_text_description": info.get("has_text_description"),
                "is_self_explanatory": info.get("is_self_explanatory"),
                "source_pdf": info.get("source_pdf"),
                "page": info.get("page"),
                "score": info.get("score"),
                "source": "strict_pipeline"
            }
            all_docs.append(Document(page_content=page_content, metadata=metadata))

        if not all_docs:
            return

        logger.info(f"總共準備了 {len(all_docs)} 筆資料，將以每批 {chunk_size} 筆進行同步...")

        try:
            # 🔧 使用测试集合名称，避免覆盖现有数据
            # 如果测试满意，可以改为 "educational_images"
            collection_name = "educational_images_strict_test"

            first_chunk = all_docs[:chunk_size]
            vector_store = PGVector.from_documents(
                documents=first_chunk,
                embedding=embeddings,
                connection=DB_CONNECTION_STRING,
                collection_name=collection_name,
                use_jsonb=True,
                pre_delete_collection=True
            )
            logger.info(f"✅ 已完成第一批次 ({len(first_chunk)} 筆) 並重設資料庫")

            for i in range(chunk_size, len(all_docs), chunk_size):
                chunk = all_docs[i : i + chunk_size]
                vector_store.add_documents(chunk)
                logger.info(f"✅ 已追加批次 {i//chunk_size + 1} ({i} ~ {min(i+chunk_size, len(all_docs))} 筆)")

            logger.info(f"🎉 全部 {len(all_docs)} 筆資料同步完成！")
        except Exception as e:
            logger.error(f"資料庫分批寫入失敗: {e}")
            import traceback
            traceback.print_exc()

async def main():
    pipeline = StrictHealthImagePipeline()
    await pipeline.step1_extract_async()
    await pipeline.step2_3_strict_analyze()  # 嚴格單階段分析
    await pipeline.step4_sync_db_async()
    logger.info("🚀 所有任務處理完成！")

if __name__ == "__main__":
    asyncio.run(main())
