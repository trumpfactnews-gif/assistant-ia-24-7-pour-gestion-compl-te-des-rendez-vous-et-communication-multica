# Suivi des promesses du guide

Chaque affirmation du guide d'origine, son état réel, et l'endroit où elle est
tenue. Trois états : **tenue**, **tenue autrement** (la promesse est honorée par
un moyen différent, expliqué), **non tenue** (aucune source ne le permet — dit
plutôt que simulé).

---

## §2 — Résultats attendus

| Promesse | État | Où |
|---|---|---|
| Score risque /100 (dette, PE, filings, marge) | tenue | `scoring.py` — 9 règles de risque |
| Score opportunité /100 (upside PE, upside DCF, qualité) | tenue | `scoring.py` — 8 règles d'opportunité |
| Recommandation STRONG_BUY → SELL | tenue | `scoring._recommend`, plus `INSUFFICIENT_DATA` sous 50 % de couverture |
| Facteurs de risque et d'opportunité détaillés | tenue | chaque règle retourne sa preuve chiffrée |
| Données financières (PE, EPS, revenus, dette, marge) | tenue | `sources/sec.py` — XBRL companyfacts |
| Filings SEC récents avec liens | tenue | liens filtrés HTTPS + hôtes SEC |
| Prix cible PE | tenue | `metrics._derive_pe_target` |
| **Prix cible DCF** | tenue | `valuation.discounted_cash_flow` — flux, WACC, valeur terminale, 3 scénarios |
| Rapport HTML | tenue | `report.py` — échappé, CSP stricte |
| Rapport JSON | tenue | `--json` |
| Résumé DeepSeek 100 mots | tenue | `--summary`, désactivé par défaut |
| Alerte Telegram | tenue | `--notify`, texte brut |
| Débat 4 IA + arbitre GLM | tenue autrement | `debate.py` : 3 fournisseurs par **API**, décompte en Python. Perplexity et Intellectia n'ont pas d'API accessible ; y accéder par navigateur télécommandé était la faille S-02. L'arbitre IA est remplacé par un décompte déterministe, non injectable. |

## §3 — Prédictions

| Promesse | État | Où |
|---|---|---|
| Direction du prix à 7 séances | tenue | `technical.classify` — règle publiée, **et mesurée** par `backtest.py` |
| Upside via DCF | tenue | `valuation.py` |
| Upside via PE sectoriel | tenue | `metrics`, avec comparables réels si `--peers` |
| Risque de baisse (dette, PE, absence de filings) | tenue | règles de risque |
| Momentum sectoriel via dashboard Perplexity | non tenue | pas d'API ; le momentum du titre et le régime de marché sont mesurés à la place |
| Catalyseurs identifiés | tenue | items 8-K (`1.01`, `2.01`, `7.01`, `8.01`) |
| Whale watching | tenue autrement | dépôts 13D/13G détectés et datés. L'identité et le sens des positions demandent le parsing de documents HTML libres : non fait. |

Le guide promettait des prédictions tout en admettant « pas de backtesting ».
C'est réglé : la commande `backtest` mesure la règle exacte utilisée, et le
rapport affiche son rendement moyen, son taux de réussite et son écart à la
référence. Si l'écart est nul, c'est écrit.

## §4 — « Pentest » de l'émetteur

| Test annoncé | État | Comment |
|---|---|---|
| Dette : remboursable ? | tenue | passif/actif + dette nette (XBRL) |
| Valorisation : PE excessif ? | tenue | PE vs médiane de comparables ou table sectorielle |
| Rentabilité : marge saine ? | tenue | marge nette |
| Croissance : le revenu croît-il ? | tenue | séries annuelles 10-K, variation et TCAC |
| Liquidité : 12 mois de cash ? | tenue | ratio de liquidité générale + autonomie en mois |
| Dilution : nouvelles actions ? | tenue | variation du nombre d'actions **et** item 8-K `3.02` |
| Gouvernance : initiés ? | tenue | **Form 4 réellement lus** — codes P/S isolés de la rémunération |
| Moat attaquable ? | non tenue | jugement qualitatif ; déclaré « non mesurable » dans la checklist plutôt qu'approximé |
| Disruption par l'IA ? | non tenue | aucune source quantifiable |
| Régulation menaçante ? | non tenue | aucune source structurée |
| Géopolitique (Iran/Chine/UE) | non tenue | non quantifiable ; le régime de marché mesuré le remplace en partie |
| Concentration produit/client | non tenue | demande le parsing du texte des 10-K (segments, clients majeurs) |
| Score de résilience 50/25/25 | tenue | `scoring._attach_resilience` — fondamentaux (XBRL), position marché (cours), macro (indice/VIX/taux). Les composantes absentes ne valent pas 50 : les poids sont renormalisés. |

## §5 — Analyse SEC

| Règle annoncée | État |
|---|---|
| `8-K` ET items ∈ {1.01, 2.01, 7.01, 8.01} → ALERTE FORTE | tenue — colonne `items` lue |
| `Form 4` ET achat d'initié → SIGNAL BULLISH | tenue — XML parsé, achat groupé distingué de l'achat isolé et de la rémunération |
| `10-Q` ET revenue > attentes → MOMENTUM POSITIF | tenue autrement — aucun consensus d'analystes dans les sources publiques ; la croissance est mesurée **contre la trajectoire propre de l'entreprise** |
| `13D` ET nouvel investisseur → CATALYSEUR | tenue autrement — dépôt détecté ; « nouvel » exigerait un historique de participations |
| 0 filing depuis 6 mois → RISQUE | tenue — et distingué d'un échec d'appel EDGAR |

## §6 — Sources

| Source | État |
|---|---|
| SEC EDGAR (submissions, archives) | tenue |
| SEC XBRL companyfacts | tenue — en séries temporelles |
| Yahoo Finance | tenue — API JSON directe, repli Stooq |
| Perplexity Finance via Chrome CDP | **supprimée** — voir S-02 de l'audit |
| DeepSeek API | tenue |
| Indices de marché (S&P 500, VIX, 10 ans US) | ajoutée — nécessaire au volet macro |

## §7 — Méthodologie

| Promesse | État | Où |
|---|---|---|
| Value : acheter sous la valeur intrinsèque | tenue | marge de sécurité DCF |
| Momentum contrarié | tenue | signal technique + critère de pessimisme |
| Catalyseur déclencheur | tenue | items 8-K, achats d'initiés |
| Critères d'achat composites | tenue | `checklist.entry_checklist` — 5 critères, chacun avec sa preuve |
| Critères de vente composites | tenue | `checklist.exit_checklist` |
| Allocation All Weather 30/40/15/7,5/7,5 | tenue | `portfolio.ALL_WEATHER` |
| Max 10 % par position, 20 % par secteur | tenue | `portfolio.build_plan` |
| Stop-loss -10 %, prise de profit +50 % | tenue | niveaux calculés sur le cours |

Le « sentiment pessimiste » du critère d'achat n'a pas de source de sentiment
dans le périmètre. Il est approché par deux marqueurs de prix (RSI bas, repli
depuis les plus hauts) — et l'intitulé du critère le dit.

## §8 — Limites annoncées

| Limite d'origine | État |
|---|---|
| Données SEC en différé 24-48 h | inchangée — inhérente à EDGAR |
| Chrome CDP instable | supprimée avec le composant |
| API DeepSeek coûteuse | plafonnée (`max_tokens`), désactivée par défaut |
| Score simpliste | règles nommées, pondérées, tracées, avec indice de confiance |
| Dépendance `.env` | secrets validés, permissions vérifiées, expurgés des logs |
| **Pas de backtesting** | levée — `backtest.py`, avec ses propres limites énoncées |

## §11 — Commandes

| Commande d'origine | État |
|---|---|
| `--ticker` | `analyze --ticker` |
| `--summary` | tenue (l'option existait mais n'était pas utilisée) |
| `--watch` | tenue (documentée mais absente du code) — `watch --interval` |
| `--list` | tenue |
| `tfn_debate.py --ticker` | `debate --ticker` |
| — | ajout : `backtest --ticker` |

---

## Ce qui reste hors de portée

Ces points demandent une source que le périmètre ne contient pas. Les ajouter
supposerait un parsing du texte des 10-K (segments, clients, facteurs de
risque), un flux de consensus d'analystes, ou une base d'événements
réglementaires — pas un ajustement de code.

* moat, disruption, risque réglementaire, géopolitique, concentration client ;
* consensus d'analystes (« revenue > attentes ») ;
* identité et sens des positions des grands investisseurs ;
* backtest du **volet fondamental** : il faudrait des données XBRL « telles que
  connues à la date ». Les faits sont retraités a posteriori, donc un backtest
  sur les données actuelles serait flatteur et faux. Seul le volet technique
  est mesuré.
