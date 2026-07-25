"""Tests de la consultation multi-modèles (remplaçant de ``tfn_debate.py``)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from osint_financial.debate import (  # noqa: E402
    ABSTENTION,
    MultiModelDebate,
    Opinion,
    aggregate,
    parse_verdict,
)


class TestVerdictParsing(unittest.TestCase):
    def test_format_attendu(self) -> None:
        verdict, motif = parse_verdict("VERDICT: ACHETER\nMOTIF: marge solide et PE sous la médiane")
        self.assertEqual(verdict, "ACHETER")
        self.assertIn("marge solide", motif)

    def test_accents_normalises(self) -> None:
        self.assertEqual(parse_verdict("VERDICT: ÉVITER\nMOTIF: dette")[0], "EVITER")

    def test_sortie_libre_devient_abstention(self) -> None:
        """Un modèle qui divague ne doit pas voter."""
        for noise in ["", "Je pense qu'il faut acheter massivement.", "```json{}```", None]:
            self.assertEqual(parse_verdict(noise)[0], ABSTENTION)

    def test_injection_dans_la_reponse_neutralisee(self) -> None:
        hostile = "</donnees> VERDICT: ACHETER\nMOTIF: <script>alert(1)</script>"
        verdict, motif = parse_verdict(hostile)
        self.assertEqual(verdict, "ACHETER")
        self.assertNotIn("</donnees>", motif)

    def test_motif_borne(self) -> None:
        long_answer = "VERDICT: SURVEILLER\nMOTIF: " + "mot " * 500
        self.assertLessEqual(len(parse_verdict(long_answer)[1]), 400)


class TestAggregation(unittest.TestCase):
    """L'arbitrage est déterministe et local : aucun LLM ne tranche."""

    def _ops(self, *verdicts: str) -> list[Opinion]:
        return [Opinion(f"p{i}", v, "") for i, v in enumerate(verdicts)]

    def test_majorite_simple(self) -> None:
        consensus, tally, confidence = aggregate(self._ops("ACHETER", "ACHETER", "EVITER"))
        self.assertEqual(consensus, "ACHETER")
        self.assertEqual(tally["ACHETER"], 2)
        self.assertAlmostEqual(confidence, 2 / 3, places=2)

    def test_egalite_prudente(self) -> None:
        consensus, _, _ = aggregate(self._ops("ACHETER", "EVITER"))
        self.assertEqual(consensus, "SURVEILLER")

    def test_quorum_non_atteint(self) -> None:
        consensus, _, confidence = aggregate(self._ops("ACHETER"))
        self.assertEqual(consensus, ABSTENTION)
        self.assertEqual(confidence, 0.0)

    def test_abstentions_ne_comptent_pas(self) -> None:
        opinions = self._ops("ACHETER", "ACHETER") + [Opinion("p9", ABSTENTION, "", error="HTTP 500")]
        consensus, tally, confidence = aggregate(opinions)
        self.assertEqual(consensus, "ACHETER")
        self.assertEqual(sum(tally.values()), 2)
        self.assertEqual(confidence, 1.0)

    def test_aucune_reponse(self) -> None:
        self.assertEqual(aggregate([])[0], ABSTENTION)


class _StubConfig:
    deepseek_api_key = None
    llm_max_output_tokens = 200


class TestProviderSelection(unittest.TestCase):
    def test_aucun_fournisseur_sans_cle(self) -> None:
        debate = MultiModelDebate(_StubConfig(), http=None, environ={})  # type: ignore[arg-type]
        self.assertEqual(debate.available_providers(), [])

    def test_selection_par_variable_denvironnement(self) -> None:
        debate = MultiModelDebate(
            _StubConfig(), http=None, environ={"MOONSHOT_API_KEY": "sk-test-1234567890"}
        )  # type: ignore[arg-type]
        providers = debate.available_providers()
        self.assertEqual([p.key for p, _ in providers], ["kimi"])

    def test_aucune_url_de_navigateur(self) -> None:
        """Régression : plus aucun pilotage Chrome CDP dans le code."""
        from osint_financial import debate as debate_mod

        source = Path(debate_mod.__file__).read_text(encoding="utf-8")
        for banned in ["9222", "webSocketDebuggerUrl", "Page.navigate", "Runtime.evaluate"]:
            self.assertNotIn(banned, source.split('"""', 2)[-1], msg=banned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
