"""Abonnement annuel par entreprise : essai gratuit a la creation (cf. api/routers/entreprise.py,
create_entreprise), puis paiement via CinetPay pour continuer au-dela.

Le webhook (`/webhook/`) est le seul endpoint de ce module SANS authentification - c'est CinetPay
qui l'appelle, pas un utilisateur connecte. Il ne fait jamais confiance au contenu du webhook lui-
meme (rejouable/falsifiable) : il rappelle `verifier_transaction` (payment_client.py) pour confirmer
aupres de CinetPay avant de crediter quoi que ce soit.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from api.config import settings
from api.database import get_db
from api.models.abonnement import Abonnement, Paiement
from api.models.entreprise import Entreprise
from api.models.tarif import get_tarif
from api.models.utilisateur import Utilisateur
from api.payment_client import PaiementError, initier_paiement, verifier_transaction
from api.schemas.abonnement import AbonnementResponse, InitierPaiementRequest, InitierPaiementResponse, TarifResponse
from api.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/paiement")


def _get_owned_abonnement_or_404(db: Session, current_user: Utilisateur, entreprise_id: int) -> Abonnement:
    abonnement = (
        db.query(Abonnement)
        .join(Entreprise, Entreprise.id == Abonnement.entreprise_id)
        .filter(Entreprise.id == entreprise_id, Entreprise.owner_id == current_user.id)
        .one_or_none()
    )
    if abonnement is None:
        raise HTTPException(status_code=404, detail="Not found.")
    return abonnement


def _statut_courant(abonnement: Abonnement, maintenant: datetime) -> str:
    """Recalcule le statut a la volee a partir des dates plutot que de faire confiance au champ
    `statut` stocke : un essai/abonnement expire depuis la derniere ecriture en base doit se voir
    comme "expire" immediatement, sans tache planifiee dediee pour le mettre a jour."""
    if abonnement.statut == "actif" and abonnement.date_fin_abonnement and abonnement.date_fin_abonnement > maintenant:
        return "actif"
    if abonnement.date_fin_essai > maintenant:
        return "essai"
    return "expire"


def _jours_restants(abonnement: Abonnement, statut: str, maintenant: datetime) -> int:
    if statut == "actif" and abonnement.date_fin_abonnement:
        return max(0, (abonnement.date_fin_abonnement - maintenant).days)
    if statut == "essai":
        return max(0, (abonnement.date_fin_essai - maintenant).days)
    return 0


def _to_response(abonnement: Abonnement) -> AbonnementResponse:
    maintenant = datetime.now(timezone.utc)
    statut = _statut_courant(abonnement, maintenant)
    return AbonnementResponse(
        statut=statut,
        date_debut_essai=abonnement.date_debut_essai,
        date_fin_essai=abonnement.date_fin_essai,
        date_fin_abonnement=abonnement.date_fin_abonnement,
        jours_restants=_jours_restants(abonnement, statut, maintenant),
    )


@router.get("/abonnement/{entreprise_id}/", response_model=AbonnementResponse)
def get_abonnement(
    entreprise_id: int, current_user: Utilisateur = Depends(get_current_user), db: Session = Depends(get_db)
):
    return _to_response(_get_owned_abonnement_or_404(db, current_user, entreprise_id))


@router.get("/tarif/", response_model=TarifResponse)
def get_tarif_actuel(db: Session = Depends(get_db)):
    """Public (pas de get_current_user) : consulte par la landing page et /Tarifs avant que le
    visiteur ait un compte."""
    return get_tarif(db)


@router.post("/initier/", response_model=InitierPaiementResponse)
def initier(
    payload: InitierPaiementRequest,
    current_user: Utilisateur = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    abonnement = _get_owned_abonnement_or_404(db, current_user, payload.entreprise_id)
    tarif = get_tarif(db)

    reference = f"kbbot-{abonnement.entreprise_id}-{uuid.uuid4().hex[:12]}"
    paiement = Paiement(
        abonnement_id=abonnement.id,
        reference=reference,
        fournisseur="cinetpay",
        montant=tarif.prix_annuel,
        devise=tarif.devise,
        statut="en_attente",
        date_creation=datetime.now(timezone.utc),
    )
    db.add(paiement)
    db.commit()

    try:
        url = initier_paiement(
            reference=reference,
            montant=str(tarif.prix_annuel),
            devise=tarif.devise,
            description=f"Abonnement annuel Veille Marches - {abonnement.entreprise.nom}",
            notify_url=f"{settings.api_public_domain}/api/paiement/webhook/",
            # entreprise_id en query string : la page de retour n'a pas d'autre moyen de savoir
            # quel abonnement rafraichir (CinetPay ne renvoie que sa propre reference de
            # transaction sur l'URL de retour, jamais nos donnees metier).
            return_url=f"{settings.frontend_domain}/paiement/retour?entreprise_id={abonnement.entreprise_id}",
        )
    except PaiementError as exc:
        paiement.statut = "echoue"
        db.commit()
        raise HTTPException(status_code=502, detail=f"Initiation du paiement impossible : {exc}") from None

    return InitierPaiementResponse(url=url)


@router.post("/webhook/", status_code=204)
async def webhook(request: Request, db: Session = Depends(get_db)):
    # CinetPay poste le webhook en application/x-www-form-urlencoded (cpm_trans_id) - accepte
    # aussi un corps JSON par souplesse, jamais verifie a ce stade contre l'API reelle.
    try:
        form = await request.form()
        reference = form.get("cpm_trans_id")
    except Exception:
        reference = None
    if reference is None:
        body = await request.json()
        reference = body.get("cpm_trans_id") or body.get("transaction_id")

    if not reference:
        raise HTTPException(status_code=400, detail="Reference de transaction manquante.")

    paiement = db.query(Paiement).filter(Paiement.reference == reference).one_or_none()
    if paiement is None:
        logger.warning("Webhook paiement recu pour une reference inconnue : %s", reference)
        return

    if paiement.statut == "reussi":
        return  # deja traite (rejeu du webhook) - idempotent, ne recredite jamais.

    try:
        confirme = verifier_transaction(reference)
    except PaiementError as exc:
        logger.error("Verification du paiement %s impossible : %s", reference, exc)
        raise HTTPException(status_code=502, detail="Verification du paiement impossible.") from None

    if not confirme:
        paiement.statut = "echoue"
        db.commit()
        return

    maintenant = datetime.now(timezone.utc)
    paiement.statut = "reussi"
    paiement.date_confirmation = maintenant

    abonnement = paiement.abonnement
    # Un renouvellement anticipe prolonge a partir de la date de fin existante si elle est encore
    # dans le futur, jamais a partir d'"aujourd'hui" (ne fait jamais perdre de jours deja payes).
    depart = abonnement.date_fin_abonnement if abonnement.date_fin_abonnement and abonnement.date_fin_abonnement > maintenant else maintenant
    abonnement.date_fin_abonnement = depart + timedelta(days=365)
    abonnement.statut = "actif"

    db.commit()
    logger.info("Paiement confirme, abonnement prolonge jusqu'au %s (entreprise=%s)", abonnement.date_fin_abonnement, abonnement.entreprise_id)
