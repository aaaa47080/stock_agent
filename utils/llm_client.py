"""
LLM 客戶端工廠 - 支持 OpenAI 和 OpenRouter
"""

import os
import logging
from dotenv import load_dotenv
import openai
from typing import Dict, Any

# Import logger from api.utils if available, otherwise create a fallback logger
try:
    from api.utils import logger
except ImportError:
    # Create a fallback logger if api.utils is not available
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Create formatter similar to the main API logger
    log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_formatter)
    logger.addHandler(console_handler)

    # Add file handler for debugging
    try:
        file_handler = logging.FileHandler("llm_client.log", encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(log_formatter)
        logger.addHandler(file_handler)
    except:
        pass  # If file creation fails, continue with console only

# 嘗試導入 LangChain 的 init_chat_model，如果未安裝則跳過或報錯
try:
    from langchain.chat_models import init_chat_model
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("Warning: langchain not installed. Local LLM support will be limited.")

# 嘗試導入 Google Gemini，如果未安裝則跳過
try:
    import google.generativeai as genai
    GOOGLE_GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GOOGLE_GEMINI_AVAILABLE = False

load_dotenv()


class GeminiWrapper:
    """Google Gemini API 包裝器，提供 OpenAI 兼容接口"""
    # ... (GeminiWrapper implementation remains the same)
    def __init__(self, genai_module):
        self.genai = genai_module
        self.chat = self  # 模擬 OpenAI 的 client.chat 結構
        self.completions = self  # 模擬 OpenAI 的 client.chat.completions 結構

    def create(self, model: str, messages: list, response_format: dict = None, temperature: float = 0.5, max_tokens: int = None, **kwargs):
        """
        模擬 OpenAI 的 chat.completions.create() 方法

        Args:
            model: Gemini 模型名稱 (參考配置文件中的可用模型)
            messages: OpenAI 格式的消息列表
            response_format: 響應格式配置 ({"type": "json_object"})
            temperature: 生成溫度
            **kwargs: 其他參數

        Returns:
            模擬 OpenAI 響應格式的對象
        """
        # 將 OpenAI 格式的消息轉換為 Gemini 格式
        # Gemini 只需要最後一條用戶消息的內容
        prompt = ""
        for msg in messages:
            if msg["role"] == "user":
                prompt = msg["content"]

        # 配置生成參數
        generation_config = {
            "temperature": temperature,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": max_tokens or 8192,  # 使用傳入的 max_tokens 或默認值
        }

        # 如果需要 JSON 輸出，設置 response_mime_type 和強化提示
        if response_format and response_format.get("type") == "json_object":
            generation_config["response_mime_type"] = "application/json"
            # 在提示詞最後強調只輸出 JSON
            if "請以 JSON 格式回覆" in prompt or "JSON 格式" in prompt:
                # 已經有 JSON 指示，加強說明
                prompt = f"{prompt}\n\n重要提醒：只輸出純 JSON 對象，不要包含任何解釋、思考過程或其他文字。"
            else:
                # 沒有 JSON 指示，添加完整說明
                prompt = f"{prompt}\n\n請以純 JSON 格式回覆，不要包含任何其他文字、解釋或標記。"

        # 創建 Gemini 模型實例（帶系統指令）
        system_instruction = None
        if response_format and response_format.get("type") == "json_object":
            system_instruction = "You are a JSON response generator. Always output valid JSON only, without any additional text, explanation, or markdown formatting."

        gemini_model = self.genai.GenerativeModel(
            model_name=model,
            generation_config=generation_config,
            system_instruction=system_instruction
        )

        # 調用 Gemini API
        response = gemini_model.generate_content(prompt)

        # 獲取響應文本，處理可能的內容審核問題
        try:
            response_text = response.text
        except Exception as e:
            # 如果 response.text 失敗，檢查候選結果
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'finish_reason') and candidate.finish_reason == 2:
                    # Finish reason 2 通常表示內容被審核系統阻止
                    raise Exception(f"The response was blocked due to content policy. Finish reason: {candidate.finish_reason}")
                elif hasattr(candidate, 'content') and candidate.content.parts:
                    # 嘗試從 content.parts 獲取文本
                    response_text = "".join([part.text for part in candidate.content.parts if hasattr(part, 'text')])
                else:
                    raise Exception(f"Could not retrieve response text. Finish reason: {candidate.finish_reason if hasattr(candidate, 'finish_reason') else 'unknown'}")
            else:
                raise Exception("No candidates returned from Gemini API")

        # 如果需要 JSON 輸出，清理和驗證響應
        if response_format and response_format.get("type") == "json_object":
            import json
            import re
            import dirtyjson

            # 嘗試清理響應（移除可能的 markdown 代碼塊標記）
            cleaned_text = response_text.strip()

            # 移除可能的 markdown JSON 代碼塊
            if cleaned_text.startswith("```json"):
                cleaned_text = re.sub(r'^```json\s*\n', '', cleaned_text)
                cleaned_text = re.sub(r'\n```\s*$', '', cleaned_text)
            elif cleaned_text.startswith("```"):
                cleaned_text = re.sub(r'^```\s*\n', '', cleaned_text)
                cleaned_text = re.sub(r'\n```\s*$', '', cleaned_text)

            try:
                # 嘗試解析 JSON 以驗證格式
                parsed = dirtyjson.loads(cleaned_text)

                # 檢查是否有 'task' 或其他包裝鍵（某些 Gemini 版本會這樣做）
                if isinstance(parsed, dict) and len(parsed) == 1:
                    # 如果只有一個鍵且不是預期的業務鍵，可能是包裝
                    single_key = list(parsed.keys())[0]
                    if single_key in ['task', 'response', 'output', 'result', 'data']:
                        logger.warning(f"⚠️  檢測到 Gemini 包裝鍵 '{single_key}'，嘗試解包...")
                        # 嘗試解包
                        inner_value = parsed[single_key]
                        if isinstance(inner_value, dict):
                            parsed = inner_value
                            logger.info(f"✅ 解包成功，新的鍵: {list(parsed.keys())}")

                # 記錄調試信息
                logger.debug(f"🔍 Gemini JSON 響應鍵: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed)}")

                # 重新序列化以確保格式正確
                response_text = json.dumps(parsed, ensure_ascii=False)

            except json.JSONDecodeError as e:
                # 記錄原始響應以便調試
                logger.warning(f"⚠️  Gemini JSON 解析失敗: {e}")
                logger.debug(f"原始響應前500字符: {response_text[:500]}")
                # 嘗試提取 JSON（查找第一個 { 到最後一個 }）
                first_brace = response_text.find('{')
                last_brace = response_text.rfind('}')
                if first_brace != -1 and last_brace != -1:
                    try:
                        extracted = response_text[first_brace:last_brace + 1]
                        parsed = dirtyjson.loads(extracted)
                        logger.info(f"✅ JSON 提取成功")
                        response_text = json.dumps(parsed, ensure_ascii=False)
                    except:
                        pass  # 保持原始響應文本

        # 將 Gemini 響應轉換為 OpenAI 格式
        class Choice:
            def __init__(self, content):
                self.message = type('obj', (object,), {'content': content})()

        class Response:
            def __init__(self, content):
                self.choices = [Choice(content)]

        return Response(response_text)


class LangChainOpenAIAdapter:
    """
    適配器：將 LangChain ChatModel 封裝成類似 OpenAI Client 的接口
    主要用於讓現有代碼 (client.chat.completions.create) 能無縫使用 LangChain 物件
    """
    def __init__(self, langchain_model):
        self.model = langchain_model
        self.chat = self
        self.completions = self

    def create(self, model: str = None, messages: list = None, response_format: dict = None, temperature: float = None, **kwargs):
        """
        模擬 OpenAI 的 create 方法
        """
        # 1. 轉換 messages (OpenAI dict -> LangChain Message objects)
        # Using langchain_core.messages as langchain.schema is deprecated/moved
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        lc_messages = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content)) # Fallback

        # 2. 執行 Invoke
        # 注意：temperature 等參數在 init_chat_model 時已經設定，這裡如果要覆蓋需要 bind
        # 但為了簡單起見，這裡直接 invoke，忽略運行時的超參數覆蓋 (除非使用 bind)
        try:
            response = self.model.invoke(lc_messages)
            content = response.content
        except Exception as e:
            logger.error(f"LangChain invoke error: {e}")
            raise e

        # 3. 封裝回 OpenAI 格式的回傳
        class Choice:
            def __init__(self, content):
                self.message = type('obj', (object,), {'content': content})()

        class Response:
            def __init__(self, content):
                self.choices = [Choice(content)]
        
        return Response(content)


class LLMClientFactory:
    """LLM 客戶端工廠，支持多種 LLM 提供商"""

    @staticmethod
    def _get_api_key(provider: str) -> str:
        """
        獲取 API Key 的核心方法。
        優先級：動態 Settings > os.environ > .env
        """
        from utils.settings import Settings

        if provider == "openai":
            # Debug prints - can be removed later
            # print("===================================test================================")
            # print(Settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""))
            # print("===================================test================================")
            return Settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", "")
        elif provider == "openai_server":
            # Debug prints - can be removed later
            # print("===================================test================================")
            # print(Settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY", ""))
            # print("===================================test================================")
            return Settings.SERVER_OPENAI_API_KEY or os.getenv("SERVER_OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        elif provider == "google_gemini":
            # 兼容 Google 官方 SDK 的變數名稱
            return os.getenv("GOOGLE_API_KEY") or getattr(Settings, "GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        elif provider == "openrouter":
            return os.getenv("OPENROUTER_API_KEY") or getattr(Settings, "OPENROUTER_API_KEY", "")
        return ""

    @staticmethod
    def create_client(provider: str, model: str = None) -> Any:
        """
        創建 LLM 客戶端

        Args:
            provider: 提供商 ("openai", "openrouter", "google_gemini", "local")
            model: 模型名稱（用於記錄）

        Returns:
            配置好的 OpenAI 客戶端 (或 LangChain 適配器)
        """
        if provider.lower() == "openai":
            return LLMClientFactory._create_openai_client()
        elif provider.lower() == "openrouter":
            return LLMClientFactory._create_openrouter_client()
        elif provider.lower() == "google_gemini":
            return LLMClientFactory._create_google_gemini_client()
        elif provider.lower() == "local":
            return LLMClientFactory._create_local_langchain_client(model)
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    @staticmethod
    def _create_openai_client():
        """創建 OpenAI 客戶端"""
        api_key = LLMClientFactory._get_api_key("openai")
        if not api_key:
            raise ValueError("未找到有效 OpenAI API Key。請先在設置中輸入並驗證。")

        return openai.OpenAI(api_key=api_key)

    @staticmethod
    def _create_openrouter_client():
        """創建 OpenRouter 客戶端"""
        api_key = LLMClientFactory._get_api_key("openrouter")
        if not api_key:
            raise ValueError("未找到有效 OpenRouter API Key。請先在設置中輸入並驗證。")

        # OpenRouter 使用 OpenAI 兼容的 API
        return openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )

    @staticmethod
    def _create_google_gemini_client():
        """創建 Google Gemini 客戶端"""
        if not GOOGLE_GEMINI_AVAILABLE:
            raise ValueError("Google Gemini SDK 未安裝，請運行: pip install google-generativeai")

        api_key = LLMClientFactory._get_api_key("google_gemini")
        if not api_key:
            raise ValueError("未找到有效 Google API Key。請先在設置中輸入並驗證。")

        genai.configure(api_key=api_key)
        return GeminiWrapper(genai)

    @staticmethod
    def _create_local_langchain_client(model_name: str):
        """創建本地 LangChain 客戶端，並封裝為 OpenAI 兼容接口"""
        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain is required for local model support. Please install it.")

        try:
            from core.config import LOCAL_LLM_CONFIG
        except ImportError:
            # Fallback default if config not found
            LOCAL_LLM_CONFIG = {
                "base_url": "http://localhost:8000/v1",
                "api_key": "not-needed",
                "temperature": 0.1,
                "seed": 42
            }

        base_url = LOCAL_LLM_CONFIG.get("base_url", "http://localhost:8000/v1")
        api_key = LOCAL_LLM_CONFIG.get("api_key", "not-needed")
        temperature = LOCAL_LLM_CONFIG.get("temperature", 0.1)
        seed = LOCAL_LLM_CONFIG.get("seed", 42)

        # 這裡 model_provider 設為 "openai" 是因為 vLLM/Ollama 通常提供 OpenAI 兼容的 API
        llm = init_chat_model(
            model=model_name or "local-model",
            model_provider="openai",
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            max_retries=2,
            model_kwargs={"seed": seed}
        )
        
        # 返回適配器，讓現有代碼 (client.chat.completions.create) 可以繼續工作
        return LangChainOpenAIAdapter(llm)

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
        elif provider == "google_gemini":
            return f"{model} (Google Gemini Official)"
        elif provider == "local":
            return f"{model} (Local LangChain)"
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


def create_llm_client_from_config(config: Dict[str, str], user_client: Any = None, user_provider: str = None, user_model: str = None) -> tuple:
    """
    從配置創建 LLM 客戶端。
    ⭐ 優先使用用戶提供的客戶端，以確保使用用戶的 Key。

    Args:
        config: 模型配置 {"provider": "...", "model": "..."}
        user_client: 可選的用戶提供的 LLM 客戶端。
        user_provider: 用戶的 provider 名稱。
        user_model: 用戶選擇的模型名稱。

    Returns:
        (client, model_name) 元組
    """
    model_from_config = config.get("model", "gpt-4o")

    # 1. 絕對優先使用傳入的 user_client
    if user_client:
        # 如果用戶指定了模型，優先使用用戶的模型
        effective_model = user_model if user_model else model_from_config
        return user_client, effective_model

    # 2. 如果沒有傳入 user_client，則根據 config 創建新 client
    provider_from_config = config.get("provider", "openai")

    # 如果用戶指定了模型，優先使用用戶的模型
    effective_model = user_model if user_model else model_from_config

    # 警告：如果 user_client 未傳入，將回退到使用後端環境變量中的 API Key
    logger.warning(
        f"create_llm_client_from_config: user_client is None. "
        f"Attempting to create a new client for provider '{provider_from_config}' "
        f"using system environment variables. This might fail if keys are not set."
    )

    client = LLMClientFactory.create_client(provider_from_config, effective_model)
    return client, effective_model


# 便捷函數
def get_bull_researcher_client():
    """獲取多頭研究員的 LLM 客戶端"""
    from core.config import BULL_RESEARCHER_MODEL
    return create_llm_client_from_config(BULL_RESEARCHER_MODEL)


def get_bear_researcher_client():
    """獲取空頭研究員的 LLM 客戶端"""
    from core.config import BEAR_RESEARCHER_MODEL
    return create_llm_client_from_config(BEAR_RESEARCHER_MODEL)


def get_trader_client():
    """獲取交易員的 LLM 客戶端"""
    from core.config import TRADER_MODEL
    return create_llm_client_from_config(TRADER_MODEL)


if __name__ == "__main__":
    # 測試
    logger.info("測試 LLM 客戶端工廠\n")

    # 測試 OpenAI
    try:
        client = LLMClientFactory.create_client("openai")
        logger.info("✅ OpenAI 客戶端創建成功")
    except Exception as e:
        logger.error(f"❌ OpenAI 客戶端創建失敗: {e}")

    # 測試 OpenRouter
    try:
        client = LLMClientFactory.create_client("openrouter")
        logger.info("✅ OpenRouter 客戶端創建成功")
    except Exception as e:
        logger.warning(f"⚠️  OpenRouter 客戶端創建失敗: {e}")
        logger.info("   提示: 需要設置 OPENROUTER_API_KEY 環境變數")

    # 測試配置
    from core.config import BULL_RESEARCHER_MODEL, BEAR_RESEARCHER_MODEL

    logger.info(f"\n多頭研究員: {LLMClientFactory.get_model_info(BULL_RESEARCHER_MODEL)}")
    logger.info(f"空頭研究員: {LLMClientFactory.get_model_info(BEAR_RESEARCHER_MODEL)}")

    # 測試 Google Gemini
    try:
        # 這裡不實際調用 generate_content，僅測試客戶端是否能成功初始化
        # 實際的模型調用應在 Agent 或其他業務邏輯中處理
        client = LLMClientFactory.create_client("google_gemini")
        logger.info("✅ Google Gemini 客戶端創建成功")
    except Exception as e:
        logger.error(f"❌ Google Gemini 客戶端創建失敗: {e}")
        logger.info("   提示: 需要設置 GOOGLE_API_KEY 環境變數")
