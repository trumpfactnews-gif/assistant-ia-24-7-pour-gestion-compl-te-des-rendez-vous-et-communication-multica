# Sentinelle — Plan de mise en marché (banques & caisses, Canada/Québec)

> Plan réaliste et pragmatique. Vérité de base : **on ne devient pas un fournisseur
> bancaire certifié en 48 h.** Les banques achètent un fournisseur fraude/sécurité
> en **9 à 24 mois** (revue de risque tiers, SOC 2, pen test). Ce qu'on construit
> vite, c'est un **actif crédible qui ouvre des portes**.

## La décision qui change tout
**Vendre le moteur de détection (API/SDK) que la banque intègre — pas une app SMS grand public.**
Les banques ont déjà leur app et leurs canaux. Elles veulent **le cerveau** (le scoring),
branché dans leur tuyau existant (alertes Interac, app, centre d'appel). Le SMS devient un
**canal de démo**, pas le produit.

## 1. Architecture technique immédiate
**Critique :** héberger l'API en région **canadienne** (résidence des données), HTTPS + clé d'API,
journal d'audit + rate-limit (déjà en place), **1 scénario bancaire** (interception d'arnaque
Interac e-Transfer), **console web** « analyste fraude » (réutilise `preview-web` + `/stats`),
**dossier sécurité 1 page**.
**Optionnel (pas tout de suite) :** SSO/SAML, réentraînement ML lourd, multi-tenant, app iOS signée.

## 2. Stratégie commerciale
**Qui approcher (PAS les achats d'abord) :**
1. Labs d'innovation & accélérateurs (Holt, Creative Destruction Lab, Plug and Play, Volt).
2. **Caisses Desjardins & credit unions** (mission « protéger les membres », cycles plus courts).
3. Équipes **Fraude / Crimes financiers** (elles portent les pertes).
4. Interac & telcos (partenaires de distribution).

**Leviers (mener avec le $ et la conformité) :** pertes évitées · déflection centre d'appel ·
conformité (FCAC/AMF/OSFI B-13) · rétention & marque · différenciation.

**Kit de pitch :** démo live 3 min · one-pager · deck 10 slides · calculateur ROI. _(voir `/pitch`)_

**À amorcer :** résidence des données ✅ · SOC 2 Type I · pen test · un **partenaire référencé**
pour sauter la file du TPRM.

## 3. Viabilité réaliste
**Obstacles → contournement :** revue de risque tiers (3-9 mois) → passer par un lab/sandbox ou un
partenaire référencé ; pas de SOC 2 → vendre un **POC isolé sur données synthétiques** ; pas de
traction → **design partner + LOI** ; build-vs-buy → vendre la **base communautaire** (effet réseau).

**Risques légaux :** Loi 25 / LPRPDE (consentement, résidence, brèche, EFVP) ; **blocage abusif /
diffamation** → processus de contestation + seuil communautaire ; usage nominatif des marques OK,
mais **ne jamais sous-entendre un partenariat** non signé ; positionner en **aide à la décision**.

**Réaliste en 48 h :** démo hébergée, pitch, dossier sécurité, premiers RDV.
**Pas réaliste :** certif, intégration réelle, contrat signé, accès aux vraies données.

## 4. Roadmap post-48 h
| Phase | Durée | Objectif |
|---|---|---|
| 0 — Asset | 48 h | Démo hébergée + kit de pitch |
| 1 — Crédibilité | 0-6 sem | SOC 2 Type I lancé, pen test, 1-2 LOI |
| 2 — POC payant | 1-3 mois | Pilote caisse/credit union, métriques |
| 3 — Prêt marché | 3-9 mois | SOC 2 Type II, TPRM, intégration |

**Première commande, honnêtement :** POC payant via lab/credit union en **3-6 mois** ;
contrat de production Big Five en **12-24 mois**.
