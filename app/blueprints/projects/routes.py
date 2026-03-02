import os
import io
import json
from datetime import datetime
from flask import render_template, redirect, url_for, request, flash, current_app, send_file
from werkzeug.utils import secure_filename
from app.blueprints.projects import projects_bp
from app.blueprints.auth.routes import login_required
from app.repositories import projects_repo, plans_repo, graphics_repo, equipment_repo

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf'}

# Fields that are mirrored between Project and InstallationPlan (project_field -> plan_field)
PROJECT_TO_PLAN_FIELD_MAP = {
    'nome': 'nome_projeto',
    'cliente': 'cliente',
    'endereco': 'endereco',
    'descricao': 'descricao',
    'data_instalacao': 'data_instalacao',
    'data_remocao': 'data_remocao',
    'inicio_veiculacao': 'inicio_veiculacao',
    'fim_veiculacao': 'fim_veiculacao',
    'produtor_db': 'produtor_responsavel',
}


def _sync_project_to_plan(project_id: str, project_data: dict) -> None:
    """After saving a project, propagate shared fields to the linked plan."""
    linked_plan = next((p for p in plans_repo.get_all() if p.get('project_id') == project_id), None)
    if not linked_plan:
        return
    updates = {plan_field: project_data[proj_field]
               for proj_field, plan_field in PROJECT_TO_PLAN_FIELD_MAP.items()
               if proj_field in project_data}
    if updates:
        plans_repo.update(linked_plan['id'], {**linked_plan, **updates})


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_date_br(iso_date):
    if not iso_date: return ''
    try:
        dt = datetime.strptime(iso_date, '%Y-%m-%d')
        return dt.strftime('%d/%m/%Y')
    except ValueError:
        return iso_date

def parse_date_br(br_date):
    if not br_date: return ''
    try:
        dt = datetime.strptime(br_date, '%d/%m/%Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return br_date

@projects_bp.route('/')
@login_required
def list_projects():
    q = request.args.get('q', '').strip().lower()
    status_filter = request.args.get('status', '')
    
    projects = projects_repo.get_all()
    
    # Filter
    filtered = []
    for p in projects:
        if status_filter and p.get('status', '') != status_filter:
            continue
        if q:
            searchable = ' '.join([
                p.get('nome', ''), p.get('cliente', ''),
                p.get('endereco', ''), p.get('descricao', ''),
            ]).lower()
            if q not in searchable:
                continue
        filtered.append(p)
    
    # Sort (before date formatting)
    sort_by = request.args.get('sort_by', '')
    sort_dir = request.args.get('sort_dir', 'asc')
    
    SORT_KEYS = {
        'nome': lambda p: (p.get('nome') or '').lower(),
        'cliente': lambda p: (p.get('cliente') or '').lower(),
        'data': lambda p: p.get('data_instalacao') or '',
        'status': lambda p: (p.get('status') or '').lower(),
    }
    if sort_by in SORT_KEYS:
        filtered.sort(key=SORT_KEYS[sort_by], reverse=(sort_dir == 'desc'))
    
    total_items = len(filtered)
    
    # Format dates for display
    for p in filtered:
        p['data_instalacao'] = format_date_br(p.get('data_instalacao', ''))
    
    # Pagination
    ALLOWED_PER_PAGE = [12, 24, 48]
    try:
        per_page = int(request.args.get('per_page', 12))
    except (ValueError, TypeError):
        per_page = 12
    if per_page not in ALLOWED_PER_PAGE:
        per_page = 12
    
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(page, total_pages)
    paginated = filtered[(page - 1) * per_page : page * per_page]
    
    status_options = ['Não Iniciado', 'Em Andamento', 'Testes', 'Instalado', 'Concluído']
    
    return render_template('projects/list.html',
                         projects=paginated,
                         total_items=total_items,
                         page=page,
                         total_pages=total_pages,
                         per_page=per_page,
                         sort_by=sort_by,
                         sort_dir=sort_dir,
                         q=q,
                         status_filter=status_filter,
                         status_options=status_options)

@projects_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        return save_project(None)
    
    return render_template('projects/form.html', project={})

@projects_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(id):
    project = projects_repo.get_by_id(id)
    if not project:
        flash('Projeto não encontrado.', 'error')
        return redirect(url_for('projects.list_projects'))
    
    if request.method == 'POST':
        return save_project(id)
    
    # Dates are already ISO in DB, which works for <input type="date">
    # No formatting needed for edit form
    
    return render_template('projects/form.html', project=project)

@projects_bp.route('/<id>')
@login_required
def view_project(id):
    project = projects_repo.get_by_id(id)
    if not project:
        flash('Projeto não encontrado.', 'error')
        return redirect(url_for('projects.list_projects'))
    
    # Format display dates
    project['data_instalacao'] = format_date_br(project.get('data_instalacao', ''))
    project['data_remocao'] = format_date_br(project.get('data_remocao', ''))
    project['inicio_veiculacao'] = format_date_br(project.get('inicio_veiculacao', ''))
    project['fim_veiculacao'] = format_date_br(project.get('fim_veiculacao', ''))
    
    # Format datas parciais
    for item in project.get('datas_parciais', []):
        if isinstance(item, dict) and 'data' in item:
            item['data'] = format_date_br(item.get('data', ''))
            
    # Check for child entities
    plan = next((p for p in plans_repo.get_all() if p.get('project_id') == id), None)
    graphics = next((g for g in graphics_repo.get_all() if g.get('project_id') == id), None)
    equipment = next((e for e in equipment_repo.get_all() if e.get('project_id') == id), None)
    
    return render_template('projects/view.html', 
                         project=project, 
                         plan=plan, 
                         graphics=graphics, 
                         equipment=equipment)

@projects_bp.route('/<id>/plan-redirect')
@login_required
def view_plan_redirect(id):
    # Check if a plan exists for this project
    plans = [p for p in plans_repo.get_all() if p.get('project_id') == id]
    if plans:
        # Redirect to the existing plan (enforcing 1-1)
        return redirect(url_for('plans.view_plan', id=plans[0]['id']))
    else:
        # Redirect to create new plan with pre-filled project_id
        return redirect(url_for('plans.new_plan', project_id=id))

@projects_bp.route('/<id>/graphics', methods=['GET', 'POST'])
@login_required
def graphic_specs(id):
    project = projects_repo.get_by_id(id)
    if not project:
        return redirect(url_for('projects.list_projects'))
        
    specs = next((g for g in graphics_repo.get_all() if g.get('project_id') == id), None)
    
    if request.method == 'POST':
        data = {
            'project_id': id,
            'cor_envelopamento': request.form.get('cor_envelopamento', ''),
            'cor_hex': request.form.get('cor_hex', '#000000'),
            'previsao_chegada_cor': request.form.get('previsao_chegada_cor', ''),
            'previsao_chegada_arq': request.form.get('previsao_chegada_arq', ''),
        }
        
        # Handle file uploads for print files
        existing_files = specs.get('arquivos_impressao', []) if specs else []
        if not isinstance(existing_files, list):
            existing_files = []
        
        if 'arquivos_impressao' in request.files:
            files = request.files.getlist('arquivos_impressao')
            for f in files:
                if f and allowed_file(f.filename):
                    fname = secure_filename(f"gfx_{id}_{f.filename}")
                    f.save(os.path.join(current_app.config['UPLOAD_DIR'], fname))
                    existing_files.append(fname)
        
        data['arquivos_impressao'] = existing_files
        
        # Handle file removal
        remove_files = request.form.getlist('remove_file')
        if remove_files:
            data['arquivos_impressao'] = [f for f in data['arquivos_impressao'] if f not in remove_files]
        
        if specs:
            graphics_repo.update(specs['id'], data)
        else:
            graphics_repo.create(data)
            
        flash('Especificações gráficas salvas.', 'success')
        return redirect(url_for('projects.graphic_specs', id=id))
    
    # Format dates for display
    if specs:
        specs['previsao_chegada_cor'] = specs.get('previsao_chegada_cor', '')
        specs['previsao_chegada_arq'] = specs.get('previsao_chegada_arq', '')
        # Ensure arquivos_impressao is a list
        if not isinstance(specs.get('arquivos_impressao'), list):
            specs['arquivos_impressao'] = []
        
    return render_template('projects/graphics_form.html', project=project, specs=specs or {})

@projects_bp.route('/<id>/equipment', methods=['GET', 'POST'])
@login_required
def equipment_list(id):
    project = projects_repo.get_by_id(id)
    if not project:
        return redirect(url_for('projects.list_projects'))
        
    eq_list = next((e for e in equipment_repo.get_all() if e.get('project_id') == id), None)
    
    if request.method == 'POST':
        # items are probably passed as a list named 'itens' or similar
        items = request.form.getlist('itens[]')
        items = [i.strip() for i in items if i.strip()]
        
        data = {
            'project_id': id,
            'itens': items
        }
        
        if eq_list:
            equipment_repo.update(eq_list['id'], data)
        else:
            equipment_repo.create(data)
            
        flash('Lista de equipamentos salva.', 'success')
        return redirect(url_for('projects.equipment_list', id=id))

    return render_template('projects/equipment_form.html', project=project, equipment=eq_list or {})

def save_project(id):
    data = {
        'nome': request.form.get('nome', '').strip(),
        'cliente': request.form.get('cliente', '').strip(),
        'produtor_db': request.form.get('produtor_db', '').strip(),
        'produtor_db_contato': request.form.get('produtor_db_contato', '').strip(),
        'produtor_ext': request.form.get('produtor_ext', '').strip(),
        'produtor_ext_contato': request.form.get('produtor_ext_contato', '').strip(),
        # Dates come as ISO 'YYYY-MM-DD' from type="date"
        'data_instalacao': request.form.get('data_instalacao', ''),
        'data_remocao': request.form.get('data_remocao', ''),
        'inicio_veiculacao': request.form.get('inicio_veiculacao', ''),
        'fim_veiculacao': request.form.get('fim_veiculacao', ''),
        'endereco': request.form.get('endereco', '').strip(),
        'descricao': request.form.get('descricao', '').strip(),
        # 'link_drive' removed from form
        'status': request.form.get('status', 'Em Andamento'),
        'conclusao': int(request.form.get('conclusao', 0)),
    }
    
    # Handle Datas Parciais (List of Objects)
    dates = request.form.getlist('datas_parciais_data[]')
    descs = request.form.getlist('datas_parciais_desc[]')
    
    # Zip them into list of dicts
    data['datas_parciais'] = []
    if dates:
        for dt, desc in zip(dates, descs):
            if dt.strip():
                data['datas_parciais'].append({
                    'data': dt.strip(),
                    'descricao': desc.strip()
                })

    # Handle Files
    # imagem_referencia
    if 'imagem_referencia' in request.files:
        f = request.files['imagem_referencia']
        if f and allowed_file(f.filename):
            fname = secure_filename(f"ref_{id or 'new'}_{f.filename}")
            f.save(os.path.join(current_app.config['UPLOAD_DIR'], fname))
            data['imagem_referencia'] = fname
            
    # foto_layout
    if 'foto_layout' in request.files:
        f = request.files['foto_layout']
        if f and allowed_file(f.filename):
            fname = secure_filename(f"layout_{id or 'new'}_{f.filename}")
            f.save(os.path.join(current_app.config['UPLOAD_DIR'], fname))
            data['foto_layout'] = fname
            
    # galeria (multiple)
    if 'galeria' in request.files:
        files = request.files.getlist('galeria')
        saved_files = []
        for f in files:
            if f and allowed_file(f.filename):
                fname = secure_filename(f"galeria_{id or 'new'}_{f.filename}")
                f.save(os.path.join(current_app.config['UPLOAD_DIR'], fname))
                saved_files.append(fname)
        
        # If editing, extend existing gallery? 
        # For now, let's just append if id exists
        if id:
             existing = projects_repo.get_by_id(id)
             old_gallery = existing.get('galeria', []) if existing else []
             if isinstance(old_gallery, list):
                 saved_files = old_gallery + saved_files
        
        data['galeria'] = saved_files

    if not data['nome']:
        flash('Nome do projeto é obrigatório.', 'error')
        return render_template('projects/form.html', project=request.form) # incomplete

    if id:
        projects_repo.update(id, data)
        _sync_project_to_plan(id, data)
        flash('Projeto atualizado.', 'success')
        return redirect(url_for('projects.view_project', id=id))
    else:
        new_proj = projects_repo.create(data)
        flash('Projeto criado.', 'success')
        return redirect(url_for('projects.view_project', id=new_proj['id']))
