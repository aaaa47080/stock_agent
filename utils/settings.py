"""
統一配置管理
集中管理系統的所有配置項
"""

import os
from typing import Any, Dict

from dotenv import load_dotenv

from core.model_config import OPENAI_DEFAULT_MODEL

load_dotenv()


class Settings:
    """系統配置類"""

    # ============================================
    # API 配置
    # ============================================
    # 伺服器端 API Key（從 .env 讀取，不會被用戶覆蓋）
    # 用於平台級功能：Market Pulse、新聞審查等公共報告
    SERVER_OPENAI_API_KEY: str = os.getenv("SERVER_OPENAI_API_KEY", "") or os.getenv(
        "OPENAI_API_KEY", ""
    )

    # 用戶端 API Key（可被用戶在 UI 中覆蓋）
    # 用於用戶個人分析：深度投資分析、聊天等
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    CRYPTOPANIC_API_KEY: str = os.getenv("CRYPTOPANIC_API_KEY", "")

    # ============================================================================
    # LLM 模型配置
    # ============================================================================
    FAST_THINKING_MODEL: str = OPENAI_DEFAULT_MODEL  # 用於快速分析（分析師）
    DEEP_THINKING_MODEL: str = OPENAI_DEFAULT_MODEL  # 用於深度思考（交易員、風險管理）

    # ============================================================================
    # 系統行為配置
    # ============================================================================
    # 重試機制
    MAX_RETRIES: int = 10  # API 調用最大重試次數
    RETRY_DELAY: float = 1.0  # 初始重試延遲（秒）
    RETRY_BACKOFF: float = 2.0  # 延遲倍增因子

    # 並行執行
    ANALYST_MAX_WORKERS: int = 10  # 分析師並行執行的最大線程數

    # 風險管理
    MAX_REPLANS: int = 10  # 風險管理回饋的最大重規劃次數（原本是1）

    # Tool 配置
    TOOL_MAX_RESULT_LENGTH: int = 8000  # 工具結果最大長度（字符）

    # LLM 緩存
    ENABLE_LLM_CACHE: bool = True  # 是否啟用 LLM 緩存
    LLM_CACHE_TTL: int = 3600  # 緩存有效期（秒），1小時
    LLM_CACHE_DIR: str = ".llm_cache"  # 緩存目錄

    # ============================================================================
    # 數據獲取配置
    # ============================================================================
    DEFAULT_EXCHANGE: str = "okx"  # 默認交易所
    DEFAULT_INTERVAL: str = "1d"  # 默認時間間隔
    DEFAULT_LIMIT: int = 100  # 默認數據條數
    NEWS_LIMIT: int = 5  # 新聞獲取數量

    # ============================================================================
    # 分析配置
    # ============================================================================
    TECHNICAL_INDICATOR_PERIOD: int = 30  # 技術指標計算週期
    RECENT_HISTORY_DAYS: int = 5  # 最近歷史數據天數

    # ============================================================================
    # 調試配置
    # ============================================================================
    DEBUG_MODE: bool = os.getenv("DEBUG", "false").lower() == "true"
    VERBOSE_LOGGING: bool = False  # 詳細日誌
    SAVE_REPORTS: bool = True  # 是否保存報告到文件

    # ============================================================================
    # Feature Flags (實驗性功能)
    # ============================================================================
    # 新版 ManagerAgent V2 - 開放式意圖理解 + DAG 執行引擎
    # 設為 True 時，使用新版 manager_v2.py
    # 設為 False 時，使用現有 manager.py（穩定版）
    ENABLE_MANAGER_V2: bool = os.getenv("ENABLE_MANAGER_V2", "true").lower() == "true"

    # Manager V2 子功能開關
    MANAGER_V2_OPEN_INTENT: bool = True  # 開放式意圖理解（無硬編碼）
    MANAGER_V2_DAG_EXECUTION: bool = True  # DAG 執行引擎
    MANAGER_V2_PARALLEL_GROUPS: bool = True  # 水平並行執行
    MANAGER_V2_SHORT_MEMORY: bool = True  # 短期記憶整合
    MANAGER_V2_SUBAGENT_CONTEXT: bool = True  # Sub-Agent 選擇性上下文

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """將配置轉換為字典"""
        return {
            key: value
            for key, value in cls.__dict__.items()
            if not key.startswith("_") and not callable(value)
        }

    @classmethod
    def update(cls, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(cls, key):
                setattr(cls, key, value)

    @classmethod
    def validate(cls) -> bool:
        """驗證配置是否有效"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("❌ 缺少 OPENAI_API_KEY，請在 .env 文件中設置")
        return True


# 創建全局配置實例（兼容性）
settings = Settings()

# 導出常用配置（向後兼容）
FAST_THINKING_MODEL = Settings.FAST_THINKING_MODEL
DEEP_THINKING_MODEL = Settings.DEEP_THINKING_MODEL
MAX_REPLANS = Settings.MAX_REPLANS
