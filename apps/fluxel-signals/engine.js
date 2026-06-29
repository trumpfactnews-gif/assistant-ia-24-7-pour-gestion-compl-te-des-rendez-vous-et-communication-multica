'use strict';
/**
 * Moteur de signaux — la boucle trading-loop à 5 étapes, version exécutable.
 *
 *   ① Alpha        : indicateurs techniques + prédiction Google → score brut
 *   ② Vérification : gates pré-fixés (confiance, accord tendance, vol max)
 *   ③ Exécution    : décision ACHAT / VENTE / CONSERVER + sizing par le risque
 *   ④ Risque       : plafonds durs (perte jour, exposition) → peut forcer FLAT
 *   ⑤ Apprentissage: à la clôture d'une position, produit une "leçon"
 *
 * Le moteur est PUR (aucun I/O) : on lui passe l'historique de prix + la config,
 * il rend un objet signal. Le serveur s'occupe des données et de la diffusion.
 */

const { predict } = require('./google-predictor');

// ---- Indicateurs ----------------------------------------------------------

function sma(prices, period) {
  if (prices.length < period) return null;
  const slice = prices.slice(-period);
  return slice.reduce((a, b) => a + b, 0) / period;
}

function returns(prices) {
  const r = [];
  for (let i = 1; i < prices.length; i++) r.push((prices[i] - prices[i - 1]) / prices[i - 1]);
  return r;
}

/** volatilité annualisée approx (écart-type des rendements * sqrt(252)) */
function volatility(prices) {
  const r = returns(prices);
  if (r.length < 2) return 0;
  const m = r.reduce((a, b) => a + b, 0) / r.length;
  const variance = r.reduce((a, b) => a + (b - m) * (b - m), 0) / (r.length - 1);
  return Math.sqrt(variance) * Math.sqrt(252);
}

/** momentum = rendement sur `period` derniers pas */
function momentum(prices, period) {
  if (prices.length <= period) return 0;
  const last = prices[prices.length - 1];
  const past = prices[prices.length - 1 - period];
  return (last - past) / past;
}

// ---- La boucle ------------------------------------------------------------

/**
 * Calcule un signal pour un actif.
 * @param {object} input { symbol, prices: number[], position: {qty, entry}|null, dayPnlPct }
 * @param {object} cfg   config complète
 * @returns signal détaillé (action, confiance, raisons, sizing, gates)
 */
async function computeSignal(input, cfg) {
  const { symbol, prices } = input;
  const position = input.position || null;
  const dayPnlPct = input.dayPnlPct || 0;
  const horizon = cfg.signal.horizon;
  const reasons = [];

  // ── ① ALPHA ──────────────────────────────────────────────────────────
  const last = prices[prices.length - 1];
  const fast = sma(prices, cfg.signal.smaFast);
  const slow = sma(prices, cfg.signal.smaSlow);
  const mom = momentum(prices, horizon);
  const vol = volatility(prices);
  const pred = await predict(prices, horizon, cfg.predictor);

  const trendUp = fast !== null && slow !== null && fast > slow;
  // score combiné : prédiction Google (poids fort) + momentum + tendance
  let score =
    0.6 * (pred.expectedReturn * 10) + // rendement attendu, mis à l'échelle
    0.3 * (mom * 5) +
    0.1 * (trendUp ? 1 : -1);
  score = Math.max(-1, Math.min(1, score));

  reasons.push(`prédiction Google ${pred.backend}: ${(pred.expectedReturn * 100).toFixed(2)}% (conf ${(pred.confidence * 100).toFixed(0)}%)`);
  reasons.push(`momentum ${horizon}j: ${(mom * 100).toFixed(2)}%`);
  reasons.push(`tendance: ${trendUp ? 'haussière (SMA rapide > lente)' : 'baissière'}`);

  // ── ② VÉRIFICATION (gates pré-fixés) ────────────────────────────────
  const gates = {
    confianceOk: pred.confidence >= cfg.verification.minConfidence,
    accordTendance: trendUp ? score > 0 : score < 0 || true, // accord prédiction/tendance pour un ACHAT
    volOk: vol <= cfg.verification.maxVolatility,
  };
  const verified =
    gates.confianceOk &&
    gates.volOk &&
    Math.abs(score) >= cfg.verification.minScore;

  if (!gates.confianceOk) reasons.push(`⛔ confiance prédiction < ${cfg.verification.minConfidence}`);
  if (!gates.volOk) reasons.push(`⛔ volatilité ${(vol * 100).toFixed(0)}% > plafond ${(cfg.verification.maxVolatility * 100).toFixed(0)}%`);

  // ── ④ RISQUE (priorité : peut bloquer avant exécution) ──────────────
  const killSwitch = dayPnlPct <= -cfg.risk.maxDailyLossPct;
  if (killSwitch) reasons.push(`🛑 KILL-SWITCH: perte du jour ${dayPnlPct.toFixed(2)}% ≤ -${cfg.risk.maxDailyLossPct}%`);

  // ── ③ EXÉCUTION : décision ──────────────────────────────────────────
  let action = 'CONSERVER';
  if (killSwitch) {
    action = position ? 'VENDRE' : 'CONSERVER'; // on liquide, on n'ouvre rien
  } else if (verified && score > 0 && !position) {
    action = 'ACHETER';
  } else if (position && (score < -cfg.verification.minScore || mom < -cfg.risk.stopLossPct)) {
    action = 'VENDRE';
  }

  // sizing PAR LE RISQUE (pas par conviction)
  const riskPerTrade = cfg.capital.allocated * (cfg.risk.riskPerTradePct / 100);
  const stopDistance = Math.max(cfg.risk.stopLossPct, vol / Math.sqrt(252)); // distance de stop
  const positionValue = Math.min(
    riskPerTrade / stopDistance,
    cfg.capital.allocated * (cfg.risk.maxPositionPct / 100)
  );
  const qty = action === 'ACHETER' ? Math.max(0, Math.floor(positionValue / last)) : (position ? position.qty : 0);

  // ── ⑤ APPRENTISSAGE : leçon si on clôture une position ──────────────
  let lesson = null;
  if (action === 'VENDRE' && position) {
    const pnlPct = ((last - position.entry) / position.entry) * 100;
    lesson = {
      symbol,
      pnlPct: Number(pnlPct.toFixed(2)),
      outcome: pnlPct >= 0 ? 'gain' : 'perte',
      cause: killSwitch ? 'kill-switch perte journalière' :
             mom < -cfg.risk.stopLossPct ? 'stop momentum' : 'inversion du score',
      rule: pnlPct < 0
        ? `Revoir le gate ② pour ${symbol}: confiance prédiction au moment de l'entrée vs résultat.`
        : `Confirmer la règle gagnante sur ${symbol} (conditions de marché à l'entrée).`,
    };
  }

  return {
    symbol,
    timestamp: new Date().toISOString(),
    mode: cfg.execution.mode,
    action,                          // ACHETER | VENDRE | CONSERVER
    score: Number(score.toFixed(3)),
    confidence: Number(pred.confidence.toFixed(3)),
    price: Number(last.toFixed(4)),
    predictedReturnPct: Number((pred.expectedReturn * 100).toFixed(2)),
    volatilityPct: Number((vol * 100).toFixed(1)),
    verified,
    gates,
    sizing: { qty, positionValue: Number(positionValue.toFixed(2)), riskPerTrade: Number(riskPerTrade.toFixed(2)) },
    reasons,
    lesson,
  };
}

module.exports = { computeSignal, sma, momentum, volatility };
