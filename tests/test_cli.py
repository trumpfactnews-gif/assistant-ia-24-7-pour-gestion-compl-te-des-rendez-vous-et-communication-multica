"""Tests de l'orchestration et de la ligne de commande, hors ligne."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fixtures import FakeHttp, chart_payload, full_routes, trending_closes  # noqa: E402

from osint_financial import cli  # noqa: E402
from osint_financial.config import load_config  # noqa: E402
from osint_financial.database import DatabaseManager  # noqa: E402
from osint_financial.metrics import CollectOptions  # noqa: E402
from osint_financial.pipeline import AnalysisRequest, run_analysis  # noqa: E402
from osint_financial.sources.sec import SecClient  # noqa: E402

OUT = Path("/tmp/osint-cli")


def make_config(output_dir: Path = OUT):
    return load_config(
        env_file=None,
        output_dir=output_dir,
        environ={"SEC_USER_AGENT": "Tests OSINT tests@example.com"},
    )


def routes_with_macro() -> dict[str, object]:
    routes = dict(full_routes())
    index = chart_payload(trending_closes(400))
    routes["%5EGSPC"] = index
    routes["%5EVIX"] = chart_payload([13.0] * 300)
    routes["%5ETNX"] = chart_payload(trending_closes(300, drift=-0.0005))
    # Les symboles d'indice doivent être testés avant la route générique.
    return {k: routes[k] for k in ["%5EGSPC", "%5EVIX", "%5ETNX", *full_routes()]}


class TestRunAnalysis(unittest.TestCase):
    def setUp(self) -> None:
        self.config = make_config()
        self.http = FakeHttp(routes_with_macro())
        self.sec = SecClient(self.http)  # type: ignore[arg-type]

    def test_chaine_complete(self) -> None:
        db = DatabaseManager(OUT / "db.sqlite")
        bundle = run_analysis(
            self.config, self.http, self.sec,  # type: ignore[arg-type]
            AnalysisRequest(ticker="AAPL"), db,
        )

        self.assertIsNotNone(bundle.analysis_id)
        self.assertIsNotNone(bundle.report_path)
        self.assertTrue(bundle.report_path.is_file())
        self.assertIsNotNone(bundle.regime)
        self.assertTrue(bundle.regime.available)
        self.assertIsNotNone(bundle.plan)
        self.assertIsNotNone(bundle.backtest)
        self.assertGreater(bundle.backtest.total_observations, 100)
        self.assertIsNotNone(bundle.scores.resilience_score)

        payload = bundle.to_dict()
        for key in ("metrics", "scores", "backtest", "market_regime", "position_plan"):
            self.assertIn(key, payload)

    def test_rapport_contient_les_nouvelles_sections(self) -> None:
        bundle = run_analysis(
            self.config, self.http, self.sec,  # type: ignore[arg-type]
            AnalysisRequest(ticker="AAPL"),
        )
        html = bundle.report_path.read_text(encoding="utf-8")
        for section in (
            "Analyse technique",
            "Valorisation par les flux",
            "Transactions d'initiés",
            "Contexte de marché",
            "Dimensionnement et cadre d'allocation",
            "Ce que vaut ce signal",
        ):
            self.assertIn(section, html, msg=section)

    def test_options_reduisent_le_perimetre(self) -> None:
        request = AnalysisRequest(
            ticker="AAPL",
            collect=CollectOptions(history=False, insiders=False, macro=False),
            with_backtest=False,
            with_report=False,
        )
        bundle = run_analysis(self.config, self.http, self.sec, request)  # type: ignore[arg-type]
        self.assertIsNone(bundle.report_path)
        self.assertIsNone(bundle.regime)
        self.assertIsNone(bundle.backtest)
        self.assertIsNone(bundle.metrics.technical)


class TestWatchMode(unittest.TestCase):
    """`--watch` : documenté dans le guide d'origine, absent du code."""

    def _args(self, **overrides):
        parser = cli.build_parser()
        argv = ["watch", "--ticker", "AAPL", "--interval", "60", "--max-iterations", "2"]
        args = parser.parse_args(argv)
        for key, value in overrides.items():
            setattr(args, key, value)
        return args

    def test_sarrete_apres_max_iterations(self) -> None:
        http = FakeHttp(routes_with_macro())
        printed: list[str] = []
        with mock.patch.object(cli, "_make_http", return_value=http), mock.patch.object(
            cli.time, "sleep"
        ), mock.patch("builtins.print", side_effect=lambda *a, **k: printed.append(" ".join(map(str, a)))):
            code = cli.cmd_watch(self._args(), make_config(OUT / "watch"))
        self.assertEqual(code, cli.EXIT_OK)
        self.assertEqual(len(printed), 2)

    def test_intervalle_borne(self) -> None:
        http = FakeHttp(routes_with_macro())
        args = self._args(interval=1, max_iterations=1)
        with mock.patch.object(cli, "_make_http", return_value=http), mock.patch.object(
            cli.time, "sleep"
        ), mock.patch("builtins.print"):
            self.assertEqual(cli.cmd_watch(args, make_config(OUT / "watch")), cli.EXIT_OK)

    def test_panne_transitoire_ne_termine_pas_la_surveillance(self) -> None:
        """Une itération en échec est journalisée, la boucle continue."""
        http = FakeHttp({})  # aucune route : tout échoue
        with mock.patch.object(cli, "_make_http", return_value=http), mock.patch.object(
            cli.time, "sleep"
        ), mock.patch("builtins.print"):
            code = cli.cmd_watch(self._args(max_iterations=3), make_config(OUT / "watch"))
        self.assertEqual(code, cli.EXIT_OK)


class TestParser(unittest.TestCase):
    def test_sous_commandes_disponibles(self) -> None:
        parser = cli.build_parser()
        for command in ("analyze", "watch", "list", "backtest", "debate"):
            args = parser.parse_args([command, "--ticker", "AAPL"] if command != "list" else [command])
            self.assertEqual(args.command, command)

    def test_liste_de_comparables(self) -> None:
        args = cli.build_parser().parse_args(
            ["analyze", "--ticker", "AAPL", "--peers", "MSFT, GOOGL ,META"]
        )
        self.assertEqual(args.peers, ("MSFT", "GOOGL", "META"))

    def test_commande_obligatoire(self) -> None:
        with self.assertRaises(SystemExit):
            cli.build_parser().parse_args([])

    def test_ticker_invalide_donne_le_code_2(self) -> None:
        env = {"SEC_USER_AGENT": "Tests OSINT tests@example.com", "OSINT_OUTPUT_DIR": str(OUT)}
        with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(cli, "_make_http"):
            self.assertEqual(cli.main(["analyze", "--ticker", "../../etc/passwd"]), cli.EXIT_USAGE)

    def test_configuration_manquante_donne_le_code_3(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cli.main(["list"]), cli.EXIT_CONFIG)


if __name__ == "__main__":
    unittest.main(verbosity=2)
