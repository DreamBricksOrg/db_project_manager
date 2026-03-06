import os
from flask import g
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

def get_db():
    if 'db' not in g:
        uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017/ooh_manager_db')
        client = MongoClient(uri)
        g.db = client.get_database()
    return g.db

def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.client.close()

def init_app(app):
    app.teardown_appcontext(close_db)
