from datetime import date

from pydantic import BaseModel


class DomaineBase(BaseModel):
    libelle: str
    description: str | None = None


class DomaineCreate(DomaineBase):
    pass


class DomaineResponse(DomaineBase):
    id: int

    model_config = {"from_attributes": True}


class SecteurActiviteBase(BaseModel):
    nom: str
    description: str | None = None


class SecteurActiviteResponse(SecteurActiviteBase):
    id: int

    model_config = {"from_attributes": True}


class EntrepriseResponse(BaseModel):
    id: int
    nom: str
    numero_identification: str
    adresse: str | None
    telephone: str | None
    email: str | None
    date_creation: date | None
    description: str | None
    repnom: str | None
    repprenom: str | None
    rccm: str
    domaines: list[DomaineResponse]
    secteurs: list[SecteurActiviteResponse]

    model_config = {"from_attributes": True}


class EntrepriseCreateUpdateRequest(BaseModel):
    nom: str | None = None
    numero_identification: str | None = None
    adresse: str | None = None
    telephone: str | None = None
    email: str | None = None
    date_creation: date | None = None
    description: str | None = None
    repnom: str | None = None
    repprenom: str | None = None
    rccm: str | None = None
    domaine_ids: list[int] = []
    secteur_ids: list[int] = []


class SetActiveEntrepriseRequest(BaseModel):
    entreprise_id: int | None = None
