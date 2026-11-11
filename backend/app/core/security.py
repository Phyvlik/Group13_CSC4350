import bcrypt

# bcrypt only reads the first 72 bytes of a password, and bcrypt>=5 rejects anything longer.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a plain text password with a fresh bcrypt salt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if the plain text password matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Over-long passwords or a malformed stored hash never match.
        return False
