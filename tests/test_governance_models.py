"""
Tests for governance Pydantic models
"""
import pytest
from pydantic import ValidationError
from api.models import (
    ReportCreateRequest,
    ReportResponse,
    VoteRequest,
    ReportDetailResponse,
    ViolationPointsResponse,
    ViolationRecordResponse,
    ActivityLogResponse,
    ReviewStatisticsResponse,
    AuditReputationResponse,
    FinalizeReportRequest,
    ConsensusResponse,
)


class TestReportModels:
    """Tests for report-related models"""

    def test_report_create_request_valid(self):
        """Test valid report creation request"""
        data = {
            "content_type": "post",
            "content_id": 123,
            "report_type": "spam",
            "description": "This is spam content"
        }
        request = ReportCreateRequest(**data)
        assert request.content_type == "post"
        assert request.content_id == 123
        assert request.report_type == "spam"
        assert request.description == "This is spam content"

    def test_report_create_request_minimal(self):
        """Test report creation request with minimal fields"""
        data = {
            "content_type": "comment",
            "content_id": 456,
            "report_type": "harassment"
        }
        request = ReportCreateRequest(**data)
        assert request.description is None

    def test_vote_request_approve(self):
        """Test approve vote request"""
        request = VoteRequest(vote_type="approve")
        assert request.vote_type == "approve"

    def test_vote_request_reject(self):
        """Test reject vote request"""
        request = VoteRequest(vote_type="reject")
        assert request.vote_type == "reject"

    def test_report_response(self):
        """Test report response model"""
        data = {
            "id": 1,
            "content_type": "post",
            "content_id": 123,
            "reporter_user_id": "user123",
            "report_type": "spam",
            "description": "Spam post",
            "review_status": "pending",
            "created_at": "2026-02-07T12:00:00",
            "updated_at": "2026-02-07T12:00:00"
        }
        response = ReportResponse(**data)
        assert response.id == 1
        assert response.review_status == "pending"

    def test_report_detail_response(self):
        """Test report detail response with votes"""
        data = {
            "id": 1,
            "content_type": "post",
            "content_id": 123,
            "reporter_user_id": "user123",
            "reporter_username": "user123",
            "report_type": "spam",
            "description": "Spam post",
            "review_status": "pending",
            "violation_level": None,
            "approve_count": 5,
            "reject_count": 2,
            "created_at": "2026-02-07T12:00:00",
            "updated_at": "2026-02-07T12:00:00",
            "votes": [
                {"reviewer_user_id": "pro1", "vote_type": "approve"},
                {"reviewer_user_id": "pro2", "vote_type": "reject"}
            ]
        }
        response = ReportDetailResponse(**data)
        assert response.approve_count == 5
        assert response.reject_count == 2
        assert len(response.votes) == 2


class TestViolationModels:
    """Tests for violation-related models"""

    def test_violation_points_response(self):
        """Test violation points response"""
        data = {
            "user_id": "user123",
            "points": 15,
            "total_violations": 5,
            "suspension_count": 2,
            "last_violation_at": "2026-02-01T12:00:00",
            "action_threshold": "suspend_7d"
        }
        response = ViolationPointsResponse(**data)
        assert response.points == 15
        assert response.action_threshold == "suspend_7d"

    def test_violation_record_response(self):
        """Test violation record response"""
        data = {
            "id": 1,
            "user_id": "user123",
            "violation_level": "medium",
            "violation_type": "spam",
            "points": 3,
            "action_taken": "warning",
            "suspended_until": None,
            "created_at": "2026-02-07T12:00:00"
        }
        response = ViolationRecordResponse(**data)
        assert response.violation_level == "medium"
        assert response.action_taken == "warning"

    def test_violation_record_with_suspension(self):
        """Test violation record with suspension"""
        data = {
            "id": 2,
            "user_id": "user456",
            "violation_level": "severe",
            "violation_type": "harassment",
            "points": 5,
            "action_taken": "suspend_3d",
            "suspended_until": "2026-02-10T12:00:00",
            "created_at": "2026-02-07T12:00:00"
        }
        response = ViolationRecordResponse(**data)
        assert response.suspended_until == "2026-02-10T12:00:00"


class TestActivityModels:
    """Tests for activity-related models"""

    def test_activity_log_response(self):
        """Test activity log response"""
        data = {
            "id": 1,
            "user_id": "user123",
            "activity_type": "report_submitted",
            "resource_type": "report",
            "resource_id": 1,
            "metadata": {"report_type": "spam"},
            "success": True,
            "error_message": None,
            "created_at": "2026-02-07T12:00:00"
        }
        response = ActivityLogResponse(**data)
        assert response.activity_type == "report_submitted"
        assert response.metadata["report_type"] == "spam"

    def test_activity_log_with_error(self):
        """Test activity log with error"""
        data = {
            "id": 2,
            "user_id": "user123",
            "activity_type": "report_submitted",
            "resource_type": None,
            "resource_id": None,
            "metadata": None,
            "success": False,
            "error_message": "Daily limit exceeded",
            "created_at": "2026-02-07T12:00:00"
        }
        response = ActivityLogResponse(**data)
        assert response.success is False
        assert response.error_message == "Daily limit exceeded"


class TestStatisticsModels:
    """Tests for statistics-related models"""

    def test_review_statistics_response(self):
        """Test review statistics response"""
        data = {
            "total_reports": 100,
            "pending_reports": 10,
            "approved_reports": 60,
            "rejected_reports": 30,
            "total_votes": 200,
            "avg_approval_rate": 0.75
        }
        response = ReviewStatisticsResponse(**data)
        assert response.total_reports == 100
        assert response.avg_approval_rate == 0.75

    def test_audit_reputation_response(self):
        """Test audit reputation response"""
        data = {
            "user_id": "pro123",
            "username": "pro_user",
            "total_reviews": 50,
            "correct_votes": 42,
            "accuracy_rate": 0.84,
            "reputation_score": 370,
            "vote_weight": 1.5
        }
        response = AuditReputationResponse(**data)
        assert response.reputation_score == 370
        assert response.vote_weight == 1.5


class TestFinalizeModels:
    """Tests for finalize-related models"""

    def test_finalize_report_request_approved(self):
        """Test finalize request with approval"""
        data = {
            "decision": "approved",
            "violation_level": "medium"
        }
        request = FinalizeReportRequest(**data)
        assert request.decision == "approved"
        assert request.violation_level == "medium"

    def test_finalize_report_request_rejected(self):
        """Test finalize request with rejection"""
        data = {
            "decision": "rejected",
            "violation_level": None
        }
        request = FinalizeReportRequest(**data)
        assert request.decision == "rejected"
        assert request.violation_level is None

    def test_consensus_response_with_consensus(self):
        """Test consensus response when consensus reached"""
        data = {
            "has_consensus": True,
            "decision": "approved",
            "total_votes": 10,
            "approve_count": 8,
            "reject_count": 2,
            "approve_rate": 0.8,
            "reason": None
        }
        response = ConsensusResponse(**data)
        assert response.has_consensus is True
        assert response.decision == "approved"

    def test_consensus_response_no_consensus(self):
        """Test consensus response when no consensus"""
        data = {
            "has_consensus": False,
            "decision": None,
            "total_votes": 5,
            "approve_count": 3,
            "reject_count": 2,
            "approve_rate": 0.6,
            "reason": "insufficient_votes"
        }
        response = ConsensusResponse(**data)
        assert response.has_consensus is False
        assert response.decision is None
        assert response.reason == "insufficient_votes"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
