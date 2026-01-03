"""
用戶 LLM Client 工廠
根據用戶提供的 API key 創建 LLM 客戶端
⭐ 重要：完全使用用戶提供的 key，不從 .env 讀取
"""

import openai
from typing import Any


def create_user_llm_client(provider: str, api_key: str) -> Any:
    """
    根據用戶提供的 key 創建 LLM 客戶端

    Args:
        provider: "openai", "google_gemini", "openrouter"
        api_key: 用戶的 API key

    Returns:
        配置好的 LLM 客戶端

    Raises:
        ValueError: 如果 provider 不支援或 api_key 為空
    """
    if not api_key or not api_key.strip():
        raise ValueError("API key 不能為空")

    api_key = api_key.strip()

    if provider == "openai":
        return _create_openai_client(api_key)
    elif provider == "google_gemini":
        return _create_google_gemini_client(api_key)
    elif provider == "openrouter":
        return _create_openrouter_client(api_key)
    else:
        raise ValueError(f"不支援的 provider: {provider}")


def _create_openai_client(api_key: str) -> Any:
    """創建 OpenAI 客戶端"""
    return openai.OpenAI(api_key=api_key)


def _create_google_gemini_client(api_key: str) -> Any:
    """創建 Google Gemini 客戶端（使用 wrapper）"""
    try:
        import google.generativeai as genai
        from utils.llm_client import GeminiWrapper

        # 配置 API key
        genai.configure(api_key=api_key)

        # 返回 wrapper（提供 OpenAI 兼容接口）
        return GeminiWrapper(genai)
    except ImportError:
        raise ValueError("Google Gemini SDK 未安裝。請運行: pip install google-generativeai")


def _create_openrouter_client(api_key: str) -> Any:
    """創建 OpenRouter 客戶端"""
    return openai.OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key
    )


def validate_user_key(provider: str, api_key: str) -> tuple[bool, str]:
    """
    驗證用戶提供的 API key 是否有效

    Args:
        provider: LLM 提供商
        api_key: API key

    Returns:
        (是否有效, 錯誤訊息)
    """
    try:
        client = create_user_llm_client(provider, api_key)

        # 嘗試進行一個輕量的測試調用
        if provider == "openai":
            # 列出模型（最輕量的驗證方式）
            client.models.list()
        elif provider == "google_gemini":
            # Gemini wrapper 已經在創建時驗證了
            pass
        elif provider == "openrouter":
            client.models.list()

        return True, "驗證成功"
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            return False, "API Key 無效或已過期"
        elif "429" in error_msg:
            return False, "API 配額不足"
        else:
            return False, f"驗證失敗: {error_msg}"
