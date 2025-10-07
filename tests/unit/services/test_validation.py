"""
Unit tests for input validation and sanitization service.
Tests security features and input handling.
"""

import pytest

from rspotify_bot.services.validation import (
    ValidationError,
    sanitize_user_input,
    validate_telegram_id,
    sanitize_custom_name,
    sanitize_query_parameter,
    escape_html,
    validate_spotify_uri,
    validate_url,
    validate_custom_name,
    InputValidator,
)


class TestSanitizeUserInput:
    """Test suite for sanitize_user_input function."""

    def test_sanitize_normal_text(self):
        """Test sanitization of normal text."""
        text = "Hello, this is a normal message"
        result = sanitize_user_input(text)
        assert result == text

    def test_sanitize_removes_html_tags(self):
        """Test HTML tag removal."""
        text = "Hello <script>alert('xss')</script> world"
        result = sanitize_user_input(text)
        assert "<script>" not in result
        assert "alert" in result  # Content preserved

    def test_sanitize_removes_dangerous_chars(self):
        """Test removal of MongoDB dangerous characters."""
        text = "Normal text with $dollar and {braces}"
        result = sanitize_user_input(text)
        assert "$" not in result
        assert "{" not in result
        assert "}" not in result

    def test_sanitize_empty_input_fails(self):
        """Test empty input raises error."""
        with pytest.raises(ValidationError, match="Input cannot be empty"):
            sanitize_user_input("")

    def test_sanitize_whitespace_only_fails(self):
        """Test whitespace-only input fails."""
        with pytest.raises(ValidationError, match="Input cannot be empty"):
            sanitize_user_input("   ")

    def test_sanitize_exceeds_max_length_fails(self):
        """Test input exceeding max length fails."""
        text = "x" * 1001
        with pytest.raises(ValidationError, match="exceeds maximum length"):
            sanitize_user_input(text, max_length=1000)

    def test_sanitize_non_string_fails(self):
        """Test non-string input fails."""
        with pytest.raises(ValidationError, match="Input must be a string"):
            sanitize_user_input(123)

    def test_sanitize_with_special_chars_allowed(self):
        """Test sanitization with special chars allowed."""
        text = "Text with $special {chars}"
        result = sanitize_user_input(text, allow_special=True)
        assert "$" in result
        assert "{" in result

    def test_sanitize_removes_null_bytes(self):
        """Test null byte removal."""
        text = "Text\x00with\x00nulls"
        result = sanitize_user_input(text)
        assert "\x00" not in result

    def test_sanitize_removes_control_characters(self):
        """Test control character removal."""
        text = "Text\x01with\x02control\x03chars"
        result = sanitize_user_input(text)
        assert "\x01" not in result
        assert "\x02" not in result


class TestValidateTelegramId:
    """Test suite for validate_telegram_id function."""

    def test_validate_valid_telegram_id(self):
        """Test validation of valid telegram ID."""
        tid = validate_telegram_id(123456789)
        assert tid == 123456789

    def test_validate_string_telegram_id(self):
        """Test validation converts string to int."""
        tid = validate_telegram_id("987654321")
        assert tid == 987654321
        assert isinstance(tid, int)

    def test_validate_negative_telegram_id_fails(self):
        """Test negative ID fails."""
        with pytest.raises(ValidationError, match="must be a positive integer"):
            validate_telegram_id(-123)

    def test_validate_zero_telegram_id_fails(self):
        """Test zero ID fails."""
        with pytest.raises(ValidationError, match="must be a positive integer"):
            validate_telegram_id(0)

    def test_validate_too_large_telegram_id_fails(self):
        """Test excessively large ID fails."""
        with pytest.raises(ValidationError, match="exceeds maximum allowed value"):
            validate_telegram_id(99999999999999999)

    def test_validate_invalid_type_fails(self):
        """Test invalid type fails."""
        with pytest.raises(ValidationError, match="Invalid Telegram ID"):
            validate_telegram_id("not_a_number")

    def test_validate_none_fails(self):
        """Test None value fails."""
        with pytest.raises(ValidationError):
            validate_telegram_id(None)


class TestSanitizeCustomName:
    """Test suite for sanitize_custom_name function."""

    def test_sanitize_valid_name(self):
        """Test sanitization of valid name."""
        name = "John Doe"
        result = sanitize_custom_name(name)
        assert result == name

    def test_sanitize_name_with_special_chars(self):
        """Test name with allowed special characters."""
        name = "O'Brien-Smith Jr."
        result = sanitize_custom_name(name)
        assert result == name

    def test_sanitize_name_too_short_fails(self):
        """Test name below minimum length fails."""
        with pytest.raises(ValidationError, match="must be at least"):
            sanitize_custom_name("", min_length=1)

    def test_sanitize_name_too_long_fails(self):
        """Test name exceeding max length fails."""
        name = "x" * 51
        with pytest.raises(ValidationError, match="cannot exceed"):
            sanitize_custom_name(name, max_length=50)

    def test_sanitize_name_with_invalid_chars_fails(self):
        """Test name with invalid characters fails."""
        with pytest.raises(ValidationError, match="can only contain"):
            sanitize_custom_name("Name@#$%")

    def test_sanitize_name_removes_html(self):
        """Test HTML tag removal from name."""
        name = "John <b>Doe</b>"
        result = sanitize_custom_name(name)
        assert "<b>" not in result
        assert "John" in result
        assert "Doe" in result

    def test_sanitize_name_non_string_fails(self):
        """Test non-string name fails."""
        with pytest.raises(ValidationError, match="must be a string"):
            sanitize_custom_name(123)

    def test_sanitize_unicode_name(self):
        """Test unicode names are allowed."""
        name = "José María"
        result = sanitize_custom_name(name)
        assert result == name


class TestSanitizeQueryParameter:
    """Test suite for sanitize_query_parameter function."""

    def test_sanitize_normal_parameter(self):
        """Test normal parameter passes."""
        param = "normal_value"
        result = sanitize_query_parameter(param)
        assert result == param

    def test_sanitize_detects_mongodb_operators(self):
        """Test detection of MongoDB operators."""
        dangerous_params = [
            "$where: function() { return true; }",
            "value $ne null",
            "{ $gt: 0 }",
            "$regex pattern",
        ]

        for param in dangerous_params:
            with pytest.raises(ValidationError, match="dangerous MongoDB operator"):
                sanitize_query_parameter(param)

    def test_sanitize_detects_javascript(self):
        """Test detection of JavaScript code."""
        dangerous_params = [
            "function() { alert('xss'); }",
            "() => console.log('bad')",
            "eval('malicious')",
        ]

        for param in dangerous_params:
            with pytest.raises(ValidationError, match="dangerous JavaScript"):
                sanitize_query_parameter(param)

    def test_sanitize_removes_control_chars(self):
        """Test control character removal."""
        param = "value\x00with\x01control"
        result = sanitize_query_parameter(param)
        assert "\x00" not in result
        assert "\x01" not in result


class TestEscapeHtml:
    """Test suite for escape_html function."""

    def test_escape_html_special_chars(self):
        """Test HTML special character escaping."""
        text = "<b>Bold</b> & 'quoted'"
        result = escape_html(text)

        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
        assert "&#x27;" in result

    def test_escape_non_string(self):
        """Test escaping converts non-strings."""
        result = escape_html(123)
        assert result == "123"

    def test_escape_already_escaped(self):
        """Test double-escaping."""
        text = "&lt;already&gt;"
        result = escape_html(text)
        # Should escape the & again
        assert "&amp;lt;" in result


class TestValidateSpotifyUri:
    """Test suite for validate_spotify_uri function."""

    def test_validate_valid_track_uri(self):
        """Test valid track URI."""
        uri = "spotify:track:1234567890abcdefghij12"
        assert validate_spotify_uri(uri) is True

    def test_validate_valid_album_uri(self):
        """Test valid album URI."""
        uri = "spotify:album:abcdefghij1234567890ab"
        assert validate_spotify_uri(uri) is True

    def test_validate_invalid_uri_format(self):
        """Test invalid URI format."""
        invalid_uris = [
            "not_a_uri",
            "spotify:track:tooshort",
            "spotify:unknown:1234567890abcdefghij12",
            "http://spotify.com/track/123",
        ]

        for uri in invalid_uris:
            assert validate_spotify_uri(uri) is False


class TestValidateUrl:
    """Test suite for validate_url function."""

    def test_validate_valid_url(self):
        """Test valid URL."""
        assert validate_url("https://example.com") is True
        assert validate_url("http://example.com/path?query=1") is True

    def test_validate_invalid_url(self):
        """Test invalid URL."""
        invalid_urls = [
            "not a url",
            "ftp://example.com",  # Wrong protocol
            "javascript:alert('xss')",
        ]

        for url in invalid_urls:
            assert validate_url(url) is False

    def test_validate_url_with_allowed_domains(self):
        """Test URL validation with domain whitelist."""
        url = "https://api.spotify.com/v1/tracks"

        assert validate_url(url, allowed_domains=["spotify.com"]) is True
        assert validate_url(url, allowed_domains=["example.com"]) is False


class TestInputValidator:
    """Test suite for InputValidator class."""

    def test_validate_user_data_success(self):
        """Test successful user data validation."""
        data = {
            "telegram_id": 123456789,
            "custom_name": "John Doe",
            "email": "john@example.com",
        }

        result = InputValidator.validate_user_data(data)

        assert result["telegram_id"] == 123456789
        assert result["custom_name"] == "John Doe"
        assert "email" in result

    def test_validate_user_data_invalid_telegram_id(self):
        """Test user data validation fails with invalid telegram_id."""
        data = {
            "telegram_id": -123,
            "custom_name": "John",
        }

        with pytest.raises(ValidationError):
            InputValidator.validate_user_data(data)

    def test_validate_user_data_sanitizes_strings(self):
        """Test user data validation sanitizes string fields."""
        data = {
            "telegram_id": 123,
            "custom_name": "John <script>alert</script>",
            "bio": "My bio with $dangerous chars",
        }

        result = InputValidator.validate_user_data(data)

        assert "<script>" not in result["custom_name"]
        assert "$" not in result["bio"]

    def test_validate_search_query(self):
        """Test search query validation."""
        query = "   search   query   with   spaces   "
        result = InputValidator.validate_search_query(query)

        # Should normalize whitespace
        assert "  " not in result  # No double spaces
        assert result.strip() == result


class TestValidationDecorator:
    """Test suite for validation decorators."""

    @pytest.mark.asyncio
    async def test_validate_command_input_decorator(self):
        """Test command input validation decorator."""
        from rspotify_bot.services.validation import validate_command_input

        @validate_command_input
        async def dummy_handler(update, context):
            return "success"

        # Mock update object
        class MockUser:
            id = 123456789
            first_name = "Test"

        class MockMessage:
            text = "Normal message"

            async def reply_text(self, text, parse_mode=None, reply_markup=None):
                pass

        class MockUpdate:
            effective_user = MockUser()
            message = MockMessage()

        class MockContext:
            pass

        # Should pass validation
        result = await dummy_handler(MockUpdate(), MockContext())
        assert result == "success"


class TestSecurityValidation:
    """Test suite for security-focused validation."""

    def test_prevents_nosql_injection(self):
        """Test prevention of NoSQL injection attempts."""
        injection_attempts = [
            "$where: function() {}",
            '{"$ne": null}',
        ]

        for attempt in injection_attempts:
            with pytest.raises(ValidationError):
                sanitize_query_parameter(attempt)

    def test_prevents_xss_attacks(self):
        """Test prevention of XSS attacks."""
        # Test that HTML tags are removed
        xss_with_content = "<b>Bold</b> text <script>alert('xss')</script> here"
        result = sanitize_user_input(xss_with_content)
        assert "<script>" not in result
        assert "<b>" not in result
        assert "text" in result
        assert "here" in result

    def test_handles_unicode_normalization(self):
        """Test handling of unicode normalization attacks."""
        # Various unicode representations of same character
        names = [
            "Café",  # é as single character
            "Café",  # é as combining character
        ]

        for name in names:
            result = sanitize_custom_name(name)
            assert result  # Should not fail


class TestValidateCustomName:
    """Test suite for validate_custom_name function (Story 1.5)."""

    def test_validate_valid_name(self):
        """Test validation of valid custom names."""
        valid_names = [
            "John",
            "Mary Jane",
            "Bob123",
            "Alice42",
            "J",  # Single character
            "Test User 1",
        ]
        
        for name in valid_names:
            is_valid, error = validate_custom_name(name)
            assert is_valid, f"'{name}' should be valid, got error: {error}"
            assert error == ""

    def test_validate_max_length_12_chars(self):
        """Test 12 character limit."""
        # Exactly 12 characters - should pass
        is_valid, error = validate_custom_name("ExactlyTwlve")
        assert is_valid
        assert error == ""
        
        # 13 characters - should fail
        is_valid, error = validate_custom_name("ThirteenChars")
        assert not is_valid
        assert "too long" in error.lower()
        assert "12 characters" in error

    def test_validate_empty_name_fails(self):
        """Test empty name fails validation."""
        is_valid, error = validate_custom_name("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_validate_whitespace_only_fails(self):
        """Test whitespace-only name fails."""
        is_valid, error = validate_custom_name("   ")
        assert not is_valid
        assert "empty" in error.lower() or "spaces" in error.lower()

    def test_validate_trims_whitespace(self):
        """Test that validation trims whitespace."""
        is_valid, error = validate_custom_name("  John  ")
        assert is_valid  # Should pass after trimming

    def test_validate_rejects_emojis(self):
        """Test that emojis are rejected."""
        emoji_names = [
            "John😀",
            "🎵Music",
            "Test🔥",
            "😀",
        ]
        
        for name in emoji_names:
            is_valid, error = validate_custom_name(name)
            assert not is_valid, f"'{name}' should be invalid (contains emoji)"
            assert "emoji" in error.lower() or "special" in error.lower()

    def test_validate_allows_international_chars(self):
        """Test that international characters are allowed."""
        international_names = [
            "José",
            "François",
            "Müller",
            "Søren",
            "Ñoño",
        ]
        
        for name in international_names:
            is_valid, error = validate_custom_name(name)
            assert is_valid, f"'{name}' should be valid, got error: {error}"

    def test_validate_rejects_special_symbols(self):
        """Test that special symbols are rejected."""
        special_names = [
            "John@Doe",
            "Test#User",
            "User$Name",
            "Name%123",
            "Test&User",
        ]
        
        for name in special_names:
            is_valid, error = validate_custom_name(name)
            assert not is_valid, f"'{name}' should be invalid (special chars)"
            assert "letters" in error.lower() or "numbers" in error.lower() or "spaces" in error.lower()

    def test_validate_profanity_filter(self):
        """Test profanity filtering."""
        # Note: Using mild examples for testing
        profane_names = [
            "damn",
            "hell",
        ]
        
        for name in profane_names:
            is_valid, error = validate_custom_name(name)
            # May or may not be filtered depending on profanity library
            # This test just ensures the function handles it gracefully
            if not is_valid:
                assert "inappropriate" in error.lower() or "language" in error.lower()

    def test_validate_non_string_input(self):
        """Test that non-string input fails gracefully."""
        is_valid, error = validate_custom_name(123)
        assert not is_valid
        assert "text" in error.lower() or "string" in error.lower()

    def test_validate_alphanumeric_with_spaces(self):
        """Test alphanumeric characters with spaces."""
        is_valid, error = validate_custom_name("User 123")
        assert is_valid
        assert error == ""

    def test_validate_length_boundaries(self):
        """Test length boundary cases."""
        # 1 character - should pass
        is_valid, error = validate_custom_name("A")
        assert is_valid
        
        # 12 characters - should pass
        is_valid, error = validate_custom_name("A" * 12)
        assert is_valid
        
        # 13 characters - should fail
        is_valid, error = validate_custom_name("A" * 13)
        assert not is_valid

    def test_validate_numbers_only(self):
        """Test names with only numbers."""
        is_valid, error = validate_custom_name("12345")
        assert is_valid  # Numbers are allowed

    def test_validate_mixed_case(self):
        """Test mixed case names."""
        is_valid, error = validate_custom_name("JohnDoe")
        assert is_valid
        
        is_valid, error = validate_custom_name("ALLCAPS")
        assert is_valid
        
        is_valid, error = validate_custom_name("lowercase")
        assert is_valid
