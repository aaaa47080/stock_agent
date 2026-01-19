"""
用戶 LLM Client 工廠
根據用戶提供的 API key 創建 LLM 客戶端
⭐ 重要：完全使用用戶提供的 key，不從 .env 讀取
"""

from typing import Any
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage

def create_user_llm_client(provider: str, api_key: str) -> Any:
    """
    根據用戶提供的 key 創建 LLM 客戶端 (LangChain BaseChatModel)

    Args:
        provider: "openai", "google_gemini", "openrouter"
        api_key: 用戶的 API key

    Returns:
        配置好的 LLM 客戶端 (BaseChatModel)

    Raises:
        ValueError: 如果 provider 不支援或 api_key 為空
    """
    if not api_key or not api_key.strip():
        raise ValueError("API key 不能為空")

    api_key = api_key.strip()
    
    lc_provider = "openai"
    base_url = None
    default_model = "gpt-4o-mini"

    if provider == "openai":
        lc_provider = "openai"
        default_model = "gpt-4o-mini"
    elif provider == "google_gemini":
        lc_provider = "google_genai"
        default_model = "gemini-2.0-flash-exp"
    elif provider == "openrouter":
        lc_provider = "openai"
        base_url = "https://openrouter.ai/api/v1"
        default_model = "gpt-4o-mini"
    else:
        raise ValueError(f"不支援的 provider: {provider}")

    return init_chat_model(
        model=default_model, # 這只是一個默認值，實際調用時通常會指定模型，或由 invoke 時 bind 指定
        model_provider=lc_provider,
        temperature=0.5,
        api_key=api_key,
        base_url=base_url
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
        # 使用一個非常簡單的 Prompt
        client.invoke([HumanMessage(content="Hi")])

        return True, "驗證成功"
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "Unauthorized" in error_msg:
            return False, "API Key 無效或已過期"
        elif "429" in error_msg:
            return False, "API 配額不足"
        else:
            return False, f"驗證失敗: {error_msg}"