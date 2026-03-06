from flask import Blueprint

drive_bp = Blueprint('drive', __name__, url_prefix='/drive', template_folder='templates')

from app.blueprints.drive import routes  # noqa
