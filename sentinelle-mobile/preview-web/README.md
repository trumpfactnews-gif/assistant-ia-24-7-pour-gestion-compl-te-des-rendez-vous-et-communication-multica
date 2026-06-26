# Sentinelle dans le navigateur — démo & captures (react-native-web)

Fait tourner les **vrais écrans** de l'app (`../src/*`) dans un navigateur via
**react-native-web** — **sans émulateur Android ni Xcode**.

## 🚀 Démo interactive (le plus simple pour essayer)

Aucune configuration Android. Il te faut seulement **Node** (déjà installé).

```bash
cd sentinelle-mobile/preview-web
npm install
npm start
```
Le terminal affiche une adresse (ex. `http://localhost:5173/index-app.html`) :
ouvre-la dans ton navigateur. L'app est **fonctionnelle** — sans serveur,
l'analyse bascule automatiquement en **mode hors ligne** (embarqué).

> C'est une démo **navigateur** : tu peux tester l'interface et l'analyse
> manuelle de messages. L'interception **automatique** des SMS n'existe que sur
> l'app Android native (le navigateur n'a pas accès aux SMS).

## 📸 Captures d'écran (vérification visuelle)

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
