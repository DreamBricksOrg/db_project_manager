"""Fix mock project data: dates and statuses."""
import random
from datetime import date, timedelta
from app.repositories import projects_repo, plans_repo
from app import create_app

app = create_app()

STATUSES = ['Concluído', 'Não Iniciado', 'Em Andamento', 'Instalado', 'Testes']

def fix_projects():
    projects = projects_repo.get_all()
    print(f"Fixing {len(projects)} projects...")
    
    for p in projects:
        # Generate installation date spread around current month
        base = date.today() + timedelta(days=random.randint(-60, 60))
        duration = random.randint(3, 30)
        
        data_instalacao = base.isoformat()
        data_remocao = (base + timedelta(days=duration)).isoformat()
        inicio_veiculacao = data_instalacao
        fim_veiculacao = data_remocao
        
        status = random.choice(STATUSES)
        conclusao = {
            'Não Iniciado': 0,
            'Em Andamento': random.randint(10, 70),
            'Testes': random.randint(80, 95),
            'Instalado': random.randint(80, 99),
            'Concluído': 100,
        }[status]
        
        update = {
            'data_instalacao': data_instalacao,
            'data_remocao': data_remocao,
            'inicio_veiculacao': inicio_veiculacao,
            'fim_veiculacao': fim_veiculacao,
            'status': status,
            'conclusao': conclusao,
        }
        
        projects_repo.update(p['id'], {**p, **update})
        print(f"  ✓ {p.get('nome', 'N/A')}: {status} ({data_instalacao} → {data_remocao})")

def fix_plans():
    plans = plans_repo.get_all()
    projects_map = {p['id']: p for p in projects_repo.get_all()}
    print(f"\nFixing {len(plans)} plans...")
    
    for plan in plans:
        project_id = plan.get('project_id')
        project = projects_map.get(project_id, {})
        
        data_instalacao = project.get('data_instalacao', '')
        data_remocao = project.get('data_remocao', '')
        
        if not data_instalacao:
            base = date.today() + timedelta(days=random.randint(-30, 30))
            duration = random.randint(5, 20)
            data_instalacao = base.isoformat()
            data_remocao = (base + timedelta(days=duration)).isoformat()
        
        update = {
            'data_instalacao': data_instalacao,
            'data_remocao': data_remocao,
            'inicio_veiculacao': data_instalacao,
            'fim_veiculacao': data_remocao,
        }
        
        plans_repo.update(plan['id'], {**plan, **update})
        print(f"  ✓ {plan.get('nome_projeto', 'N/A')}: {data_instalacao} → {data_remocao}")

if __name__ == '__main__':
    with app.app_context():
        print("=== Fixing Mock Data ===")
        fix_projects()
        fix_plans()
        print("\n✅ All projects and plans updated!")
