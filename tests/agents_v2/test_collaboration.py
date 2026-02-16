"""Tests for Agent Collaboration"""
import pytest
from core.agents_v2.collaboration import CollaborationRequest, CollaborationResponse


class TestCollaborationRequest:
    """Test CollaborationRequest"""

    def test_request_creation(self):
        """Should create collaboration request"""
        request = CollaborationRequest(
            requester="technical_analysis",
            target="sentiment_analysis",
            reason="需要確認市場情緒",
            data_needed="social_sentiment_data"
        )
        assert request.requester == "technical_analysis"
        assert request.target == "sentiment_analysis"
        assert request.status == "pending"
        assert request.request_id is not None

    def test_request_accept(self):
        """Should be able to accept request"""
        request = CollaborationRequest(
            requester="tech", target="sentiment",
            reason="test", data_needed="data"
        )
        request.accept()
        assert request.status == "accepted"

    def test_request_reject(self):
        """Should be able to reject request"""
        request = CollaborationRequest(
            requester="tech", target="sentiment",
            reason="test", data_needed="data"
        )
        request.reject()
        assert request.status == "rejected"

    def test_request_complete(self):
        """Should be able to complete request"""
        request = CollaborationRequest(
            requester="tech", target="sentiment",
            reason="test", data_needed="data"
        )
        request.complete()
        assert request.status == "completed"


class TestCollaborationResponse:
    """Test CollaborationResponse"""

    def test_response_creation(self):
        """Should create collaboration response"""
        response = CollaborationResponse(
            request_id="req-123",
            responder="sentiment_analysis",
            data={"sentiment": "positive", "score": 0.7},
            accepted=True
        )
        assert response.request_id == "req-123"
        assert response.accepted is True
        assert response.data["sentiment"] == "positive"

    def test_response_with_message(self):
        """Should support optional message"""
        response = CollaborationResponse(
            request_id="req-123",
            responder="sentiment_analysis",
            data={},
            accepted=False,
            message="數據不可用"
        )
        assert response.message == "數據不可用"
