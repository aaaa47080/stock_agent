"""
Tests for utility functions in utils/utils.py
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

from utils.utils import (
    safe_float,
    DataFrameEncoder
)


class TestSafeFloat:
    """Tests for safe_float function"""

    def test_integer_conversion(self):
        """Test converting integer to float"""
        result = safe_float(42)
        assert result == 42.0
        assert isinstance(result, float)

    def test_float_passthrough(self):
        """Test that float passes through"""
        result = safe_float(3.14)
        assert result == 3.14

    def test_string_number(self):
        """Test converting string number to float"""
        result = safe_float("123.45")
        assert result == 123.45

    def test_invalid_string_returns_default(self):
        """Test that invalid string returns default"""
        result = safe_float("not a number", default=0.0)
        assert result == 0.0

    def test_none_returns_default(self):
        """Test that None returns default"""
        result = safe_float(None, default=5.0)
        assert result == 5.0

    def test_custom_default(self):
        """Test custom default value"""
        result = safe_float("invalid", default=-1.0)
        assert result == -1.0

    def test_empty_string_returns_default(self):
        """Test that empty string returns default"""
        result = safe_float("", default=0.0)
        assert result == 0.0

    def test_zero_value(self):
        """Test zero value"""
        result = safe_float(0)
        assert result == 0.0

    def test_negative_value(self):
        """Test negative value"""
        result = safe_float(-42.5)
        assert result == -42.5

    def test_very_large_number(self):
        """Test very large number"""
        result = safe_float(1e10)
        assert result == 1e10

    def test_very_small_number(self):
        """Test very small number"""
        result = safe_float(1e-10)
        assert result == 1e-10

    def test_boolean_true(self):
        """Test boolean True conversion"""
        result = safe_float(True, default=0.0)
        assert result == 1.0

    def test_boolean_false(self):
        """Test boolean False conversion"""
        result = safe_float(False, default=0.0)
        assert result == 0.0


class TestDataFrameEncoder:
    """Tests for DataFrameEncoder class"""

    def test_encode_dataframe(self):
        """Test encoding a pandas DataFrame"""
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        encoder = DataFrameEncoder()
        result = encoder.default(df)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_encode_timestamp(self):
        """Test encoding pandas Timestamp"""
        ts = pd.Timestamp("2024-01-01")
        encoder = DataFrameEncoder()
        result = encoder.default(ts)
        assert isinstance(result, str)
        assert "2024-01-01" in result

    def test_encode_numpy_bool(self):
        """Test encoding numpy boolean"""
        val = np.bool_(True)
        encoder = DataFrameEncoder()
        result = encoder.default(val)
        assert result is True

    def test_encode_numpy_int(self):
        """Test encoding numpy integer"""
        val = np.int64(42)
        encoder = DataFrameEncoder()
        result = encoder.default(val)
        assert result == 42
        assert isinstance(result, int)

    def test_encode_numpy_float(self):
        """Test encoding numpy float"""
        val = np.float64(3.14)
        encoder = DataFrameEncoder()
        result = encoder.default(val)
        assert result == 3.14
        assert isinstance(result, float)

    def test_encode_numpy_array(self):
        """Test encoding numpy array"""
        arr = np.array([1, 2, 3])
        encoder = DataFrameEncoder()
        result = encoder.default(arr)
        assert result == [1, 2, 3]

    def test_encode_dataframe_with_values(self):
        """Test encoding DataFrame with various values"""
        df = pd.DataFrame({
            "int_col": [1, 2],
            "float_col": [3.14, 2.71],
            "str_col": ["a", "b"]
        })
        encoder = DataFrameEncoder()
        result = encoder.default(df)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["int_col"] == 1
        assert result[0]["float_col"] == 3.14


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
