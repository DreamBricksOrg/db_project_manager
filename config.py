# OOH Project Manager Configuration

import os
import secrets
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / 'data'
UPLOAD_DIR = BASE_DIR / 'app' / 'static' / 'uploads'


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ('1', 'true', 'yes', 'on')


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    ENV = os.environ.get('FLASK_ENV', 'production')
    DEBUG = _env_bool('FLASK_DEBUG', False)

    DATA_DIR = DATA_DIR
    UPLOAD_DIR = UPLOAD_DIR

    # 64 MB. The old 2 GB limit meant a single request could exhaust memory and
    # disk; raise it deliberately if genuinely large media uploads are needed.
    MAX_CONTENT_LENGTH = _env_int('MAX_UPLOAD_MB', 64) * 1024 * 1024

    # Session / cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Only send the cookie over HTTPS. Disable explicitly for plain-HTTP dev.
    SESSION_COOKIE_SECURE = _env_bool('SESSION_COOKIE_SECURE', True)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=_env_int('SESSION_HOURS', 12))
    SESSION_REFRESH_EACH_REQUEST = True

    # CSRF (Flask-WTF)
    WTF_CSRF_TIME_LIMIT = None  # tie token lifetime to the session instead
    WTF_CSRF_SSL_STRICT = _env_bool('WTF_CSRF_SSL_STRICT', True)

    # Login throttling
    LOGIN_MAX_ATTEMPTS = _env_int('LOGIN_MAX_ATTEMPTS', 5)
    LOGIN_LOCKOUT_SECONDS = _env_int('LOGIN_LOCKOUT_SECONDS', 300)

    ENSURE_INDEXES = _env_bool('ENSURE_INDEXES', True)

    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

    @staticmethod
    def resolve_secret_key() -> str:
        """Return the signing key, refusing to run on a shared default in prod.

        A hardcoded fallback lets anyone who has read the source forge a session
        cookie, so production must supply its own key.
        """
        key = os.environ.get('SECRET_KEY', '').strip()
        if key and key != 'your-secret-key-here':
            return key
        if _env_bool('FLASK_DEBUG', False) or os.environ.get('FLASK_ENV') == 'development':
            # Ephemeral key: sessions do not survive a restart, which is fine in
            # development and strictly better than a published constant.
            return secrets.token_hex(32)
        raise RuntimeError(
            'SECRET_KEY is not set. Generate one with '
            '`python -c "import secrets; print(secrets.token_hex(32))"` '
            'and set it in the environment before starting the app.'
        )

    # Populated in create_app() via resolve_secret_key().
    SECRET_KEY = None
