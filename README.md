# OOH Project Manager

Sistema de gerenciamento de projetos OOH (Out of Home) com planos de instalação, templates, galeria de fotos, kanban e integração com Google Drive.

## Tecnologias

- **Backend:** Flask 3 (Python 3.12)
- **Banco de Dados:** MongoDB 7
- **Segurança:** Flask-WTF (CSRF), hashes PBKDF2-SHA256
- **Upload de Fotos:** Pillow (EXIF), Google Drive API
- **Deploy:** Docker + Gunicorn
- **Testes:** pytest + mongomock

## Setup Rápido (Docker)

```bash
# 1. Clone o repositório
git clone <repo-url>
cd dbprojectmanager

# 2. Configure as variáveis de ambiente
cp .env.example .env

# 3. Gere a SECRET_KEY (obrigatória — a app não sobe sem ela)
python -c "import secrets; print(secrets.token_hex(32))"
# Cole o valor em SECRET_KEY no .env, e defina MONGO_USER / MONGO_PASSWORD

# 4. Suba os containers
docker compose up -d --build
```

Acesse em: `http://localhost:5000`

No primeiro boot, se não existir nenhum usuário, a app cria a conta `admin`.
A senha vem de `ADMIN_INITIAL_PASSWORD`; se estiver em branco, uma senha
aleatória é gerada e impressa **uma única vez** nos logs:

```bash
docker compose logs app | grep -A2 "bootstrap admin"
```

> Em desenvolvimento sem HTTPS, defina `SESSION_COOKIE_SECURE=false` e
> `WTF_CSRF_SSL_STRICT=false` no `.env` — caso contrário o cookie de sessão
> nunca é enviado e o login não persiste.

## Setup Local (Desenvolvimento)

### Pré-requisitos

- Python 3.12+
- MongoDB rodando na porta configurada

### Instalação

```bash
pip install -r requirements-dev.txt
cp .env.example .env

# Para desenvolvimento local sem HTTPS:
#   SECRET_KEY=<gere uma>
#   FLASK_DEBUG=1
#   SESSION_COOKIE_SECURE=false
#   WTF_CSRF_SSL_STRICT=false
#   MONGODB_URI=mongodb://localhost:27020/ooh_manager_db

python run.py
```

O servidor sobe em `127.0.0.1:5000`. Para expor na rede, use
`FLASK_RUN_HOST=0.0.0.0`.

### Testes

```bash
pytest
```

A suíte roda contra `mongomock` — não é necessário ter um MongoDB de pé.

### Scripts auxiliares

```bash
python scripts/seed_db.py    # popula o banco com dados fake
python scripts/fix_dates.py  # normaliza datas/status de dados mock
```

## Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `SECRET_KEY` | **Obrigatória.** Chave de assinatura da sessão. A app se recusa a subir em produção sem ela | — |
| `FLASK_DEBUG` | Modo debug. Nunca ativar em produção | `0` |
| `FLASK_ENV` | Ambiente | `production` |
| `LOG_LEVEL` | Nível de log | `INFO` |
| `MONGODB_URI` | URI de conexão. No Docker é montada a partir de `MONGO_*` | `mongodb://localhost:27017/ooh_manager_db` |
| `MONGO_USER` / `MONGO_PASSWORD` | Credenciais do MongoDB (Docker) | — |
| `MONGO_DB` | Nome do banco | `ooh_manager_db` |
| `MONGODB_PORT` | Porta do MongoDB | `27020` |
| `MONGODB_MAX_POOL_SIZE` | Tamanho do pool de conexões | `50` |
| `ENSURE_INDEXES` | Cria os índices no boot | `true` |
| `APP_PORT` | Porta publicada da aplicação | `5000` |
| `APP_BIND` | Interface do host onde a porta é publicada | `127.0.0.1` |
| `SESSION_COOKIE_SECURE` | Envia o cookie só por HTTPS | `true` |
| `WTF_CSRF_SSL_STRICT` | Valida a origem do CSRF sobre HTTPS | `true` |
| `SESSION_HOURS` | Duração da sessão | `12` |
| `LOGIN_MAX_ATTEMPTS` | Tentativas antes do bloqueio | `5` |
| `LOGIN_LOCKOUT_SECONDS` | Duração do bloqueio | `300` |
| `MAX_UPLOAD_MB` | Tamanho máximo de upload | `64` |
| `ADMIN_INITIAL_PASSWORD` | Senha do admin criado no primeiro boot | aleatória |

## Segurança

Pontos relevantes para quem for operar ou estender o sistema:

- **Senhas** são armazenadas com PBKDF2-SHA256 (600k iterações). Registros
  antigos em texto puro continuam funcionando e são convertidos para hash
  automaticamente no primeiro login bem-sucedido.
- **CSRF** é obrigatório em todos os POSTs. Formulários carregam
  `csrf_token`; `fetch()` e htmx recebem o header `X-CSRFToken` via um wrapper
  global em `base.html`.
- **Login** tem bloqueio por IP+usuário após `LOGIN_MAX_ATTEMPTS` falhas. O
  contador é por processo — com vários workers Gunicorn, cada um mantém o seu.
  Para um limite compartilhado, mova `LoginThrottle` para o Redis.
- **Buscas** escapam a entrada do usuário antes do `$regex`.
- **Uploads** são validados decodificando os bytes com Pillow, não apenas pela
  extensão.
- **MongoDB** roda com `--auth` e sem porta publicada no host.
- A pasta `secrets/` está no `.gitignore` e no `.dockerignore` — nunca suba
  esses arquivos no repositório nem os embuta na imagem.

## Health check

`GET /healthz` retorna `200` quando a app responde e alcança o MongoDB, e
`503` caso contrário. É usado pelos health checks do Docker e do compose.

## Rotas

| Prefixo | Blueprint | Descrição |
|---------|-----------|-----------|
| `/login`, `/logout` | `auth` | Autenticação (logout é POST) |
| `/plans` | `plans` | Planos de instalação, templates e PDF |
| `/projects` | `projects` | Projetos, gráficos, equipamentos e fotos |
| `/projects/<id>/kanban`, `/projects/<id>/gantt` | `kanban` | Quadro kanban e gantt do projeto |
| `/admin` | `admin` | CRUD de usuários, clientes, contatos, produtores, instaladores, serviços, materiais, ferramentas e equipamentos |
| `/api/autocomplete/*` | `api` | Autocomplete das telas de cadastro |
| `/drive` | `drive` | OAuth e status do Google Drive |
| `/healthz` | — | Health check |

Para a lista completa:

```bash
flask --app run:app routes
```

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
│   │   ├── admin/       # Painel administrativo (CRUD gerado via crud.py)
│   │   ├── api/         # Endpoints JSON de autocomplete
│   │   ├── auth/        # Autenticação
│   │   ├── drive/       # OAuth Google Drive
│   │   ├── kanban/      # Kanban e Gantt por projeto
│   │   ├── plans/       # Planos de instalação
│   │   └── projects/    # Projetos e fotos
│   ├── models/          # Entidades (dataclasses)
│   ├── repositories/    # Acesso ao MongoDB
│   ├── services/        # Serviços (Google Drive)
│   ├── static/          # CSS, JS, uploads
│   ├── templates/       # Jinja2 templates (base, componentes, erros)
│   ├── database.py      # Cliente MongoDB e declaração de índices
│   ├── querying.py      # Filtro/ordenação/paginação em MongoDB
│   └── security.py      # Hash de senha e throttling de login
├── scripts/             # seed_db.py, fix_dates.py
├── secrets/             # Credenciais OAuth (não versionado)
├── tests/               # Suíte pytest (mongomock)
├── .env                 # Variáveis de ambiente (não versionado)
├── .env.example         # Template de variáveis
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
└── run.py               # Entry point
```
