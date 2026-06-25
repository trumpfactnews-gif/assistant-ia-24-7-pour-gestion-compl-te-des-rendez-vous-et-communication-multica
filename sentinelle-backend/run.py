"""Serveur de développement Sentinelle.

Pour la production, utiliser gunicorn :  gunicorn wsgi:app
"""

import os

from sentinelle.app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    debug = app.config["SENTINELLE_CONFIG"].debug
    app.run(host="0.0.0.0", port=port, debug=debug)
