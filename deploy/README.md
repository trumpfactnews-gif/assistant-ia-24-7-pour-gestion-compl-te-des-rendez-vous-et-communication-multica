# Déploiement Sentinelle — Canada (AWS `ca-central-1`)

Met l'API Sentinelle en ligne, en **HTTPS**, sur un serveur **en région
canadienne** (résidence des données). Cap : ~1 heure.

> **Ce que ça donne** : une API publique HTTPS hébergée au Canada, avec clé d'API
> et CORS verrouillé — assez pour brancher la console/l'app et faire une démo à un
> prospect.
> **Ce que ça ne donne PAS** : SOC 2, pen test, revue de risque tiers. Ce sont des
> chantiers séparés (voir `../docs/GO-TO-MARKET.md`).

## Architecture
```
Internet ──HTTPS──> Caddy (443, certificat Let's Encrypt auto) ──> API gunicorn (8000, interne)
                                                                     └─ volume data/ (base + modèle), au Canada
```

## Prérequis
- Un compte AWS et un **nom de domaine** (ex. `sentinelle.ca`).
- Une IP publique en `ca-central-1`.

## Étape 1 — Créer le serveur (région CANADA)
Le plus simple : **Lightsail** (ou EC2).
- Région : **`ca-central-1` (Canada Central, Montréal)** ← important pour la résidence des données.
- Image : **Ubuntu 22.04**. Taille : 2 Go RAM minimum (le build entraîne le modèle).
- Ouvre les ports **22 (SSH)**, **80** et **443** (pare-feu Lightsail/Security Group).
- Attache une **IP statique**.

## Étape 2 — DNS
Crée un enregistrement **A** : `api.tondomaine.ca` → l'IP statique du serveur.
(Attends que ça propage : `ping api.tondomaine.ca` doit répondre l'IP.)

## Étape 3 — Installer Docker (sur le serveur, en SSH)
```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin git
sudo usermod -aG docker $USER && newgrp docker
```

## Étape 4 — Récupérer le code
```bash
git clone <URL_DU_DÉPÔT> sentinelle && cd sentinelle
git checkout claude/adoring-mayer-zv3m0g
cd deploy
```

## Étape 5 — Configurer
```bash
cp .env.prod.example .env
nano .env        # mets ton DOMAIN, génère les clés :
                 #   openssl rand -hex 32   -> SENTINELLE_SECRET_KEY
                 #   openssl rand -hex 24   -> SENTINELLE_API_KEY
                 #   SENTINELLE_CORS_ORIGIN -> l'origine de ta console
```

## Étape 6 — Lancer
```bash
docker compose -f docker-compose.prod.yml up -d --build
```
Caddy obtient automatiquement le certificat HTTPS pour `DOMAIN`.

## Étape 7 — Vérifier
```bash
curl https://api.tondomaine.ca/health
# -> {"status":"ok","service":"sentinelle","ml_available":true}
```
Puis pointe la **console** (`../console/index.html`) et l'**app** vers
`https://api.tondomaine.ca` (+ ta clé d'API).

---

## Résidence des données (argument banque)
- Serveur et **toutes les données** (base communautaire + modèle) dans le volume
  Docker, **sur l'instance `ca-central-1`** — rien ne quitte le Canada.
- N'active aucun service AWS multi-région. Si tu passes à une base gérée, prends
  **RDS PostgreSQL en `ca-central-1`**.
- Conserve les **journaux** au Canada (CloudWatch `ca-central-1` ou local).

## Checklist sécurité (avant de montrer à un prospect)
- [ ] `SENTINELLE_SECRET_KEY` et `SENTINELLE_API_KEY` générés (jamais les valeurs d'exemple).
- [ ] `SENTINELLE_CORS_ORIGIN` = ton origine réelle (pas `*`).
- [ ] Ports : seuls 22/80/443 ouverts ; SSH par clé uniquement.
- [ ] Sauvegardes du volume `sentinelle-data` (snapshot quotidien).
- [ ] Mises à jour OS (`unattended-upgrades`).

## Sauvegarde
```bash
docker run --rm -v sentinelle-data:/data -v $PWD:/backup alpine \
  tar czf /backup/sentinelle-backup-$(date +%F).tgz -C /data .
```

## Mettre à jour
```bash
git pull && docker compose -f docker-compose.prod.yml up -d --build
```

## Passer à l'échelle (plus tard)
- **SQLite → PostgreSQL** (RDS `ca-central-1`) : le schéma et le dépôt sont déjà
  écrits pour migrer.
- Plusieurs réplicas `api` derrière Caddy/ALB ; **Redis** pour le rate-limit partagé.
- Conteneurs gérés : **ECS Fargate** (`ca-central-1`) ou App Runner.
