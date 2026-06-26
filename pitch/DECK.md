# Sentinelle — Deck investisseur/banque (10 slides)

> Format : 1 section = 1 diapo. Convertir en slides avec Marp, Deckset, Slides.com
> ou copier dans PowerPoint/Canva. Garder une idée par diapo, gros titres, peu de texte.
> Les chiffres marqués _(illustratif)_ sont à remplacer par les données réelles du prospect.

---

## Slide 1 — Titre
# 🛡️ Sentinelle
### Repérer l'arnaque *avant* qu'elle réussisse.
Moteur de détection de fraude par message — **API prête à intégrer** pour les banques et caisses du Canada.
_[Logo · présentateur · date]_

---

## Slide 2 — Le problème
**La fraude par message texte est devenue industrielle.**
- Smishing, faux conseiller, faux Interac, faux Postes Canada, « grand-maman »…
- L'arnaque au **virement autorisé** (APP scam) et la fraude **Interac** sont en forte croissance au Canada.
- Le filtre anti-pourriel ne lit pas le *langage* de la fraude. Le client est seul face au message.

> « 3 Canadiens sur 4 ont été exposés à une tentative de fraude. » _(ordre de grandeur public, illustratif)_

---

## Slide 3 — Ça coûte cher (à la banque)
- La banque **assume** souvent la perte, ou y est poussée par la pression réglementaire.
- Chaque fraude génère **appels, enquêtes, attrition**.
- Pertes annuelles assumées : **9 M$** pour 500 000 clients _(illustratif — voir calculateur)_.

---

## Slide 4 — La solution
**Sentinelle = le cerveau anti-fraude, livré en API.**
- Vous l'intégrez dans **votre** app, vos alertes, votre centre d'appel.
- Verdict en **< 200 ms**, **explicable** et **bilingue (FR/EN)**.
- Pas une 2ᵉ app à promouvoir : **le moteur**, dans votre tuyau.

---

## Slide 5 — Comment ça marche
**Quatre signaux fusionnés en un verdict 0-100 :**
1. 🧠 Heuristiques expertes (arnaques canadiennes/québécoises)
2. 🤖 Classifieur ML bilingue (TF-IDF)
3. 🔗 Anti-hameçonnage d'URL (sosies, typosquatting, raccourcisseurs)
4. 👥 Base communautaire (effet réseau, blocage au seuil)

→ Score · catégorie · indices · **action recommandée**.

---

## Slide 6 — Démo
**Faux SMS Desjardins → Verdict « Fraude probable 87/100 ».**
- Catégorie : faux conseiller bancaire · Indices : NIP demandé, domaine sosie `.xyz`
- Explication claire + « Que faire ? » + numéro du Centre antifraude
_[Insérer capture `demo-verdict` / démo live]_

---

## Slide 7 — Le ROI
**+20× la première année** _(hypothèses illustratives)_ :
- 5,4 M$ de pertes évitées + 65 k$ d'économies centre d'appel
- Rentabilité en **< 1 mois**
- Estimation **conservatrice** (exclut rétention/marque)
➡️ Calculateur interactif fourni (`roi-calculator.html`).

---

## Slide 8 — Sécurité & conformité
- 🇨🇦 **Résidence des données au Canada** (ca-central-1)
- 🔒 Numéros **jamais en clair** (condensé salé) · pas de conservation du contenu
- 🔑 Clé d'API · chiffrement · journal d'audit
- 📜 **Loi 25 / LPRPDE** · **SOC 2 en feuille de route** · pen test planifié

---

## Slide 9 — État & feuille de route
- ✅ **Aujourd'hui** : produit fonctionnel, API REST, 47 tests, app mobile + extension iOS, démo hébergeable.
- 🔜 **0-3 mois** : SOC 2 Type I, pen test, POC payant avec un partenaire pilote.
- 🎯 **3-9 mois** : SOC 2 Type II, intégration, déploiement élargi.

---

## Slide 10 — La demande
**Un POC payant de 60-90 jours.**
- Données synthétiques, aucun accès au cœur bancaire requis.
- Objectif : mesurer ensemble les **pertes évitées**.
- Cherche : **1 caisse / credit union partenaire pilote**.

**Prochain pas : 30 min de démo live.**
_[nom · courriel · téléphone]_
