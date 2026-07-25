# OSINT Financial Intelligence v4

Analyse financière sur sources publiques (SEC EDGAR, données de marché), avec
scoring déterministe et traçable.

> Aide à la décision documentaire. **Ne constitue pas un conseil en
> investissement.** Les scores viennent d'une heuristique, pas d'un modèle
> validé statistiquement.

Réécriture de `osint_v3.py` — voir [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) pour
les 15 failles et 13 défauts corrigés.

## Installation

Aucune dépendance : bibliothèque standard Python ≥ 3.10.

```bash
cp .env.example .env && chmod 600 .env   # puis renseigner SEC_USER_AGENT
python -m osint_financial analyze --ticker AAPL
```

## Commandes

```bash
python -m osint_financial analyze --ticker AAPL              # analyse + rapport HTML
python -m osint_financial analyze --ticker AAPL --summary    # + résumé LLM (optionnel)
python -m osint_financial analyze --ticker AAPL --notify     # + alerte Telegram
python -m osint_financial analyze --ticker AAPL --json       # sortie machine
python -m osint_financial list --ticker AAPL --limit 10      # historique
python -m osint_financial debate --ticker AAPL               # consultation multi-modèles
```

Codes de sortie : `0` succès · `2` entrée invalide · `3` configuration ·
`4` échec d'exécution.

## Configuration

| Variable | Requis | Rôle |
|----------|--------|------|
| `SEC_USER_AGENT` | **oui** | User-Agent nominatif avec courriel — imposé par data.sec.gov |
| `OSINT_OUTPUT_DIR` | non | répertoire des rapports (défaut `osint_reports`) |
| `OSINT_DB_PATH` | non | base SQLite |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | non | alertes (`--notify`) |
| `DEEPSEEK_API_KEY` | non | résumé (`--summary`) et avis « fondamental » |
| `MOONSHOT_API_KEY`, `ZHIPU_API_KEY` | non | avis supplémentaires pour `debate` |
| `OSINT_HTTP_TIMEOUT`, `OSINT_HTTP_RETRIES`, `OSINT_RPS` | non | réglages réseau |

Les variables d'environnement l'emportent sur `.env`. Le fichier est refusé s'il
est lisible par le groupe ou par tous.

## Architecture

```
cli.py            entrée, sous-commandes, codes de sortie
config.py         .env + validation, secrets enregistrés pour expurgation
validation.py     ticker, CIK, confinement de chemin, filtrage d'URL
httpclient.py     HTTPS + allowlist + timeout + quota + débit + reprise
sources/sec.py    ticker→CIK, filings, faits XBRL
sources/market.py cotation Yahoo, repli Stooq
metrics.py        agrégation, dérivées, traçabilité des sources
scoring.py        9 règles nommées, indice de confiance
report.py         HTML entièrement échappé, CSP stricte, écriture atomique
database.py       SQLite paramétré, 0600, WAL
notify.py         Telegram en texte brut
summarizer.py     LLM optionnel, contenu tiers assaini
debate.py         consultation multi-modèles, agrégation locale
```

## Lecture des scores

* **Risque / Opportunité** : partent de 50, ajustés par des règles nommées.
  Chaque facteur affiché indique la valeur chiffrée qui l'a déclenché.
* **Confiance** : part des règles réellement évaluables. Sous 50 %, la
  recommandation devient `INSUFFICIENT_DATA` — l'outil refuse de conclure
  plutôt que de produire un « HOLD » vide de sens.
* **Critères non évaluables** : listés explicitement dans la sortie et le
  rapport.

## Tests

```bash
python -m unittest discover -s tests -v
```

63 tests, sans accès réseau. Chaque faille de l'audit a son test de
non-régression.

## Limites connues

* Données SEC en différé (24-48 h) : inadapté au trading intrajournalier.
* PE sectoriels statiques, pas de médiane calculée sur comparables.
* Pas de DCF, pas de prédiction de cours, pas de backtest — voir §3 de l'audit.
* Perplexity Finance et Intellectia ne sont plus des sources : ils n'ont pas
  d'API accessible et y accéder par pilotage de navigateur était la faille la
  plus grave de la version précédente (S-02).
