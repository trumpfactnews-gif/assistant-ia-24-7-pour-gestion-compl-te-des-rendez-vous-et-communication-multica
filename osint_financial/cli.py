"""Point d'entrée en ligne de commande.

Failles corrigées du ``main()`` d'origine :

* ``args.ticker.upper()`` sur ``None`` → ``AttributeError`` quand ni
  ``--ticker`` ni ``--list`` n'était donné ;
* ``--summary`` était déclaré puis jamais utilisé (fonctionnalité morte) ;
* ``--watch`` était documenté mais absent du parseur ;
* ``DatabaseManager()`` instancié deux fois ;
* ``from report import generate_html_report`` importé au milieu de la fonction
  depuis un module absent du dépôt → ``ImportError`` en fin de course, après
  tous les appels réseau ;
* imports morts (``sys``, ``json``, ``DeepSeekSummarizer``) et dictionnaire
  ``POINTS`` inutilisé ;
* aucun code de sortie exploitable en script/CI ;
* aucune gestion d'erreur : toute exception affichait une trace complète.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, metrics as metrics_mod, scoring
from .config import Config, load_config
from .database import DatabaseManager
from .debate import MultiModelDebate
from .errors import ConfigError, OsintError, ValidationError
from .httpclient import HttpClient
from .logging_setup import get_logger, setup_logging
from .notify import TelegramNotifier
from .report import generate_html_report, write_atomic
from .sources.sec import SecClient
from .summarizer import DeepSeekSummarizer
from .validation import safe_child_path, validate_ticker

log = get_logger(__name__)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_CONFIG = 3
EXIT_RUNTIME = 4


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
    analyze.add_argument("--ticker", required=True, help="symbole US (ex. AAPL, BRK.B)")
    analyze.add_argument("--summary", action="store_true", help="résumé LLM (DeepSeek) optionnel")
    analyze.add_argument("--notify", action="store_true", help="envoyer une alerte Telegram")
    analyze.add_argument("--no-report", action="store_true", help="ne pas écrire le rapport HTML")
    analyze.add_argument("--json", action="store_true", help="sortie JSON sur stdout")

    listing = sub.add_parser("list", help="lister les analyses enregistrées")
    listing.add_argument("--ticker", default=None, help="filtrer sur un ticker")
    listing.add_argument("--limit", type=int, default=25)

    debate_cmd = sub.add_parser(
        "debate",
        help="consulter plusieurs modèles sur une analyse (API uniquement, sans navigateur)",
    )
    debate_cmd.add_argument("--ticker", required=True)
    debate_cmd.add_argument("--json", action="store_true")

    return parser


def _make_http(config: Config) -> HttpClient:
    return HttpClient(
        user_agent=config.sec_user_agent,
        timeout=config.http_timeout,
        retries=config.http_retries,
        max_bytes=config.max_response_bytes,
        requests_per_second=config.requests_per_second,
    )


def cmd_analyze(args: argparse.Namespace, config: Config) -> int:
    ticker = validate_ticker(args.ticker)
    log.info("analyse de %s", ticker)

    http = _make_http(config)
    sec_client = SecClient(http, cache_dir=config.output_dir / ".cache")

    data = metrics_mod.collect(http, ticker, sec_client)
    result = scoring.compute(data)

    summary = None
    if args.summary:
        summary = DeepSeekSummarizer(config, http).summarize(data, result)

    db = DatabaseManager(config.db_path)
    analysis_id = db.save_analysis(
        ticker=ticker,
        metrics_payload=data.to_dict(),
        scores_payload=result.to_dict(),
        company_name=data.company_name,
        cik=data.cik,
        price=data.price,
        currency=data.currency,
    )

    report_path = None
    if not args.no_report:
        # `safe_child_path` revalide le confinement même si `validate_ticker`
        # laissait passer quelque chose : défense en profondeur.
        directory = safe_child_path(config.output_dir, ticker)
        report_path = safe_child_path(config.output_dir, ticker, f"{ticker}_report.html")
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        write_atomic(report_path, generate_html_report(data, result, summary))
        log.info("rapport écrit : %s", report_path)

    if args.notify:
        TelegramNotifier(config, http).send_analysis(data, result)

    if args.json:
        print(
            json.dumps(
                {
                    "analysis_id": analysis_id,
                    "metrics": data.to_dict(),
                    "scores": result.to_dict(),
                    "summary": summary,
                    "report": str(report_path) if report_path else None,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        _print_human(data, result, summary, report_path)

    return EXIT_OK


def _print_human(data, result, summary, report_path) -> None:
    print(f"\n{data.company_name} ({data.ticker})")
    if data.price is not None:
        print(f"  Cours          : {data.price:.2f} {data.currency} ({data.price_source})")
    print(f"  Risque         : {result.risk_score}/100")
    print(f"  Opportunité    : {result.opportunity_score}/100")
    print(f"  Score net      : {result.net_score:+.1f}")
    print(f"  Confiance      : {result.confidence:.0%}")
    print(f"  Recommandation : {result.recommendation}")

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
    for warning in data.warnings:
        print(f"\n  [!] {warning}")
    if summary:
        print(f"\n  Synthèse (générée, non vérifiée) :\n    {summary}")
    if report_path:
        print(f"\n  Rapport : {report_path}")
    print(
        "\n  Aide à la décision automatisée à partir de sources publiques. "
        "Ne constitue pas un conseil en investissement.\n"
    )


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


def cmd_debate(args: argparse.Namespace, config: Config) -> int:
    ticker = validate_ticker(args.ticker)
    http = _make_http(config)
    sec_client = SecClient(http, cache_dir=config.output_dir / ".cache")

    data = metrics_mod.collect(http, ticker, sec_client)
    scores = scoring.compute(data)
    result = MultiModelDebate(config, http).run(data, scores)

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
    print(f"  Score interne : {scores.recommendation} (confiance {scores.confidence:.0%})")
    print(
        "\n  Les verdicts proviennent de modèles de langage : ils peuvent être "
        "erronés ou influencés par le contenu analysé. Le décompte est fait "
        "localement, sans arbitre IA.\n"
    )
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    setup_logging(args.verbose)

    try:
        config = load_config(env_file=args.env_file, output_dir=args.output_dir)
    except ConfigError as exc:
        log.error("configuration invalide : %s", exc)
        return EXIT_CONFIG

    handlers = {"analyze": cmd_analyze, "list": cmd_list, "debate": cmd_debate}
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
