"""
LLM Client Factory - Unified LangChain Implementation
"""

import os
import logging
import json
import re
from typing import Dict, Any, List, Union, Optional
from dotenv import load_dotenv
from core.model_config import OPENAI_DEFAULT_MODEL, OPENAI_LEGACY_MODEL, GEMINI_DEFAULT_MODEL

# LangChain Imports
try:
    from langchain.chat_models import init_chat_model
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    BaseChatModel = None  # Define dummy if not available
    print("Warning: langchain not installed. Please install langchain langchain-openai langchain-google-genai")

# Import settings
from utils.settings import Settings

# Configure Logger
try:
    from api.utils import logger
except ImportError:
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

load_dotenv()

class LLMClientFactory:
    """
    Factory for creating unified LangChain LLM clients.
    Supports OpenAI, Google Gemini, OpenRouter, and Local models via LangChain.
    """

    @staticmethod
    def _get_api_key(provider: str) -> str:
        """Get API Key based on provider."""
        if provider == "openai":
            return Settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        elif provider == "openai_server":
            return Settings.SERVER_OPENAI_API_KEY or os.getenv("SERVER_OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        elif provider == "google_gemini":
            return os.getenv("GOOGLE_API_KEY") or getattr(Settings, "GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        elif provider == "openrouter":
            return os.getenv("OPENROUTER_API_KEY") or getattr(Settings, "OPENROUTER_API_KEY", "")
        return ""

    @staticmethod
    def create_client(provider: str, model: str = None) -> BaseChatModel:
        """
        Create a LangChain ChatModel instance.

        Args:
            provider: Provider name ("openai", "openrouter", "google_gemini", "local")
            model: Model name (e.g., "gpt-4", "gemini-pro")

        Returns:
            BaseChatModel: A configured LangChain chat model.
        """
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is required. Please install it.")

        api_key = LLMClientFactory._get_api_key(provider)
        
        # Map internal provider names to LangChain init_chat_model providers
        lc_provider = "openai" # Default to openai (works for openrouter/local too)
        kwargs = {}

        if provider == "openai" or provider == "openai_server":
            lc_provider = "openai"
            if not api_key:
                raise ValueError("Missing OpenAI API Key.")
            kwargs["api_key"] = api_key

        elif provider == "google_gemini":
            lc_provider = "google_genai" # uses langchain-google-genai
            if not api_key:
                raise ValueError("Missing Google API Key.")
            kwargs["api_key"] = api_key
            # Gemini specific settings for safety or others can be added here
            
        elif provider == "openrouter":
            lc_provider = "openai" # OpenRouter is OpenAI compatible
            if not api_key:
                raise ValueError("Missing OpenRouter API Key.")
            kwargs["api_key"] = api_key
            kwargs["base_url"] = "https://openrouter.ai/api/v1"
            
        elif provider == "local":
            lc_provider = "openai" # Local models usually provide OpenAI compatible API
            from core.config import LOCAL_LLM_CONFIG
            kwargs["base_url"] = LOCAL_LLM_CONFIG.get("base_url", "http://localhost:8000/v1")
            kwargs["api_key"] = LOCAL_LLM_CONFIG.get("api_key", "not-needed")
            kwargs["temperature"] = LOCAL_LLM_CONFIG.get("temperature", 0.1)

        # Initialize the model
        try:
            # Default model names if not provided
            if not model:
                if provider == "google_gemini":
                    model = GEMINI_DEFAULT_MODEL
                else:
                    model = OPENAI_LEGACY_MODEL

            logger.info(f"Initializing LLM: Provider={lc_provider}, Model={model}")
            
            llm = init_chat_model(
                model=model,
                model_provider=lc_provider,
                temperature=0.5, # Default temperature, can be overridden in invoke/bind
                **kwargs
            )
            return llm

        except Exception as e:
            logger.error(f"Failed to initialize LLM client for {provider}/{model}: {e}")
            raise e

    @staticmethod
    def get_model_info(config: Dict[str, str]) -> str:
        provider = config.get("provider", "openai")
        model = config.get("model", "unknown")
        return f"{model} ({provider})"


def supports_json_mode(model: str) -> bool:
    """Check if model supports native JSON mode."""
    # This is less critical with LangChain as we can use parsers,
    # but still useful for deciding whether to set response_format={"type": "json_object"}
    # if we were using bind.
    unsupported_models = ["gemma", "llama"]
    model_lower = model.lower()
    for unsupported in unsupported_models:
        if unsupported in model_lower:
            return False
    return True


def extract_json_from_response(response_text: str) -> dict:
    """
    Extract JSON from response text.
    Handles ```json blocks, raw JSON, and text with extra context.
    """
    if not response_text or not response_text.strip():
        raise ValueError("Empty response")

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Try code blocks
    code_block_patterns = [
        r'```json\s*\n(.*?)\n```',
        r'```\s*\n(.*?)\n```',
    ]
    for pattern in code_block_patterns:
        matches = re.findall(pattern, response_text, re.DOTALL)
        if matches:
            try:
                return json.loads(matches[0])
            except json.JSONDecodeError:
                continue

    # Try finding { }
    first_brace = response_text.find('{')
    last_brace = response_text.rfind('}')
    if first_brace != -1 and last_brace != -1:
        try:
            return json.loads(response_text[first_brace:last_brace + 1])
        except:
            pass
            
    # Try dirtyjson if available
    try:
        import dirtyjson
        return dirtyjson.loads(response_text)
    except ImportError:
        pass
    except Exception:
        pass

    raise ValueError(f"Could not extract JSON from response: {response_text[:100]}...")


def create_llm_client_from_config(config: Dict[str, str], user_client: Any = None, user_provider: str = None, user_model: str = None) -> tuple:
    """
    Create LLM client from config or use provided user_client.
    
    Args:
        config: {"provider": "...", "model": "..."}
        user_client: Existing LangChain model instance (optional)
        
    Returns:
        (client, model_name)
    """
    model_from_config = config.get("model", OPENAI_DEFAULT_MODEL)
    
    # 1. Use user_client if provided
    if user_client:
        effective_model = user_model if user_model else model_from_config
        return user_client, effective_model

    # 2. Create new client
    provider_from_config = config.get("provider", "openai")
    effective_model = user_model if user_model else model_from_config

    logger.warning(
        f"create_llm_client_from_config: Creating new client for {provider_from_config}/{effective_model} (System Keys)"
    )

    client = LLMClientFactory.create_client(provider_from_config, effective_model)
    return client, effective_model

if __name__ == "__main__":
    # Simple Test
    try:
        print("Testing OpenAI Client...")
        llm = LLMClientFactory.create_client("openai", "gpt-5-mini")
        res = llm.invoke([HumanMessage(content="Hello, say 'test'!")])
        print(f"Response: {res.content}")
    except Exception as e:
        print(f"OpenAI Test Failed: {e}")