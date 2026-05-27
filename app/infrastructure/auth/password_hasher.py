from __future__ import annotations

import bcrypt


def hash_password(plaintext: str) -> str:
    """Return a bcrypt hash of *plaintext*.  Called at boot-time only."""
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    """Return True iff *plaintext* matches *hashed*."""
    return bcrypt.checkpw(plaintext.encode(), hashed.encode())
