"""Interface en ligne de commande de predopt.

Commandes :

- ``predopt generate`` — génère un univers de marchés synthétiques (JSON) ;
- ``predopt analyze``  — analyse un fichier de marchés et classe les
  meilleures opportunités (simples et combinés) ;
- ``predopt bench``    — benchmark du moteur combinatoire à grande échelle.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .data import generate_sample_markets, load_markets, markets_to_legs, save_markets
from .engine import CombinationEngine, search_space_size
from .report import export_csv, export_json, render_combos, render_stats

_DISCLAIMER = (
    "⚠ Les probabilités sont des estimations statistiques, pas des garanties.\n"
    "  Une EV positive ne protège pas de la variance : ne misez que ce que\n"
    "  vous pouvez perdre, et préférez le Kelly fractionné (défaut : 50 %)."
)


def _cmd_generate(args: argparse.Namespace) -> int:
    markets = generate_sample_markets(
        n_markets=args.markets, seed=args.seed, vig=args.vig
    )
    save_markets(markets, args.out)
    print(f"{len(markets)} marchés synthétiques écrits dans {args.out}")
    return 0


def _cmd_analyze(args: argparse.Namespace) -> int:
    markets = load_markets(args.file)
    legs = markets_to_legs(
        markets,
        devig_method=args.devig,
        model_weight=args.model_weight,
        min_leg_ev=args.min_leg_ev,
        max_odds=args.max_odds,
    )
    if not legs:
        print("Aucune jambe candidate après filtrage — assouplissez --min-leg-ev / --max-odds.")
        return 1

    engine = CombinationEngine(legs, haircut=args.haircut, kelly_cap=args.kelly_cap)
    combos, stats = engine.search(
        min_legs=args.min_legs,
        max_legs=args.max_legs,
        top=args.top,
        objective=args.objective,
        min_prob=args.min_prob,
        min_payout=args.min_payout,
    )

    if args.json:
        Path(args.json).write_text(
            export_json(combos, stats, bankroll=args.bankroll, kelly_multiplier=args.kelly_multiplier),
            encoding="utf-8",
        )
    if args.csv:
        Path(args.csv).write_text(
            export_csv(combos, bankroll=args.bankroll, kelly_multiplier=args.kelly_multiplier),
            encoding="utf-8",
        )

    print(f"Univers : {len(markets)} marchés → {len(legs)} jambes candidates "
          f"(objectif : {args.objective})")
    print(render_stats(stats))
    print()
    print(render_combos(combos, bankroll=args.bankroll, kelly_multiplier=args.kelly_multiplier))
    print()
    print(_DISCLAIMER)
    if args.json:
        print(f"\nExport JSON : {args.json}")
    if args.csv:
        print(f"Export CSV  : {args.csv}")
    return 0


def _cmd_bench(args: argparse.Namespace) -> int:
    markets = generate_sample_markets(n_markets=args.markets, seed=args.seed)
    legs = markets_to_legs(markets)
    space = search_space_size(len(legs), 1, args.legs)
    print(f"{len(markets)} marchés, {len(legs)} jambes candidates")
    print(f"Espace de recherche (1 à {args.legs} jambes) : {space:,} combinaisons".replace(",", " "))
    engine = CombinationEngine(legs, haircut=0.03)
    combos, stats = engine.search(
        min_legs=1, max_legs=args.legs, top=args.top,
        objective=args.objective, min_prob=args.min_prob,
    )
    print(render_stats(stats))
    if combos:
        best = combos[0]
        print(f"Meilleur combiné : {best.n_legs} jambes, P={100 * best.prob:.2f}%, "
              f"cote {best.payout:.2f}, EV {100 * best.ev:+.2f}%")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="predopt",
        description="Optimiseur de paris pour marchés prédictifs (style Polymarket) : "
                    "moteur combinatoire à élagage, probabilités dé-viggées, EV, Kelly.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_gen = sub.add_parser("generate", help="générer des marchés synthétiques (JSON)")
    p_gen.add_argument("--markets", type=int, default=50, help="nombre de marchés (défaut 50)")
    p_gen.add_argument("--seed", type=int, default=42, help="graine aléatoire")
    p_gen.add_argument("--vig", type=float, default=0.02, help="marge de la plateforme (défaut 0.02)")
    p_gen.add_argument("--out", default="markets.json", help="fichier de sortie")
    p_gen.set_defaults(func=_cmd_generate)

    p_an = sub.add_parser("analyze", help="analyser un fichier de marchés et classer les opportunités")
    p_an.add_argument("file", help="fichier JSON de marchés")
    p_an.add_argument("--min-legs", type=int, default=1, help="taille min. des combinés (défaut 1)")
    p_an.add_argument("--max-legs", type=int, default=3, help="taille max. des combinés (défaut 3)")
    p_an.add_argument("--top", type=int, default=15, help="nombre d'opportunités affichées (défaut 15)")
    p_an.add_argument(
        "--objective", choices=["ev", "sharpe", "log_growth", "prob"], default="sharpe",
        help="critère de classement : ev (agressif), sharpe (équilibré, défaut), "
             "log_growth (croissance bankroll), prob (prudent)",
    )
    p_an.add_argument("--min-prob", type=float, default=0.0, help="probabilité de gain minimale")
    p_an.add_argument("--min-payout", type=float, default=1.0, help="cote combinée minimale")
    p_an.add_argument("--min-leg-ev", type=float, default=0.0,
                      help="EV minimale d'une jambe pour entrer dans le pool (défaut 0 = edge positif)")
    p_an.add_argument("--max-odds", type=float, default=50.0,
                      help="cote max. d'une jambe (écarte les contrats illiquides, défaut 50)")
    p_an.add_argument("--devig", choices=["power", "proportional"], default="power",
                      help="méthode de retrait de la marge (défaut power)")
    p_an.add_argument("--model-weight", type=float, default=0.5,
                      help="poids de l'estimation de modèle vs marché, dans [0,1] (défaut 0.5)")
    p_an.add_argument("--haircut", type=float, default=0.03,
                      help="malus de corrélation par jambe supplémentaire (défaut 0.03)")
    p_an.add_argument("--bankroll", type=float, default=None,
                      help="bankroll pour le calcul des mises conseillées")
    p_an.add_argument("--kelly-multiplier", type=float, default=0.5,
                      help="fraction du Kelly plein appliquée aux mises (défaut 0.5)")
    p_an.add_argument("--kelly-cap", type=float, default=0.25,
                      help="plafond de la fraction de bankroll par pari (défaut 0.25)")
    p_an.add_argument("--json", default=None, help="exporter le résultat en JSON vers ce fichier")
    p_an.add_argument("--csv", default=None, help="exporter le résultat en CSV vers ce fichier")
    p_an.set_defaults(func=_cmd_analyze)

    p_be = sub.add_parser("bench", help="benchmark du moteur combinatoire")
    p_be.add_argument("--markets", type=int, default=300, help="nombre de marchés synthétiques")
    p_be.add_argument("--legs", type=int, default=5, help="taille max. des combinés")
    p_be.add_argument("--top", type=int, default=50, help="top-K recherché")
    p_be.add_argument("--objective", choices=["ev", "sharpe", "log_growth", "prob"], default="ev")
    p_be.add_argument("--min-prob", type=float, default=0.0)
    p_be.add_argument("--seed", type=int, default=7)
    p_be.set_defaults(func=_cmd_bench)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
