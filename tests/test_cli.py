"""Tests de bout en bout de la CLI (generate → analyze → exports)."""

import json

import pytest

from predopt.cli import main


def test_generate_then_analyze(tmp_path, capsys):
    markets_file = tmp_path / "markets.json"
    assert main(["generate", "--markets", "30", "--seed", "5", "--out", str(markets_file)]) == 0
    assert markets_file.exists()

    json_out = tmp_path / "result.json"
    csv_out = tmp_path / "result.csv"
    rc = main([
        "analyze", str(markets_file),
        "--max-legs", "3", "--top", "10",
        "--objective", "sharpe",
        "--bankroll", "1000",
        "--json", str(json_out),
        "--csv", str(csv_out),
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "jambes candidates" in out
    assert "P(gain)" in out
    assert "Mise" in out

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    assert payload["combos"]
    assert payload["stats"]["space_size"] > 0
    first = payload["combos"][0]
    assert first["rank"] == 1
    assert "stake" in first

    csv_text = csv_out.read_text(encoding="utf-8")
    assert csv_text.splitlines()[0].startswith("rank,")
    assert len(csv_text.splitlines()) == len(payload["combos"]) + 1


def test_analyze_no_legs_after_filter(tmp_path, capsys):
    markets_file = tmp_path / "markets.json"
    main(["generate", "--markets", "5", "--seed", "1", "--out", str(markets_file)])
    rc = main(["analyze", str(markets_file), "--min-leg-ev", "10.0"])
    assert rc == 1
    assert "Aucune jambe" in capsys.readouterr().out


def test_bench_smoke(capsys):
    rc = main(["bench", "--markets", "40", "--legs", "3", "--top", "10"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Espace de recherche" in out
    assert "Meilleur combiné" in out
