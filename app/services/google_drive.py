from pathlib import Path
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ['https://www.googleapis.com/auth/drive']
BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRETS_DIR = BASE_DIR / 'secrets'
TOKEN_PATH = SECRETS_DIR / 'token.json'

def _get_client_secret_path():
    for f in SECRETS_DIR.iterdir():
        if f.name.startswith('client_secret') and f.suffix == '.json':
            return str(f)
    raise FileNotFoundError('OAuth client secret not found in secrets/')


def get_oauth_flow(redirect_uri):
    return Flow.from_client_secrets_file(
        _get_client_secret_path(),
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )


def save_credentials(creds):
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PATH, 'w') as f:
        f.write(creds.to_json())


def get_drive_service():
    if not TOKEN_PATH.exists():
        return None

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        save_credentials(creds)

    if not creds.valid:
        return None

    return build('drive', 'v3', credentials=creds)


def get_or_create_folder(service, name, parent_id=None):
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields='files(id, name)', spaces='drive').execute()
    files = results.get('files', [])

    if files:
        return files[0]['id']

    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    if parent_id:
        metadata['parents'] = [parent_id]

    folder = service.files().create(body=metadata, fields='id').execute()
    return folder['id']


def upload_to_drive(project_name, filepath, filename, drive_pasta=None):
    service = get_drive_service()
    if not service:
        return None

    try:
        # Root: Projetos
        projetos_id = get_or_create_folder(service, 'Projetos')

        # Navigate the folder path: drive_pasta segments or project_name
        if drive_pasta:
            segments = [s.strip() for s in drive_pasta.replace('\\', '/').split('/') if s.strip()]
        else:
            segments = [project_name]

        current_parent = projetos_id
        for segment in segments:
            current_parent = get_or_create_folder(service, segment, current_parent)

        # Final folder: Fotos da Instalação
        photos_id = get_or_create_folder(service, 'Fotos da Instalação', current_parent)

        # Detect mimetype
        ext = filename.rsplit('.', 1)[-1].lower()
        mime_map = {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
                    'gif': 'image/gif', 'webp': 'image/webp'}
        mimetype = mime_map.get(ext, 'application/octet-stream')

        media = MediaFileUpload(str(filepath), mimetype=mimetype, resumable=True)
        file_metadata = {
            'name': filename,
            'parents': [photos_id]
        }
        uploaded = service.files().create(
            body=file_metadata, media_body=media, fields='id,webViewLink'
        ).execute()

        return {
            'file_id': uploaded.get('id'),
            'web_link': uploaded.get('webViewLink')
        }
    except Exception as e:
        print(f'[Drive] Upload failed: {e}')
        return None


def disconnect_drive():
    if TOKEN_PATH.exists():
        TOKEN_PATH.unlink()
        return True
    return False
