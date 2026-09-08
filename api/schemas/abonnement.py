from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AbonnementResponse(BaseModel):
    statut: str
    date_debut_essai: datetime
    date_fin_essai: datetime
    date_fin_abonnement: datetime | None
    jours_restants: int

    model_config = {"from_attributes": True}


class InitierPaiementRequest(BaseModel):
    entreprise_id: int


class InitierPaiementResponse(BaseModel):
    url: str


class TarifResponse(BaseModel):
    prix_annuel: Decimal
    devise: str
    essai_gratuit_jours: int

    model_config = {"from_attributes": True}
