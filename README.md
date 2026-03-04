# OOH Project Manager

Sistema de gerenciamento de projetos OOH (Out of Home) com planos de instalação, templates, galeria de fotos e integração com Google Drive.

## Tecnologias

- **Backend:** Flask (Python 3.12)
- **Banco de Dados:** MongoDB 7
- **Upload de Fotos:** Pillow (EXIF), Google Drive API
- **Deploy:** Docker + Gunicorn

## Setup Rápido (Docker)

```bash
# 1. Clone o repositório
git clone <repo-url>
cd dbprojectmanager

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com seus valores

# 3. Suba os containers
docker-compose up -d --build
```

Acesse em: `http://localhost:5000`

## Setup Local (Desenvolvimento)

### Pré-requisitos

- Python 3.12+
- MongoDB rodando na porta configurada

### Instalação

```bash
# 1. Instale as dependências
pip install -r requirements.txt

# 2. Configure as variáveis de ambiente
cp .env.example .env
# Edite o .env com seus valores

# 3. Rode o servidor
python run.py
```

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `MONGODB_URI` | URI de conexão MongoDB | `mongodb://localhost:27020/ooh_manager_db` |
| `MONGODB_PORT` | Porta do MongoDB | `27020` |
| `SECRET_KEY` | Chave secreta do Flask | `dev-secret-key` |
| `APP_PORT` | Porta da aplicação (Docker) | `5000` |

## Google Drive — Setup

O sistema faz upload automático das fotos de instalação para o Google Drive.

### 1. Criar credenciais OAuth 2.0

1. Acesse [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto (ou use um existente)
3. Ative a **Google Drive API**
4. Vá em **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**
5. Tipo: **Web application**
6. Adicione em **Authorized redirect URIs:**
   - Local: `http://127.0.0.1:5000/drive/callback`
   - Produção: `https://seu-dominio.com/drive/callback`
7. Baixe o JSON e coloque na pasta `secrets/`

### 2. Adicionar test users (se não publicou o app)

1. No Google Console → **OAuth consent screen → Test users**
2. Adicione o e-mail da conta do Drive que será usada

### 3. Conectar o Drive

1. Acesse o sistema e vá para um projeto
2. Clique em **Câmera** ou **Galeria** para upload de foto
3. Na modal que aparecer, clique em **"Conectar Drive"**
4. Faça login com a conta Google desejada
5. Pronto! Todas as fotos serão enviadas ao Drive automaticamente

### Trocar a conta do Drive

1. Delete o arquivo `secrets/token.json`
2. Faça upload de uma foto — a modal de login reaparecerá
3. Conecte com a nova conta

### Estrutura no Drive

```
Projetos/
  └── Nome do Projeto/
        └── Fotos da Instalação/
              ├── install_xxx_abc123.jpg
              └── install_xxx_def456.png
```

### Arquivos da pasta `secrets/`

| Arquivo | Função | Gerado por |
|---------|--------|------------|
| `client_secret_*.json` | Credenciais OAuth do projeto Google Cloud | Download manual do Console |
| `token.json` | Token de acesso da conta Google conectada | Gerado automaticamente pelo sistema |

> ⚠️ A pasta `secrets/` está no `.gitignore` — nunca suba esses arquivos no repositório.

## Estrutura do Projeto

```
dbprojectmanager/
├── app/
│   ├── blueprints/
│   │   ├── admin/       # Painel administrativo
│   │   ├── auth/        # Autenticação
│   │   ├── drive/       # OAuth Google Drive
│   │   ├── plans/       # Planos de instalação
│   │   └── projects/    # Projetos e fotos
│   ├── models/          # Entidades (dataclasses)
│   ├── repositories/    # Acesso ao MongoDB
│   ├── services/        # Serviços (Google Drive)
│   ├── static/          # CSS, JS, uploads
│   └── templates/       # Jinja2 templates
├── secrets/             # Credenciais OAuth (não versionado)
├── .env                 # Variáveis de ambiente (não versionado)
├── .env.example         # Template de variáveis
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
└── run.py               # Entry point
```
