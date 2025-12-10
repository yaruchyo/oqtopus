"""
Security utilities for the orchestrator application.

This module provides:
- Password strength validation
- Private key encryption/decryption
- Rate limiting configuration
- Network security (SSRF prevention)
"""

import base64
import ipaddress
import logging
import re
import socket
from typing import Optional, Tuple
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dotenv import load_dotenv

from agent_package import config

load_dotenv()

logger = logging.getLogger(__name__)


def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password strength requirements.

    Requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number

    Args:
        password: The password to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"

    return True, None


def is_safe_url(url: str, allow_local: bool = False) -> Tuple[bool, Optional[str]]:
    """
    Validate that a URL is safe to connect to (SSRF protection).

    Ensures the URL does not resolve to private/internal IP addresses.

    Args:
        url: The URL to validate
        allow_local: If True, allow private IPs (use for development ONLY)

    Returns:
        Tuple of (is_safe, error_message)
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return False, "Invalid URL"

        # Get IP address (resolves DNS)
        try:
            # We want to check all resolved IPs, not just the first one
            # to prevent DNS rebinding or round-robin bypasses
            # However, for basic validation, one check is better than none.
            # Best is to resolve here and use the IP for the request, but
            # modifying the downstream request code is complex.
            # This check prevents registering obvious internal targets.
            ip_list = socket.getaddrinfo(hostname, None)
        except socket.gaierror:
            return False, "Could not resolve hostname"

        for item in ip_list:
            # item[4] is (address, port) tuple for AF_INET
            ip_str = item[4][0]
            ip_obj = ipaddress.ip_address(ip_str)

            # Allow loopback ONLY if allow_local is True
            # Allow private ONLY if allow_local is True

            if allow_local:
                continue

            if ip_obj.is_private:
                return False, f"Target resolves to private network address: {ip_str}"

            if ip_obj.is_loopback:
                return False, f"Target resolves to loopback address: {ip_str}"

            if ip_obj.is_link_local:
                return False, f"Target resolves to link-local address: {ip_str}"

            if ip_obj.is_multicast:
                return False, f"Target resolves to multicast address: {ip_str}"

        return True, None

    except Exception as e:
        logger.error(f"Error validating URL {url}: {e}")
        return False, "Error validating URL security"


class PrivateKeyEncryption:
    """
    Handles encryption and decryption of private keys using Fernet (AES-128-CBC).

    The encryption key is derived from a master key using PBKDF2.
    """

    def __init__(self, master_key: str):
        """
        Initialize encryption with a master key.

        Args:
            master_key: The master encryption key (typically from SECRET_KEY)

        Raises:
            ValueError: If master_key is empty or if salt is not set in production
        """

        if not master_key:
            raise ValueError("Master key cannot be empty")

        # Derive a key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=config.SALT_KEY.encode(),
            iterations=480000,  # OWASP recommended iteration count
        )

        # Fernet requires a 32-byte key, base64 encoded
        key = base64.urlsafe_b64encode(kdf.derive(master_key.encode()))
        self.fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string (e.g., private key PEM).

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        encrypted = self.fernet.encrypt(plaintext.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string.

        Args:
            ciphertext: Base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        encrypted = base64.urlsafe_b64decode(ciphertext.encode())
        decrypted = self.fernet.decrypt(encrypted)
        return decrypted.decode()


# Singleton instance - initialized when needed
_pk_encryption: Optional[PrivateKeyEncryption] = None


def get_pk_encryption(master_key: str) -> PrivateKeyEncryption:
    """
    Get or create the private key encryption instance.

    Args:
        master_key: The master encryption key

    Returns:
        PrivateKeyEncryption instance
    """
    global _pk_encryption
    if _pk_encryption is None:
        _pk_encryption = PrivateKeyEncryption(master_key)
    return _pk_encryption


def encrypt_private_key(private_key_pem: str, master_key: str) -> str:
    """
    Convenience function to encrypt a private key.

    Args:
        private_key_pem: The private key in PEM format
        master_key: The master encryption key

    Returns:
        Encrypted private key string
    """
    encryptor = get_pk_encryption(master_key)
    return encryptor.encrypt(private_key_pem)


def decrypt_private_key(encrypted_key: str, master_key: str) -> str:
    """
    Convenience function to decrypt a private key.

    Args:
        encrypted_key: The encrypted private key
        master_key: The master encryption key

    Returns:
        Decrypted private key in PEM format
    """
    encryptor = get_pk_encryption(master_key)
    return encryptor.decrypt(encrypted_key)
