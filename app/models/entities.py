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
    # Layout photo filename
    foto_layout: str = ''
