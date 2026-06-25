"""Point d'entrée WSGI pour la production (gunicorn wsgi:app)."""

from sentinelle.app import create_app

app = create_app()
