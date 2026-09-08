"""Module de commodité et rétrocompatibilité pour importer les modèles de résultats d'attribution.

Permet à la fois :
from api.models.resultats_attribution import SoumissionnaireResultat, ResultatAttribution, LotResultat, AlerteResultat
et
from api.models.resultat import SoumissionnaireResultat, ResultatAttribution, LotResultat, AlerteResultat
"""

from api.models.resultats_attribution import (
    AlerteResultat,
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)

__all__ = [
    "AlerteResultat",
    "LotResultat",
    "ResultatAttribution",
    "SoumissionnaireResultat",
]
