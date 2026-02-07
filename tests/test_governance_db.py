"""
Tests for governance database operations
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from datetime import datetime, timedelta
from core.database.governance import (
    create_report,
    get_pending_reports,
    get_report_by_id,
    get_user_reports,
    check_daily_report_limit,
    vote_on_report,
    get_report_votes,
    check_report_consensus,
    finalize_report,
    add_violation_points,
    get_user_violation_points,
    get_user_violations,
    determine_suspension_action,
    apply_suspension,
    check_user_suspension,
    get_audit_reputation,
    calculate_vote_weight,
    update_audit_reputation,
    log_activity,
    get_user_activity_logs,
    get_content_author,
    get_report_statistics,
    get_top_reviewers,
    PRO_DAILY_REPORT_LIMIT,
    DEFAULT_DAILY_REPORT_LIMIT,
)


class TestReportManagement:
    """Tests for report management functions"""

    def setup_method(self):
        """Setup test fixtures"""
        self.valid_report_data = {
            'reporter_user_id': 'test-user-001',
            'content_type': 'post',
            'content_id': 123,
            'report_type': 'spam',
            'description': 'This is spam content'
        }

    @patch('core.database.governance.get_content_author')
    @patch('core.database.governance.check_daily_report_limit')
    @patch('core.database.governance.get_user_membership')
    @patch('core.database.governance.get_connection')
    def test_create_report_success(self, mock_get_conn, mock_membership, mock_check_limit, mock_get_author):
        """Test successful report creation"""
        mock_membership.return_value = {'is_pro': False}  # Free user
        mock_check_limit.return_value = True
        mock_get_author.return_value = 'content-author-id'

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # No duplicate report
        mock_cursor.fetchone.side_effect = [None, (1,)]  # First call for duplicate check, second for insert returning

        result = create_report(None, **self.valid_report_data)

        assert result["success"] is True
        assert result["report_id"] == 1
        mock_conn.commit.assert_called()

    @patch('core.database.governance.get_content_author')
    @patch('core.database.governance.check_daily_report_limit')
    @patch('core.database.governance.get_user_membership')
    def test_create_report_limit_exceeded(self, mock_membership, mock_check_limit, mock_get_author):
        """Test report creation when daily limit exceeded"""
        mock_membership.return_value = {'is_pro': False}
        mock_check_limit.return_value = False
        mock_get_author.return_value = 'content-author-id'

        result = create_report(None, **self.valid_report_data)

        assert result["success"] is False
        assert result["error"] == "daily_limit_exceeded"

    @patch('core.database.governance.get_content_author')
    @patch('core.database.governance.check_daily_report_limit')
    @patch('core.database.governance.get_user_membership')
    def test_create_report_own_content(self, mock_membership, mock_check_limit, mock_get_author):
        """Test report creation on own content (should fail)"""
        mock_membership.return_value = {'is_pro': False}
        mock_check_limit.return_value = True
        mock_get_author.return_value = 'test-user-001'  # Same as reporter

        result = create_report(None, **self.valid_report_data)

        assert result["success"] is False
        assert result["error"] == "cannot_report_own_content"

    @patch('core.database.governance.get_content_author')
    @patch('core.database.governance.check_daily_report_limit')
    @patch('core.database.governance.get_user_membership')
    @patch('core.database.governance.get_connection')
    def test_create_report_duplicate(self, mock_get_conn, mock_membership, mock_check_limit, mock_get_author):
        """Test duplicate report creation (should fail)"""
        mock_membership.return_value = {'is_pro': False}
        mock_check_limit.return_value = True
        mock_get_author.return_value = 'content-author-id'

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (1,)  # Duplicate exists

        result = create_report(None, **self.valid_report_data)

        assert result["success"] is False
        assert result["error"] == "duplicate_report"

    @patch('core.database.governance.get_connection')
    def test_get_pending_reports_empty(self, mock_get_conn):
        """Test getting pending reports when none exist"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        reports = get_pending_reports(None, 20, 0, None)

        assert reports == []

    @patch('core.database.governance.get_connection')
    def test_get_pending_reports_with_data(self, mock_get_conn):
        """Test getting pending reports with data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        now = datetime.now()
        mock_cursor.fetchall.return_value = [
            (1, 'post', 123, 'test-user-001', 'spam', 'Test desc',
             'pending', None, 0, 0, now, now, 'reporter_user')
        ]

        reports = get_pending_reports(None, 20, 0, None)

        assert len(reports) == 1
        assert reports[0]["id"] == 1
        assert reports[0]["report_type"] == "spam"

    @patch('core.database.governance.get_connection')
    def test_get_report_by_id_not_found(self, mock_get_conn):
        """Test getting non-existent report"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = get_report_by_id(None, 999)

        assert result is None

    @patch('core.database.governance.get_connection')
    def test_get_report_by_id_found(self, mock_get_conn):
        """Test getting existing report"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        now = datetime.now()
        mock_cursor.fetchone.return_value = (
            1, 'post', 123, 'test-user-001', 'spam', 'Test desc',
            'pending', None, 0, 0, now, now, 'reporter_user'
        )

        result = get_report_by_id(None, 1)

        assert result is not None
        assert result["id"] == 1
        assert result["content_type"] == "post"

    @patch('core.database.governance.get_connection')
    def test_check_daily_report_limit_allowed(self, mock_get_conn):
        """Test daily report limit check when allowed"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (2,)  # Current count

        result = check_daily_report_limit(None, 'test-user', 5)

        assert result is True

    @patch('core.database.governance.get_connection')
    def test_check_daily_report_limit_exceeded(self, mock_get_conn):
        """Test daily report limit check when exceeded"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (5,)  # At limit

        result = check_daily_report_limit(None, 'test-user', 5)

        assert result is False


class TestVoting:
    """Tests for voting functions"""

    @patch('core.database.governance.get_user_membership')
    @patch('core.database.governance.get_audit_reputation')
    @patch('core.database.governance.get_connection')
    def test_vote_on_report_approve(self, mock_get_conn, mock_reputation, mock_membership):
        """Test successful approve vote"""
        mock_membership.return_value = {'is_pro': True}
        mock_reputation.return_value = {'reputation_score': 50}

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            ('pending',),  # Report status
            None,  # No existing vote
            (1,),  # Insert returning ID
        ]

        result = vote_on_report(None, 1, 'voter-user', 'approve')

        assert result["success"] is True
        assert result["vote_id"] == 1
        mock_conn.commit.assert_called()

    @patch('core.database.governance.get_user_membership')
    def test_vote_on_report_non_pro(self, mock_membership):
        """Test voting by non-PRO user (should fail)"""
        mock_membership.return_value = {'is_pro': False}

        result = vote_on_report(None, 1, 'voter-user', 'approve')

        assert result["success"] is False
        assert result["error"] == "pro_membership_required"

    @patch('core.database.governance.get_user_membership')
    @patch('core.database.governance.get_audit_reputation')
    @patch('core.database.governance.get_connection')
    def test_vote_on_report_already_voted(self, mock_get_conn, mock_reputation, mock_membership):
        """Test voting when already voted"""
        mock_membership.return_value = {'is_pro': True}
        mock_reputation.return_value = {'reputation_score': 50}

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            ('pending',),  # Report status
            (1, 'approve'),  # Existing vote
        ]

        result = vote_on_report(None, 1, 'voter-user', 'approve')

        assert result["success"] is False
        assert result["error"] == "already_voted"

    @patch('core.database.governance.get_connection')
    def test_get_report_votes_empty(self, mock_get_conn):
        """Test getting votes when none exist"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        votes = get_report_votes(None, 1)

        assert votes == []

    @patch('core.database.governance.get_connection')
    def test_check_report_consensus_approve(self, mock_get_conn):
        """Test consensus check for approve"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # 8 approve, 2 reject = 80% approve > 70% threshold
        mock_cursor.fetchone.return_value = (10, 8, 2)

        result = check_report_consensus(None, 1)

        assert result["has_consensus"] is True
        assert result["decision"] == "approved"
        assert result["approve_rate"] == 0.8

    @patch('core.database.governance.get_connection')
    def test_check_report_consensus_reject(self, mock_get_conn):
        """Test consensus check for reject"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # 2 approve, 8 reject = 20% approve < 30% threshold
        mock_cursor.fetchone.return_value = (10, 2, 8)

        result = check_report_consensus(None, 1)

        assert result["has_consensus"] is True
        assert result["decision"] == "rejected"

    @patch('core.database.governance.get_connection')
    def test_check_report_consensus_no_consensus(self, mock_get_conn):
        """Test consensus check when no consensus"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # 5 approve, 4 reject = 55.6% approve (between thresholds)
        mock_cursor.fetchone.return_value = (9, 5, 4)

        result = check_report_consensus(None, 1)

        assert result["has_consensus"] is False
        # decision key should not be in result when no consensus
        assert "decision" not in result or result.get("decision") is None

    @patch('core.database.governance.get_connection')
    def test_check_report_consensus_below_threshold(self, mock_get_conn):
        """Test consensus check when below minimum votes"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Only 2 votes total
        mock_cursor.fetchone.return_value = (2, 2, 0)

        result = check_report_consensus(None, 1)

        assert result["has_consensus"] is False
        assert "minimum_votes" in result

    @patch('core.database.governance.get_connection')
    @patch('core.database.governance.get_content_author')
    @patch('core.database.governance.add_violation_points')
    @patch('core.database.governance.apply_suspension')
    @patch('core.database.governance.get_user_violation_points')
    @patch('core.database.governance.determine_suspension_action')
    @patch('core.database.governance.get_report_votes')
    @patch('core.database.governance.update_audit_reputation')
    def test_finalize_report_approved(self, mock_update_reputation, mock_get_votes, mock_determine_action,
                                       mock_get_violation_points, mock_apply_suspension, mock_add_violation,
                                       mock_get_author, mock_get_conn):
        """Test finalizing report with approve decision"""
        mock_apply_suspension.return_value = True
        mock_add_violation.return_value = {"success": True}
        mock_get_author.return_value = 'content-author-user'
        mock_get_violation_points.return_value = {"points": 0}
        mock_determine_action.return_value = 'warning'
        mock_get_votes.return_value = []
        mock_update_reputation.return_value = None

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = ('reporter-user', 'post', 123)

        result = finalize_report(None, 1, 'approved', 'medium', 'admin-user')

        assert result["success"] is True
        assert result["decision"] == "approved"
        mock_conn.commit.assert_called()

    @patch('core.database.governance.get_connection')
    @patch('core.database.governance.get_content_author')
    @patch('core.database.governance.get_report_votes')
    @patch('core.database.governance.update_audit_reputation')
    def test_finalize_report_rejected(self, mock_update_reputation, mock_get_votes, mock_get_author, mock_get_conn):
        """Test finalizing report with reject decision"""
        mock_get_author.return_value = 'content-author-user'
        mock_get_votes.return_value = []
        mock_update_reputation.return_value = None

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = ('reporter-user', 'post', 123)

        result = finalize_report(None, 1, 'rejected', None, 'admin-user')

        assert result["success"] is True
        assert result["decision"] == "rejected"


class TestViolations:
    """Tests for violation functions"""

    @patch('core.database.governance.get_connection')
    def test_add_violation_points(self, mock_get_conn):
        """Test adding violation points"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (5,)  # violation id

        result = add_violation_points(
            None, 'test-user', 3, 'medium', 'spam',
            'report', 1, 'admin-user'
        )

        assert result["success"] is True
        assert result["violation_id"] == 5
        mock_conn.commit.assert_called()

    @patch('core.database.governance.get_connection')
    def test_get_user_violation_points(self, mock_get_conn):
        """Test getting user violation points"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Return all 4 columns
        mock_cursor.fetchone.return_value = (15, 5, 2, datetime.now())

        result = get_user_violation_points(None, 'test-user')

        assert result["points"] == 15
        assert result["total_violations"] == 5
        assert result["suspension_count"] == 2

    @patch('core.database.governance.get_connection')
    def test_get_user_violation_points_no_record(self, mock_get_conn):
        """Test getting violation points for user with no record"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None

        result = get_user_violation_points(None, 'test-user')

        assert result["points"] == 0
        assert result["total_violations"] == 0

    @patch('core.database.governance.get_connection')
    def test_get_user_violations(self, mock_get_conn):
        """Test getting user violation history"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        now = datetime.now()
        # Return all 9 columns
        mock_cursor.fetchall.return_value = [
            (1, 'medium', 'spam', 3, 'report', 'suspend_3d', now, now, 'admin-user'),
            (2, 'mild', 'harassment', 1, 'report', None, None, now, 'admin-user'),
        ]

        result = get_user_violations(None, 'test-user')

        assert len(result) == 2
        assert result[0]["violation_level"] == "medium"
        assert result[1]["violation_type"] == "harassment"

    def test_determine_suspension_action_warning(self):
        """Test suspension action determination for warning"""
        result = determine_suspension_action(5)
        assert result == "warning"

    def test_determine_suspension_action_suspend_3d(self):
        """Test suspension action determination for 3 day suspension"""
        result = determine_suspension_action(10)
        assert result == "suspend_3d"

    def test_determine_suspension_action_suspend_7d(self):
        """Test suspension action determination for 7 day suspension"""
        result = determine_suspension_action(20)
        assert result == "suspend_7d"

    def test_determine_suspension_action_suspend_30d(self):
        """Test suspension action determination for 30 day suspension"""
        result = determine_suspension_action(35)
        assert result == "suspend_30d"

    def test_determine_suspension_action_permanent_ban(self):
        """Test suspension action determination for permanent ban"""
        result = determine_suspension_action(45)
        assert result == "permanent_ban"

    def test_determine_suspension_action_no_action(self):
        """Test suspension action when no action needed"""
        result = determine_suspension_action(3)
        assert result is None

    @patch('core.database.governance.get_connection')
    def test_apply_suspension_success(self, mock_get_conn):
        """Test applying suspension to user"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1

        result = apply_suspension(None, 'test-user', 'suspend_7d')

        assert result is True
        mock_conn.commit.assert_called()

    @patch('core.database.governance.get_connection')
    def test_check_user_suspension_active(self, mock_get_conn):
        """Test checking user suspension status when active"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        future_time = datetime.now() + timedelta(days=5)
        mock_cursor.fetchone.return_value = ('suspend_7d', future_time, 1)

        result = check_user_suspension(None, 'test-user')

        assert result["is_suspended"] is True
        assert result["action"] == "suspend_7d"

    @patch('core.database.governance.get_connection')
    def test_check_user_suspension_none(self, mock_get_conn):
        """Test checking user suspension when not suspended"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None

        result = check_user_suspension(None, 'test-user')

        assert result["is_suspended"] is False


class TestAuditReputation:
    """Tests for audit reputation functions"""

    @patch('core.database.governance.get_connection')
    def test_get_audit_reputation_exists(self, mock_get_conn):
        """Test getting existing audit reputation"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Return all 4 columns: total_reviews, correct_votes, accuracy_rate, reputation_score
        mock_cursor.fetchone.return_value = (100, 85, 0.85, 50)

        result = get_audit_reputation(None, 'test-user')

        assert result["total_reviews"] == 100
        assert result["correct_votes"] == 85
        assert result["accuracy_rate"] == 0.85
        assert result["reputation_score"] == 50

    @patch('core.database.governance.get_connection')
    def test_get_audit_reputation_new_user(self, mock_get_conn):
        """Test getting reputation for new user"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None

        result = get_audit_reputation(None, 'test-user')

        assert result["total_reviews"] == 0
        assert result["accuracy_rate"] == 1.0
        assert result["reputation_score"] == 0

    def test_calculate_vote_weight_new_user(self):
        """Test vote weight calculation for new user"""
        reputation = {"reputation_score": 0}
        result = calculate_vote_weight(reputation)
        assert result == 1.0

    def test_calculate_vote_weight_experienced_user(self):
        """Test vote weight calculation for experienced user"""
        reputation = {"reputation_score": 60, "total_reviews": 15}
        result = calculate_vote_weight(reputation)
        assert result == 1.5

    def test_calculate_vote_weight_top_reviewer(self):
        """Test vote weight for top reviewer"""
        reputation = {"reputation_score": 95, "total_reviews": 30}
        result = calculate_vote_weight(reputation)
        assert result == 2.0

    @patch('core.database.governance.get_connection')
    def test_update_audit_reputation_correct(self, mock_get_conn):
        """Test updating reputation after correct vote"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (10, 8)  # total_reviews, correct_votes

        result = update_audit_reputation(None, 'test-user', was_correct=True)

        assert result["success"] is True
        mock_conn.commit.assert_called()

    @patch('core.database.governance.get_connection')
    def test_update_audit_reputation_incorrect(self, mock_get_conn):
        """Test updating reputation after incorrect vote"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (10, 8)  # total_reviews, correct_votes

        result = update_audit_reputation(None, 'test-user', was_correct=False)

        assert result["success"] is True


class TestActivityLogging:
    """Tests for activity logging functions"""

    @patch('core.database.governance.get_connection')
    def test_log_activity(self, mock_get_conn):
        """Test logging user activity"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (1,)

        result = log_activity(
            None, 'test-user', 'report_submitted', 'post', 123,
            {'key': 'value'}, True, None, '127.0.0.1', 'Mozilla'
        )

        assert result["success"] is True
        assert result["log_id"] == 1

    @patch('core.database.governance.get_connection')
    def test_get_user_activity_logs(self, mock_get_conn):
        """Test getting user activity logs"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        now = datetime.now()
        # Return 8 columns (id through created_at)
        mock_cursor.fetchall.return_value = [
            (1, 'report_submitted', 'post', 123, '{"key": "value"}', True, None, now),
            (2, 'review_vote', 'report', 1, None, True, None, now),
        ]

        result = get_user_activity_logs(None, 'test-user')

        assert len(result) == 2
        assert result[0]["activity_type"] == "report_submitted"


class TestHelpers:
    """Tests for helper functions"""

    @patch('core.database.governance.get_connection')
    def test_get_content_author_post(self, mock_get_conn):
        """Test getting author of a post"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = ('author-user-id',)

        result = get_content_author(None, 'post', 123)

        assert result == 'author-user-id'

    @patch('core.database.governance.get_connection')
    def test_get_content_author_comment(self, mock_get_conn):
        """Test getting author of a comment"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = ('comment-author-id',)

        result = get_content_author(None, 'comment', 456)

        assert result == 'comment-author-id'

    @patch('core.database.governance.get_connection')
    def test_get_content_author_not_found(self, mock_get_conn):
        """Test getting author when content not found"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = None

        result = get_content_author(None, 'post', 999)

        assert result is None

    @patch('core.database.governance.get_connection')
    def test_get_report_statistics(self, mock_get_conn):
        """Test getting report statistics"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (100, 60, 30, 10, 200)

        result = get_report_statistics(None, 30)

        assert result["total_reports"] == 100
        assert result["approved_reports"] == 60
        assert result["rejected_reports"] == 30
        assert result["pending_reports"] == 10

    @patch('core.database.governance.get_connection')
    def test_get_top_reviewers(self, mock_get_conn):
        """Test getting top reviewers"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Return all 6 columns
        mock_cursor.fetchall.return_value = [
            ('user1', 'User One', 100, 85, 0.85, 850),
            ('user2', 'User Two', 80, 70, 0.875, 700),
        ]

        result = get_top_reviewers(None, 10)

        assert len(result) == 2
        assert result[0]["user_id"] == "user1"
        assert result[0]["total_reviews"] == 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
