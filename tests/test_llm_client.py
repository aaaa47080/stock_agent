"""
Tests for LLM client utilities
"""
import pytest
import json

from utils.llm_client import (
    extract_json_from_response,
    supports_json_mode,
    LLMClientFactory
)


class TestExtractJsonFromResponse:
    """Tests for extract_json_from_response function"""

    def test_valid_json_object(self):
        """Test extracting valid JSON object"""
        response = '{"name": "test", "value": 123}'
        result = extract_json_from_response(response)
        assert result == {"name": "test", "value": 123}

    def test_valid_json_array(self):
        """Test extracting valid JSON array"""
        response = '[1, 2, 3]'
        result = extract_json_from_response(response)
        assert result == [1, 2, 3]

    def test_json_in_code_block(self):
        """Test extracting JSON from markdown code block"""
        response = '''```json
{"status": "ok"}
```'''
        result = extract_json_from_response(response)
        assert result == {"status": "ok"}

    def test_json_in_plain_code_block(self):
        """Test extracting JSON from plain code block"""
        response = '''```
{"data": "value"}
```'''
        result = extract_json_from_response(response)
        assert result == {"data": "value"}

    def test_json_with_surrounding_text(self):
        """Test extracting JSON with text around it"""
        response = 'Here is the result: {"key": "value"} and some more text'
        result = extract_json_from_response(response)
        assert result == {"key": "value"}

    def test_nested_json(self):
        """Test extracting nested JSON object"""
        response = '{"outer": {"inner": "value"}}'
        result = extract_json_from_response(response)
        assert result == {"outer": {"inner": "value"}}

    def test_complex_json(self):
        """Test extracting complex JSON with arrays and nested objects"""
        response = '''{
            "items": [
                {"id": 1, "name": "first"},
                {"id": 2, "name": "second"}
            ],
            "count": 2
        }'''
        result = extract_json_from_response(response)
        assert result["count"] == 2
        assert len(result["items"]) == 2

    def test_empty_response_raises_error(self):
        """Test that empty response raises ValueError"""
        with pytest.raises(ValueError, match="Empty response"):
            extract_json_from_response("")

    def test_whitespace_only_response_raises_error(self):
        """Test that whitespace-only response raises ValueError"""
        with pytest.raises(ValueError, match="Empty response"):
            extract_json_from_response("   \n\t  ")

    def test_invalid_json_raises_error(self):
        """Test that invalid JSON raises ValueError"""
        with pytest.raises(ValueError):
            extract_json_from_response("this is not json at all")

    def test_incomplete_json_raises_error(self):
        """Test that incomplete JSON raises ValueError"""
        with pytest.raises(ValueError):
            extract_json_from_response('{"key": "value"')

    def test_json_with_special_characters(self):
        """Test JSON with special characters"""
        response = '{"message": "Hello\\nWorld!", "path": "C:\\\\Users"}'
        result = extract_json_from_response(response)
        assert result["message"] == "Hello\nWorld!"

    def test_json_with_unicode(self):
        """Test JSON with unicode characters"""
        response = '{"chinese": "中文測試", "emoji": "🚀"}'
        result = extract_json_from_response(response)
        assert result["chinese"] == "中文測試"

    def test_json_array_wrapped_in_object(self):
        """Test extracting JSON array wrapped in object from response"""
        response = 'The results are: {"items": [1, 2, 3, 4, 5]} end.'
        result = extract_json_from_response(response)
        assert result == {"items": [1, 2, 3, 4, 5]}

    def test_json_boolean_and_null(self):
        """Test JSON with boolean and null values"""
        response = '{"active": true, "deleted": false, "data": null}'
        result = extract_json_from_response(response)
        assert result["active"] is True
        assert result["deleted"] is False
        assert result["data"] is None


class TestSupportsJsonMode:
    """Tests for supports_json_mode function"""

    def test_gpt4_supports_json(self):
        """Test that GPT-4 models support JSON mode"""
        assert supports_json_mode("gpt-4") is True
        assert supports_json_mode("gpt-4o") is True
        assert supports_json_mode("gpt-5.2-pro") is True

    def test_gpt35_supports_json(self):
        """Test that GPT-3.5 models support JSON mode"""
        assert supports_json_mode("gpt-3.5-turbo") is True

    def test_llama_does_not_support_json(self):
        """Test that LLaMA models do not support JSON mode"""
        assert supports_json_mode("llama-2-70b") is False
        assert supports_json_mode("llama3") is False
        assert supports_json_mode("LLaMA-2") is False

    def test_gemma_does_not_support_json(self):
        """Test that Gemma models do not support JSON mode"""
        assert supports_json_mode("gemma-7b") is False
        assert supports_json_mode("GEMMA-2") is False

    def test_case_insensitive_check(self):
        """Test that model name check is case insensitive"""
        assert supports_json_mode("LLAMA") is False
        assert supports_json_mode("Gemma") is False
        assert supports_json_mode("GPT-4") is True

    def test_unknown_model_defaults_to_true(self):
        """Test that unknown models default to supporting JSON"""
        assert supports_json_mode("unknown-model") is True
        assert supports_json_mode("custom-llm") is True


class TestLLMClientFactoryGetModelInfo:
    """Tests for LLMClientFactory.get_model_info"""

    def test_get_model_info_basic(self):
        """Test basic model info generation"""
        config = {"provider": "openai", "model": "gpt-4"}
        result = LLMClientFactory.get_model_info(config)
        assert result == "gpt-4 (openai)"

    def test_get_model_info_missing_provider(self):
        """Test model info with missing provider defaults to openai"""
        config = {"model": "gpt-4o"}
        result = LLMClientFactory.get_model_info(config)
        assert result == "gpt-4o (openai)"

    def test_get_model_info_missing_model(self):
        """Test model info with missing model shows unknown"""
        config = {"provider": "google_gemini"}
        result = LLMClientFactory.get_model_info(config)
        assert result == "unknown (google_gemini)"

    def test_get_model_info_empty_config(self):
        """Test model info with empty config"""
        config = {}
        result = LLMClientFactory.get_model_info(config)
        assert result == "unknown (openai)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
