"""MongoDB connection.

A single MongoClient is shared by the whole process. PyMongo's client is
thread-safe and maintains its own connection pool, so creating one per
request (as this module used to) defeats pooling and leaks sockets.
"""

import os
import logging
from threading import Lock

from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_URI = 'mongodb://localhost:27017/ooh_manager_db'

_client: MongoClient | None = None
_client_lock = Lock()


def get_client() -> MongoClient:
    """Return the process-wide MongoClient, creating it on first use.

    Credentials are passed as parameters rather than embedded in the URI.
    Interpolating them into a connection string silently breaks on any
    password containing '@', ':', '/', '?', '#' or '%' — and the resulting
    failure looks like an unreachable host, not a bad password.
    """
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                uri = os.getenv('MONGODB_URI', DEFAULT_URI)

                options = {
                    'maxPoolSize': int(os.getenv('MONGODB_MAX_POOL_SIZE', '50')),
                    'serverSelectionTimeoutMS': int(
                        os.getenv('MONGODB_SERVER_SELECTION_TIMEOUT_MS', '5000')
                    ),
                    'tz_aware': True,
                }

                user = os.getenv('MONGO_USER', '').strip()
                password = os.getenv('MONGO_PASSWORD', '').strip()
                if user and password:
                    options['username'] = user
                    options['password'] = password
                    options['authSource'] = os.getenv('MONGO_AUTH_SOURCE', 'admin')

                _client = MongoClient(uri, **options)
    return _client


def get_db():
    """Return the configured database handle."""
    return get_client().get_database()


def close_client(exception=None):
    """Close the shared client. Only for shutdown hooks and tests."""
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None


# Indexes are declared here so they stay next to the queries that need them.
# Format: collection -> list of (keys, kwargs)
INDEXES: dict[str, list[tuple[list[tuple[str, int]], dict]]] = {
    'users': [
        ([('id', ASCENDING)], {'unique': True}),
        ([('username', ASCENDING)], {'unique': True}),
    ],
    'clients': [([('id', ASCENDING)], {'unique': True}), ([('nome', ASCENDING)], {})],
    'contacts': [([('id', ASCENDING)], {'unique': True}), ([('nome', ASCENDING)], {})],
    'producers': [([('id', ASCENDING)], {'unique': True}), ([('nome', ASCENDING)], {})],
    'installers': [([('id', ASCENDING)], {'unique': True}), ([('nome', ASCENDING)], {})],
    'services': [([('id', ASCENDING)], {'unique': True}), ([('nome', ASCENDING)], {})],
    'materials': [([('id', ASCENDING)], {'unique': True}), ([('nome', ASCENDING)], {})],
    'tools': [([('id', ASCENDING)], {'unique': True}), ([('nome', ASCENDING)], {})],
    'projects': [
        ([('id', ASCENDING)], {'unique': True}),
        ([('status', ASCENDING)], {}),
        ([('data_instalacao', ASCENDING)], {}),
        ([('nome', ASCENDING)], {}),
    ],
    'plans': [
        ([('id', ASCENDING)], {'unique': True}),
        ([('project_id', ASCENDING)], {}),
        ([('status', ASCENDING)], {}),
        ([('data_instalacao', ASCENDING)], {}),
    ],
    'plan_templates': [([('id', ASCENDING)], {'unique': True})],
    'graphics': [([('id', ASCENDING)], {'unique': True}), ([('project_id', ASCENDING)], {})],
    'equipment': [
        ([('id', ASCENDING)], {'unique': True}),
        ([('project_id', ASCENDING)], {}),
        ([('nome', ASCENDING)], {}),
    ],
    'installation_photos': [
        ([('id', ASCENDING)], {'unique': True}),
        ([('project_id', ASCENDING)], {}),
    ],
    'kanban_tasks': [
        ([('id', ASCENDING)], {'unique': True}),
        ([('project_id', ASCENDING), ('column_id', ASCENDING)], {}),
    ],
    'kanban_columns': [
        ([('id', ASCENDING)], {'unique': True}),
        ([('project_id', ASCENDING)], {}),
    ],
    'kanban_tags': [([('id', ASCENDING)], {'unique': True})],
}


def ensure_indexes(app=None) -> None:
    """Create the declared indexes. Idempotent; safe to call on every boot.

    Index creation never blocks startup: a unique index can legitimately fail
    on a database that still holds duplicate legacy rows, and that is a data
    problem to fix, not a reason to refuse to boot.
    """
    try:
        db = get_db()
    except PyMongoError:
        logger.exception('Could not reach MongoDB to ensure indexes')
        return

    created = failed = 0
    for collection, specs in INDEXES.items():
        for keys, kwargs in specs:
            try:
                db[collection].create_index(keys, background=True, **kwargs)
                created += 1
            except PyMongoError as exc:
                failed += 1
                logger.warning(
                    'Index %s on %s not created: %s', keys, collection, exc
                )
    logger.info('MongoDB indexes ensured (%d ok, %d skipped)', created, failed)


def init_app(app):
    """Wire the database into the Flask app."""
    if app.config.get('ENSURE_INDEXES', True):
        ensure_indexes(app)
