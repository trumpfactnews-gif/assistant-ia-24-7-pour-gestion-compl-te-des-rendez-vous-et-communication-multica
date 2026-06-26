<#
  Équivalent Windows (PowerShell) de scaffold.sh.
  Monte un projet React Native exécutable à partir du code de ce dossier.

  Usage (PowerShell) :
     cd sentinelle-mobile
     ./scaffold.ps1                 # cible par défaut : ..\SentinelleApp
     ./scaffold.ps1 -Target C:\dev\SentinelleApp

  Prérequis : Node >= 18, JDK 17, Android Studio + SDK, un émulateur ou un
  appareil en débogage USB. Voir le README.

  Note : ce script reflète scaffold.sh (validé de bout en bout sous Linux). Les
  commandes (npx / npm / copie) sont identiques ; il n'a pas pu être exécuté
  sous Windows depuis l'environnement de développement.
#>
param([string]$Target = "$PSScriptRoot\..\SentinelleApp")

$ErrorActionPreference = "Stop"
$Here = $PSScriptRoot
$RN = "0.76.5"

Write-Host "> 1/5 Scaffold React Native $RN -> $Target"
npx --yes "@react-native-community/cli@15.0.1" init SentinelleApp `
    --version $RN --directory $Target --skip-git-init

Write-Host "> 2/5 Copie du code de l'application"
Copy-Item "$Here\src", "$Here\__tests__" -Destination $Target -Recurse -Force
Copy-Item "$Here\App.tsx", "$Here\index.js", "$Here\app.json", `
          "$Here\tsconfig.json", "$Here\jest.config.js", "$Here\jest.setup.js" `
          -Destination $Target -Force

Write-Host "> 3/5 Dependances JS"
Push-Location $Target
npm install "@react-native-async-storage/async-storage" react-native-permissions react-native-push-notification
npm install -D "@types/jest" "@types/react-native-push-notification"
Pop-Location

Write-Host "> 4/5 Module natif Android (interception SMS, live + headless)"
$Dest = "$Target\android\app\src\main\java\ca\sentinelle\sms"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item "$Here\android-native\java\ca\sentinelle\sms\*.java" -Destination $Dest -Force

Write-Host "> 5/5 Verifications"
Push-Location $Target
npx tsc --noEmit
npx jest --silent
Pop-Location

Write-Host @"

====================================================================
OK Projet monte. Il reste DEUX editions manuelles (~5 min) :

1) Enregistrer le module natif
   Fichier : android\app\src\main\java\com\sentinelleapp\MainApplication.kt
   - Import en haut :   import ca.sentinelle.sms.SmsListenerPackage
   - Dans getPackages(), a l'interieur de « .apply { » :
        add(SmsListenerPackage())

2) Fusionner le manifeste
   Recopie permissions + <receiver>/<service> de
        sentinelle-mobile\android-native\AndroidManifest.additions.xml
   dans android\app\src\main\AndroidManifest.xml

Puis (emulateur demarre OU appareil branche en USB) :
   cd $Target
   npm start            # Terminal 1 : Metro
   npm run android      # Terminal 2 : build + installation
====================================================================
"@
