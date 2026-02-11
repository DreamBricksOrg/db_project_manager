"""OOH Project Manager - Flask Application Factory"""

from flask import Flask
from config import Config


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure directories exist
    config_class.DATA_DIR.mkdir(exist_ok=True)
    config_class.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Register blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.plans import plans_bp
    from app.blueprints.api import api_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(plans_bp, url_prefix='/plans')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    from app.blueprints.projects import projects_bp
    app.register_blueprint(projects_bp, url_prefix='/projects')

    # Root redirect
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('plans.list_plans'))

    return app
