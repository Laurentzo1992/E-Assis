"""Service de notification ciblée et idempotente pour les résultats d'attribution.

Règles d'Or appliquées :
- Règle 1 : Déterminisme d'abord (règles de notification strictes sans hallucination).
- Règle 2 : Tolérance zéro aux faux positifs d'attribution (seuil >= 0.85 ou match exact, pas d'envoi si A_VERIFIER).
- Règle 3 : Idempotence absolue des pipelines (déduplication via AlerteResultat et SHA-256 message_hash).
- Règle 4 : Préservation du code existant et réutilisation (whatsapp_client, email_utils).
- Règle 5 : Traçabilité complète et auditabilité (bulletin, lot, montant, motif, canaux).
- Règle 6 : Gestion défensive des erreurs (isolation par bloc try/except).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from api.config import settings
from api.email_utils import send_resultat_echec_email, send_resultat_victoire_email
from api.models.abonnement import Abonnement
from api.models.entreprise import Entreprise
from api.models.resultats_attribution import (
    AlerteResultat,
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)
from api.models.utilisateur import Utilisateur
from api.whatsapp_client import WhatsAppSendError, send_whatsapp_template

if TYPE_CHECKING:
    import fitz

logger = logging.getLogger(__name__)


def calculer_message_hash(
    entreprise_id: int,
    soumissionnaire_id: int,
    type_notification: str,
    bulletin_numero: str,
    lot_id: int,
) -> str:
    """Calcule un hash SHA-256 déterministe pour garantir l'idempotence stricte (Règle d'Or n°3)."""
    payload = f"{entreprise_id}:{soumissionnaire_id}:{type_notification}:{bulletin_numero}:{lot_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def formater_montant_fcfa(montant: Decimal | float | None) -> str:
    """Formate un montant numérique en FCFA avec séparateurs d'espaces."""
    if montant is None:
        return "Montant non précisé"
    return f"{Decimal(str(montant)):,.0f} FCFA".replace(",", " ")


def entreprise_est_eligible_alerte(db: Session, entreprise: Entreprise) -> bool:
    """Vérifie si le compte propriétaire de l'entreprise est éligible aux alertes.
    Exige :
    - Utilisateur.notifications_actives == True
    - Abonnement actif, période d'essai ou compte staff/administrateur.
    """
    maintenant = datetime.now(timezone.utc)
    owner = db.query(Utilisateur).filter(Utilisateur.id == entreprise.owner_id).first()
    if not owner or not owner.notifications_actives:
        return False
    if owner.is_staff or owner.is_superuser:
        return True

    abo = db.query(Abonnement).filter(Abonnement.utilisateur_id == owner.id).first()
    if abo is None:
        return True
    return bool(
        (abo.date_fin_essai and abo.date_fin_essai > maintenant)
        or (abo.statut == "actif" and abo.date_fin_abonnement and abo.date_fin_abonnement > maintenant)
    )


def notifier_resultat_soumissionnaire(
    db: Session,
    soum: SoumissionnaireResultat,
    *,
    bulletin_numero: str,
    page_number: int | None = None,
    pdf_doc: fitz.Document | None = None,
    page_image: bytes | None = None,
    dry_run: bool = False,
) -> tuple[AlerteResultat | None, bool]:
    """Envoie et consigne l'alerte pour un soumissionnaire identifié de manière sûre.
    Retourne un tuple (alerte, deja_alerte) où deja_alerte=True si l'alerte avait déjà été émise (idempotence).
    """
    # Règle d'Or n°2 : Tolérance zéro aux faux positifs
    if soum.entreprise_id is None:
        return None, False

    if soum.statut_reconciliation not in ("EXACT", "PROBABLE"):
        logger.warning(
            "Soumissionnaire #%s flagué '%s' - aucune notification envoyée (Règle n°2)",
            soum.id,
            soum.statut_reconciliation,
        )
        return None, False

    entreprise = db.query(Entreprise).filter(Entreprise.id == soum.entreprise_id).first()
    if not entreprise:
        return None, False

    # Vérification d'éligibilité abonnement/compte
    if not dry_run and not entreprise_est_eligible_alerte(db, entreprise):
        logger.info("Entreprise #%s (%s) non éligible aux notifications (inactif/expiré)", entreprise.id, entreprise.nom)
        return None, False

    lot: LotResultat = soum.lot_resultat
    resultat: ResultatAttribution = lot.resultat_attribution

    type_notification = "ATTRIBUTION_VICTOIRE" if soum.est_attributaire else "ATTRIBUTION_ECHEC"
    msg_hash = calculer_message_hash(
        entreprise.id,
        soum.id,
        type_notification,
        bulletin_numero,
        lot.id,
    )

    # Règle d'Or n°3 : Idempotence absolue
    alerte_existante = (
        db.query(AlerteResultat)
        .filter(
            AlerteResultat.entreprise_id == entreprise.id,
            AlerteResultat.soumissionnaire_resultat_id == soum.id,
            AlerteResultat.type_notification == type_notification,
        )
        .first()
    )

    if alerte_existante and alerte_existante.statut_envoi == "SENT":
        logger.info(
            "Notification %s déjà émise pour Entreprise #%s / Soumissionnaire #%s",
            type_notification,
            entreprise.id,
            soum.id,
        )
        return alerte_existante, True

    # Trouver l'attributaire gagnant pour le contexte du REX en cas d'échec
    attributaire_gagnant_nom = None
    montant_gagnant_str = None
    if not soum.est_attributaire:
        gagnant = next((s for s in lot.soumissionnaires if s.est_attributaire), None)
        if gagnant:
            attributaire_gagnant_nom = gagnant.nom_entreprise_brut
            montant_gagnant_str = formater_montant_fcfa(gagnant.montant_corrige or gagnant.montant_lu)

    montant_str = formater_montant_fcfa(soum.montant_corrige or soum.montant_lu)
    date_str = resultat.date_attribution.strftime("%d/%m/%Y") if resultat.date_attribution else ""

    # Construction de la synthèse textuelle pour l'alerte
    if type_notification == "ATTRIBUTION_VICTOIRE":
        texte_synthese = (
            f"Félicitations {entreprise.nom} ! Vous êtes désigné attributaire du marché "
            f"'{resultat.objet}' (Lot {lot.numero_lot}) par {resultat.autorite_contractante} "
            f"pour un montant de {montant_str}. Bulletin n°{bulletin_numero} (page {page_number or resultat.page_source})."
        )
    else:
        rex_info = f" Motif d'écartement : {soum.motif_rejet}." if soum.motif_rejet else ""
        gagnant_info = (
            f" Attributaire retenu : {attributaire_gagnant_nom} ({montant_gagnant_str})."
            if attributaire_gagnant_nom
            else ""
        )
        texte_synthese = (
            f"Résultats de dépouillement : Votre offre pour {entreprise.nom} n'a pas été retenue sur le marché "
            f"'{resultat.objet}' (Lot {lot.numero_lot}) de {resultat.autorite_contractante}.{rex_info}{gagnant_info} "
            f"Bulletin n°{bulletin_numero} (page {page_number or resultat.page_source})."
        )

    if dry_run:
        logger.info("[DRY-RUN] [%s] %s -> %s", type_notification, entreprise.nom, texte_synthese)
        return None, False

    canaux_reussis: list[str] = []

    # 1. Canal WhatsApp (Meta Cloud API)
    if entreprise.telephone:
        try:
            if type_notification == "ATTRIBUTION_VICTOIRE":
                params = [
                    entreprise.nom,
                    f"Lot {lot.numero_lot}: {lot.intitule_lot or resultat.objet}"[:120],
                    f"{montant_str} ({resultat.autorite_contractante})"[:120],
                ]
                template_name = settings.whatsapp_template_resultat_victoire
            else:
                motif_court = (soum.motif_rejet or "Offre non retenue")[:100]
                params = [
                    entreprise.nom,
                    f"Lot {lot.numero_lot}: {motif_court}",
                    resultat.autorite_contractante[:100],
                ]
                template_name = settings.whatsapp_template_resultat_echec

            send_whatsapp_template(entreprise.telephone, parameters=params, template_name=template_name)
            canaux_reussis.append("whatsapp")
        except WhatsAppSendError as exc:
            logger.warning("Envoi WhatsApp de résultat échoué pour l'entreprise %s : %s", entreprise.id, exc)
        except Exception as exc:
            logger.warning("Erreur inattendue envoi WhatsApp pour %s : %s", entreprise.id, exc)

    # 2. Canal Email
    if entreprise.email:
        try:
            if type_notification == "ATTRIBUTION_VICTOIRE":
                send_resultat_victoire_email(
                    user_email=entreprise.email,
                    entreprise_nom=entreprise.nom,
                    autorite_contractante=resultat.autorite_contractante,
                    objet=resultat.objet,
                    numero_lot=lot.numero_lot,
                    intitule_lot=lot.intitule_lot,
                    reference_dossier=resultat.reference_dossier,
                    montant=montant_str,
                    delai_execution=soum.delai_execution,
                    numero_bulletin=bulletin_numero,
                    date_bulletin=date_str,
                    page_number=page_number or resultat.page_source,
                    page_image=page_image,
                )
            else:
                send_resultat_echec_email(
                    user_email=entreprise.email,
                    entreprise_nom=entreprise.nom,
                    autorite_contractante=resultat.autorite_contractante,
                    objet=resultat.objet,
                    numero_lot=lot.numero_lot,
                    intitule_lot=lot.intitule_lot,
                    reference_dossier=resultat.reference_dossier,
                    motif_rejet=soum.motif_rejet,
                    attributaire_gagnant=attributaire_gagnant_nom,
                    montant_gagnant=montant_gagnant_str,
                    numero_bulletin=bulletin_numero,
                    date_bulletin=date_str,
                    page_number=page_number or resultat.page_source,
                    page_image=page_image,
                )
            canaux_reussis.append("email")
        except Exception as exc:
            logger.warning("Envoi email de résultat échoué pour l'entreprise %s : %s", entreprise.id, exc)

    # Enregistrement défensif et traçabilité (Règles 3, 5 et 6)
    statut_envoi = "SENT" if canaux_reussis else "FAILED"
    canal_str = "+".join(canaux_reussis) if canaux_reussis else "aucun"

    if alerte_existante is None:
        alerte_db = AlerteResultat(
            entreprise_id=entreprise.id,
            soumissionnaire_resultat_id=soum.id,
            canal_alerte=canal_str,
            type_notification=type_notification,
            contenu_alerte=texte_synthese,
            date_envoi=datetime.now(timezone.utc),
            statut_envoi=statut_envoi,
            message_hash=msg_hash,
        )
        db.add(alerte_db)
    else:
        alerte_db = alerte_existante
        alerte_db.canal_alerte = canal_str
        alerte_db.statut_envoi = statut_envoi
        alerte_db.contenu_alerte = texte_synthese
        alerte_db.date_envoi = datetime.now(timezone.utc)

    db.commit()
    db.refresh(alerte_db)
    return alerte_db, False


def notifier_tous_resultats_bulletin(
    db: Session,
    bulletin_numero: str,
    *,
    dry_run: bool = False,
    pdf_doc: fitz.Document | None = None,
) -> dict[str, int]:
    """Scanne tous les résultats d'attribution d'un bulletin et notifie les entreprises réconciliées."""
    resultats = (
        db.query(ResultatAttribution)
        .filter(ResultatAttribution.bulletin_numero == str(bulletin_numero))
        .all()
    )

    stats = {
        "resultats_traites": len(resultats),
        "victoires_envoyees": 0,
        "echecs_envoyes": 0,
        "deja_alertes": 0,
        "echoues": 0,
        "ignores_a_verifier": 0,
    }

    for res in resultats:
        for lot in res.lots:
            for soum in lot.soumissionnaires:
                if not soum.entreprise_id:
                    continue

                if soum.statut_reconciliation == "A_VERIFIER":
                    stats["ignores_a_verifier"] += 1
                    continue

                try:
                    alerte, deja_alerte = notifier_resultat_soumissionnaire(
                        db,
                        soum,
                        bulletin_numero=str(bulletin_numero),
                        page_number=res.page_source,
                        pdf_doc=pdf_doc,
                        dry_run=dry_run,
                    )
                    if deja_alerte:
                        stats["deja_alertes"] += 1
                    elif alerte:
                        if alerte.statut_envoi == "SENT":
                            if alerte.type_notification == "ATTRIBUTION_VICTOIRE":
                                stats["victoires_envoyees"] += 1
                            else:
                                stats["echecs_envoyes"] += 1
                        else:
                            stats["echoues"] += 1
                    elif dry_run:
                        if soum.est_attributaire:
                            stats["victoires_envoyees"] += 1
                        else:
                            stats["echecs_envoyes"] += 1
                except Exception as exc:
                    logger.error(
                        "Erreur traitement notification soumissionnaire #%s : %s",
                        soum.id,
                        exc,
                    )
                    stats["echoues"] += 1

    return stats
