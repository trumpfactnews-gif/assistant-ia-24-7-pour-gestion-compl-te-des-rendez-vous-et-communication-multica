# Architecture — Sentinelle backend

## Vue d'ensemble

```
sentinelle-backend/
├── run.py / wsgi.py          # points d'entrée (dev / prod gunicorn)
├── sentinelle/
│   ├── config.py             # configuration (env-surchargeable)
│   ├── app.py                # application factory Flask (auth, rate-limit, CORS)
│   ├── detection/
│   │   ├── patterns.py       # DONNÉES : règles, domaines officiels, marques
│   │   ├── heuristics.py     # règles → signaux + score (noisy-OR)
│   │   ├── url_analysis.py   # anti-hameçonnage (sosies, typosquat, shorteners)
│   │   ├── classifier.py     # enveloppe du modèle ML (chargement paresseux)
│   │   └── engine.py         # ORCHESTRATION : fusion des 4 sources → Verdict
│   ├── db/
│   │   ├── schema.sql        # tables reports + blocklist
│   │   ├── database.py       # connexion SQLite (WAL)
│   │   └── repository.py     # CRUD + agrégation communautaire
│   ├── api/
│   │   ├── routes.py         # blueprint des endpoints v1
│   │   ├── schemas.py        # validation des entrées
│   │   └── errors.py         # gestion d'erreurs JSON
│   ├── ml/
│   │   ├── train.py          # pipeline d'entraînement
│   │   └── data/seed_dataset.csv
│   └── utils/
│       ├── privacy.py        # normalisation/hachage/masquage de numéros
│       └── i18n.py           # libellés & recommandations bilingues
└── tests/                    # pytest (44 tests)
```

## Principe de conception : données ≠ logique

`patterns.py` ne contient **que des données** (règles regex pondérées, listes de
domaines officiels, marques usurpées). Les algorithmes vivent ailleurs. On peut
donc ajuster la détection — ou, à terme, remplacer les heuristiques par un modèle
entraîné — sans toucher au moteur.

## Flux d'une requête `/analyze`

1. **Validation** (`api/schemas.py`) — longueur, types, langue.
2. **Heuristiques** (`heuristics.evaluate`) — applique les 16 règles ; produit
   des signaux et un score via **noisy-OR** (les signaux faibles s'accumulent,
   un signal fort domine, plafond 100). Filtre les faux positifs connus
   (livraison d'OTP légitime).
3. **Analyse d'URL** (`url_analysis.analyze_text_urls`) — extrait et note chaque
   lien ; un domaine officiel reconnu obtient un score 0.
4. **ML** (`classifier.predict_proba`) — probabilité de fraude, ou `None` si
   aucun modèle.
5. **Communauté** (`repository`) — l'expéditeur ou un domaine est-il déjà bloqué ?
6. **Combinaison** (`engine._combine`) — voir ci-dessous.
7. **Réponse** — `Verdict.to_dict()` (score, niveau, catégorie, signaux,
   explication FR/EN, action recommandée).

## Logique de combinaison (défensive)

```python
rule_component = max(heuristiques, url)

si ML disponible :
    blended = (1 - poids_ml) * rule_component + poids_ml * (ml * 100)
    score   = max(rule_component * 0.7, blended, (ml*100) * 0.7)
sinon :
    score   = rule_component

score = max(score, communauté)            # plancher communautaire

# planchers pour combinaisons critiques
si (identifiants_demandés et lien_piégé) : score = max(score, 85)
si communauté_bloquée                    : score = max(score, 90)
```

**Intuition** : le ML sert surtout à *attraper l'inédit* (relever le score). On
limite sa capacité à *abaisser* un signal de règle fort (`* 0.7`), parce qu'un
faux négatif (fraude manquée) coûte plus cher qu'un faux positif (alerte de trop)
dans un produit de protection.

## Anti-hameçonnage d'URL

- **Domaine enregistrable** (eTLD+1) extrait avec gestion des suffixes
  multi-niveaux canadiens (`gc.ca`, `qc.ca`…). Heuristique, pas une Public
  Suffix List complète.
- **Allowlist** des domaines officiels (banques, gouvernements, postes, télécoms).
- **Sosies** : jeton de marque présent hors du domaine officiel
  (`desjardins.secure-login.xyz`).
- **Typosquatting** : distance d'édition ≤ 2 sur la racine (`desjardlns.com`).
- Autres : IP littérale, punycode, `@` trompeur, raccourcisseurs, TLD abusifs,
  empilement de sous-domaines.

## Modèle communautaire

- Une cible est **bloquée** au-delà de `block_threshold` **rapporteurs distincts**
  (anti-abus : un seul acteur ne peut pas bloquer un numéro).
- `blocklist` est dérivée et recalculée à chaque signalement à partir de `reports`
  (source de vérité) — pas de dérive d'état.

## Choix de stockage

SQLite (WAL) : zéro configuration, suffisant pour un nœud unique et le
développement. Le schéma et le dépôt sont écrits pour migrer vers PostgreSQL
(mêmes requêtes, types compatibles) quand l'échelle l'exige.

## Concurrence / déploiement

- Connexions SQLite à durée de vie courte (context manager, commit/rollback auto).
- Rate-limiter **en mémoire** par nœud → à remplacer par Redis en horizontal.
- gunicorn (2 workers × 4 threads par défaut) ; le modèle ML est chargé
  paresseusement par worker et mis en cache.
