"""Tests for Conversation Memory"""
import pytest
from datetime import datetime
from core.agents_v2.memory import ConversationContext


class TestConversationContext:
    """Test ConversationContext dataclass"""

    def test_context_creation(self):
        """Context should be created with session_id"""
        context = ConversationContext(session_id="test-123")
        assert context.session_id == "test-123"
        assert context.main_topic is None
        assert context.symbols_mentioned == []

    def test_context_default_values(self):
        """Context should have sensible defaults"""
        context = ConversationContext(session_id="test")
        assert context.analysis_history == []
        assert context.user_preferences == {}
        assert isinstance(context.created_at, datetime)

    def test_context_touch(self):
        """touch() should update last_activity"""
        context = ConversationContext(session_id="test")
        old_time = context.last_activity
        context.touch()
        assert context.last_activity >= old_time

    def test_context_add_symbol(self):
        """add_symbol() should add unique symbols"""
        context = ConversationContext(session_id="test")
        context.add_symbol("BTC")
        context.add_symbol("ETH")
        context.add_symbol("BTC")  # duplicate

        assert "BTC" in context.symbols_mentioned
        assert "ETH" in context.symbols_mentioned
        assert len(context.symbols_mentioned) == 2  # no duplicates

    def test_context_add_analysis(self):
        """add_analysis() should add to history"""
        context = ConversationContext(session_id="test")
        context.add_analysis({"symbol": "BTC", "type": "technical"})

        assert len(context.analysis_history) == 1
        assert context.analysis_history[0]["symbol"] == "BTC"
