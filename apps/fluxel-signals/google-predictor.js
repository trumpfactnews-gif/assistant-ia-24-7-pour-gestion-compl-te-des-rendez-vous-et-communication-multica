'use strict';
/**
 * Adaptateur "modèle de prédiction Google".
 *
 * Étape ① de la boucle (Recherche d'alpha) : prédire le rendement attendu d'un
 * actif sur l'horizon cible.
 *
 * Deux backends :
 *   - 'vertex'  → Google Cloud Vertex AI Forecasting (le vrai modèle de prévision
 *                 de séries temporelles). Nécessite GCP + endpoint déployé.
 *   - 'local'   → fallback statistique (lissage exponentiel de Holt / tendance)
 *                 pour tourner SANS compte Google. Déterministe, zéro réseau.
 *
 * Choix via la config (predictor.backend). Le fallback permet de tester toute la
 * chaîne immédiatement ; on bascule sur 'vertex' quand les credentials sont prêts.
 */

/**
 * Prédiction locale : tendance de Holt (niveau + pente) sur la série de prix.
 * Retourne le rendement attendu sur `horizon` pas, borné, + une confiance
 * dérivée de la régularité de la tendance (R²-like).
 */
function predictLocal(prices, horizon) {
  const n = prices.length;
  if (n < 10) return { expectedReturn: 0, confidence: 0, backend: 'local' };

  const alpha = 0.4, beta = 0.2; // lissage niveau / tendance
  let level = prices[0];
  let trend = prices[1] - prices[0];
  let sse = 0, sst = 0;
  const mean = prices.reduce((a, b) => a + b, 0) / n;

  for (let i = 1; i < n; i++) {
    const forecast = level + trend;
    const err = prices[i] - forecast;
    sse += err * err;
    sst += (prices[i] - mean) * (prices[i] - mean);
    const prevLevel = level;
    level = alpha * prices[i] + (1 - alpha) * (level + trend);
    trend = beta * (level - prevLevel) + (1 - beta) * trend;
  }

  const last = prices[n - 1];
  const projected = level + trend * horizon;
  let expectedReturn = (projected - last) / last;
  // borne de sécurité : pas de prédiction délirante
  expectedReturn = Math.max(-0.25, Math.min(0.25, expectedReturn));

  // confiance ~ qualité d'ajustement de la tendance, dans [0,1]
  const r2 = sst > 0 ? Math.max(0, 1 - sse / sst) : 0;
  const confidence = Math.max(0, Math.min(1, r2));

  return { expectedReturn, confidence, backend: 'local' };
}

/**
 * Prédiction Vertex AI Forecasting.
 * Squelette d'intégration : POST sur l'endpoint de prédiction du modèle déployé.
 * Renseigner predictor.vertex.{endpointUrl, accessToken} dans la config.
 * Tant que ce n'est pas configuré, on retombe sur le local (jamais d'échec dur).
 */
async function predictVertex(prices, horizon, cfg) {
  const v = (cfg && cfg.vertex) || {};
  if (!v.endpointUrl || !v.accessToken) {
    const local = predictLocal(prices, horizon);
    return { ...local, backend: 'local(vertex-non-configuré)' };
  }
  try {
    const body = JSON.stringify({
      instances: [{ history: prices, horizon }],
    });
    const res = await fetch(v.endpointUrl, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${v.accessToken}`,
        'Content-Type': 'application/json',
      },
      body,
    });
    if (!res.ok) throw new Error(`Vertex HTTP ${res.status}`);
    const json = await res.json();
    // Adapter selon le schéma de sortie réel de ton modèle Vertex :
    const pred = json.predictions?.[0] ?? {};
    const projected = Number(pred.value ?? pred.point_forecast ?? prices[prices.length - 1]);
    const last = prices[prices.length - 1];
    let expectedReturn = (projected - last) / last;
    expectedReturn = Math.max(-0.25, Math.min(0.25, expectedReturn));
    const confidence = Number(pred.confidence ?? 0.5);
    return { expectedReturn, confidence, backend: 'vertex' };
  } catch (err) {
    // Dégradation gracieuse : on n'arrête jamais la boucle sur une erreur réseau
    const local = predictLocal(prices, horizon);
    return { ...local, backend: `local(vertex-erreur:${err.message})` };
  }
}

async function predict(prices, horizon, cfg) {
  if (cfg && cfg.backend === 'vertex') return predictVertex(prices, horizon, cfg);
  return predictLocal(prices, horizon);
}

module.exports = { predict, predictLocal, predictVertex };
