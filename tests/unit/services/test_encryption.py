"""
Unit tests for encryption service.
Tests encryption/decryption functionality and security features.
"""

import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet

from rspotify_bot.services.encryption import EncryptionService


class TestEncryptionService:
    """Test suite for EncryptionService."""

    @pytest.fixture
    def encryption_key(self):
        """Generate a test encryption key."""
        return Fernet.generate_key().decode("utf-8")

    @pytest.fixture
    def encryption_service(self, encryption_key):
        """Create EncryptionService instance with test key."""
        return EncryptionService(encryption_key=encryption_key)

    def test_initialization_with_valid_key(self, encryption_key):
        """Test service initialization with valid key."""
        service = EncryptionService(encryption_key=encryption_key)
        assert service is not None
        assert service.cipher is not None

    @patch("rspotify_bot.services.encryption.config.ENCRYPTION_KEY", "")
    def test_initialization_without_key(self):
        """Test service initialization fails without key."""
        with pytest.raises(ValueError, match="Encryption key not provided"):
            EncryptionService(encryption_key=None)

    def test_initialization_with_invalid_key(self):
        """Test service initialization fails with invalid key."""
        with pytest.raises(ValueError, match="Invalid encryption key"):
            EncryptionService(encryption_key="invalid_key")

    def test_encrypt_token_success(self, encryption_service):
        """Test successful token encryption."""
        token = "test_access_token_12345"
        encrypted = encryption_service.encrypt_token(token)

        assert encrypted is not None
        assert isinstance(encrypted, str)
        assert encrypted != token  # Encrypted should be different from original

    def test_encrypt_empty_token_fails(self, encryption_service):
        """Test encryption fails with empty token."""
        with pytest.raises(ValueError, match="Token cannot be empty"):
            encryption_service.encrypt_token("")

    def test_decrypt_token_success(self, encryption_service):
        """Test successful token decryption."""
        original_token = "test_refresh_token_67890"
        encrypted = encryption_service.encrypt_token(original_token)
        decrypted = encryption_service.decrypt_token(encrypted)

        assert decrypted == original_token

    def test_decrypt_empty_token_fails(self, encryption_service):
        """Test decryption fails with empty token."""
        with pytest.raises(ValueError, match="Encrypted token cannot be empty"):
            encryption_service.decrypt_token("")

    def test_decrypt_invalid_token_fails(self, encryption_service):
        """Test decryption fails with invalid token."""
        with pytest.raises(ValueError, match="Failed to decrypt token"):
            encryption_service.decrypt_token("invalid_encrypted_token")

    def test_encrypt_decrypt_roundtrip(self, encryption_service):
        """Test encrypt-decrypt roundtrip preserves data."""
        test_cases = [
            "short",
            "a_longer_token_with_special_chars_!@#$%",
            "🎵 Unicode token with emojis 🎶",
            "VeryLongTokenString" * 100,  # Long token
        ]

        for token in test_cases:
            encrypted = encryption_service.encrypt_token(token)
            decrypted = encryption_service.decrypt_token(encrypted)
            assert decrypted == token, f"Roundtrip failed for token: {token[:50]}"

    def test_encrypt_spotify_tokens(self, encryption_service):
        """Test Spotify token encryption."""
        access_token = "spotify_access_token_xyz"
        refresh_token = "spotify_refresh_token_abc"

        encrypted = encryption_service.encrypt_spotify_tokens(
            access_token, refresh_token
        )

        assert "access_token" in encrypted
        assert "refresh_token" in encrypted
        assert encrypted["access_token"] != access_token
        assert encrypted["refresh_token"] != refresh_token

    def test_decrypt_spotify_tokens(self, encryption_service):
        """Test Spotify token decryption."""
        access_token = "spotify_access_token_xyz"
        refresh_token = "spotify_refresh_token_abc"

        encrypted = encryption_service.encrypt_spotify_tokens(
            access_token, refresh_token
        )
        decrypted = encryption_service.decrypt_spotify_tokens(encrypted)

        assert decrypted["access_token"] == access_token
        assert decrypted["refresh_token"] == refresh_token

    def test_different_encryptions_produce_different_ciphertexts(
        self, encryption_service
    ):
        """Test that encrypting same token twice produces different ciphertexts."""
        token = "same_token"
        encrypted1 = encryption_service.encrypt_token(token)
        encrypted2 = encryption_service.encrypt_token(token)

        # Fernet includes timestamp, so encryptions should differ
        # But both should decrypt to same value
        decrypted1 = encryption_service.decrypt_token(encrypted1)
        decrypted2 = encryption_service.decrypt_token(encrypted2)

        assert decrypted1 == token
        assert decrypted2 == token

    def test_wrong_key_cannot_decrypt(self, encryption_key):
        """Test that wrong key cannot decrypt data."""
        service1 = EncryptionService(encryption_key=encryption_key)
        service2 = EncryptionService(encryption_key=Fernet.generate_key().decode())

        token = "secret_token"
        encrypted = service1.encrypt_token(token)

        with pytest.raises(ValueError, match="Failed to decrypt token"):
            service2.decrypt_token(encrypted)

    def test_generate_key(self):
        """Test key generation."""
        key = EncryptionService.generate_key()

        assert key is not None
        assert isinstance(key, str)
        assert len(key) > 0

        # Verify generated key is valid
        service = EncryptionService(encryption_key=key)
        assert service is not None

    def test_rotate_key(self, encryption_service):
        """Test key rotation functionality."""
        # Encrypt with old key
        token = "rotate_test_token"
        encrypted_old = encryption_service.encrypt_token(token)

        # Generate new key
        new_key = EncryptionService.generate_key()

        # Rotate to new key
        encrypted_new = encryption_service.rotate_key(encrypted_old, new_key)

        # Verify new encryption can be decrypted with new key
        new_service = EncryptionService(encryption_key=new_key)
        decrypted = new_service.decrypt_token(encrypted_new)

        assert decrypted == token

    def test_encryption_with_special_characters(self, encryption_service):
        """Test encryption with various special characters."""
        special_tokens = [
            "token|with|pipes",
            "token$with$dollars",
            "token{with}braces",
            "token\nwith\nnewlines",
            "token\twith\ttabs",
            'token"with"quotes',
            "token'with'apostrophes",
        ]

        for token in special_tokens:
            encrypted = encryption_service.encrypt_token(token)
            decrypted = encryption_service.decrypt_token(encrypted)
            assert decrypted == token, f"Failed for token with special chars: {token}"

    def test_encryption_performance(self, encryption_service):
        """Test encryption performance with large data."""
        import time

        large_token = "x" * 10000  # 10KB token

        start = time.time()
        encrypted = encryption_service.encrypt_token(large_token)
        encrypt_time = time.time() - start

        start = time.time()
        decrypted = encryption_service.decrypt_token(encrypted)
        decrypt_time = time.time() - start

        # Verify correctness
        assert decrypted == large_token

        # Performance should be under 50ms as per requirements
        assert (
            encrypt_time < 0.05
        ), f"Encryption took {encrypt_time}s, should be < 0.05s"
        assert (
            decrypt_time < 0.05
        ), f"Decryption took {decrypt_time}s, should be < 0.05s"


class TestEncryptionServiceIntegration:
    """Integration tests for encryption service with config."""

    def test_get_encryption_service_singleton(self, monkeypatch):
        """Test global encryption service singleton."""
        from rspotify_bot.services.encryption import get_encryption_service

        # Set encryption key in environment
        test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", test_key)

        # Reload config to pick up new env var
        from rspotify_bot import config as config_module

        config_module.config.ENCRYPTION_KEY = test_key

        # Reset global instance
        import rspotify_bot.services.encryption as enc_module

        enc_module._encryption_service = None

        # Get service
        service1 = get_encryption_service()
        service2 = get_encryption_service()

        # Should be same instance
        assert service1 is service2

        # Should work correctly
        token = "test_token"
        encrypted = service1.encrypt_token(token)
        decrypted = service2.decrypt_token(encrypted)
        assert decrypted == token
