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


class ConversationMemory:
    """對話記憶管理服務"""

    CRYPTO_SYMBOLS = {
        'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX',
        'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'ETC', 'FIL', 'NEAR',
        'APT', 'ARB', 'OP', 'PI'
    }

    def __init__(self):
        self.sessions: Dict[str, ConversationContext] = {}

    def get_or_create(self, session_id: str) -> ConversationContext:
        """獲取或創建對話上下文"""
        if session_id not in self.sessions:
            self.sessions[session_id] = ConversationContext(session_id)
        return self.sessions[session_id]

    def update_with_query(self, context: ConversationContext, query: str) -> None:
        """根據新查詢更新上下文"""
        symbols = self._extract_symbols(query)
        for symbol in symbols:
            context.add_symbol(symbol)

        if self._is_new_topic(query, context):
            context.main_topic = self._extract_topic(query)

        context.touch()

    def get_relevant_context(self, session_id: str, current_query: str = None) -> Dict[str, Any]:
        """獲取與當前查詢相關的歷史上下文"""
        context = self.sessions.get(session_id)
        if not context:
            return {}

        return {
            "main_topic": context.main_topic,
            "symbols": context.symbols_mentioned,
            "recent_analysis": context.analysis_history[-3:],
            "user_preferences": context.user_preferences
        }

    def _extract_symbols(self, query: str) -> List[str]:
        """從查詢中提取加密貨幣符號"""
        query_upper = query.upper()
        return [s for s in self.CRYPTO_SYMBOLS if s in query_upper]

    def _is_new_topic(self, query: str, context: ConversationContext) -> bool:
        """判斷是否為新主題"""
        if not context.main_topic:
            return True
        new_topic_indicators = ["那", "換", "另一個", "呢"]
        return any(indicator in query for indicator in new_topic_indicators)

    def _extract_topic(self, query: str) -> str:
        """從查詢中提取主題"""
        return query[:50] if len(query) > 50 else query
