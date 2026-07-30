"""Tests for the repository, query helpers and generated admin CRUD."""

import time

from app.querying import merge_filters, text_filter


class TestRepository:
    def test_create_assigns_an_id(self, app):
        from app.repositories import clients_repo

        with app.app_context():
            created = clients_repo.create({'nome': 'ACME'})
            assert created['id']
            assert clients_repo.get_by_id(created['id'])['nome'] == 'ACME'

    def test_find_one_by_looks_up_a_single_field(self, app):
        from app.repositories import users_repo

        with app.app_context():
            users_repo.create({'username': 'julio', 'nome': 'Julio'})
            assert users_repo.find_one_by('username', 'julio')['nome'] == 'Julio'
            assert users_repo.find_one_by('username', 'ausente') is None

    def test_update_cannot_rewrite_the_id(self, app):
        from app.repositories import clients_repo

        with app.app_context():
            created = clients_repo.create({'id': 'fixed-1', 'nome': 'Antes'})
            clients_repo.update('fixed-1', {'id': 'hijacked', 'nome': 'Depois'})

            assert clients_repo.get_by_id('fixed-1')['nome'] == 'Depois'
            assert clients_repo.get_by_id('hijacked') is None
            assert created['id'] == 'fixed-1'

    def test_count_matches_filters(self, app):
        from app.repositories import projects_repo

        with app.app_context():
            projects_repo.create({'nome': 'A', 'status': 'Concluído'})
            projects_repo.create({'nome': 'B', 'status': 'Em Andamento'})
            projects_repo.create({'nome': 'C', 'status': 'Em Andamento'})

            assert projects_repo.count() == 3
            assert projects_repo.count({'status': 'Em Andamento'}) == 2

    def test_find_sorts_skips_and_limits(self, app):
        from app.repositories import projects_repo

        with app.app_context():
            for name in ('C', 'A', 'B', 'D'):
                projects_repo.create({'nome': name})

            page = projects_repo.find(sort=[('nome', 1)], skip=1, limit=2)
            assert [p['nome'] for p in page] == ['B', 'C']

    def test_search_escapes_regex_metacharacters(self, app):
        from app.repositories import clients_repo

        with app.app_context():
            clients_repo.create({'nome': 'ACME'})
            clients_repo.create({'nome': 'A.C.M.E'})

            # '.' must be a literal, not "any character".
            results = [c['nome'] for c in clients_repo.search('nome', 'A.C')]
            assert results == ['A.C.M.E']

    def test_search_does_not_hang_on_a_catastrophic_pattern(self, app):
        from app.repositories import clients_repo

        with app.app_context():
            clients_repo.create({'nome': 'a' * 40 + '!'})

            evil = '(a+)+$'
            started = time.monotonic()
            clients_repo.search('nome', evil)
            assert time.monotonic() - started < 2.0


class TestQueryHelpers:
    def test_text_filter_is_empty_for_a_blank_query(self):
        assert text_filter('', ('nome',)) == {}

    def test_text_filter_covers_every_field(self):
        built = text_filter('abc', ('nome', 'email'))
        assert [list(clause)[0] for clause in built['$or']] == ['nome', 'email']

    def test_text_filter_escapes_the_term(self):
        built = text_filter('a.c', ('nome',))
        assert built['$or'][0]['nome']['$regex'] == r'a\.c'

    def test_merge_filters_drops_empties(self):
        assert merge_filters({}, {'a': 1}, {}) == {'a': 1}
        assert merge_filters({}, {}) == {}
        assert merge_filters({'a': 1}, {'b': 2}) == {'$and': [{'a': 1}, {'b': 2}]}


class TestGeneratedCrud:
    def test_every_entity_exposes_the_four_views(self, app):
        expected = []
        for name, singular in [
            ('clients', 'client'), ('contacts', 'contact'),
            ('producers', 'producer'), ('installers', 'installer'),
            ('services', 'service'), ('materials', 'material'),
            ('tools', 'tool'), ('equipment', 'equipment'),
        ]:
            expected += [
                f'admin.list_{name}', f'admin.new_{singular}',
                f'admin.edit_{singular}', f'admin.delete_{singular}',
            ]

        registered = {r.endpoint for r in app.url_map.iter_rules()}
        assert set(expected) <= registered

    def test_crud_urls_are_unchanged(self, app):
        by_endpoint = {r.endpoint: str(r) for r in app.url_map.iter_rules()}
        assert by_endpoint['admin.list_clients'] == '/admin/clients'
        assert by_endpoint['admin.new_client'] == '/admin/clients/new'
        assert by_endpoint['admin.edit_client'] == '/admin/clients/<id>/edit'
        assert by_endpoint['admin.delete_client'] == '/admin/clients/<id>/delete'
        assert by_endpoint['admin.list_equipment'] == '/admin/equipment'

    def test_create_via_the_generated_view(self, auth_client, csrf_app):
        from app.repositories import clients_repo

        resp = auth_client.post('/admin/clients/new', data={
            'nome': 'Cliente Novo', 'email': 'a@b.com',
            'telefone': '11999', 'documento': '123',
        })
        assert resp.status_code == 302

        with csrf_app.app_context():
            found = clients_repo.find_one_by('nome', 'Cliente Novo')
        assert found['email'] == 'a@b.com'

    def test_required_field_blocks_creation(self, auth_client, csrf_app):
        from app.repositories import clients_repo

        resp = auth_client.post('/admin/clients/new', data={'nome': ''})
        assert resp.status_code == 200  # re-renders the form

        with csrf_app.app_context():
            assert clients_repo.count() == 0

    def test_services_validate_their_own_required_field(self, auth_client, csrf_app):
        from app.repositories import services_repo

        auth_client.post('/admin/services/new', data={'responsavel': 'Alguém'})
        with csrf_app.app_context():
            assert services_repo.count() == 0

        auth_client.post('/admin/services/new', data={
            'tipo_servico': 'Montagem', 'responsavel': 'Alguém',
        })
        with csrf_app.app_context():
            assert services_repo.count() == 1

    def test_edit_and_delete(self, auth_client, csrf_app):
        from app.repositories import contacts_repo

        with csrf_app.app_context():
            contacts_repo.create({'id': 'c1', 'nome': 'Antes'})

        auth_client.post('/admin/contacts/c1/edit', data={
            'nome': 'Depois', 'telefone': '', 'email': '',
        })
        with csrf_app.app_context():
            assert contacts_repo.get_by_id('c1')['nome'] == 'Depois'

        auth_client.post('/admin/contacts/c1/delete')
        with csrf_app.app_context():
            assert contacts_repo.get_by_id('c1') is None

    def test_admin_routes_require_authentication(self, csrf_app):
        anon = csrf_app.test_client()
        resp = anon.get('/admin/clients')
        assert resp.status_code == 302
        assert '/login' in resp.headers['Location']

    def test_non_admin_cannot_reach_admin(self, csrf_app):
        test_client = csrf_app.test_client()
        with test_client.session_transaction() as sess:
            sess['user_id'] = 'u1'
            sess['role'] = 'user'
        resp = test_client.get('/admin/clients')
        assert resp.status_code == 302
        assert '/admin' not in resp.headers['Location']


class TestUserAdmin:
    def test_created_user_password_is_hashed(self, auth_client, csrf_app):
        from app.repositories import users_repo
        from app.security import is_hashed

        auth_client.post('/admin/users/new', data={
            'nome': 'Novo', 'username': 'novo',
            'password': 'longenoughpw', 'role': 'user',
        })
        with csrf_app.app_context():
            created = users_repo.find_one_by('username', 'novo')

        assert created is not None
        assert is_hashed(created['password'])
        assert created['password'] != 'longenoughpw'

    def test_short_password_is_rejected(self, auth_client, csrf_app):
        from app.repositories import users_repo

        auth_client.post('/admin/users/new', data={
            'nome': 'Novo', 'username': 'curto', 'password': 'abc',
        })
        with csrf_app.app_context():
            assert users_repo.find_one_by('username', 'curto') is None

    def test_duplicate_username_is_rejected(self, auth_client, csrf_app):
        from app.repositories import users_repo
        from app.security import hash_password

        with csrf_app.app_context():
            users_repo.create({
                'username': 'existente', 'password': hash_password('x' * 10),
                'nome': 'Existente', 'role': 'user',
            })

        auth_client.post('/admin/users/new', data={
            'nome': 'Outro', 'username': 'existente', 'password': 'y' * 10,
        })
        with csrf_app.app_context():
            assert users_repo.count({'username': 'existente'}) == 1

    def test_blank_password_on_edit_keeps_the_current_one(self, auth_client, csrf_app):
        from app.repositories import users_repo
        from app.security import hash_password

        original = hash_password('originalpw')
        with csrf_app.app_context():
            users_repo.create({
                'id': 'u9', 'username': 'manter', 'password': original,
                'nome': 'Manter', 'role': 'user',
            })

        auth_client.post('/admin/users/u9/edit', data={
            'nome': 'Manter Editado', 'username': 'manter', 'password': '',
        })
        with csrf_app.app_context():
            after = users_repo.get_by_id('u9')

        assert after['nome'] == 'Manter Editado'
        assert after['password'] == original

    def test_cannot_delete_own_account(self, csrf_app):
        from app.repositories import users_repo
        from app.security import hash_password

        with csrf_app.app_context():
            users_repo.create({
                'id': 'me', 'username': 'eu', 'password': hash_password('x' * 10),
                'nome': 'Eu', 'role': 'admin',
            })

        test_client = csrf_app.test_client()
        with test_client.session_transaction() as sess:
            sess['user_id'] = 'me'
            sess['username'] = 'eu'
            sess['role'] = 'admin'

        test_client.post('/admin/users/me/delete')
        with csrf_app.app_context():
            assert users_repo.get_by_id('me') is not None
