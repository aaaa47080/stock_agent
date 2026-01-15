import os
import sys
import json
import asyncio
from typing import List, Dict, Optional, Set
from langchain_postgres.vectorstores import PGVector
from langchain_core.messages import HumanMessage

# 確保可以導入 config
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from core.config import DB_CONNECTION_STRING, embeddings, llm

COLLECTION_NAME = "educational_images"

# ==================== 資料源圖片映射管理 ====================

class DatasourceImageMapper:
    """管理 PDF 來源與資料源的映射關係"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # 配置檔案在 Agent_System/ 根目錄，不是 retrieval/
            parent_dir = os.path.dirname(current_dir)
            config_path = os.path.join(parent_dir, "datasource_image_config.json")
        self.config_path = config_path
        self.pdf_to_datasource: Dict[str, str] = {}
        self.datasource_pdfs: Dict[str, Set[str]] = {}
        self.text_to_image_mapping: Dict[str, str] = {}  # 文字資料源 → 圖片資料源
        self._load_and_build_mapping()

    def _load_and_build_mapping(self):
        """載入配置並掃描目錄建立映射"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            datasources = config.get("datasources", {})

            for ds_id, ds_config in datasources.items():
                self.datasource_pdfs[ds_id] = set()
                pdf_dirs = ds_config.get("pdf_directories", [])

                for pdf_dir in pdf_dirs:
                    if os.path.exists(pdf_dir):
                        # 遞迴掃描目錄中的所有 PDF
                        for root, dirs, files in os.walk(pdf_dir):
                            for fname in files:
                                if fname.lower().endswith('.pdf'):
                                    self.pdf_to_datasource[fname] = ds_id
                                    self.datasource_pdfs[ds_id].add(fname)

            # 載入文字資料源 → 圖片資料源的映射
            text_mapping = config.get("text_to_image_datasource_mapping", {})
            for key, value in text_mapping.items():
                if not key.startswith("_"):  # 跳過 _description 等說明欄位
                    self.text_to_image_mapping[key] = value

            print(f"📂 圖片資料源映射已建立:")
            for ds_id, pdfs in self.datasource_pdfs.items():
                print(f"   - {ds_id}: {len(pdfs)} 個 PDF")

        except FileNotFoundError:
            print(f"⚠️ 找不到配置檔案: {self.config_path}，將不進行資料源過濾")
        except Exception as e:
            print(f"⚠️ 載入圖片資料源配置失敗: {e}")

    def get_datasource(self, source_pdf: str) -> Optional[str]:
        """根據 PDF 名稱取得對應的資料源 ID"""
        return self.pdf_to_datasource.get(source_pdf)

    def is_in_datasources(self, source_pdf: str, datasource_ids: List[str]) -> bool:
        """判斷 PDF 是否屬於指定的資料源"""
        if not datasource_ids:
            return True  # 未指定則不過濾
        ds_id = self.get_datasource(source_pdf)
        if ds_id is None:
            return True  # 找不到映射則保留
        return ds_id in datasource_ids

    def convert_text_datasources_to_image_datasources(
        self, text_datasource_ids: Optional[List[str]]
    ) -> Optional[List[str]]:
        """
        將文字資料源 ID 轉換為對應的圖片資料源 ID

        例如：["public_health", "dialysis_education"] → ["public_health"]
              ["medical_kb_jsonl"] → ["infection_control"]
        """
        if not text_datasource_ids:
            return None

        image_ds_ids = set()
        for text_ds in text_datasource_ids:
            if text_ds in self.text_to_image_mapping:
                image_ds_ids.add(self.text_to_image_mapping[text_ds])

        return list(image_ds_ids) if image_ds_ids else None

# 全域映射器實例
_mapper: Optional[DatasourceImageMapper] = None

def get_image_mapper() -> DatasourceImageMapper:
    """取得全域圖片映射器"""
    global _mapper
    if _mapper is None:
        _mapper = DatasourceImageMapper()
    return _mapper

# ==================== 圖片資料源 ID 定義 ====================
# 這些 ID 對應 datasource_image_config.json 中的 datasources
IMAGE_DATASOURCE_PUBLIC_HEALTH = "public_health"      # 衛教園地
IMAGE_DATASOURCE_INFECTION_CONTROL = "infection_control"  # 感染控制

# 初始化 Vector Store
vector_store = PGVector(
    embeddings=embeddings,
    collection_name=COLLECTION_NAME,
    connection=DB_CONNECTION_STRING,
    use_jsonb=True,
)

IMAGE_RELEVANCE_CHECK_PROMPT = """
您是一個專業的醫療圖片審核員。
請判斷以下圖片是否與使用者的問題高度相關，且適合展示給使用者。

使用者問題：{question}
圖片主題：{topic}
圖片檔名：{filename}

判斷標準：
1. 圖片主題必須與問題直接相關（例如：問 B型肝炎，圖片是 B型肝炎衛教）。
2. 如果圖片是通用的（如「正確洗手」），只有在問題涉及預防或衛生時才算相關。
3. 如果圖片主題與問題完全無關（例如：問 腸病毒，圖片是 高血壓），請判定為不相關。

請以 JSON 格式回覆：
{{
    "is_relevant": true/false,
    "reason": "簡短理由"
}}
"""

async def verify_image_relevance(query: str, image_info: Dict) -> Dict:
    """
    使用 LLM 驗證圖片相關性
    """
    try:
        prompt = IMAGE_RELEVANCE_CHECK_PROMPT.format(
            question=query,
            topic=image_info.get('health_topic', '未知'),
            filename=image_info.get('filename', '未知')
        )
        
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        # 處理可能的 Markdown 標記
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
        
        result = json.loads(content)
        return {
            "is_relevant": result.get("is_relevant", False),
            "reason": result.get("reason", "")
        }
    except Exception as e:
        print(f"⚠️ 圖片驗證失敗: {e}")
        # 失敗時預設保留，避免因 LLM 錯誤遺漏
        return {"is_relevant": True, "reason": "Verification failed"}

async def retrieve_relevant_images(
    query: str,
    k: int = None,
    score_threshold: float = None,
    image_datasource_ids: Optional[List[str]] = None
) -> List[Dict]:
    """
    根據查詢檢索相關的衛教圖片（包含 LLM 驗證）

    Args:
        query: 使用者查詢
        k: 檢索數量（如果為 None，則使用配置中的預設值）
        score_threshold: 相似度閾值（如果為 None，則使用配置中的預設值）
        image_datasource_ids: 圖片資料源過濾（如 ["public_health"] 只檢索衛教圖片）
            - "public_health": 衛教園地圖片
            - "infection_control": 感染控制圖片
            - None 或空列表: 不過濾，檢索所有圖片
    """
    # 如果沒有提供參數，則使用配置中的預設值
    if k is None:
        from core.config import IMAGE_RETRIEVAL_CONFIG
        k = IMAGE_RETRIEVAL_CONFIG['educational_images_k']

    # if score_threshold is None:
    #     from core.config import IMAGE_RETRIEVAL_CONFIG
    #     score_threshold = IMAGE_RETRIEVAL_CONFIG['image_score_threshold']
    try:
        # 取得映射器
        mapper = get_image_mapper()

        # 如果有指定資料源過濾，需要多檢索一些以補償過濾損失
        search_k = k * 3 if image_datasource_ids else k

        # 使用 similarity_search_with_score 以進行過濾
        results = vector_store.similarity_search_with_score(query, k=search_k)

        candidates = []
        seen_images = set()  # 用於去重
        filtered_by_datasource = 0

        for doc, score in results:
            # score 在 PGVector 中通常是距離，越小越相關
            if score < 1.5:  # 初步過濾
                source_pdf = doc.metadata.get("source_pdf", "")
                image_path = doc.metadata.get("image_path")
                filename = doc.metadata.get("filename")
                
                # 確保 filename 沒有前後空白
                if filename:
                    filename = filename.strip()

                # 去重檢查：優先使用 filename，如果沒有則使用 image_path
                unique_key = filename if filename else image_path
                
                if not unique_key: # 如果兩者都沒有，跳過
                    continue

                if unique_key in seen_images:
                    continue
                
                # 根據資料源過濾
                if image_datasource_ids:
                    if not mapper.is_in_datasources(source_pdf, image_datasource_ids):
                        filtered_by_datasource += 1
                        continue

                seen_images.add(unique_key)
                candidates.append({
                    "filename": filename,
                    "image_path": image_path,
                    "health_topic": doc.metadata.get("health_topic"),
                    "main_category": doc.metadata.get("main_category"),
                    "source_pdf": source_pdf,
                    "datasource_id": mapper.get_datasource(source_pdf),
                    "core_message": doc.metadata.get("core_message", ""),
                    "detailed_description": doc.page_content,
                    "score": float(score)
                })

                # 達到所需數量就停止
                if len(candidates) >= k:
                    break

        if filtered_by_datasource > 0:
            print(f"   [資料源過濾] 過濾了 {filtered_by_datasource} 張不符合資料源的圖片")

        if not candidates:
            return []

        # 並行執行 LLM 驗證
        verification_tasks = [verify_image_relevance(query, img) for img in candidates]
        verification_results = await asyncio.gather(*verification_tasks)

        final_images = []
        for img, result in zip(candidates, verification_results):
            if result['is_relevant']:
                img['verification_reason'] = result['reason']
                final_images.append(img)
            else:
                print(f"   [過濾圖片] {img['filename']} - 原因: {result['reason']}")

        return final_images

    except Exception as e:
        print(f"Error retrieving images: {e}")
        return []

if __name__ == "__main__":
    # 測試
    async def test():
        test_query = "COVID-19 消毒"

        print("=" * 60)
        print(f"測試查詢: {test_query}")
        print("=" * 60)

        # 測試 1: 不過濾
        print("\n【測試 1】不過濾資料源:")
        images = await retrieve_relevant_images(test_query)
        for img in images:
            print(f"  - {img['filename']} | {img.get('datasource_id', 'N/A')} | {img['health_topic']}")

        # 測試 2: 只檢索衛教圖片
        print("\n【測試 2】只檢索衛教圖片 (public_health):")
        images = await retrieve_relevant_images(test_query, image_datasource_ids=["public_health"])
        for img in images:
            print(f"  - {img['filename']} | {img.get('datasource_id', 'N/A')} | {img['health_topic']}")

        # 測試 3: 只檢索感控圖片
        print("\n【測試 3】只檢索感控圖片 (infection_control):")
        images = await retrieve_relevant_images(test_query, image_datasource_ids=["infection_control"])
        for img in images:
            print(f"  - {img['filename']} | {img.get('datasource_id', 'N/A')} | {img['health_topic']}")

    asyncio.run(test())
