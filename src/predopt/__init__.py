"""predopt — Optimiseur de paris pour marchés prédictifs décentralisés.

Pipeline : marchés (prix) → dé-vig → probabilités pondérées (modèle,
historique) → jambes → moteur combinatoire branch-and-bound → classement
par EV / Sharpe / croissance log / probabilité, avec mises Kelly.
"""

from .data import generate_sample_markets, load_markets, markets_to_legs, save_markets
from .engine import CombinationEngine, SearchStats, search_space_size
from .metrics import (
    build_combo,
    combo_score,
    expected_log_growth,
    expected_value,
    kelly_fraction,
    sharpe_ratio,
    variance,
)
from .models import Combo, Leg, Market, MarketType, Outcome
from .probability import (
    beta_shrink,
    blend_log_odds,
    correlation_haircut,
    devig,
    devig_power,
    devig_proportional,
    estimate_outcome_prob,
    overround,
)

__version__ = "1.0.0"

__all__ = [
    "CombinationEngine",
    "SearchStats",
    "search_space_size",
    "Market",
    "MarketType",
    "Outcome",
    "Leg",
    "Combo",
    "load_markets",
    "save_markets",
    "markets_to_legs",
    "generate_sample_markets",
    "build_combo",
    "combo_score",
    "expected_value",
    "variance",
    "sharpe_ratio",
    "kelly_fraction",
    "expected_log_growth",
    "devig",
    "devig_power",
    "devig_proportional",
    "overround",
    "beta_shrink",
    "blend_log_odds",
    "estimate_outcome_prob",
    "correlation_haircut",
]
