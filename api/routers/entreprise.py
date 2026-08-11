"""Routes du module Entreprise - reproduit entreprise/urls.py (prefixe /api/entreprise/), toutes
les routes necessitent une authentification (IsAuthenticated dans l'original)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.database import get_db
from api.models.abonnement import Abonnement
from api.models.entreprise import Domaine, Entreprise, EntrepriseDomaine, EntrepriseSecteur, SecteurActivite
from api.models.tarif import get_tarif
from api.models.utilisateur import Utilisateur
from api.schemas.entreprise import (
    DomaineCreate,
    DomaineResponse,
    EntrepriseCreateUpdateRequest,
    EntrepriseResponse,
    SecteurActiviteBase,
    SecteurActiviteResponse,
    SetActiveEntrepriseRequest,
)
from api.security import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])


# --- /api/entreprise/domaines/ ----------------------------------------------------------------


@router.get("/api/entreprise/domaines/", response_model=list[DomaineResponse])
def list_domaines(db: Session = Depends(get_db)):
    return db.scalars(select(Domaine)).all()


@router.post("/api/entreprise/domaines/", response_model=DomaineResponse, status_code=201)
def create_domaine(payload: DomaineCreate, db: Session = Depends(get_db)):
    # Meme validation que create_secteur : necessaire depuis que le formulaire entreprise permet
    # d'ajouter un domaine par saisie libre en plus des cases a cocher (une entree en doublon ou
    # vide y est possible, alors qu'un unique(libelle) DB brut renverrait une IntegrityError 500
    # non geree plutot qu'un message exploitable par le frontend).
    libelle = (payload.libelle or "").strip()
    if not libelle:
        return JSONResponse(status_code=400, content={"detail": "Le libellé du domaine est obligatoire."})
    existant = db.scalar(select(Domaine).where(Domaine.libelle.ilike(libelle)))
    if existant is not None:
        return existant
    domaine = Domaine(libelle=libelle, description=(payload.description or "").strip() or None)
    db.add(domaine)
    db.commit()
    db.refresh(domaine)
    return domaine


@router.get("/api/entreprise/domaines/{domaine_id}/", response_model=DomaineResponse)
def get_domaine(domaine_id: int, db: Session = Depends(get_db)):
    domaine = db.get(Domaine, domaine_id)
    if domaine is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return domaine


@router.delete("/api/entreprise/domaines/{domaine_id}/", status_code=204)
def delete_domaine(domaine_id: int, db: Session = Depends(get_db)):
    domaine = db.get(Domaine, domaine_id)
    if domaine is None:
        raise HTTPException(status_code=404, detail="Not found.")
    db.delete(domaine)
    db.commit()


# --- /api/entreprise/secteurs/ ----------------------------------------------------------------


@router.get("/api/entreprise/secteurs/", response_model=list[SecteurActiviteResponse])
def list_secteurs(db: Session = Depends(get_db)):
    return db.scalars(select(SecteurActivite)).all()


@router.post("/api/entreprise/secteurs/", status_code=201)
def create_secteur(payload: SecteurActiviteBase, db: Session = Depends(get_db)):
    # Validation manuelle reprise du create() custom de SecteurActiviteViewSet cote Django.
    nom = (payload.nom or "").strip()
    if not nom:
        return JSONResponse(status_code=400, content={"detail": "Le nom du secteur est obligatoire."})
    if db.scalar(select(SecteurActivite).where(SecteurActivite.nom.ilike(nom))):
        return JSONResponse(status_code=400, content={"detail": "Ce secteur existe déjà."})

    secteur = SecteurActivite(nom=nom, description=(payload.description or "").strip())
    db.add(secteur)
    db.commit()
    db.refresh(secteur)
    return SecteurActiviteResponse.model_validate(secteur)


@router.get("/api/entreprise/secteurs/{secteur_id}/", response_model=SecteurActiviteResponse)
def get_secteur(secteur_id: int, db: Session = Depends(get_db)):
    secteur = db.get(SecteurActivite, secteur_id)
    if secteur is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return secteur


@router.delete("/api/entreprise/secteurs/{secteur_id}/", status_code=204)
def delete_secteur(secteur_id: int, db: Session = Depends(get_db)):
    secteur = db.get(SecteurActivite, secteur_id)
    if secteur is None:
        raise HTTPException(status_code=404, detail="Not found.")
    db.delete(secteur)
    db.commit()


# --- /api/entreprise/entreprises/ (scope : uniquement celles de l'utilisateur connecte) -------


def _owned_query(current_user: Utilisateur):
    return select(Entreprise).where(Entreprise.owner_id == current_user.id)


def _apply_relations(db: Session, entreprise: Entreprise, domaine_ids: list[int], secteur_ids: list[int]) -> None:
    db.query(EntrepriseDomaine).filter(EntrepriseDomaine.entreprise_id == entreprise.id).delete()
    db.query(EntrepriseSecteur).filter(EntrepriseSecteur.entreprise_id == entreprise.id).delete()
    for domaine_id in domaine_ids:
        db.add(EntrepriseDomaine(entreprise_id=entreprise.id, domaine_id=domaine_id))
    for secteur_id in secteur_ids:
        db.add(EntrepriseSecteur(entreprise_id=entreprise.id, secteur_id=secteur_id))
    db.commit()


@router.get("/api/entreprise/entreprises/", response_model=list[EntrepriseResponse])
def list_entreprises(current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(_owned_query(current_user)).all()


@router.post("/api/entreprise/entreprises/", response_model=EntrepriseResponse, status_code=201)
def create_entreprise(
    payload: EntrepriseCreateUpdateRequest,
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entreprise = Entreprise(
        nom=payload.nom,
        numero_identification=payload.numero_identification,
        adresse=payload.adresse,
        telephone=payload.telephone,
        email=payload.email,
        date_creation=payload.date_creation,
        description=payload.description,
        repnom=payload.repnom,
        repprenom=payload.repprenom,
        rccm=payload.rccm,
        owner_id=current_user.id,
    )
    db.add(entreprise)
    db.commit()
    db.refresh(entreprise)
    _apply_relations(db, entreprise, payload.domaine_ids, payload.secteur_ids)

    # Essai gratuit demarre immediatement - pas d'abonnement paye tant qu'aucun paiement confirme
    # ne l'a prolonge (cf. api/routers/paiement.py). Duree lue en base (table tarifs_abonnement,
    # modifiable depuis /admin) plutot qu'en variable d'environnement.
    maintenant = datetime.now(timezone.utc)
    tarif = get_tarif(db)
    db.add(
        Abonnement(
            entreprise_id=entreprise.id,
            statut="essai",
            date_debut_essai=maintenant,
            date_fin_essai=maintenant + timedelta(days=tarif.essai_gratuit_jours),
        )
    )
    db.commit()

    db.refresh(entreprise)
    return entreprise


def _get_owned_or_404(db: Session, current_user: Utilisateur, entreprise_id: int) -> Entreprise:
    entreprise = db.scalar(_owned_query(current_user).where(Entreprise.id == entreprise_id))
    if entreprise is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return entreprise


# "active/" et "set-active/" doivent etre enregistres AVANT "/{entreprise_id}/" : Starlette
# matche les routes dans l'ordre de declaration, et un GET sur ".../active/" serait sinon capture
# par "/{entreprise_id}/" (avec entreprise_id="active", rejete en 422 par la validation int avant
# meme d'atteindre la bonne route) - bug constate en testant l'ordre reel des routes enregistrees.


@router.get("/api/entreprise/entreprises/active/")
def get_active_entreprise(current_user: Utilisateur = Depends(get_current_user)):
    if current_user.active_entreprise is None:
        return JSONResponse(status_code=404, content={"detail": "Aucune entreprise active définie."})
    return EntrepriseResponse.model_validate(current_user.active_entreprise)


@router.post("/api/entreprise/entreprises/set-active/")
def set_active_entreprise(
    payload: SetActiveEntrepriseRequest,
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.entreprise_id:
        return JSONResponse(status_code=400, content={"detail": "Le champ 'entreprise_id' est requis."})

    entreprise = db.scalar(_owned_query(current_user).where(Entreprise.id == payload.entreprise_id))
    if entreprise is None:
        return JSONResponse(
            status_code=404, content={"detail": "Entreprise non trouvée ou non liée à l'utilisateur."}
        )

    current_user.active_entreprise_id = entreprise.id
    db.commit()
    return EntrepriseResponse.model_validate(entreprise)


@router.get("/api/entreprise/entreprises/{entreprise_id}/", response_model=EntrepriseResponse)
def get_entreprise(
    entreprise_id: int, current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)
):
    return _get_owned_or_404(db, current_user, entreprise_id)


@router.put("/api/entreprise/entreprises/{entreprise_id}/", response_model=EntrepriseResponse)
def update_entreprise(
    entreprise_id: int,
    payload: EntrepriseCreateUpdateRequest,
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    entreprise = _get_owned_or_404(db, current_user, entreprise_id)
    for field in (
        "nom", "numero_identification", "adresse", "telephone", "email",
        "date_creation", "description", "repnom", "repprenom", "rccm",
    ):
        value = getattr(payload, field)
        if value is not None:
            setattr(entreprise, field, value)
    db.commit()
    _apply_relations(db, entreprise, payload.domaine_ids, payload.secteur_ids)
    db.refresh(entreprise)
    return entreprise


@router.delete("/api/entreprise/entreprises/{entreprise_id}/", status_code=204)
def delete_entreprise(
    entreprise_id: int, current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)
):
    entreprise = _get_owned_or_404(db, current_user, entreprise_id)
    db.delete(entreprise)
    db.commit()
