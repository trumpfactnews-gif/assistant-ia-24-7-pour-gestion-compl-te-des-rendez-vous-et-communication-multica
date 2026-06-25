"""Fixtures partagées pour la suite de tests."""

from __future__ import annotations

import pytest

from sentinelle.app import create_app
from sentinelle.config import Config
from sentinelle.db import Repository


def make_config(tmp_path, **overrides) -> Config:
    """Construit une configuration de test isolée (base et modèle dans tmp)."""
    defaults = dict(
        env="test",
        debug=True,
        database_path=str(tmp_path / "test.db"),
        # Modèle inexistant : le moteur tourne en mode heuristique (déterministe).
        model_path=str(tmp_path / "no-model.joblib"),
        rate_limit_per_minute=0,  # désactive la limitation pendant les tests
        api_key=None,
        community_block_threshold=2,
    )
    defaults.update(overrides)
    cfg = Config(**defaults)
    cfg.ensure_directories()
    return cfg


@pytest.fixture
def config(tmp_path) -> Config:
    return make_config(tmp_path)


@pytest.fixture
def app(config):
    return create_app(config)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def repo(config) -> Repository:
    r = Repository(config.database_path, config.community_block_threshold)
    r.init()
    return r
