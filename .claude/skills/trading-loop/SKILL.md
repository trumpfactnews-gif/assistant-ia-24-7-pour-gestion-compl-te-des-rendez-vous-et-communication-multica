---
name: trading-loop
description: >-
  Boucle de trading quantitatif auto-améliorante à 5 étapes (recherche d'alpha →
  vérification du signal → exécution → surveillance du risque → apprentissage).
  À utiliser quand on veut concevoir, lancer ou faire tourner un système de trading
  qui s'exécute en cycle, capitalise chaque trade en règle, et tient un journal de
  leçons vivant. Couvre l'orchestration de la boucle, les garde-fous de risque et
  la transformation perte → leçon → règle. Démarre TOUJOURS en mode paper/simulation.
---

# Trading Loop — Le cycle qui trade pendant que tu dors

> *« L'ingénierie de boucle est l'abstraction au-dessus du prompting. »*
> Ce skill transforme cette idée en une boucle opérationnelle : au lieu de prompter
> un trade à la fois, tu conçois **la boucle** qui fait la recherche, vérifie,
> exécute, surveille — et **apprend de chaque perte**.

## ⚠️ Garde-fous obligatoires (lis avant tout)

Ce skill orchestre une boucle de décision financière. Il ne donne **aucun conseil
en investissement** et n'a aucune garantie de performance. Avant toute exécution :

1. **Paper-trading par défaut.** Toute nouvelle stratégie démarre en simulation
   (`MODE=paper`). Passage en capital réel uniquement sur validation humaine explicite.
2. **Plafonds durs codés en amont.** Taille de position max, perte journalière max
   (kill-switch), exposition brute max — refusés si dépassés, jamais « contournables »
   par la boucle elle-même.
3. **Human-in-the-loop sur les changements de régime.** Tout nouveau type d'ordre,
   tout passage live, toute hausse de levier → validation humaine.
4. **Aucune promesse de gain.** La boucle réduit l'erreur humaine et capitalise les
   leçons ; elle ne « bat le marché » pas par magie.

Si la demande vise à manipuler un marché, contourner une réglementation, ou opérer
sans autorisation → refuser.

## Les 5 étapes du cycle

La boucle tourne en continu. Chaque tour produit des artefacts qui alimentent le
tour suivant.

```
        ┌──────────────────────────────────────────────────────────┐
        │                                                          ▼
  ① RECHERCHE D'ALPHA ──▶ ② VÉRIFICATION ──▶ ③ EXÉCUTION ──▶ ④ RISQUE
        ▲                                                          │
        │                                                          ▼
        └──────────────────── ⑤ APPRENTISSAGE ◀────────────────────┘
                         (perte → leçon → règle)
```

### ① Recherche d'alpha — *générer des hypothèses*
- Formule des hypothèses de signal testables (momentum, mean-reversion, événementiel,
  cross-asset, sentiment…).
- Chaque hypothèse = une **fiche signal** : univers, horizon, logique, données requises,
  critère de succès attendu.
- Sortie : `signals/<id>.md` (candidat non vérifié).
- Agents utiles : `Investment Researcher`, `Trend Researcher`, `AI Engineer`.

### ② Vérification du signal — *réfuter avant de croire*
- Backtest hors-échantillon + walk-forward. Cherche à **invalider** le signal, pas à
  le confirmer (biais de look-ahead, survivorship, overfitting, coûts/slippage réalistes).
- Test adversarial : un second passage qui essaie activement de casser le résultat.
- Gate : un signal ne passe que si Sharpe net de coûts, drawdown et stabilité du
  régime dépassent des seuils **fixés à l'avance**.
- Sortie : signal `verified` ou `rejected` (le rejet est aussi une leçon → étape ⑤).
- Agents utiles : `Model QA Specialist`, `Performance Benchmarker`, `Reality Checker`.

### ③ Exécution — *placer l'ordre proprement*
- Traduit le signal vérifié en ordres (sizing selon le risque, pas selon la conviction).
- Algo d'exécution adapté (TWAP/VWAP/limit), gestion du slippage, idempotence des ordres.
- En `MODE=paper` : journalise l'ordre simulé. En `MODE=live` : passe par le broker
  **seulement** après le gate humain.
- Sortie : `trades/<ts>.json` (ordre, fills, coûts réels).
- Agents utiles : `Backend Architect`, `DevOps Automator`.

### ④ Surveillance du risque — *le système qui te réveille*
- Suit en temps réel : exposition, P&L, drawdown, corrélations, breaches de limites.
- **Kill-switch** : coupe et liquide si perte journalière max atteinte.
- Alertes sur régime changeant (volatilité, liquidité, corrélation qui s'effondre).
- Sortie : `risk/<date>.md` + déclencheurs d'alerte.
- Agents utiles : `SRE (Site Reliability Engineer)`, `Incident Response Commander`.

### ⑤ Apprentissage — *chaque perte écrit une règle*
- C'est l'étape qui rend la boucle **auto-améliorante**. À la clôture de chaque
  trade (gagnant **ou** perdant) :
  1. Post-mortem court : qu'attendait-on, qu'est-il arrivé, pourquoi l'écart.
  2. Extrais **une leçon atomique**.
  3. Convertis la leçon en **règle** réutilisable (filtre, contrainte de sizing,
     condition de marché à éviter…).
  4. Ajoute la règle à `references/LESSONS.md` (le document vivant) — qui re-rentre
     dans l'étape ① et ② au tour suivant.
- Sortie : nouvelle entrée datée dans `LESSONS.md`.
- Agents utiles : `Test Results Analyzer`, `Feedback Synthesizer`, `ZK Steward`.

> Après 100 trades, `LESSONS.md` est un document vivant. Après 1000, il ressemble
> davantage à de la connaissance institutionnelle qu'à ce qu'un humain seul pourrait
> retenir. **C'est ça, le composé** — pas le capital, la connaissance.

## Comment lancer la boucle

1. **Cadre** : définis univers, capital, plafonds de risque dans `references/config.md`.
   Reste en `MODE=paper`.
2. **Un tour manuel d'abord** : exécute ①→⑤ une fois à la main, vérifie que chaque
   étape produit son artefact. Ne jamais automatiser une boucle qu'on n'a pas faite
   tourner à la main au moins une fois.
3. **Orchestre** : enchaîne les étapes (pipeline d'agents, ou cron/loop). Pour la
   cadence, voir `/loop` ; pour un fan-out d'agents par étape, voir le tool Workflow.
4. **Boucle d'apprentissage active** : tant que `LESSONS.md` grossit et que les
   règles réduisent le drawdown, la boucle s'améliore. Sinon → revoir l'étape ②.

## Fichiers du skill
- `references/cycle.md` — détail opérationnel de chaque étape, schémas d'artefacts.
- `references/LESSONS.md` — le journal de leçons vivant (perte → leçon → règle).
- `references/config.md` — gabarit de configuration (univers, risque, mode).

## Principe directeur
Tu n'es pas la personne qui tape un prompt par trade. Tu es l'architecte de la boucle.
Le travail n'est pas « quel trade ? » mais « quelle boucle se corrige elle-même ? ».
