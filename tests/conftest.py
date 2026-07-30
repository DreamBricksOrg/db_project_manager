"""Shared test fixtures.

The suite runs against mongomock, so no MongoDB server is needed. The patch
targets ``app.database.get_client`` — every repository goes through it, so a
single seam covers the whole data layer.
"""

import os
import sys
from pathlib import Path

import mongomock
import pytest

# Make the project root importable when pytest is invoked from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault('SECRET_KEY', 'test-secret-key')
os.environ.setdefault('ENSURE_INDEXES', 'false')
os.environ.setdefault('SESSION_COOKIE_SECURE', 'false')
os.environ.setdefault('WTF_CSRF_SSL_STRICT', 'false')


@pytest.fixture
def mongo(monkeypatch):
    """Swap the real MongoClient for a fresh in-memory one per test.

    ``mongo_repository`` does ``from app.database import get_db``, which binds
    the function object into its own namespace at import time. Patching only
    ``app.database.get_db`` would therefore be picked up by whichever test
    happened to trigger the import first, and every later test would keep
    writing into that same database. Patching the name the repository actually
    calls is what makes the isolation real.
    """
    import app.database
    import app.repositories.mongo_repository as repo_module

    client = mongomock.MongoClient()

    def fake_get_client():
        return client

    def fake_get_db():
        return client['test_db']

    monkeypatch.setattr(app.database, 'get_client', fake_get_client)
    monkeypatch.setattr(app.database, 'get_db', fake_get_db)
    monkeypatch.setattr(repo_module, 'get_db', fake_get_db)
    return client


@pytest.fixture
def app(mongo):
    from app import create_app
    from config import Config

    application = create_app(Config)
    application.config.update(TESTING=True, ENSURE_INDEXES=False)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def csrf_app(mongo):
    """App with CSRF disabled, for tests that only exercise business logic."""
    from app import create_app
    from config import Config

    application = create_app(Config)
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    return application


@pytest.fixture
def auth_client(csrf_app):
    """A test client already logged in as an admin."""
    from app.repositories import users_repo
    from app.security import hash_password

    with csrf_app.app_context():
        users_repo.create({
            'username': 'admin',
            'password': hash_password('supersecret123'),
            'role': 'admin',
            'nome': 'Administrador',
        })

    test_client = csrf_app.test_client()
    with test_client.session_transaction() as sess:
        sess['user_id'] = 'seeded'
        sess['username'] = 'admin'
        sess['role'] = 'admin'
        sess['nome'] = 'Administrador'
        sess['tipo'] = 'admin'
    return test_client
