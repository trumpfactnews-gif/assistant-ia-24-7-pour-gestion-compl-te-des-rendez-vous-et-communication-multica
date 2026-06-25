# Image de production Sentinelle
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SENTINELLE_ENV=production \
    SENTINELLE_DB_PATH=/app/data/sentinelle.db \
    SENTINELLE_MODEL_PATH=/app/data/model.joblib

WORKDIR /app

# Dépendances d'abord (meilleure mise en cache des couches).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code applicatif.
COPY . .

# Entraîne le modèle au build : l'image livrée embarque déjà le classifieur ML.
RUN python -m sentinelle.ml.train --output /app/data/model.joblib --quiet

# Utilisateur non privilégié.
RUN useradd --create-home --uid 10001 sentinelle \
    && chown -R sentinelle:sentinelle /app
USER sentinelle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

# 2 workers x 4 threads : bon point de départ ; ajuster selon le CPU/charge.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", \
     "--timeout", "30", "--access-logfile", "-", "wsgi:app"]
