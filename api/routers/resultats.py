"""Routes de l'API pour les résultats d'attribution de marchés publics.

Expose :
- L'espace Entreprise (consultation des victoires, retours d'expérience REX et alertes).
- L'espace Administrateur (audit par bulletin, modération et arbitrage des statuts A_VERIFIER).

Conformément à la Charte d'Ingénierie :
- Règle 2 : Tolérance zéro aux faux positifs d'attribution (seuls les statuts réconciliés sont visibles par les clients).
- Règle 3 : Idempotence absolue et intégrité des données.
- Règle 4 : Rétrocompatibilité et préservation des routes existantes.
- Règle 5 : Traçabilité complète (pages sources, motifs PV, scores de réconciliation).
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from api.database import get_db
from api.models.backend import Publication
from api.models.entreprise import Entreprise
from api.models.resultats_attribution import (
    AlerteResultat,
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)
from api.models.utilisateur import Utilisateur
from api.schemas.resultats import (
    AlerteResultatResponse,
    ReconcilierSoumissionnaireRequest,
    ReconcilierSoumissionnaireResponse,
    ResultatAttributionResponse,
    ResultatEntrepriseItem,
    SoumissionnaireAVerifierResponse,
)
from api.security import get_current_user
from api.services.resultats_notifier import notifier_resultat_soumissionnaire

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Résultats d'Attribution"])


def require_staff_user(current_user: Utilisateur = Depends(get_current_user)) -> Utilisateur:
    """Vérifie que l'utilisateur dispose des droits d'administration."""
    if not (current_user.is_staff or current_user.is_superuser):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas la permission d'effectuer cette action administrative.",
        )
    return current_user


def _check_entreprise_access(db: Session, entreprise_id: int, current_user: Utilisateur) -> Entreprise:
    """Vérifie que l'utilisateur est bien le propriétaire de l'entreprise ou administrateur."""
    entreprise = db.get(Entreprise, entreprise_id)
    if entreprise is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entreprise #{entreprise_id} introuvable.",
        )
    if not (current_user.is_staff or current_user.is_superuser) and entreprise.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Vous n'avez pas accès aux résultats de cette entreprise.",
        )
    return entreprise


# ==============================================================================
# ESPACE ENTREPRISE (Client Authentifié)
# ==============================================================================


@router.get(
    "/api/resultats/entreprise/{entreprise_id}",
    response_model=list[ResultatEntrepriseItem],
    summary="Historique des résultats de marchés pour une entreprise (alias Dashboard)",
)
@router.get(
    "/api/resultats/entreprise/{entreprise_id}/",
    response_model=list[ResultatEntrepriseItem],
    include_in_schema=False,
)
@router.get(
    "/api/entreprises/{entreprise_id}/resultats",
    response_model=list[ResultatEntrepriseItem],
    summary="Historique des résultats de marchés pour une entreprise",
)
@router.get(
    "/api/entreprises/{entreprise_id}/resultats/",
    response_model=list[ResultatEntrepriseItem],
    include_in_schema=False,
)
def get_resultats_entreprise(
    entreprise_id: int,
    type_filtre: str | None = Query(
        None, description="Filtre optionnel : 'victoires' (attribués) ou 'echecs' (REX)"
    ),
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Retourne la liste des résultats d'attribution consolidés concernant l'entreprise."""
    _check_entreprise_access(db, entreprise_id, current_user)

    # Récupération des soumissionnaires rattachés avec certitude (Règle n°2 : exclusion stricte de A_VERIFIER)
    query = (
        select(SoumissionnaireResultat)
        .options(
            joinedload(SoumissionnaireResultat.lot_resultat).joinedload(
                LotResultat.resultat_attribution
            )
        )
        .where(
            SoumissionnaireResultat.entreprise_id == entreprise_id,
            SoumissionnaireResultat.statut_reconciliation.in_(["EXACT", "PROBABLE", "MANUEL"]),
        )
        .order_by(SoumissionnaireResultat.id.desc())
    )

    if type_filtre == "victoires":
        query = query.where(SoumissionnaireResultat.est_attributaire.is_(True))
    elif type_filtre == "echecs":
        query = query.where(SoumissionnaireResultat.est_attributaire.is_(False))

    soumissionnaires = db.scalars(query).all()
    items: list[ResultatEntrepriseItem] = []

    for s in soumissionnaires:
        lot = s.lot_resultat
        res = lot.resultat_attribution if lot else None

        # Si l'entreprise n'est pas attributaire, récupérer les infos de l'attributaire gagnant sur le lot
        nom_gagnant: str | None = None
        montant_gagnant = None
        if not s.est_attributaire and lot:
            gagnant = db.scalar(
                select(SoumissionnaireResultat).where(
                    SoumissionnaireResultat.lot_resultat_id == lot.id,
                    SoumissionnaireResultat.est_attributaire.is_(True),
                )
            )
            if gagnant:
                nom_gagnant = gagnant.nom_entreprise_brut
                montant_gagnant = gagnant.montant_corrige or gagnant.montant_lu

        montant_valeur = s.montant_corrige or s.montant_lu

        pub_id = res.publication_id if res else None
        if not pub_id and res and res.bulletin_numero:
            pub = db.scalar(select(Publication).where(Publication.numero == str(res.bulletin_numero)))
            if pub:
                pub_id = pub.id
                res.publication_id = pub.id
                db.commit()

        items.append(
            ResultatEntrepriseItem(
                soumissionnaire_id=s.id,
                resultat_id=res.id if res else 0,
                publication_id=pub_id,
                bulletin_numero=res.bulletin_numero if res else None,
                page_source=res.page_source if res else None,
                autorite_contractante=res.autorite_contractante if res else "Inconnue",
                reference_dossier=res.reference_dossier if res else None,
                objet=res.objet if res else "",
                numero_lot=lot.numero_lot if lot else "1",
                intitule_lot=lot.intitule_lot if lot else None,
                est_attributaire=s.est_attributaire,
                statut=s.statut,
                rang_classement=s.rang_classement,
                montant_attribue_ou_soumis=montant_valeur,
                delai_execution=s.delai_execution,
                motif_rejet=s.motif_rejet,
                nom_attributaire_retenu=nom_gagnant,
                montant_attributaire_retenu=montant_gagnant,
                score_reconciliation=s.score_matching,
                statut_reconciliation=s.statut_reconciliation,
            )
        )

    return items


@router.get(
    "/api/entreprises/{entreprise_id}/alertes-resultats",
    response_model=list[AlerteResultatResponse],
    summary="Alertes reçues sur les résultats d'attribution",
)
@router.get(
    "/api/entreprises/{entreprise_id}/alertes-resultats/",
    response_model=list[AlerteResultatResponse],
    include_in_schema=False,
)
def get_alertes_resultats_entreprise(
    entreprise_id: int,
    db: Session = Depends(get_db),
    current_user: Utilisateur = Depends(get_current_user),
):
    """Consulte l'historique des alertes émises (WhatsApp & Email) pour l'entreprise."""
    _check_entreprise_access(db, entreprise_id, current_user)

    alertes = (
        db.scalars(
            select(AlerteResultat)
            .where(AlerteResultat.entreprise_id == entreprise_id)
            .order_by(AlerteResultat.date_envoi.desc())
        )
        .all()
    )
    return alertes


# ==============================================================================
# ESPACE ADMINISTRATEUR (Back-office, Modération & Audit)
# ==============================================================================


@router.get(
    "/api/admin/resultats/a-verifier",
    response_model=list[SoumissionnaireAVerifierResponse],
    summary="Liste des soumissionnaires ambigus nécessitant un arbitrage manuel",
)
@router.get(
    "/api/admin/resultats/a-verifier/",
    response_model=list[SoumissionnaireAVerifierResponse],
    include_in_schema=False,
)
def list_soumissionnaires_a_verifier(
    db: Session = Depends(get_db),
    _admin: Utilisateur = Depends(require_staff_user),
):
    """Retourne la liste des soumissionnaires marqués A_VERIFIER (Règle d'Or n°2)."""
    soumissionnaires = (
        db.scalars(
            select(SoumissionnaireResultat)
            .options(
                joinedload(SoumissionnaireResultat.lot_resultat).joinedload(
                    LotResultat.resultat_attribution
                )
            )
            .where(SoumissionnaireResultat.statut_reconciliation == "A_VERIFIER")
            .order_by(SoumissionnaireResultat.id.desc())
        )
        .all()
    )

    resultats: list[SoumissionnaireAVerifierResponse] = []
    # Charger l'ensemble des entreprises inscrites pour proposer des correspondances potentielles
    entreprises_existantes = db.scalars(select(Entreprise)).all()

    for s in soumissionnaires:
        lot = s.lot_resultat
        res = lot.resultat_attribution if lot else None

        candidats_proposes: list[dict[str, Any]] = []
        for ent in entreprises_existantes:
            # Si nom proche ou mention partielle
            if s.nom_entreprise_normalise and ent.nom.lower() in s.nom_entreprise_normalise:
                candidats_proposes.append(
                    {
                        "entreprise_id": ent.id,
                        "nom": ent.nom,
                        "ifu": ent.numero_identification,
                        "rccm": ent.rccm,
                    }
                )

        resultats.append(
            SoumissionnaireAVerifierResponse(
                id=s.id,
                nom_entreprise_brut=s.nom_entreprise_brut,
                nom_entreprise_normalise=s.nom_entreprise_normalise,
                ifu_extrait=s.ifu_extrait,
                rccm_extrait=s.rccm_extrait,
                score_matching=s.score_matching,
                methode_matching=s.methode_matching,
                bulletin_numero=res.bulletin_numero if res else None,
                page_source=res.page_source if res else None,
                autorite_contractante=res.autorite_contractante if res else "Inconnue",
                objet=res.objet if res else "",
                numero_lot=lot.numero_lot if lot else "1",
                est_attributaire=s.est_attributaire,
                montant=s.montant_corrige or s.montant_lu,
                candidats_reconcilies_possibles=candidats_proposes,
            )
        )

    return resultats


@router.post(
    "/api/admin/resultats/{soumissionnaire_id}/reconcilier",
    response_model=ReconcilierSoumissionnaireResponse,
    summary="Arbitrer et réconcilier manuellement un soumissionnaire",
)
@router.post(
    "/api/admin/resultats/{soumissionnaire_id}/reconcilier/",
    response_model=ReconcilierSoumissionnaireResponse,
    include_in_schema=False,
)
def reconcilier_soumissionnaire_manuellement(
    soumissionnaire_id: int,
    payload: ReconcilierSoumissionnaireRequest,
    db: Session = Depends(get_db),
    _admin: Utilisateur = Depends(require_staff_user),
):
    """Permet à un administrateur de valider ou rejeter un candidat en doute (Règle d'Or n°2 & n°5)."""
    soumissionnaire = db.get(SoumissionnaireResultat, soumissionnaire_id)
    if soumissionnaire is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Soumissionnaire introuvable.")

    action = payload.action.upper()
    if action not in ["VALIDER", "REJETER"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'action doit être 'VALIDER' ou 'REJETER'.",
        )

    alerte_emise = False

    if action == "REJETER":
        soumissionnaire.statut_reconciliation = "NON_ASSIGNE"
        soumissionnaire.entreprise_id = None
        soumissionnaire.methode_matching = "REJET_MANUEL"
        db.commit()
        db.refresh(soumissionnaire)
        return ReconcilierSoumissionnaireResponse(
            status="success",
            soumissionnaire_id=soumissionnaire.id,
            statut_reconciliation="NON_ASSIGNE",
            entreprise_id=None,
            alerte_emise=False,
            detail="Rattachement rejeté avec succès. Aucune notification émise.",
        )

    # Action VALIDER
    if not payload.entreprise_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'identifiant de l'entreprise (entreprise_id) est obligatoire pour valider.",
        )

    entreprise = db.get(Entreprise, payload.entreprise_id)
    if entreprise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entreprise cible introuvable.")

    soumissionnaire.entreprise_id = entreprise.id
    soumissionnaire.statut_reconciliation = "MANUEL"
    soumissionnaire.methode_matching = "MANUEL_ADMIN"
    soumissionnaire.score_matching = 1.0

    db.commit()
    db.refresh(soumissionnaire)

    # Déclencher la notification si demandé (Règle d'Or n°3 : idempotence vérifiée)
    if payload.emettre_alerte:
        try:
            alerte = notifier_resultat_soumissionnaire(db, soumissionnaire, entreprise)
            alerte_emise = alerte is not None
        except Exception as exc:
            logger.error("Erreur lors de l'émission manuelle de l'alerte pour #%d : %s", soumissionnaire.id, exc)

    return ReconcilierSoumissionnaireResponse(
        status="success",
        soumissionnaire_id=soumissionnaire.id,
        statut_reconciliation="MANUEL",
        entreprise_id=entreprise.id,
        alerte_emise=alerte_emise,
        detail=f"Soumissionnaire validé et rattaché avec succès à l'entreprise '{entreprise.nom}'.",
    )


@router.get(
    "/api/admin/resultats/bulletin/{bulletin_numero}",
    response_model=list[ResultatAttributionResponse],
    summary="Audit complet des résultats d'attribution d'un bulletin",
)
@router.get(
    "/api/admin/resultats/bulletin/{bulletin_numero}/",
    response_model=list[ResultatAttributionResponse],
    include_in_schema=False,
)
def get_resultats_bulletin_audit(
    bulletin_numero: str,
    db: Session = Depends(get_db),
    _admin: Utilisateur = Depends(require_staff_user),
):
    """Permet à l'administrateur d'auditer l'ensemble des délibérations extraites d'un numéro de bulletin."""
    resultats = (
        db.scalars(
            select(ResultatAttribution)
            .options(
                joinedload(ResultatAttribution.lots).joinedload(
                    LotResultat.soumissionnaires
                )
            )
            .where(ResultatAttribution.bulletin_numero == str(bulletin_numero))
            .order_by(ResultatAttribution.page_source.asc(), ResultatAttribution.id.asc())
        )
        .unique()
        .all()
    )
    return resultats
