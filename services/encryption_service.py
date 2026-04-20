from cryptography.fernet import Fernet
from django.conf import settings


def _fernet() -> Fernet:
    """Build and return a Fernet instance using the ENCRYPTION_KEY setting."""
    key = settings.ENCRYPTION_KEY
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)


def encrypt(value: str) -> bytes:
    """Encrypt *value* using Fernet symmetric encryption; returns raw ciphertext bytes."""
    return _fernet().encrypt(value.encode())


def decrypt(token: bytes) -> str:
    """Decrypt Fernet *token* and return the original plaintext string."""
    return _fernet().decrypt(token).decode()
