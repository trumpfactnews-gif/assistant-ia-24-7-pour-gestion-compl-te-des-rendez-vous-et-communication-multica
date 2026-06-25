# Vie privée & conformité — Sentinelle

Sentinelle analyse des communications personnelles. La confidentialité n'est pas
une option : c'est une condition d'existence du produit. Ce document décrit les
mesures techniques en place et le cadre réglementaire applicable.

> Ce document est une **note d'ingénierie**, pas un avis juridique. Faites valider
> votre traitement par un·e conseiller·ère en protection des renseignements
> personnels avant tout déploiement réel.

## Données traitées

| Donnée | Traitement | Stockage |
|--------|-----------|----------|
| Contenu d'un SMS analysé (`/analyze`) | Analysé à la volée | **Non stocké** |
| Numéro de l'expéditeur (`sender`) | Normalisé puis **haché** (SHA-256 salé) | Condensé seulement |
| Numéro signalé (`/report`) | Normalisé puis **haché** | Condensé + affichage masqué |
| Domaine signalé | En clair (donnée non personnelle) | Domaine enregistrable |
| Contenu signalé (`message`) | **Haché** (déduplication) | Condensé seulement |
| Identifiant de rapporteur | **Haché** | Condensé seulement |

## Mesures techniques

- **Hachage salé des numéros** (`utils/privacy.py`) : un numéro n'est jamais
  écrit en clair. Le sel provient de `SENTINELLE_SECRET_KEY` — **à définir en
  production** pour résister aux attaques par dictionnaire/rainbow table.
- **Masquage à l'affichage** : `+1514***0199` (jamais le numéro complet).
- **Minimisation** : la base ne conserve que la cible, la catégorie, un compteur
  et des horodatages — le strict nécessaire au blocage communautaire.
- **Pas de journalisation du contenu** des messages analysés.
- **Hachage déterministe** : permet la fonction (rechercher/compter) sans révéler
  la donnée source.

> Limite connue : le hachage d'un numéro est réversible par force brute (l'espace
> des numéros nord-américains est petit). Le sel secret élève la barre, mais pour
> une garantie forte, envisager un HMAC à clé conservée dans un KMS/HSM, voire un
> chiffrement réversible côté serveur. Voir la feuille de route.

## Cadre réglementaire (Canada / Québec)

- **Loi 25 (Québec)** — modernisation de la protection des renseignements
  personnels : consentement clair, responsable de la protection des
  renseignements, évaluation des facteurs relatifs à la vie privée (ÉFVP),
  droit à la portabilité, notification des incidents.
- **LPRPDE / PIPEDA** (fédéral) : consentement valable, finalité limitée,
  mesures de sécurité proportionnées.
- **Interception de SMS (app mobile)** : exige un **consentement explicite et
  éclairé**. Sur Android, le `READ_SMS`/`RECEIVE_SMS` est une permission
  sensible soumise aux politiques du Play Store. Sur iOS, l'interception
  silencieuse est **impossible** — utiliser une extension de filtrage.

## Bonnes pratiques de déploiement

1. Définir `SENTINELLE_SECRET_KEY` (sel) et `SENTINELLE_API_KEY` (accès).
2. Servir l'API en HTTPS uniquement (terminaison TLS en amont).
3. Restreindre CORS à vos origines réelles (défaut `*` à durcir).
4. Conserver les sauvegardes de la base chiffrées au repos.
5. Documenter une durée de conservation et purger les signalements obsolètes.
6. Tenir un registre des traitements et une procédure de réponse aux incidents.

## Droits des personnes

Le produit doit permettre, côté application :
- la suppression d'un appareil/compte et de ses signalements ;
- l'export des données associées à un identifiant ;
- le retrait du consentement à l'analyse à tout moment.
