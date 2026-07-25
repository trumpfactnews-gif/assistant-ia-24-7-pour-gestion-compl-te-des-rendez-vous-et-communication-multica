"""Orchestration d'une analyse complète.

Regroupe collecte, scoring, backtest, contexte de marché, dimensionnement,
persistance et rapport. La CLI ne fait plus que de la mise en forme : c'est ce
qui rend l'ensemble testable hors ligne, contrairement au ``main()`` d'origine
qui mélangeait réseau, calcul, écriture disque et affichage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import backtest as backtest_mod
from . import macro as macro_mod
from . import metrics as metrics_mod
from . import checklist, portfolio, scoring
from .config import Config
from .database import DatabaseManager
from .errors import OsintError
from .httpclient import HttpClient
from .logging_setup import get_logger
from .metrics import CollectOptions, Metrics
from .report import generate_html_report, write_atomic
from .sources import prices, sec
from .summarizer import DeepSeekSummarizer
from .validation import safe_child_path, validate_ticker

log = get_logger(__name__)


@dataclass
class AnalysisBundle:
    """Tout ce qu'une analyse produit."""

    metrics: Metrics
    scores: scoring.ScoreResult
    backtest: backtest_mod.BacktestResult | None = None
    regime: macro_mod.MarketRegime | None = None
    plan: portfolio.PositionPlan | None = None
    entry: checklist.Checklist | None = None
    exit: checklist.Checklist | None = None
    summary: str | None = None
    report_path: Path | None = None
    analysis_id: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "analysis_id": self.analysis_id,
            "metrics": self.metrics.to_dict(),
            "scores": self.scores.to_dict(),
            "backtest": self.backtest.to_dict() if self.backtest else None,
            "market_regime": self.regime.to_dict() if self.regime else None,
            "position_plan": self.plan.to_dict() if self.plan else None,
            "entry_checklist": self.entry.to_dict() if self.entry else None,
            "exit_checklist": self.exit.to_dict() if self.exit else None,
            "summary": self.summary,
            "report": str(self.report_path) if self.report_path else None,
        }


@dataclass
class AnalysisRequest:
    ticker: str
    collect: CollectOptions = field(default_factory=CollectOptions)
    with_backtest: bool = True
    with_summary: bool = False
    with_report: bool = True
    backtest_horizon: int = backtest_mod.DEFAULT_HORIZON


def run_analysis(
    config: Config,
    http: HttpClient,
    sec_client: sec.SecClient,
    request: AnalysisRequest,
    db: DatabaseManager | None = None,
) -> AnalysisBundle:
    """Exécute la chaîne complète pour un ticker."""
    ticker = validate_ticker(request.ticker)

    data = metrics_mod.collect(http, ticker, sec_client, request.collect)

    regime = None
    if request.collect.macro:
        regime = macro_mod.assess(http)
        data.warnings.extend(regime.warnings)

    result = scoring.compute(data, macro_score=regime.score if regime and regime.available else None)

    backtest_result = None
    if request.with_backtest and request.collect.history:
        backtest_result = _run_backtest(http, ticker, request)

    plan = portfolio.build_plan(
        recommendation=result.recommendation,
        confidence=result.confidence,
        price=data.price,
        volatility_annual_pct=data.technical.volatility_annual_pct if data.technical else None,
    )

    summary = None
    if request.with_summary:
        summary = DeepSeekSummarizer(config, http).summarize(data, result)

    bundle = AnalysisBundle(
        metrics=data,
        scores=result,
        backtest=backtest_result,
        regime=regime,
        plan=plan,
        entry=checklist.entry_checklist(data, result, regime),
        exit=checklist.exit_checklist(data),
        summary=summary,
    )

    if db is not None:
        bundle.analysis_id = db.save_analysis(
            ticker=ticker,
            metrics_payload=data.to_dict(),
            scores_payload=result.to_dict(),
            company_name=data.company_name,
            cik=data.cik,
            price=data.price,
            currency=data.currency,
        )

    if request.with_report:
        # `safe_child_path` revalide le confinement même si `validate_ticker`
        # laissait passer quelque chose : défense en profondeur.
        directory = safe_child_path(config.output_dir, ticker)
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        report_path = safe_child_path(config.output_dir, ticker, f"{ticker}_report.html")
        write_atomic(
            report_path,
            generate_html_report(
                data, result, summary, backtest_result, plan, regime,
                checklists=[bundle.entry, bundle.exit],
            ),
        )
        bundle.report_path = report_path
        log.info("rapport écrit : %s", report_path)

    return bundle


def _run_backtest(
    http: HttpClient, ticker: str, request: AnalysisRequest
) -> backtest_mod.BacktestResult | None:
    """Le backtest exige plus d'historique que l'analyse courante."""
    try:
        series = prices.fetch_history(http, ticker, range_="5y")
    except OsintError as exc:
        log.debug("backtest impossible : %s", exc)
        return None
    return backtest_mod.run(series, horizon=request.backtest_horizon)
