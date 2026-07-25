"""Génération du rapport HTML.

Toute valeur interpolée est échappée (`html.escape(..., quote=True)`), les URL
sont filtrées par :func:`sanitize_url`, et une CSP `default-src 'none'` empêche
tout script, image ou requête sortante — le rapport est ouvert en ``file://``,
donc dans une origine privilégiée. Écriture atomique en 0600.
"""

from __future__ import annotations

import html
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .backtest import BacktestResult
from .checklist import Checklist
from .httpclient import LINKABLE_HOSTS
from .macro import MarketRegime
from .metrics import Metrics
from .portfolio import PositionPlan
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

_INSIDER_LABEL = {
    "ACHAT_GROUPE": "Achat groupé d'initiés",
    "ACHAT_ISOLE": "Achat isolé d'initié",
    "VENTE_GROUPEE": "Ventes groupées d'initiés",
    "VENTE": "Ventes d'initiés",
    "NEUTRE_REMUNERATION": "Rémunération uniquement",
    "NEUTRE": "Neutre",
    "INCONNU": "Aucun Form 4 exploitable",
}

DISCLAIMER = (
    "Document généré automatiquement à partir de sources publiques (SEC EDGAR, "
    "données de marché). Il ne constitue ni un conseil en investissement, ni une "
    "recommandation personnalisée, ni une sollicitation d'achat ou de vente. Les "
    "scores sont produits par une heuristique déterministe et non par un modèle "
    "validé statistiquement. Le DCF repose sur des hypothèses explicites, pas sur "
    "une mesure. Vérifiez toute donnée avant décision."
)

_CSS = """
:root { color-scheme: light dark; }
body { font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 0;
       padding: 2rem 1rem; background: #f6f7f9; color: #16181d; line-height: 1.55; }
main { max-width: 62rem; margin: 0 auto; }
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
.card .hint { font-size: .75rem; color: #6b7280; margin-top: .15rem; }
.scroll { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e3e6ea;
        border-radius: .6rem; overflow: hidden; font-size: .9rem; }
th, td { text-align: left; padding: .55rem .75rem; border-bottom: 1px solid #eef0f3; }
th { background: #f0f2f5; font-weight: 600; }
tr:last-child td { border-bottom: none; }
ul { margin: .4rem 0 0; padding-left: 1.1rem; }
li { margin: .25rem 0; }
.warn { background: #fff8e6; border-left: 4px solid #d29a1a; padding: .75rem 1rem;
        border-radius: .3rem; }
.note { font-size: .82rem; color: #6b7280; margin-top: .5rem; }
.footer { margin-top: 2.5rem; font-size: .78rem; color: #6b7280; border-top: 1px solid #e3e6ea;
          padding-top: 1rem; }
@media (prefers-color-scheme: dark) {
  body { background: #14161a; color: #e8eaed; }
  .card, table { background: #1c1f25; border-color: #2c313a; }
  th { background: #232830; } td { border-color: #262b33; }
  .sub, .card .label, .card .hint, .note, .footer { color: #9aa3af; }
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


def _card(label: str, value: str, hint: str | None = None) -> str:
    extra = f'<div class="hint">{e(hint)}</div>' if hint else ""
    return (
        f'<div class="card"><div class="label">{e(label)}</div>'
        f'<div class="value">{e(value)}</div>{extra}</div>'
    )


def _list_block(items: list[str], empty: str) -> str:
    if not items:
        return f'<p class="sub">{e(empty)}</p>'
    entries = "".join(f"<li>{e(item)}</li>" for item in items)
    return f"<ul>{entries}</ul>"


def _table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f'<p class="sub">{e(empty)}</p>'
    head = "".join(f"<th>{e(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def _filings_table(metrics: Metrics) -> str:
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
        items = ", ".join(filing.item_labels()) or ", ".join(filing.items) or "—"
        flag = "⚠ alerte" if filing.is_alert else ("dilution" if filing.is_dilution else "")
        rows.append(
            [
                link,
                e(filing.filed_at.isoformat() if filing.filed_at else None),
                e(items),
                e(flag or "—"),
                e(filing.description or "—"),
            ]
        )
    return _table(
        ["Formulaire", "Date", "Items", "Signal", "Description"],
        rows,
        "Aucun dépôt SEC récent disponible.",
    )


def _technical_block(metrics: Metrics, backtest: BacktestResult | None) -> str:
    view = metrics.technical
    if view is None:
        return '<p class="sub">Historique de cours indisponible : aucune mesure technique.</p>'

    cards = "".join(
        [
            _card("Signal 7 séances", view.signal, f"{view.history_points} séances d'historique"),
            _card("Momentum 20 j", _fmt_pct(view.momentum_20d_pct, True)),
            _card("Momentum 60 j", _fmt_pct(view.momentum_60d_pct, True)),
            _card("RSI 14", f"{view.rsi_14:.0f}" if view.rsi_14 is not None else "—"),
            _card("SMA 50", _fmt_money(view.sma_50, metrics.currency)),
            _card("SMA 200", _fmt_money(view.sma_200, metrics.currency)),
            _card(
                "Volatilité annualisée",
                f"{view.volatility_annual_pct:.0f} %" if view.volatility_annual_pct else "—",
            ),
            _card(
                "Écart au plus haut 52 s.",
                _fmt_pct(view.distance_from_high_pct, True),
            ),
        ]
    )

    measured = ""
    if backtest is not None and backtest.total_observations:
        rows = []
        for label, stats in backtest.per_signal.items():
            rows.append(
                [
                    e(label),
                    e(stats.observations),
                    e(f"{stats.mean_return_pct:+.2f} %" if stats.mean_return_pct is not None else "—"),
                    e(f"{stats.hit_rate_pct:.0f} %" if stats.hit_rate_pct is not None else "—"),
                    e(
                        f"{backtest.edge_pct(label):+.2f} pt"
                        if backtest.edge_pct(label) is not None
                        else "—"
                    ),
                ]
            )
        baseline = backtest.baseline
        rows.append(
            [
                "<em>Référence (toutes séances)</em>",
                e(baseline.observations),
                e(f"{baseline.mean_return_pct:+.2f} %" if baseline.mean_return_pct is not None else "—"),
                e(f"{baseline.hit_rate_pct:.0f} %" if baseline.hit_rate_pct is not None else "—"),
                "—",
            ]
        )
        measured = (
            f"<h2>Ce que vaut ce signal, mesuré sur {backtest.total_observations} séances</h2>"
            + _table(
                ["Signal", "Observations", "Rendement moyen à " + str(backtest.horizon) + " séances",
                 "Taux de séances positives", "Écart à la référence"],
                rows,
                "",
            )
            + '<p class="note">Mesure en échantillon sur ce seul titre, sans frais ni '
            "dividendes, sur fenêtres glissantes qui se recouvrent. À lire comme un "
            "ordre de grandeur, pas comme un test statistique.</p>"
        )
        if backtest.warnings:
            measured += f'<div class="warn">{_list_block(backtest.warnings, "")}</div>'

    return f'<div class="grid">{cards}</div>{measured}'


def _dcf_block(metrics: Metrics) -> str:
    dcf = metrics.dcf
    if not dcf.available or dcf.assumptions is None:
        return (
            '<p class="sub">DCF non calculable.</p>'
            + _list_block(dcf.warnings, "Aucune précision disponible.")
        )
    assumptions = dcf.assumptions
    cards = "".join(
        [
            _card("Valeur DCF / action", _fmt_money(dcf.value_per_share, metrics.currency)),
            _card(
                "Fourchette",
                f"{dcf.low_per_share} – {dcf.high_per_share}",
                "croissance ±5 points",
            ),
            _card("Écart au cours", _fmt_pct(dcf.upside_pct, True)),
            _card("Valeur d'entreprise", _fmt_money(dcf.enterprise_value, metrics.currency)),
        ]
    )
    rows = [
        ["Flux de trésorerie disponible", e(_fmt_money(assumptions.free_cash_flow, metrics.currency))],
        ["Croissance retenue", e(f"{assumptions.growth * 100:.1f} % / an")],
        ["Coût du capital (WACC)", e(f"{assumptions.wacc * 100:.1f} %")],
        ["Croissance terminale", e(f"{assumptions.terminal_growth * 100:.1f} %")],
        ["Horizon de projection", e(f"{assumptions.years} ans")],
        ["Dette nette déduite", e(_fmt_money(assumptions.net_debt, metrics.currency))],
        ["Nombre d'actions", e(f"{assumptions.shares:,.0f}".replace(",", " "))],
    ]
    return (
        f'<div class="grid">{cards}</div>'
        + _table(["Hypothèse", "Valeur"], rows, "")
        + _list_block(dcf.warnings, "")
        + '<p class="note">Un DCF est un modèle d\'hypothèses. Changez la croissance '
        "ou le coût du capital de deux points et la valeur bouge de dizaines de "
        "pourcents : la fourchette compte plus que le chiffre central.</p>"
    )


def _insider_block(metrics: Metrics) -> str:
    activity = metrics.insider
    if activity is None or not activity.available:
        return '<p class="sub">Aucun Form 4 exploitable sur la période couverte.</p>'
    verdict = activity.verdict()
    cards = "".join(
        [
            _card("Signal", _INSIDER_LABEL.get(verdict, verdict), f"{activity.forms_read} Form 4 lus"),
            _card(
                "Achats de marché",
                f"{len(activity.buys)} ({activity.distinct_buyers} initiés)",
                _fmt_money(activity.buy_value, metrics.currency),
            ),
            _card(
                "Ventes de marché",
                f"{len(activity.sells)} ({activity.distinct_sellers} initiés)",
                _fmt_money(activity.sell_value, metrics.currency),
            ),
            _card("Solde net", _fmt_money(activity.net_value, metrics.currency)),
        ]
    )
    rows = []
    for transaction in sorted(
        [t for t in activity.transactions if t.is_open_market_buy or t.is_open_market_sell],
        key=lambda t: (t.transaction_date is None, t.transaction_date),
        reverse=True,
    )[:12]:
        role = transaction.officer_title or (
            "administrateur" if transaction.is_director else "initié"
        )
        rows.append(
            [
                e(transaction.transaction_date.isoformat() if transaction.transaction_date else None),
                e(transaction.owner or "—"),
                e(role),
                e("achat" if transaction.is_open_market_buy else "vente"),
                e(f"{transaction.shares:,.0f}".replace(",", " ") if transaction.shares else "—"),
                e(_fmt_money(transaction.value, metrics.currency)),
            ]
        )
    return (
        f'<div class="grid">{cards}</div>'
        + _table(
            ["Date", "Initié", "Fonction", "Sens", "Titres", "Montant"],
            rows,
            "Aucune transaction de marché : uniquement de la rémunération.",
        )
        + '<p class="note">Seuls les codes P (achat sur le marché) et S (vente) sont '
        "comptés. Attributions, exercices d'options et retenues fiscales sont exclus : "
        "ce sont des mouvements de rémunération, pas des paris sur le titre.</p>"
    )


def _portfolio_block(plan: PositionPlan | None, metrics: Metrics) -> str:
    if plan is None:
        return ""
    cards = "".join(
        [
            _card("Pondération suggérée", f"{plan.suggested_weight_pct:.2f} %",
                  f"plafond {plan.max_weight_pct:.0f} %"),
            _card("Stop-loss", _fmt_money(plan.stop_loss_price, metrics.currency)),
            _card(
                "Prise de profit partielle",
                _fmt_money(plan.partial_take_profit_price, metrics.currency),
            ),
            _card(
                "Volatilité retenue",
                f"{plan.volatility_annual_pct:.0f} %" if plan.volatility_annual_pct else "—",
            ),
        ]
    )
    allocation = _table(
        ["Classe d'actifs", "Cible All Weather"],
        [[e(name), e(f"{weight:.1f} %")] for name, weight in plan.to_dict()["all_weather_reference"].items()],
        "",
    )
    return (
        "<h2>Dimensionnement et cadre d'allocation</h2>"
        f'<div class="grid">{cards}</div>'
        + _list_block(plan.rationale, "")
        + _list_block(plan.rules, "")
        + allocation
    )


def _macro_block(regime: MarketRegime | None) -> str:
    if regime is None or not regime.available:
        return ""
    cards = "".join(
        [
            _card("Régime de marché", regime.regime, f"score {regime.score}/100"),
            _card("VIX", f"{regime.vix_level:.1f}" if regime.vix_level else "—", regime.vix_state),
            _card(
                "S&P 500 vs SMA 200",
                "au-dessus" if regime.index_above_sma200 else "en dessous"
                if regime.index_above_sma200 is not None else "—",
            ),
            _card("Taux 10 ans, 60 j", _fmt_pct(regime.rates_change_60d_pct, True)),
        ]
    )
    return (
        "<h2>Contexte de marché</h2>"
        f'<div class="grid">{cards}</div>'
        + _list_block(regime.observations, "Aucune observation notable.")
        + '<p class="note">Mesuré sur des séries publiques (indice, volatilité '
        "implicite, taux longs). Les facteurs géopolitiques ne sont pas modélisés : "
        "aucune source exploitable ne les quantifie.</p>"
    )


_CRITERION_MARK = {"rempli": "✔", "non rempli": "✘", "non mesurable": "?"}


def _checklists_block(checklists: list[Checklist] | None) -> str:
    if not checklists:
        return ""
    blocks = []
    for entry in checklists:
        if entry is None:
            continue
        rows = [
            [
                e(_CRITERION_MARK.get(criterion.state, "?")),
                e(criterion.label),
                e(criterion.state),
                e(criterion.evidence),
            ]
            for criterion in entry.criteria
        ]
        verdict = "satisfaits" if entry.satisfied else "non satisfaits"
        blocks.append(
            f"<h2>{e(entry.name)} — {e(verdict)} ({e(entry.score)})</h2>"
            + _table(["", "Critère", "État", "Constat"], rows, "")
        )
    if not blocks:
        return ""
    return "".join(blocks) + (
        '<p class="note">Un critère non mesurable n\'est jamais compté comme '
        "rempli : une conjonction comportant un inconnu reste non satisfaite.</p>"
    )


def generate_html_report(
    metrics: Metrics,
    scores: ScoreResult,
    summary: str | None = None,
    backtest: BacktestResult | None = None,
    plan: PositionPlan | None = None,
    regime: MarketRegime | None = None,
    checklists: list[Checklist] | None = None,
) -> str:
    """Retourne le document HTML complet, entièrement échappé."""
    color, label = _BADGE.get(scores.recommendation, ("#4b5563", scores.recommendation))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    resilience = (
        f"{scores.resilience_score}/100" if scores.resilience_score is not None else "—"
    )
    parts = " · ".join(
        f"{name} {value}" for name, value in scores.resilience_parts.items() if value is not None
    )

    cards = "".join(
        [
            _card("Score de risque", f"{scores.risk_score}/100"),
            _card("Score d'opportunité", f"{scores.opportunity_score}/100"),
            _card("Score net", f"{scores.net_score:+.1f}"),
            _card("Confiance", f"{scores.confidence:.0%}"),
            _card("Résilience", resilience, parts or None),
            _card("Cours", _fmt_money(metrics.price, metrics.currency), metrics.price_source),
            _card("PE", f"{metrics.pe_ratio:.1f}" if metrics.pe_ratio else "—"),
            _card(
                "PE de référence",
                f"{metrics.pe_sector:.1f}" if metrics.pe_sector else "—",
                metrics.pe_source,
            ),
            _card("Prix cible (PE)", _fmt_money(metrics.target_price_pe, metrics.currency)),
            _card("Capitalisation", _fmt_money(metrics.market_cap, metrics.currency)),
        ]
    )

    financials = [
        ["Chiffre d'affaires", _fmt_money(metrics.revenue), metrics.fact_dates.get("revenue", "—")],
        ["Croissance annuelle", _fmt_pct(metrics.revenue_growth_yoy_pct, True), "calculé"],
        ["Résultat net", _fmt_money(metrics.net_income), metrics.fact_dates.get("net_income", "—")],
        ["Marge nette", _fmt_pct(metrics.profit_margin), "calculé"],
        ["Flux de trésorerie disponible", _fmt_money(metrics.free_cash_flow), "calculé"],
        ["Actif total", _fmt_money(metrics.assets), metrics.fact_dates.get("assets", "—")],
        ["Passif total", _fmt_money(metrics.liabilities), metrics.fact_dates.get("liabilities", "—")],
        ["Passif / actif", _fmt_pct(metrics.debt_to_assets), "calculé"],
        [
            "Ratio de liquidité générale",
            f"{metrics.current_ratio:.2f}" if metrics.current_ratio else "—",
            "calculé",
        ],
        ["Trésorerie", _fmt_money(metrics.cash), metrics.fact_dates.get("cash", "—")],
        ["Dette nette", _fmt_money(metrics.net_debt), "calculé"],
        [
            "Actions en circulation",
            f"{metrics.shares_outstanding:,.0f}".replace(",", " ")
            if metrics.shares_outstanding
            else "—",
            metrics.fact_dates.get("shares", "—"),
        ],
        [
            "Variation du nombre d'actions",
            _fmt_pct(metrics.share_count_growth_pct, True),
            "calculé",
        ],
        [
            "BPA dilué",
            f"{metrics.eps:.2f}" if metrics.eps is not None else "—",
            metrics.fact_dates.get("eps", "—"),
        ],
    ]
    financials_table = _table(
        ["Poste", "Valeur", "Période"],
        [[e(name), e(value), e(source)] for name, value, source in financials],
        "",
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

    peers_note = ""
    if metrics.peer_valuation.peers_used or metrics.peer_valuation.peers_failed:
        used = ", ".join(f"{t} (PE {pe})" for t, pe in metrics.peer_valuation.peers_used)
        failed = ", ".join(metrics.peer_valuation.peers_failed)
        peers_note = (
            f'<p class="note">Comparables retenus : {e(used or "aucun")}.'
            + (f" Écartés : {e(failed)}." if failed else "")
            + "</p>"
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
    Généré le {e(generated)} · Cours au {e(metrics.price_as_of or 'inconnu')}
  </p>
  <p><span class="badge" style="background:{e(color)}">{e(label)} — {e(scores.recommendation)}</span></p>

  <h2>Scores</h2>
  <div class="grid">{cards}</div>
  {peers_note}

  <h2>Facteurs de risque</h2>
  {_list_block(scores.risk_factors, "Aucun facteur de risque déclenché.")}

  <h2>Facteurs d'opportunité</h2>
  {_list_block(scores.opportunity_factors, "Aucun facteur d'opportunité déclenché.")}

  <h2>Analyse technique</h2>
  {_technical_block(metrics, backtest)}

  <h2>Valorisation par les flux (DCF)</h2>
  {_dcf_block(metrics)}

  <h2>Transactions d'initiés (Form 4)</h2>
  {_insider_block(metrics)}

  <h2>Données financières (SEC XBRL)</h2>
  {financials_table}

  <h2>Dépôts SEC récents</h2>
  {_filings_table(metrics)}

  {_macro_block(regime)}
  {_checklists_block(checklists)}
  {_portfolio_block(plan, metrics)}
  {summary_block}
  {warnings_block}

  <p class="footer">{e(DISCLAIMER)}</p>
</main>
</body>
</html>
"""


def write_atomic(path: Path, content: str) -> Path:
    """Écrit ``content`` de façon atomique, en 0600, sans état partiel."""
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
