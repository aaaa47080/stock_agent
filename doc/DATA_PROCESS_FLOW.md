# Data Processing Workflow Handover (Detailed Execution Flow)

此文件詳細記錄 `Agent_System/data_process/` 下核心腳本的**完整執行邏輯與順序**，包含變數傳遞、迴圈結構與錯誤處理機制，供開發者進行維護或重構。

## 目錄
1. [ingest_health_images.py (感染科與衛教圖片 pipeline)](#1-ingest_health_imagespy-衛教圖片流水線)
    - [資料源映射配置 (datasource_image_config.json)](#⚙️-資料源映射配置-datasource_image_configjson)
2. [ingest_general_medical.py (感染科與衛教文字資料PDF+Jsonl pipeline)](#2-ingest_general_medicalpy-通用-rag-載入器)
3. [ingest_dialysis_pdf.py (洗腎深度 OCR（文字＋表格）pipeline)](#3-ingest_dialysis_pdfpy-洗腎深度-ocr-處理)

---

## 1. `ingest_health_images.py` (感染科與衛教圖片 PipeLine，圖片大部分少文字＋規則表格)

### 執行順序
1. **初始化**：建立 `high_value_images/` 等目錄。
2. **提取與去重**：使用 `ThreadPoolExecutor` 平行提取 PDF 圖片，計算 MD5 Hash 去重，暫存於 `image_search/`。
3. **嚴格分析 (VLM)**：使用 `Qwen3_4b_VL` 批次分析圖片，僅保留 **Score >= 4** 且具備實用文字說明的衛教圖片。
4. **資料庫同步**：將分析結果與高品質圖片路徑寫入 `educational_images_strict_test`。

### 💾 資料儲存格式 (VDB Format)
*   **Collection Name**: `educational_images_strict_test` (或 `educational_images`)
*   **Page Content**:
    ```text
    主題: {health_topic}
    分類: {main_category}
    核心訊息: {core_message}
    詳細描述: {detailed_description}
    來源文件: {source_pdf}
    ```
*   **Metadata**:
    *   `filename`: 圖片檔名 (例如 `abc_p1_img1.jpg`)
    *   `image_path`: 圖片路徑 (同 filename)
    *   `health_topic`: 衛教主題
    *   `main_category`: 醫學分類 (如慢性病管理、感染控制)
    *   `content_type`: 內容類型 (步驟說明、症狀圖示、注意事項等)
    *   `score`: VLM 評分 (4-5)
    *   `source_pdf`: 原始 PDF 來源
    *   `page`: 所在頁碼
    *   `source`: 標記為 `strict_pipeline`

### ⚙️ 資料源映射配置 (datasource_image_config.json)
為了讓系統能根據檢索到的文字內容精準匹配對應類別的圖片，我們使用此設定檔定義「PDF 路徑」與「資料源」的關係：
1. **目錄定義**：定義 `public_health` (衛教園地) 與 `infection_control` (感染控制) 等圖片目錄所對應的 PDF 原始路徑。
2. **文字轉圖片映射** (`text_to_image_datasource_mapping`)：定義當檢索到特定的文字資料源（如 `medical_kb_jsonl`）時，系統應優先去哪個圖片類別中尋找對應圖示。
3. **自動映射機制**：系統啟動時會掃描設定的目錄，建立「PDF 檔名 -> 資料源 ID」的映射表，確保檢索時能根據 `source_pdf` 元數據過濾出正確的圖片。

---

## 2. `ingest_general_medical.py` (通用 RAG 載入器)

### 執行順序
1. **模式判定**：決定是否啟用 DeepSeek OCR (掃描件自動觸發)。
2. **JSONL 處理**：載入問答對，採「嵌入問題、儲存答案」策略。
3. **PDF 處理**：按資料夾遍歷，提取文字或執行 OCR，進行文本切分與清理。

### 💾 資料儲存格式 (VDB Format)

#### **A. JSONL 資料格式**
*   **Collection Name**: `medical_knowledge_base`
*   **Page Content** (僅包含問題與輔助檢索資訊):
    ```text
    {question_text}
    關鍵字: {keywords} (若有)
    參考: {reference} (若有)
    ```
*   **Metadata**:
    *   `original_text`: **完整答案內容** (檢索後回傳給使用者看的內容)
    *   `original_full_text`: 原始 "問題+答案" 的完整 Markdown
    *   `title`: 問題標題
    *   `source_file`: 來源 JSONL 檔名
    *   `source_type`: `jsonl`

#### **B. PDF 資料格式**
*   **Collection Name**: 根據資料夾映射 (如 `pneumonia_guidelines` 等)
*   **Page Content**: 切分後的 Markdown/文字區塊 (Chunk)。
*   **Metadata**:
    *   `pdf_file`: 原始 PDF 檔名
    *   `source_type`: `pdf` 或 `ocr_pdf`
    *   `page`: 頁碼
    *   `folder`: 所屬資料夾名稱

---

## 3. `ingest_dialysis_pdf.py` (洗腎深度 OCR 處理)

### 執行順序
1. **OCR 與物件偵測**：使用 DeepSeek OCR 識別文字、表格與圖片 Bounding Box。
2. **過濾機制**：偵測到「參考文獻」區塊後停止該檔案後續處理。
3. **深度提取**：裁切高解析度表格/圖片，生成 HTML 預覽與 OCR 替代文字。
4. **內容合成**：將頁面文字與圖片預留位置 (`{filename}`) 組合。

### 💾 資料儲存格式 (VDB Format)
*   **Collection Name**: `dialysis_education_materials`
*   **Page Content**:
    ```text
    {頁面本文內容}
    
    ## {表格或圖片標題}
    {OCR 提取出的表格文字內容 或 圖片描述}
    (此區塊包含圖片/圖表資料，請參考附件: {jpg_filename})
    ```
*   **Metadata**:
    *   `source_file`: 原始 PDF 檔名
    *   `source_type`: `ocr_pdf`
    *   `page`: 頁碼
    *   `has_table`: Boolean (該 Chunk 是否包含表格或圖片)
    *   `table_images`: **List of filenames** (該區塊關聯的所有圖片檔名，用於前端渲染)
    *   `original_text`: 該頁完整的原始 OCR 文字
    *   `category`: `洗腎衛教`
    *   `reference`: 參考來源
    *   `collection_name`: `dialysis_education_materials`

---

## 總結：VDB 核心差異

| 腳本 | 嵌入內容 (Embedding) | Metadata 特色 |
| :--- | :--- | :--- |
| **Images** | VLM 生成的圖片文字描述 | 包含 `score` 與 `image_path` |
| **General** | PDF 全文 Chunks 或 JSONL 問題 | JSONL 答案存於 `original_text` 避免稀釋權重 |
| **Dialysis** | 包含 OCR 文字與圖片預留位置 | 包含 `table_images` 陣列，支援多圖關聯檢索 |
