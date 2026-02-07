"""
Tests for governance API endpoints
Note: These are unit tests for the API layer using mocked database layer.
"""
import pytest
from datetime import datetime
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestReportEndpoints:
    """Tests for report management endpoints"""

    def test_submit_report_request_validation(self):
        """Test report request validation"""
        from api.models import ReportCreateRequest

        # Valid request
        valid_data = {
            "content_type": "post",
            "content_id": 123,
            "report_type": "spam",
            "description": "This is spam content"
        }
        request = ReportCreateRequest(**valid_data)
        assert request.content_type == "post"
        assert request.content_id == 123
        assert request.report_type == "spam"

        # Test with minimal data
        minimal = ReportCreateRequest(content_type="comment", content_id=456, report_type="harassment")
        assert minimal.description is None

    def test_report_response_serialization(self):
        """Test report response serialization"""
        from api.models import ReportResponse

        report = ReportResponse(
            id=1,
            reporter_user_id="user1",
            content_type="post",
            content_id=123,
            report_type="spam",
            description="Test spam",
            review_status="pending",
            created_at="2026-02-08T12:00:00"
        )
        assert report.id == 1
        assert report.review_status == "pending"
        assert report.created_at == "2026-02-08T12:00:00"


class TestVotingEndpoints:
    """Tests for voting endpoints"""

    def test_vote_request_validation(self):
        """Test vote request validation"""
        from api.models import VoteRequest

        # Valid approve vote
        vote = VoteRequest(vote_type="approve")
        assert vote.vote_type == "approve"

        # Valid reject vote
        vote = VoteRequest(vote_type="reject")
        assert vote.vote_type == "reject"

    def test_consensus_response(self):
        """Test consensus response serialization"""
        from api.models import ConsensusResponse

        consensus = ConsensusResponse(
            has_consensus=True,
            decision="approved",
            total_votes=5,
            approve_count=4,
            reject_count=1,
            approve_rate=0.8
        )
        assert consensus.has_consensus is True
        assert consensus.decision == "approved"
        assert consensus.approve_rate == 0.8


class TestViolationEndpoints:
    """Tests for violation record endpoints"""

    def test_violation_points_response(self):
        """Test violation points response serialization"""
        from api.models import ViolationPointsResponse

        violation = ViolationPointsResponse(
            user_id="test-user",
            points=15,
            total_violations=5,
            suspension_count=2,
            last_violation_at="2026-02-01T12:00:00"
        )
        assert violation.points == 15
        assert violation.user_id == "test-user"


class TestStatisticsEndpoints:
    """Tests for statistics endpoints"""

    def test_review_statistics_response(self):
        """Test review statistics response serialization"""
        from api.models import ReviewStatisticsResponse

        stats = ReviewStatisticsResponse(
            total_reports=100,
            pending_reports=10,
            approved_reports=60,
            rejected_reports=30,
            total_votes=200,
            avg_approval_rate=0.75
        )
        assert stats.total_reports == 100
        assert stats.approved_reports == 60
        assert stats.avg_approval_rate == 0.75


class TestReputationEndpoints:
    """Tests for reputation endpoints"""

    def test_audit_reputation_response(self):
        """Test audit reputation response serialization"""
        from api.models import AuditReputationResponse

        reputation = AuditReputationResponse(
            user_id="test-pro",
            username="TestPro",
            total_reviews=20,
            correct_votes=17,
            accuracy_rate=0.85,
            reputation_score=145,
            vote_weight=1.5
        )
        assert reputation.total_reviews == 20
        assert reputation.accuracy_rate == 0.85
        assert reputation.vote_weight == 1.5
        assert reputation.username == "TestPro"


class TestActivityLogEndpoints:
    """Tests for activity log endpoints"""

    def test_activity_log_response(self):
        """Test activity log response serialization"""
        from api.models import ActivityLogResponse

        log = ActivityLogResponse(
            id=1,
            user_id="test-user",
            activity_type="report_submitted",
            resource_type="report",
            resource_id=1,
            metadata={"report_type": "spam"},
            success=True,
            error_message=None,
            created_at="2026-02-07T12:00:00"
        )
        assert log.activity_type == "report_submitted"
        assert log.success is True


class TestFinalizeEndpoints:
    """Tests for finalize endpoints"""

    def test_finalize_request_validation(self):
        """Test finalize request validation"""
        from api.models import FinalizeReportRequest

        # Approved
        request = FinalizeReportRequest(decision="approved", violation_level="medium")
        assert request.decision == "approved"
        assert request.violation_level == "medium"

        # Rejected
        request = FinalizeReportRequest(decision="rejected")
        assert request.decision == "rejected"
        assert request.violation_level is None

    def test_consensus_response_with_reason(self):
        """Test consensus response with no consensus reason"""
        from api.models import ConsensusResponse

        consensus = ConsensusResponse(
            has_consensus=False,
            decision=None,
            total_votes=4,
            approve_count=2,
            reject_count=2,
            approve_rate=0.5,
            reason="no_clear_consensus"
        )
        assert consensus.has_consensus is False
        assert consensus.reason == "no_clear_consensus"


class TestViolationRecordEndpoints:
    """Tests for violation record endpoints"""

    def test_violation_record_response(self):
        """Test violation record response serialization"""
        from api.models import ViolationRecordResponse

        record = ViolationRecordResponse(
            id=1,
            user_id="test-user",
            violation_level="medium",
            violation_type="spam",
            points=3,
            action_taken="warning",
            suspended_until=None,
            created_at="2026-02-01T12:00:00"
        )
        assert record.points == 3
        assert record.action_taken == "warning"

    def test_violation_record_with_suspension(self):
        """Test violation record with suspension"""
        from api.models import ViolationRecordResponse

        record = ViolationRecordResponse(
            id=2,
            user_id="bad-user",
            violation_level="severe",
            violation_type="scam",
            points=30,
            action_taken="suspend_30d",
            suspended_until="2026-03-01T12:00:00",
            created_at="2026-02-01T12:00:00"
        )
        assert record.suspended_until == "2026-03-01T12:00:00"


class TestReportDetailEndpoints:
    """Tests for report detail endpoints"""

    def test_report_detail_response(self):
        """Test report detail response serialization"""
        from api.models import ReportDetailResponse

        detail = ReportDetailResponse(
            id=1,
            content_type="post",
            content_id=123,
            reporter_user_id="user1",
            reporter_username="User1",
            report_type="spam",
            description="Spam post",
            review_status="pending",
            violation_level=None,
            approve_count=3,
            reject_count=0,
            created_at="2026-02-08T12:00:00",
            updated_at=None,
            votes=[]
        )
        assert detail.id == 1
        assert detail.approve_count == 3
        assert detail.reject_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
