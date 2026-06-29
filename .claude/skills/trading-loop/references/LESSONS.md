# LESSONS — Journal de leçons vivant

> Le cœur auto-améliorant de la boucle. Chaque trade clôturé (gagnant **ou** perdant)
> et chaque signal rejeté ajoute une entrée. Chaque leçon devient une **règle** que
> les étapes ① Recherche et ② Vérification appliquent au tour suivant.
>
> Règle d'or : **une perte n'est complète que quand elle a écrit sa règle.**

## Format d'une entrée

```
### YYYY-MM-DD — <titre court> (#NNNN)
- **Contexte** : signal / trade concerné, régime de marché.
- **Attendu vs réel** : ce qu'on pensait, ce qui s'est passé, l'écart.
- **Cause racine** : pourquoi l'écart (1 ligne, pas de récit).
- **Leçon** (atomique) : la généralisation réutilisable.
- **Règle** (actionnable) : la contrainte concrète injectée dans ①/②/③.
- **Vérif** : comment on saura que la règle aide (métrique à suivre).
```

## Règles actives (résumé exécutable)

| # | Règle | Étape ciblée | Statut |
|---|-------|--------------|--------|
| — | (vide — la boucle remplit au fur et à mesure) | — | — |

---

## Entrées

<!-- Exemple illustratif (à remplacer par les vraies leçons de la boucle) :

### 2026-06-29 — Momentum mort en haute volatilité (#0001)
- **Contexte** : sig-2026-0001 (momentum 20j), VIX à 34.
- **Attendu vs réel** : Sharpe backtest 1.2 ; en réel le signal a généré un
  drawdown de 6% en 3 jours.
- **Cause racine** : le backtest sous-pondérait les régimes de stress (peu d'échantillons).
- **Leçon** : le momentum se dégrade fortement quand la volatilité dépasse un seuil.
- **Règle** : ② doit rejeter / ① doit filtrer tout signal momentum quand VIX > 30.
- **Vérif** : drawdown max des trades momentum sur les 20 prochains trades.

-->
