# fluxel-signals

Moteur de signaux **ACHAT / VENTE / NEUTRE** pour la page `/marches` de fluxel.
Implémente la boucle [`trading-loop`](../../.claude/skills/trading-loop/) à 5 étapes
(alpha → vérification → exécution → risque → apprentissage), avec un adaptateur
**modèle de prédiction Google (Vertex AI Forecasting)** et un fallback local.

- **Zéro dépendance npm** (Node ≥ 18, `fetch` natif). Se déploie tel quel sur ton VPS.
- **Mode `paper` par défaut** : aucun ordre réel n'est envoyé. Garde-fous de risque
  durs (kill-switch perte journalière, plafond de position, sizing par le risque).
- Expose une API JSON + un widget JS à coller dans la page.

## Lancer en local
```bash
cd apps/fluxel-signals
node server.js          # http://localhost:8787
curl "http://localhost:8787/api/signals?symbols=BTC,AAPL,NVDA"
```

## Déployer sur le VPS (où vit fluxel)
```bash
# 1. copier le dossier sur le VPS
scp -r apps/fluxel-signals user@TON_VPS:/opt/fluxel-signals

# 2. service systemd (tourne 24/7, redémarre seul)
sudo tee /etc/systemd/system/fluxel-signals.service <<'EOF'
[Unit]
Description=fluxel-signals
After=network.target
[Service]
WorkingDirectory=/opt/fluxel-signals
ExecStart=/usr/bin/node server.js
Environment=PORT=8787
Restart=always
User=www-data
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now fluxel-signals

# 3. exposer derrière ton reverse-proxy (Nginx) en HTTPS, ex. /signals/
#    location /signals/ { proxy_pass http://127.0.0.1:8787/; }
```

## Embarquer le widget dans la page /marches
Colle ce snippet dans le HTML de la page (ou le composant correspondant) :
```html
<div id="fluxel-signals"
     data-api="https://fluxel.tfnmedia.tech/signals"
     data-symbols="BTC,ETH,AAPL,NVDA,TSLA"
     data-refresh="30000"></div>
<script src="https://fluxel.tfnmedia.tech/signals/widget.js"></script>
```
Si la page est en React/Next.js, on peut aussi consommer directement `/api/signals`
et rendre tes propres composants — dis-moi le framework.

## Brancher tes vraies données de marché
`datasource.js` → mets `cfg.datasource.source = "http"` et complète `fetchHttp()`
avec ton fournisseur (Binance, Alpha Vantage, Yahoo, ou ton API fluxel existante).
Par défaut, une source synthétique déterministe (`demo`) permet de tout tester sans clé.

## Brancher le vrai modèle Google (Vertex AI Forecasting)
1. Entraîne/déploie un modèle de prévision de séries temporelles sur Vertex AI.
2. Dans `config.json` :
   ```json
   "predictor": { "backend": "vertex",
     "vertex": { "endpointUrl": "https://...-aiplatform.googleapis.com/v1/.../endpoints/ID:predict",
                 "accessToken": "<token OAuth GCP>" } }
   ```
3. Adapte le parsing de la réponse dans `google-predictor.js → predictVertex()`
   au schéma de sortie de ton modèle. En cas d'erreur réseau, fallback local automatique.

> Alternative : pour de l'analyse de sentiment/actualités plutôt que de la prévision
> de prix, on peut brancher **Gemini** en étape ① — dis-moi si tu préfères cet axe.

## Passer en exécution réelle (live) — NON activé
Le mode `live` exige : un broker avec API (ordres idempotents), un test du
kill-switch, et **ta validation humaine explicite**. Tant que `execution.mode` reste
`paper`, rien n'est envoyé à un marché. Ne pas activer `live` sans relire les plafonds
de `config.json` et tester la coupure de risque.

## Réglages clés (`config.json`)
| Champ | Rôle |
|------|------|
| `execution.mode` | `paper` (simulation) / `live` (réel — gardé) |
| `verification.minConfidence` / `minScore` / `maxVolatility` | gates de l'étape ② |
| `risk.maxDailyLossPct` | kill-switch perte journalière |
| `risk.maxPositionPct` / `riskPerTradePct` | sizing par le risque |
| `predictor.backend` | `local` / `vertex` |
| `watchlist` | actifs suivis |

## Limites (honnêteté)
Aucun modèle ne « sait » où va le marché. Ces signaux sont algorithmiques et
probabilistes ; ils ne constituent pas un conseil en investissement. Le mode paper
sert à valider la boucle **avant** d'envisager le moindre euro réel.
