"""
用戶 LLM Client 工廠
根據用戶提供的 API key 創建 LLM 客戶端
⭐ 重要：完全使用用戶提供的 key，不從 .env 讀取
"""

from typing import Any, Optional
import socket
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from core.model_config import OPENAI_DEFAULT_MODEL, GEMINI_DEFAULT_MODEL

def create_user_llm_client(provider: str, api_key: str, model: Optional[str] = None) -> Any:
    """
    根據用戶提供的 key 創建 LLM 客戶端 (LangChain BaseChatModel)

    Args:
        provider: "openai", "google_gemini", "openrouter"
        api_key: 用戶的 API key
        model: 用戶選擇的模型名稱（可選，未提供則使用 provider 預設值）

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
    default_model = OPENAI_DEFAULT_MODEL

    if provider == "openai":
        lc_provider = "openai"
        default_model = OPENAI_DEFAULT_MODEL
    elif provider == "google_gemini":
        lc_provider = "google_genai"
        default_model = GEMINI_DEFAULT_MODEL
    elif provider == "openrouter":
        lc_provider = "openai"
        base_url = "https://openrouter.ai/api/v1"
        default_model = OPENAI_DEFAULT_MODEL
    else:
        raise ValueError(f"不支援的 provider: {provider}")

    return init_chat_model(
        model=model or default_model,
        model_provider=lc_provider,
        temperature=0.5,
        api_key=api_key,
        base_url=base_url
    )


def explain_llm_exception(exc: Exception) -> str:
    """將底層 LLM 例外轉為可診斷的訊息。"""
    chain = []
    current = exc
    seen = set()

    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)

    messages = " | ".join(str(item) for item in chain if str(item))

    if any(isinstance(item, socket.gaierror) for item in chain) or (
        "nodename nor servname provided" in messages
        or "Name or service not known" in messages
        or "Temporary failure in name resolution" in messages
    ):
        return "LLM 連線失敗：DNS 解析失敗，請檢查目前環境是否可連外網，以及 OpenAI/OpenRouter 網域是否可解析。"

    if "401" in messages or "Unauthorized" in messages:
        return "API Key 無效或已過期"

    if "429" in messages:
        return "API 配額不足"

    if "Connection error" in messages or "ConnectError" in messages or "APIConnectionError" in messages:
        return "LLM 連線失敗：無法連到模型提供商，請檢查外網連線、防火牆或代理設定。"

    return f"驗證失敗: {exc}"


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
        return False, explain_llm_exception(e)
