# predopt — Optimiseur de paris pour marchés prédictifs décentralisés

Logiciel de calcul mathématique pour identifier les meilleures opportunités de
paris sur les plateformes de prédiction décentralisées (style Polymarket) :
génération et analyse de combinaisons à très grande échelle (milliers de
milliards de possibilités couvertes), calcul de probabilités par type de
marché, pondération statistique par données historiques, et classement des
opportunités par rapport probabilité de gain / montant risqué.

**Zéro dépendance** : Python ≥ 3.10 standard uniquement.

---

## Démarrage rapide

```bash
# Depuis la racine du dépôt (aucune installation requise)
export PYTHONPATH=src

# 1. Générer un univers de marchés synthétiques pour tester
python3 -m predopt generate --markets 60 --out markets.json

# 2. Analyser : classer les meilleures opportunités (simples + combinés)
python3 -m predopt analyze markets.json --max-legs 3 --top 15 --bankroll 1000

# 3. Benchmark à grande échelle
python3 -m predopt bench --markets 300 --legs 5
```

Installation propre (optionnelle) :

```bash
pip install -e .            # expose la commande `predopt`
pip install -e ".[dev]"     # + pytest
```

Un fichier d'exemple est fourni : [`examples/sample_markets.json`](examples/sample_markets.json).

---

## Pipeline de calcul

```
Prix des marchés (JSON)
   │
   ▼
① Dé-vig ────────────── retrait de la marge de la plateforme
   │                     (méthode « power » : corrige le biais favori/outsider)
   ▼
② Pondération ───────── fusion marché ⊕ historique ⊕ modèle
   │                     · lissage bayésien Beta des fréquences historiques
   │                     · mélange en log-odds pondéré par le volume de données
   ▼
③ Jambes candidates ─── une issue = une jambe (prob. estimée, cote = 1/prix)
   │
   ▼
④ Moteur combinatoire ─ branch-and-bound exact sur l'espace Σₖ C(n,k)
   │                     (milliers de milliards de combinaisons, < 1 s)
   ▼
⑤ Classement ────────── EV, Sharpe, croissance log, probabilité
                         + mises conseillées (Kelly fractionné)
```

### ① Probabilités implicites et dé-vig

Le prix d'un contrat (∈ ]0,1[) est une probabilité implicite, mais la somme
des prix d'un marché dépasse 1 (marge / spread). Deux méthodes de retrait :

- `proportional` — normalisation simple `pᵢ / Σp` ;
- `power` (défaut) — résout `Σ pᵢᵏ = 1` : retire plus de marge aux issues
  improbables, conformément au biais longshot observé empiriquement.

### ② Pondération statistique

Pour chaque issue, la probabilité finale part du marché dé-viggé puis intègre :

- **Historique** (`hist_wins`/`hist_trials`) : fréquence lissée par un prior
  Beta centré sur le marché (poids `prior_strength` = 10 observations), puis
  fusionnée avec un poids croissant `n / (n + 10)` — peu de données ⇒ on
  reste près du marché, beaucoup ⇒ on converge vers la fréquence observée.
- **Modèle externe** (`model_prob`) : mélange en log-odds avec le poids
  `--model-weight` (défaut 0,5).

### ③ Types de marchés

- `binary` — Oui/Non (2 issues) ;
- `categorical` — multi-options (élections, vainqueurs, N issues).

Les deux types passent par le même pipeline ; le dé-vig opère sur l'ensemble
des issues du marché. Un combiné ne prend jamais deux issues du même marché.

### ④ Moteur combinatoire (le cœur)

Avec n jambes et des combinés de k jambes, l'espace `Σₖ C(n,k)` explose :
C(869, 5) ≈ 4 100 milliards. L'énumération brute est impossible ; le moteur
utilise un **branch-and-bound** exact fondé sur la séparabilité en log des
métriques d'un combiné indépendant :

- `log(prob) = Σ log(pᵢ)` et `log(p·cote) = Σ log(pᵢ·coteᵢ)` sont additifs ;
- jambes triées par poids décroissant ⇒ la meilleure complétion d'un préfixe
  se lit dans une somme cumulée ;
- si même la complétion la plus optimiste ne peut ni battre le K-ième
  meilleur score connu, ni satisfaire `--min-prob` / `--min-payout`, la
  branche entière est éliminée d'un coup.

Garanties :

- objectifs `ev` et `prob` : optimisation **exacte** sur tout l'espace
  (vérifiée par tests contre l'énumération brute) ;
- objectifs `sharpe` et `log_growth` (non séparables) : pool élargi collecté
  via les deux surrogates exacts (~20× sur-échantillonné), puis reclassement
  exact du pool — quasi exact en pratique, vérifié sur petites instances.

### ⑤ Métriques et classement

Par unité misée, avec `p` = probabilité jointe et `O` = cote combinée :

| Métrique | Formule | Usage |
|---|---|---|
| EV | `p·O − 1` | espérance de gain (objectif `ev`, agressif) |
| Variance | `p(1−p)·O²` | risque |
| Sharpe | `EV / σ` | rendement ajusté du risque (`sharpe`, défaut) |
| Kelly | `f* = EV / (O − 1)` | fraction de bankroll optimale |
| Croissance log | `E[log(1 + f·X)]` à ½-Kelly | croissance long terme (`log_growth`) |
| Probabilité | `p` | prudence maximale (`prob`) |

Le **malus de corrélation** `--haircut h` (défaut 0,03) corrige l'hypothèse
d'indépendance : `p' = p·(1−h)^(k−1)`.

Les mises affichées utilisent le **Kelly fractionné** (`--kelly-multiplier`,
défaut 50 % du Kelly plein) plafonné par `--kelly-cap` (défaut 25 % de la
bankroll) — le Kelly plein est notoirement trop volatil en pratique.

---

## Performance mesurée

Machine de développement standard, cœur unique, Python pur :

| Marchés | Jambes | k max | Objectif | Espace couvert | Temps |
|---:|---:|---:|---|---:|---:|
| 100 | 297 | 4 | ev | 322 millions | 0,004 s |
| 300 | 869 | 5 | ev | 4 106 milliards | 0,011 s |
| 300 | 869 | 5 | ev, P ≥ 10 % | 4 106 milliards | 0,083 s |
| 300 | 869 | 5 | sharpe, P ≥ 5 % | 4 106 milliards | 0,568 s |
| 500 | 1 414 | 6 | ev | 11,0 × 10¹⁵ | 0,019 s |
| 500 | 1 414 | 6 | ev, P ≥ 5 % | 11,0 × 10¹⁵ | 0,223 s |

Reproduire : `python3 benchmarks/bench_engine.py` ou `python3 -m predopt bench`.

> L'« espace couvert » est l'espace de recherche complet sur lequel
> l'optimalité est garantie — l'élagage évite de matérialiser chaque
> combinaison, c'est précisément ce qui rend le temps réel possible.

---

## Format de données

```json
{
  "markets": [
    {
      "id": "us-recession-2026",
      "question": "Récession aux USA avant fin 2026 ?",
      "type": "binary",
      "category": "economie",
      "outcomes": [
        {"name": "Oui", "price": 0.32, "model_prob": 0.38,
         "hist_wins": 12, "hist_trials": 40},
        {"name": "Non", "price": 0.70}
      ]
    },
    {
      "id": "election-x-2027",
      "question": "Qui remportera l'élection X ?",
      "type": "categorical",
      "category": "politique",
      "outcomes": [
        {"name": "Candidat A", "price": 0.45},
        {"name": "Candidat B", "price": 0.38},
        {"name": "Candidat C", "price": 0.22}
      ]
    }
  ]
}
```

`model_prob`, `hist_wins`/`hist_trials`, `category`, `liquidity` sont
optionnels. Les prix peuvent sommer au-delà de 1 (marge retirée au dé-vig).
Pour analyser des marchés réels, exportez-les dans ce format (par exemple
depuis l'API publique de la plateforme).

---

## Référence CLI

```
predopt generate --markets N --seed S --vig V --out FICHIER
predopt analyze FICHIER [options]
predopt bench [options]
```

Options principales de `analyze` :

| Option | Défaut | Rôle |
|---|---|---|
| `--min-legs / --max-legs` | 1 / 3 | taille des combinés |
| `--top` | 15 | nombre d'opportunités affichées |
| `--objective` | `sharpe` | `ev` \| `sharpe` \| `log_growth` \| `prob` |
| `--min-prob` | 0 | probabilité de gain minimale |
| `--min-payout` | 1 | cote combinée minimale |
| `--min-leg-ev` | 0 | edge minimal d'une jambe (0 = EV positive) |
| `--max-odds` | 50 | écarte les cotes extrêmes/illiquides |
| `--devig` | `power` | méthode de dé-vig |
| `--model-weight` | 0,5 | poids du modèle vs marché |
| `--haircut` | 0,03 | malus de corrélation par jambe supplémentaire |
| `--bankroll` | — | active le calcul des mises conseillées |
| `--kelly-multiplier` | 0,5 | fraction du Kelly plein |
| `--kelly-cap` | 0,25 | plafond de mise par pari |
| `--json / --csv` | — | exports machine |

> Astuce : `--objective ev` sans `--min-prob` favorise des longshots à EV
> énorme mais probabilité quasi nulle. Pour des paris utilisables, gardez
> `sharpe` (défaut) ou combinez `ev` avec `--min-prob 0.05` et plus.

## API Python

```python
from predopt import (
    load_markets, markets_to_legs, CombinationEngine, generate_sample_markets,
)

markets = load_markets("markets.json")          # ou generate_sample_markets(100)
legs = markets_to_legs(markets, min_leg_ev=0.0) # jambes à edge positif
engine = CombinationEngine(legs, haircut=0.03, kelly_cap=0.25)

combos, stats = engine.search(
    min_legs=1, max_legs=4, top=20,
    objective="sharpe", min_prob=0.05,
)
best = combos[0]
print(best.prob, best.payout, best.ev, best.kelly,
      [leg.label() for leg in best.legs])
print(stats.space_size, stats.nodes_visited, stats.elapsed_s)
```

## Tests

```bash
pip install pytest
python3 -m pytest tests/ -v
```

54 tests couvrent : dé-vig (somme à 1, biais longshot, validation), lissage
bayésien, mélanges log-odds, métriques (valeurs de Kelly connues, maximum de
la croissance log), **équivalence exacte moteur ↔ force brute** (avec et sans
contraintes), exclusivité une-jambe-par-marché, respect des contraintes,
optimalité vérifiée à l'échelle de 42 milliards de combinaisons, exports CLI.

## Architecture

```
src/predopt/
├── models.py       # Market, Outcome, Leg, Combo (validation incluse)
├── probability.py  # dé-vig, lissage Beta, mélange log-odds, malus corrélation
├── metrics.py      # EV, variance, Sharpe, Kelly, croissance log
├── engine.py       # branch-and-bound top-K + référence force brute
├── data.py         # JSON in/out, générateur d'univers synthétiques
├── report.py       # tableaux texte, exports JSON/CSV
└── cli.py          # commandes generate / analyze / bench
tests/              # 54 tests (pytest)
benchmarks/         # balayage de performance
examples/           # jeu de données d'exemple
```

## Limites et avertissements

- **Hypothèse d'indépendance** : les combinés multiplient les probabilités ;
  le malus de corrélation est une correction heuristique, pas un modèle de
  dépendance. Évitez de combiner des marchés fortement liés.
- **Les probabilités sont des estimations** : l'edge affiché n'existe que si
  vos entrées (`model_prob`, historique) contiennent une information réelle
  que le marché n'a pas. Sur un marché efficient, l'EV après frais est ≈ 0.
- **Frais et liquidité non modélisés** : slippage, frais de transaction et
  profondeur de carnet réduisent l'edge réel.
- **Jeu responsable** : une EV positive ne protège pas de la variance.
  Ne misez que ce que vous pouvez perdre ; le Kelly fractionné et le plafond
  de mise sont là pour ça. Vérifiez la légalité de ces plateformes dans
  votre juridiction.
