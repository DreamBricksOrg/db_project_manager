"""Kanban Routes - Board, Tasks, Columns and Tags management"""

from datetime import datetime
from flask import render_template, request, jsonify, session
from app.blueprints.kanban import kanban_bp
from app.blueprints.auth.routes import login_required
from app.repositories import (
    projects_repo, users_repo,
    kanban_tasks_repo, kanban_columns_repo, kanban_tags_repo
)

# ── Default data ──────────────────────────────────────────────────────────────
DEFAULT_COLUMNS = [
    {'name': 'Backlog',       'color': '#94a3b8', 'order': 0},
    {'name': 'A Fazer',       'color': '#f59e0b', 'order': 1},
    {'name': 'Em Andamento',  'color': '#3b82f6', 'order': 2},
    {'name': 'Revisão',       'color': '#8b5cf6', 'order': 3},
    {'name': 'Concluído',     'color': '#10b981', 'order': 4},
]

DEFAULT_TAGS = [
    {'name': 'Design',    'color': '#f472b6'},
    {'name': 'Backend',   'color': '#6366f1'},
    {'name': 'Frontend',  'color': '#22d3ee'},
    {'name': 'UX',        'color': '#fb923c'},
    {'name': 'Bug',       'color': '#ef4444'},
    {'name': 'Feature',   'color': '#10b981'},
    {'name': 'Docs',      'color': '#a3a3a3'},
    {'name': 'Urgente',   'color': '#dc2626'},
]


def _ensure_defaults(project_id: str):
    """Create default columns/tags for a new project board."""
    existing = kanban_columns_repo.get_by_project(project_id)
    if not existing:
        for col in DEFAULT_COLUMNS:
            kanban_columns_repo.create({**col, 'project_id': project_id})

    if not kanban_tags_repo.get_all():
        for tag in DEFAULT_TAGS:
            kanban_tags_repo.create(tag)


# ── Board view ─────────────────────────────────────────────────────────────────
@kanban_bp.route('/projects/<project_id>/kanban')
@login_required
def board(project_id):
    project = projects_repo.get_by_id(project_id)
    if not project:
        from flask import flash, redirect, url_for
        flash('Projeto não encontrado.', 'error')
        return redirect(url_for('projects.list_projects'))

    _ensure_defaults(project_id)

    columns = sorted(
        kanban_columns_repo.get_by_project(project_id),
        key=lambda c: c.get('order', 0)
    )
    tasks = kanban_tasks_repo.get_by_project(project_id)
    tags = sorted(kanban_tags_repo.get_all(), key=lambda t: t.get('name', ''))
    users = [u for u in users_repo.get_all() if u.get('nome') or u.get('username')]

    # Group tasks by column
    tasks_by_col = {col['id']: [] for col in columns}
    for task in tasks:
        col_id = task.get('column_id', '')
        if col_id in tasks_by_col:
            tasks_by_col[col_id].append(task)

    # Sort tasks within each column by order
    for col_id in tasks_by_col:
        tasks_by_col[col_id].sort(key=lambda t: t.get('order', 0))

    today = datetime.now().strftime('%Y-%m-%d')
    return render_template(
        'kanban/board.html',
        project=project,
        columns=columns,
        tasks_by_col=tasks_by_col,
        tags=tags,
        users=users,
        today=today,
        now=datetime.now(),
    )


# ── Task CRUD ──────────────────────────────────────────────────────────────────
@kanban_bp.route('/projects/<project_id>/kanban/tasks', methods=['POST'])
@login_required
def create_task(project_id):
    data = request.get_json(force=True)
    column_id = data.get('column_id', '')

    # Determine next order in column
    col_tasks = [t for t in kanban_tasks_repo.get_by_project(project_id)
                 if t.get('column_id') == column_id]
    next_order = max((t.get('order', 0) for t in col_tasks), default=-1) + 1

    task = kanban_tasks_repo.create({
        'project_id':    project_id,
        'column_id':     column_id,
        'title':         data.get('title', 'Nova Tarefa'),
        'description':   data.get('description', ''),
        'priority':      data.get('priority', 'media'),
        'assignee_id':   data.get('assignee_id', ''),
        'assignee_name': data.get('assignee_name', ''),
        'start_date':    data.get('start_date', ''),
        'end_date':      data.get('end_date', ''),
        'tags':          data.get('tags', []),
        'order':         next_order,
        'created_at':    datetime.now().isoformat(),
        'created_by':    session.get('user_id', ''),
    })
    return jsonify({'success': True, 'task': task})


@kanban_bp.route('/projects/<project_id>/kanban/tasks/<task_id>', methods=['PUT'])
@login_required
def update_task(project_id, task_id):
    data = request.get_json(force=True)
    allowed = ('title', 'description', 'priority', 'assignee_id',
               'assignee_name', 'start_date', 'end_date', 'tags')
    update = {k: data[k] for k in allowed if k in data}
    update['updated_at'] = datetime.now().isoformat()
    task = kanban_tasks_repo.update(task_id, update)
    return jsonify({'success': True, 'task': task})


@kanban_bp.route('/projects/<project_id>/kanban/tasks/<task_id>', methods=['DELETE'])
@login_required
def delete_task(project_id, task_id):
    kanban_tasks_repo.delete(task_id)
    return jsonify({'success': True})


@kanban_bp.route('/projects/<project_id>/kanban/tasks/<task_id>/move', methods=['PATCH'])
@login_required
def move_task(project_id, task_id):
    """Move a task to a new column and/or position."""
    data = request.get_json(force=True)
    new_col   = data.get('column_id')
    new_order = data.get('order', 0)
    kanban_tasks_repo.update(task_id, {
        'column_id': new_col,
        'order':     new_order,
        'updated_at': datetime.now().isoformat(),
    })
    return jsonify({'success': True})


# ── Column CRUD ────────────────────────────────────────────────────────────────
@kanban_bp.route('/projects/<project_id>/kanban/columns', methods=['POST'])
@login_required
def create_column(project_id):
    data = request.get_json(force=True)
    cols = kanban_columns_repo.get_by_project(project_id)
    next_order = max((c.get('order', 0) for c in cols), default=-1) + 1
    col = kanban_columns_repo.create({
        'project_id': project_id,
        'name':       data.get('name', 'Nova Coluna'),
        'color':      data.get('color', '#94a3b8'),
        'order':      next_order,
    })
    return jsonify({'success': True, 'column': col})


@kanban_bp.route('/projects/<project_id>/kanban/columns/<col_id>', methods=['PUT'])
@login_required
def update_column(project_id, col_id):
    data = request.get_json(force=True)
    col = kanban_columns_repo.update(col_id, {
        'name':  data.get('name', ''),
        'color': data.get('color', '#94a3b8'),
    })
    return jsonify({'success': True, 'column': col})


@kanban_bp.route('/projects/<project_id>/kanban/columns/<col_id>', methods=['DELETE'])
@login_required
def delete_column(project_id, col_id):
    # Move orphan tasks to first column
    remaining = [c for c in kanban_columns_repo.get_by_project(project_id)
                 if c['id'] != col_id]
    if remaining:
        fallback = sorted(remaining, key=lambda c: c.get('order', 0))[0]
        orphans = [t for t in kanban_tasks_repo.get_by_project(project_id)
                   if t.get('column_id') == col_id]
        for t in orphans:
            kanban_tasks_repo.update(t['id'], {'column_id': fallback['id']})

    kanban_columns_repo.delete(col_id)
    return jsonify({'success': True})


# ── Tags ───────────────────────────────────────────────────────────────────────
@kanban_bp.route('/kanban/tags', methods=['GET'])
@login_required
def list_tags():
    tags = sorted(kanban_tags_repo.get_all(), key=lambda t: t.get('name', ''))
    return jsonify(tags)


@kanban_bp.route('/kanban/tags', methods=['POST'])
@login_required
def create_tag():
    data = request.get_json(force=True)
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Nome obrigatório'}), 400
    tag = kanban_tags_repo.create({
        'name':  name,
        'color': data.get('color', '#6366f1'),
    })
    return jsonify({'success': True, 'tag': tag})
