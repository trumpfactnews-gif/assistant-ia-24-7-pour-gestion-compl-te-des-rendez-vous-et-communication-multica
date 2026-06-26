# Kit de pitch Sentinelle (banques & caisses)

De quoi ouvrir une porte chez une institution financière. À personnaliser avec le
nom du prospect et ses chiffres réels.

| Fichier | Quoi | Comment l'utiliser |
|---|---|---|
| `roi-calculator.html` | **Calculateur de ROI interactif** | Ouvrir dans un navigateur (double-clic). Bouger les curseurs en réunion. |
| `ONE-PAGER.md` | One-pager (1 page) | Exporter en PDF (VS Code « Markdown PDF », ou coller dans un doc). |
| `DECK.md` | Deck 10 slides | Convertir en slides (Marp, Deckset, Slides.com) ou recopier dans PowerPoint/Canva. |
| `../docs/GO-TO-MARKET.md` | Plan de mise en marché | Document de référence interne (stratégie, qui approcher, risques). |

## Ordre conseillé en réunion (30 min)
1. **Problème + coût** (slides 2-3) — mener avec le $, pas la tech.
2. **Démo live 3 min** — coller un faux SMS Interac → verdict. _(app web : `../sentinelle-mobile/preview-web`, `npm start`)_
3. **ROI** — ouvrir `roi-calculator.html`, entrer LEURS chiffres en direct.
4. **Sécurité & conformité** (slide 8) — répondre à la 1ʳᵉ objection avant qu'elle arrive.
5. **La demande** (slide 10) — un POC payant de 60-90 jours. Fixer le prochain RDV.

## Règles d'or
- Tous les montants par défaut sont **illustratifs** : remplace-les par les données du prospect.
- Ne jamais promettre une certification que tu n'as pas (SOC 2 = « en feuille de route »).
- Ne jamais sous-entendre un partenariat (Desjardins, Interac…) non signé.
- Vendre **l'aide à la décision**, jamais une garantie zéro-fraude.
