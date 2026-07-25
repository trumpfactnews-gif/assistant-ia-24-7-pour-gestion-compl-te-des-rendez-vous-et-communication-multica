"""Point d'entrée en ligne de commande.

Sous-commandes : ``analyze``, ``list``, ``backtest``, ``debate``, ``watch``.
Codes de sortie explicites, gestion d'erreur typée, aucune trace brute à
l'écran.
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time
from pathlib import Path

from . import __version__, backtest as backtest_mod, scoring
from .config import Config, load_config
from .database import DatabaseManager
from .debate import MultiModelDebate
from .errors import ConfigError, OsintError, ValidationError
from .httpclient import HttpClient
from .logging_setup import get_logger, setup_logging
from .metrics import CollectOptions
from .notify import TelegramNotifier
from .pipeline import AnalysisBundle, AnalysisRequest, run_analysis
from .sources import prices
from .sources.sec import SecClient
from .validation import validate_ticker

log = get_logger(__name__)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFIG = 3
EXIT_RUNTIME = 4

WATCH_MIN_INTERVAL = 60
WATCH_MAX_INTERVAL = 86_400


def _ticker_list(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="osint",
        description="Analyse financière OSINT sur sources publiques (SEC EDGAR, marché).",
        epilog="Aide à la décision documentaire — ne constitue pas un conseil en investissement.",
    )
    parser.add_argument("--version", action="version", version=f"osint {__version__}")
    parser.add_argument("-v", "--verbose", action="store_true", help="journalisation détaillée")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="fichier de secrets")
    parser.add_argument("--output-dir", type=Path, default=None, help="répertoire des rapports")

    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="analyser un ticker")
    _add_analysis_arguments(analyze)
    analyze.add_argument("--summary", action="store_true", help="résumé LLM (DeepSeek) optionnel")
    analyze.add_argument("--notify", action="store_true", help="envoyer une alerte Telegram")
    analyze.add_argument("--no-report", action="store_true", help="ne pas écrire le rapport HTML")
    analyze.add_argument("--json", action="store_true", help="sortie JSON sur stdout")

    watch = sub.add_parser("watch", help="surveiller un ticker et alerter sur changement")
    _add_analysis_arguments(watch)
    watch.add_argument(
        "--interval", type=int, default=900,
        help="secondes entre deux analyses (60 à 86400, défaut 900)",
    )
    watch.add_argument("--max-iterations", type=int, default=0, help="0 = sans limite")
    watch.add_argument(
        "--notify", action="store_true", help="alerte Telegram à chaque changement"
    )

    listing = sub.add_parser("list", help="lister les analyses enregistrées")
    listing.add_argument("--ticker", default=None, help="filtrer sur un ticker")
    listing.add_argument("--limit", type=int, default=25)

    backtest_cmd = sub.add_parser(
        "backtest", help="mesurer le signal technique sur l'historique disponible"
    )
    backtest_cmd.add_argument("--ticker", required=True)
    backtest_cmd.add_argument("--horizon", type=int, default=backtest_mod.DEFAULT_HORIZON)
    backtest_cmd.add_argument("--range", dest="range_", default="5y",
                              choices=["1y", "2y", "5y", "10y", "max"])
    backtest_cmd.add_argument("--json", action="store_true")

    debate_cmd = sub.add_parser(
        "debate",
        help="consulter plusieurs modèles sur une analyse (API uniquement, sans navigateur)",
    )
    debate_cmd.add_argument("--ticker", required=True)
    debate_cmd.add_argument("--json", action="store_true")

    return parser


def _add_analysis_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ticker", required=True, help="symbole US (ex. AAPL, BRK.B)")
    parser.add_argument(
        "--peers", type=_ticker_list, default=(),
        help="comparables pour le PE de référence (ex. MSFT,GOOGL,META)",
    )
    parser.add_argument("--no-history", action="store_true", help="sauter l'analyse technique")
    parser.add_argument("--no-insiders", action="store_true", help="ne pas lire les Form 4")
    parser.add_argument("--no-macro", action="store_true", help="sauter le contexte de marché")
    parser.add_argument("--no-backtest", action="store_true", help="sauter la mesure du signal")


def _make_http(config: Config) -> HttpClient:
    return HttpClient(
        user_agent=config.sec_user_agent,
        timeout=config.http_timeout,
        retries=config.http_retries,
        max_bytes=config.max_response_bytes,
        requests_per_second=config.requests_per_second,
    )


def _build_request(args: argparse.Namespace) -> AnalysisRequest:
    return AnalysisRequest(
        ticker=validate_ticker(args.ticker),
        collect=CollectOptions(
            history=not args.no_history,
            insiders=not args.no_insiders,
            macro=not args.no_macro,
            peers=tuple(args.peers),
        ),
        with_backtest=not args.no_backtest,
        with_summary=bool(getattr(args, "summary", False)),
        with_report=not bool(getattr(args, "no_report", False)),
    )


# ------------------------------------------------------------------ analyze


def cmd_analyze(args: argparse.Namespace, config: Config) -> int:
    request = _build_request(args)
    log.info("analyse de %s", request.ticker)

    http = _make_http(config)
    sec_client = SecClient(http, cache_dir=config.output_dir / ".cache")
    db = DatabaseManager(config.db_path)

    bundle = run_analysis(config, http, sec_client, request, db)

    if args.notify:
        TelegramNotifier(config, http).send_analysis(bundle.metrics, bundle.scores, bundle.plan)

    if args.json:
        print(json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2, default=str))
    else:
        _print_bundle(bundle)
    return EXIT_OK


def _print_bundle(bundle: AnalysisBundle) -> None:
    data, result = bundle.metrics, bundle.scores
    print(f"\n{data.company_name} ({data.ticker})")
    if data.price is not None:
        print(f"  Cours          : {data.price:.2f} {data.currency} ({data.price_source})")
    print(f"  Risque         : {result.risk_score}/100")
    print(f"  Opportunité    : {result.opportunity_score}/100")
    print(f"  Score net      : {result.net_score:+.1f}")
    print(f"  Confiance      : {result.confidence:.0%}")
    if result.resilience_score is not None:
        parts = ", ".join(
            f"{name} {value}" for name, value in result.resilience_parts.items() if value is not None
        )
        print(f"  Résilience     : {result.resilience_score}/100  ({parts})")
    print(f"  Recommandation : {result.recommendation}")

    view = data.technical
    if view is not None and view.has_signal:
        print(
            f"\n  Technique      : {view.signal} — momentum 20 j {view.momentum_20d_pct:+.1f} %, "
            f"RSI {view.rsi_14:.0f}, volatilité {view.volatility_annual_pct:.0f} %"
        )
    if bundle.backtest and bundle.backtest.total_observations:
        stats = bundle.backtest.per_signal.get(view.signal) if view else None
        if stats and stats.observations:
            edge = bundle.backtest.edge_pct(view.signal)
            print(
                f"  Mesuré         : sur {stats.observations} cas passés, rendement moyen à "
                f"{bundle.backtest.horizon} séances {stats.mean_return_pct:+.2f} % "
                f"({stats.hit_rate_pct:.0f} % de cas positifs"
                + (f", écart de {edge:+.2f} pt vs référence)" if edge is not None else ")")
            )

    if data.dcf.available and data.dcf.upside_pct is not None:
        print(
            f"  DCF            : {data.dcf.value_per_share:.2f} {data.currency} "
            f"({data.dcf.upside_pct:+.1f} %), fourchette "
            f"{data.dcf.low_per_share}–{data.dcf.high_per_share}"
        )
    if data.insider is not None and data.insider.available:
        print(
            f"  Initiés        : {data.insider.verdict()} — {len(data.insider.buys)} achat(s), "
            f"{len(data.insider.sells)} vente(s) sur {data.insider.forms_read} Form 4"
        )
    if bundle.regime is not None and bundle.regime.available:
        print(f"  Marché         : {bundle.regime.regime} (score {bundle.regime.score}/100)")

    if result.risk_factors:
        print("\n  Risques :")
        for item in result.risk_factors:
            print(f"    - {item}")
    if result.opportunity_factors:
        print("\n  Opportunités :")
        for item in result.opportunity_factors:
            print(f"    - {item}")
    if result.missing_inputs:
        print("\n  Critères non évaluables :")
        for item in result.missing_inputs:
            print(f"    - {item}")

    marks = {"rempli": "✔", "non rempli": "✘", "non mesurable": "?"}
    for entry in (bundle.entry, bundle.exit):
        if entry is None:
            continue
        verdict = "SATISFAITS" if entry.satisfied else "non satisfaits"
        print(f"\n  {entry.name} — {verdict} ({entry.score}) :")
        for criterion in entry.criteria:
            print(f"    {marks.get(criterion.state, '?')} {criterion.label} — {criterion.evidence}")

    plan = bundle.plan
    if plan is not None and plan.suggested_weight_pct > 0:
        print(
            f"\n  Dimensionnement : {plan.suggested_weight_pct:.2f} % du portefeuille "
            f"(plafond {plan.max_weight_pct:.0f} %), stop {plan.stop_loss_price}, "
            f"prise de profit partielle {plan.partial_take_profit_price}"
        )

    for warning in bundle.metrics.warnings:
        print(f"\n  [!] {warning}")
    if bundle.summary:
        print(f"\n  Synthèse (générée, non vérifiée) :\n    {bundle.summary}")
    if bundle.report_path:
        print(f"\n  Rapport : {bundle.report_path}")
    print(
        "\n  Aide à la décision automatisée à partir de sources publiques. "
        "Ne constitue pas un conseil en investissement.\n"
    )


# -------------------------------------------------------------------- watch


class _StopWatch:
    """Arrêt propre sur SIGINT/SIGTERM, sans trace d'interruption."""

    def __init__(self) -> None:
        self.stopped = False
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, self._handle)
            except (ValueError, OSError):  # pragma: no cover - hors thread principal
                pass

    def _handle(self, *_: object) -> None:
        self.stopped = True
        log.info("arrêt demandé : fin après l'itération en cours")


def cmd_watch(args: argparse.Namespace, config: Config) -> int:
    """Mode surveillance : ré-analyse périodique, alerte sur changement.

    Documenté dans le guide d'origine (``--watch``) mais absent du code.
    N'alerte que lorsque la recommandation change : une notification à chaque
    tour serait ignorée au bout de deux jours.
    """
    interval = max(WATCH_MIN_INTERVAL, min(WATCH_MAX_INTERVAL, int(args.interval)))
    if interval != args.interval:
        log.warning("intervalle ramené à %d s (bornes %d–%d)", interval, WATCH_MIN_INTERVAL, WATCH_MAX_INTERVAL)

    request = _build_request(args)
    http = _make_http(config)
    sec_client = SecClient(http, cache_dir=config.output_dir / ".cache")
    db = DatabaseManager(config.db_path)
    notifier = TelegramNotifier(config, http) if args.notify else None

    watcher = _StopWatch()
    previous: str | None = None
    iterations = 0
    max_iterations = max(0, int(args.max_iterations))

    log.info("surveillance de %s toutes les %d s (Ctrl-C pour arrêter)", request.ticker, interval)
    while not watcher.stopped:
        iterations += 1
        try:
            bundle = run_analysis(config, http, sec_client, request, db)
        except OsintError as exc:
            # Une panne transitoire ne doit pas terminer une surveillance.
            log.warning("itération %d en échec : %s", iterations, exc)
        else:
            current = bundle.scores.recommendation
            changed = previous is not None and current != previous
            marker = "→ CHANGEMENT" if changed else ""
            print(
                f"[{iterations:>3}] {bundle.metrics.ticker} {current} "
                f"(confiance {bundle.scores.confidence:.0%}, "
                f"cours {bundle.metrics.price if bundle.metrics.price is not None else '—'}) {marker}"
            )
            if changed and notifier is not None:
                notifier.send(
                    f"Changement de recommandation {bundle.metrics.ticker} : "
                    f"{previous} → {current}\n"
                    f"Confiance {bundle.scores.confidence:.0%}, "
                    f"cours {bundle.metrics.price} {bundle.metrics.currency}"
                )
            previous = current

        if max_iterations and iterations >= max_iterations:
            break
        if watcher.stopped:
            break
        _sleep_interruptible(interval, watcher)

    log.info("surveillance terminée après %d itération(s)", iterations)
    return EXIT_OK


def _sleep_interruptible(seconds: int, watcher: _StopWatch) -> None:
    """Attend par tranches d'une seconde pour rester réactif à l'arrêt."""
    for _ in range(seconds):
        if watcher.stopped:
            return
        time.sleep(1)


# ----------------------------------------------------------------- backtest


def cmd_backtest(args: argparse.Namespace, config: Config) -> int:
    ticker = validate_ticker(args.ticker)
    http = _make_http(config)
    series = prices.fetch_history(http, ticker, range_=args.range_)
    result = backtest_mod.run(series, horizon=args.horizon)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return EXIT_OK

    print(f"\nBacktest du signal technique — {ticker}")
    print(f"  Historique : {len(series)} séances jusqu'au {series.last_date}")
    print(f"  Horizon    : {result.horizon} séances")
    print(f"  Observations : {result.total_observations}\n")
    print(f"  {'Signal':<16}{'N':>7}{'Moyenne':>11}{'Positifs':>11}{'Écart':>10}")
    for label, stats in result.per_signal.items():
        edge = result.edge_pct(label)
        print(
            f"  {label:<16}{stats.observations:>7}"
            f"{(f'{stats.mean_return_pct:+.2f} %' if stats.mean_return_pct is not None else '—'):>11}"
            f"{(f'{stats.hit_rate_pct:.0f} %' if stats.hit_rate_pct is not None else '—'):>11}"
            f"{(f'{edge:+.2f} pt' if edge is not None else '—'):>10}"
        )
    baseline = result.baseline
    print(
        f"  {'RÉFÉRENCE':<16}{baseline.observations:>7}"
        f"{(f'{baseline.mean_return_pct:+.2f} %' if baseline.mean_return_pct is not None else '—'):>11}"
        f"{(f'{baseline.hit_rate_pct:.0f} %' if baseline.hit_rate_pct is not None else '—'):>11}"
        f"{'—':>10}"
    )
    for warning in result.warnings:
        print(f"\n  [!] {warning}")
    print(
        "\n  Mesure en échantillon, un seul titre, sans frais ni dividendes, "
        "sur fenêtres glissantes qui se recouvrent.\n"
    )
    return EXIT_OK


# --------------------------------------------------------------------- list


def cmd_list(args: argparse.Namespace, config: Config) -> int:
    db = DatabaseManager(config.db_path)
    rows = db.list_analyses(ticker=args.ticker, limit=args.limit)
    if not rows:
        print("Aucune analyse enregistrée.")
        return EXIT_OK
    print(f"{'DATE':<26} {'TICKER':<8} {'RISQ':>5} {'OPP':>5} {'CONF':>5}  RECOMMANDATION")
    for row in rows:
        print(
            f"{row.created_at:<26} {row.ticker:<8} {row.risk_score:>5.1f} "
            f"{row.opportunity_score:>5.1f} {row.confidence:>4.0%}  {row.recommendation}"
        )
    return EXIT_OK


# ------------------------------------------------------------------- debate


def cmd_debate(args: argparse.Namespace, config: Config) -> int:
    ticker = validate_ticker(args.ticker)
    http = _make_http(config)
    sec_client = SecClient(http, cache_dir=config.output_dir / ".cache")

    request = AnalysisRequest(ticker=ticker, with_backtest=False, with_report=False)
    bundle = run_analysis(config, http, sec_client, request)
    result = MultiModelDebate(config, http).run(bundle.metrics, bundle.scores)

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return EXIT_OK

    print(f"\nConsultation multi-modèles — {ticker}")
    if not result.opinions:
        print("  Aucun fournisseur configuré (voir .env.example).")
        return EXIT_OK
    for opinion in result.opinions:
        status = opinion.error or opinion.rationale or "—"
        print(f"  {opinion.provider:<10} {opinion.verdict:<12} {status}")
    print(f"\n  Décompte   : {result.tally}")
    print(f"  Consensus  : {result.consensus} (confiance {result.confidence:.0%})")
    print(
        f"  Score interne : {bundle.scores.recommendation} "
        f"(confiance {bundle.scores.confidence:.0%})"
    )
    print(
        "\n  Les verdicts proviennent de modèles de langage : ils peuvent être "
        "erronés ou influencés par le contenu analysé. Le décompte est fait "
        "localement, sans arbitre IA.\n"
    )
    return EXIT_OK


# --------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    try:
        config = load_config(env_file=args.env_file, output_dir=args.output_dir)
    except ConfigError as exc:
        log.error("configuration invalide : %s", exc)
        return EXIT_CONFIG

    handlers = {
        "analyze": cmd_analyze,
        "watch": cmd_watch,
        "list": cmd_list,
        "backtest": cmd_backtest,
        "debate": cmd_debate,
    }
    try:
        return handlers[args.command](args, config)
    except ValidationError as exc:
        log.error("entrée invalide : %s", exc)
        return EXIT_USAGE
    except OsintError as exc:
        log.error("échec de l'analyse : %s", exc)
        return EXIT_RUNTIME
    except KeyboardInterrupt:  # pragma: no cover
        log.warning("interrompu")
        return EXIT_RUNTIME
    except OSError as exc:
        log.error("erreur système : %s", exc)
        return EXIT_RUNTIME


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
