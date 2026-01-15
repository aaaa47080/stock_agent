from langchain_core.embeddings import Embeddings
from typing import List
import httpx
import asyncio
import numpy as np

class AsyncVLLMServerEmbeddings(Embeddings):
    """異步版本的 VLLM Embeddings，支持 LangChain 的同步接口"""
    
    def __init__(
        self,
        model: str,
        api_base: str = "http://localhost:8081/v1",
        normalize: bool = True,
        timeout: float = 30.0
    ):
        self.model = model
        self.api_url = f"{api_base.rstrip('/')}/embeddings"
        self.normalize = normalize
        self.timeout = timeout
        self._async_client = None
        self._sync_client = None

    def __del__(self):
        """清理資源"""
        if hasattr(self, '_sync_client') and self._sync_client:
            self._sync_client.close()

    async def _ensure_async_client(self):
        """確保異步客戶端已初始化"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self._async_client

    def _ensure_sync_client(self):
        """確保同步客戶端已初始化（用於同步接口）"""
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=self.timeout)
        return self._sync_client

    async def _get_embeddings_async(self, texts: List[str]) -> List[List[float]]:
        """異步獲取 embeddings"""
        if not texts:
            return []
        
        client = await self._ensure_async_client()
        
        response = await client.post(
            self.api_url,
            json={"model": self.model, "input": texts}
        )
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise RuntimeError(f"Embedding API error: {data['error']}")
        
        embeddings = [item['embedding'] for item in data['data']]
        
        if self.normalize:
            emb_array = np.array(embeddings)
            norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            embeddings = (emb_array / norms).tolist()
        
        return embeddings

    def _get_embeddings_sync(self, texts: List[str]) -> List[List[float]]:
        """同步獲取 embeddings（在異步環境中會使用線程池）"""
        if not texts:
            return []
        
        # 檢查是否在事件循環中
        try:
            loop = asyncio.get_running_loop()
            # 在事件循環中：使用 run_in_executor 避免阻塞
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(self._blocking_get_embeddings, texts)
                return future.result()
        except RuntimeError:
            # 不在事件循環中：直接執行同步請求
            return self._blocking_get_embeddings(texts)

    def _blocking_get_embeddings(self, texts: List[str]) -> List[List[float]]:
        """真正的阻塞式請求（僅在線程池中執行）"""
        client = self._ensure_sync_client()
        
        response = client.post(
            self.api_url,
            json={"model": self.model, "input": texts}
        )
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            raise RuntimeError(f"Embedding API error: {data['error']}")
        
        embeddings = [item['embedding'] for item in data['data']]
        
        if self.normalize:
            emb_array = np.array(embeddings)
            norms = np.linalg.norm(emb_array, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)
            embeddings = (emb_array / norms).tolist()
        
        return embeddings

    # ===== LangChain 接口 =====
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入多個文檔（LangChain 同步接口）"""
        return self._get_embeddings_sync(texts)

    def embed_query(self, text: str) -> List[float]:
        """嵌入單個查詢（LangChain 同步接口）"""
        return self._get_embeddings_sync([text])[0]

    # ===== 異步接口（供高級用戶使用）=====
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """異步嵌入多個文檔"""
        return await self._get_embeddings_async(texts)

    async def aembed_query(self, text: str) -> List[float]:
        """異步嵌入單個查詢"""
        embeddings = await self._get_embeddings_async([text])
        return embeddings[0]


# ===== 使用示例 =====
async def example_usage():
    # 初始化
    embeddings = AsyncVLLMServerEmbeddings(
        model="intfloat/multilingual-e5-large-instruct",
        api_base="http://localhost:8081/v1"
    )
    
    # 異步使用（推薦）
    query_embedding = await embeddings.aembed_query("什麼是敗血症？")
    print(f"Query embedding shape: {len(query_embedding)}")
    
    docs_embeddings = await embeddings.aembed_documents([
        "敗血症是一種嚴重的感染反應",
        "需要及時使用抗生素治療"
    ])
    print(f"Docs embeddings count: {len(docs_embeddings)}")
    
    # 同步使用（在異步環境中會自動使用線程池）
    query_embedding_sync = embeddings.embed_query("什麼是敗血症？")
    print(f"Sync query embedding shape: {len(query_embedding_sync)}")


if __name__ == "__main__":
    asyncio.run(example_usage())