"""Génération du rapport HTML.

Faille majeure de l'original : ``generate_html_report`` interpolait des chaînes
issues du réseau (raison sociale, intitulés de filings, URL, résumé produit par
un LLM) dans du HTML, puis écrivait le fichier sur disque. Ouvert en
``file://``, ce document s'exécute dans une origine privilégiée : une
description de filing contenant ``<img src=x onerror=fetch(...)>`` ou un lien
``javascript:`` donnait une exécution de script capable de lire les fichiers
locaux voisins (dont ``.env``) et de les exfiltrer.

Contre-mesures ici :

* ``html.escape(..., quote=True)`` sur **toute** valeur interpolée, y compris
  les nombres formatés ;
* URL filtrées par :func:`sanitize_url` (HTTPS + hôtes SEC uniquement) ;
* Content-Security-Policy ``default-src 'none'`` : aucun script, aucune image,
  aucune requête sortante ne peut partir du rapport, même si un échappement
  était contourné ;
* ``rel="noopener noreferrer"`` et ``referrerpolicy="no-referrer"`` ;
* écriture atomique avec permissions 0600.
"""

from __future__ import annotations

import html
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .httpclient import LINKABLE_HOSTS
from .metrics import Metrics
from .scoring import ScoreResult
from .validation import sanitize_url

_BADGE = {
    "STRONG_BUY": ("#0b6b3a", "Achat renforcé"),
    "BUY": ("#127a45", "Achat"),
    "HOLD": ("#8a6d1f", "Conservation"),
    "REDUCE": ("#a4531b", "Réduction"),
    "SELL": ("#9b1c1c", "Vente"),
    "INSUFFICIENT_DATA": ("#4b5563", "Données insuffisantes"),
}

DISCLAIMER = (
    "Document généré automatiquement à partir de sources publiques (SEC EDGAR, "
    "données de marché). Il ne constitue ni un conseil en investissement, ni une "
    "recommandation personnalisée, ni une sollicitation d'achat ou de vente. Les "
    "scores sont produits par une heuristique déterministe et non par un modèle "
    "validé statistiquement. Vérifiez toute donnée avant décision."
)

_CSS = """
:root { color-scheme: light dark; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0;
       padding: 2rem 1rem; background: #f6f7f9; color: #16181d; line-height: 1.55; }
main { max-width: 60rem; margin: 0 auto; }
h1 { font-size: 1.6rem; margin: 0 0 .25rem; }
h2 { font-size: 1.05rem; margin: 2rem 0 .6rem; text-transform: uppercase;
     letter-spacing: .06em; color: #4b5563; }
.sub { color: #4b5563; margin: 0 0 1.5rem; font-size: .9rem; }
.badge { display: inline-block; padding: .35rem .8rem; border-radius: 999px;
         color: #fff; font-weight: 600; font-size: .85rem; }
.grid { display: grid; gap: .75rem; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); }
.card { background: #fff; border: 1px solid #e3e6ea; border-radius: .6rem; padding: .9rem 1rem; }
.card .label { font-size: .75rem; text-transform: uppercase; letter-spacing: .05em; color: #6b7280; }
.card .value { font-size: 1.25rem; font-weight: 650; margin-top: .2rem; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e3e6ea;
        border-radius: .6rem; overflow: hidden; font-size: .9rem; }
th, td { text-align: left; padding: .55rem .75rem; border-bottom: 1px solid #eef0f3; }
th { background: #f0f2f5; font-weight: 600; }
tr:last-child td { border-bottom: none; }
ul { margin: .4rem 0 0; padding-left: 1.1rem; }
li { margin: .25rem 0; }
.warn { background: #fff8e6; border-left: 4px solid #d29a1a; padding: .75rem 1rem;
        border-radius: .3rem; }
.footer { margin-top: 2.5rem; font-size: .78rem; color: #6b7280; border-top: 1px solid #e3e6ea;
          padding-top: 1rem; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e8eaed; }
  .card, table { background: #1c1f25; border-color: #2c313a; }
  th { background: #232830; } td { border-color: #262b33; }
  .sub, .card .label, .footer { color: #9aa3af; }
  .warn { background: #2a2415; }
}
"""


def e(value: object) -> str:
    """Échappe toute valeur pour insertion dans du HTML."""
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def _fmt_money(value: float | None, currency: str = "USD") -> str:
    if value is None:
        return "—"
    magnitude = abs(value)
    for threshold, suffix in ((1e12, " T"), (1e9, " Md"), (1e6, " M")):
        if magnitude >= threshold:
            return f"{value / threshold:,.2f}{suffix} {currency}".replace(",", " ")
    return f"{value:,.2f} {currency}".replace(",", " ")


def _fmt_pct(value: float | None, already_pct: bool = False) -> str:
    if value is None:
        return "—"
    return f"{value:+.1f} %" if already_pct else f"{value:.1%}"


def _card(label: str, value: str) -> str:
    return f'<div class="card"><div class="label">{e(label)}</div><div class="value">{e(value)}</div></div>'


def _list_block(items: list[str], empty: str) -> str:
    if not items:
        return f"<p class=\"sub\">{e(empty)}</p>"
    entries = "".join(f"<li>{e(item)}</li>" for item in items)
    return f"<ul>{entries}</ul>"


def _filings_table(metrics: Metrics) -> str:
    if not metrics.filings:
        return '<p class="sub">Aucun dépôt SEC récent disponible.</p>'
    rows = []
    for filing in metrics.filings[:20]:
        safe_url = sanitize_url(filing.url, LINKABLE_HOSTS)
        label = e(filing.form)
        link = (
            f'<a href="{e(safe_url)}" rel="noopener noreferrer" '
            f'referrerpolicy="no-referrer" target="_blank">{label}</a>'
            if safe_url
            else label
        )
        rows.append(
            "<tr>"
            f"<td>{link}</td>"
            f"<td>{e(filing.filed_at.isoformat() if filing.filed_at else None)}</td>"
            f"<td>{e(filing.description or '—')}</td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Formulaire</th><th>Date</th><th>Description</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def generate_html_report(
    metrics: Metrics,
    scores: ScoreResult,
    summary: str | None = None,
) -> str:
    """Retourne le document HTML complet, entièrement échappé."""
    color, label = _BADGE.get(scores.recommendation, ("#4b5563", scores.recommendation))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    cards = "".join(
        [
            _card("Score de risque", f"{scores.risk_score}/100"),
            _card("Score d'opportunité", f"{scores.opportunity_score}/100"),
            _card("Score net", f"{scores.net_score:+.1f}"),
            _card("Confiance", f"{scores.confidence:.0%}"),
            _card("Cours", _fmt_money(metrics.price, metrics.currency)),
            _card("PE", f"{metrics.pe_ratio:.1f}" if metrics.pe_ratio else "—"),
            _card("PE médian secteur", f"{metrics.pe_sector:.0f}" if metrics.pe_sector else "—"),
            _card("Prix cible (PE)", _fmt_money(metrics.target_price_pe, metrics.currency)),
        ]
    )

    financials = "".join(
        f"<tr><td>{e(name)}</td><td>{e(value)}</td><td>{e(source)}</td></tr>"
        for name, value, source in [
            ("Chiffre d'affaires", _fmt_money(metrics.revenue), metrics.fact_dates.get("revenue", "—")),
            ("Résultat net", _fmt_money(metrics.net_income), metrics.fact_dates.get("net_income", "—")),
            ("Marge nette", _fmt_pct(metrics.profit_margin), "calculé"),
            ("Actif total", _fmt_money(metrics.assets), metrics.fact_dates.get("assets", "—")),
            ("Passif total", _fmt_money(metrics.liabilities), metrics.fact_dates.get("liabilities", "—")),
            ("Passif / actif", _fmt_pct(metrics.debt_to_assets), "calculé"),
            ("Trésorerie", _fmt_money(metrics.cash), metrics.fact_dates.get("cash", "—")),
            ("BPA dilué", f"{metrics.eps:.2f}" if metrics.eps is not None else "—",
             metrics.fact_dates.get("eps", "—")),
        ]
    )

    summary_block = ""
    if summary:
        # Le texte vient d'un LLM : donnée non fiable, échappée comme le reste.
        summary_block = (
            "<h2>Synthèse générée (non vérifiée)</h2>"
            f'<div class="warn">{e(summary)}</div>'
        )

    warnings_block = ""
    if metrics.warnings or scores.missing_inputs:
        warnings_block = (
            "<h2>Limites de cette analyse</h2>"
            f'<div class="warn">{_list_block(list(metrics.warnings) + scores.missing_inputs, "Aucune")}</div>'
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<title>Analyse OSINT — {e(metrics.ticker)}</title>
<style>{_CSS}</style>
</head>
<body>
<main>
  <h1>{e(metrics.company_name)} <span style="font-weight:400">({e(metrics.ticker)})</span></h1>
  <p class="sub">
    CIK {e(metrics.cik)} · Secteur estimé : {e(metrics.sic_description or metrics.sector)} ·
    Généré le {e(generated)} · Prix : {e(metrics.price_source or 'indisponible')}
    {e(metrics.price_as_of or '')}
  </p>
  <p><span class="badge" style="background:{e(color)}">{e(label)} — {e(scores.recommendation)}</span></p>

  <h2>Scores</h2>
  <div class="grid">{cards}</div>

  <h2>Facteurs de risque</h2>
  {_list_block(scores.risk_factors, "Aucun facteur de risque déclenché.")}

  <h2>Facteurs d'opportunité</h2>
  {_list_block(scores.opportunity_factors, "Aucun facteur d'opportunité déclenché.")}

  <h2>Données financières (SEC XBRL)</h2>
  <table>
    <thead><tr><th>Poste</th><th>Valeur</th><th>Période</th></tr></thead>
    <tbody>{financials}</tbody>
  </table>

  <h2>Dépôts SEC récents</h2>
  {_filings_table(metrics)}

  {summary_block}
  {warnings_block}

  <p class="footer">{e(DISCLAIMER)}</p>
</main>
</body>
</html>
"""


def write_atomic(path: Path, content: str) -> Path:
    """Écrit ``content`` de façon atomique, en 0600, sans état partiel.

    L'original ouvrait directement le fichier cible : une interruption laissait
    un rapport tronqué que rien ne distinguait d'un rapport valide.
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_name, 0o600)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
    return path
