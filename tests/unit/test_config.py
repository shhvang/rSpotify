"""
Unit tests for configuration management.
"""

import pytest
from unittest.mock import patch
import os
import tempfile
from pathlib import Path

from rspotify_bot.config import Config, validate_environment


class TestConfig:
    """Test configuration class functionality."""

    def test_config_initialization(self):
        """Test that config initializes with expected defaults."""
        config = Config()
        assert config.ENVIRONMENT == "development"
        assert config.DEBUG is False  # Default from env var parsing
        assert config.LOG_LEVEL == "INFO"
        assert config.FLASK_HOST == "0.0.0.0"
        assert config.FLASK_PORT == 8080

    @patch.dict(
        os.environ, {"TELEGRAM_BOT_TOKEN": "test_token", "MONGODB_URI": "test_uri"}
    )
    def test_validate_required_vars_success(self):
        """Test validation passes with required variables."""
        config = Config()
        assert config.validate_required_vars() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_required_vars_failure(self):
        """Test validation fails without required variables."""
        config = Config()
        assert config.validate_required_vars() is False

    @patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"})
    def test_get_log_level(self):
        """Test log level conversion."""
        import logging

        config = Config()
        assert config.get_log_level() == logging.DEBUG

    @patch.dict(os.environ, {"ENVIRONMENT": "production"})
    def test_is_production(self):
        """Test production environment detection."""
        config = Config()
        assert config.is_production() is True
        assert config.is_development() is False

    @patch.dict(os.environ, {"ENVIRONMENT": "development"})
    def test_is_development(self):
        """Test development environment detection."""
        config = Config()
        assert config.is_development() is True
        assert config.is_production() is False


class TestEnvironmentValidation:
    """Test environment validation functions."""

    @patch.dict(
        os.environ, {"TELEGRAM_BOT_TOKEN": "test_token", "MONGODB_URI": "test_uri"}
    )
    def test_validate_environment_success(self):
        """Test successful environment validation."""
        assert validate_environment() is True

    @patch.dict(os.environ, {}, clear=True)
    def test_validate_environment_failure(self):
        """Test failed environment validation."""
        assert validate_environment() is False
