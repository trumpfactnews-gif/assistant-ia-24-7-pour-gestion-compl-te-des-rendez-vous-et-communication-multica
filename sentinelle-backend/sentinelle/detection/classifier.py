"""Classifieur d'apprentissage automatique (enveloppe).

Charge un modèle scikit-learn sérialisé (TF-IDF + régression logistique) entraîné
par `sentinelle/ml/train.py`. S'il n'existe pas, le moteur fonctionne quand même
(heuristiques + URL + communauté) : le composant ML est simplement neutre.

Cette dégradation gracieuse est volontaire : on ne veut jamais que l'absence de
modèle empêche la protection de base de fonctionner.
"""

from __future__ import annotations

import logging
import os
from threading import Lock

logger = logging.getLogger(__name__)


class FraudClassifier:
    """Enveloppe paresseuse autour d'un pipeline scikit-learn."""

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None
        self._loaded = False
        self._lock = Lock()

    @property
    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._model is not None

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            if not os.path.exists(self.model_path):
                logger.info(
                    "Aucun modèle ML à %s — fonctionnement en mode heuristique seul.",
                    self.model_path,
                )
                return
            try:
                import joblib  # import différé : dépendance optionnelle au runtime

                self._model = joblib.load(self.model_path)
                logger.info("Modèle ML chargé depuis %s", self.model_path)
            except Exception as exc:  # pragma: no cover - défensif
                logger.warning("Échec du chargement du modèle ML (%s) : %s",
                               self.model_path, exc)
                self._model = None

    def predict_proba(self, text: str) -> float | None:
        """Probabilité que `text` soit frauduleux (0..1), ou None si indisponible."""
        self._ensure_loaded()
        if self._model is None or not text or not text.strip():
            return None
        try:
            proba = self._model.predict_proba([text])[0]
            # La classe positive (« fraude ») est étiquetée 1 à l'entraînement.
            classes = list(getattr(self._model, "classes_", [0, 1]))
            idx = classes.index(1) if 1 in classes else len(proba) - 1
            return float(proba[idx])
        except Exception as exc:  # pragma: no cover - défensif
            logger.warning("Échec de prédiction ML : %s", exc)
            return None

    def reload(self) -> None:
        """Force le rechargement (utile après un réentraînement)."""
        with self._lock:
            self._model = None
            self._loaded = False
