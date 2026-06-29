# Cycle de trading — détail opérationnel des 5 étapes

Ce document précise, pour chaque étape, l'entrée attendue, le travail, le gate de
passage et le schéma de l'artefact produit. Tout artefact est versionné (git) :
la traçabilité fait partie de la boucle.

---

## ① Recherche d'alpha

**Entrée** : univers + leçons existantes (`LESSONS.md`).
**Travail** : générer N hypothèses de signal distinctes, idéalement par angles
différents (prix, flux, sentiment, événementiel, cross-asset).
**Gate** : une hypothèse n'avance que si elle est *falsifiable* et a un critère de
succès chiffré défini AVANT le backtest.

Schéma `signals/<id>.md` :
```yaml
id: sig-2026-0001
status: candidate          # candidate | verified | rejected
univers: [AAPL, MSFT, ...]
horizon: 5d
logique: "momentum 20j filtré par régime de volatilité"
donnees: [ohlcv_daily, vix]
critere_succes: "Sharpe net > 1.0, maxDD < 8% en walk-forward"
hypotheses_risque: ["se dégrade en régime de faible liquidité"]
```

---

## ② Vérification du signal

**Entrée** : `signals/<id>.md` en `candidate`.
**Travail** :
- Backtest **hors-échantillon** + **walk-forward** (jamais d'optimisation sur le test).
- Coûts réalistes : commissions, spread, slippage, impact.
- Contrôles de biais : look-ahead, survivorship, data-snooping, p-hacking.
- **Passe adversariale** : un second évaluateur dont le but est de RÉFUTER le signal
  (perturbe les périodes, randomise les labels, teste la robustesse aux paramètres).
**Gate** : passe seulement si TOUS les seuils pré-fixés sont tenus ET que la passe
adversariale ne le casse pas. Sinon → `rejected` (et écris la leçon, étape ⑤).

Artefact : mise à jour du `status` + bloc `verification:` avec métriques nettes,
courbe d'équité, et verdict adversarial.

---

## ③ Exécution

**Entrée** : signal `verified`.
**Travail** :
- **Sizing par le risque** (ex. risque fixe par trade / volatilité ciblée), jamais
  « plus de conviction = plus gros ».
- Choix d'algo : limit / TWAP / VWAP selon liquidité et urgence.
- Ordres **idempotents** (un id client par intention) pour éviter les doublons.
- `MODE=paper` → simulateur de fills. `MODE=live` → broker, après gate humain.
**Gate** : refuser l'ordre si un plafond de `config.md` est dépassé (taille, exposition).

Schéma `trades/<ts>.json` :
```json
{
  "ts": "2026-06-29T14:03:00Z",
  "signal_id": "sig-2026-0001",
  "side": "buy", "qty": 100, "symbol": "AAPL",
  "mode": "paper",
  "intended_price": 201.40,
  "fills": [{"price": 201.43, "qty": 100}],
  "costs": {"commission": 0.5, "slippage_bps": 1.5}
}
```

---

## ④ Surveillance du risque

**Entrée** : positions ouvertes + flux de marché.
**Travail** : calcul continu exposition / P&L / drawdown / corrélations ; détection
de breach ; **kill-switch** sur perte journalière max.
**Gate** : si breach → liquidation/cap automatique + alerte humaine ; la boucle ne
peut pas relever ses propres limites.

Schéma `risk/<date>.md` : tableau des limites (valeur / seuil / état), liste des
breaches, et actions déclenchées.

---

## ⑤ Apprentissage

**Entrée** : trade clôturé (ou signal rejeté).
**Travail** : post-mortem → leçon atomique → règle réutilisable → append `LESSONS.md`.
**Gate** : aucun trade n'est « terminé » tant que sa leçon n'est pas écrite.

La règle produite doit être **actionnable** par ① ou ② au prochain tour
(ex. « exclure les signaux momentum quand VIX > 30 » devient un filtre concret).
