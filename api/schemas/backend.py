from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel

from api.schemas.entreprise import DomaineResponse, EntrepriseResponse


class TypeProcedureResponse(BaseModel):
    id: int
    libelle: str

    model_config = {"from_attributes": True}


class TypeProcedureCreateUpdateRequest(BaseModel):
    libelle: str | None = None
    description: str | None = None


class PublicationResponse(BaseModel):
    id: int
    titre: str
    numero: str
    date_publication: date
    source: str
    type_publication: str | None
    domaines: list[DomaineResponse]

    model_config = {"from_attributes": True}


class PublicationCreateUpdateRequest(BaseModel):
    titre: str | None = None
    numero: str | None = None
    date_publication: date | None = None
    source: str | None = None
    source_url: str | None = None
    type_publication: str | None = None
    domaine_ids: list[int] = []


class LotResponse(BaseModel):
    id: int
    marche_id: int
    numero_lot: int
    description: str | None
    montant: Decimal | None

    model_config = {"from_attributes": True}


class LotCreateUpdateRequest(BaseModel):
    marche_id: int | None = None
    numero_lot: int | None = None
    description: str | None = None
    montant: Decimal | None = None


class MarcheResponse(BaseModel):
    id: int
    publication: PublicationResponse
    type_procedure: TypeProcedureResponse | None
    ministere: str | None
    region: str | None
    objet: str
    budget_min: Decimal | None
    budget_max: Decimal | None
    lots: list[LotResponse]

    model_config = {"from_attributes": True}


class MarcheCreateUpdateRequest(BaseModel):
    publication_id: int | None = None
    type_procedure_id: int | None = None
    ministere: str | None = None
    region: str | None = None
    objet: str | None = None
    budget_min: Decimal | None = None
    budget_max: Decimal | None = None


class AppelOffreResponse(MarcheResponse):
    dateDepot: date | None
    referenceDossier: str | None
    lieuDepot: str | None
    conditionsParticipation: str | None
    criteresSelection: str | None
    cautionnement: Decimal | None
    dureeValiditeOffres: str | None


class AppelOffreCreateUpdateRequest(MarcheCreateUpdateRequest):
    dateDepot: date | None = None
    referenceDossier: str | None = None
    lieuDepot: str | None = None
    conditionsParticipation: str | None = None
    criteresSelection: str | None = None
    cautionnement: Decimal | None = None
    dureeValiditeOffres: str | None = None


class ResultatResponse(BaseModel):
    marche: MarcheResponse
    date_attribution: date | None
    entreprise_attributaire: EntrepriseResponse | None
    montant_attribue: Decimal | None
    reference_decision: str | None
    nombre_offres_recues: int | None
    delai_execution: str | None
    motif_rejet_autres_offres: str | None

    model_config = {"from_attributes": True}


class ResultatCreateUpdateRequest(BaseModel):
    marche_id: int | None = None
    date_attribution: date | None = None
    entreprise_attributaire_id: int | None = None
    montant_attribue: Decimal | None = None
    reference_decision: str | None = None
    nombre_offres_recues: int | None = None
    delai_execution: str | None = None
    motif_rejet_autres_offres: str | None = None


class PublicationDomaineResponse(BaseModel):
    id: int
    publication_id: int
    domaine_id: int

    model_config = {"from_attributes": True}


class PublicationDomaineCreateUpdateRequest(BaseModel):
    publication_id: int | None = None
    domaine_id: int | None = None


class AlerteResponse(BaseModel):
    id: int
    entreprise: EntrepriseResponse
    publication: PublicationResponse
    type_alerte: str
    date_alerte: datetime
    contenu_alerte: str
    canal_alerte: str

    model_config = {"from_attributes": True}


class AlerteCreateUpdateRequest(BaseModel):
    entreprise_id: int | None = None
    publication_id: int | None = None
    type_alerte: str | None = None
    date_alerte: datetime | None = None
    contenu_alerte: str | None = None
    canal_alerte: str | None = None
