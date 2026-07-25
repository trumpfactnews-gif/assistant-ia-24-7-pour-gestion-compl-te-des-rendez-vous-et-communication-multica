"""OSINT Financial Intelligence — moteur d'analyse financière sur sources publiques.

Réécriture durcie de `osint_v3.py` : validation stricte des entrées, HTTP
contraint (allowlist + timeouts + quotas), sortie HTML échappée, SQL paramétré,
secrets non journalisés, et scoring explicite avec indice de confiance.

Cet outil produit une aide à la décision documentaire. Ce n'est pas un conseil
en investissement.
"""

__version__ = "4.0.0"
__all__ = ["__version__"]
