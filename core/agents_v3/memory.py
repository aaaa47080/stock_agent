"""
Agent V3 對話記憶

管理會話上下文和使用者偏好
"""
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


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

    def touch(self) -> None:
        """更新最後活動時間"""
        self.last_activity = datetime.now()

    def add_symbol(self, symbol: str) -> None:
        """添加符號（去重）"""
        symbol = symbol.upper()
        if symbol not in self.symbols_mentioned:
            self.symbols_mentioned.append(symbol)
            self.touch()

    def add_analysis(self, analysis: Dict) -> None:
        """添加分析記錄"""
        self.analysis_history.append(analysis)
        self.touch()

    def set_preference(self, key: str, value: Any) -> None:
        """設置使用者偏好"""
        self.user_preferences[key] = value
        self.touch()

    def get_preference(self, key: str, default: Any = None) -> Any:
        """獲取使用者偏好"""
        return self.user_preferences.get(key, default)


class ConversationMemory:
    """
    對話記憶管理服務

    職責：
    - 管理會話上下文
    - 提取和追蹤提及的符號
    - 記錄分析歷史
    - 儲存使用者偏好
    """

    # 常見加密貨幣符號
    CRYPTO_SYMBOLS = {
        'BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'AVAX',
        'MATIC', 'LINK', 'UNI', 'ATOM', 'LTC', 'BCH', 'ETC', 'FIL', 'NEAR',
        'APT', 'ARB', 'OP', 'PI'
    }

    def __init__(self):
        self._contexts: Dict[str, ConversationContext] = {}

    def get_or_create(self, session_id: str) -> ConversationContext:
        """
        獲取或創建會話上下文

        Args:
            session_id: 會話 ID

        Returns:
            會話上下文
        """
        if session_id not in self._contexts:
            self._contexts[session_id] = ConversationContext(session_id=session_id)
        return self._contexts[session_id]

    def update_with_query(self, context: ConversationContext, query: str) -> None:
        """
        根據查詢更新上下文

        Args:
            context: 會話上下文
            query: 使用者查詢
        """
        # 提取符號
        symbols = self._extract_symbols(query)
        for symbol in symbols:
            context.add_symbol(symbol)

        # 更新主題
        if not context.main_topic and query:
            context.main_topic = query[:50]
            context.touch()

    def get_relevant_context(
        self,
        session_id: str,
        current_query: str = None
    ) -> Dict[str, Any]:
        """
        獲取相關的上下文資訊

        Args:
            session_id: 會話 ID
            current_query: 當前查詢（可選）

        Returns:
            相關上下文字典
        """
        context = self.get_or_create(session_id)

        result = {
            "session_id": session_id,
            "main_topic": context.main_topic,
            "symbols_mentioned": context.symbols_mentioned,
            "preferences": context.user_preferences,
            "recent_analyses": context.analysis_history[-5:]  # 最近 5 條
        }

        # 如果有當前查詢，提取符號
        if current_query:
            result["current_symbols"] = self._extract_symbols(current_query)

        return result

    def clear_session(self, session_id: str) -> bool:
        """
        清除會話

        Args:
            session_id: 會話 ID

        Returns:
            是否成功清除
        """
        if session_id in self._contexts:
            del self._contexts[session_id]
            return True
        return False

    def get_all_sessions(self) -> List[str]:
        """獲取所有會話 ID"""
        return list(self._contexts.keys())

    def cleanup_inactive(self, max_age_hours: int = 24) -> int:
        """
        清理不活躍的會話

        Args:
            max_age_hours: 最大不活躍時間（小時）

        Returns:
            清理的會話數量
        """
        now = datetime.now()
        to_remove = []

        for session_id, context in self._contexts.items():
            age = (now - context.last_activity).total_seconds() / 3600
            if age > max_age_hours:
                to_remove.append(session_id)

        for session_id in to_remove:
            del self._contexts[session_id]

        return len(to_remove)

    def _extract_symbols(self, query: str) -> List[str]:
        """
        從查詢中提取加密貨幣符號

        Args:
            query: 使用者查詢

        Returns:
            提取的符號列表
        """
        query_upper = query.upper()
        found = []

        for symbol in self.CRYPTO_SYMBOLS:
            # 檢查是否在查詢中
            if symbol in query_upper:
                # 避免部分匹配（如 ATOMS 匹配 ATOM）
                import re
                pattern = r'\b' + symbol + r'\b'
                if re.search(pattern, query_upper):
                    found.append(symbol)

        return found

    def _is_new_topic(self, query: str, context: ConversationContext) -> bool:
        """
        判斷是否是新話題

        Args:
            query: 當前查詢
            context: 會話上下文

        Returns:
            是否是新話題
        """
        new_topic_indicators = ["那", "換", "另一個", "呢", "還有", "另外"]

        # 檢查是否有新話題指示詞
        for indicator in new_topic_indicators:
            if indicator in query:
                return True

        # 檢查是否有新的符號
        new_symbols = self._extract_symbols(query)
        if new_symbols and context.symbols_mentioned:
            if not any(s in context.symbols_mentioned for s in new_symbols):
                return True

        return False
