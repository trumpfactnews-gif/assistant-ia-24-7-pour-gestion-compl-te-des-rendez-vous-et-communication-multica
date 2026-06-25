.PHONY: help setup train run test docker-build docker-up docker-down clean

help:
	@echo "Cibles disponibles :"
	@echo "  setup        Crée le venv et installe les dépendances (dev)"
	@echo "  train        Entraîne le modèle ML sur le jeu de données seed"
	@echo "  run          Lance le serveur de développement (port 8000)"
	@echo "  test         Exécute la suite de tests (pytest)"
	@echo "  docker-build Construit l'image Docker"
	@echo "  docker-up    Démarre l'API via docker compose"
	@echo "  docker-down  Arrête docker compose"
	@echo "  clean        Supprime les fichiers générés"

setup:
	python3 -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements-dev.txt

train:
	. .venv/bin/activate && python -m sentinelle.ml.train --output data/model.joblib

run:
	. .venv/bin/activate && python run.py

test:
	. .venv/bin/activate && pytest -q

docker-build:
	docker build -t sentinelle-api:latest .

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf data .pytest_cache **/__pycache__ .coverage
