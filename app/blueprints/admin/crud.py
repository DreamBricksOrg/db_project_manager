"""Generic admin CRUD.

Nine admin entities had four near-identical views each: list with search and
pagination, create, edit, delete. The only real differences were the repository,
the form fields, the template names and the wording of the flash messages, so
those are described once per entity in a :class:`CrudSpec` and the views are
generated from it.

Anything genuinely entity-specific hangs off the optional hooks rather than
forcing a copy of the whole block.
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from flask import current_app, flash, redirect, render_template, request, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from app.blueprints.auth.routes import admin_required
from app.querying import merge_filters, paginate_query, read_page, text_filter

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
PER_PAGE_CHOICES = (10, 25, 50)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file) -> Optional[str]:
    """Validate and store an uploaded image, returning its relative path.

    The extension alone is not evidence of file type, so the bytes are decoded
    with Pillow before anything is written to the uploads directory.
    """
    if not file or not file.filename or not allowed_file(file.filename):
        return None

    try:
        # verify() consumes the stream, so check a copy and rewind afterwards.
        Image.open(file.stream).verify()
    except (UnidentifiedImageError, OSError, ValueError):
        logger.warning('Rejected upload %r: not a decodable image', file.filename)
        flash('O arquivo enviado não é uma imagem válida.', 'error')
        return None
    finally:
        file.stream.seek(0)

    original_filename = secure_filename(file.filename)
    extension = original_filename.rsplit('.', 1)[1].lower()
    new_filename = f'{uuid.uuid4().hex}.{extension}'

    upload_folder = current_app.config['UPLOAD_DIR']
    os.makedirs(upload_folder, exist_ok=True)
    file.save(os.path.join(upload_folder, new_filename))
    return f'uploads/{new_filename}'


@dataclass(frozen=True)
class CrudSpec:
    """Describes one admin entity well enough to generate its four views."""

    name: str                       # URL segment and endpoint plural, e.g. 'clients'
    singular: str                   # endpoint singular, e.g. 'client'
    repo: object                    # MongoRepository
    fields: tuple                   # form fields copied verbatim, stripped
    search_fields: tuple            # fields the list search box looks at
    label: str                      # human label, e.g. 'Cliente'
    created: str                    # e.g. 'Cliente criado com sucesso!'
    updated: str                    # e.g. 'Cliente atualizado!'
    deleted: str                    # e.g. 'Cliente removido.'
    missing: str                    # e.g. 'Cliente não encontrado.'
    required: str = 'nome'          # field that must be filled in
    required_message: str = 'Nome é obrigatório.'
    item_var: str = ''              # template variable for a single item
    list_var: str = ''              # template variable for the page of items
    template_dir: str = ''          # defaults to admin/<name>
    sort_field: str = 'nome'
    has_image: bool = False

    # Optional hooks for the parts that genuinely differ per entity.
    # annotate_page(items) -> None: decorate the current page before rendering.
    annotate_page: Optional[Callable] = None
    # form_context(item) -> dict: extra template context on the edit form.
    form_context: Optional[Callable] = None
    # delete_guard(item) -> str | None: return a message to block the delete.
    delete_guard: Optional[Callable] = None

    def resolved(self) -> 'CrudSpec':
        """Fill in the conventional defaults."""
        return CrudSpec(
            **{
                **self.__dict__,
                'item_var': self.item_var or self.singular,
                'list_var': self.list_var or self.name,
                'template_dir': self.template_dir or f'admin/{self.name}',
            }
        )

    def template(self, page: str) -> str:
        return f'{self.template_dir}/{page}.html'

    def endpoint(self, action: str) -> str:
        return f'admin.{action}_{self.name if action == "list" else self.singular}'


def read_form(spec: CrudSpec) -> dict:
    """Pull the declared fields off the submitted form."""
    data = {f: request.form.get(f, '').strip() for f in spec.fields}
    if spec.has_image:
        image_path = save_image(request.files.get('image'))
        if image_path:
            data['image'] = image_path
    return data


def register_crud(bp, spec: CrudSpec) -> None:
    """Attach list/new/edit/delete views for ``spec`` to the blueprint."""
    spec = spec.resolved()
    list_endpoint = spec.endpoint('list')

    def list_view():
        q = request.args.get('q', '').strip()
        filters = merge_filters(text_filter(q, spec.search_fields))
        page, per_page = read_page(PER_PAGE_CHOICES)

        # Filtering, sorting and paging happen in MongoDB; only the current
        # page is materialised.
        pg = paginate_query(
            spec.repo, filters, [(spec.sort_field, 1)], page, per_page
        )

        if spec.annotate_page:
            spec.annotate_page(pg['items'])

        return render_template(
            spec.template('list'),
            list_endpoint=list_endpoint,
            q=q,
            **{spec.list_var: pg['items']},
            **pg,
        )

    def new_view():
        if request.method == 'POST':
            data = read_form(spec)
            if not data.get(spec.required):
                flash(spec.required_message, 'error')
            else:
                created = spec.repo.create(data)
                logger.info('Created %s %s', spec.singular, created.get('id'))
                flash(spec.created, 'success')
                return redirect(url_for(list_endpoint))
        return render_template(spec.template('form'), **{spec.item_var: None})

    def edit_view(id):
        item = spec.repo.get_by_id(id)
        if not item:
            flash(spec.missing, 'error')
            return redirect(url_for(list_endpoint))

        if request.method == 'POST':
            data = read_form(spec)
            if not data.get(spec.required):
                flash(spec.required_message, 'error')
            else:
                spec.repo.update(id, data)
                logger.info('Updated %s %s', spec.singular, id)
                flash(spec.updated, 'success')
                return redirect(url_for(list_endpoint))

        extra = spec.form_context(item) if spec.form_context else {}
        return render_template(spec.template('form'), **{spec.item_var: item}, **extra)

    def delete_view(id):
        item = spec.repo.get_by_id(id)
        blocked = spec.delete_guard(item) if (spec.delete_guard and item) else None
        if blocked:
            flash(blocked, 'error')
        else:
            spec.repo.delete(id)
            logger.info('Deleted %s %s', spec.singular, id)
            flash(spec.deleted, 'success')
        return redirect(url_for(list_endpoint))

    # Flask derives endpoint names from the function name, so set them to the
    # names the existing templates already call in url_for().
    list_view.__name__ = f'list_{spec.name}'
    new_view.__name__ = f'new_{spec.singular}'
    edit_view.__name__ = f'edit_{spec.singular}'
    delete_view.__name__ = f'delete_{spec.singular}'

    base = f'/{spec.name}'
    bp.route(base)(admin_required(list_view))
    bp.route(f'{base}/new', methods=['GET', 'POST'])(admin_required(new_view))
    bp.route(f'{base}/<id>/edit', methods=['GET', 'POST'])(admin_required(edit_view))
    bp.route(f'{base}/<id>/delete', methods=['POST'])(admin_required(delete_view))
