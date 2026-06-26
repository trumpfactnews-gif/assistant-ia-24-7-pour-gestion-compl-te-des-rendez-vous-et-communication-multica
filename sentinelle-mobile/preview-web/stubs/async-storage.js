// Stub AsyncStorage pour l'aperçu : pré-ensemencé avec des données de démo.
const verdictFraud = {
  risk_score: 85, level: 'fraud',
  level_label: { fr: 'Fraude probable', en: 'Likely fraud' },
  category: 'bank_fraud',
  category_label: { fr: 'Faux conseiller bancaire', en: 'Fake bank advisor' },
  is_fraud: true, language: 'fr', version: '1',
  components: { heuristics: 55, url: 85, ml: 0.83, community: 0 },
  signals: [
    { code: 'bank_keywords', category: 'bank_fraud', label: { fr: 'Vocabulaire bancaire', en: 'Banking vocabulary' }, evidence: 'Desjardins' },
    { code: 'credential_request', category: 'generic', label: { fr: "Demande d'identifiants / code secret", en: 'Request for credentials' }, evidence: 'NIP' },
    { code: 'url_lookalike_brand', category: 'url', label: { fr: 'Marque « desjardins » hors de son domaine officiel', en: "Brand 'desjardins' off official domain" }, evidence: 'desjardins-securite.xyz' },
    { code: 'url_suspicious_tld', category: 'url', label: { fr: 'Extension de domaine à risque (.xyz)', en: 'High-abuse TLD (.xyz)' }, evidence: 'desjardins-securite.xyz' },
  ],
  analyzed_urls: [{ url: 'http://desjardins-securite.xyz/login', host: 'desjardins-securite.xyz', registrable_domain: 'desjardins-securite.xyz', is_official: false, score: 85, reasons: [] }],
  explanation: {
    fr: 'Message classé « Fraude probable » (85/100). Catégorie probable : Faux conseiller bancaire. Indices : Vocabulaire bancaire, Demande d’identifiants, Marque sosie.',
    en: 'Message classified as Likely fraud (85/100).',
  },
  recommended_action: {
    fr: "Il s'agit très probablement d'une fraude. Ne cliquez sur rien, ne répondez pas, supprimez le message et signalez-le. En cas de perte, appelez le Centre antifraude (1-888-495-8501).",
    en: 'This is very likely a fraud. Do not click anything.',
  },
};
const verdictSafe = {
  risk_score: 8, level: 'safe',
  level_label: { fr: 'Sûr', en: 'Safe' }, category: 'none',
  category_label: { fr: 'Aucune', en: 'None' },
  is_fraud: false, language: 'fr', version: '1',
  components: { heuristics: 0, url: 0, ml: 0.08, community: 0 },
  signals: [], analyzed_urls: [],
  explanation: { fr: 'Message classé « Sûr » (8/100).', en: 'Safe (8/100).' },
  recommended_action: { fr: 'Aucune action particulière.', en: 'No action needed.' },
};

const STORE = {
  'sentinelle.consent': 'true',
  'sentinelle.config': JSON.stringify({ apiBaseUrl: 'http://10.0.2.2:8000', autoProtect: true, lang: 'fr' }),
  'sentinelle.history': JSON.stringify([
    { id: 'demo', at: Date.now(), message: 'Desjardins: votre compte est bloqué. Vérifiez votre identité: http://desjardins-securite.xyz/login', sender: '+15145550199', verdict: verdictFraud },
    { id: 'd2', at: Date.now() - 3600000, message: 'Postes Canada: frais de douane 2,99$ à régler: http://postescanada-livraison.click', sender: '+15145550148', verdict: { ...verdictFraud, risk_score: 78, category: 'package_delivery', category_label: { fr: 'Arnaque de colis', en: 'Package scam' } } },
    { id: 'd3', at: Date.now() - 7200000, message: 'Salut! On se voit à 19h au resto ce soir?', sender: 'Maman', verdict: verdictSafe },
  ]),
};

const AsyncStorage = {
  getItem: (k) => Promise.resolve(k in STORE ? STORE[k] : null),
  setItem: (k, v) => { STORE[k] = v; return Promise.resolve(); },
  removeItem: (k) => { delete STORE[k]; return Promise.resolve(); },
};
export default AsyncStorage;
