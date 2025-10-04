"""
Encryption service for rSpotify Bot.
Handles secure encryption and decryption of sensitive data like Spotify OAuth tokens.
"""

import logging
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken

from ..config import config

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service with encryption key.

        Args:
            encryption_key: Base64-encoded Fernet encryption key.
                          If not provided, will use ENCRYPTION_KEY from config.

        Raises:
            ValueError: If encryption key is not provided or invalid.
        """
        key = encryption_key or config.ENCRYPTION_KEY

        if not key:
            raise ValueError(
                "Encryption key not provided. Set ENCRYPTION_KEY environment variable "
                "or pass key to constructor."
            )

        try:
            # Ensure key is bytes
            key_bytes = key.encode() if isinstance(key, str) else key
            self.cipher = Fernet(key_bytes)
            logger.info("Encryption service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize encryption service: {e}")
            raise ValueError(f"Invalid encryption key: {e}")

    def encrypt_token(self, token: str) -> str:
        """
        Encrypt a token string.

        Args:
            token: Plain text token to encrypt

        Returns:
            Encrypted token as base64-encoded string

        Raises:
            ValueError: If token is empty or encryption fails
        """
        if not token:
            raise ValueError("Token cannot be empty")

        try:
            # Convert to bytes and encrypt
            token_bytes = token.encode("utf-8")
            encrypted_bytes = self.cipher.encrypt(token_bytes)

            # Return as base64 string
            encrypted_str = encrypted_bytes.decode("utf-8")
            logger.debug("Token encrypted successfully")
            return encrypted_str

        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            raise ValueError(f"Failed to encrypt token: {e}")

    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt an encrypted token.

        Args:
            encrypted_token: Base64-encoded encrypted token

        Returns:
            Decrypted plain text token

        Raises:
            ValueError: If decryption fails or token is invalid
        """
        if not encrypted_token:
            raise ValueError("Encrypted token cannot be empty")

        try:
            # Convert from base64 string to bytes
            encrypted_bytes = encrypted_token.encode("utf-8")

            # Decrypt
            decrypted_bytes = self.cipher.decrypt(encrypted_bytes)
            decrypted_str = decrypted_bytes.decode("utf-8")

            logger.debug("Token decrypted successfully")
            return decrypted_str

        except InvalidToken:
            logger.error("Token decryption failed: Invalid token or wrong key")
            raise ValueError("Failed to decrypt token: Invalid token or encryption key")
        except Exception as e:
            logger.error(f"Token decryption failed: {e}")
            raise ValueError(f"Failed to decrypt token: {e}")

    def encrypt_spotify_tokens(self, access_token: str, refresh_token: str) -> dict:
        """
        Encrypt Spotify OAuth tokens.

        Args:
            access_token: Spotify access token
            refresh_token: Spotify refresh token

        Returns:
            Dictionary with encrypted tokens
        """
        return {
            "access_token": self.encrypt_token(access_token),
            "refresh_token": self.encrypt_token(refresh_token),
        }

    def decrypt_spotify_tokens(self, encrypted_tokens: dict) -> dict:
        """
        Decrypt Spotify OAuth tokens.

        Args:
            encrypted_tokens: Dictionary with encrypted access_token and refresh_token

        Returns:
            Dictionary with decrypted tokens
        """
        return {
            "access_token": self.decrypt_token(
                encrypted_tokens.get("access_token", "")
            ),
            "refresh_token": self.decrypt_token(
                encrypted_tokens.get("refresh_token", "")
            ),
        }

    @staticmethod
    def generate_key() -> str:
        """
        Generate a new Fernet encryption key.

        Returns:
            Base64-encoded encryption key as string

        Note:
            This is a utility method for generating new keys.
            Store the generated key securely in environment variables.
        """
        key = Fernet.generate_key()
        return key.decode("utf-8")

    def rotate_key(self, old_encrypted_data: str, new_cipher_key: str) -> str:
        """
        Rotate encryption key by re-encrypting data with new key.

        Args:
            old_encrypted_data: Data encrypted with current key
            new_cipher_key: New encryption key to use

        Returns:
            Data re-encrypted with new key
        """
        # Decrypt with old key
        decrypted = self.decrypt_token(old_encrypted_data)

        # Create new cipher with new key
        new_cipher = Fernet(new_cipher_key.encode())

        # Encrypt with new key
        new_encrypted_bytes = new_cipher.encrypt(decrypted.encode("utf-8"))
        return new_encrypted_bytes.decode("utf-8")


# Global encryption service instance (initialized when config is loaded)
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get or create global encryption service instance.

    Returns:
        EncryptionService instance

    Raises:
        ValueError: If encryption key is not configured
    """
    global _encryption_service

    if _encryption_service is None:
        _encryption_service = EncryptionService()

    return _encryption_service
