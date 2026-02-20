
import random
from faker import Faker
from app.repositories import (
    users_repo, clients_repo, contacts_repo, producers_repo,
    installers_repo, services_repo, materials_repo,
    tools_repo, equipment_repo, projects_repo, plans_repo
)
from app import create_app

app = create_app()
fake = Faker('pt_BR')

def seed_users(count=10):
    print(f"Seeding {count} users...")
    roles = ['admin', 'user']
    for _ in range(count):
        user = {
            'nome': fake.name(),
            'username': fake.user_name(),
            'password': '123',  # Default password
            'role': random.choice(roles),
            'active': True
        }
        # Check for duplicates not needed for seeding script usually, but good practice
        existing = next((u for u in users_repo.get_all() if u.get('username') == user['username']), None)
        if not existing:
            users_repo.create(user)

def seed_clients(count=10):
    print(f"Seeding {count} clients...")
    for _ in range(count):
        client = {
            'nome': fake.company(),
            'email': fake.email(),
            'telefone': fake.phone_number(),
            'documento': fake.cnpj()
        }
        clients_repo.create(client)

def seed_contacts(count=10):
    print(f"Seeding {count} contacts...")
    for _ in range(count):
        contact = {
            'nome': fake.name(),
            'email': fake.email(),
            'telefone': fake.phone_number()
        }
        contacts_repo.create(contact)

def seed_producers(count=10):
    print(f"Seeding {count} producers...")
    for _ in range(count):
        producer = {
            'nome': fake.name(),
            'email': fake.email(),
            'telefone': fake.phone_number()
        }
        producers_repo.create(producer)

def seed_installers(count=10):
    print(f"Seeding {count} installers...")
    specialties = ['Elétrica', 'Hidráulica', 'Estrutura', 'Adesivagem', 'Geral']
    for _ in range(count):
        installer = {
            'nome': fake.name(),
            'email': fake.email(),
            'telefone': fake.phone_number(),
            'especialidade': random.choice(specialties)
        }
        installers_repo.create(installer)

def seed_services(count=10):
    print(f"Seeding {count} services...")
    types = ['Impressão', 'Transporte', 'Aluguel de Guindaste', 'Eletricista Externo', 'Segurança']
    for _ in range(count):
        service = {
            'tipo_servico': random.choice(types),
            'responsavel': fake.company()
        }
        services_repo.create(service)

def seed_materials(count=10):
    print(f"Seeding {count} materials...")
    materials = ['Parafuso', 'Bucha', 'Cabo de Aço', 'Lona', 'Adesivo', 'Vinil', 'Madeira', 'Ferro', 'Tinta', 'Silicone', 'Fita Dupla Face', 'Abraçadeira']
    for _ in range(count):
        materials_repo.create({'nome': random.choice(materials) + ' ' + fake.word()})

def seed_tools(count=10):
    print(f"Seeding {count} tools...")
    tools = ['Furadeira', 'Parafusadeira', 'Martelo', 'Alicate', 'Chave de Fenda', 'Nível', 'Trena', 'Escada', 'Serra', 'Multímetro']
    for _ in range(count):
        tools_repo.create({'nome': random.choice(tools) + ' ' + fake.word()})

def seed_equipment(count=10):
    print(f"Seeding {count} equipment...")
    equipment = ['Andaime', 'Gerador', 'EPI Completo', 'Cinto de Segurança', 'Capacete', 'Luvas', 'Óculos de Proteção', 'Botas']
    for _ in range(count):
        equipment_repo.create({'nome': random.choice(equipment) + ' ' + fake.word()})

def seed_projects(count=10):
    print(f"Seeding {count} projects...")
    statuses = ['active', 'concluded', 'cancelled']
    clients = clients_repo.get_all()
    producers = producers_repo.get_all()
    
    if not clients or not producers:
        print("Need clients and producers to seed projects.")
        return

    for _ in range(count):
        project = {
            'nome': 'Projeto ' + fake.bs().title(),
            'cliente': random.choice(clients)['nome'],
            'produtor_db': random.choice(producers)['nome'],
            'status': random.choice(statuses),
            'descricao': fake.text(),
            'data_instalacao': fake.date_between(start_date='-1y', end_date='+1y').isoformat(),
            'endereco': fake.address()
        }
        projects_repo.create(project)

def seed_plans(count=10):
    print(f"Seeding {count} plans...")
    projects = projects_repo.get_all()
    if not projects:
        print("Need projects to seed plans.")
        return

    # Fetch resources for relationships
    all_materials = [m['nome'] for m in materials_repo.get_all()]
    all_tools = [t['nome'] for t in tools_repo.get_all()]
    all_equipment = [e['nome'] for e in equipment_repo.get_all()]
    all_installers = [i['id'] for i in installers_repo.get_all()]
    all_services = services_repo.get_all()

    for _ in range(count):
        project = random.choice(projects)
        
        # Generate relationships
        plan_materials = random.sample(all_materials, k=min(len(all_materials), random.randint(3, 8))) if all_materials else []
        plan_tools = random.sample(all_tools, k=min(len(all_tools), random.randint(2, 5))) if all_tools else []
        plan_equipment = random.sample(all_equipment, k=min(len(all_equipment), random.randint(1, 3))) if all_equipment else []
        plan_installers = random.sample(all_installers, k=min(len(all_installers), random.randint(1, 3))) if all_installers else []
        
        plan_services = []
        if all_services and random.choice([True, False]):
            svcs = random.sample(all_services, k=random.randint(1, 2))
            plan_services = [{'tipo': s['tipo_servico'], 'responsavel': s['responsavel']} for s in svcs]

        plan = {
            'project_id': project.get('id'),
            'nome_projeto': project.get('nome'),
            'cliente': project.get('cliente'),
            'produtor_responsavel': project.get('produtor_db'),
            'telefone_contato': fake.phone_number(),
            'data_instalacao': project.get('data_instalacao'),
            'data_remocao': fake.date_between(start_date='+1d', end_date='+2d').isoformat(),
            'inicio_veiculacao': project.get('data_instalacao'),
            'fim_veiculacao': fake.date_between(start_date='+15d', end_date='+30d').isoformat(),
            'endereco': project.get('endereco'),
            'descricao': fake.text(),
            'informacoes_importantes': fake.text(),
            'cor_iluminacao': fake.color(),
            # Relationships
            'materiais': plan_materials,
            'ferramentas': plan_tools,
            'equipamentos': plan_equipment,
            'instaladores': plan_installers,
            'servicos_externos': plan_services
        }
        plans_repo.create(plan)

if __name__ == '__main__':
    with app.app_context():
        print("Starting database seed...")
        seed_users(10)
        seed_clients(10)
        seed_contacts(10)
        seed_producers(10)
        seed_installers(10)
        seed_services(10)
        seed_materials(10)
        seed_tools(10)
        seed_equipment(10)
        seed_projects(10)
        seed_plans(10)
        print("Database seed completed!")
