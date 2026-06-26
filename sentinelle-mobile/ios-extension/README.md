# Extension de filtrage SMS — iOS

iOS **interdit** l'interception silencieuse des SMS (contrairement à Android).
Le seul mécanisme natif est une **SMS Filter Extension** (framework
`IdentityLookup`). Cette extension :

- ne s'applique qu'aux **expéditeurs inconnus** (numéros absents des contacts) ;
- classe le message en **Junk / Promotion / Transaction** ou le laisse passer ;
- peut **déférer** la décision à un service réseau (le backend Sentinelle) ;
- ne peut **pas** afficher de notification personnalisée ni lire la liste des SMS.

L'utilisateur doit l'activer dans **Réglages → Messages → Inconnus et indésirables
→ Filtrage SMS**.

## Stratégie : hors ligne d'abord

[`MessageFilter/MessageFilterExtension.swift`](MessageFilter/MessageFilterExtension.swift)
applique d'abord un sous-ensemble compact des heuristiques (carte cadeau, demande
d'identifiants, marque usurpée + lien, urgence…) **entièrement sur l'appareil** —
aucune donnée ne sort. Si le résultat est ambigu, l'extension **défère au réseau**,
et le système interroge le backend.

## Contrat backend

Le déféré réseau cible l'URL déclarée dans `Info.plist`
(`ILMessageFilterExtensionNetworkURL`), pointant vers :

```
POST /api/v1/ios-filter   →   { "action": "junk" | "allow" | "promotion" | "transaction" | "none" }
```

Cet endpoint existe déjà dans [`sentinelle-backend`](../../sentinelle-backend) :
il fait tourner le moteur complet et mappe le niveau du verdict
(fraude/suspect → `junk`, sinon → `allow`).

## Intégration dans Xcode

1. **Ajouter une cible** : `File → New → Target… → Message Filter Extension`
   (nom suggéré : `MessageFilter`).
2. **Remplacer** le `MessageFilterExtension.swift` généré par celui de ce dossier
   (ou copier son contenu).
3. **Fusionner** les clés de [`MessageFilter/Info.plist`](MessageFilter/Info.plist)
   dans l'Info.plist de la cible — en particulier `ILMessageFilterExtensionNetworkURL`
   (HTTPS obligatoire). Retirez cette clé pour un fonctionnement 100 % hors ligne.
4. **Signature & capacités** : l'extension a son propre bundle id ; activez
   App Groups si vous souhaitez partager la configuration avec l'app principale.
5. **Compiler & exécuter** sur un appareil réel (le filtrage SMS ne fonctionne pas
   sur simulateur), puis activer le filtre dans les Réglages iOS.

## Mises en garde (à valider)

> Ces fichiers sont un **point de départ fonctionnel**, pas un binaire signé. Je
> n'ai pas pu les compiler ici (ni macOS ni Xcode dans l'environnement).
>
> - Le **format exact** de la requête envoyée par iOS au service réseau est
>   défini par Apple et peut évoluer : l'endpoint `/api/v1/ios-filter` est
>   volontairement **tolérant** (lit `message`/`messageBody`/`text`), à confirmer
>   contre la doc Apple de votre version d'iOS.
> - Vérifiez l'**emplacement** des clés `IL…` dans l'Info.plist selon votre
>   version d'Xcode.
> - Les actions `promotion`/`transaction` requièrent iOS 14+ (gérées par
>   disponibilité dans le code).

## Vie privée

- L'analyse hors ligne ne fait sortir **aucune** donnée de l'appareil.
- Le déféré réseau n'envoie au backend que le message d'un expéditeur **inconnu**,
  uniquement quand l'heuristique locale est indécise. Le backend ne conserve pas
  le contenu (voir [`PRIVACY.md`](../../sentinelle-backend/docs/PRIVACY.md)).
