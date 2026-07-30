"""OOH Project Manager - Flask Application Factory"""

import logging
import sys

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_wtf.csrf import CSRFError, CSRFProtect
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config

csrf = CSRFProtect()

logger = logging.getLogger(__name__)


def configure_logging(app: Flask) -> None:
    """Send app logs to stdout so the container runtime can collect them."""
    level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO'), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)-8s %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))

    root = logging.getLogger()
    # Replace handlers rather than appending, so reloads do not duplicate lines.
    root.handlers = [handler]
    root.setLevel(level)

    # Gunicorn installs its own handlers; keep its access log but route app
    # messages through ours.
    app.logger.handlers = []
    app.logger.propagate = True
    logging.getLogger('werkzeug').setLevel(logging.WARNING)


def wants_json() -> bool:
    """True when the caller expects a JSON body rather than an HTML page."""
    if request.path.startswith('/api/') or request.path.startswith('/kanban/'):
        return True
    if '/kanban/' in request.path or '/gantt' in request.path:
        return True
    return request.accept_mimetypes.best == 'application/json'


def _error_response(code: int, slug: str, heading: str, message: str):
    """Render an error as JSON or HTML depending on what the caller wants."""
    if wants_json():
        return jsonify(error=slug, message=message), code
    return render_template('errors/error.html', code=code, heading=heading, message=message), code


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(error):
        return _error_response(
            404, 'not_found', 'Página não encontrada',
            'O endereço acessado não existe ou foi movido.',
        )

    @app.errorhandler(403)
    def forbidden(error):
        return _error_response(
            403, 'forbidden', 'Acesso negado',
            'Você não tem permissão para acessar este recurso.',
        )

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(error):
        limit_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
        return _error_response(
            413, 'payload_too_large', 'Arquivo muito grande',
            f'O limite de upload é {limit_mb} MB.',
        )

    @app.errorhandler(CSRFError)
    def csrf_error(error):
        logger.warning(
            'CSRF rejected for %s %s: %s', request.method, request.path, error.description
        )
        return _error_response(
            400, 'csrf', 'Sessão expirada',
            'Recarregue a página e tente novamente.',
        )

    @app.errorhandler(Exception)
    def internal_error(error):
        # Let Werkzeug's own HTTP exceptions (redirects, aborts) pass through
        # so they keep their intended status and body.
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return error

        # Log the traceback server-side; never leak it to the browser.
        logger.exception('Unhandled error on %s %s', request.method, request.path)
        return _error_response(
            500, 'internal', 'Erro interno',
            'Algo falhou do nosso lado. A equipe foi notificada nos logs.',
        )


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    # Resolved at startup so a missing production key fails loudly and early,
    # rather than silently signing sessions with a key that is in the repo.
    app.config['SECRET_KEY'] = config_class.resolve_secret_key()

    configure_logging(app)

    # Trust reverse proxy headers (Nginx/ALB) so request.url uses https
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    # Ensure directories exist
    config_class.DATA_DIR.mkdir(exist_ok=True)
    config_class.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    csrf.init_app(app)

    from app import database
    database.init_app(app)

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

    from app.blueprints.drive import drive_bp
    app.register_blueprint(drive_bp)

    from app.blueprints.kanban import kanban_bp
    app.register_blueprint(kanban_bp)

    register_error_handlers(app)

    # Root redirect
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('plans.list_plans'))

    @app.route('/healthz')
    def healthz():
        """Liveness/readiness probe: confirms the process can reach MongoDB.

        Authentication failures are reported distinctly from connectivity
        failures — collapsing both into "unreachable" sends you looking at the
        network when the real problem is a credential.
        """
        from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

        try:
            database.get_client().admin.command('ping')
        except OperationFailure as exc:
            logger.error('Health check: MongoDB rejected our credentials: %s', exc)
            return jsonify(status='error', database='auth_failed'), 503
        except ServerSelectionTimeoutError as exc:
            logger.error('Health check: could not reach MongoDB: %s', exc)
            return jsonify(status='error', database='unreachable'), 503
        except Exception:
            logger.exception('Health check failed')
            return jsonify(status='error', database='error'), 503
        return jsonify(status='ok', database='ok'), 200

    @app.route('/manifest.webmanifest')
    def manifest():
        return send_from_directory(app.static_folder, 'manifest.webmanifest')

    @app.route('/service-worker.js')
    def service_worker():
        return send_from_directory(app.static_folder, 'service-worker.js')

    logger.info('Application ready (debug=%s)', app.debug)
    return app
