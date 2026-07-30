"""Password hashing and login throttling helpers."""

import logging
import time
from threading import Lock

from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger(__name__)

# Werkzeug prefixes every hash it produces with the method name.
_HASH_PREFIXES = ('pbkdf2:', 'scrypt:', 'argon2:')

HASH_METHOD = 'pbkdf2:sha256:600000'


def hash_password(password: str) -> str:
    """Return a salted hash for a plaintext password."""
    return generate_password_hash(password, method=HASH_METHOD)


def is_hashed(stored: str) -> bool:
    """True if the stored value already looks like a Werkzeug hash."""
    return bool(stored) and stored.startswith(_HASH_PREFIXES)


def verify_password(stored: str, candidate: str) -> tuple[bool, bool]:
    """Check a password against the stored value.

    Returns ``(ok, needs_rehash)``. Legacy rows hold plaintext, so those are
    compared directly and flagged for upgrade on the next successful login.
    """
    if not stored:
        return False, False
    if is_hashed(stored):
        return check_password_hash(stored, candidate), False
    # Legacy plaintext row. Constant-time compare, then ask the caller to
    # re-store it as a hash.
    import hmac

    ok = hmac.compare_digest(stored, candidate)
    return ok, ok


class LoginThrottle:
    """In-memory sliding lockout keyed by username and client IP.

    Good enough for a single-process or few-worker deployment. Behind several
    Gunicorn workers each process keeps its own counters, so move this to Redis
    if you need a shared limit.
    """

    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 300):
        self.max_attempts = max_attempts
        self.lockout_seconds = lockout_seconds
        self._attempts: dict[str, list[float]] = {}
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> list[float]:
        recent = [t for t in self._attempts.get(key, []) if now - t < self.lockout_seconds]
        if recent:
            self._attempts[key] = recent
        else:
            self._attempts.pop(key, None)
        return recent

    def retry_after(self, key: str) -> int:
        """Seconds until the caller may try again; 0 if not locked out."""
        now = time.time()
        with self._lock:
            recent = self._prune(key, now)
            if len(recent) < self.max_attempts:
                return 0
            return max(1, int(self.lockout_seconds - (now - min(recent))))

    def register_failure(self, key: str) -> None:
        now = time.time()
        with self._lock:
            recent = self._prune(key, now)
            recent.append(now)
            self._attempts[key] = recent

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
