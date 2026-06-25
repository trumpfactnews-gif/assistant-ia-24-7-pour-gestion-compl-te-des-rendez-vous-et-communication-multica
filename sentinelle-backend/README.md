# 🛡️ Sentinelle — Backend de détection de fraude par SMS

> Copilote de sécurité numérique pour les citoyens canadiens : détecte **avant**
> que la fraude ne réussisse, en combinant heuristiques expertes, apprentissage
> automatique, anti-hameçonnage et intelligence communautaire.

Ce dépôt contient **l'épine dorsale** de Sentinelle : un microservice Python/Flask
qui analyse un message texte et renvoie un verdict de fraude explicable, en
français et en anglais.

---

## Ce qui est réellement livré ici

| Composant | État | Description |
|-----------|------|-------------|
| Moteur de détection hybride | ✅ Fonctionnel | Heuristiques + ML + URL + communauté |
| Heuristiques Canada/Québec | ✅ Fonctionnel | 16 règles bilingues (banque, ARC, colis, « grand-maman », 407 ETR, crypto…) |
| Anti-hameçonnage d'URL | ✅ Fonctionnel | Domaines sosies, typosquatting, raccourcisseurs, TLD abusifs |
| Classifieur ML | ✅ Fonctionnel | TF-IDF (mots+caractères) + régression logistique, bilingue |
| Base communautaire | ✅ Fonctionnel | Signalements + blocage au seuil, numéros **hachés** |
| API REST | ✅ Fonctionnel | `/analyze`, `/report`, `/check-url`, `/check-number`, `/stats`, `/health` |
| Tests | ✅ 44 tests | `pytest` (heuristiques, URL, moteur, dépôt, API) |
| Déploiement Docker | ✅ Fonctionnel | Image multi-couches, gunicorn, modèle entraîné au build |
| Application mobile React Native | ⛔ Non incluse | Voir [« Intégration mobile »](#intégration-mobile-react-native) |
| Paiement premium (Stripe/Google Play) | ⛔ Non inclus | Voir [Feuille de route](#feuille-de-route) |

> **Transparence.** Le modèle ML est entraîné sur un **jeu de données seed** de
> 100 exemples illustratifs (voir `sentinelle/ml/data/seed_dataset.csv`). Il
> démontre le pipeline complet, mais n'a **aucune garantie de performance en
> production** : un déploiement réel exige un corpus de plusieurs milliers de
> messages étiquetés. Les scores de détection sont des **aides à la décision**,
> pas un verdict infaillible.

---

## Démarrage rapide

```bash
cd sentinelle-backend

# 1. Environnement + dépendances
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# 2. (Optionnel mais recommandé) Entraîner le modèle ML
python -m sentinelle.ml.train --output data/model.joblib

# 3. Lancer l'API (mode développement)
python run.py
# -> http://127.0.0.1:8000

# 4. Tester
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{"message":"ARC: remboursement de 458$ en attente. Réclamez: http://arc-remboursement.top"}'
```

Sans modèle entraîné, le moteur fonctionne quand même (heuristiques + URL +
communauté) : le composant ML est simplement neutre.

### Avec Docker

```bash
docker compose up --build      # API sur http://localhost:8000
```

L'image entraîne le modèle pendant le build et démarre gunicorn.

### Avec Make

```bash
make setup   # venv + dépendances
make train   # entraîne le modèle
make run     # serveur de dev
make test    # suite de tests
```

---

## Comment fonctionne la détection

Quatre sources de signal sont fusionnées en un score de risque **0–100** :

```
                    ┌─────────────────┐
   message (+ ┌────►│  Heuristiques   │── score + catégorie
   expéditeur)│     │  (16 règles)    │
              │     ├─────────────────┤
              ├────►│  Classifieur ML │── probabilité de fraude
              │     │  (TF-IDF + LR)  │
              │     ├─────────────────┤   ┌──────────────────┐
              ├────►│  Analyse d'URL  │──►│  Moteur          │──► Verdict
              │     │  (anti-phishing)│   │  (combinaison)   │    { score, niveau,
              │     ├─────────────────┤   └──────────────────┘      catégorie,
              └────►│  Base commun.   │── numéro/domaine signalé      signaux,
                    │  (signalements) │                               explication FR/EN,
                    └─────────────────┘                               action recommandée }
```

- **Combinaison défensive** : le ML peut *relever* le verdict (attraper une
  fraude inédite) mais ne peut que faiblement l'*abaisser*. La communauté et
  certaines combinaisons critiques (identifiants demandés + lien piégé) imposent
  un **plancher** de risque.
- **Niveaux** : `safe` (0–24) · `caution` (25–49) · `suspicious` (50–74) ·
  `fraud` (75–100).

Détails complets dans [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## API en bref

| Méthode | Route | Rôle |
|---------|-------|------|
| `POST` | `/api/v1/analyze` | Analyser un message → verdict |
| `POST` | `/api/v1/report` | Signaler un numéro/domaine frauduleux |
| `GET`  | `/api/v1/check-number?number=…` | Réputation d'un numéro (caller ID) |
| `POST` | `/api/v1/check-url` | Analyse anti-hameçonnage d'une URL |
| `GET`  | `/api/v1/stats` | Statistiques communautaires |
| `GET`  | `/health` | Sonde de santé |

Référence complète + exemples : [`docs/API.md`](docs/API.md).

---

## Intégration mobile (React Native)

L'application mobile (non incluse) intercepte les SMS via un module natif
(BroadcastReceiver Android, avec **consentement explicite** de l'utilisateur) et
appelle l'API :

```js
const res = await fetch("https://api.sentinelle.ca/api/v1/analyze", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": API_KEY },
  body: JSON.stringify({ message: smsBody, sender: smsFrom, lang: "fr" }),
});
const verdict = await res.json();
if (verdict.is_fraud) {
  showShieldNotification(verdict.explanation.fr, verdict.recommended_action.fr);
}
```

> ⚠️ **iOS** ne permet pas l'interception silencieuse des SMS. Sur iOS, le modèle
> viable est une **extension de filtrage de SMS** (`IdentityLookup`/
> `ILMessageFilterExtension`) ou le partage manuel d'un message suspect vers l'app.

---

## Configuration

Toutes les variables ont des valeurs par défaut raisonnables. Voir
[`.env.example`](.env.example). En **production**, définir impérativement
`SENTINELLE_SECRET_KEY` (sel des condensés de numéros) et, idéalement,
`SENTINELLE_API_KEY`.

---

## Vie privée & éthique

Sentinelle traite des données sensibles. Principes appliqués :

- **Numéros jamais stockés en clair** : seul un condensé salé (SHA-256) est
  conservé ; les affichages sont masqués (`+1514***0199`).
- **Pas de stockage du contenu des messages** par défaut (analyse à la volée).
- **Minimisation** : la base communautaire ne garde que ce qui est nécessaire au
  blocage (cible, catégorie, compteur).

Détails et cadre **Loi 25 (Québec) / LPRPDE** : [`docs/PRIVACY.md`](docs/PRIVACY.md).

---

## Feuille de route

- [ ] Élargir le corpus d'entraînement (objectif : plusieurs milliers d'exemples réels).
- [ ] Module premium : abonnement Stripe / Google Play (interface de gestion).
- [ ] Webhooks de menaces partagées entre instances ; magasin Redis pour le rate-limit.
- [ ] Application React Native (Android d'abord) + extension de filtrage iOS.
- [ ] Tableau de bord communautaire (tendances de fraude par région).
- [ ] Migration SQLite → PostgreSQL pour l'échelle.

---

## Licence

MIT.

> **Avertissement.** Sentinelle est un outil d'aide à la vigilance. Il ne
> remplace ni un avis juridique, ni votre institution financière, ni le
> [Centre antifraude du Canada](https://antifraudcentre-centreantifraude.ca/)
> (**1-888-495-8501**). Aucune détection automatisée n'est parfaite.
