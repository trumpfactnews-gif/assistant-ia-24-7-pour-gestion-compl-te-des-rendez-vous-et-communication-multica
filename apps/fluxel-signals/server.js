'use strict';
/**
 * Serveur de signaux fluxel — HTTP pur (zéro dépendance npm).
 *
 * Endpoints :
 *   GET /api/health          → état du service
 *   GET /api/signals         → signaux ACHAT/VENTE/CONSERVER pour la watchlist
 *   GET /api/signals?symbols=BTC,AAPL
 *   GET /widget.js           → widget JS à embarquer dans la page fluxel
 *   GET /                     → page de démo (aperçu du widget)
 *
 * État paper en mémoire : positions ouvertes + P&L du jour (simulation).
 * Aucun ordre réel n'est envoyé. Pour passer live : voir README (section broker).
 */

const http = require('http');
const fs = require('fs');
const path = require('path');
const { computeSignal } = require('./engine');
const { getPrices } = require('./datasource');

const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, 'config.json'), 'utf8'));
const LESSONS_PATH = path.join(__dirname, 'lessons.log.jsonl');

// État paper (simulation) — en prod, persister en base.
const state = {
  positions: {},   // symbol -> { qty, entry }
  dayPnlPct: 0,
};

function appendLesson(lesson) {
  if (!lesson) return;
  try {
    fs.appendFileSync(LESSONS_PATH, JSON.stringify({ ts: new Date().toISOString(), ...lesson }) + '\n');
  } catch (_) { /* non bloquant */ }
}

async function buildSignals(symbols) {
  const out = [];
  for (const symbol of symbols) {
    const prices = await getPrices(symbol, cfg.datasource);
    const position = state.positions[symbol] || null;
    const signal = await computeSignal({ symbol, prices, position, dayPnlPct: state.dayPnlPct }, cfg);

    // Application paper de la décision (simulation d'exécution)
    if (cfg.execution.mode === 'paper') {
      if (signal.action === 'ACHETER' && signal.sizing.qty > 0) {
        state.positions[symbol] = { qty: signal.sizing.qty, entry: signal.price };
      } else if (signal.action === 'VENDRE' && position) {
        appendLesson(signal.lesson);
        delete state.positions[symbol];
      }
    }
    out.push(signal);
  }
  return out;
}

function send(res, code, body, type = 'application/json') {
  res.writeHead(code, {
    'Content-Type': type,
    'Access-Control-Allow-Origin': cfg.server.corsOrigin || '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Cache-Control': 'no-store',
  });
  res.end(typeof body === 'string' ? body : JSON.stringify(body));
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  if (req.method === 'OPTIONS') return send(res, 204, '');

  try {
    if (url.pathname === '/api/health') {
      return send(res, 200, { ok: true, mode: cfg.execution.mode, predictor: cfg.predictor.backend, watchlist: cfg.watchlist });
    }

    if (url.pathname === '/api/signals') {
      const q = url.searchParams.get('symbols');
      const symbols = q ? q.split(',').map(s => s.trim().toUpperCase()).filter(Boolean) : cfg.watchlist;
      const signals = await buildSignals(symbols);
      return send(res, 200, {
        generatedAt: new Date().toISOString(),
        mode: cfg.execution.mode,
        disclaimer: 'Signaux algorithmiques en mode ' + cfg.execution.mode + '. Aucun conseil en investissement. Aucun ordre réel envoyé.',
        signals,
      });
    }

    if (url.pathname === '/widget.js') {
      const js = fs.readFileSync(path.join(__dirname, 'widget.js'), 'utf8');
      return send(res, 200, js, 'application/javascript');
    }

    if (url.pathname === '/') {
      const html = fs.readFileSync(path.join(__dirname, 'demo.html'), 'utf8');
      return send(res, 200, html, 'text/html; charset=utf-8');
    }

    return send(res, 404, { error: 'not found' });
  } catch (err) {
    return send(res, 500, { error: err.message });
  }
});

const port = process.env.PORT || cfg.server.port || 8787;
server.listen(port, () => {
  console.log(`fluxel-signals sur http://localhost:${port}  (mode=${cfg.execution.mode}, predictor=${cfg.predictor.backend})`);
});

module.exports = { buildSignals, state };
