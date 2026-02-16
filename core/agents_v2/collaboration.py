"""Agent Collaboration models and services"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional
import uuid


@dataclass
class CollaborationRequest:
    """Agent 協作請求"""
    requester: str              # 請求方 Agent
    target: str                 # 目標 Agent
    reason: str                 # 請求原因
    data_needed: str            # 需要的數據類型
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status: str = "pending"     # pending, accepted, rejected, completed
    created_at: datetime = field(default_factory=datetime.now)

    def accept(self):
        """標記請求為已接受"""
        self.status = "accepted"

    def reject(self):
        """標記請求為已拒絕"""
        self.status = "rejected"

    def complete(self):
        """標記請求為已完成"""
        self.status = "completed"


@dataclass
class CollaborationResponse:
    """Agent 協作回應"""
    request_id: str
    responder: str
    data: Dict[str, Any]
    accepted: bool = True
    message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
