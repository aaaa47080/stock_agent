"""
Tests for forum database operations in core/database/forum.py
"""
import pytest
from unittest.mock import patch, MagicMock

from core.database.forum import (
    get_boards,
    get_board_by_slug,
    check_daily_post_limit
)


class TestGetBoards:
    """Tests for get_boards function"""

    def test_get_active_boards_only(self):
        """Test getting only active boards"""
        with patch('core.database.forum.DatabaseBase.query_all') as mock_query:
            mock_query.return_value = [
                {"id": 1, "name": "Board 1", "slug": "board-1", "description": "Test", "post_count": 5, "is_active": 1},
                {"id": 2, "name": "Board 2", "slug": "board-2", "description": "Test", "post_count": 3, "is_active": 1}
            ]

            result = get_boards(active_only=True)

            assert len(result) == 2
            assert result[0]["is_active"] is True

    def test_get_all_boards(self):
        """Test getting all boards including inactive"""
        with patch('core.database.forum.DatabaseBase.query_all') as mock_query:
            mock_query.return_value = [
                {"id": 1, "name": "Board 1", "slug": "board-1", "description": "Test", "post_count": 5, "is_active": 1},
                {"id": 2, "name": "Board 2", "slug": "board-2", "description": "Test", "post_count": 0, "is_active": 0}
            ]

            result = get_boards(active_only=False)

            assert len(result) == 2

    def test_empty_boards(self):
        """Test with no boards"""
        with patch('core.database.forum.DatabaseBase.query_all') as mock_query:
            mock_query.return_value = []

            result = get_boards()

            assert result == []

    def test_converts_is_active_to_bool(self):
        """Test that is_active is converted to boolean"""
        with patch('core.database.forum.DatabaseBase.query_all') as mock_query:
            mock_query.return_value = [
                {"id": 1, "name": "Board", "slug": "board", "description": "", "post_count": 0, "is_active": 1}
            ]

            result = get_boards()

            assert isinstance(result[0]["is_active"], bool)


class TestGetBoardBySlug:
    """Tests for get_board_by_slug function"""

    def test_get_existing_board(self):
        """Test getting an existing board"""
        with patch('core.database.forum.DatabaseBase.query_one') as mock_query:
            mock_query.return_value = {
                "id": 1, "name": "Test Board", "slug": "test-board", "description": "Test", "post_count": 5, "is_active": 1
            }

            result = get_board_by_slug("test-board")

            assert result is not None
            assert result["slug"] == "test-board"

    def test_get_nonexistent_board(self):
        """Test getting a nonexistent board"""
        with patch('core.database.forum.DatabaseBase.query_one') as mock_query:
            mock_query.return_value = None

            result = get_board_by_slug("nonexistent")

            assert result is None

    def test_converts_is_active_to_bool(self):
        """Test that is_active is converted to boolean"""
        with patch('core.database.forum.DatabaseBase.query_one') as mock_query:
            mock_query.return_value = {
                "id": 1, "name": "Board", "slug": "board", "description": "", "post_count": 0, "is_active": 1
            }

            result = get_board_by_slug("board")

            assert isinstance(result["is_active"], bool)


class TestCheckDailyPostLimit:
    """Tests for check_daily_post_limit function"""

    def test_free_user_within_limit(self):
        """Test free user within limit"""
        with patch('core.database.forum.get_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"count": 3}

            with patch('core.database.forum.get_user_membership') as mock_membership:
                mock_membership.return_value = {"is_pro": False}

                with patch('core.database.forum.get_limits') as mock_limits:
                    mock_limits.return_value = {"daily_post_free": 5}

                    result = check_daily_post_limit("user-123")

                    assert result["allowed"] is True

    def test_free_user_at_limit(self):
        """Test free user at limit"""
        with patch('core.database.forum.get_connection') as mock_conn:
            mock_cursor = MagicMock()
            mock_conn.return_value.__enter__.return_value.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = {"count": 5}

            with patch('core.database.forum.get_user_membership') as mock_membership:
                mock_membership.return_value = {"is_pro": False}

                with patch('core.database.forum.get_limits') as mock_limits:
                    mock_limits.return_value = {"daily_post_free": 5}

                    result = check_daily_post_limit("user-123")

                    assert result["allowed"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
