#!/usr/bin/env python3
"""OOH Project Manager - Entry Point"""

import os

from app import create_app

app = create_app()

if __name__ == '__main__':
    # Debug defaults to off. The Werkzeug debugger exposes an interactive
    # console to anyone who can reach a traceback, so it must be opted into
    # explicitly (FLASK_DEBUG=1) and never in a deployed environment.
    debug = os.environ.get('FLASK_DEBUG', '').strip().lower() in ('1', 'true', 'yes', 'on')
    # Bind to loopback by default; set FLASK_RUN_HOST=0.0.0.0 deliberately when
    # the dev server needs to be reachable from another machine.
    host = os.environ.get('FLASK_RUN_HOST', '127.0.0.1')
    port = int(os.environ.get('FLASK_RUN_PORT', '5000'))
    app.run(debug=debug, host=host, port=port)
