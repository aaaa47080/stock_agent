"""Model routing strategy — select model by task complexity."""

from typing import Optional


class ModelRouter:
    """根據任務複雜度選擇合適的模型。"""

    TASK_MODEL_MAP = {
        "simple_qa": "gemini-3.1-flash-preview",
        "market_data": "gpt-5-mini",
        "deep_analysis": "gpt-5.2-pro",
        "research": "gpt-5.2-pro",
    }

    DEFAULT_MODEL = "gpt-5-mini"

    @classmethod
    def get_model(cls, task_type: str, user_preference: Optional[str] = None) -> str:
        if user_preference:
            return user_preference
        return cls.TASK_MODEL_MAP.get(task_type, cls.DEFAULT_MODEL)
