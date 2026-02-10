"""Admin Blueprint - CRUD for contacts, producers, installers, services"""

from flask import Blueprint

admin_bp = Blueprint('admin', __name__, template_folder='templates')

from app.blueprints.admin import routes
