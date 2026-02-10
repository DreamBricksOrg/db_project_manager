"""Admin Routes - CRUD for contacts, producers, installers, services, materials"""

from flask import render_template, redirect, url_for, request, flash

from app.blueprints.admin import admin_bp
from app.blueprints.auth.routes import admin_required
from app.repositories import contacts_repo, producers_repo, installers_repo, services_repo, materials_repo, tools_repo


@admin_bp.route('/')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html')


# ============ CONTACTS ============
@admin_bp.route('/contacts')
@admin_required
def list_contacts():
    contacts = contacts_repo.get_all()
    return render_template('admin/contacts/list.html', contacts=contacts)


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
    return render_template('admin/contacts/form.html', contact=None);


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
    return render_template('admin/producers/list.html', producers=producers)


@admin_bp.route('/producers/new', methods=['GET', 'POST'])
@admin_required
def new_producer():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'username': request.form.get('username', '').strip(),
            'password': request.form.get('password', '').strip()
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
            'email': request.form.get('email', '').strip(),
            'username': request.form.get('username', '').strip(),
            'password': request.form.get('password', '').strip()
        }
        # Keep old password if not provided
        if not data['password']:
            data['password'] = producer.get('password', '')
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
    return render_template('admin/installers/list.html', installers=installers)


@admin_bp.route('/installers/new', methods=['GET', 'POST'])
@admin_required
def new_installer():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip(),
            'telefone': request.form.get('telefone', '').strip(),
            'email': request.form.get('email', '').strip(),
            'especialidade': request.form.get('especialidade', '').strip(),
            'username': request.form.get('username', '').strip(),
            'password': request.form.get('password', '').strip()
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
            'especialidade': request.form.get('especialidade', '').strip(),
            'username': request.form.get('username', '').strip(),
            'password': request.form.get('password', '').strip()
        }
        # Keep old password if not provided
        if not data['password']:
            data['password'] = installer.get('password', '')
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
    return render_template('admin/services/list.html', services=services)


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


# ============ MATERIALS ============
@admin_bp.route('/materials')
@admin_required
def list_materials():
    materials = materials_repo.get_all()
    return render_template('admin/materials/list.html', materials=materials)


@admin_bp.route('/materials/new', methods=['GET', 'POST'])
@admin_required
def new_material():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip()
        }
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
    return render_template('admin/tools/list.html', tools=tools)


@admin_bp.route('/tools/new', methods=['GET', 'POST'])
@admin_required
def new_tool():
    if request.method == 'POST':
        data = {
            'nome': request.form.get('nome', '').strip()
        }
        
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
