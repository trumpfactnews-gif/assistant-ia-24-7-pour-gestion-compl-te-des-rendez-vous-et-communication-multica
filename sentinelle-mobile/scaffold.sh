#!/usr/bin/env bash
#
# Monte un projet React Native exécutable à partir du code de ce dossier.
# (Le dépôt contient le code + les modules natifs, pas le projet généré.)
#
# Usage :
#   cd sentinelle-mobile
#   ./scaffold.sh [dossier-cible]        # défaut : ../SentinelleApp
#
# Prérequis : Node ≥ 18, et la chaîne Android (Android Studio + SDK + un
# émulateur ou un appareil en débogage USB). Voir le README.
#
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$HERE/../SentinelleApp}"
RN_VERSION="0.76.5"

echo "▶ 1/5 Scaffold React Native ${RN_VERSION} → ${TARGET}"
npx --yes @react-native-community/cli@15.0.1 init SentinelleApp \
    --version "${RN_VERSION}" --directory "${TARGET}" --skip-git-init

echo "▶ 2/5 Copie du code de l'application"
cp -R "${HERE}/src" "${HERE}/__tests__" "${TARGET}/"
cp "${HERE}/App.tsx" "${HERE}/index.js" "${HERE}/app.json" \
   "${HERE}/tsconfig.json" "${HERE}/jest.config.js" "${HERE}/jest.setup.js" "${TARGET}/"

echo "▶ 3/5 Dépendances JS"
( cd "${TARGET}" \
  && npm install @react-native-async-storage/async-storage react-native-permissions react-native-push-notification \
  && npm install -D @types/jest @types/react-native-push-notification )

echo "▶ 4/5 Module natif Android (interception SMS, live + headless)"
DEST="${TARGET}/android/app/src/main/java/ca/sentinelle/sms"
mkdir -p "${DEST}"
cp "${HERE}"/android-native/java/ca/sentinelle/sms/*.java "${DEST}/"

echo "▶ 5/5 Vérifications"
( cd "${TARGET}" && npx tsc --noEmit && npx jest --silent ) || true

cat <<'NEXT'

════════════════════════════════════════════════════════════════════
✅ Projet monté. Il reste DEUX éditions manuelles (≈ 5 min) :

1) Enregistrer le module natif
   Fichier : android/app/src/main/java/com/sentinelleapp/MainApplication.kt
   • Ajoute l'import en haut :
        import ca.sentinelle.sms.SmsListenerPackage
   • Dans getPackages(), à l'intérieur de « .apply { » :
        add(SmsListenerPackage())

2) Fusionner le manifeste
   Recopie les permissions + le <receiver>/<service> de
        sentinelle-mobile/android-native/AndroidManifest.additions.xml
   dans   android/app/src/main/AndroidManifest.xml

Puis lance l'app (émulateur démarré OU appareil branché en USB) :
   cd <dossier-cible>
   npm start            # Terminal 1 : Metro
   npm run android      # Terminal 2 : build + installation
════════════════════════════════════════════════════════════════════
NEXT
