from datetime import datetime, timezone
from typing import Optional

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher
from jwt.exceptions import InvalidTokenError


password_hash = PasswordHash((Argon2Hasher(),))


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2.

    Args:
        password: Plaintext password string.

    Returns:
        Hashed password string suitable for database storage.
    """
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its stored hash.

    Args:
        plain_password: Plaintext password provided by user.
        hashed_password: Stored hashed password from the database.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    return password_hash.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[datetime] = None) -> str:
    """Create a JWT access token.

    Args:
        data: Payload data to encode into the token (typically user id/email).
        expires_delta: Optional datetime for token expiration.

    Returns:
        Encoded JWT token string.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = expires_delta
    else:
        expire = datetime.now(timezone.utc)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, get_settings().SECRET_KEY, algorithm=get_settings().ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT access token.

    Args:
        token: Encoded JWT token string.

    Returns:
        Decoded payload dictionary if valid, None otherwise.
    """
    try:
        payload = jwt.decode(token, get_settings().SECRET_KEY, algorithms=[get_settings().ALGORITHM])
        return payload
    except InvalidTokenError:
        return None


def get_settings():
    from app.core.config import get_settings
    return get_settings()
