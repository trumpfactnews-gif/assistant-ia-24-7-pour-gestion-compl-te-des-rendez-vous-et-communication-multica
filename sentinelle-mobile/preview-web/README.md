# Aperçu visuel (sans appareil) — react-native-web

Rend les **vrais écrans** de l'app (`../src/screens/*`) dans un navigateur
headless via **react-native-web**, puis produit des captures d'écran avec
**Playwright**. Permet une vérification visuelle / non-régression **sans
émulateur Android ni Xcode**.

## Utilisation

```bash
cd sentinelle-mobile/preview-web
npm install

# Chemin vers un binaire Chromium (ex. celui de Playwright) :
export CHROME_BIN=/chemin/vers/chromium
#   ou, si Playwright est installé :  npx playwright install chromium

npm run preview        # build (esbuild) + capture (Playwright)
# -> board.png (les 5 écrans) + screen-1..5.png
```

## Comment ça marche

- `build.mjs` : esbuild bundle `preview.tsx`, en **aliasant** :
  - `react-native` → `stubs/rn-shim.js` (réexporte react-native-web + compléments) ;
  - les modules natifs (`async-storage`, `permissions`, `push-notification`) → stubs ;
  - `@app` → `..` (le code de l'app), `react`/`react-dom` → une **seule** copie.
- `stubs/async-storage.js` pré-ensemence config + historique de démo.
- `preview.tsx` monte chaque écran réel dans un cadre « téléphone ».
- `shot.mjs` charge la page et capture.

## Limites (honnêteté)

- react-native-web **n'est pas pixel-identique** à un rendu natif Android/iOS
  (polices, ombres, certains composants diffèrent). C'est fidèle pour la
  **structure, la mise en page et les styles**, pas pour le rendu pixel près.
- `index.html` ajoute `#root * { min-width: 0 }` : en natif, Yoga met
  `min-width:0` par défaut ; le navigateur non, d'où un débordement des textes
  `numberOfLines={1}` sans ce correctif. C'est un artefact **du web**, pas un
  bug de l'app.
