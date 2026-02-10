"""Plans Blueprint - Installation plans management"""

from flask import Blueprint

plans_bp = Blueprint('plans', __name__, template_folder='templates')

from app.blueprints.plans import routes
