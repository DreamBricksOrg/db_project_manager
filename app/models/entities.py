"""Data Models - Dataclasses for all entities"""

from dataclasses import dataclass, field
from typing import Optional
import uuid


def generate_id() -> str:
    return str(uuid.uuid4())


@dataclass
class User:
    id: str
    username: str
    password: str  # Plain text for MVP, hash in production
    role: str  # 'admin' or 'user'
    nome: str = ''


@dataclass
class Contact:
    id: str
    nome: str
    telefone: str
    email: str


@dataclass
class Client:
    id: str
    nome: str
    email: str
    telefone: str
    documento: str = '' # CPF/CNPJ



@dataclass
class Producer:
    id: str
    nome: str
    telefone: str
    email: str


@dataclass
class Installer:
    id: str
    nome: str
    telefone: str
    email: str
    especialidade: str  # Montagem, Eletrica, Sistemas


@dataclass
class ExternalService:
    id: str
    tipo_servico: str  # Caminhão guincho, Instalador Especial
    responsavel: str


@dataclass
class Material:
    id: str
    nome: str


@dataclass
class Tool:
    id: str
    nome: str


@dataclass
class Project:
    id: str
    nome: str
    cliente: str
    produtor_db: str = ''
    produtor_db_contato: str = ''
    produtor_ext: str = ''
    produtor_ext_contato: str = ''
    data_instalacao: str = ''
    data_remocao: str = ''
    inicio_veiculacao: str = ''
    fim_veiculacao: str = ''
    datas_parciais: list[str] = field(default_factory=list) # List of date strings
    endereco: str = ''
    descricao: str = ''
    imagem_referencia: str = ''
    foto_layout: str = ''
    galeria: list[str] = field(default_factory=list) # List of filenames
    link_drive: str = ''
    status: str = 'Em Andamento' 
    conclusao: int = 0
    # Virtual fields
    plano_id: str = ''

@dataclass
class GraphicSpecs:
    id: str
    project_id: str
    cor_envelopamento: str = ''
    previsao_chegada_cor: str = ''
    arquivos_impressao: str = ''
    previsao_chegada_arq: str = ''

@dataclass
class Equipment:
    id: str
    project_id: str
    itens: list[str] = field(default_factory=list)

@dataclass
class InstallationPlan:
    id: str
    # Basic info
    nome_projeto: str
    cliente: str
    contato_cliente: str
    telefone_contato: str
    produtor_responsavel: str
    # Dates
    data_instalacao: str
    data_remocao: str
    inicio_veiculacao: str
    fim_veiculacao: str
    # Location
    endereco: str
    # Description
    descricao: str
    # Team
    instaladores: list[str] = field(default_factory=list)  # List of installer IDs
    equipe_db: str = '' # Names or description
    equipe_externa: str = '' # Names or description
    # External services
    servicos_externos: list[dict] = field(default_factory=list)  # [{tipo, responsavel}]
    # Materials
    materiais: list[str] = field(default_factory=list)
    # Tools
    ferramentas: list[str] = field(default_factory=list)
    # Lighting
    cor_iluminacao: str = '#ffffff'  # Default white
    # Notes
    informacoes_importantes: str = ''
    # Media
    foto_layout: str = ''
    imagem_referencia: str = ''
    # Relationships
    project_id: str = ''
    # Status
    status: str = 'Em Andamento'


@dataclass
class PlanTemplate:
    id: str
    nome: str
    descricao: str = ''
    servicos_externos: list[dict] = field(default_factory=list)
    materiais: list[str] = field(default_factory=list)
    ferramentas: list[str] = field(default_factory=list)
    equipamentos: list[str] = field(default_factory=list)
    informacoes_importantes: str = ''
