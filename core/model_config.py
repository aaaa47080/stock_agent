"""
模型配置文件 - 統一管理所有 LLM 模型配置
"""

# 模型配置
MODEL_CONFIG = {
    "openai": {
        "default_model": "gpt-4o-mini",
        "available_models": [
            {"value": "gpt-4o", "display": "gpt-4o"},
            {"value": "gpt-4o-mini", "display": "gpt-4o-mini"},
            {"value": "gpt-4-turbo", "display": "gpt-4-turbo"}
        ]
    },
    "google_gemini": {
        "default_model": "gemini-3-flash-preview",
        "available_models": [
            {"value": "gemini-3-flash-preview", "display": "Gemini 3 Flash Preview"}
        ]
    },
    "openrouter": {
        "default_model": "gpt-4o-mini",  # 作為參考，實際使用時由用戶自行輸入
        "available_models": []  # OpenRouter 有太多模型，讓用戶自行輸入
    }
}

def get_available_models(provider):
    """
    獲取指定提供商的可用模型列表
    
    Args:
        provider (str): 提供商名稱 ('openai', 'google_gemini', 'openrouter')
    
    Returns:
        list: 模型配置列表，每個項目包含 'value' 和 'display' 鍨性
    """
    return MODEL_CONFIG.get(provider, {}).get("available_models", [])

def get_default_model(provider):
    """
    獲取指定提供商的默認模型
    
    Args:
        provider (str): 提供商名稱 ('openai', 'google_gemini', 'openrouter')
    
    Returns:
        str: 默認模型名稱
    """
    return MODEL_CONFIG.get(provider, {}).get("default_model", "gpt-4o-mini")

def get_all_providers():
    """
    獲取所有支持的提供商列表
    
    Returns:
        list: 支持的提供商名稱列表
    """
    return list(MODEL_CONFIG.keys())

def is_valid_model(provider, model_name):
    """
    檢查指定提供商是否支持特定模型

    Args:
        provider (str): 提供商名稱
        model_name (str): 模型名稱

    Returns:
        bool: 模型是否有效
    """
    available_models = get_available_models(provider)
    return any(model['value'] == model_name for model in available_models)

def get_model_display_name(provider, model_value):
    """
    獲取模型的顯示名稱

    Args:
        provider (str): 提供商名稱
        model_value (str): 模型值

    Returns:
        str: 模型的顯示名稱，如果找不到則返回模型值本身
    """
    available_models = get_available_models(provider)
    for model in available_models:
        if model['value'] == model_value:
            return model['display']
    return model_value  # 如果找不到顯示名稱，返回模型值本身