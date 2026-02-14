"""
Tests for messages router in api/routers/messages.py
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import WebSocket

from api.routers.messages import (
    router,
    SendMessageRequest,
    MarkReadRequest,
    MessageConnectionManager
)


class TestSendMessageRequest:
    """Tests for SendMessageRequest model"""

    def test_valid_request(self):
        """Test valid request"""
        req = SendMessageRequest(to_user_id="user-123", content="Hello!")
        assert req.to_user_id == "user-123"
        assert req.content == "Hello!"

    def test_content_min_length(self):
        """Test content minimum length"""
        req = SendMessageRequest(to_user_id="user-123", content="A")
        assert req.content == "A"

    def test_missing_to_user_id(self):
        """Test missing to_user_id"""
        with pytest.raises(Exception):
            SendMessageRequest(content="Hello")

    def test_missing_content(self):
        """Test missing content"""
        with pytest.raises(Exception):
            SendMessageRequest(to_user_id="user-123")

    def test_empty_content(self):
        """Test empty content"""
        with pytest.raises(Exception):
            SendMessageRequest(to_user_id="user-123", content="")


class TestMarkReadRequest:
    """Tests for MarkReadRequest model"""

    def test_valid_request(self):
        """Test valid request"""
        req = MarkReadRequest(conversation_id=1)
        assert req.conversation_id == 1

    def test_missing_conversation_id(self):
        """Test missing conversation_id"""
        with pytest.raises(Exception):
            MarkReadRequest()


class TestMessageConnectionManager:
    """Tests for MessageConnectionManager class"""

    def test_init(self):
        """Test initialization"""
        manager = MessageConnectionManager()
        assert manager.active_connections == {}
        assert manager.lock is not None

    @pytest.mark.asyncio
    async def test_connect(self):
        """Test connect method"""
        manager = MessageConnectionManager()
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.accept = AsyncMock()

        await manager.connect(mock_ws, "user-123")

        mock_ws.accept.assert_called_once()
        assert "user-123" in manager.active_connections
        assert mock_ws in manager.active_connections["user-123"]

    @pytest.mark.asyncio
    async def test_disconnect(self):
        """Test disconnect method"""
        manager = MessageConnectionManager()
        mock_ws = MagicMock(spec=WebSocket)

        # First connect
        manager.active_connections["user-123"] = {mock_ws}

        await manager.disconnect(mock_ws, "user-123")

        assert "user-123" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_last_connection(self):
        """Test disconnect when it's the last connection"""
        manager = MessageConnectionManager()
        mock_ws = MagicMock(spec=WebSocket)
        manager.active_connections["user-123"] = {mock_ws}

        await manager.disconnect(mock_ws, "user-123")

        # Should remove the user key when no connections left
        assert "user-123" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_to_user(self):
        """Test sending message to user"""
        manager = MessageConnectionManager()
        mock_ws = MagicMock(spec=WebSocket)
        mock_ws.send_json = AsyncMock()

        manager.active_connections["user-123"] = {mock_ws}

        await manager.send_to_user("user-123", {"text": "Hello"})

        mock_ws.send_json.assert_called_once_with({"text": "Hello"})

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_user(self):
        """Test sending to user with no connections"""
        manager = MessageConnectionManager()

        # Should not raise
        await manager.send_to_user("nonexistent", {"text": "Hello"})


class TestMessageRouter:
    """Tests for messages router"""

    def test_router_defined(self):
        """Test that router is defined"""
        assert router is not None

    def test_router_has_routes(self):
        """Test that router has routes"""
        assert len(router.routes) > 0


class TestConnectionManagerEdgeCases:
    """Edge case tests for MessageConnectionManager"""

    @pytest.mark.asyncio
    async def test_multiple_connections_same_user(self):
        """Test multiple connections for same user"""
        manager = MessageConnectionManager()
        mock_ws1 = MagicMock(spec=WebSocket)
        mock_ws1.accept = AsyncMock()
        mock_ws2 = MagicMock(spec=WebSocket)
        mock_ws2.accept = AsyncMock()

        await manager.connect(mock_ws1, "user-123")
        await manager.connect(mock_ws2, "user-123")

        assert len(manager.active_connections["user-123"]) == 2

    @pytest.mark.asyncio
    async def test_disconnect_one_of_multiple(self):
        """Test disconnecting one of multiple connections"""
        manager = MessageConnectionManager()
        mock_ws1 = MagicMock(spec=WebSocket)
        mock_ws2 = MagicMock(spec=WebSocket)

        manager.active_connections["user-123"] = {mock_ws1, mock_ws2}

        await manager.disconnect(mock_ws1, "user-123")

        assert "user-123" in manager.active_connections
        assert mock_ws1 not in manager.active_connections["user-123"]
        assert mock_ws2 in manager.active_connections["user-123"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
