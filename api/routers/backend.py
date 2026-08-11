"""Routes de l'app 'backend' Django (marches publics) - reproduit backend/urls.py, monte sous
/api/backend/api/ (double segment "api" : quirk de l'original conserve, cf. plan)."""

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import get_db
from api.config import settings
from api.minio_client import build_presign_client
from api.models.backend import Alerte, AppelOffre, Lot, Marche, Publication, Resultat, TypeProcedure
from api.models.entreprise import Domaine, Entreprise
from api.models.utilisateur import Utilisateur
from api.schemas.backend import (
    AlerteCreateUpdateRequest,
    AlerteResponse,
    AppelOffreCreateUpdateRequest,
    AppelOffreResponse,
    LotCreateUpdateRequest,
    LotResponse,
    MarcheCreateUpdateRequest,
    MarcheResponse,
    PublicationCreateUpdateRequest,
    PublicationResponse,
    ResultatCreateUpdateRequest,
    ResultatResponse,
    TypeProcedureCreateUpdateRequest,
    TypeProcedureResponse,
)
from api.schemas.entreprise import DomaineCreate, DomaineResponse
from api.security import get_current_user

router = APIRouter(prefix="/api/backend/api", dependencies=[Depends(get_current_user)])


def require_staff(current_user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    if not (current_user.is_staff or current_user.is_superuser):
        raise HTTPException(status_code=403, detail="Vous n'avez pas la permission d'effectuer cette action.")
    return current_user


def _get_or_404(db: Session, model, object_id: int):
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return obj


# --- publications ------------------------------------------------------------------------------


@router.get("/publications/", response_model=list[PublicationResponse])
def list_publications(db: Session = Depends(get_db)):
    return db.scalars(select(Publication).order_by(Publication.date_publication.desc())).all()


@router.post("/publications/", response_model=PublicationResponse, status_code=201)
def create_publication(
    payload: PublicationCreateUpdateRequest, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    publication = Publication(
        titre=payload.titre,
        numero=payload.numero,
        date_publication=payload.date_publication,
        source=payload.source,
        source_url=payload.source_url,
        type_publication=payload.type_publication,
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return publication


@router.get("/publications/{publication_id}/", response_model=PublicationResponse)
def get_publication(publication_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Publication, publication_id)


@router.delete("/publications/{publication_id}/", status_code=204)
def delete_publication(
    publication_id: int, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    db.delete(_get_or_404(db, Publication, publication_id))
    db.commit()


@router.get("/publications/{publication_id}/pdf-url/")
def get_publication_pdf_url(publication_id: int, db: Session = Depends(get_db)):
    publication = _get_or_404(db, Publication, publication_id)
    # cle MinIO deterministe a partir du numero de bulletin - meme convention que
    # ingestion/scrape_and_upload.py (_object_name) et api/scripts/match_and_alert.py (sens inverse).
    object_name = f"pdf/quotidien/{publication.numero}.pdf"
    client = build_presign_client()
    url = client.presigned_get_object(settings.minio_bucket, object_name, expires=timedelta(minutes=15))
    return {"url": url}


# --- types-procedure (reserve aux admins, IsAdminUser dans l'original) --------------------------


@router.get("/types-procedure/", response_model=list[TypeProcedureResponse])
def list_types_procedure(db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)):
    return db.scalars(select(TypeProcedure)).all()


@router.post("/types-procedure/", response_model=TypeProcedureResponse, status_code=201)
def create_type_procedure(
    payload: TypeProcedureCreateUpdateRequest, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    type_procedure = TypeProcedure(libelle=payload.libelle, description=payload.description)
    db.add(type_procedure)
    db.commit()
    db.refresh(type_procedure)
    return type_procedure


@router.get("/types-procedure/{type_procedure_id}/", response_model=TypeProcedureResponse)
def get_type_procedure(type_procedure_id: int, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)):
    return _get_or_404(db, TypeProcedure, type_procedure_id)


@router.delete("/types-procedure/{type_procedure_id}/", status_code=204)
def delete_type_procedure(
    type_procedure_id: int, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    db.delete(_get_or_404(db, TypeProcedure, type_procedure_id))
    db.commit()


# --- marches -------------------------------------------------------------------------------------


@router.get("/marches/", response_model=list[MarcheResponse])
def list_marches(db: Session = Depends(get_db)):
    return db.scalars(select(Marche)).all()


@router.post("/marches/", response_model=MarcheResponse, status_code=201)
def create_marche(
    payload: MarcheCreateUpdateRequest, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    marche = Marche(
        publication_id=payload.publication_id,
        type_procedure_id=payload.type_procedure_id,
        ministere=payload.ministere,
        region=payload.region,
        objet=payload.objet,
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
    )
    db.add(marche)
    db.commit()
    db.refresh(marche)
    return marche


@router.get("/marches/{marche_id}/", response_model=MarcheResponse)
def get_marche(marche_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Marche, marche_id)


@router.delete("/marches/{marche_id}/", status_code=204)
def delete_marche(marche_id: int, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)):
    db.delete(_get_or_404(db, Marche, marche_id))
    db.commit()


# --- appels-offres (heritage multi-table : cree d'abord le Marche, puis l'extension) ------------


def _to_appel_offre_response(appel_offre: AppelOffre) -> AppelOffreResponse:
    # AppelOffreResponse etend MarcheResponse (parite avec l'heritage multi-table Django d'origine :
    # AppelOffre "est" un Marche) mais AppelOffre lui-meme ne porte que les champs d'extension - les
    # champs de Marche doivent etre lus via la relation .marche et assembles explicitement, jamais
    # renvoyes tel quel (AppelOffreResponse(from_attributes=True) sur l'objet AppelOffre brut echoue :
    # id/publication/objet/... n'existent pas directement dessus).
    return AppelOffreResponse(
        id=appel_offre.marche.id,
        publication=appel_offre.marche.publication,
        type_procedure=appel_offre.marche.type_procedure,
        ministere=appel_offre.marche.ministere,
        region=appel_offre.marche.region,
        objet=appel_offre.marche.objet,
        budget_min=appel_offre.marche.budget_min,
        budget_max=appel_offre.marche.budget_max,
        page_number=appel_offre.marche.page_number,
        lots=appel_offre.marche.lots,
        dateDepot=appel_offre.dateDepot,
        referenceDossier=appel_offre.referenceDossier,
        lieuDepot=appel_offre.lieuDepot,
        conditionsParticipation=appel_offre.conditionsParticipation,
        criteresSelection=appel_offre.criteresSelection,
        cautionnement=appel_offre.cautionnement,
        dureeValiditeOffres=appel_offre.dureeValiditeOffres,
    )


@router.get("/appels-offres/", response_model=list[AppelOffreResponse])
def list_appels_offres(db: Session = Depends(get_db)):
    return [_to_appel_offre_response(ao) for ao in db.scalars(select(AppelOffre)).all()]


@router.post("/appels-offres/", response_model=AppelOffreResponse, status_code=201)
def create_appel_offre(
    payload: AppelOffreCreateUpdateRequest, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    marche = Marche(
        publication_id=payload.publication_id,
        type_procedure_id=payload.type_procedure_id,
        ministere=payload.ministere,
        region=payload.region,
        objet=payload.objet,
        budget_min=payload.budget_min,
        budget_max=payload.budget_max,
    )
    db.add(marche)
    db.commit()
    db.refresh(marche)

    appel_offre = AppelOffre(
        marche_id=marche.id,
        dateDepot=payload.dateDepot,
        referenceDossier=payload.referenceDossier,
        lieuDepot=payload.lieuDepot,
        conditionsParticipation=payload.conditionsParticipation,
        criteresSelection=payload.criteresSelection,
        cautionnement=payload.cautionnement,
        dureeValiditeOffres=payload.dureeValiditeOffres,
    )
    db.add(appel_offre)
    db.commit()
    db.refresh(appel_offre)
    return _to_appel_offre_response(appel_offre)


@router.get("/appels-offres/{marche_id}/", response_model=AppelOffreResponse)
def get_appel_offre(marche_id: int, db: Session = Depends(get_db)):
    return _to_appel_offre_response(_get_or_404(db, AppelOffre, marche_id))


@router.delete("/appels-offres/{marche_id}/", status_code=204)
def delete_appel_offre(
    marche_id: int, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    appel_offre = _get_or_404(db, AppelOffre, marche_id)
    db.delete(appel_offre)
    db.delete(_get_or_404(db, Marche, marche_id))
    db.commit()


# --- resultats -------------------------------------------------------------------------------------


@router.get("/resultats/", response_model=list[ResultatResponse])
def list_resultats(db: Session = Depends(get_db)):
    return db.scalars(select(Resultat)).all()


@router.post("/resultats/", response_model=ResultatResponse, status_code=201)
def create_resultat(
    payload: ResultatCreateUpdateRequest, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    resultat = Resultat(
        marche_id=payload.marche_id,
        date_attribution=payload.date_attribution,
        entreprise_attributaire_nom=payload.entreprise_attributaire_nom,
        entreprise_attributaire_id=payload.entreprise_attributaire_id,
        montant_attribue=payload.montant_attribue,
        reference_decision=payload.reference_decision,
        nombre_offres_recues=payload.nombre_offres_recues,
        delai_execution=payload.delai_execution,
        motif_rejet_autres_offres=payload.motif_rejet_autres_offres,
    )
    db.add(resultat)
    db.commit()
    db.refresh(resultat)
    return resultat


@router.get("/resultats/{marche_id}/", response_model=ResultatResponse)
def get_resultat(marche_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Resultat, marche_id)


@router.delete("/resultats/{marche_id}/", status_code=204)
def delete_resultat(marche_id: int, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)):
    db.delete(_get_or_404(db, Resultat, marche_id))
    db.commit()


# --- lots -------------------------------------------------------------------------------------


@router.get("/lots/", response_model=list[LotResponse])
def list_lots(db: Session = Depends(get_db)):
    return db.scalars(select(Lot)).all()


@router.post("/lots/", response_model=LotResponse, status_code=201)
def create_lot(
    payload: LotCreateUpdateRequest, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    lot = Lot(
        marche_id=payload.marche_id,
        numero_lot=payload.numero_lot,
        description=payload.description,
        montant=payload.montant,
    )
    db.add(lot)
    db.commit()
    db.refresh(lot)
    return lot


@router.get("/lots/{lot_id}/", response_model=LotResponse)
def get_lot(lot_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, Lot, lot_id)


@router.delete("/lots/{lot_id}/", status_code=204)
def delete_lot(lot_id: int, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)):
    db.delete(_get_or_404(db, Lot, lot_id))
    db.commit()


# --- domaines (meme table que /api/entreprise/domaines/, endpoint distinct comme l'original) ----


@router.get("/domaines/", response_model=list[DomaineResponse])
def list_domaines_backend(db: Session = Depends(get_db)):
    return db.scalars(select(Domaine)).all()


@router.post("/domaines/", response_model=DomaineResponse, status_code=201)
def create_domaine_backend(
    payload: DomaineCreate, db: Session = Depends(get_db), _: Utilisateur = Depends(require_staff)
):
    domaine = Domaine(libelle=payload.libelle, description=payload.description)
    db.add(domaine)
    db.commit()
    db.refresh(domaine)
    return domaine



# --- alertes (scope : uniquement celles des entreprises de l'utilisateur connecte - une alerte
# expose le detail d'une mise en relation entreprise <-> marche, donnee privee, contrairement aux
# publications/marches/resultats qui sont des donnees publiques de marches publics) -----------


def _alertes_query(current_user: Utilisateur):
    return select(Alerte).join(Entreprise, Alerte.entreprise_id == Entreprise.id).where(
        Entreprise.owner_id == current_user.id
    )


def _get_owned_alerte_or_404(db: Session, current_user: Utilisateur, alerte_id: int) -> Alerte:
    alerte = db.scalar(_alertes_query(current_user).where(Alerte.id == alerte_id))
    if alerte is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return alerte


@router.get("/alertes/", response_model=list[AlerteResponse])
def list_alertes(current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(_alertes_query(current_user)).all()


@router.post("/alertes/", response_model=AlerteResponse, status_code=201)
def create_alerte(
    payload: AlerteCreateUpdateRequest,
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entreprise = db.scalar(
        select(Entreprise).where(Entreprise.id == payload.entreprise_id, Entreprise.owner_id == current_user.id)
    )
    if entreprise is None:
        raise HTTPException(status_code=404, detail="Not found.")
    alerte = Alerte(
        entreprise_id=payload.entreprise_id,
        publication_id=payload.publication_id,
        marche_id=payload.marche_id,
        type_alerte=payload.type_alerte,
        date_alerte=payload.date_alerte,
        contenu_alerte=payload.contenu_alerte,
        canal_alerte=payload.canal_alerte,
    )
    db.add(alerte)
    db.commit()
    db.refresh(alerte)
    return alerte


@router.post("/alertes/marquer-lues/", status_code=204)
def marquer_alertes_lues(current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)):
    # Marquage a l'ouverture : appele par le frontend quand l'utilisateur consulte l'ecran
    # "Alertes & Resultats" - toutes les alertes non lues de ses entreprises passent a lu=True en
    # une fois (pas de marquage alerte par alerte, l'ecran les affiche toutes simultanement).
    for alerte in db.scalars(_alertes_query(current_user).where(Alerte.lu.is_(False))):
        alerte.lu = True
    db.commit()


@router.get("/alertes/{alerte_id}/", response_model=AlerteResponse)
def get_alerte(alerte_id: int, current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_owned_alerte_or_404(db, current_user, alerte_id)


@router.delete("/alertes/{alerte_id}/", status_code=204)
def delete_alerte(
    alerte_id: int, current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)
):
    db.delete(_get_owned_alerte_or_404(db, current_user, alerte_id))
    db.commit()
