# Config de la boucle — gabarit

> À remplir avant tout tour. Les plafonds de risque sont des **limites dures** :
> la boucle ne peut jamais les relever elle-même. Tout passage `live` ou toute
> hausse de plafond exige une validation humaine explicite.

```yaml
mode: paper                 # paper | live   (toujours démarrer en paper)

univers:
  classes: [actions_us]     # actions_us | etf | fx | crypto | ...
  liste: []                 # tickers ou règle de sélection

capital:
  base_currency: USD
  alloue: 0                 # capital simulé en paper ; réel uniquement après gate humain

risque:
  perte_journaliere_max_pct: 2.0     # déclenche le kill-switch
  position_max_pct: 5.0              # par position, % du capital
  exposition_brute_max_pct: 100.0    # somme des |positions|
  levier_max: 1.0                    # >1 interdit sans validation humaine
  risque_par_trade_pct: 0.5          # base du sizing par le risque

verification:
  seuil_sharpe_net: 1.0
  drawdown_max_pct: 8.0
  oos_min_mois: 12                   # historique hors-échantillon minimum
  passe_adversariale: true

execution:
  algo_defaut: limit                 # limit | twap | vwap
  slippage_modele_bps: 2.0
  idempotence: true

gates_humains:
  - passage_live
  - hausse_d_un_plafond_de_risque
  - nouveau_type_d_ordre
  - hausse_de_levier
```

## Checklist avant de lancer
- [ ] `mode: paper`
- [ ] Plafonds de risque renseignés et raisonnables
- [ ] Un tour ①→⑤ exécuté à la main et vérifié
- [ ] `LESSONS.md` accessible en lecture par ① et ②
- [ ] Kill-switch testé (simuler une perte > seuil et vérifier la coupure)
