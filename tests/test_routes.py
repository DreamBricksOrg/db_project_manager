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

    def test_healthz_reports_error_when_mongo_is_down(self, app, monkeypatch):
        import app.database as database

        def boom():
            raise RuntimeError('connection refused')

        monkeypatch.setattr(database, 'get_client', boom)
        resp = app.test_client().get('/healthz')
        assert resp.status_code == 503
        assert resp.get_json()['database'] == 'unreachable'


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
