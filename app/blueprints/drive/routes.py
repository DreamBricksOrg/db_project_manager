import os
from flask import redirect, url_for, request, flash, session

# Allow OAuth over HTTP for local development
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
# Google may return extra scopes — allow it
os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

from app.blueprints.drive import drive_bp
from app.blueprints.auth.routes import login_required
from app.services.google_drive import get_oauth_flow, save_credentials, get_drive_service


@drive_bp.route('/auth')
@login_required
def auth():
    """Start Google OAuth flow."""
    flow = get_oauth_flow(request.host_url.rstrip('/') + url_for('drive.callback'))
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['drive_oauth_state'] = state
    # Save code_verifier for PKCE
    session['drive_code_verifier'] = flow.code_verifier
    return redirect(authorization_url)


@drive_bp.route('/callback')
@login_required
def callback():
    """Handle Google OAuth callback."""
    flow = get_oauth_flow(request.host_url.rstrip('/') + url_for('drive.callback'))
    # Restore PKCE code_verifier
    flow.code_verifier = session.pop('drive_code_verifier', None)
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    save_credentials(creds)
    flash('Google Drive conectado com sucesso!', 'success')
    return redirect(url_for('projects.list_projects'))


@drive_bp.route('/status')
@login_required
def status():
    """Check if Drive is connected."""
    service = get_drive_service()
    if service:
        try:
            about = service.about().get(fields='user').execute()
            email = about.get('user', {}).get('emailAddress', 'desconhecido')
            flash(f'Drive conectado: {email}', 'success')
        except Exception:
            flash('Drive com token inválido. Reconecte.', 'warning')
    else:
        flash('Drive não conectado. Clique em "Conectar Drive".', 'info')
    return redirect(url_for('projects.list_projects'))


@drive_bp.route('/check')
@login_required
def check():
    """JSON check if Drive is connected."""
    service = get_drive_service()
    return {'connected': service is not None}
