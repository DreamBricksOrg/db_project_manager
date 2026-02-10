"""Repository instances for each entity"""

from app.repositories.csv_repository import CSVRepository

# User repository
users_repo = CSVRepository('users.csv', ['id', 'username', 'password', 'role', 'nome'])

# Contact repository
contacts_repo = CSVRepository('contacts.csv', ['id', 'nome', 'telefone', 'email'])

# Producer repository (with login credentials)
producers_repo = CSVRepository('producers.csv', ['id', 'nome', 'telefone', 'email', 'username', 'password'])

# Installer repository (with login credentials)
installers_repo = CSVRepository('installers.csv', ['id', 'nome', 'telefone', 'email', 'especialidade', 'username', 'password'])

# External service repository
services_repo = CSVRepository('services.csv', ['id', 'tipo_servico', 'responsavel'])

# Material repository
materials_repo = CSVRepository('materials.csv', ['id', 'nome'])

# Installation plan repository
plans_repo = CSVRepository('plans.csv', [
    'id', 'nome_projeto', 'cliente', 'contato_cliente', 'telefone_contato',
    'produtor_responsavel', 'data_instalacao', 'data_remocao', 
    'inicio_veiculacao', 'fim_veiculacao', 'endereco', 'descricao',
    'instaladores', 'servicos_externos', 'materiais', 
    'informacoes_importantes', 'foto_layout'
])
