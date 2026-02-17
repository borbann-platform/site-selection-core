"""
Unit tests for secret encryption helpers used by BYOK storage.
"""

from src.services.secret_encryption import decrypt_secret, encrypt_secret, mask_secret


def test_encrypt_decrypt_roundtrip():
    plaintext = "sk-test-secret"
    encrypted = encrypt_secret(plaintext)

    assert encrypted != plaintext
    assert decrypt_secret(encrypted) == plaintext


def test_mask_secret_hides_middle_characters():
    assert mask_secret("sk-1234567890") == "sk-1...7890"
