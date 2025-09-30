"""
Configuration management for rSpotify Bot.
Loads environment variables and provides configuration validation.
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


class Config:
    """Configuration class for environment variable management."""

    # Telegram Configuration
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    OWNER_TELEGRAM_ID: str = os.getenv("OWNER_TELEGRAM_ID", "")

    # Spotify Configuration
    SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
    SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    SPOTIFY_REDIRECT_URI: str = os.getenv("SPOTIFY_REDIRECT_URI", "")

    # Database Configuration
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "rspotify_bot")

    # Encryption Configuration
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # DuckDNS Configuration
    DUCKDNS_TOKEN: str = os.getenv("DUCKDNS_TOKEN", "")
    DUCKDNS_DOMAIN: str = os.getenv("DUCKDNS_DOMAIN", "")

    # Web Callback Configuration
    FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("FLASK_PORT", "8080"))
    FLASK_SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "")

    # Environment Configuration
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Deployment Configuration
    SERVER_HOST: str = os.getenv("SERVER_HOST", "")
    SERVER_USER: str = os.getenv("SERVER_USER", "")
    DEPLOY_KEY_PATH: str = os.getenv("DEPLOY_KEY_PATH", "")

    # Optional Configuration
    PASTEBIN_API_KEY: str = os.getenv("PASTEBIN_API_KEY", "")
    PASTEBIN_USER_KEY: str = os.getenv("PASTEBIN_USER_KEY", "")

    # Rate Limiting Configuration
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
    RATE_LIMIT_BURST: int = int(os.getenv("RATE_LIMIT_BURST", "5"))

    # Cache Configuration
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "1800"))

    @classmethod
    def validate_required_vars(cls) -> bool:
        """
        Validate that all required environment variables are set.

        Returns:
            bool: True if all required variables are set, False otherwise.
        """
        required_vars = [
            ("TELEGRAM_BOT_TOKEN", cls.TELEGRAM_BOT_TOKEN),
            ("MONGODB_URI", cls.MONGODB_URI),
            ("ENCRYPTION_KEY", cls.ENCRYPTION_KEY),
        ]

        missing_vars = []
        for var_name, var_value in required_vars:
            if not var_value:
                missing_vars.append(var_name)

        if missing_vars:
            logger.error(
                f"Missing required environment variables: {missing_vars}"
            )
            return False

        return True

    @classmethod
    def validate_optional_vars(cls) -> list[str]:
        """
        Check optional environment variables and return list of missing ones.

        Returns:
            list[str]: List of missing optional variables.
        """
        optional_vars = [
            ("SPOTIFY_CLIENT_ID", cls.SPOTIFY_CLIENT_ID),
            ("SPOTIFY_CLIENT_SECRET", cls.SPOTIFY_CLIENT_SECRET),
            ("DUCKDNS_TOKEN", cls.DUCKDNS_TOKEN),
            ("FLASK_SECRET_KEY", cls.FLASK_SECRET_KEY),
        ]

        missing_vars = []
        for var_name, var_value in optional_vars:
            if not var_value:
                missing_vars.append(var_name)

        if missing_vars:
            logger.warning(f"Missing optional environment variables: {missing_vars}")

        return missing_vars

    @classmethod
    def get_log_level(cls) -> int:
        """
        Convert LOG_LEVEL string to logging level constant.

        Returns:
            int: Logging level constant.
        """
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        return level_map.get(cls.LOG_LEVEL.upper(), logging.INFO)

    @classmethod
    def is_production(cls) -> bool:
        """Check if running in production environment."""
        return cls.ENVIRONMENT.lower() == "production"

    @classmethod
    def is_development(cls) -> bool:
        """Check if running in development environment."""
        return cls.ENVIRONMENT.lower() == "development"


# Global config instance
config = Config()


def setup_logging() -> None:
    """Setup logging configuration based on environment."""
    # Create logs directory FIRST before setting up handlers
    Path("logs").mkdir(exist_ok=True)

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    if config.is_development():
        # More verbose logging in development with UTF-8 encoding
        stream_handler = logging.StreamHandler()
        stream_handler.setStream(sys.stdout)

        logging.basicConfig(
            level=config.get_log_level(),
            format=log_format,
            handlers=[
                stream_handler,
                logging.FileHandler(
                    "logs/rspotify_bot.log", mode="a", encoding="utf-8"
                ),
            ],
        )
    else:
        # Production logging
        logging.basicConfig(
            level=config.get_log_level(),
            format=log_format,
            handlers=[logging.StreamHandler()],
        )


def validate_environment() -> bool:
    """
    Validate the complete environment configuration.

    Returns:
        bool: True if environment is valid for operation.
    """
    logger.info("Validating environment configuration...")
    logger.info(f"Environment: {config.ENVIRONMENT}")
    logger.info(f"Debug mode: {config.DEBUG}")

    # Check required variables
    if not config.validate_required_vars():
        logger.error("Environment validation failed: missing required variables")
        return False

    # Check optional variables
    missing_optional = config.validate_optional_vars()
    if missing_optional:
        logger.warning(
            f"Some optional features may not work due to missing variables: "
            f"{missing_optional}"
        )

    logger.info("Environment validation completed successfully")
    return True
