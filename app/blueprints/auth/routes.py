"""Auth Routes - Login/Logout"""

import logging
import os
import secrets
from functools import wraps

from flask import current_app, flash, redirect, render_template, request, session, url_for

from app.blueprints.auth import auth_bp
from app.repositories import users_repo
from app.security import LoginThrottle, hash_password, verify_password

logger = logging.getLogger(__name__)

_throttle: LoginThrottle | None = None


def get_throttle() -> LoginThrottle:
    global _throttle
    if _throttle is None:
        _throttle = LoginThrottle(
            max_attempts=current_app.config.get('LOGIN_MAX_ATTEMPTS', 5),
            lockout_seconds=current_app.config.get('LOGIN_LOCKOUT_SECONDS', 300),
        )
    return _throttle


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para continuar.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para continuar.', 'error')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Acesso restrito a administradores.', 'error')
            return redirect(url_for('plans.list_plans'))
        return f(*args, **kwargs)
    return decorated_function


def init_default_users():
    """Create the first admin user if the collection is empty.

    The password is taken from ADMIN_INITIAL_PASSWORD when provided; otherwise a
    random one is generated and logged once. Shipping a known default password
    ('admin123') meant every deployment of this app had the same credentials.
    """
    if users_repo.count() > 0:
        return

    password = os.environ.get('ADMIN_INITIAL_PASSWORD', '').strip()
    generated = False
    if not password:
        password = secrets.token_urlsafe(12)
        generated = True

    users_repo.create({
        'username': 'admin',
        'password': hash_password(password),
        'role': 'admin',
        'nome': 'Administrador',
    })

    if generated:
        logger.warning(
            'No users found. Created bootstrap admin account.\n'
            '  username: admin\n'
            '  password: %s\n'
            'Change it after first login; this is the only time it is shown.',
            password,
        )
    else:
        logger.info('Created bootstrap admin account from ADMIN_INITIAL_PASSWORD.')


def find_user_for_login(username: str, password: str):
    """Return the session payload for valid credentials, else None."""
    user = users_repo.find_one_by('username', username)
    if not user:
        # Spend roughly the same time as a real check so the response time does
        # not reveal whether the username exists.
        hash_password(password)
        return None

    ok, needs_rehash = verify_password(user.get('password', ''), password)
    if not ok:
        return None

    if needs_rehash:
        # Legacy plaintext row: upgrade it now that we know the password.
        users_repo.update(user['id'], {'password': hash_password(password)})
        logger.info('Upgraded stored password to a hash for user %s', user['id'])

    return {
        'id': user['id'],
        'username': user['username'],
        'nome': user.get('nome', user['username']),
        'role': user.get('role', 'user'),
        'tipo': 'admin',
    }


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('plans.list_plans'))

    init_default_users()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        throttle = get_throttle()
        throttle_key = f'{request.remote_addr}|{username.lower()}'

        wait = throttle.retry_after(throttle_key)
        if wait:
            logger.warning('Throttled login attempt for %r from %s', username, request.remote_addr)
            flash(
                f'Muitas tentativas de login. Tente novamente em {wait // 60 + 1} minuto(s).',
                'error',
            )
            return render_template('auth/login.html'), 429

        user = find_user_for_login(username, password)

        if user:
            throttle.reset(throttle_key)
            # New session id on privilege change, so a pre-login cookie cannot
            # be reused to ride the authenticated session (session fixation).
            session.clear()
            session.permanent = True
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['nome'] = user['nome']
            session['tipo'] = user['tipo']
            logger.info('Login ok for %s from %s', user['username'], request.remote_addr)
            flash(f'Bem-vindo, {user["nome"]}!', 'success')
            return redirect(url_for('plans.list_plans'))

        throttle.register_failure(throttle_key)
        logger.warning('Failed login for %r from %s', username, request.remote_addr)
        flash('Usuário ou senha incorretos.', 'error')

    return render_template('auth/login.html')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'success')
    return redirect(url_for('auth.login'))
