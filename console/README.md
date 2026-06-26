# Console analyste fraude — Sentinelle

Tableau de bord web **autonome** (un seul fichier `index.html`, aucune
installation) qui se connecte à l'API Sentinelle. Pensé pour les **démos banque**
et l'usage par un analyste fraude.

## Ce qu'elle montre / permet
- **Statut** de connexion + disponibilité du modèle IA.
- **Stats communautaires** en direct : signalements, numéros/domaines bloqués et suivis, seuil.
- **Analyser un message** → verdict complet (score, niveau, catégorie, indices, action).
- **Vérifier une URL** (anti-hameçonnage) → officiel/sosie, score, raisons.
- **Réputation d'un numéro** (caller ID) → bloqué ?, nombre de signalements, affichage masqué.

## Utilisation
1. Démarre l'API : `cd ../sentinelle-backend && python run.py` (ou la version hébergée).
2. Ouvre `index.html` dans un navigateur (double-clic).
3. En haut à droite, mets l'**adresse du serveur** (défaut `http://127.0.0.1:8000`)
   et, si besoin, la **clé d'API**, puis **Connecter**.

L'adresse/clé sont mémorisées (localStorage). La console appelle l'API en
cross-origin (le backend autorise CORS).

> Démo : si tu pointes vers un backend vide, les compteurs sont à zéro. Signale
> quelques numéros/domaines (via l'app ou `curl /api/v1/report`) pour voir l'effet
> communautaire (blocage au seuil).

## Pour la démo banque
Garde cette console ouverte sur un écran : tu colles un faux SMS Interac → verdict
« Fraude probable » instantané, et tu montres les stats communautaires qui grossissent.
C'est le « cerveau » que la banque intégrerait dans son app.
