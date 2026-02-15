"""Data models for Professional Agent system"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class Viewpoint:
    """Agent 的分析觀點"""
    content: str                    # 觀點內容
    confidence: float               # 信心度 0-1
    evidence: List[str]             # 支撐證據
    tools_used: List[str]           # 使用的工具
    user_agreed: Optional[bool] = None  # 用戶是否認同
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "content": self.content,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "tools_used": self.tools_used,
            "user_agreed": self.user_agreed,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class DiscussionRound:
    """討論回合"""
    speaker: str          # "agent" or "user"
    content: str          # 內容
    type: str             # "proposal", "concern", "revision", "agreement"
    timestamp: datetime = field(default_factory=datetime.now)
