"""
Tests for governance validators in core/validators/governance.py
"""
import pytest

from core.validators.governance import (
    validate_report_type,
    validate_content_type,
    validate_vote_type,
    validate_violation_level,
    validate_report_description,
    sanitize_description
)


class TestValidateReportType:
    """Tests for validate_report_type function"""

    def test_valid_report_types(self):
        """Test all valid report types"""
        valid_types = ["spam", "harassment", "misinformation", "scam", "illegal", "other"]
        for report_type in valid_types:
            result = validate_report_type(report_type)
            assert result["valid"] is True
            assert result["error"] is None

    def test_empty_report_type(self):
        """Test empty report type"""
        result = validate_report_type("")
        assert result["valid"] is False
        assert "不能為空" in result["error"]

    def test_none_report_type(self):
        """Test None report type"""
        result = validate_report_type(None)
        assert result["valid"] is False

    def test_invalid_report_type(self):
        """Test invalid report type"""
        result = validate_report_type("invalid_type")
        assert result["valid"] is False
        assert "無效" in result["error"]

    def test_case_sensitive(self):
        """Test that report type is case sensitive"""
        result = validate_report_type("SPAM")
        assert result["valid"] is False


class TestValidateContentType:
    """Tests for validate_content_type function"""

    def test_valid_content_types(self):
        """Test valid content types"""
        for content_type in ["post", "comment"]:
            result = validate_content_type(content_type)
            assert result["valid"] is True

    def test_empty_content_type(self):
        """Test empty content type"""
        result = validate_content_type("")
        assert result["valid"] is False
        assert "不能為空" in result["error"]

    def test_none_content_type(self):
        """Test None content type"""
        result = validate_content_type(None)
        assert result["valid"] is False

    def test_invalid_content_type(self):
        """Test invalid content type"""
        result = validate_content_type("message")
        assert result["valid"] is False
        assert "無效" in result["error"]


class TestValidateVoteType:
    """Tests for validate_vote_type function"""

    def test_valid_vote_types(self):
        """Test valid vote types"""
        for vote_type in ["approve", "reject"]:
            result = validate_vote_type(vote_type)
            assert result["valid"] is True

    def test_empty_vote_type(self):
        """Test empty vote type"""
        result = validate_vote_type("")
        assert result["valid"] is False
        assert "不能為空" in result["error"]

    def test_none_vote_type(self):
        """Test None vote type"""
        result = validate_vote_type(None)
        assert result["valid"] is False

    def test_invalid_vote_type(self):
        """Test invalid vote type"""
        result = validate_vote_type("maybe")
        assert result["valid"] is False
        assert "無效" in result["error"]


class TestValidateViolationLevel:
    """Tests for validate_violation_level function"""

    def test_valid_violation_levels(self):
        """Test all valid violation levels"""
        valid_levels = ["mild", "medium", "severe", "critical"]
        for level in valid_levels:
            result = validate_violation_level(level)
            assert result["valid"] is True

    def test_none_violation_level(self):
        """Test None violation level (should be valid)"""
        result = validate_violation_level(None)
        assert result["valid"] is True

    def test_empty_violation_level(self):
        """Test empty violation level (should be valid)"""
        result = validate_violation_level("")
        assert result["valid"] is True

    def test_invalid_violation_level(self):
        """Test invalid violation level"""
        result = validate_violation_level("extreme")
        assert result["valid"] is False
        assert "無效" in result["error"]


class TestValidateReportDescription:
    """Tests for validate_report_description function"""

    def test_valid_description(self):
        """Test valid description"""
        result = validate_report_description("This is a valid description")
        assert result["valid"] is True

    def test_none_description(self):
        """Test None description (should be valid)"""
        result = validate_report_description(None)
        assert result["valid"] is True

    def test_empty_description(self):
        """Test empty string description (treated as whitespace-only)"""
        result = validate_report_description("")
        # Empty string is treated as whitespace-only, so it's invalid
        assert result["valid"] is False
        assert "空白" in result["error"]

    def test_whitespace_only_description(self):
        """Test whitespace only description"""
        result = validate_report_description("   \n\t  ")
        assert result["valid"] is False
        assert "空白" in result["error"]

    def test_max_length_description(self):
        """Test description at max length"""
        long_description = "x" * 1000
        result = validate_report_description(long_description)
        assert result["valid"] is True

    def test_too_long_description(self):
        """Test description exceeding max length"""
        too_long_description = "x" * 1001
        result = validate_report_description(too_long_description)
        assert result["valid"] is False
        assert "過長" in result["error"]

    def test_unicode_description(self):
        """Test description with unicode characters"""
        result = validate_report_description("這是中文描述 🎉")
        assert result["valid"] is True


class TestSanitizeDescription:
    """Tests for sanitize_description function"""

    def test_basic_sanitization(self):
        """Test basic text sanitization"""
        result = sanitize_description("  hello world  ")
        assert result == "hello world"

    def test_multiple_spaces(self):
        """Test removing multiple spaces"""
        result = sanitize_description("hello    world")
        assert result == "hello world"

    def test_newlines_and_tabs(self):
        """Test handling newlines and tabs"""
        result = sanitize_description("hello\n\tworld")
        assert result == "hello world"

    def test_empty_string(self):
        """Test empty string"""
        result = sanitize_description("")
        assert result == ""

    def test_none_input(self):
        """Test None input"""
        result = sanitize_description(None)
        assert result == ""

    def test_whitespace_only(self):
        """Test whitespace only input"""
        result = sanitize_description("   \n\t  ")
        assert result == ""

    def test_preserves_content(self):
        """Test that valid content is preserved"""
        result = sanitize_description("This is a normal description.")
        assert result == "This is a normal description."

    def test_unicode_content(self):
        """Test unicode content is preserved"""
        result = sanitize_description("  這是測試  ")
        assert result == "這是測試"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
