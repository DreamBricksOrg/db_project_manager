"""Repository instances for each entity"""

from app.repositories.mongo_repository import MongoRepository

# User repository
users_repo = MongoRepository('users')

# Client repository
clients_repo = MongoRepository('clients')

# Contact repository
contacts_repo = MongoRepository('contacts')

# Producer repository (with login credentials)
producers_repo = MongoRepository('producers')

# Installer repository (with login credentials)
installers_repo = MongoRepository('installers')

# External service repository
services_repo = MongoRepository('services')

# Material repository
materials_repo = MongoRepository('materials')

# Installation plan repository
plans_repo = MongoRepository('plans')

# Tool repository
tools_repo = MongoRepository('tools')

# Project repository
projects_repo = MongoRepository('projects')

# Graphic specs repository
graphics_repo = MongoRepository('graphics')

# Equipment repository
equipment_repo = MongoRepository('equipment')

# Plan template repository
plan_templates_repo = MongoRepository('plan_templates')

