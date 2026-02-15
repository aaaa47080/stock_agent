"""Conversation Memory for tracking context across sessions"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class ConversationContext:
    """對話上下文"""
    session_id: str
    main_topic: Optional[str] = None
    symbols_mentioned: List[str] = field(default_factory=list)
    analysis_history: List[Dict] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)

    def touch(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.now()

    def add_symbol(self, symbol: str):
        """Add a symbol if not already present"""
        if symbol not in self.symbols_mentioned:
            self.symbols_mentioned.append(symbol)
            self.touch()

    def add_analysis(self, analysis: Dict):
        """Add analysis to history"""
        self.analysis_history.append(analysis)
        self.touch()
