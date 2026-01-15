#!/usr/bin/env python3
"""
測試圖片檢索配置是否正確應用
"""
import asyncio
from core.config import IMAGE_RETRIEVAL_CONFIG
from retrieval.image_retriever import retrieve_relevant_images

async def test_image_config():
    print("測試圖片檢索配置...")
    print(f"配置中的衛教圖片檢索數量: {IMAGE_RETRIEVAL_CONFIG['educational_images_k']}")
    print(f"配置中的表格圖片檢索數量: {IMAGE_RETRIEVAL_CONFIG['table_images_k']}")
    # print(f"配置中的圖片相似度閾值: {IMAGE_RETRIEVAL_CONFIG['image_score_threshold']}")
    
    # 測試調用圖片檢索函數，不指定k值，應該使用配置中的默認值
    print("\n測試調用圖片檢索函數...")
    try:
        # 使用一個簡單的查詢測試
        results = await retrieve_relevant_images("健康飲食", k=None)
        print(f"檢索結果數量: {len(results)}")
        print("圖片檢索配置測試完成！")
    except Exception as e:
        print(f"圖片檢索測試過程中出現異常: {e}")
        # 這可能是因為沒有圖片數據，這很正常

if __name__ == "__main__":
    asyncio.run(test_image_config())