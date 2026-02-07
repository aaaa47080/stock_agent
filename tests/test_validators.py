"""
Tests for validators module
"""
import pytest
from core.validators.pi_address import (
    validate_pi_address,
    validate_pi_tx_hash,
    mask_wallet_address
)
from core.validators.content_filter import (
    filter_sensitive_content,
    sanitize_description
)


class TestPiAddressValidator:
    """Tests for Pi Network address validator"""

    def test_valid_address(self):
        """Test valid Pi Network address"""
        # Valid: G followed by 55 uppercase Base32 characters
        valid_addr = 'G' + 'A' * 55
        is_valid, error = validate_pi_address(valid_addr)
        assert is_valid is True
        assert error == ""

    def test_valid_address_with_base32_chars(self):
        """Test valid address with mixed Base32 characters"""
        # Base32 charset: A-Z and 2-7 (no '1')
        base32_charset = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
        valid_addr = 'G' + ''.join(base32_charset[i % len(base32_charset)] for i in range(55))
        is_valid, error = validate_pi_address(valid_addr)
        assert is_valid is True
        assert error == ""

    def test_empty_address(self):
        """Test empty address"""
        is_valid, error = validate_pi_address("")
        assert is_valid is False
        assert "不能為空" in error

    def test_none_address(self):
        """Test None address"""
        is_valid, error = validate_pi_address(None)
        assert is_valid is False
        assert "不能為空" in error

    def test_wrong_length(self):
        """Test address with wrong length"""
        is_valid, error = validate_pi_address("G" + "A" * 10)
        assert is_valid is False
        assert "56" in error

    def test_not_starting_with_g(self):
        """Test address not starting with G"""
        is_valid, error = validate_pi_address("A" + "G" * 55)
        assert is_valid is False
        assert "G" in error

    def test_invalid_characters(self):
        """Test address with invalid characters"""
        is_valid, error = validate_pi_address("G" + "a" * 55)  # lowercase
        assert is_valid is False
        assert "字符" in error

    def test_address_masking(self):
        """Test wallet address masking"""
        address = "GABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        masked = mask_wallet_address(address, mask_length=4)
        assert masked == "GABC...4567"

    def test_address_masking_short(self):
        """Test masking short address (should return as-is)"""
        address = "GABC"
        masked = mask_wallet_address(address, mask_length=4)
        assert masked == address

    def test_tx_hash_valid(self):
        """Test valid transaction hash"""
        valid_hash = "a" * 64
        is_valid, error = validate_pi_tx_hash(valid_hash)
        assert is_valid is True
        assert error == ""

    def test_tx_hash_optional(self):
        """Test optional transaction hash (None is allowed)"""
        is_valid, error = validate_pi_tx_hash(None)
        assert is_valid is True
        assert error == ""

    def test_tx_hash_empty_string(self):
        """Test empty transaction hash"""
        is_valid, error = validate_pi_tx_hash("")
        assert is_valid is True
        assert error == ""

    def test_tx_hash_wrong_length(self):
        """Test transaction hash with wrong length"""
        is_valid, error = validate_pi_tx_hash("a" * 32)
        assert is_valid is False
        assert "64" in error

    def test_tx_hash_invalid_chars(self):
        """Test transaction hash with invalid characters"""
        is_valid, error = validate_pi_tx_hash("z" * 64)
        assert is_valid is False
        assert "十六進制" in error


class TestContentFilter:
    """Tests for content filter"""

    def test_valid_content(self):
        """Test valid content"""
        content = "這是一個正常的詐騙描述，該地址假冒官方進行詐騙，請大家小心"
        result = filter_sensitive_content(content)
        assert result["valid"] is True
        assert len(result["warnings"]) == 0

    def test_empty_content(self):
        """Test empty content"""
        result = filter_sensitive_content("")
        assert result["valid"] is False
        assert any("不能為空" in w for w in result["warnings"])

    def test_content_too_short(self):
        """Test content that is too short"""
        result = filter_sensitive_content("太短了")
        assert result["valid"] is False
        assert any("過短" in w for w in result["warnings"])

    def test_content_too_long(self):
        """Test content that is too long"""
        long_content = "a" * 2001
        result = filter_sensitive_content(long_content)
        assert result["valid"] is False
        assert any("過長" in w for w in result["warnings"])

    def test_content_with_email(self):
        """Test content containing email address"""
        result = filter_sensitive_content("這是詐騙請聯絡我 scam@example.com " + "x" * 50)
        assert result["valid"] is False
        assert any("郵件" in w for w in result["warnings"])

    def test_content_with_phone(self):
        """Test content containing phone number"""
        result = filter_sensitive_content("這是詐騙電話 0912345678 " + "x" * 50)
        assert result["valid"] is False
        assert any("電話" in w for w in result["warnings"])

    def test_content_with_url(self):
        """Test content containing non-official URL"""
        result = filter_sensitive_content("這是詐騙請訪問 https://scam.com " + "x" * 50)
        assert result["valid"] is False
        assert any("網址" in w for w in result["warnings"])

    def test_content_with_official_url(self):
        """Test content containing official Pi Network URL"""
        content = "請到 minepi.com 查看更多 " + "x" * 50
        result = filter_sensitive_content(content)
        # Official URLs should not trigger warning
        assert result["valid"] is True

    def test_content_with_sensitive_words(self):
        """Test content containing sensitive words"""
        result = filter_sensitive_content("這是詐騙請加我微信詳談 " + "x" * 50)
        assert result["valid"] is False
        assert any("敏感詞" in w or "微信" in w for w in result["warnings"])

    def test_sanitize_description(self):
        """Test description sanitization"""
        dirty = "  這是   多餘空白\n\n的描述  "
        clean = sanitize_description(dirty)
        assert clean == "這是 多餘空白 的描述"

    def test_sanitize_empty(self):
        """Test sanitizing empty content"""
        clean = sanitize_description("")
        assert clean == ""

    def test_sanitize_none(self):
        """Test sanitizing None"""
        clean = sanitize_description(None)
        assert clean == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
