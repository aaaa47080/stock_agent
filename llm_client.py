"""
LLM 客戶端工廠 - 支持 OpenAI 和 OpenRouter
"""

import os
from dotenv import load_dotenv
import openai
from typing import Dict, Any

load_dotenv()


class LLMClientFactory:
    """LLM 客戶端工廠，支持多種 LLM 提供商"""

    @staticmethod
    def create_client(provider: str, model: str = None) -> Any:
        """
        創建 LLM 客戶端

        Args:
            provider: 提供商 ("openai" 或 "openrouter")
            model: 模型名稱（用於記錄）

        Returns:
            配置好的 OpenAI 客戶端
        """
        if provider.lower() == "openai":
            return LLMClientFactory._create_openai_client()
        elif provider.lower() == "openrouter":
            return LLMClientFactory._create_openrouter_client()
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    @staticmethod
    def _create_openai_client():
        """創建 OpenAI 客戶端"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未找到 OPENAI_API_KEY 環境變量")

        return openai.OpenAI(api_key=api_key)

    @staticmethod
    def _create_openrouter_client():
        """創建 OpenRouter 客戶端"""
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("未找到 OPENROUTER_API_KEY 環境變量")

        # OpenRouter 使用 OpenAI 兼容的 API
        return openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )

    @staticmethod
    def get_model_info(config: Dict[str, str]) -> str:
        """
        獲取模型信息字符串

        Args:
            config: 模型配置字典 {"provider": "...", "model": "..."}

        Returns:
            模型信息字符串
        """
        provider = config.get("provider", "openai")
        model = config.get("model", "unknown")

        if provider == "openrouter":
            return f"{model} (via OpenRouter)"
        else:
            return f"{model} (OpenAI)"


def supports_json_mode(model: str) -> bool:
    """
    檢查模型是否支持 JSON 模式

    Args:
        model: 模型名稱

    Returns:
        是否支持 JSON 模式
    """
    # 已知不支持 JSON 模式的模型
    unsupported_models = [
        "gemma",  # Google Gemma 系列
        "llama",  # Meta Llama 部分版本
    ]

    # 檢查模型名稱是否包含不支持的模型關鍵字
    model_lower = model.lower()
    for unsupported in unsupported_models:
        if unsupported in model_lower:
            return False

    # 默認假設支持（GPT、Claude、Gemini Pro 等）
    return True


def extract_json_from_response(response_text: str) -> dict:
    """
    從模型響應中提取 JSON 內容

    處理以下情況：
    1. 純 JSON 響應
    2. JSON 包裹在代碼塊中（```json ... ```）
    3. JSON 前後有其他文字
    4. 空響應或無效響應

    Args:
        response_text: 模型的原始響應文本

    Returns:
        解析後的 JSON 字典

    Raises:
        ValueError: 如果無法提取有效的 JSON
    """
    import re
    import json

    if not response_text or not response_text.strip():
        raise ValueError("響應為空")

    # 嘗試 1: 直接解析整個響應
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # 嘗試 2: 提取代碼塊中的 JSON（```json ... ``` 或 ``` ... ```）
    code_block_patterns = [
        r'```json\s*\n(.*?)\n```',  # ```json ... ```
        r'```\s*\n(.*?)\n```',       # ``` ... ```
    ]

    for pattern in code_block_patterns:
        matches = re.findall(pattern, response_text, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                continue

    # 嘗試 3: 查找第一個 { 到最後一個 } 之間的內容
    first_brace = response_text.find('{')
    last_brace = response_text.rfind('}')

    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        try:
            json_str = response_text[first_brace:last_brace + 1]
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 如果所有嘗試都失敗，拋出錯誤
    raise ValueError(f"無法從響應中提取有效的 JSON。響應前100個字符: {response_text[:100]}")


def create_llm_client_from_config(config: Dict[str, str]) -> tuple:
    """
    從配置創建 LLM 客戶端

    Args:
        config: 模型配置 {"provider": "...", "model": "..."}

    Returns:
        (client, model_name) 元組
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o")

    client = LLMClientFactory.create_client(provider, model)
    return client, model


# 便捷函數
def get_bull_researcher_client():
    """獲取多頭研究員的 LLM 客戶端"""
    from config import BULL_RESEARCHER_MODEL
    return create_llm_client_from_config(BULL_RESEARCHER_MODEL)


def get_bear_researcher_client():
    """獲取空頭研究員的 LLM 客戶端"""
    from config import BEAR_RESEARCHER_MODEL
    return create_llm_client_from_config(BEAR_RESEARCHER_MODEL)


def get_trader_client():
    """獲取交易員的 LLM 客戶端"""
    from config import TRADER_MODEL
    return create_llm_client_from_config(TRADER_MODEL)


if __name__ == "__main__":
    # 測試
    print("測試 LLM 客戶端工廠\n")

    # 測試 OpenAI
    try:
        client = LLMClientFactory.create_client("openai")
        print("✅ OpenAI 客戶端創建成功")
    except Exception as e:
        print(f"❌ OpenAI 客戶端創建失敗: {e}")

    # 測試 OpenRouter
    try:
        client = LLMClientFactory.create_client("openrouter")
        print("✅ OpenRouter 客戶端創建成功")
    except Exception as e:
        print(f"⚠️  OpenRouter 客戶端創建失敗: {e}")
        print("   提示: 需要設置 OPENROUTER_API_KEY 環境變量")

    # 測試配置
    from config import BULL_RESEARCHER_MODEL, BEAR_RESEARCHER_MODEL

    print(f"\n多頭研究員: {LLMClientFactory.get_model_info(BULL_RESEARCHER_MODEL)}")
    print(f"空頭研究員: {LLMClientFactory.get_model_info(BEAR_RESEARCHER_MODEL)}")
