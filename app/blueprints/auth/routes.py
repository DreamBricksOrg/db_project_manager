"""Auth Routes - Login/Logout"""

from flask import render_template, redirect, url_for, request, session, flash
from functools import wraps

from app.blueprints.auth import auth_bp
from app.repositories import users_repo, installers_repo, producers_repo


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
    """Create default admin user if no users exist"""
    users = users_repo.get_all()
    if not users:
        users_repo.create({
            'username': 'admin',
            'password': 'admin123',  # MVP only - hash in production
            'role': 'admin',
            'nome': 'Administrador'
        })


def find_user_for_login(username: str, password: str):
    """Check users, producers, and installers for matching credentials"""
    # Check admin users first
    users = users_repo.get_all()
    user = next((u for u in users if u.get('username') == username and u.get('password') == password), None)
    if user:
        return {
            'id': user['id'],
            'username': user['username'],
            'nome': user.get('nome', user['username']),
            'role': user.get('role', 'user'),
            'tipo': 'admin'
        }
    
    # Check producers
    producers = producers_repo.get_all()
    producer = next((p for p in producers if p.get('username') == username and p.get('password') == password), None)
    if producer:
        return {
            'id': producer['id'],
            'username': producer['username'],
            'nome': producer.get('nome', producer['username']),
            'role': 'user',
            'tipo': 'produtor'
        }
    
    # Check installers
    installers = installers_repo.get_all()
    installer = next((i for i in installers if i.get('username') == username and i.get('password') == password), None)
    if installer:
        return {
            'id': installer['id'],
            'username': installer['username'],
            'nome': installer.get('nome', installer['username']),
            'role': 'user',
            'tipo': 'instalador'
        }
    
    return None


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('plans.list_plans'))
    
    init_default_users()
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        user = find_user_for_login(username, password)
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['nome'] = user['nome']
            session['tipo'] = user['tipo']
            flash(f'Bem-vindo, {user["nome"]}!', 'success')
            return redirect(url_for('plans.list_plans'))
        
        flash('Usuário ou senha incorretos.', 'error')
    
    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Você saiu do sistema.', 'success')
    return redirect(url_for('auth.login'))

