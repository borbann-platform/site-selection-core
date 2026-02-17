"""
Helpers for encrypting/decrypting stored BYOK credentials.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from src.config.agent_settings import agent_settings
from src.config.settings import settings


def _derive_fernet_key(secret_material: str) -> bytes:
    digest = hashlib.sha256(secret_material.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    secret_material = (
        agent_settings.AGENT_CREDENTIALS_ENCRYPTION_KEY.strip()
        or settings.JWT_SECRET_KEY.strip()
    )
    if not secret_material:
        raise ValueError(
            "Missing encryption key. Set AGENT_CREDENTIALS_ENCRYPTION_KEY or JWT_SECRET_KEY."
        )
    return Fernet(_derive_fernet_key(secret_material))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt plaintext for at-rest credential storage."""
    token = _get_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt previously encrypted secret token."""
    try:
        value = _get_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("Unable to decrypt stored credential token.") from exc
    return value.decode("utf-8")


def mask_secret(value: str | None) -> str:
    """Return masked key safe for UI display."""
    if not value:
        return ""
    if len(value) <= 8:
        return f"{value[:2]}***"
    return f"{value[:4]}...{value[-4:]}"
