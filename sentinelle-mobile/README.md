# 🛡️ Sentinelle Mobile — bouclier anti-fraude SMS (React Native)

Application mobile qui intercepte les SMS entrants (Android), les envoie au
[backend Sentinelle](../sentinelle-backend) pour analyse, et **alerte
l'utilisateur avant que la fraude ne réussisse** — avec une interface
« bouclier de sécurité » bilingue (FR/EN).

---

## Ce que contient ce dossier

C'est **le code applicatif** (TypeScript) + **le module natif Android**
d'interception des SMS. Pour garder le dépôt léger et lisible, il n'inclut **pas**
le projet généré (`android/`, `ios/`, `node_modules/`) : on les crée au moment de
l'intégration (voir ci-dessous).

| Élément | État |
|---------|------|
| Logique applicative (TS) : API, état, écrans, navigation | ✅ Complet |
| Client API typé, miroir fidèle du backend | ✅ Complet, **testé contre le vrai backend** |
| Module natif Android d'interception SMS (Java) | ✅ Complet |
| Tests unitaires (client, verdict, téléphone) | ✅ Jest |
| Projet natif `android/` / `ios/` généré | ⛔ À scaffolder (voir étapes) |

```
sentinelle-mobile/
├── App.tsx                     # racine : onboarding → écoute SMS → routing
├── index.js
├── src/
│   ├── api/{types,client}.ts   # contrat + client HTTP (pur, testable hors RN)
│   ├── config.ts  theme.ts
│   ├── state/AppContext.tsx    # config, client, historique, actions
│   ├── navigation/index.tsx    # pile minimaliste
│   ├── services/               # notifications, pont SMS natif
│   ├── utils/                  # verdict, téléphone, stockage
│   ├── components/             # ShieldStatus, VerdictCard, SignalList, ui
│   └── screens/                # Onboarding, Home, Analyze, Detail, Settings
├── android-native/             # module natif à copier dans le projet Android
└── __tests__/                  # tests Jest
```

---

## Mettre en route (Android)

> Prérequis : Node ≥ 18, JDK 17, Android Studio + SDK, un émulateur ou appareil.

### 1. Générer le projet natif puis y greffer le code

```bash
# Crée un projet RN 0.76 nommé Sentinelle dans un dossier temporaire
npx @react-native-community/cli@latest init Sentinelle --version 0.76.5

# Copie le code de ce dossier par-dessus le scaffold
cp -r sentinelle-mobile/src sentinelle-mobile/App.tsx sentinelle-mobile/index.js \
      sentinelle-mobile/app.json sentinelle-mobile/tsconfig.json \
      sentinelle-mobile/__tests__  Sentinelle/

cd Sentinelle
npm install @react-native-async-storage/async-storage react-native-permissions react-native-push-notification
```

### 2. Greffer le module natif SMS

```bash
mkdir -p android/app/src/main/java/ca/sentinelle/sms
cp ../sentinelle-mobile/android-native/java/ca/sentinelle/sms/*.java \
   android/app/src/main/java/ca/sentinelle/sms/
```

- **Enregistrer le package** dans `MainApplication.kt` (ou `.java`), dans la liste
  des packages :
  ```kotlin
  add(SmsListenerPackage())   // import ca.sentinelle.sms.SmsListenerPackage
  ```
- **Fusionner les permissions** depuis
  [`android-native/AndroidManifest.additions.xml`](android-native/AndroidManifest.additions.xml)
  dans `android/app/src/main/AndroidManifest.xml`.

### 3. Lancer

```bash
npm start            # Metro
npm run android      # build + déploie sur l'émulateur/appareil
```

L'émulateur Android atteint le backend local via `http://10.0.2.2:8000`
(valeur par défaut, modifiable dans **Paramètres**).

---

## Connexion au backend

Le client (`src/api/client.ts`) appelle les routes du backend :
`/analyze`, `/report`, `/check-url`, `/check-number`, `/stats`, `/health`.

Démarrer le backend en parallèle :

```bash
cd ../sentinelle-backend && source .venv/bin/activate && python run.py
```

Si le backend exige une clé (`SENTINELLE_API_KEY`), renseignez-la dans
**Paramètres → Clé d'API** (envoyée via l'en-tête `X-API-Key`).

---

## iOS

iOS **interdit** l'interception silencieuse des SMS. Sur iOS :
- l'analyse **automatique** n'est pas disponible ;
- le flux **manuel** (coller un message dans l'app) fonctionne ;
- pour un filtrage natif, implémenter une **SMS Filter Extension**
  (`ILMessageFilterExtension`) — non incluse ici.

L'app détecte l'absence du module natif et bascule automatiquement en mode manuel.

---

## Tests & qualité

```bash
npm test            # tests Jest (client, verdict, téléphone)
npm run typecheck   # tsc --noEmit (nécessite npm install)
```

> La logique **pure** (API + utils) est vérifiable sans tout l'écosystème RN via
> `npx tsc -p tsconfig.pure.json`. Le client a été testé en intégration contre le
> vrai backend (analyze / report → blocage / check-url / gestion d'erreurs).

---

## Vie privée

- Consentement explicite requis avant toute analyse (écran d'onboarding).
- Les numéros ne sont jamais affichés/stockés en clair (masquage `+1514***0199`).
- L'historique reste **local** à l'appareil (AsyncStorage) ; effaçable dans Paramètres.
- Permissions SMS = catégorie sensible Play Store : justifier l'usage anti-fraude
  lors de la soumission. Voir [`../sentinelle-backend/docs/PRIVACY.md`](../sentinelle-backend/docs/PRIVACY.md).

---

## Feuille de route

- [ ] Interception en état « tué » : tâche Headless JS + receiver manifeste.
- [ ] Extension de filtrage SMS iOS.
- [ ] File d'attente hors-ligne (analyse différée quand le réseau revient).
- [ ] Caller ID en temps réel via `/check-number`.
- [ ] Écran communautaire (stats `/stats`, tendances régionales).
