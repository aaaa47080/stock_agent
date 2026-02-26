"""
Agent V4 — Prompt Registry

Centralized prompt management. All prompts are loaded from YAML files.
Supports multi-language prompts.
"""
import yaml
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


class PromptRegistry:
    _prompts: Dict[str, Dict] = {}
    _loaded: bool = False

    @classmethod
    def load(cls, prompts_dir=None):
        if prompts_dir is None:
            prompts_dir = Path(__file__).parent / "prompts"
        for yaml_file in Path(prompts_dir).glob("*.yaml"):
            scope = yaml_file.stem
            with open(yaml_file, "r", encoding="utf-8") as f:
                cls._prompts[scope] = yaml.safe_load(f) or {}
        cls._loaded = True

    @classmethod
    def get(cls, scope: str, key: str, language: Optional[str] = None) -> str:
        """
        Get prompt template by scope and key.
        
        Args:
            scope: Prompt category (e.g., 'crypto_agent', 'chat_agent')
            key: Prompt key (e.g., 'system', 'analysis')
            language: Language code (zh-TW, zh-CN, en). If None, auto-detect from template structure.
        
        Returns:
            Prompt template string
        """
        if not cls._loaded:
            cls.load()
        
        entry = cls._prompts.get(scope, {}).get(key, {})
        
        if isinstance(entry, dict):
            # 多語言版本：優先使用指定語言，否則返回第一個可用語言
            if language:
                return entry.get(language, entry.get("zh-TW", ""))
            # 自動檢測：如果有 template key，返回 template 內容
            if "template" in entry:
                return entry.get("template", "")
            # 否則返回第一個可用語言
            first_lang = next(iter(entry.keys()), None)
            if first_lang:
                return entry.get(first_lang, "")
            return ""
        else:
            # 單一語言版本（向後相容）
            return str(entry)

    @classmethod
    def render(cls, scope: str, key: str, language: Optional[str] = None, include_time: bool = True, **kwargs) -> str:
        """
        Render prompt template with variables.
        
        Args:
            scope: Prompt category
            key: Prompt key
            language: Language code (zh-TW, zh-CN, en)
            include_time: Whether to include current time info
            **kwargs: Variables to format into template
        
        Returns:
            Formatted prompt string
        """
        template = cls.get(scope, key, language)
        
        # 自動注入當前時間（如果模板需要）
        if include_time:
            now = datetime.now()
            time_info = {
                # 繁體中文
                "current_time_tw": now.strftime("%Y 年 %m 月 %d 日 %H:%M"),
                "current_date_tw": now.strftime("%Y-%m-%d"),
                "current_datetime_tw": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone_tw": "台灣時間 (UTC+8)",
                # 簡體中文
                "current_time_cn": now.strftime("%Y 年 %m 月 %d 日 %H:%M"),
                "current_date_cn": now.strftime("%Y-%m-%d"),
                "current_datetime_cn": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone_cn": "台湾时间 (UTC+8)",
                # English
                "current_time_en": now.strftime("%B %d, %Y %H:%M"),
                "current_date_en": now.strftime("%Y-%m-%d"),
                "current_datetime_en": now.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone_en": "Taiwan Time (UTC+8)",
                # ISO format (universal)
                "current_time_iso": now.isoformat(timespec='minutes'),
                "current_timestamp": str(int(now.timestamp())),
            }
            # 合併到 kwargs，允許覆蓋
            kwargs = {**time_info, **kwargs}
        
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing variable {e} in prompt {scope}.{key}")
