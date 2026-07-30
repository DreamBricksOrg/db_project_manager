"""Helpers for turning request query strings into MongoDB queries.

The list views used to pull whole collections into Python and then filter,
sort and slice them. That works until the collections grow. These helpers keep
the same URL contract but let MongoDB do the work.
"""

import re
from typing import Any, Iterable

from flask import request

DEFAULT_PER_PAGE_CHOICES = (10, 25, 50)


def text_filter(query: str, fields: Iterable[str]) -> dict:
    """Build a case-insensitive "any of these fields contains query" filter.

    The term is escaped: unescaped user input in ``$regex`` is a denial-of-
    service vector.
    """
    if not query:
        return {}
    pattern = {'$regex': re.escape(query), '$options': 'i'}
    return {'$or': [{field: pattern} for field in fields]}


def merge_filters(*filters: dict) -> dict:
    """Combine filters with $and, dropping the empty ones."""
    active = [f for f in filters if f]
    if not active:
        return {}
    if len(active) == 1:
        return active[0]
    return {'$and': active}


def read_page(per_page_choices: Iterable[int] = DEFAULT_PER_PAGE_CHOICES) -> tuple[int, int]:
    """Read and validate ``page`` / ``per_page`` from the query string."""
    choices = list(per_page_choices)
    default = choices[0]

    try:
        per_page = int(request.args.get('per_page', default))
    except (ValueError, TypeError):
        per_page = default
    if per_page not in choices:
        per_page = default

    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1

    return page, per_page


def read_sort(sort_fields: dict[str, str], default: list | None = None) -> tuple[str, str, list]:
    """Translate ``sort_by`` / ``sort_dir`` into a PyMongo sort spec.

    ``sort_fields`` maps the public sort key to the document field, which also
    acts as an allowlist — an arbitrary field name from the URL never reaches
    the query.
    """
    sort_by = request.args.get('sort_by', '')
    sort_dir = request.args.get('sort_dir', 'asc')
    direction = -1 if sort_dir == 'desc' else 1

    if sort_by in sort_fields:
        return sort_by, sort_dir, [(sort_fields[sort_by], direction)]
    return sort_by, sort_dir, (default or [])


def paginate_query(repo, filters: dict, sort: list, page: int, per_page: int) -> dict[str, Any]:
    """Run a counted, sorted, paginated query and return the view context."""
    total_items = repo.count(filters)
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    page = min(max(1, page), total_pages)

    items = repo.find(
        filters=filters,
        sort=sort,
        skip=(page - 1) * per_page,
        limit=per_page,
    )

    return {
        'items': items,
        'page': page,
        'total_pages': total_pages,
        'total_items': total_items,
        'per_page': per_page,
    }
