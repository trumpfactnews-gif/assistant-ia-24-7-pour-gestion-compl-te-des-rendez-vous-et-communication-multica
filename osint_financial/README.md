# OSINT Financial Intelligence v4

Analyse financière sur sources publiques (SEC EDGAR, données de marché), avec
scoring déterministe et traçable.

> Aide à la décision documentaire. **Ne constitue pas un conseil en
> investissement.** Les scores viennent d'une heuristique, pas d'un modèle
> validé statistiquement.

Réécriture de `osint_v3.py`. Deux documents complètent celui-ci :

* [`SECURITY_AUDIT.md`](SECURITY_AUDIT.md) — les 15 failles et 13 défauts
  corrigés, avec preuve de concept et test de non-régression ;
* [`PROMESSES.md`](PROMESSES.md) — chaque affirmation du guide d'origine, son
  état réel (tenue / tenue autrement / non tenue) et l'endroit où elle est
  tenue.

## Installation

Aucune dépendance : bibliothèque standard Python ≥ 3.10.

```bash
cp .env.example .env && chmod 600 .env   # puis renseigner SEC_USER_AGENT
python -m osint_financial analyze --ticker AAPL
```

## Commandes

```bash
python -m osint_financial analyze --ticker AAPL
python -m osint_financial analyze --ticker AAPL --peers MSFT,GOOGL,META
python -m osint_financial analyze --ticker AAPL --summary --notify --json
python -m osint_financial backtest --ticker AAPL --horizon 7 --range 5y
python -m osint_financial watch --ticker AAPL --interval 900 --notify
python -m osint_financial list --ticker AAPL --limit 10
python -m osint_financial debate --ticker AAPL
```

Options de périmètre (chaque appel réseau se paie) : `--no-history`,
`--no-insiders`, `--no-macro`, `--no-backtest`, `--no-report`.

Codes de sortie : `0` succès · `2` entrée invalide · `3` configuration ·
`4` échec d'exécution.

## Ce que produit une analyse

* **Scores** risque / opportunité / net, avec la valeur chiffrée qui déclenche
  chaque facteur ;
* **Confiance** — part des règles réellement évaluables. Sous 50 %, la
  recommandation devient `INSUFFICIENT_DATA` : l'outil refuse de conclure
  plutôt que d'afficher un « HOLD » vide ;
* **Résilience** — 50 % fondamentaux, 25 % position de marché, 25 % macro ; les
  composantes absentes sont renormalisées, jamais remplacées par une valeur
  neutre ;
* **Technique** — signal directionnel à 7 séances, momentum, RSI, volatilité,
  drawdown ;
* **Backtest** — le rendement réellement observé après ce signal dans le passé
  du titre, comparé à la moyenne de toutes les séances ;
* **DCF** — valeur par action, fourchette à ±5 points de croissance, et la
  liste des hypothèses ;
* **Initiés** — Form 4 lus, achats de marché distingués de la rémunération ;
* **Dépôts SEC** — avec les items 8-K et le marquage des items d'alerte ;
* **Checklists §7** — critères d'achat et de vente, chacun rempli / non rempli /
  non mesurable ;
* **Dimensionnement** — pondération suggérée, stop-loss, prise de profit,
  cadre All Weather ;
* **Sorties** — rapport HTML, JSON, base SQLite, alerte Telegram.

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
pipeline.py       orchestration d'une analyse complète
config.py         .env + validation, secrets enregistrés pour expurgation
validation.py     ticker, CIK, confinement de chemin, filtrage d'URL
httpclient.py     HTTPS + allowlist + timeout + quota + débit + reprise
sources/sec.py    ticker→CIK, filings + items 8-K, séries XBRL
sources/forms.py  Form 4 (XML), achats/ventes d'initiés, garde anti-XXE
sources/prices.py historique quotidien (Yahoo, repli Stooq)
sources/market.py cotation instantanée
metrics.py        agrégation, croissance, liquidité, dilution, traçabilité
technical.py      SMA, RSI, momentum, signal directionnel
backtest.py       mesure du signal sur l'historique
valuation.py      DCF (3 scénarios) et PE de comparables
macro.py          régime de marché (S&P 500, VIX, taux 10 ans)
scoring.py        17 règles nommées, confiance, résilience 50/25/25
checklist.py      critères d'achat et de vente du §7
portfolio.py      dimensionnement, stop-loss, All Weather
report.py         HTML entièrement échappé, CSP stricte, écriture atomique
database.py       SQLite paramétré, 0600, WAL
notify.py         Telegram en texte brut
summarizer.py     LLM optionnel, contenu tiers assaini
debate.py         consultation multi-modèles, agrégation locale
```

## Tests

```bash
python -m unittest discover -s tests -v
```

146 tests, sans accès réseau : chaque faille de l'audit a son test de
non-régression, et chaque capacité ajoutée sa vérification (parsing Form 4 et
refus XXE, absence de données futures dans le backtest, bornes du DCF,
renormalisation de la résilience, arrêt du mode `watch`).

## Limites connues

* Données SEC en différé (24-48 h) : inadapté au trading intrajournalier.
* Le backtest ne couvre que le volet technique, en échantillon, sur un seul
  titre, sans frais — voir §3 de l'audit.
* Le DCF est un modèle d'hypothèses ; lisez la fourchette, pas le point central.
* Moat, disruption, régulation, géopolitique et concentration client restent
  hors de portée des sources utilisées, et sont affichés comme tels.
* Perplexity Finance et Intellectia ne sont plus des sources : pas d'API
  accessible, et y accéder par pilotage de navigateur était la faille la plus
  grave de la version précédente (S-02).
