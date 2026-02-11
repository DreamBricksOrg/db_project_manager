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
    projects = projects_repo.get_all()
    # Format dates for list view
    for p in projects:
        p['data_instalacao'] = format_date_br(p.get('data_instalacao', ''))
    return render_template('projects/list.html', projects=projects)

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
            'previsao_chegada_cor': parse_date_br(request.form.get('previsao_chegada_cor', '')),
            'arquivos_impressao': request.form.get('arquivos_impressao', ''), # or file upload?
            'previsao_chegada_arq': parse_date_br(request.form.get('previsao_chegada_arq', '')),
        }
        
        if specs:
            graphics_repo.update(specs['id'], data)
        else:
            graphics_repo.create(data)
            
        flash('Especificações gráficas salvas.', 'success')
        return redirect(url_for('projects.graphic_specs', id=id))
    
    # Format dates
    if specs:
        specs['previsao_chegada_cor'] = format_date_br(specs.get('previsao_chegada_cor', ''))
        specs['previsao_chegada_arq'] = format_date_br(specs.get('previsao_chegada_arq', ''))
        
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
            
    # layout_rafa
    if 'layout_rafa' in request.files:
        f = request.files['layout_rafa']
        if f and allowed_file(f.filename):
            fname = secure_filename(f"layout_{id or 'new'}_{f.filename}")
            f.save(os.path.join(current_app.config['UPLOAD_DIR'], fname))
            data['layout_rafa'] = fname
            
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
        flash('Projeto atualizado.', 'success')
        return redirect(url_for('projects.view_project', id=id))
    else:
        new_proj = projects_repo.create(data)
        flash('Projeto criado.', 'success')
        return redirect(url_for('projects.view_project', id=new_proj['id']))
