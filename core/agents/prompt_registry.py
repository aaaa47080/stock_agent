"""
Agent V4 — Prompt Registry

Centralized prompt management. All prompts are loaded from YAML files.
"""
import yaml
from pathlib import Path
from typing import Dict


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
    def get(cls, scope: str, key: str) -> str:
        if not cls._loaded:
            cls.load()
        entry = cls._prompts.get(scope, {}).get(key, {})
        return entry.get("template", "") if isinstance(entry, dict) else str(entry)

    @classmethod
    def render(cls, scope: str, key: str, **kwargs) -> str:
        template = cls.get(scope, key)
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing variable {e} in prompt {scope}.{key}")
