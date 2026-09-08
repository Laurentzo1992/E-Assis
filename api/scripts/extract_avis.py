"""Pipeline d'extraction, classification par domaine et alertes des avis d'appels d'offres.

Règles d'Or appliquées :
- Règle 1 : Déterminisme d'abord, IA en complément ciblé (sommaire page 2 + classification par domaine).
- Règle 2 : Tolérance zéro aux faux positifs (alertes strictement ciblées sur les domaines en DB).
- Règle 3 : Idempotence absolue des pipelines (pas de doublon de marché ou d'alerte sur N réexécutions).
- Règle 4 : Préservation du code existant et rétrocompatibilité (ce pipeline fonctionne en parallèle
  des résultats d'attribution sans jamais interférer avec eux).
- Règle 5 : Traçabilité complète et auditabilité (page_number conservé sur chaque marché et alerte).
- Règle 6 : Gestion défensive des erreurs (aucun crash si aucun domaine trouvé ou si l'IA renvoie null).
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import date
from pathlib import Path
from typing import Any

import fitz

from api.database import SessionLocal
from api.models.backend import Marche, Publication
from api.models.entreprise import Domaine
from api.services.avis_extractor import (
    AvisMarcheDTO,
    alerter_entreprises_pour_marche,
    classifier_marche_par_domaine,
    decouper_avis_marches,
    detecter_page_debut_avis,
    sauvegarder_marche_et_appel_offre,
)

logger = logging.getLogger(__name__)


def extract_avis(
    bulletin_ref: str,
    bulletin_numero_override: str | None = None,
    client_llm: Any = None,
) -> dict[str, Any]:
    """Exécute le pipeline complet d'extraction et d'alerte des appels d'offres.

    Args:
        bulletin_ref: Chemin vers le fichier PDF local ou clé d'objet MinIO.
        bulletin_numero_override: Numéro de bulletin explicite (ex: "4482").
        client_llm: Client LLM optionnel pour injection ou tests.
    """
    stats = {
        "bulletin_numero": None,
        "page_debut_avis": None,
        "total_marches_extraits": 0,
        "marches_avec_domaine": 0,
        "marches_sans_domaine": 0,
        "alertes_creees": 0,
    }

    # 1. Extraction du numéro de bulletin
    bulletin_numero = bulletin_numero_override
    if not bulletin_numero:
        match_num = re.search(r"(\d{4})", bulletin_ref)
        if match_num:
            bulletin_numero = match_num.group(1)
        else:
            bulletin_numero = "INCONNU"

    stats["bulletin_numero"] = bulletin_numero
    logger.info("=== DÉMARRAGE PIPELINE APPELS D'OFFRES - BULLETIN N°%s ===", bulletin_numero)

    # 2. Récupération du PDF (Fichier local ou MinIO)
    pdf_bytes: bytes | None = None
    pdf_path = Path(bulletin_ref)
    if pdf_path.is_file():
        try:
            pdf_bytes = pdf_path.read_bytes()
            logger.info("PDF local chargé avec succès : %s (%d octets)", bulletin_ref, len(pdf_bytes))
        except Exception as exc:
            logger.warning("Erreur lors de la lecture du fichier local %s : %s", bulletin_ref, exc)

    if pdf_bytes is None:
        try:
            from ingestion import config as ingestion_config

            client = ingestion_config.build_minio_client()
            response = client.get_object(ingestion_config.MINIO_BUCKET, bulletin_ref)
            try:
                pdf_bytes = response.read()
                logger.info("PDF téléchargé avec succès depuis MinIO : %s", bulletin_ref)
            finally:
                response.close()
                response.release_conn()
        except Exception as exc:
            logger.debug("PDF introuvable dans MinIO pour %s : %s", bulletin_ref, exc)

    if not pdf_bytes:
        logger.error("Impossible de récupérer le PDF pour le bulletin %s", bulletin_ref)
        return stats

    # Synchronisation MinIO automatique pour affichage immédiat dans le visualiseur PDF
    if bulletin_numero and bulletin_numero != "INCONNU":
        try:
            from ingestion import config as ingestion_config
            from ingestion.config import upload_bytes

            m_client = ingestion_config.build_minio_client()
            target_key = f"pdf/quotidien/{bulletin_numero}.pdf"
            upload_bytes(m_client, ingestion_config.MINIO_BUCKET, target_key, pdf_bytes, "application/pdf")
            logger.info("PDF synchronisé dans MinIO sous '%s'.", target_key)
        except Exception as m_exc:
            logger.debug("Synchronisation MinIO : %s", m_exc)

    # 3. Traitement du document avec PyMuPDF
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        total_pages = len(doc)
        logger.info("Document PDF ouvert : %d pages.", total_pages)

        # 4. Étape Sommaire : Extraction de la page 2 et détection de la page de début des avis
        page_sommaire_text = ""
        if total_pages >= 2:
            page_sommaire_text = doc[1].get_text("text") or ""

        page_debut = detecter_page_debut_avis(page_sommaire_text, client_llm=client_llm)
        stats["page_debut_avis"] = page_debut
        logger.info("La section des avis d'appels d'offres démarre à la page %d.", page_debut)

        # 5. Découpage des marchés entre entêtes
        marches_dtos = decouper_avis_marches(doc, page_debut=page_debut)
        stats["total_marches_extraits"] = len(marches_dtos)

        # 6. Session DB et classification par domaines
        with SessionLocal() as db:
            # Récupération ou création de la Publication
            publication = db.query(Publication).filter(Publication.numero == bulletin_numero).first()
            if not publication:
                publication = Publication(
                    titre=f"Quotidien des marchés publics N°{bulletin_numero}",
                    numero=bulletin_numero,
                    date_publication=date.today(),
                    source="DGCMEF",
                    type_publication="QUOTIDIEN",
                )
                db.add(publication)
                db.commit()
                db.refresh(publication)

            # Chargement de tous les domaines d'activité enregistrés par l'admin
            domaines_db = db.query(Domaine).all()
            domaines_list = [{"id": d.id, "libelle": d.libelle} for d in domaines_db]
            logger.info("Nombre de domaines d'activité chargés en base : %d", len(domaines_list))

            # 7. Classification par l'IA et enregistrement de chaque marché
            total_alertes = 0
            for idx, dto in enumerate(marches_dtos, start=1):
                logger.info(
                    "Traitement marché [%d/%d] - Page %d : %s...",
                    idx,
                    len(marches_dtos),
                    dto.page_number,
                    dto.objet[:50],
                )

                # Classification sémantique par l'IA (Gestion défensive absolue : Règle 6)
                domaine_id = classifier_marche_par_domaine(
                    dto.titre_ou_entete,
                    domaines_list,
                    client_llm=client_llm,
                )
                dto.domaine_id = domaine_id

                if domaine_id:
                    stats["marches_avec_domaine"] += 1
                else:
                    stats["marches_sans_domaine"] += 1

                # Sauvegarde du Marché & AppelOffre (Idempotence : Règle 3)
                marche_db = sauvegarder_marche_et_appel_offre(db, dto, publication)

                # Génération des alertes ciblées pour les entreprises du domaine
                alertes = alerter_entreprises_pour_marche(db, marche_db, publication)
                total_alertes += len(alertes)

            stats["alertes_creees"] = total_alertes
    finally:
        doc.close()

    logger.info(
        "=== SYNTHÈSE EXTRACTION APPELS D'OFFRES ===\n"
        "  - Bulletin : N°%s\n"
        "  - Page de début : %s\n"
        "  - Total marchés extraits : %d\n"
        "  - Avec domaine associé : %d\n"
        "  - Sans domaine (non bloquant) : %d\n"
        "  - Alertes ciblées créées : %d\n"
        "===========================================",
        stats["bulletin_numero"],
        stats["page_debut_avis"],
        stats["total_marches_extraits"],
        stats["marches_avec_domaine"],
        stats["marches_sans_domaine"],
        stats["alertes_creees"],
    )
    return stats


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Pipeline d'extraction des avis d'appels d'offres (DGCMEF)",
    )
    parser.add_argument(
        "bulletin_ref",
        nargs="?",
        help="Chemin vers le fichier PDF du bulletin ou clé MinIO",
    )
    parser.add_argument(
        "--pdf",
        dest="pdf_path",
        help="Chemin explicite vers le PDF",
    )
    parser.add_argument(
        "--bulletin",
        "-b",
        dest="bulletin_num",
        help="Numéro explicite du bulletin (ex: 4482)",
    )

    args = parser.parse_args()
    ref = args.pdf_path or args.bulletin_ref

    if not ref:
        parser.error("Vous devez fournir un chemin PDF (positionnel ou via --pdf).")

    extract_avis(ref, bulletin_numero_override=args.bulletin_num)


if __name__ == "__main__":
    main()