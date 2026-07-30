"""Smoke tests that actually render the pages.

These exist to catch template breakage — a missing variable, a bad include, a
csrf_token() call in a template that no longer has a request context — which
unit tests on the Python side would miss entirely.
"""

import pytest

# GET pages that render without needing a specific record to exist.
ADMIN_LIST_PAGES = [
    '/admin/', '/admin/users', '/admin/clients', '/admin/contacts',
    '/admin/producers', '/admin/installers', '/admin/services',
    '/admin/materials', '/admin/tools', '/admin/equipment',
]

ADMIN_NEW_PAGES = [
    '/admin/users/new', '/admin/clients/new', '/admin/contacts/new',
    '/admin/producers/new', '/admin/installers/new', '/admin/services/new',
    '/admin/materials/new', '/admin/tools/new', '/admin/equipment/new',
]


class TestPagesRender:
    @pytest.mark.parametrize('path', ADMIN_LIST_PAGES)
    def test_admin_list_pages_render(self, auth_client, path):
        resp = auth_client.get(path)
        assert resp.status_code == 200, f'{path} returned {resp.status_code}'

    @pytest.mark.parametrize('path', ADMIN_NEW_PAGES)
    def test_admin_form_pages_render(self, auth_client, path):
        resp = auth_client.get(path)
        assert resp.status_code == 200, f'{path} returned {resp.status_code}'

    def test_forms_include_a_csrf_field(self, app):
        """The token is injected by the app, not hardcoded per template."""
        test_client = app.test_client()
        html = test_client.get('/login').get_data(as_text=True)
        assert 'name="csrf_token"' in html
        assert 'name="csrf-token"' in html  # meta tag used by fetch/htmx

    def test_project_and_plan_lists_render(self, auth_client):
        assert auth_client.get('/projects/').status_code == 200
        assert auth_client.get('/plans/').status_code == 200

    def test_plans_list_accepts_search_and_filters(self, auth_client):
        resp = auth_client.get('/plans/?q=teste&status=&start_date=2026-01-01')
        assert resp.status_code == 200

    def test_projects_list_accepts_sort_and_pagination(self, auth_client):
        resp = auth_client.get('/projects/?sort_by=nome&sort_dir=desc&per_page=24&page=1')
        assert resp.status_code == 200

    def test_unknown_sort_field_is_ignored(self, auth_client):
        # sort_by is validated against an allowlist, so junk must not reach Mongo.
        resp = auth_client.get('/projects/?sort_by=__proto__&sort_dir=desc')
        assert resp.status_code == 200


class TestErrorHandling:
    def test_unknown_page_renders_the_404_template(self, auth_client):
        resp = auth_client.get('/nao-existe')
        assert resp.status_code == 404
        assert 'Página não encontrada' in resp.get_data(as_text=True)

    def test_unknown_api_path_returns_json(self, auth_client):
        resp = auth_client.get('/api/nao-existe')
        assert resp.status_code == 404
        assert resp.is_json
        assert resp.get_json()['error'] == 'not_found'

    def test_error_page_renders_for_anonymous_users(self, csrf_app):
        # base.html only fills `content` when logged in; the error page has to
        # be visible either way.
        resp = csrf_app.test_client().get('/nao-existe')
        assert resp.status_code == 404
        assert 'Página não encontrada' in resp.get_data(as_text=True)


class TestHealthcheck:
    def test_healthz_reports_ok_when_mongo_answers(self, app):
        resp = app.test_client().get('/healthz')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'ok'

    def test_healthz_distinguishes_unreachable_from_bad_credentials(self, app, monkeypatch):
        """A wrong password and a dead host must not look identical.

        Reporting both as "unreachable" sends whoever is on call to inspect
        the network when the real problem is a credential.
        """
        from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

        from app import database

        cases = [
            (ServerSelectionTimeoutError('no route to host'), 'unreachable'),
            (OperationFailure('Authentication failed.'), 'auth_failed'),
            (RuntimeError('something else entirely'), 'error'),
        ]

        for exc, expected in cases:
            def boom(_exc=exc):
                raise _exc

            monkeypatch.setattr(database, 'get_client', boom)
            resp = app.test_client().get('/healthz')
            assert resp.status_code == 503
            assert resp.get_json()['database'] == expected


class TestConnectionCredentials:
    def test_password_with_special_characters_is_not_interpolated(self, monkeypatch):
        """Credentials go to MongoClient as parameters, never into the URI.

        A password containing '@' terminates the userinfo section of a
        connection string, so the driver reads the wrong host and the failure
        surfaces as an unreachable server instead of a bad password.
        """
        import app.database as database

        captured = {}

        class FakeClient:
            def __init__(self, uri, **options):
                captured['uri'] = uri
                captured['options'] = options

        monkeypatch.setattr(database, 'MongoClient', FakeClient)
        monkeypatch.setattr(database, '_client', None)
        monkeypatch.setenv('MONGODB_URI', 'mongodb://mongodb:27020/ooh_manager_db')
        monkeypatch.setenv('MONGO_USER', 'dreambricks')
        monkeypatch.setenv('MONGO_PASSWORD', 'HP365@pm')

        database.get_client()

        assert 'HP365@pm' not in captured['uri']
        assert captured['options']['username'] == 'dreambricks'
        assert captured['options']['password'] == 'HP365@pm'
        assert captured['options']['authSource'] == 'admin'

        monkeypatch.setattr(database, '_client', None)

    def test_no_credentials_means_no_auth_options(self, monkeypatch):
        import app.database as database

        captured = {}

        class FakeClient:
            def __init__(self, uri, **options):
                captured['options'] = options

        monkeypatch.setattr(database, 'MongoClient', FakeClient)
        monkeypatch.setattr(database, '_client', None)
        monkeypatch.delenv('MONGO_USER', raising=False)
        monkeypatch.delenv('MONGO_PASSWORD', raising=False)

        database.get_client()

        assert 'username' not in captured['options']
        monkeypatch.setattr(database, '_client', None)


class TestUploadValidation:
    def test_non_image_bytes_are_rejected(self, auth_client, csrf_app):
        import io

        from app.repositories import installation_photos_repo, projects_repo

        with csrf_app.app_context():
            projects_repo.create({'id': 'p1', 'nome': 'Projeto'})

        # A .jpg name on content that is not an image at all.
        payload = {'photo': (io.BytesIO(b'not an image, just bytes'), 'evil.jpg')}
        resp = auth_client.post(
            '/projects/p1/photos', data=payload, content_type='multipart/form-data'
        )

        assert resp.status_code == 400
        with csrf_app.app_context():
            assert installation_photos_repo.count() == 0

    def test_real_image_is_accepted(self, auth_client, csrf_app):
        import io

        from PIL import Image

        from app.repositories import installation_photos_repo, projects_repo

        with csrf_app.app_context():
            projects_repo.create({'id': 'p2', 'nome': 'Projeto'})

        buf = io.BytesIO()
        Image.new('RGB', (8, 8), 'blue').save(buf, format='JPEG')
        buf.seek(0)

        resp = auth_client.post(
            '/projects/p2/photos',
            data={'photo': (buf, 'foto.jpg')},
            content_type='multipart/form-data',
        )

        assert resp.status_code == 200
        with csrf_app.app_context():
            assert installation_photos_repo.count() == 1
