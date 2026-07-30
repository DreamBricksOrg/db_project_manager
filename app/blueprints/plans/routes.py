"""Plans Routes - Installation plans management"""

import calendar
import io
import logging
import os
from datetime import datetime, date
from flask import render_template, redirect, url_for, request, flash, current_app, send_file, jsonify
from werkzeug.utils import secure_filename
from xhtml2pdf import pisa

from app.blueprints.plans import plans_bp
from app.blueprints.auth.routes import login_required, admin_required
from app.querying import merge_filters, read_page, read_sort, text_filter
from app.repositories import (
    plans_repo, contacts_repo, producers_repo,
    installers_repo, services_repo, materials_repo,
    tools_repo, equipment_repo, projects_repo, plan_templates_repo
)

logger = logging.getLogger(__name__)

# Public sort key -> document field. Doubles as an allowlist so an arbitrary
# field name from the query string never reaches the database.
PLAN_SORT_FIELDS = {
    'projeto': 'nome_projeto',
    'cliente': 'cliente',
    'data': 'data_instalacao',
    'endereco': 'endereco',
}

# Fields mirrored between Plan and Project (plan_field -> project_field)
PLAN_TO_PROJECT_FIELD_MAP = {
    'nome_projeto': 'nome',
    'cliente': 'cliente',
    'endereco': 'endereco',
    'descricao': 'descricao',
    'data_instalacao': 'data_instalacao',
    'data_remocao': 'data_remocao',
    'inicio_veiculacao': 'inicio_veiculacao',
    'fim_veiculacao': 'fim_veiculacao',
    'produtor_responsavel': 'produtor_db',
    'status': 'status',
}


def _sync_plan_to_project(project_id: str, plan_data: dict) -> None:
    """After saving a plan, propagate shared fields back to the linked project."""
    project = projects_repo.get_by_id(project_id)
    if not project:
        return
    updates = {proj_field: plan_data[plan_field]
               for plan_field, proj_field in PLAN_TO_PROJECT_FIELD_MAP.items()
               if plan_field in plan_data}
    if updates:
        # $set only what changed instead of rewriting the whole document.
        projects_repo.update(project_id, updates)

# Status colors for the Gantt chart
STATUS_COLORS = {
    'Não Iniciado': '#94a3b8',
    'Em Andamento': '#e2f50b',
    'Testes': '#3bd4f6',
    'Instalado': '#9808e6',
    'Concluído': '#11f018',
}

DEFAULT_PLAN_STATUS = 'Em Andamento'


def get_plan_status(plan):
    """Derive status from plan data, fallback to project if older."""
    if 'status' in plan and plan['status']:
        return plan['status']
    project_id = plan.get('project_id')
    if project_id:
        project = projects_repo.get_by_id(project_id)
        if project and project.get('status'):
            return project['status']
    return DEFAULT_PLAN_STATUS


def annotate_plan_statuses(plans):
    """Set ``_status`` on every plan, resolving fallbacks in one extra query.

    Calling :func:`get_plan_status` in a loop issues one project lookup per
    plan that predates the status field. This resolves them all at once.
    """
    missing_ids = {
        p['project_id'] for p in plans
        if not p.get('status') and p.get('project_id')
    }

    project_status = {}
    if missing_ids:
        project_status = {
            proj['id']: proj.get('status')
            for proj in projects_repo.find({'id': {'$in': list(missing_ids)}})
        }

    for plan in plans:
        if plan.get('status'):
            plan['_status'] = plan['status']
        else:
            plan['_status'] = (
                project_status.get(plan.get('project_id')) or DEFAULT_PLAN_STATUS
            )
    return plans


def format_date_br(iso_date):
    """Convert yyyy-mm-dd to dd/mm/aaaa"""
    if not iso_date:
        return ''
    try:
        dt = datetime.strptime(iso_date, '%Y-%m-%d')
        return dt.strftime('%d/%m/%Y')
    except ValueError:
        return iso_date


def parse_date_br(br_date):
    """Convert dd/mm/aaaa to yyyy-mm-dd"""
    if not br_date:
        return ''
    try:
        dt = datetime.strptime(br_date, '%d/%m/%Y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return br_date


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def parse_iso_date(s):
    """Safely parse an ISO date string, return None on failure."""
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


@plans_bp.route('/')
@login_required
def list_plans():
    q = request.args.get('q', '').strip().lower()
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    
    if 'status' in request.args:
        status_filter = request.args.get('status', '')
    else:
        status_filter = 'Em Andamento'
    
    # Gantt month/year filters (default to current)
    today = date.today()
    try:
        gantt_month = int(request.args.get('gantt_month', today.month))
        gantt_year = int(request.args.get('gantt_year', today.year))
    except (ValueError, TypeError):
        gantt_month = today.month
        gantt_year = today.year
    
    days_in_month = calendar.monthrange(gantt_year, gantt_month)[1]

    # ── Query ────────────────────────────────────────────────────────────
    # Date range and free-text search run in MongoDB. Status cannot: it is
    # derived (plan status, falling back to the linked project), so it is
    # applied below — but only over the already-narrowed result set.
    date_clauses = []
    if start_date:
        date_clauses.append({'$or': [
            {'data_instalacao': {'$gte': start_date}},
            {'data_instalacao': {'$in': [None, '']}},
        ]})
    if end_date:
        date_clauses.append({'$or': [
            {'data_instalacao': {'$lte': end_date}},
            {'data_instalacao': {'$in': [None, '']}},
        ]})

    search_clause = {}
    if q:
        # Installers are stored as IDs on the plan, so resolve the names that
        # match first and search by the resulting IDs.
        matching_installer_ids = [
            i['id'] for i in installers_repo.search('nome', q, limit=100)
        ]
        search_clause = text_filter(q, (
            'nome_projeto', 'cliente', 'contato_cliente',
            'produtor_responsavel', 'endereco', 'materiais',
        ))
        if matching_installer_ids:
            search_clause['$or'].append({'instaladores': {'$in': matching_installer_ids}})

    filters = merge_filters(*date_clauses, search_clause)

    # Sorting happens in MongoDB, on the raw ISO dates, before any formatting.
    sort_by, sort_dir, sort = read_sort(PLAN_SORT_FIELDS, default=[('data_instalacao', 1)])

    filtered_plans = annotate_plan_statuses(plans_repo.find(filters, sort=sort))

    if status_filter:
        filtered_plans = [p for p in filtered_plans if p['_status'] == status_filter]

    # Build Gantt rows - only plans overlapping selected month
    month_start = date(gantt_year, gantt_month, 1)
    month_end = date(gantt_year, gantt_month, days_in_month)
    
    WEEKDAY_NAMES = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
    
    # Build weekday headers
    weekdays = []
    for day_num in range(1, days_in_month + 1):
        d = date(gantt_year, gantt_month, day_num)
        weekdays.append(WEEKDAY_NAMES[d.weekday()])
    
    gantt_rows = []
    for p in filtered_plans:
        plan_start = parse_iso_date(p.get('data_instalacao', ''))
        plan_end = parse_iso_date(p.get('data_remocao', '')) or parse_iso_date(p.get('fim_veiculacao', ''))
        if not plan_end and plan_start:
            plan_end = plan_start
        
        # Only include if plan overlaps the selected month
        if plan_start and plan_end:
            if plan_end < month_start or plan_start > month_end:
                continue
        elif plan_start:
            if plan_start < month_start or plan_start > month_end:
                continue
        else:
            continue
        
        status = p.get('_status', 'Em Andamento')
        color = STATUS_COLORS.get(status, '#3b82f6')
        
        days = []
        for day_num in range(1, days_in_month + 1):
            current_day = date(gantt_year, gantt_month, day_num)
            active = False
            if plan_start and plan_end:
                active = plan_start <= current_day <= plan_end
            elif plan_start:
                active = current_day == plan_start
            days.append({'day': day_num, 'active': active})
        
        gantt_rows.append({
            'id': p.get('id'),
            'project': p.get('nome_projeto', 'Sem Nome'),
            'status': status,
            'color': color,
            'days': days,
        })

    # Pagination. The derived-status filter above runs in Python, so the final
    # count is only known here; the slice stays in Python for the same reason.
    page, per_page = read_page((10, 25, 50))
    total_items = len(filtered_plans)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(page, total_pages)
    paginated_plans = filtered_plans[(page - 1) * per_page: page * per_page]

    # Format dates for display in the table (current page only)
    for p in paginated_plans:
        raw = p.get('data_instalacao', '')
        if raw and '/' not in raw:
            p['data_instalacao'] = format_date_br(raw)

    # Month names for template
    month_names = {
        1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
        5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
        9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
    }

    return render_template('plans/list.html', 
                         plans=paginated_plans,
                         gantt_rows=gantt_rows,
                         gantt_month=gantt_month,
                         gantt_year=gantt_year,
                         days_in_month=days_in_month,
                         weekdays=weekdays,
                         month_names=month_names,
                         status_filter=status_filter,
                         status_options=list(STATUS_COLORS.keys()),
                         page=page,
                         total_pages=total_pages,
                         total_items=total_items,
                         per_page=per_page,
                         sort_by=sort_by,
                         sort_dir=sort_dir,
                         q=q, 
                         start_date=start_date, 
                         end_date=end_date)


@plans_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new_plan():
    if request.method == 'POST':
        return save_plan(None)
    
    plan_data = None
    project_id = request.args.get('project_id')
    template_id = request.args.get('template_id')
    
    if project_id:
        project = projects_repo.get_by_id(project_id)
        if project:
            plan_data = {
                'project_id': project_id,
                'nome_projeto': project.get('nome', ''),
                'cliente': project.get('cliente', ''),
                'produtor_responsavel': project.get('produtor_db', ''),
                'telefone_contato': project.get('produtor_db_contato', ''),
                'endereco': project.get('endereco', ''),
                'descricao': project.get('descricao', ''),
                'data_instalacao': project.get('data_instalacao', ''),
                'data_remocao': project.get('data_remocao', ''),
                'inicio_veiculacao': project.get('inicio_veiculacao', ''),
                'fim_veiculacao': project.get('fim_veiculacao', ''),
                'imagem_referencia': project.get('imagem_referencia', ''),
                'foto_layout': project.get('foto_layout', '')
            }
            flash('Dados pré-preenchidos a partir do Projeto.', 'info')
    
    # Apply template data on top of project data (or standalone)
    if template_id:
        tpl = plan_templates_repo.get_by_id(template_id)
        if tpl:
            if plan_data is None:
                plan_data = {}
            plan_data['descricao'] = tpl.get('descricao', '') or plan_data.get('descricao', '')
            plan_data['servicos_externos'] = tpl.get('servicos_externos', [])
            plan_data['materiais'] = tpl.get('materiais', [])
            plan_data['ferramentas'] = tpl.get('ferramentas', [])
            plan_data['equipamentos'] = tpl.get('equipamentos', [])
            plan_data['informacoes_importantes'] = tpl.get('informacoes_importantes', '')
            flash(f'Template "{tpl.get("nome", "")}" aplicado.', 'info')

    # Load data for autocomplete
    context = get_form_context()
    return render_template('plans/form.html', plan=plan_data, **context)



def hex_to_rgb(hex_color):
    """Convert hex string (e.g., #ffffff) to rgb string (e.g., 255, 255, 255)"""
    if not hex_color or not hex_color.startswith('#'):
        return ''
    h = hex_color.lstrip('#')
    try:
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        return f"{rgb[0]}, {rgb[1]}, {rgb[2]}"
    except ValueError:
        return ''


@plans_bp.route('/<id>')
@login_required
def view_plan(id):
    plan = plans_repo.get_by_id(id)
    if not plan:
        flash('Plano não encontrado.', 'error')
        return redirect(url_for('plans.list_plans'))

    # Format dates for view (View uses convert to BR for display)
    plan['data_instalacao'] = format_date_br(plan.get('data_instalacao', ''))
    plan['data_remocao'] = format_date_br(plan.get('data_remocao', ''))
    plan['inicio_veiculacao'] = format_date_br(plan.get('inicio_veiculacao', ''))
    plan['fim_veiculacao'] = format_date_br(plan.get('fim_veiculacao', ''))

    # Calculate RGB for lighting
    plan['rgb_iluminacao'] = hex_to_rgb(plan.get('cor_iluminacao', ''))

    # Get installer names
    all_installers = {i['id']: i for i in installers_repo.get_all()}
    installer_names = []
    if plan.get('instaladores'):
        installers_list = plan['instaladores'] if isinstance(plan['instaladores'], list) else []
        for inst_id in installers_list:
            if inst_id in all_installers:
                installer_names.append(all_installers[inst_id])

    # Create lookup maps for resources (to get images)
    materials_map = {m['nome']: m for m in materials_repo.get_all()}
    tools_map = {t['nome']: t for t in tools_repo.get_all()}
    equipment_map = {e['nome']: e for e in equipment_repo.get_all()}

    return render_template(
        'plans/view.html', 
        plan=plan, 
        installer_names=installer_names,
        materials_map=materials_map,
        tools_map=tools_map,
        equipment_map=equipment_map
    )


@plans_bp.route('/<id>/pdf')
@login_required
def export_pdf(id):
    plan = plans_repo.get_by_id(id)
    if not plan:
        flash('Plano não encontrado.', 'error')
        return redirect(url_for('plans.list_plans'))

    # Format dates for PDF
    plan_data = plan.copy()
    plan_data['data_instalacao'] = format_date_br(plan.get('data_instalacao', ''))
    plan_data['data_remocao'] = format_date_br(plan.get('data_remocao', ''))
    plan_data['inicio_veiculacao'] = format_date_br(plan.get('inicio_veiculacao', ''))
    plan_data['fim_veiculacao'] = format_date_br(plan.get('fim_veiculacao', ''))

    # Get installer names
    all_installers = {i['id']: i for i in installers_repo.get_all()}
    installer_names = []
    if plan.get('instaladores'):
        installers_list = plan['instaladores'] if isinstance(plan['instaladores'], list) else []
        for inst_id in installers_list:
            if inst_id in all_installers:
                installer_names.append(all_installers[inst_id])

    # Get absolute path for logo
    logo_path = os.path.join(current_app.root_path, 'static', 'images', 'dreambricks_logo_250x160.png')

    # Render template
    html = render_template(
        'plans/pdf_template.html', 
        plan=plan_data, 
        installer_names=installer_names,
        now=datetime.now(),
        logo_path=logo_path
    )

    # Generate PDF
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    
    if not pdf.err:
        result.seek(0)
        filename = f"plano_instalacao_{secure_filename(plan['nome_projeto'])}.pdf"
        return send_file(result, download_name=filename, as_attachment=True)
    
    flash('Erro ao gerar PDF.', 'error')
    return redirect(url_for('plans.view_plan', id=id))


@plans_bp.route('/<id>/edit', methods=['GET', 'POST'])
@login_required
def edit_plan(id):
    plan = plans_repo.get_by_id(id)
    if not plan:
        flash('Plano não encontrado.', 'error')
        return redirect(url_for('plans.list_plans'))

    if request.method == 'POST':
        return save_plan(id)

    # Dates are ISO in DB, suitable for type="date" inputs
    # No formatting needed for edit form

    context = get_form_context()
    return render_template('plans/form.html', plan=plan, **context)


@plans_bp.route('/<id>/delete', methods=['POST'])
@admin_required
def delete_plan(id):
    plan = plans_repo.get_by_id(id)
    if plan and plan.get('foto_layout'):
        # Delete associated image
        try:
            filepath = current_app.config['UPLOAD_DIR'] / plan['foto_layout']
            if filepath.exists():
                filepath.unlink()
        except Exception:
            pass
    
    plans_repo.delete(id)
    flash('Plano removido.', 'success')
    return redirect(url_for('plans.list_plans'))


def get_form_context():
    """Get all data needed for the form autocomplete"""
    return {
        'contacts': contacts_repo.get_all(),
        'producers': producers_repo.get_all(),
        'installers': installers_repo.get_all(),
        'services': services_repo.get_all(),
        'materials': materials_repo.get_all(),
        'tools': tools_repo.get_all(),
        'equipment': equipment_repo.get_all(),
        'existing_clients': plans_repo.get_unique_values('cliente')
    }


def save_plan(plan_id):
    """Save or update a plan"""
    # Get materials from form
    materiais = request.form.getlist('materiais[]')
    
    # Get tools from form
    ferramentas = request.form.getlist('ferramentas[]')

    # Save new tools for future autocomplete
    existing_tools = {t['nome'].lower() for t in tools_repo.get_all()}
    for tool in ferramentas:
        if tool.strip() and tool.strip().lower() not in existing_tools:
            tools_repo.create({'nome': tool.strip()})
            existing_tools.add(tool.strip().lower())

    # Save new materials for future autocomplete
    existing_materials = {m['nome'].lower() for m in materials_repo.get_all()}
    for mat in materiais:
        if mat.strip() and mat.strip().lower() not in existing_materials:
            materials_repo.create({'nome': mat.strip()})
            existing_materials.add(mat.strip().lower())

    # Get equipment from form
    equipamentos = request.form.getlist('equipamentos[]')

    # Save new equipment for future autocomplete
    existing_equipment = {e['nome'].lower() for e in equipment_repo.get_all()}
    for eq in equipamentos:
        if eq.strip() and eq.strip().lower() not in existing_equipment:
            equipment_repo.create({'nome': eq.strip()})
            existing_equipment.add(eq.strip().lower())
    
    # Get external services from form
    servicos_tipos = request.form.getlist('servico_tipo[]')
    servicos_resp = request.form.getlist('servico_responsavel[]')
    servicos_externos = [
        {'tipo': t.strip(), 'responsavel': r.strip()} 
        for t, r in zip(servicos_tipos, servicos_resp) 
        if t.strip()
    ]
    
    data = {
        'nome_projeto': request.form.get('nome_projeto', '').strip(),
        'cliente': request.form.get('cliente', '').strip(),
        'contato_cliente': request.form.get('contato_cliente', '').strip(),
        'telefone_contato': request.form.get('telefone_contato', '').strip(),
        'produtor_responsavel': request.form.get('produtor_responsavel', '').strip(),
        # Use simple get for dates as they come in standard ISO format from type="date"
        'data_instalacao': request.form.get('data_instalacao', ''),
        'data_remocao': request.form.get('data_remocao', ''),
        'inicio_veiculacao': request.form.get('inicio_veiculacao', ''),
        'fim_veiculacao': request.form.get('fim_veiculacao', ''),
        'endereco': request.form.get('endereco', '').strip(),
        'descricao': request.form.get('descricao', '').strip(),
        'instaladores': request.form.getlist('instaladores'),
        'equipe_db': request.form.get('equipe_db', '').strip(),
        'equipe_externa': request.form.get('equipe_externa', '').strip(),
        'servicos_externos': servicos_externos,
        'materiais': materiais,
        'ferramentas': ferramentas,
        'equipamentos': equipamentos,
        'cor_iluminacao': request.form.get('cor_iluminacao', '#ffffff'),
        'informacoes_importantes': request.form.get('informacoes_importantes', '').strip(),
        'status': request.form.get('status', 'Em Andamento'),
    }
    
    # Preserve existing filepaths if not updated
    if plan_id:
        existing = plans_repo.get_by_id(plan_id)
        if existing:
            data['foto_layout'] = existing.get('foto_layout', '')
            data['imagem_referencia'] = existing.get('imagem_referencia', '')
            data['project_id'] = existing.get('project_id', '')

    # Handle New Project ID from URL or Form if creating
    if not plan_id:
        if request.form.get('project_id'):
            data['project_id'] = request.form.get('project_id')
        elif request.args.get('project_id'):
            data['project_id'] = request.args.get('project_id')

    if not data['nome_projeto']:
        flash('Nome do projeto é obrigatório.', 'error')
        # Return data as is (ISO format) for form repopulation
        
        context = get_form_context()
        return render_template('plans/form.html', plan=data if not plan_id else {**plans_repo.get_by_id(plan_id), **data}, **context)
    
    # Handle file uploads
    # Foto Layout
    if 'foto_layout' in request.files and request.files['foto_layout'].filename:
        file = request.files['foto_layout']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"layout_{plan_id or 'new'}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_DIR'], filename)
            file.save(filepath)
            data['foto_layout'] = filename
    elif request.form.get('prefilled_foto_layout'):
        data['foto_layout'] = request.form.get('prefilled_foto_layout')
            
    # Imagem Referencia
    if 'imagem_referencia' in request.files and request.files['imagem_referencia'].filename:
        file = request.files['imagem_referencia']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"ref_{plan_id or 'new'}_{file.filename}")
            filepath = os.path.join(current_app.config['UPLOAD_DIR'], filename)
            file.save(filepath)
            data['imagem_referencia'] = filename
    elif request.form.get('prefilled_imagem_referencia'):
        data['imagem_referencia'] = request.form.get('prefilled_imagem_referencia')
    
    
    if plan_id:
        plans_repo.update(plan_id, data)
        if data.get('project_id'):
            _sync_plan_to_project(data['project_id'], data)
        flash('Plano atualizado!', 'success')
    else:
        plans_repo.create(data)
        flash('Plano criado com sucesso!', 'success')
    
    # Redirect back to Project if linked
    if data.get('project_id'):
        return redirect(url_for('projects.view_project', id=data['project_id']))
        
    return redirect(url_for('plans.list_plans'))


# ---- Template Routes ----

@plans_bp.route('/<id>/save-template', methods=['POST'])
@login_required
def save_template(id):
    """Save current plan data as a reusable template."""
    plan = plans_repo.get_by_id(id)
    if not plan:
        flash('Plano não encontrado.', 'error')
        return redirect(url_for('plans.list_plans'))
    
    nome = request.form.get('template_name', '').strip()
    if not nome:
        flash('Informe um nome para o template.', 'error')
        return redirect(url_for('plans.edit_plan', id=id))
    
    from app.models.entities import generate_id
    template_data = {
        'id': generate_id(),
        'nome': nome,
        'descricao': plan.get('descricao', ''),
        'servicos_externos': plan.get('servicos_externos', []),
        'materiais': plan.get('materiais', []),
        'ferramentas': plan.get('ferramentas', []),
        'equipamentos': plan.get('equipamentos', []),
        'informacoes_importantes': plan.get('informacoes_importantes', ''),
    }
    plan_templates_repo.create(template_data)
    flash(f'Template "{nome}" salvo com sucesso!', 'success')
    return redirect(url_for('plans.edit_plan', id=id))


@plans_bp.route('/templates')
@login_required
def list_templates():
    """List all plan templates."""
    templates = plan_templates_repo.get_all()
    return render_template('plans/templates_list.html', templates=templates)


@plans_bp.route('/templates/<id>')
@login_required
def view_template(id):
    """View a plan template."""
    template = plan_templates_repo.get_by_id(id)
    if not template:
        flash('Template não encontrado.', 'error')
        return redirect(url_for('plans.list_templates'))

    materials_map = {m['nome']: m for m in materials_repo.get_all()}
    tools_map = {t['nome']: t for t in tools_repo.get_all()}
    equipment_map = {e['nome']: e for e in equipment_repo.get_all()}

    return render_template(
        'plans/template_view.html',
        template=template,
        materials_map=materials_map,
        tools_map=tools_map,
        equipment_map=equipment_map
    )


@plans_bp.route('/templates/<id>/edit', methods=['GET', 'POST'])
@login_required
def edit_template(id):
    """Edit a plan template."""
    template = plan_templates_repo.get_by_id(id)
    if not template:
        flash('Template não encontrado.', 'error')
        return redirect(url_for('plans.list_templates'))

    if request.method == 'POST':
        nome = request.form.get('nome')
        descricao = request.form.get('descricao', '')
        informacoes_importantes = request.form.get('informacoes_importantes', '')

        # Get external services from form
        servicos_tipos = request.form.getlist('servico_tipo[]')
        servicos_resp = request.form.getlist('servico_responsavel[]')
        servicos_externos = [
            {'tipo': t.strip(), 'responsavel': r.strip()} 
            for t, r in zip(servicos_tipos, servicos_resp) 
            if t.strip()
        ]

        template_data = {
            'nome': nome,
            'descricao': descricao,
            'servicos_externos': servicos_externos,
            'materiais': request.form.getlist('materiais[]'),
            'ferramentas': request.form.getlist('ferramentas[]'),
            'equipamentos': request.form.getlist('equipamentos[]'),
            'informacoes_importantes': informacoes_importantes,
        }

        if not nome:
            flash('O nome do template é obrigatório.', 'error')
            context = get_form_context()
            return render_template('plans/template_form.html', template=template, **context)

        plan_templates_repo.update(id, template_data)
        flash('Template atualizado com sucesso.', 'success')
        return redirect(url_for('plans.view_template', id=id))

    context = get_form_context()
    return render_template('plans/template_form.html', template=template, **context)


@plans_bp.route('/templates/<id>/delete', methods=['POST'])
@login_required
def delete_template(id):
    """Delete a plan template."""
    plan_templates_repo.delete(id)
    flash('Template excluído.', 'success')
    return redirect(url_for('plans.list_templates'))


@plans_bp.route('/api/templates')
@login_required
def api_templates():
    """Return all templates as JSON (for modals)."""
    templates = plan_templates_repo.get_all()
    result = [{'id': t['id'], 'nome': t.get('nome', '')} for t in templates]
    return jsonify(result)
