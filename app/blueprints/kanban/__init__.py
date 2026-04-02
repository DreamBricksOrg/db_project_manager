from flask import Blueprint

kanban_bp = Blueprint('kanban', __name__, template_folder='templates')

from app.blueprints.kanban import routes  # noqa: F401, E402
