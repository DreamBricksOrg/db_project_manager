"""Tests for the authentication and request-security changes."""

import pytest

from app.security import LoginThrottle, hash_password, is_hashed, verify_password


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password('hunter2')
        assert hashed != 'hunter2'
        assert 'hunter2' not in hashed
        assert is_hashed(hashed)

    def test_hash_is_salted(self):
        assert hash_password('same') != hash_password('same')

    def test_verify_accepts_correct_password(self):
        ok, needs_rehash = verify_password(hash_password('correct'), 'correct')
        assert ok is True
        assert needs_rehash is False

    def test_verify_rejects_wrong_password(self):
        ok, _ = verify_password(hash_password('correct'), 'wrong')
        assert ok is False

    def test_legacy_plaintext_is_accepted_and_flagged_for_upgrade(self):
        # Rows written before hashing existed hold plaintext.
        ok, needs_rehash = verify_password('legacy-plain', 'legacy-plain')
        assert ok is True
        assert needs_rehash is True

    def test_legacy_plaintext_rejects_wrong_password(self):
        ok, needs_rehash = verify_password('legacy-plain', 'nope')
        assert ok is False
        assert needs_rehash is False

    def test_empty_stored_password_never_matches(self):
        assert verify_password('', '') == (False, False)


class TestLoginThrottle:
    def test_allows_attempts_below_the_limit(self):
        throttle = LoginThrottle(max_attempts=3, lockout_seconds=60)
        throttle.register_failure('k')
        throttle.register_failure('k')
        assert throttle.retry_after('k') == 0

    def test_locks_out_at_the_limit(self):
        throttle = LoginThrottle(max_attempts=3, lockout_seconds=60)
        for _ in range(3):
            throttle.register_failure('k')
        assert throttle.retry_after('k') > 0

    def test_success_clears_the_counter(self):
        throttle = LoginThrottle(max_attempts=2, lockout_seconds=60)
        throttle.register_failure('k')
        throttle.register_failure('k')
        throttle.reset('k')
        assert throttle.retry_after('k') == 0

    def test_keys_are_independent(self):
        throttle = LoginThrottle(max_attempts=1, lockout_seconds=60)
        throttle.register_failure('a')
        assert throttle.retry_after('a') > 0
        assert throttle.retry_after('b') == 0


class TestLoginFlow:
    def test_bootstrap_admin_password_is_stored_hashed(self, csrf_app):
        from app.blueprints.auth.routes import init_default_users
        from app.repositories import users_repo

        with csrf_app.app_context():
            init_default_users()
            admin = users_repo.find_one_by('username', 'admin')

        assert admin is not None
        assert is_hashed(admin['password'])

    def test_login_succeeds_with_correct_credentials(self, csrf_app):
        from app.repositories import users_repo

        with csrf_app.app_context():
            users_repo.create({
                'username': 'julio',
                'password': hash_password('rightpassword'),
                'role': 'admin',
                'nome': 'Julio',
            })

        test_client = csrf_app.test_client()
        resp = test_client.post(
            '/login',
            data={'username': 'julio', 'password': 'rightpassword'},
        )
        assert resp.status_code == 302
        with test_client.session_transaction() as sess:
            assert sess['username'] == 'julio'

    def test_login_fails_with_wrong_password(self, csrf_app):
        from app.repositories import users_repo

        with csrf_app.app_context():
            users_repo.create({
                'username': 'julio',
                'password': hash_password('rightpassword'),
                'role': 'admin',
                'nome': 'Julio',
            })

        test_client = csrf_app.test_client()
        resp = test_client.post(
            '/login', data={'username': 'julio', 'password': 'wrong'}
        )
        assert resp.status_code == 200
        with test_client.session_transaction() as sess:
            assert 'user_id' not in sess

    def test_legacy_plaintext_password_is_upgraded_on_login(self, csrf_app):
        from app.repositories import users_repo

        with csrf_app.app_context():
            users_repo.create({
                'id': 'legacy-1',
                'username': 'antigo',
                'password': 'admin123',  # pre-hashing row
                'role': 'admin',
                'nome': 'Antigo',
            })

        test_client = csrf_app.test_client()
        resp = test_client.post(
            '/login', data={'username': 'antigo', 'password': 'admin123'}
        )
        assert resp.status_code == 302

        with csrf_app.app_context():
            stored = users_repo.get_by_id('legacy-1')['password']
        assert is_hashed(stored), 'plaintext row should be rehashed after login'

    def test_repeated_failures_are_throttled(self, csrf_app):
        import app.blueprints.auth.routes as auth_routes

        auth_routes._throttle = None  # fresh counters for this test
        csrf_app.config['LOGIN_MAX_ATTEMPTS'] = 3
        test_client = csrf_app.test_client()

        for _ in range(3):
            test_client.post('/login', data={'username': 'x', 'password': 'bad'})

        resp = test_client.post('/login', data={'username': 'x', 'password': 'bad'})
        assert resp.status_code == 429
        auth_routes._throttle = None

    def test_logout_rejects_get(self, auth_client):
        # Logout changes state, so it must not be reachable via a GET link.
        assert auth_client.get('/logout').status_code == 405


class TestCsrf:
    def test_post_without_token_is_rejected(self, client):
        resp = client.post('/login', data={'username': 'a', 'password': 'b'})
        assert resp.status_code == 400

    def test_login_page_serves_a_token(self, client):
        html = client.get('/login').get_data(as_text=True)
        assert 'name="csrf_token"' in html


class TestSessionConfig:
    def test_cookie_flags_are_hardened(self, app):
        assert app.config['SESSION_COOKIE_HTTPONLY'] is True
        assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'

    def test_secret_key_is_required_in_production(self, monkeypatch):
        from config import Config

        monkeypatch.delenv('SECRET_KEY', raising=False)
        monkeypatch.delenv('FLASK_DEBUG', raising=False)
        monkeypatch.delenv('FLASK_ENV', raising=False)
        with pytest.raises(RuntimeError, match='SECRET_KEY'):
            Config.resolve_secret_key()

    def test_placeholder_secret_key_is_refused(self, monkeypatch):
        from config import Config

        monkeypatch.setenv('SECRET_KEY', 'your-secret-key-here')
        monkeypatch.delenv('FLASK_DEBUG', raising=False)
        monkeypatch.delenv('FLASK_ENV', raising=False)
        with pytest.raises(RuntimeError):
            Config.resolve_secret_key()
