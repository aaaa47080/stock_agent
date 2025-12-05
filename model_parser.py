"""
模型配置解析器
將 "provider:model" 格式轉換為完整配置
"""

from typing import Dict, List, Tuple


def parse_model_string(model_string: str) -> Dict[str, str]:
    """
    解析模型字符串

    Args:
        model_string: 格式為 "provider:model"
                     例如: "openai:gpt-4o" 或 "openrouter:anthropic/claude-3.5-sonnet"

    Returns:
        配置字典 {"provider": "...", "model": "...", "name": "..."}

    Examples:
        >>> parse_model_string("openai:gpt-4o")
        {"provider": "openai", "model": "gpt-4o", "name": "GPT-4o"}

        >>> parse_model_string("openrouter:anthropic/claude-3.5-sonnet")
        {"provider": "openrouter", "model": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet"}
    """
    if ":" not in model_string:
        raise ValueError(
            f"無效的模型格式: '{model_string}'\n"
            f"正確格式: 'provider:model'\n"
            f"例如: 'openai:gpt-4o' 或 'openrouter:anthropic/claude-3.5-sonnet'"
        )

    provider, model = model_string.split(":", 1)
    provider = provider.strip().lower()
    model = model.strip()

    # 驗證提供商
    if provider not in ["openai", "openrouter"]:
        raise ValueError(
            f"不支持的提供商: '{provider}'\n"
            f"支持的提供商: openai, openrouter"
        )

    # 生成友好的名稱
    name = _generate_model_name(provider, model)

    return {
        "provider": provider,
        "model": model,
        "name": name
    }


def parse_committee_models(model_strings: List[str]) -> List[Dict[str, str]]:
    """
    解析委員會模型列表

    Args:
        model_strings: 模型字符串列表

    Returns:
        配置字典列表
    """
    return [parse_model_string(s) for s in model_strings]


def _generate_model_name(provider: str, model: str) -> str:
    """
    生成友好的模型名稱

    Args:
        provider: 提供商
        model: 模型名稱

    Returns:
        友好的名稱
    """
    # OpenAI 模型名稱映射
    openai_names = {
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o Mini",
        "o4-mini": "o4-mini",
        "gpt-4-turbo": "GPT-4 Turbo",
        "gpt-4": "GPT-4",
    }

    # OpenRouter 模型名稱映射
    openrouter_names = {
        "anthropic/claude-3.5-sonnet": "Claude 3.5 Sonnet",
        "anthropic/claude-3-opus": "Claude 3 Opus",
        "anthropic/claude-3-haiku": "Claude 3 Haiku",
        "google/gemini-pro-1.5": "Gemini Pro 1.5",
        "google/gemini-flash-1.5": "Gemini Flash 1.5",
        "meta-llama/llama-3.1-405b-instruct": "Llama 3.1 405B",
        "meta-llama/llama-3.1-70b-instruct": "Llama 3.1 70B",
        "qwen/qwen-2.5-72b-instruct": "Qwen 2.5 72B",
        "deepseek/deepseek-chat": "DeepSeek Chat",
        "openai/gpt-4o": "GPT-4o (via OpenRouter)",
        "openai/gpt-4o-mini": "GPT-4o Mini (via OpenRouter)",
    }

    if provider == "openai":
        return openai_names.get(model, model)
    elif provider == "openrouter":
        return openrouter_names.get(model, model.split("/")[-1])

    return model


# ============================================================================
# 便捷函數
# ============================================================================

def load_simple_config():
    """
    從 config_simple.py 加載配置

    Returns:
        配置字典
    """
    try:
        from config_simple import (
            ENABLE_MULTI_MODEL_DEBATE,
            ENABLE_COMMITTEE_MODE,
            BULL_MODEL,
            BEAR_MODEL,
            TRADER_MODEL,
            BULL_COMMITTEE_MODELS,
            BEAR_COMMITTEE_MODELS,
            SYNTHESIS_MODEL,
        )

        config = {
            "enable_multi_model": ENABLE_MULTI_MODEL_DEBATE,
            "enable_committee": ENABLE_COMMITTEE_MODE,
        }

        if ENABLE_COMMITTEE_MODE:
            # 委員會模式
            config["bull_committee"] = parse_committee_models(BULL_COMMITTEE_MODELS)
            config["bear_committee"] = parse_committee_models(BEAR_COMMITTEE_MODELS)
            config["synthesis"] = parse_model_string(SYNTHESIS_MODEL)
        else:
            # 單一模型模式
            config["bull"] = parse_model_string(BULL_MODEL)
            config["bear"] = parse_model_string(BEAR_MODEL)
            config["trader"] = parse_model_string(TRADER_MODEL)

        return config

    except ImportError:
        print("⚠️  找不到 config_simple.py，使用默認配置")
        return {
            "enable_multi_model": False,
            "enable_committee": False,
        }


def print_config_summary():
    """打印配置摘要"""
    config = load_simple_config()

    print("\n" + "=" * 70)
    print("📋 當前模型配置")
    print("=" * 70)

    if config["enable_committee"]:
        print("\n🏛️ 委員會模式: 啟用")
        print(f"\n多頭委員會 ({len(config['bull_committee'])} 位專家):")
        for i, model in enumerate(config["bull_committee"], 1):
            print(f"  {i}. {model['name']}")

        print(f"\n空頭委員會 ({len(config['bear_committee'])} 位專家):")
        for i, model in enumerate(config["bear_committee"], 1):
            print(f"  {i}. {model['name']}")

        print(f"\n綜合模型: {config['synthesis']['name']}")
    else:
        print("\n🎭 單一模型辯論")
        if config["enable_multi_model"]:
            print(f"  🐂 多頭研究員: {config['bull']['name']}")
            print(f"  🐻 空頭研究員: {config['bear']['name']}")
            print(f"  💼 交易員: {config['trader']['name']}")
        else:
            print("  ⚠️  多模型辯論未啟用")

    print("\n" + "=" * 70)


# ============================================================================
# 測試
# ============================================================================

if __name__ == "__main__":
    # 測試解析
    test_cases = [
        "openai:gpt-4o",
        "openai:o4-mini",
        "openrouter:anthropic/claude-3.5-sonnet",
        "openrouter:google/gemini-pro-1.5",
        "openrouter:meta-llama/llama-3.1-70b-instruct",
        "openrouter:qwen/qwen-2.5-72b-instruct",
    ]

    print("\n🧪 測試模型解析\n")
    for case in test_cases:
        try:
            config = parse_model_string(case)
            print(f"✅ {case}")
            print(f"   → Provider: {config['provider']}")
            print(f"   → Model: {config['model']}")
            print(f"   → Name: {config['name']}\n")
        except Exception as e:
            print(f"❌ {case}")
            print(f"   → Error: {e}\n")

    # 打印當前配置
    print_config_summary()
