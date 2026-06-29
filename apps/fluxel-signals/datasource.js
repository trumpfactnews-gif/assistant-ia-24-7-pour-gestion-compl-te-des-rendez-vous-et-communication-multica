'use strict';
/**
 * Source de données de prix.
 *
 * - 'demo'  : génère un historique synthétique déterministe par symbole, pour
 *             que le service tourne SANS clé API ni réseau (tests, démo VPS).
 * - 'http'  : à brancher sur ton fournisseur réel (Binance, Alpha Vantage,
 *             Yahoo, ta propre API fluxel...). Voir fetchHttp ci-dessous.
 *
 * Remplace `getPrices` par ta vraie source quand tu passes en production.
 */

// Générateur pseudo-aléatoire déterministe (mulberry32) — pas de Math.random,
// donc même série à chaque appel pour un symbole donné.
function seeded(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashSymbol(sym) {
  let h = 0;
  for (let i = 0; i < sym.length; i++) h = (h * 31 + sym.charCodeAt(i)) | 0;
  return Math.abs(h);
}

/** Historique synthétique : marche aléatoire avec dérive + volatilité par actif. */
function demoPrices(symbol, length = 120) {
  const rng = seeded(hashSymbol(symbol));
  const base = 50 + (hashSymbol(symbol) % 400);
  const drift = (rng() - 0.45) * 0.002;       // léger biais haussier/baissier
  const vol = 0.01 + rng() * 0.03;            // volatilité propre à l'actif
  const prices = [base];
  for (let i = 1; i < length; i++) {
    const shock = (rng() - 0.5) * 2 * vol;
    const next = prices[i - 1] * (1 + drift + shock);
    prices.push(Math.max(1, next));
  }
  return prices;
}

async function fetchHttp(symbol, cfg) {
  // EXEMPLE à adapter à ton fournisseur. Doit renvoyer un tableau de prix de clôture.
  // const res = await fetch(`${cfg.baseUrl}/klines?symbol=${symbol}`);
  // const json = await res.json();
  // return json.map(c => Number(c.close));
  throw new Error('datasource http non configurée — voir datasource.js');
}

async function getPrices(symbol, cfg) {
  const source = (cfg && cfg.source) || 'demo';
  if (source === 'http') return fetchHttp(symbol, cfg);
  return demoPrices(symbol);
}

module.exports = { getPrices, demoPrices };
