# Référence API — Sentinelle v1

Base URL (dév) : `http://127.0.0.1:8000`

- Toutes les réponses sont en JSON (UTF-8).
- Si `SENTINELLE_API_KEY` est défini, les routes `/api/*` exigent l'en-tête
  `X-API-Key`. `/health` et `/` restent publics.
- Limitation de débit : `SENTINELLE_RATE_LIMIT` requêtes/minute par IP (429 sinon).
- CORS activé (`Access-Control-Allow-Origin: *`) pour les clients mobiles/web.

### Format d'erreur

```json
{ "error": { "code": "missing_field", "message": "Le champ « message » est requis." } }
```

Codes : `invalid_body`, `missing_field`, `invalid_field`, `field_too_long`,
`unauthorized` (401), `rate_limited` (429), `not_found` (404), `internal_error` (500).

---

## `POST /api/v1/analyze`

Analyse un message texte et renvoie un verdict de fraude.

**Corps**

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `message` | string | ✅ | Le texte du SMS à analyser |
| `sender` | string | ⬜ | Numéro/identifiant de l'expéditeur (active la vérification communautaire) |
| `lang` | `"fr"`\|`"en"` | ⬜ | Forcer la langue de détection (sinon auto) |

**Exemple**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{"message":"Desjardins: compte bloqué, vérifiez: http://desjardins-securite.xyz","sender":"+15145550199"}'
```

**Réponse `200`** (extrait)

```json
{
  "risk_score": 85,
  "level": "fraud",
  "level_label": { "fr": "Fraude probable", "en": "Likely fraud" },
  "category": "bank_fraud",
  "category_label": { "fr": "Faux conseiller bancaire", "en": "Fake bank advisor" },
  "is_fraud": true,
  "language": "fr",
  "components": { "heuristics": 55, "url": 85, "ml": 0.83, "community": 0 },
  "signals": [
    { "code": "bank_keywords", "category": "bank_fraud",
      "label": { "fr": "Vocabulaire bancaire", "en": "Banking vocabulary" },
      "evidence": "Desjardins" },
    { "code": "url_lookalike_brand", "category": "url",
      "label": { "fr": "Marque « desjardins » utilisée hors de son domaine officiel",
                 "en": "Brand 'desjardins' used outside its official domain" },
      "evidence": "desjardins-securite.xyz" }
  ],
  "analyzed_urls": [
    { "url": "http://desjardins-securite.xyz", "host": "desjardins-securite.xyz",
      "registrable_domain": "desjardins-securite.xyz", "is_official": false,
      "score": 85, "reasons": [ /* … */ ] }
  ],
  "explanation": {
    "fr": "Message classé « Fraude probable » (85/100). Catégorie probable : Faux conseiller bancaire. Indices : …",
    "en": "Message classified as 'Likely fraud' (85/100). Likely category: Fake bank advisor. Indicators: …"
  },
  "recommended_action": {
    "fr": "Il s'agit très probablement d'une fraude. Ne cliquez sur rien…",
    "en": "This is very likely a fraud. Do not click anything…"
  }
}
```

**Niveaux** : `safe` (0–24) · `caution` (25–49) · `suspicious` (50–74) · `fraud` (75–100).
`is_fraud` vaut `true` dès le niveau `suspicious`.

---

## `POST /api/v1/report`

Signale un numéro ou un domaine frauduleux. Au seuil de rapporteurs **distincts**
(`SENTINELLE_BLOCK_THRESHOLD`, défaut 3), la cible est bloquée pour toute la communauté.

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `type` | `"number"`\|`"domain"` | ✅ | Type de cible |
| `value` | string | ✅ | Numéro (tout format) ou URL/domaine |
| `category` | string | ⬜ | Catégorie d'arnaque |
| `reporter_id` | string | ⬜ | Identifiant du rapporteur (haché ; compte les signalements distincts) |
| `message` | string | ⬜ | Contenu signalé (haché pour déduplication) |

```bash
curl -X POST http://127.0.0.1:8000/api/v1/report \
  -H 'Content-Type: application/json' \
  -d '{"type":"number","value":"+15145550199","category":"bank_fraud","reporter_id":"device-abc"}'
```

**Réponse `201`**

```json
{ "target_type": "number", "target_display": "+1514***0199",
  "category": "bank_fraud", "report_count": 1, "blocked": false, "block_threshold": 3 }
```

---

## `GET /api/v1/check-number?number=…`

Réputation communautaire d'un numéro (caller ID). Le numéro est normalisé puis haché.

```bash
curl "http://127.0.0.1:8000/api/v1/check-number?number=514-555-0199"
```

```json
{ "blocked": true, "report_count": 3, "category": "bank_fraud", "display": "+1514***0199" }
```

---

## `POST /api/v1/check-url`

Analyse anti-hameçonnage d'une URL (sans contexte de message).

```bash
curl -X POST http://127.0.0.1:8000/api/v1/check-url \
  -H 'Content-Type: application/json' \
  -d '{"url":"http://desjardins.secure-login.xyz/verifier"}'
```

```json
{
  "url": "http://desjardins.secure-login.xyz/verifier",
  "host": "desjardins.secure-login.xyz",
  "registrable_domain": "secure-login.xyz",
  "is_official": false,
  "score": 100,
  "community_blocked": false,
  "reasons": [
    { "code": "url_lookalike_brand", "fr": "…", "en": "…" },
    { "code": "url_lure_tokens", "fr": "…", "en": "…" }
  ]
}
```

Codes de raison : `url_userinfo`, `url_ip_literal`, `url_punycode`,
`url_shortener`, `url_suspicious_tld`, `url_lookalike_brand`, `url_typosquat`,
`url_lure_tokens`, `url_many_subdomains`.

---

## `GET /api/v1/stats`

```json
{ "total_reports": 42, "blocked_numbers": 7, "tracked_numbers": 15,
  "blocked_domains": 3, "tracked_domains": 9, "block_threshold": 3 }
```

---

## `GET /health`

```json
{ "status": "ok", "service": "sentinelle", "ml_available": true }
```
