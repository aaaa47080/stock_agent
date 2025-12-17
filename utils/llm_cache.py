"""
LLM 響應緩存機制
通過緩存相似的請求來降低 API 調用成本和延遲
"""
import hashlib
import json
import time
from typing import Dict, Optional, Any
from pathlib import Path
import pickle


class LLMCache:
    """
    簡單的 LLM 響應緩存
    基於請求內容的 hash 值進行緩存
    """

    def __init__(self, cache_dir: str = ".llm_cache", ttl: int = 3600):
        """
        Args:
            cache_dir: 緩存目錄
            ttl: 緩存有效期（秒），默認 1 小時
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.ttl = ttl
        self.memory_cache = {}  # 內存緩存，用於當前會話

    def _generate_key(self, prompt: str, model: str, **kwargs) -> str:
        """
        生成緩存鍵

        Args:
            prompt: 提示詞
            model: 模型名稱
            **kwargs: 其他參數（如 temperature）

        Returns:
            緩存鍵（hash 值）
        """
        # 將所有參數序列化為字符串
        cache_input = {
            "prompt": prompt,
            "model": model,
            **kwargs
        }

        # 生成 hash
        cache_str = json.dumps(cache_input, sort_keys=True)
        return hashlib.sha256(cache_str.encode()).hexdigest()

    def get(self, prompt: str, model: str, **kwargs) -> Optional[Any]:
        """
        從緩存中獲取響應

        Args:
            prompt: 提示詞
            model: 模型名稱
            **kwargs: 其他參數

        Returns:
            緩存的響應，如果不存在則返回 None
        """
        key = self._generate_key(prompt, model, **kwargs)

        # 先檢查內存緩存
        if key in self.memory_cache:
            cached_data = self.memory_cache[key]
            if time.time() - cached_data['timestamp'] < self.ttl:
                print(f"  ⚡ [LLM 緩存命中 - 內存] 跳過 API 調用")
                return cached_data['response']
            else:
                # 緩存過期，刪除
                del self.memory_cache[key]

        # 檢查磁盤緩存
        cache_file = self.cache_dir / f"{key}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)

                # 檢查是否過期
                if time.time() - cached_data['timestamp'] < self.ttl:
                    print(f"  ⚡ [LLM 緩存命中 - 磁盤] 跳過 API 調用")
                    # 加載到內存緩存
                    self.memory_cache[key] = cached_data
                    return cached_data['response']
                else:
                    # 過期，刪除文件
                    cache_file.unlink()
            except Exception as e:
                print(f"  ⚠️  讀取緩存失敗: {e}")

        return None

    def set(self, prompt: str, model: str, response: Any, **kwargs):
        """
        將響應保存到緩存

        Args:
            prompt: 提示詞
            model: 模型名稱
            response: LLM 響應
            **kwargs: 其他參數
        """
        key = self._generate_key(prompt, model, **kwargs)

        cached_data = {
            'response': response,
            'timestamp': time.time()
        }

        # 保存到內存緩存
        self.memory_cache[key] = cached_data

        # 保存到磁盤緩存
        try:
            cache_file = self.cache_dir / f"{key}.pkl"
            with open(cache_file, 'wb') as f:
                pickle.dump(cached_data, f)
        except Exception as e:
            print(f"  ⚠️  保存緩存失敗: {e}")

    def clear(self):
        """清空所有緩存"""
        # 清空內存緩存
        self.memory_cache.clear()

        # 清空磁盤緩存
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                cache_file.unlink()
            except Exception as e:
                print(f"  ⚠️  刪除緩存文件失敗: {e}")

    def clear_expired(self):
        """清理過期的緩存"""
        current_time = time.time()

        # 清理內存緩存
        expired_keys = [
            key for key, data in self.memory_cache.items()
            if current_time - data['timestamp'] >= self.ttl
        ]
        for key in expired_keys:
            del self.memory_cache[key]

        # 清理磁盤緩存
        for cache_file in self.cache_dir.glob("*.pkl"):
            try:
                with open(cache_file, 'rb') as f:
                    cached_data = pickle.load(f)

                if current_time - cached_data['timestamp'] >= self.ttl:
                    cache_file.unlink()
            except Exception:
                # 如果文件損壞或無法讀取，也刪除它
                cache_file.unlink()


# 全局緩存實例
_global_cache = LLMCache(ttl=3600)  # 默認 1 小時過期


def get_global_cache() -> LLMCache:
    """獲取全局緩存實例"""
    return _global_cache


def cached_llm_call(client, model: str, messages: list, use_cache: bool = True, **kwargs):
    """
    帶緩存的 LLM 調用包裝函數

    Args:
        client: OpenAI 客戶端
        model: 模型名稱
        messages: 消息列表
        use_cache: 是否使用緩存
        **kwargs: 其他參數

    Returns:
        LLM 響應

    使用範例:
        response = cached_llm_call(
            client=client,
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7
        )
    """
    cache = get_global_cache()

    # 生成緩存鍵（基於消息內容）
    prompt = json.dumps(messages, sort_keys=True)

    # 嘗試從緩存獲取
    if use_cache:
        cached_response = cache.get(prompt, model, **kwargs)
        if cached_response is not None:
            return cached_response

    # 緩存未命中，調用 API
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        **kwargs
    )

    # 保存到緩存
    if use_cache:
        cache.set(prompt, model, response, **kwargs)

    return response
