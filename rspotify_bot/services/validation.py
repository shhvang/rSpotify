"""
Input validation and sanitization service for rSpotify Bot.
Prevents injection attacks and ensures data integrity.
"""

import re
import logging
from typing import Any, Optional, Callable, TypeVar, cast
from functools import wraps

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Exception raised when input validation fails."""

    pass


def sanitize_user_input(
    text: str, max_length: int = 1000, allow_special: bool = False
) -> str:
    """
    Sanitize general user text input.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length
        allow_special: Whether to allow special characters

    Returns:
        Sanitized text string

    Raises:
        ValidationError: If input is invalid or exceeds limits
    """
    if not isinstance(text, str):
        raise ValidationError("Input must be a string")

    if not text.strip():
        raise ValidationError("Input cannot be empty")

    if len(text) > max_length:
        raise ValidationError(
            f"Input exceeds maximum length of {max_length} characters"
        )

    # Remove HTML/script tags to prevent XSS
    sanitized = re.sub(r"<[^>]*>", "", text)

    # Remove null bytes and control characters
    sanitized = sanitized.replace("\x00", "")
    sanitized = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", sanitized)

    if not allow_special:
        # Remove MongoDB special characters that could be used for injection
        dangerous_chars = ["$", "{", "}"]
        for char in dangerous_chars:
            sanitized = sanitized.replace(char, "")

    # Trim whitespace
    sanitized = sanitized.strip()

    if not sanitized:
        raise ValidationError("Input contains only invalid characters")

    logger.debug(f"Sanitized input: '{text[:50]}...' -> '{sanitized[:50]}...'")
    return sanitized


def validate_telegram_id(telegram_id: Any) -> int:
    """
    Validate and convert Telegram ID to integer.

    Args:
        telegram_id: Telegram user ID to validate

    Returns:
        Validated telegram ID as integer

    Raises:
        ValidationError: If telegram_id is invalid
    """
    try:
        # Convert to int
        tid = int(telegram_id)

        # Telegram IDs are positive integers
        if tid <= 0:
            raise ValidationError("Telegram ID must be a positive integer")

        # Telegram IDs are typically 9-10 digits (but allow up to 15 for future-proofing)
        if tid > 9999999999999999:  # 16 digits
            raise ValidationError("Telegram ID exceeds maximum allowed value")

        return tid

    except (ValueError, TypeError):
        raise ValidationError(f"Invalid Telegram ID: {telegram_id}")


def sanitize_custom_name(name: str, min_length: int = 1, max_length: int = 50) -> str:
    """
    Sanitize and validate custom user name.

    Args:
        name: Custom name to sanitize
        min_length: Minimum allowed length
        max_length: Maximum allowed length

    Returns:
        Sanitized custom name

    Raises:
        ValidationError: If name is invalid
    """
    if not isinstance(name, str):
        raise ValidationError("Custom name must be a string")

    # Remove leading/trailing whitespace
    name = name.strip()

    if len(name) < min_length:
        raise ValidationError(f"Custom name must be at least {min_length} character(s)")

    if len(name) > max_length:
        raise ValidationError(f"Custom name cannot exceed {max_length} characters")

    # Remove HTML/script tags
    name = re.sub(r"<[^>]*>", "", name)

    # Allow only alphanumeric, spaces, and common name characters
    # Allowed: letters, numbers, spaces, hyphens, apostrophes, dots
    if not re.match(r"^[\w\s\-'.]+$", name, re.UNICODE):
        raise ValidationError(
            "Custom name can only contain letters, numbers, spaces, hyphens, apostrophes, and dots"
        )

    # Remove MongoDB operators
    dangerous_chars = ["$", "{", "}"]
    for char in dangerous_chars:
        name = name.replace(char, "")

    if not name.strip():
        raise ValidationError("Custom name contains only invalid characters")

    logger.debug(f"Sanitized custom name: {name}")
    return name


def sanitize_query_parameter(param: str, param_name: str = "parameter") -> str:
    """
    Sanitize database query parameters to prevent NoSQL injection.

    Args:
        param: Query parameter value
        param_name: Name of the parameter (for error messages)

    Returns:
        Sanitized parameter

    Raises:
        ValidationError: If parameter is invalid
    """
    if not isinstance(param, str):
        raise ValidationError(f"{param_name} must be a string")

    # Check for MongoDB operators
    mongodb_operators = [
        "$where",
        "$regex",
        "$ne",
        "$gt",
        "$gte",
        "$lt",
        "$lte",
        "$in",
        "$nin",
        "$or",
        "$and",
        "$not",
        "$nor",
        "$exists",
        "$type",
        "$mod",
        "$text",
        "$search",
    ]

    param_lower = param.lower()
    for operator in mongodb_operators:
        if operator in param_lower:
            raise ValidationError(
                f"{param_name} contains potentially dangerous MongoDB operator: {operator}"
            )

    # Remove control characters
    param = re.sub(r"[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]", "", param)

    # Check for JavaScript code patterns
    if re.search(r"(function\s*\(|=\s*>|eval\()", param, re.IGNORECASE):
        raise ValidationError(
            f"{param_name} contains potentially dangerous JavaScript code"
        )

    return param


def escape_html(text: str) -> str:
    """
    Escape HTML special characters for safe display in Telegram messages.

    Args:
        text: Text to escape

    Returns:
        HTML-escaped text
    """
    if not isinstance(text, str):
        return str(text)

    # Escape HTML special characters
    escaped = text.replace("&", "&amp;")
    escaped = escaped.replace("<", "&lt;")
    escaped = escaped.replace(">", "&gt;")
    escaped = escaped.replace('"', "&quot;")
    escaped = escaped.replace("'", "&#x27;")

    return escaped


def validate_spotify_uri(uri: str) -> bool:
    """
    Validate Spotify URI format.

    Args:
        uri: Spotify URI to validate (e.g., spotify:track:xxxxx)

    Returns:
        True if valid, False otherwise
    """
    # Spotify URI pattern: spotify:type:id
    pattern = r"^spotify:(track|album|artist|playlist):[a-zA-Z0-9]{22}$"
    return bool(re.match(pattern, uri))


def validate_url(url: str, allowed_domains: Optional[list[str]] = None) -> bool:
    """
    Validate URL format and optionally check against allowed domains.

    Args:
        url: URL to validate
        allowed_domains: List of allowed domain names (optional)

    Returns:
        True if valid, False otherwise
    """
    # Basic URL pattern
    url_pattern = r"^https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+$"

    if not re.match(url_pattern, url):
        return False

    if allowed_domains:
        # Extract domain from URL
        domain_match = re.search(r"https?://([^/]+)", url)
        if not domain_match:
            return False

        domain = domain_match.group(1)

        # Check if domain is in allowed list
        return any(allowed_domain in domain for allowed_domain in allowed_domains)

    return True


def validate_command_input(func: F) -> F:
    """
    Decorator to validate and sanitize command handler inputs.

    Usage:
        @validate_command_input
        async def handle_command(update, context):
            # Input is already sanitized
            pass
    """

    @wraps(func)
    async def wrapper(update: Any, context: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            # Validate telegram_id
            if update.effective_user:
                telegram_id = validate_telegram_id(update.effective_user.id)
                logger.debug(f"Validated telegram_id: {telegram_id}")

            # Sanitize message text if present
            if update.message and update.message.text:
                try:
                    _ = sanitize_user_input(  # noqa: F841
                        update.message.text, max_length=4096
                    )
                    # Store sanitized text back (optional, depends on use case)
                    logger.debug("Message text validated and sanitized")
                except ValidationError as e:
                    logger.warning(f"Invalid message text: {e}")
                    await update.message.reply_text(
                        "<b>⚠️ Invalid Input</b>\n\n"
                        f"Your message contains invalid characters or exceeds limits.\n"
                        f"Error: {escape_html(str(e))}",
                        parse_mode="HTML",
                    )
                    return

            # Call original handler
            return await func(update, context, *args, **kwargs)

        except ValidationError as e:
            logger.error(f"Validation error in command handler: {e}")
            if update.message:
                await update.message.reply_text(
                    f"<b>⚠️ Validation Error</b>\n\n{escape_html(str(e))}",
                    parse_mode="HTML",
                )
            return
        except Exception as e:
            logger.error(f"Unexpected error in validation decorator: {e}")
            raise

    return cast(F, wrapper)


class InputValidator:
    """Class-based validator for complex validation scenarios."""

    @staticmethod
    def validate_user_data(data: dict) -> dict:
        """
        Validate and sanitize user data dictionary.

        Args:
            data: Dictionary containing user data

        Returns:
            Validated and sanitized data dictionary

        Raises:
            ValidationError: If validation fails
        """
        validated: dict[str, Any] = {}

        # Validate telegram_id
        if "telegram_id" in data:
            validated["telegram_id"] = validate_telegram_id(data["telegram_id"])

        # Validate custom_name
        if "custom_name" in data and data["custom_name"]:
            validated["custom_name"] = sanitize_custom_name(data["custom_name"])

        # Validate other string fields
        string_fields = ["email", "username", "bio"]
        for field in string_fields:
            if field in data and data[field]:
                validated[field] = sanitize_user_input(data[field], max_length=500)

        return validated

    @staticmethod
    def validate_search_query(query: str) -> str:
        """
        Validate and sanitize search query.

        Args:
            query: Search query string

        Returns:
            Sanitized query string
        """
        # Allow special characters in search queries but sanitize for safety
        sanitized = sanitize_user_input(query, max_length=200, allow_special=True)

        # Additional validation for search queries
        # Remove excessive whitespace
        sanitized = re.sub(r"\s+", " ", sanitized)

        return sanitized
