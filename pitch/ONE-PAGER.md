# 🛡️ Sentinelle — Détection de fraude par message, prête à intégrer

**Le moteur qui repère l'arnaque *avant* que votre client clique ou vire l'argent — livré en API, intégrable dans votre app et vos alertes.**

---

### Le problème (Canada / Québec)
La fraude par message texte (smishing, faux conseiller bancaire, faux Interac, arnaque au colis, « bonjour grand-maman ») explose. L'arnaque au **virement autorisé** (APP scam) et les fraudes **Interac e-Transfer** coûtent cher — et la pression réglementaire (FCAC, AMF, OSFI) pour **protéger activement** le client monte. Les filtres anti-pourriel ne lisent pas le *langage* de la fraude.

### La solution
Sentinelle analyse un message et renvoie en **< 200 ms** un **verdict explicable et bilingue (FR/EN)** : score 0-100, catégorie d'arnaque, indices détectés, action recommandée. À brancher dans **votre** canal existant — app mobile, alertes SMS, centre d'appel.

**Quatre sources de signal fusionnées :**
- 🧠 Heuristiques expertes (arnaques canadiennes : banque, ARC/Revenu Québec, Postes Canada, 407 ETR, crypto…)
- 🤖 Classifieur d'apprentissage automatique (TF-IDF, bilingue)
- 🔗 Anti-hameçonnage d'URL (domaines sosies, typosquatting, raccourcisseurs)
- 👥 Base communautaire (numéros/domaines signalés, effet réseau)

### Pourquoi les banques l'adoptent
| Levier | Impact |
|---|---|
| 💸 **Pertes évitées** | Moins de fraudes réussies = moins de pertes assumées |
| ☎️ **Déflection centre d'appel** | Chaque fraude bloquée = appels en moins |
| 🏛️ **Conformité** | Preuve de protection active (FCAC / AMF / OSFI B-13) |
| ❤️ **Rétention & marque** | Un client fraudé part ; protéger fidélise |

➡️ **ROI illustratif : +20× la première année** (voir `roi-calculator.html`).

### Sécurité & conformité
Résidence des données au Canada · numéros **jamais stockés en clair** (condensé salé) · pas de conservation du contenu · clé d'API + chiffrement + journal d'audit · **Loi 25 / LPRPDE** · *SOC 2 en feuille de route*.

### Statut
Produit **fonctionnel et testé** (backend Python/Flask, 47 tests, API REST, app mobile + extension iOS). Pré-certification — **nous cherchons un partenaire pilote** (caisse / credit union).

### La demande
Un **POC payant de 60-90 jours** sur données synthétiques, avec métriques de pertes évitées. Aucune intégration à votre cœur bancaire requise pour démarrer.

**Contact :** _[nom / courriel / téléphone]_ · Démo live sur demande.

> Sentinelle est un outil d'aide à la vigilance, non un substitut au Centre antifraude du Canada (1-888-495-8501). Aucune détection n'est parfaite.
