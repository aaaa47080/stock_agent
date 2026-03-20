"""
Agent Description Loader

從 .md 檔案載入 agent 描述，供 Manager 在路由時使用。

設計原則：
1. 描述存放在獨立的 .md 檔案中，易於維護
2. 使用 YAML frontmatter 格式，支援分層讀取
3. 啟動時載入記憶體，運行時快速讀取

分層讀取：
- get_metadata(): 只讀取 frontmatter（name, description, routing_keywords, priority）
- get_full_description(): 讀取完整內容（包括 when_to_use, capabilities 等）
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


@dataclass
class AgentDescription:
    """Agent 描述資料結構"""

    # Frontmatter 元數據（輕量級，用於路由）
    name: str
    description: str
    routing_keywords: List[str] = field(default_factory=list)
    priority: int = 10

    # 完整描述（需要時才載入）
    when_to_use: str = ""
    capabilities: List[str] = field(default_factory=list)
    market_indicators: str = ""
    raw_content: str = ""


class AgentDescriptionLoader:
    """
    Agent 描述載入器

    使用方式：
        loader = AgentDescriptionLoader()
        loader.load_all()

        # 只取得元數據（用於路由）
        metadata = loader.get_metadata("crypto")

        # 取得完整描述（用於 prompt）
        full_desc = loader.get_full_description("crypto")

        # 取得路由配置
        config = loader.get_routing_config()
    """

    def __init__(self, descriptions_dir: Optional[str] = None):
        if descriptions_dir is None:
            # 預設路徑：core/agents/descriptions/
            descriptions_dir = Path(__file__).parent / "descriptions"
        self.descriptions_dir = Path(descriptions_dir)
        self._cache: Dict[str, AgentDescription] = {}

    def load_all(self) -> Dict[str, AgentDescription]:
        """載入所有 agent 描述（只載入 frontmatter）"""
        if not self.descriptions_dir.exists():
            return {}

        for md_file in self.descriptions_dir.glob("*_agent.md"):
            try:
                desc = self._parse_frontmatter(md_file)
                if desc:
                    self._cache[desc.name] = desc
            except Exception as e:
                import logging

                logging.warning(
                    f"[AgentDescriptionLoader] Failed to parse {md_file}: {e}"
                )

        return self._cache

    def _parse_frontmatter(self, file_path: Path) -> Optional[AgentDescription]:
        """只解析 YAML frontmatter（輕量級）"""
        content = file_path.read_text(encoding="utf-8")

        # 提取 frontmatter
        frontmatter = self._extract_frontmatter(content)
        if not frontmatter:
            return None

        return AgentDescription(
            name=frontmatter.get("name", ""),
            description=frontmatter.get("description", ""),
            routing_keywords=[
                kw.strip().lower() for kw in frontmatter.get("routing_keywords", [])
            ],
            priority=frontmatter.get("priority", 10),
            raw_content=content,  # 保存原始內容，需要時解析
        )

    def _extract_frontmatter(self, content: str) -> Optional[dict]:
        """提取 YAML frontmatter"""
        pattern = r"^---\s*\n(.*?)\n---\s*\n"
        match = re.match(pattern, content, re.DOTALL)
        if not match:
            return None

        try:
            return yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            return None

    def _parse_full_content(self, desc: AgentDescription) -> AgentDescription:
        """解析完整內容（當需要時才調用）"""
        if not desc.raw_content:
            return desc

        content = desc.raw_content

        # 跳過 frontmatter
        content_after_fm = re.sub(
            r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL
        )

        desc.when_to_use = self._extract_section(content_after_fm, "When to Use")
        desc.capabilities = self._extract_list_section(content_after_fm, "Capabilities")
        desc.market_indicators = self._extract_section(
            content_after_fm, "Market Indicators"
        )

        return desc

    def _extract_section(self, content: str, section_name: str) -> str:
        """提取特定 section 的內容"""
        pattern = rf"## {section_name}\s*\n(.*?)(?=\n## |\Z)"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_list_section(self, content: str, section_name: str) -> list:
        """提取列表形式的 section"""
        section_content = self._extract_section(content, section_name)
        if not section_content:
            return []

        items = []
        for line in section_content.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                items.append(line[2:].strip())
        return items

    def get(self, agent_name: str) -> Optional[AgentDescription]:
        """取得特定 agent 的描述（只含 frontmatter）"""
        return self._cache.get(agent_name)

    def get_full_description(self, agent_name: str) -> Optional[AgentDescription]:
        """取得完整描述（包括 when_to_use, capabilities 等）"""
        desc = self._cache.get(agent_name)
        if desc and not desc.when_to_use:  # 還沒解析過完整內容
            self._parse_full_content(desc)
        return desc

    def get_all_for_prompt(self) -> str:
        """
        取得所有 agent 描述，格式化為 prompt 可用的字串
        """
        lines = []
        for name, desc in self._cache.items():
            # 確保載入完整內容
            if not desc.when_to_use:
                self._parse_full_content(desc)

            lines.append(f"## {name}")
            lines.append(desc.description)
            if desc.when_to_use:
                lines.append(f"\n適用情境：{desc.when_to_use}")
            if desc.market_indicators:
                lines.append(f"\n市場指標：{desc.market_indicators}")
            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def get_routing_guide(self) -> str:
        """
        取得路由指南（完整版）
        """
        lines = []
        for name, desc in self._cache.items():
            # 確保載入完整內容
            if not desc.when_to_use:
                self._parse_full_content(desc)

            lines.append(f"## {name}")
            lines.append(desc.description)
            if desc.when_to_use:
                lines.append(f"適用情境：{desc.when_to_use}")
            if desc.capabilities:
                lines.append(f"能力：{', '.join(desc.capabilities)}")
            if desc.market_indicators:
                lines.append(f"市場指標：{desc.market_indicators}")
            lines.append("")  # 空行分隔

        return "\n".join(lines)

    def get_routing_config(self) -> list:
        """
        取得路由配置，按優先級排序

        Returns:
            List of tuples: [(agent_name, routing_keywords, priority), ...]
            按優先級排序（數字越小越優先）
        """
        config = []
        for name, desc in self._cache.items():
            if desc.routing_keywords:  # 只返回有關鍵詞的 agent
                config.append((name, desc.routing_keywords, desc.priority))

        # 按優先級排序（數字越小越優先）
        config.sort(key=lambda x: x[2])
        return config


# 全域實例
_loader_instance: Optional[AgentDescriptionLoader] = None


def get_agent_descriptions() -> AgentDescriptionLoader:
    """取得全域 Agent Description Loader 實例"""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = AgentDescriptionLoader()
        _loader_instance.load_all()
    return _loader_instance
