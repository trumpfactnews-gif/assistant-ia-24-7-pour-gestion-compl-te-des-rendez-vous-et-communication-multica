"""Présentation des résultats : tableaux texte, export JSON et CSV."""

from __future__ import annotations

import csv
import io
import json
from typing import Optional, Sequence

from .engine import SearchStats
from .models import Combo


def _fmt_pct(x: float) -> str:
    return f"{100.0 * x:.2f}%"


def _fmt_money(x: float) -> str:
    return f"{x:,.2f}".replace(",", " ")


def _truncate(s: str, width: int) -> str:
    return s if len(s) <= width else s[: width - 1] + "…"


def render_table(rows: list[list[str]], headers: list[str]) -> str:
    """Tableau texte aligné, sans dépendance externe."""
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    sep = "─"
    line = "┼".join(sep * (w + 2) for w in widths)
    out = [
        "│".join(f" {h:<{w}} " for h, w in zip(headers, widths)),
        line,
    ]
    for row in rows:
        out.append("│".join(f" {c:<{w}} " for c, w in zip(row, widths)))
    return "\n".join(out)


def render_combos(
    combos: Sequence[Combo],
    bankroll: Optional[float] = None,
    kelly_multiplier: float = 0.5,
    leg_width: int = 60,
) -> str:
    """Tableau des meilleurs combinés, une ligne par combiné + détail des jambes.

    Si ``bankroll`` est fournie, affiche la mise conseillée (Kelly fractionné
    par ``kelly_multiplier``) et le gain potentiel correspondant.
    """
    if not combos:
        return "Aucun combiné ne satisfait les contraintes."

    headers = ["#", "Jambes", "P(gain)", "Cote", "EV", "Sharpe", "Kelly"]
    if bankroll is not None:
        headers += ["Mise", "Gain pot."]

    rows = []
    for combo in combos:
        row = [
            str(combo.rank),
            str(combo.n_legs),
            _fmt_pct(combo.prob),
            f"{combo.payout:.2f}",
            _fmt_pct(combo.ev),
            f"{combo.sharpe:.3f}",
            _fmt_pct(combo.kelly),
        ]
        if bankroll is not None:
            stake = bankroll * combo.kelly * kelly_multiplier
            row += [_fmt_money(stake), _fmt_money(stake * combo.gain_net)]
        rows.append(row)

    lines = [render_table(rows, headers), ""]
    for combo in combos:
        lines.append(f"#{combo.rank} — {combo.n_legs} jambe(s), "
                     f"P={_fmt_pct(combo.prob)}, cote {combo.payout:.2f}, EV {_fmt_pct(combo.ev)}")
        for leg in combo.legs:
            lines.append(
                f"    · {_truncate(leg.label(), leg_width):<{leg_width}} "
                f"prix {leg.price:.3f} | cote {leg.odds:.2f} | p̂ {_fmt_pct(leg.prob)} "
                f"| edge {_fmt_pct(leg.ev)}"
            )
    return "\n".join(lines)


def render_stats(stats: SearchStats) -> str:
    """Résumé de la recherche : couverture, élagage, débit effectif."""
    coverage = (
        f"{stats.space_size:,}".replace(",", " ")
        + " combinaisons couvertes, "
        + f"{stats.nodes_visited:,}".replace(",", " ")
        + " nœuds visités, "
        + f"{stats.combos_evaluated:,}".replace(",", " ")
        + " combinés évalués"
    )
    speed = ""
    if stats.elapsed_s > 0:
        eff = stats.space_size / stats.elapsed_s
        speed = f" — {stats.elapsed_s:.3f}s (débit effectif ≈ {eff:,.0f} combinaisons/s)".replace(",", " ")
    return (
        f"Recherche : {coverage} "
        f"(élagage {100.0 * stats.pruning_ratio:.4f}%){speed}"
    )


def combos_to_dicts(
    combos: Sequence[Combo],
    bankroll: Optional[float] = None,
    kelly_multiplier: float = 0.5,
) -> list[dict]:
    out = []
    for combo in combos:
        d = {
            "rank": combo.rank,
            "n_legs": combo.n_legs,
            "prob": round(combo.prob, 6),
            "payout": round(combo.payout, 4),
            "ev": round(combo.ev, 6),
            "variance": round(combo.variance, 6),
            "sharpe": round(combo.sharpe, 4),
            "kelly": round(combo.kelly, 6),
            "score": round(combo.score, 6),
            "legs": [
                {
                    "market_id": leg.market_id,
                    "question": leg.market_question,
                    "outcome": leg.outcome,
                    "category": leg.category,
                    "price": round(leg.price, 6),
                    "odds": round(leg.odds, 4),
                    "prob": round(leg.prob, 6),
                    "edge_ev": round(leg.ev, 6),
                }
                for leg in combo.legs
            ],
        }
        if bankroll is not None:
            stake = bankroll * combo.kelly * kelly_multiplier
            d["stake"] = round(stake, 2)
            d["potential_net_gain"] = round(stake * combo.gain_net, 2)
        out.append(d)
    return out


def export_json(combos: Sequence[Combo], stats: SearchStats, **kwargs) -> str:
    payload = {
        "stats": {
            "space_size": stats.space_size,
            "nodes_visited": stats.nodes_visited,
            "combos_evaluated": stats.combos_evaluated,
            "elapsed_s": round(stats.elapsed_s, 4),
            "pruning_ratio": round(stats.pruning_ratio, 8),
        },
        "combos": combos_to_dicts(combos, **kwargs),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def export_csv(combos: Sequence[Combo], **kwargs) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["rank", "n_legs", "prob", "payout", "ev", "sharpe", "kelly", "stake", "legs"]
    )
    for d in combos_to_dicts(combos, **kwargs):
        legs_str = " || ".join(f"{leg['question']} -> {leg['outcome']}" for leg in d["legs"])
        writer.writerow(
            [
                d["rank"], d["n_legs"], d["prob"], d["payout"], d["ev"],
                d["sharpe"], d["kelly"], d.get("stake", ""), legs_str,
            ]
        )
    return buf.getvalue()
