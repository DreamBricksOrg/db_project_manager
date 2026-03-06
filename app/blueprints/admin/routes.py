"""Admin Routes - CRUD for contacts, producers, installers, services, materials"""

from flask import render_template, redirect, url_for, request, flash

from app.blueprints.admin import admin_bp
from app.blueprints.auth.routes import admin_required
from app.repositories import contacts_repo, producers_repo, installers_repo, services_repo, materials_repo, tools_repo, clients_repo, equipment_repo, users_repo


def paginate_list(items, search_fields=None):
    """Shared pagination + search for admin lists."""
    q = request.args.get('q', '').strip().lower()
    
    if q and search_fields:
        items = [i for i in items if any(q in str(i.get(f, '')).lower() for f in search_fields)]
    
    total_items = len(items)
    
    ALLOWED = [10, 25, 50]
    try:
        per_page = int(request.args.get('per_page', 10))
    except (ValueError, TypeError):
        per_page = 10
    if per_page not in ALLOWED:
        per_page = 10
    
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(page, total_pages)
    
    return {
        'items': items[(page - 1) * per_page : page * per_page],
        'page': page,
        'total_pages': total_pages,
        'total_items': total_items,
        'per_page': per_page,
        'q': q,
    }


@admin_bp.route('/')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')


# ============ USERS ============
@admin_bp.route('/users')
@admin_required
def list_users():
    users = users_repo.get_all()
    users.sort(key=lambda x: x.get('nome', '').lower())
    pg = paginate_list(users, search_fields=['nome', 'username'])
    return render_template('admin/users/list.html', users=pg['items'], list_endpoint='admin.list_users', **pg)


@admin_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def new_user():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'username': request.form.get('username', '').strip(),
            'password': request.form.get('password', '').strip(),
            'role': request.form.get('role', 'user'),
            'active': request.form.get('active') == 'true'
        }
        
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            # Check if username exists (only if provided)
            if data['username']:
                existing = next((u for u in users_repo.get_all() if u.get('username') == data['username']), None)
                if existing:
                    flash('Nome de usuário já existe.', 'error')
                    return render_template('admin/users/form.html', user=None)

            users_repo.create(data)
            flash('Usuário criado com sucesso!', 'success')
            return redirect(url_for('admin.list_users'))
    
    return render_template('admin/users/form.html', user=None)


@admin_bp.route('/users/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(id):
    user = users_repo.get_by_id(id)
    if not user:
        flash('Usuário não encontrado.', 'error')
        return redirect(url_for('admin.list_users'))
        
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'username': request.form.get('username', '').strip(),
            'role': request.form.get('role', 'user'),
            'active': request.form.get('active') == 'true'
        }
        
        password = request.form.get('password', '').strip()
        if password:
            data['password'] = password
            
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            # Check if username exists (if changed and provided)
            if data['username'] and data['username'] != user.get('username'):
                existing = next((u for u in users_repo.get_all() if u.get('username') == data['username']), None)
                if existing:
                    flash('Nome de usuário já existe.', 'error')
                    return render_template('admin/users/form.html', user=user)

            users_repo.update(id, data)
            flash('Usuário atualizado!', 'success')
            return redirect(url_for('admin.list_users'))
    
    return render_template('admin/users/form.html', user=user)


@admin_bp.route('/users/<id>/delete', methods=['POST'])
@admin_required
def delete_user(id):
    user = users_repo.get_by_id(id)
    if user and user.get('username') == 'admin':
        flash('Não é possível excluir o administrador principal.', 'error')
    else:
        users_repo.delete(id)
        flash('Usuário removido.', 'success')
    return redirect(url_for('admin.list_users'))


# ============ CLIENTS ============
@admin_bp.route('/clients')
@admin_required
def list_clients():
    clients = clients_repo.get_all()
    pg = paginate_list(clients, search_fields=['nome', 'email', 'telefone'])
    return render_template('admin/clients/list.html', clients=pg['items'], list_endpoint='admin.list_clients', **pg)


@admin_bp.route('/clients/new', methods=['GET', 'POST'])
@admin_required
def new_client():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'email': request.form.get('email', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'documento': request.form.get('documento', '').strip()
        }
        
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
            return render_template('admin/clients/form.html', client=None)
            
        clients_repo.create(data)
        flash('Cliente criado com sucesso!', 'success')
        return redirect(url_for('admin.list_clients'))
    
    return render_template('admin/clients/form.html', client=None)


@admin_bp.route('/clients/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_client(id):
    client = clients_repo.get_by_id(id)
    if not client:
        flash('Cliente não encontrado.', 'error')
        return redirect(url_for('admin.list_clients'))
        
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'email': request.form.get('email', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'documento': request.form.get('documento', '').strip()
        }
        
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            clients_repo.update(id, data)
            flash('Cliente atualizado!', 'success')
            return redirect(url_for('admin.list_clients'))
    
    return render_template('admin/clients/form.html', client=client)


@admin_bp.route('/clients/<id>/delete', methods=['POST'])
@admin_required
def delete_client(id):
    clients_repo.delete(id)
    flash('Cliente removido.', 'success')
    return redirect(url_for('admin.list_clients'))


# ============ CONTACTS ============
@admin_bp.route('/contacts')
@admin_required
def list_contacts():
    contacts = contacts_repo.get_all()
    pg = paginate_list(contacts, search_fields=['nome', 'email', 'telefone'])
    return render_template('admin/contacts/list.html', contacts=pg['items'], list_endpoint='admin.list_contacts', **pg)


@admin_bp.route('/contacts/new', methods=['GET', 'POST'])
@admin_required
def new_contact():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip()
        }
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            contacts_repo.create(data)
            flash('Contato criado com sucesso!', 'success')
            return redirect(url_for('admin.list_contacts'))
    return render_template('admin/contacts/form.html', contact=None)


@admin_bp.route('/contacts/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_contact(id):
    contact = contacts_repo.get_by_id(id)
    if not contact:
        flash('Contato não encontrado.', 'error')
        return redirect(url_for('admin.list_contacts'))
    
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip()
        }
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            contacts_repo.update(id, data)
            flash('Contato atualizado!', 'success')
            return redirect(url_for('admin.list_contacts'))
    
    return render_template('admin/contacts/form.html', contact=contact)


@admin_bp.route('/contacts/<id>/delete', methods=['POST'])
@admin_required
def delete_contact(id):
    contacts_repo.delete(id)
    flash('Contato removido.', 'success')
    return redirect(url_for('admin.list_contacts'))


# ============ PRODUCERS ============
@admin_bp.route('/producers')
@admin_required
def list_producers():
    producers = producers_repo.get_all()
    pg = paginate_list(producers, search_fields=['nome', 'email', 'telefone'])
    return render_template('admin/producers/list.html', producers=pg['items'], list_endpoint='admin.list_producers', **pg)



@admin_bp.route('/producers/new', methods=['GET', 'POST'])
@admin_required
def new_producer():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip()
        }
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            producers_repo.create(data)
            flash('Produtor criado com sucesso!', 'success')
            return redirect(url_for('admin.list_producers'))
    return render_template('admin/producers/form.html', producer=None)



@admin_bp.route('/producers/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_producer(id):
    producer = producers_repo.get_by_id(id)
    if not producer:
        flash('Produtor não encontrado.', 'error')
        return redirect(url_for('admin.list_producers'))
    
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip()
        }

        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            producers_repo.update(id, data)
            flash('Produtor atualizado!', 'success')
            return redirect(url_for('admin.list_producers'))
    
    return render_template('admin/producers/form.html', producer=producer)


@admin_bp.route('/producers/<id>/delete', methods=['POST'])
@admin_required
def delete_producer(id):
    producers_repo.delete(id)
    flash('Produtor removido.', 'success')
    return redirect(url_for('admin.list_producers'))


# ============ INSTALLERS ============
@admin_bp.route('/installers')
@admin_required
def list_installers():
    installers = installers_repo.get_all()
    pg = paginate_list(installers, search_fields=['nome', 'email', 'especialidade'])
    return render_template('admin/installers/list.html', installers=pg['items'], list_endpoint='admin.list_installers', **pg)



@admin_bp.route('/installers/new', methods=['GET', 'POST'])
@admin_required
def new_installer():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'especialidade': request.form.get('especialidade', '').strip()
        }
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            installers_repo.create(data)
            flash('Instalador criado com sucesso!', 'success')
            return redirect(url_for('admin.list_installers'))
    return render_template('admin/installers/form.html', installer=None)



@admin_bp.route('/installers/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_installer(id):
    installer = installers_repo.get_by_id(id)
    if not installer:
        flash('Instalador não encontrado.', 'error')
        return redirect(url_for('admin.list_installers'))
    
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'especialidade': request.form.get('especialidade', '').strip()
        }

        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            installers_repo.update(id, data)
            flash('Instalador atualizado!', 'success')
            return redirect(url_for('admin.list_installers'))
    
    return render_template('admin/installers/form.html', installer=installer)


@admin_bp.route('/installers/<id>/delete', methods=['POST'])
@admin_required
def delete_installer(id):
    installers_repo.delete(id)
    flash('Instalador removido.', 'success')
    return redirect(url_for('admin.list_installers'))


# ============ EXTERNAL SERVICES ============
@admin_bp.route('/services')
@admin_required
def list_services():
    services = services_repo.get_all()
    pg = paginate_list(services, search_fields=['tipo_servico', 'responsavel'])
    return render_template('admin/services/list.html', services=pg['items'], list_endpoint='admin.list_services', **pg)


@admin_bp.route('/services/new', methods=['GET', 'POST'])
@admin_required
def new_service():
    if request.method == 'POST':
        data = {
            'tipo_servico': request.form.get('tipo_servico', '').strip(),
            'responsavel': request.form.get('responsavel', '').strip()
        }
        if not data['tipo_servico']:
            flash('Tipo de serviço é obrigatório.', 'error')
        else:
            services_repo.create(data)
            flash('Serviço criado com sucesso!', 'success')
            return redirect(url_for('admin.list_services'))
    return render_template('admin/services/form.html', service=None)


@admin_bp.route('/services/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_service(id):
    service = services_repo.get_by_id(id)
    if not service:
        flash('Serviço não encontrado.', 'error')
        return redirect(url_for('admin.list_services'))
    
    if request.method == 'POST':
        data = {
            'tipo_servico': request.form.get('tipo_servico', '').strip(),
            'responsavel': request.form.get('responsavel', '').strip()
        }
        if not data['tipo_servico']:
            flash('Tipo de serviço é obrigatório.', 'error')
        else:
            services_repo.update(id, data)
            flash('Serviço atualizado!', 'success')
            return redirect(url_for('admin.list_services'))
    
    return render_template('admin/services/form.html', service=service)


@admin_bp.route('/services/<id>/delete', methods=['POST'])
@admin_required
def delete_service(id):
    services_repo.delete(id)
    flash('Serviço removido.', 'success')
    return redirect(url_for('admin.list_services'))


# ============ HELPER FUNCTIONS for UPLOADS ============
import os
import uuid
from werkzeug.utils import secure_filename
from flask import current_app

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_image(file):
    if file and allowed_file(file.filename):
        original_filename = secure_filename(file.filename)
        extension = original_filename.rsplit('.', 1)[1].lower()
        new_filename = f"{uuid.uuid4().hex}.{extension}"
        
        upload_folder = current_app.config['UPLOAD_DIR']
        os.makedirs(upload_folder, exist_ok=True)
        
        file.save(os.path.join(upload_folder, new_filename))
        return f"uploads/{new_filename}"
    return None

# ============ MATERIALS ============
@admin_bp.route('/materials')
@admin_required
def list_materials():
    materials = materials_repo.get_all()
    pg = paginate_list(materials, search_fields=['nome'])
    return render_template('admin/materials/list.html', materials=pg['items'], list_endpoint='admin.list_materials', **pg)


@admin_bp.route('/materials/new', methods=['GET', 'POST'])
@admin_required
def new_material():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip()
        }
        
        image_path = save_image(request.files.get('image'))
        if image_path:
            data['image'] = image_path

        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            materials_repo.create(data)
            flash('Material criado com sucesso!', 'success')
            return redirect(url_for('admin.list_materials'))
    return render_template('admin/materials/form.html', material=None)


@admin_bp.route('/materials/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_material(id):
    material = materials_repo.get_by_id(id)
    if not material:
        flash('Material não encontrado.', 'error')
        return redirect(url_for('admin.list_materials'))
    
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip()
        }
        
        image_path = save_image(request.files.get('image'))
        if image_path:
            data['image'] = image_path
            
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            materials_repo.update(id, data)
            flash('Material atualizado!', 'success')
            return redirect(url_for('admin.list_materials'))
    
    return render_template('admin/materials/form.html', material=material)


@admin_bp.route('/materials/<id>/delete', methods=['POST'])
@admin_required
def delete_material(id):
    materials_repo.delete(id)
    flash('Material removido.', 'success')
    return redirect(url_for('admin.list_materials'))


# ============ TOOLS ============

@admin_bp.route('/tools')
@admin_required
def list_tools():
    tools = tools_repo.get_all()
    pg = paginate_list(tools, search_fields=['nome'])
    return render_template('admin/tools/list.html', tools=pg['items'], list_endpoint='admin.list_tools', **pg)


@admin_bp.route('/tools/new', methods=['GET', 'POST'])
@admin_required
def new_tool():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip()
        }
        
        image_path = save_image(request.files.get('image'))
        if image_path:
            data['image'] = image_path
        
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
            return render_template('admin/tools/form.html', tool=None)
            
        tools_repo.create(data)
        flash('Ferramenta criada com sucesso!', 'success')
        return redirect(url_for('admin.list_tools'))
    
    return render_template('admin/tools/form.html', tool=None)


@admin_bp.route('/tools/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_tool(id):
    tool = tools_repo.get_by_id(id)
    if not tool:
        flash('Ferramenta não encontrada.', 'error')
        return redirect(url_for('admin.list_tools'))
        
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip()
        }
        
        image_path = save_image(request.files.get('image'))
        if image_path:
            data['image'] = image_path
        
        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            tools_repo.update(id, data)
            flash('Ferramenta atualizada!', 'success')
            return redirect(url_for('admin.list_tools'))
    
    return render_template('admin/tools/form.html', tool=tool)


@admin_bp.route('/tools/<id>/delete', methods=['POST'])
@admin_required
def delete_tool(id):
    tools_repo.delete(id)
    flash('Ferramenta removida.', 'success')
    return redirect(url_for('admin.list_tools'))


# ============ EQUIPMENT ============

@admin_bp.route('/equipment')
@admin_required
def list_equipment():
    equipment = equipment_repo.get_all()
    pg = paginate_list(equipment, search_fields=['nome'])
    return render_template('admin/equipment/list.html', equipment=pg['items'], list_endpoint='admin.list_equipment', **pg)


@admin_bp.route('/equipment/new', methods=['GET', 'POST'])
@admin_required
def new_equipment():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip()
        }
        
        image_path = save_image(request.files.get('image'))
        if image_path:
            data['image'] = image_path

        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            equipment_repo.create(data)
            flash('Equipamento criado com sucesso!', 'success')
            return redirect(url_for('admin.list_equipment'))
    return render_template('admin/equipment/form.html', equipment=None)


@admin_bp.route('/equipment/<id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_equipment(id):
    eq = equipment_repo.get_by_id(id)
    if not eq:
        flash('Equipamento não encontrado.', 'error')
        return redirect(url_for('admin.list_equipment'))
    
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip()
        }
        
        image_path = save_image(request.files.get('image'))
        if image_path:
            data['image'] = image_path

        if not data['nome']:
            flash('Nome é obrigatório.', 'error')
        else:
            equipment_repo.update(id, data)
            flash('Equipamento atualizado!', 'success')
            return redirect(url_for('admin.list_equipment'))
    
    return render_template('admin/equipment/form.html', equipment=eq)


@admin_bp.route('/equipment/<id>/delete', methods=['POST'])
@admin_required
def delete_equipment(id):
    equipment_repo.delete(id)
    flash('Equipamento removido.', 'success')
    return redirect(url_for('admin.list_equipment'))
