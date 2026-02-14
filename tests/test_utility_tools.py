"""
Tests for utility tools in core/tools/utility_tools.py
"""
import pytest
from unittest.mock import patch, mock_open
from datetime import datetime
from zoneinfo import ZoneInfo

from core.tools.utility_tools import get_current_time_tool, introduction_tool


class TestGetCurrentTimeTool:
    """Tests for get_current_time_tool function"""

    def test_default_timezone(self):
        """Test with default timezone (Asia/Taipei)"""
        result = get_current_time_tool.invoke({"timezone": "Asia/Taipei"})

        assert "當前時間" in result
        assert "時區" in result
        assert "Asia/Taipei" in result
        assert "UTC" in result

    def test_utc_timezone(self):
        """Test with UTC timezone"""
        result = get_current_time_tool.invoke({"timezone": "UTC"})

        assert "UTC" in result

    def test_new_york_timezone(self):
        """Test with America/New_York timezone"""
        result = get_current_time_tool.invoke({"timezone": "America/New_York"})

        assert "America/New_York" in result

    def test_tokyo_timezone(self):
        """Test with Asia/Tokyo timezone"""
        result = get_current_time_tool.invoke({"timezone": "Asia/Tokyo"})

        assert "Asia/Tokyo" in result

    def test_invalid_timezone_falls_back_to_taipei(self):
        """Test that invalid timezone falls back to Asia/Taipei"""
        result = get_current_time_tool.invoke({"timezone": "Invalid/Timezone"})

        # Should still return valid result with default timezone
        assert "當前時間" in result
        assert "Asia/Taipei" in result

    def test_output_format(self):
        """Test that output contains expected format elements"""
        result = get_current_time_tool.invoke({"timezone": "Asia/Taipei"})

        # Check for Chinese weekday
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        has_weekday = any(day in result for day in weekdays)
        assert has_weekday

        # Check for period markers
        assert "上午" in result or "下午" in result

    def test_tool_has_correct_name(self):
        """Test that tool has correct name"""
        assert get_current_time_tool.name == "get_current_time_tool"

    def test_tool_has_description(self):
        """Test that tool has description"""
        assert get_current_time_tool.description
        assert "時間" in get_current_time_tool.description

    def test_empty_timezone_uses_default(self):
        """Test that empty string timezone uses default"""
        result = get_current_time_tool.invoke({"timezone": ""})
        # Falls back to Taipei due to invalid timezone
        assert "當前時間" in result


class TestIntroductionTool:
    """Tests for introduction_tool function"""

    def test_tool_has_correct_name(self):
        """Test that tool has correct name"""
        assert introduction_tool.name == "introduction_tool"

    def test_tool_has_description(self):
        """Test that tool has description"""
        assert introduction_tool.description
        assert "開發者" in introduction_tool.description or "平台" in introduction_tool.description

    @patch("builtins.open", mock_open(read_data="Test Developer Info"))
    def test_reads_file_content(self):
        """Test that tool reads and returns file content"""
        result = introduction_tool.invoke("")
        assert "Test Developer Info" in result

    @patch("builtins.open", mock_open(read_data="Developer: Danny"))
    def test_prepends_prefix(self):
        """Test that tool prepends '平台開發者詳細資訊:' prefix"""
        result = introduction_tool.invoke("")
        assert "平台開發者詳細資訊:" in result

    @patch("builtins.open", side_effect=FileNotFoundError("File not found"))
    def test_handles_file_not_found(self, mock_file):
        """Test that tool handles file not found error"""
        with pytest.raises(FileNotFoundError):
            introduction_tool.invoke("")

    @patch("builtins.open", mock_open(read_data=""))
    def test_empty_file(self):
        """Test with empty file content"""
        result = introduction_tool.invoke("")
        assert "平台開發者詳細資訊:" in result


class TestTimeFormatting:
    """Tests for time formatting logic"""

    def test_weekday_mapping(self):
        """Test that all weekdays are properly mapped to Chinese"""
        # This tests the weekday_map inside the function indirectly
        result = get_current_time_tool.invoke({"timezone": "Asia/Taipei"})

        # Check that one of the Chinese weekdays is in the result
        weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        found_weekday = any(day in result for day in weekdays)
        assert found_weekday

    def test_12_hour_format(self):
        """Test that 12-hour format is included"""
        result = get_current_time_tool.invoke({"timezone": "Asia/Taipei"})

        # Should contain 上午 or 下午
        assert "上午" in result or "下午" in result

    def test_utc_time_included(self):
        """Test that UTC time is included in output"""
        result = get_current_time_tool.invoke({"timezone": "Asia/Taipei"})

        assert "UTC 時間" in result
        # UTC time should be in ISO-like format
        assert "-" in result  # Date separator
        assert ":" in result  # Time separator


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
