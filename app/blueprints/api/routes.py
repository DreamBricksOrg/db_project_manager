"""API Routes - HTMX autocomplete endpoints"""

from flask import request, render_template_string

from app.blueprints.api import api_bp
from app.blueprints.auth.routes import login_required
from app.repositories import (
    contacts_repo, producers_repo, installers_repo, 
    services_repo, materials_repo, plans_repo,
    tools_repo, clients_repo, equipment_repo
)


AUTOCOMPLETE_TEMPLATE = '''
{% for item in items %}
<div class="autocomplete-item" 
     onclick="selectAutocomplete(this, '{{ target_input }}', '{{ item.value }}')">
    {{ item.label }}
</div>
{% endfor %}
{% if not items %}
<div class="autocomplete-item" style="color: #64748b; cursor: default;">
    Nenhum resultado encontrado
</div>
{% endif %}
'''


@api_bp.route('/autocomplete/clients')
@login_required
def autocomplete_clients():
    query = request.args.get('q', '').lower()
    target = request.args.get('target', 'cliente')
    
    # Use Clients Repository
    clients = clients_repo.get_all()
    items = [{'value': c['nome'], 'label': c['nome']} for c in clients if query in c['nome'].lower()][:10]
    
    # Fallback to existing unique values if repo empty (optional transition strategy)
    if not items:
        legacy_clients = plans_repo.get_unique_values('cliente')
        items = [{'value': c, 'label': c} for c in legacy_clients if query in c.lower()][:10]
        
    return render_template_string(AUTOCOMPLETE_TEMPLATE, items=items, target_input=target)


@api_bp.route('/autocomplete/contacts')
@login_required
def autocomplete_contacts():
    query = request.args.get('q', '').lower()
    target = request.args.get('target', 'contato_cliente')
    contacts = contacts_repo.get_all()
    items = [
        {'value': c['nome'], 'label': f"{c['nome']} - {c['telefone']}"}
        for c in contacts if query in c['nome'].lower()
    ][:10]
    return render_template_string(AUTOCOMPLETE_TEMPLATE, items=items, target_input=target)


@api_bp.route('/autocomplete/contacts/phone')
@login_required
def get_contact_phone():
    """Return phone when a contact is selected"""
    nome = request.args.get('nome', '')
    
    # Check Contacts
    contacts = contacts_repo.get_all()
    contact = next((c for c in contacts if c['nome'] == nome), None)
    if contact:
        return contact.get('telefone', '')
        
    # Check Producers
    producers = producers_repo.get_all()
    producer = next((p for p in producers if p['nome'] == nome), None)
    if producer:
        return producer.get('telefone', '')
        
    return ''


@api_bp.route('/autocomplete/producers')
@login_required
def autocomplete_producers():
    query = request.args.get('q', '').lower()
    target = request.args.get('target', 'produtor_responsavel')
    producers = producers_repo.get_all()
    items = [
        {'value': p['nome'], 'label': p['nome']}
        for p in producers if query in p['nome'].lower()
    ][:10]
    return render_template_string(AUTOCOMPLETE_TEMPLATE, items=items, target_input=target)


@api_bp.route('/autocomplete/materials')
@login_required
def autocomplete_materials():
    query = request.args.get('q', '').lower()
    materials = materials_repo.get_all()
    items = [
        {'value': m['nome'], 'label': m['nome']}
        for m in materials if query in m['nome'].lower()
    ][:10]
    return render_template_string(AUTOCOMPLETE_TEMPLATE, items=items, target_input='material_input')


@api_bp.route('/autocomplete/tools')
@login_required
def autocomplete_tools():
    query = request.args.get('q', '').lower()
    tools = tools_repo.get_all()
    items = [
        {'value': t['nome'], 'label': t['nome']}
        for t in tools if query in t['nome'].lower()
    ][:10]
    return render_template_string(AUTOCOMPLETE_TEMPLATE, items=items, target_input='tool_input')


@api_bp.route('/autocomplete/equipment')
@login_required
def autocomplete_equipment():
    query = request.args.get('q', '').lower()
    equipment = equipment_repo.get_all()
    items = [
        {'value': e['nome'], 'label': e['nome']}
        for e in equipment if query in e['nome'].lower()
    ][:10]
    return render_template_string(AUTOCOMPLETE_TEMPLATE, items=items, target_input='equipment_input')


@api_bp.route('/autocomplete/services')
@login_required
def autocomplete_services():
    query = request.args.get('q', '').lower()
    services = services_repo.get_all()
    items = [
        {'value': s['tipo_servico'], 'label': f"{s['tipo_servico']} - {s['responsavel']}"}
        for s in services if query in s['tipo_servico'].lower()
    ][:10]
    return render_template_string(AUTOCOMPLETE_TEMPLATE, items=items, target_input='servico_tipo')


@api_bp.route('/autocomplete/installers')
@login_required
def autocomplete_installers():
    query = request.args.get('q', '').lower()
    installers = installers_repo.get_all()
    items = [
        {'value': i['id'], 'label': f"{i['nome']} ({i.get('especialidade', 'Geral')})"}
        for i in installers if query in i['nome'].lower()
    ][:10]
    return render_template_string(AUTOCOMPLETE_TEMPLATE, items=items, target_input='installer_input')


@api_bp.route('/installer/<id>')
@login_required
def get_installer(id):
    """Get installer info by ID"""
    installer = installers_repo.get_by_id(id)
    if installer:
        return {'id': installer['id'], 'nome': installer['nome'], 'especialidade': installer.get('especialidade', '')}
    return {'error': 'not found'}, 404
