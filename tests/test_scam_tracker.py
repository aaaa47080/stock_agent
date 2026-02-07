"""
Tests for scam tracker database operations
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from core.database.scam_tracker import (
    create_scam_report,
    get_scam_reports,
    get_scam_report_by_id,
    search_wallet,
    vote_scam_report,
    add_scam_comment,
    get_scam_comments,
    _update_verification_status
)


class TestScamReportCreation:
    """Tests for scam report creation"""

    def setup_method(self):
        """Setup test fixtures"""
        self.valid_report_data = {
            'scam_wallet_address': 'G' + 'A' * 55,
            'reporter_user_id': 'test-user-001',
            'reporter_wallet_address': 'G' + 'B' * 55,
            'scam_type': 'fake_official',
            'description': '這是一個假冒官方的詐騙地址，假冒 Pi Network 官方人員進行詐騙。',
            'transaction_hash': None
        }

    @patch('core.database.scam_tracker.get_connection')
    @patch('core.database.scam_tracker.get_user_membership')
    def test_create_report_success(self, mock_membership, mock_get_connection):
        """Test successful report creation"""
        # Mock user as PRO member
        mock_membership.return_value = {'is_pro': True}

        # Mock database connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock database responses
        mock_cursor.fetchone.side_effect = [
            (0,),  # No existing reports today
            None,  # No duplicate wallet
        ]
        mock_cursor.execute.return_value = None
        mock_conn.commit.return_value = None

        # Mock insert returning ID
        mock_cursor.fetchone.return_value = (1,)

        result = create_scam_report(**self.valid_report_data)

        assert result["success"] is True
        assert result["report_id"] == 1
        mock_conn.commit.assert_called()

    @patch('core.database.scam_tracker.get_user_membership')
    def test_create_report_non_pro_user(self, mock_membership):
        """Test report creation by non-PRO user (should fail)"""
        mock_membership.return_value = {'is_pro': False}

        result = create_scam_report(**self.valid_report_data)

        assert result["success"] is False
        assert result["error"] == "pro_membership_required"

    def test_create_report_invalid_wallet_address(self):
        """Test report creation with invalid wallet address"""
        invalid_data = self.valid_report_data.copy()
        invalid_data['scam_wallet_address'] = 'INVALID'

        result = create_scam_report(**invalid_data)

        assert result["success"] is False
        assert result["error"] == "invalid_scam_wallet"


class TestScamReportQueries:
    """Tests for scam report queries"""

    @patch('core.database.scam_tracker.get_connection')
    def test_get_reports_empty(self, mock_get_connection):
        """Test getting reports when none exist"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        reports = get_scam_reports()

        assert reports == []

    @patch('core.database.scam_tracker.get_connection')
    def test_get_reports_with_data(self, mock_get_connection):
        """Test getting reports with data"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock database row
        from datetime import datetime
        now = datetime.now()

        mock_row = (
            1,  # id
            'G' + 'A' * 55,  # scam_wallet_address
            'fake_official',  # scam_type
            'Test description',  # description
            'pending',  # verification_status
            5,  # approve_count
            2,  # reject_count
            3,  # comment_count
            100,  # view_count
            'GABC...XYZ',  # reporter_wallet_masked
            now,  # created_at
            'testuser'  # reporter_username
        )
        mock_cursor.fetchall.return_value = [mock_row]

        reports = get_scam_reports()

        assert len(reports) == 1
        assert reports[0]["id"] == 1
        assert reports[0]["scam_type"] == "fake_official"
        assert reports[0]["net_votes"] == 3

    @patch('core.database.scam_tracker.get_connection')
    @patch('core.database.scam_tracker.validate_pi_address')
    def test_search_wallet_not_found(self, mock_validate, mock_get_connection):
        """Test searching for wallet that hasn't been reported"""
        mock_validate.return_value = (True, "")

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = search_wallet('G' + 'A' * 55)

        assert result is None

    @patch('core.database.scam_tracker.get_connection')
    @patch('core.database.scam_tracker.validate_pi_address')
    @patch('core.database.scam_tracker.get_scam_report_by_id')
    def test_search_wallet_found(self, mock_get_report, mock_validate, mock_get_connection):
        """Test searching for wallet that has been reported"""
        mock_validate.return_value = (True, "")

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)  # Report ID

        mock_get_report.return_value = {
            "id": 1,
            "scam_wallet_address": "G" + "A" * 55,
            "scam_type": "fake_official"
        }

        result = search_wallet('G' + 'A' * 55)

        assert result is not None
        assert result["id"] == 1


class TestVoting:
    """Tests for voting functionality"""

    @patch('core.database.scam_tracker.get_connection')
    def test_vote_approve_success(self, mock_get_connection):
        """Test successful approve vote"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock responses
        mock_cursor.fetchone.side_effect = [
            ('other-user',),  # Different from voter
            (0,),  # Recent votes
            None,  # No existing vote
        ]

        result = vote_scam_report(1, 'voter-user', 'approve')

        assert result["success"] is True
        assert result["action"] == "voted"
        mock_conn.commit.assert_called()

    @patch('core.database.scam_tracker.get_connection')
    def test_vote_own_report(self, mock_get_connection):
        """Test voting on own report (should fail)"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = ('voter-user',)  # Same as voter

        result = vote_scam_report(1, 'voter-user', 'approve')

        assert result["success"] is False
        assert result["error"] == "cannot_vote_own_report"

    @patch('core.database.scam_tracker.get_connection')
    def test_vote_too_fast(self, mock_get_connection):
        """Test voting too frequently (rate limit)"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            ('other-user',),  # Different from voter
            (5,),  # At rate limit
        ]

        result = vote_scam_report(1, 'voter-user', 'approve')

        assert result["success"] is False
        assert result["error"] == "vote_too_fast"


class TestVerificationStatus:
    """Tests for verification status updates"""

    @patch('core.database.scam_tracker.get_config')
    def test_update_to_verified(self, mock_get_config):
        """Test status update to verified"""
        mock_get_config.side_effect = [10, 0.7]  # threshold, rate

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (10, 7)  # 10 total, 7 approve

        _update_verification_status(mock_cursor, 1)

        mock_cursor.execute.assert_called()
        args = mock_cursor.execute.call_args
        assert 'verified' in args[0][2]

    @patch('core.database.scam_tracker.get_config')
    def test_update_to_disputed(self, mock_get_config):
        """Test status update to disputed"""
        mock_get_config.side_effect = [10, 0.7]  # threshold, rate

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (10, 2)  # 10 total, 2 approve

        _update_verification_status(mock_cursor, 1)

        args = mock_cursor.execute.call_args
        assert 'disputed' in args[0][2]

    @patch('core.database.scam_tracker.get_config')
    def test_stays_pending_below_threshold(self, mock_get_config):
        """Test status stays pending when below vote threshold"""
        mock_get_config.side_effect = [10, 0.7]  # threshold, rate

        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = (5, 4)  # Only 5 total votes

        _update_verification_status(mock_cursor, 1)

        args = mock_cursor.execute.call_args
        assert 'pending' in args[0][2]


class TestComments:
    """Tests for comment functionality"""

    @patch('core.database.scam_tracker.get_connection')
    @patch('core.database.scam_tracker.get_user_membership')
    @patch('core.database.scam_tracker.validate_pi_tx_hash')
    def test_add_comment_pro_user(self, mock_validate, mock_membership, mock_get_connection):
        """Test adding comment as PRO user"""
        mock_membership.return_value = {'is_pro': True}
        mock_validate.return_value = (True, "")

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (1,)  # Report exists
        mock_cursor.execute.return_value = None

        result = add_scam_comment(1, 'user-001', 'This is a testimony')

        assert result["success"] is True
        assert result["comment_id"] == 1

    @patch('core.database.scam_tracker.get_connection')
    @patch('core.database.scam_tracker.get_user_membership')
    def test_add_comment_non_pro_user(self, mock_membership, mock_get_connection):
        """Test adding comment as non-PRO user (should fail)"""
        mock_membership.return_value = {'is_pro': False}

        result = add_scam_comment(1, 'user-001', 'This is a testimony')

        assert result["success"] is False
        assert result["error"] == "pro_membership_required"

    @patch('core.database.scam_tracker.get_connection')
    def test_get_comments_empty(self, mock_get_connection):
        """Test getting comments when none exist"""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_connection.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        comments = get_scam_comments(1)

        assert comments == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
