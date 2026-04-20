"""
Unit tests for services/encryption_service.py.
"""
import pytest
from cryptography.fernet import Fernet, InvalidToken

from services import encryption_service


@pytest.mark.unit
class TestEncrypt:
    def test_returns_bytes(self):
        result = encryption_service.encrypt("hello")
        assert isinstance(result, bytes)

    def test_non_empty_ciphertext(self):
        result = encryption_service.encrypt("hello")
        assert len(result) > 0

    def test_does_not_contain_plaintext(self):
        result = encryption_service.encrypt("super-secret")
        assert b"super-secret" not in result

    def test_empty_string_encrypts(self):
        result = encryption_service.encrypt("")
        assert isinstance(result, bytes)

    def test_different_calls_produce_different_ciphertext(self):
        # Fernet uses random IV, so two encryptions of the same value differ.
        ct1 = encryption_service.encrypt("same-value")
        ct2 = encryption_service.encrypt("same-value")
        assert ct1 != ct2

    def test_long_string_encrypts(self):
        long_str = "x" * 10_000
        result = encryption_service.encrypt(long_str)
        assert isinstance(result, bytes)

    def test_unicode_encrypts(self):
        result = encryption_service.encrypt("مرحبا 日本語 emoji 🔐")
        assert isinstance(result, bytes)


@pytest.mark.unit
class TestDecrypt:
    def test_roundtrip(self):
        original = "my-sensitive-data"
        token = encryption_service.encrypt(original)
        recovered = encryption_service.decrypt(token)
        assert recovered == original

    def test_roundtrip_empty_string(self):
        token = encryption_service.encrypt("")
        assert encryption_service.decrypt(token) == ""

    def test_roundtrip_unicode(self):
        value = "مرحبا 日本語 🔐"
        assert encryption_service.decrypt(encryption_service.encrypt(value)) == value

    def test_roundtrip_long_string(self):
        value = "A" * 10_000
        assert encryption_service.decrypt(encryption_service.encrypt(value)) == value

    def test_invalid_token_raises(self):
        with pytest.raises((InvalidToken, Exception)):
            encryption_service.decrypt(b"not-a-valid-token")

    def test_tampered_token_raises(self, settings):
        token = encryption_service.encrypt("original")
        # Flip a byte in the ciphertext
        tampered = bytearray(token)
        tampered[10] ^= 0xFF
        with pytest.raises(Exception):
            encryption_service.decrypt(bytes(tampered))

    def test_decrypt_bytes_input(self):
        """decrypt() must accept raw bytes as returned by value_encrypted."""
        value = "sensitive"
        token = encryption_service.encrypt(value)
        assert encryption_service.decrypt(token) == value


@pytest.mark.unit
class TestFernetKeyConfiguration:
    def test_bad_key_raises_on_encrypt(self, settings):
        settings.ENCRYPTION_KEY = "not-a-valid-fernet-key"
        with pytest.raises(Exception):
            encryption_service.encrypt("value")

    def test_bytes_key_accepted(self, settings):
        """The service must accept the key as bytes too (env-loaded str vs bytes)."""
        key = Fernet.generate_key()
        settings.ENCRYPTION_KEY = key  # bytes
        token = encryption_service.encrypt("test")
        assert encryption_service.decrypt(token) == "test"

    def test_string_key_accepted(self, settings):
        key = Fernet.generate_key().decode()
        settings.ENCRYPTION_KEY = key  # str
        token = encryption_service.encrypt("test")
        assert encryption_service.decrypt(token) == "test"
