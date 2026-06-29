/**
 * Widget fluxel-signals — à embarquer dans la page /marches du VPS.
 *
 * Usage dans la page :
 *   <div id="fluxel-signals" data-api="https://fluxel.tfnmedia.tech:8787"></div>
 *   <script src="https://fluxel.tfnmedia.tech:8787/widget.js"></script>
 *
 * (ou sers ce fichier statiquement et pointe data-api vers ton API de signaux)
 */
(function () {
  'use strict';

  var COLORS = { ACHETER: '#16a34a', VENDRE: '#dc2626', CONSERVER: '#64748b' };
  var LABELS = { ACHETER: 'ACHAT', VENDRE: 'VENTE', CONSERVER: 'NEUTRE' };

  function el(tag, css, txt) {
    var n = document.createElement(tag);
    if (css) n.style.cssText = css;
    if (txt != null) n.textContent = txt;
    return n;
  }

  function render(root, data) {
    root.innerHTML = '';
    var card = el('div', 'font-family:system-ui,sans-serif;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;max-width:560px;background:#fff');

    var head = el('div', 'display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:#0f172a;color:#fff');
    head.appendChild(el('strong', 'font-size:15px', 'Signaux marché'));
    head.appendChild(el('span', 'font-size:11px;opacity:.7', 'mode ' + data.mode));
    card.appendChild(head);

    data.signals.forEach(function (s) {
      var row = el('div', 'display:flex;align-items:center;gap:12px;padding:10px 16px;border-top:1px solid #f1f5f9');
      row.appendChild(el('span', 'font-weight:600;width:64px', s.symbol));

      var badge = el('span',
        'min-width:62px;text-align:center;padding:4px 10px;border-radius:999px;color:#fff;font-size:12px;font-weight:700;background:' + COLORS[s.action],
        LABELS[s.action]);
      row.appendChild(badge);

      var meta = el('div', 'flex:1;font-size:12px;color:#475569');
      meta.appendChild(el('div', '', 'prix ' + s.price + '  ·  prédiction ' + s.predictedReturnPct + '%'));
      meta.appendChild(el('div', 'color:#94a3b8', 'confiance ' + Math.round(s.confidence * 100) + '%  ·  score ' + s.score + (s.verified ? '' : '  ·  ⛔ non validé')));
      row.appendChild(meta);
      card.appendChild(row);
    });

    var foot = el('div', 'padding:8px 16px;font-size:10px;color:#94a3b8;border-top:1px solid #f1f5f9', data.disclaimer);
    card.appendChild(foot);
    root.appendChild(card);
  }

  function boot() {
    var root = document.getElementById('fluxel-signals');
    if (!root) return;
    var api = (root.getAttribute('data-api') || '').replace(/\/$/, '');
    var symbols = root.getAttribute('data-symbols');
    var url = api + '/api/signals' + (symbols ? '?symbols=' + encodeURIComponent(symbols) : '');

    function refresh() {
      fetch(url).then(function (r) { return r.json(); }).then(function (d) { render(root, d); })
        .catch(function (e) { root.textContent = 'Signaux indisponibles : ' + e.message; });
    }
    refresh();
    var every = parseInt(root.getAttribute('data-refresh') || '30000', 10);
    if (every > 0) setInterval(refresh, every);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
