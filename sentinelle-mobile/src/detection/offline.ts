/**
 * Analyseur de secours « hors ligne » (sur l'appareil, sans serveur).
 *
 * Sous-ensemble compact des heuristiques du backend, pour que l'application
 * reste utile quand l'API n'est pas joignable (mode démo, hors ligne, ou avant
 * d'avoir hébergé le backend). Produit un `Verdict` au même format que l'API.
 *
 * Logique pure (aucune dépendance React Native) : testable et bundlable partout.
 */

import type { Bilingual, RiskLevel, Signal, Verdict, Lang } from '../api/types';

interface Rule {
  code: string;
  category: string;
  weight: number;
  re: RegExp;
  label: Bilingual;
}

const R = (code: string, category: string, weight: number, src: string, fr: string, en: string): Rule => ({
  code,
  category,
  weight,
  re: new RegExp(src, 'i'),
  label: { fr, en },
});

const RULES: Rule[] = [
  R('gift_card', 'generic', 0.8, 'carte[s]? cadeau|gift card|google play (?:card|gift)|itunes',
    'Demande de carte cadeau', 'Gift-card request'),
  R('credential_request', 'generic', 0.7,
    'mot de passe|code de v[ée]rification|votre nip|num[ée]ro de carte|nas\\b|verification code|card number|social insurance|password',
    "Demande d'identifiants / code secret", 'Request for credentials'),
  R('threat', 'generic', 0.6,
    'mandat|arrestation|poursuite|amende|compte (?:bloqu|suspendu|ferm)|account (?:suspended|locked|closed)|warrant|lawsuit',
    'Menace / intimidation', 'Threat / intimidation'),
  R('urgency', 'generic', 0.35,
    'urgent|imm[ée]diat|dans les 24|sous 24|act now|within 24|immediately|derni[èe]re chance|last chance',
    'Pression / urgence', 'Pressure / urgency'),
  R('money', 'generic', 0.4, 'virement|interac|e-?transfer|\\$\\s?\\d|\\d+\\s?\\$|payez|wire money',
    "Demande d'argent / paiement", 'Money / payment request'),
  R('too_good', 'generic', 0.45,
    'f[ée]licitations|vous avez gagn[ée]|gratuit|you won|congratulations|free (?:gift|prize)|claim your prize',
    'Offre trop belle pour être vraie', 'Too-good-to-be-true offer'),
  R('bank_fraud', 'bank_fraud', 0.55,
    'desjardins|banque|caisse|rbc|td\\b|bmo|scotia|cibc|tangerine|transaction suspecte|your account|suspicious transaction',
    'Vocabulaire bancaire', 'Banking vocabulary'),
  R('gov_phishing', 'gov_phishing', 0.6,
    'arc\\b|revenu qu[ée]bec|service[ -]?canada|cra\\b|remboursement d.imp|tax refund|gst|tps',
    "Usurpation d'organisme gouvernemental", 'Government-agency impersonation'),
  R('package_delivery', 'package_delivery', 0.55,
    'postes? canada|canada post|colis|livraison|frais de douane|purolator|fedex|ups\\b|parcel|delivery (?:failed|fee)|customs fee',
    'Arnaque de colis / livraison', 'Package / delivery scam'),
  R('family_emergency', 'family_emergency', 0.6,
    "c.est moi|grand[- ]?(?:maman|papa)|j.ai eu un accident|chang[ée] de num[ée]ro|it.s me|i lost my phone|i had an accident",
    "Fausse urgence d'un proche", 'Fake relative emergency'),
  R('toll_road', 'toll_road', 0.6, '407\\s*etr|p[ée]age|unpaid toll|toll (?:charge|bill)',
    'Arnaque de péage (407 ETR)', 'Toll-road scam (407 ETR)'),
  R('crypto_investment', 'crypto_investment', 0.55,
    'crypto|bitcoin|investiss?ement|rendement garanti|guaranteed return|double your',
    'Investissement / crypto', 'Crypto / investment lure'),
];

const SUSPICIOUS_TLDS = new Set(['xyz', 'top', 'click', 'tk', 'ml', 'ga', 'cf', 'gq', 'link', 'zip', 'mov', 'work']);
const SHORTENERS = new Set(['bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'ow.ly', 'is.gd', 'cutt.ly', 'rb.gy']);
const OFFICIAL = new Set([
  'desjardins.com', 'rbc.com', 'td.com', 'bmo.com', 'scotiabank.com', 'cibc.com', 'tangerine.ca',
  'interac.ca', 'canada.ca', 'revenuquebec.ca', 'canadapost.ca', 'postescanada.ca', 'paypal.com',
  'amazon.ca', 'amazon.com', 'netflix.com', 'ups.com', 'fedex.com', '407etr.com',
]);
const BRANDS = ['desjardins', 'interac', 'rbc', 'scotiabank', 'cibc', 'tangerine', 'bmo', 'revenuquebec',
  'canadapost', 'postescanada', 'paypal', 'netflix', 'amazon', 'fedex', '407etr'];

const URL_RE = /\b((?:https?:\/\/)?(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}(?:\/[^\s]*)?)/gi;

const LEVEL_LABEL: Record<RiskLevel, Bilingual> = {
  safe: { fr: 'Sûr', en: 'Safe' },
  caution: { fr: 'Prudence', en: 'Caution' },
  suspicious: { fr: 'Suspect', en: 'Suspicious' },
  fraud: { fr: 'Fraude probable', en: 'Likely fraud' },
};
const CATEGORY_LABEL: Record<string, Bilingual> = {
  none: { fr: 'Aucune', en: 'None' },
  bank_fraud: { fr: 'Faux conseiller bancaire', en: 'Fake bank advisor' },
  gov_phishing: { fr: 'Hameçonnage gouvernemental', en: 'Government phishing' },
  package_delivery: { fr: 'Arnaque de colis', en: 'Package delivery scam' },
  family_emergency: { fr: 'Urgence familiale', en: 'Family emergency' },
  crypto_investment: { fr: 'Investissement / crypto', en: 'Crypto / investment' },
  toll_road: { fr: 'Péage routier (407 ETR)', en: 'Toll road (407 ETR)' },
  phishing: { fr: 'Hameçonnage', en: 'Phishing' },
  spam: { fr: 'Pourriel', en: 'Spam' },
};
const ACTION: Record<RiskLevel, Bilingual> = {
  safe: { fr: 'Aucune action particulière. Restez vigilant.', en: 'No action needed. Stay vigilant.' },
  caution: {
    fr: "Soyez prudent. Ne cliquez sur aucun lien avant d'avoir vérifié l'expéditeur.",
    en: 'Be cautious. Do not click links before verifying the sender.',
  },
  suspicious: {
    fr: "Ne cliquez sur aucun lien et ne répondez pas. Contactez l'organisation par son numéro officiel.",
    en: 'Do not click links or reply. Contact the organization via its official number.',
  },
  fraud: {
    fr: 'Très probablement une fraude. Ne cliquez sur rien, supprimez et signalez. En cas de perte, appelez le Centre antifraude (1-888-495-8501).',
    en: 'Very likely fraud. Do not click anything, delete and report. If you lost money, call the Canadian Anti-Fraud Centre (1-888-495-8501).',
  },
};

function registrableDomain(host: string): string {
  const labels = host.toLowerCase().replace(/^\.+|\.+$/g, '').split('.');
  if (labels.length <= 2) return labels.join('.');
  const lastTwo = labels.slice(-2).join('.');
  const multi = new Set(['gc.ca', 'qc.ca', 'co.uk', 'com.au']);
  return multi.has(lastTwo) ? labels.slice(-3).join('.') : lastTwo;
}

function levelFromScore(score: number): RiskLevel {
  if (score >= 75) return 'fraud';
  if (score >= 50) return 'suspicious';
  if (score >= 25) return 'caution';
  return 'safe';
}

function noisyOr(weights: number[]): number {
  let pInnocent = 1;
  for (const w of weights) pInnocent *= 1 - Math.min(Math.max(w, 0), 0.99);
  return Math.round((1 - pInnocent) * 100);
}

/** Analyse un message hors ligne et renvoie un Verdict (même format que l'API). */
export function offlineAnalyze(text: string, lang: Lang = 'fr'): Verdict {
  const body = text || '';
  const signals: Signal[] = [];
  const weights: number[] = [];
  const categoryWeights: Record<string, number> = {};

  for (const rule of RULES) {
    const m = rule.re.exec(body);
    if (m) {
      signals.push({ code: rule.code, category: rule.category, label: rule.label, evidence: m[0] });
      weights.push(rule.weight);
      if (rule.category !== 'generic') {
        categoryWeights[rule.category] = (categoryWeights[rule.category] ?? 0) + rule.weight;
      }
    }
  }

  // Analyse des URL (sosies / raccourcisseurs / TLD à risque).
  let urlScore = 0;
  const analyzed: Verdict['analyzed_urls'] = [];
  const matches = body.match(URL_RE) ?? [];
  for (const raw of matches) {
    const host = raw.replace(/^https?:\/\//i, '').split('/')[0]?.split(':')[0] ?? '';
    if (!host || !host.includes('.')) continue;
    const reg = registrableDomain(host);
    const isOfficial = OFFICIAL.has(reg);
    let score = 0;
    const reasons: { code: string; fr: string; en: string }[] = [];
    if (!isOfficial) {
      const tld = reg.split('.').pop() ?? '';
      const tokens = host.toLowerCase().split(/[.\-_]/);
      const brand = BRANDS.find((b) => tokens.includes(b) || (b.length >= 6 && host.toLowerCase().includes(b)));
      if (brand) {
        score += 55;
        reasons.push({ code: 'url_lookalike_brand', fr: `Marque « ${brand} » hors de son domaine officiel`, en: `Brand '${brand}' off its official domain` });
      }
      if (SHORTENERS.has(reg)) {
        score += 45;
        reasons.push({ code: 'url_shortener', fr: 'Lien raccourci masquant la destination', en: 'Link shortener hiding destination' });
      }
      if (SUSPICIOUS_TLDS.has(tld)) {
        score += 30;
        reasons.push({ code: 'url_suspicious_tld', fr: `Extension de domaine à risque (.${tld})`, en: `High-abuse TLD (.${tld})` });
      }
    }
    score = Math.min(score, 100);
    urlScore = Math.max(urlScore, score);
    analyzed.push({ url: raw, host, registrable_domain: reg, is_official: isOfficial, score, reasons });
    for (const r of reasons) {
      signals.push({ code: r.code, category: 'url', label: { fr: r.fr, en: r.en }, evidence: host });
    }
  }

  const heur = noisyOr(weights);
  let risk = Math.max(heur, urlScore);
  const hasCred = signals.some((s) => s.code === 'credential_request');
  const riskyLink = analyzed.some((u) => u.score >= 45);
  if (hasCred && riskyLink) risk = Math.max(risk, 85);

  const level = levelFromScore(risk);
  let category = Object.keys(categoryWeights).sort((a, b) => categoryWeights[b]! - categoryWeights[a]!)[0] ?? 'none';
  if (category === 'none') {
    if (urlScore >= 50) category = 'phishing';
    else if (risk >= 50) category = 'spam';
  }

  const catLabel = CATEGORY_LABEL[category] ?? CATEGORY_LABEL.none!;
  const lvlLabel = LEVEL_LABEL[level];
  const top = signals.slice(0, 4).map((s) => s.label);
  const frIdx = top.length ? top.map((t) => t.fr).join(', ') : 'aucun indice marquant';
  const enIdx = top.length ? top.map((t) => t.en).join(', ') : 'no notable indicator';

  return {
    risk_score: risk,
    level,
    level_label: lvlLabel,
    category,
    category_label: catLabel,
    is_fraud: level === 'suspicious' || level === 'fraud',
    language: lang,
    version: 'offline',
    components: { heuristics: heur, url: urlScore, ml: null, community: 0 },
    signals,
    analyzed_urls: analyzed,
    explanation: {
      fr: `Message classé « ${lvlLabel.fr} » (${risk}/100). Catégorie probable : ${catLabel.fr}. Indices : ${frIdx}. (Analyse hors ligne)`,
      en: `Message classified as '${lvlLabel.en}' (${risk}/100). Likely category: ${catLabel.en}. Indicators: ${enIdx}. (Offline analysis)`,
    },
    recommended_action: ACTION[level],
  };
}
