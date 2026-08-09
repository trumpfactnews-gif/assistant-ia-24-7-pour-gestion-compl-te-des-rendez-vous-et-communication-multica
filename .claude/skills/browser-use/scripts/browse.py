#!/usr/bin/env python3
"""Lanceur minimal pour parcourir Internet avec browser-use.

Usage:
    python browse.py "Va sur example.com et donne-moi le titre de la page"

Prérequis:
    pip install browser-use  (Python >= 3.11)
    Une clé LLM dans .env, p.ex. ANTHROPIC_API_KEY=...

Variables d'environnement optionnelles:
    BU_MODEL          modèle LLM (défaut: claude-sonnet-4-6)
    BU_HEADLESS       "0" pour afficher le navigateur (défaut: headless)
    BU_MAX_STEPS      nombre max d'étapes de l'agent (défaut: 25)
    CHROMIUM_PATH     chemin du binaire Chromium (utile en environnement
                      Claude Code web: /opt/pw-browsers/chromium)
"""

import asyncio
import os
import sys


async def run(task: str) -> None:
    from browser_use import Agent, Browser, ChatAnthropic

    model = os.environ.get("BU_MODEL", "claude-sonnet-4-6")
    headless = os.environ.get("BU_HEADLESS", "1") != "0"
    max_steps = int(os.environ.get("BU_MAX_STEPS", "25"))

    browser_kwargs = {"headless": headless}
    chromium_path = os.environ.get("CHROMIUM_PATH")
    if chromium_path:
        # Certains environnements (Claude Code web) fournissent Chromium
        # à un chemin fixe; on l'utilise plutôt que de le retélécharger.
        browser_kwargs["executable_path"] = chromium_path

    agent = Agent(
        task=task,
        llm=ChatAnthropic(model=model, temperature=0.0),
        browser=Browser(**browser_kwargs),
    )
    history = await agent.run(max_steps=max_steps)

    print("\n=== Résultat ===")
    print(history.final_result())


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    task = " ".join(sys.argv[1:])
    try:
        asyncio.run(run(task))
    except ImportError:
        print(
            "browser-use n'est pas installé. Lance:  pip install browser-use\n"
            "(Python >= 3.11 requis).",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
