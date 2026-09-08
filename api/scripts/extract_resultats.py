"""Pipeline d'extraction, réconciliation et enregistrement des résultats d'attribution.

Règles d'Or appliquées :
- Règle 1 : Déterminisme d'abord, IA en complément ciblé (TabularResultatsParser).
- Règle 2 : Tolérance zéro aux faux positifs d'attribution (EntityResolver).
- Règle 3 : Idempotence absolue des pipelines (pas de doublons sur N réexécutions).
- Règle 4 : Préservation du code existant et rétrocompatibilité (maintien des liens Marche/Resultat).
- Règle 5 : Traçabilité complète et auditabilité (bulletin, page, extrait brut, score, méthode).
- Règle 6 : Gestion défensive des erreurs (isolation par bloc try/except).
"""

from __future__ import annotations

import argparse
import logging
import re
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any

from api.database import SessionLocal
from api.models.backend import Marche, Publication, Resultat
from api.models.entreprise import Entreprise
from api.models.resultats_attribution import (
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)
from api.services.client_resultats_extractor import (
    detecter_mentions_entreprises,
    executer_analyses_ia_paralleles,
    sauvegarder_resultat_client,
)
from api.services.entity_resolution import EntityResolver, ReconciliationResult
from api.services.tabular_resultats_parser import (
    ResultatExtractionDTO,
    TabularResultatsParser,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def sauvegarder_resultat_complet(
    db: Session,
    dto: ResultatExtractionDTO,
    *,
    bulletin_numero: str,
    page_source: int,
    publication_id: int | None = None,
    marche_id: int | None = None,
    resolver: EntityResolver | None = None,
) -> ResultatAttribution:
    """Enregistre de manière strictement idempotente un résultat d'attribution complet."""
    if resolver is None:
        resolver = EntityResolver(db)

    # 1. Recherche idempotente du ResultatAttribution parent
    query = db.query(ResultatAttribution).filter(ResultatAttribution.bulletin_numero == str(bulletin_numero))
    if dto.reference_dossier:
        query = query.filter(ResultatAttribution.reference_dossier == dto.reference_dossier)
    else:
        query = query.filter(ResultatAttribution.objet == dto.objet)

    resultat_db = query.first()

    if resultat_db is None:
        resultat_db = ResultatAttribution(
            publication_id=publication_id,
            marche_id=marche_id,
            bulletin_numero=str(bulletin_numero),
            page_source=page_source,
            autorite_contractante=dto.autorite_contractante[:255],
            reference_dossier=dto.reference_dossier[:255] if dto.reference_dossier else None,
            objet=dto.objet,
            date_attribution=dto.date_attribution,
            statut_deliberation=dto.statut_deliberation[:50],
            raw_source_snippet=dto.snippet_source,
        )
        db.add(resultat_db)
        db.flush()
    else:
        # Mise à jour des métadonnées sans créer de doublon
        resultat_db.page_source = page_source
        resultat_db.autorite_contractante = dto.autorite_contractante[:255]
        resultat_db.statut_deliberation = dto.statut_deliberation[:50]
        if dto.date_attribution:
            resultat_db.date_attribution = dto.date_attribution
        if publication_id and not resultat_db.publication_id:
            resultat_db.publication_id = publication_id
        if marche_id and not resultat_db.marche_id:
            resultat_db.marche_id = marche_id

    # 2. Gestion des lots
    for lot_dto in dto.lots:
        lot_db = (
            db.query(LotResultat)
            .filter(
                LotResultat.resultat_attribution_id == resultat_db.id,
                LotResultat.numero_lot == str(lot_dto.numero_lot),
            )
            .first()
        )
        if lot_db is None:
            lot_db = LotResultat(
                resultat_attribution_id=resultat_db.id,
                numero_lot=str(lot_dto.numero_lot)[:50],
                intitule_lot=lot_dto.intitule_lot,
                montant_estime=lot_dto.montant_estime,
                statut_lot=lot_dto.statut_lot[:50],
            )
            db.add(lot_db)
            db.flush()
        else:
            lot_db.intitule_lot = lot_dto.intitule_lot
            lot_db.statut_lot = lot_dto.statut_lot[:50]
            if lot_dto.montant_estime:
                lot_db.montant_estime = lot_dto.montant_estime

        # 3. Gestion des soumissionnaires du lot
        for s_dto in lot_dto.soumissionnaires:
            # Réconciliation d'entités stricte (Règle d'Or n°2)
            recon: ReconciliationResult = resolver.reconcilier(
                s_dto.nom_entreprise_brut,
                ifu_extrait=s_dto.ifu,
                rccm_extrait=s_dto.rccm,
            )

            from sqlalchemy import or_
            soum_db = (
                db.query(SoumissionnaireResultat)
                .filter(
                    SoumissionnaireResultat.lot_resultat_id == lot_db.id,
                    or_(
                        SoumissionnaireResultat.nom_entreprise_brut == s_dto.nom_entreprise_brut[:255],
                        SoumissionnaireResultat.nom_entreprise_normalise == s_dto.nom_entreprise_normalise[:255],
                    ),
                )
                .first()
            )

            if soum_db is None:
                soum_db = SoumissionnaireResultat(
                    lot_resultat_id=lot_db.id,
                    entreprise_id=recon.entreprise_id if recon.est_certain else None,
                    nom_entreprise_brut=s_dto.nom_entreprise_brut[:255],
                    nom_entreprise_normalise=s_dto.nom_entreprise_normalise[:255],
                    ifu_extrait=s_dto.ifu[:30] if s_dto.ifu else None,
                    rccm_extrait=s_dto.rccm[:50] if s_dto.rccm else None,
                    statut=s_dto.statut[:30],
                    est_attributaire=s_dto.est_attributaire,
                    rang_classement=s_dto.rang_classement,
                    montant_lu=s_dto.montant_lu,
                    montant_corrige=s_dto.montant_corrige,
                    delai_execution=s_dto.delai_execution[:100] if s_dto.delai_execution else None,
                    motif_rejet=s_dto.motif_rejet,
                    score_matching=recon.score,
                    methode_matching=recon.methode[:50],
                    statut_reconciliation=recon.statut[:30],
                )
                db.add(soum_db)
            else:
                # Sanctuarisation : si le soumissionnaire a été qualifié par l'analyse ciblée IA, ne JAMAIS l'écraser
                if getattr(soum_db, "methode_matching", None) == "RECHERCHE_CIBLEE_IA":
                    continue

                # Mise à jour idempotente standard pour les tiers
                soum_db.nom_entreprise_brut = s_dto.nom_entreprise_brut[:255]
                soum_db.nom_entreprise_normalise = s_dto.nom_entreprise_normalise[:255]
                soum_db.est_attributaire = s_dto.est_attributaire
                soum_db.statut = s_dto.statut[:30]
                soum_db.montant_lu = s_dto.montant_lu
                soum_db.montant_corrige = s_dto.montant_corrige
                soum_db.motif_rejet = s_dto.motif_rejet
                soum_db.score_matching = recon.score
                soum_db.methode_matching = recon.methode[:50]
                soum_db.statut_reconciliation = recon.statut[:30]
                if recon.est_certain:
                    soum_db.entreprise_id = recon.entreprise_id

    # 4. Rétrocompatibilité (Règle d'Or n°4) : synchronisation avec l'ancienne table Resultat si applicable
    if marche_id:
        premier_lot = dto.lots[0] if dto.lots else None
        attributaire = next((s for s in premier_lot.soumissionnaires if s.est_attributaire), None) if premier_lot else None
        if attributaire:
            ancien_res = db.query(Resultat).filter(Resultat.marche_id == marche_id).first()
            if ancien_res is None:
                recon_attr = resolver.reconcilier(attributaire.nom_entreprise_brut, ifu_extrait=attributaire.ifu, rccm_extrait=attributaire.rccm)
                ancien_res = Resultat(
                    marche_id=marche_id,
                    date_attribution=dto.date_attribution,
                    entreprise_attributaire_nom=attributaire.nom_entreprise_brut[:255],
                    entreprise_attributaire_id=recon_attr.entreprise_id if recon_attr.est_certain else None,
                    montant_attribue=float(attributaire.montant_corrige or attributaire.montant_lu) if (attributaire.montant_corrige or attributaire.montant_lu) else None,
                )
                db.add(ancien_res)

    db.commit()
    db.refresh(resultat_db)
    return resultat_db


def process_sections_resultats(
    db: Session,
    sections: list[dict],
    *,
    bulletin_numero: str,
    publication_id: int | None = None,
    client_llm: Any = None,
) -> dict[str, int]:
    """Parcourt les sections textuelles d'un bulletin et extrait les résultats d'attribution."""
    resolver = EntityResolver(db)
    stats = {
        "sections_examinees": len(sections),
        "resultats_extraits": 0,
        "lots_extraits": 0,
        "soumissionnaires_extraits": 0,
        "reconciliations_certaines": 0,
        "a_verifier": 0,
        "non_assignes": 0,
    }

    for idx, sec in enumerate(sections, start=1):
        texte = sec.get("texte") or sec.get("text") or ""
        page_num = sec.get("page_number") or 1

        if not TabularResultatsParser.est_section_resultat(texte):
            continue

        try:
            dtos = TabularResultatsParser.extraire_resultats_section(texte, client_llm=client_llm)
            for dto in dtos:
                if not dto or not dto.lots:
                    continue

                res_db = sauvegarder_resultat_complet(
                    db,
                    dto,
                    bulletin_numero=bulletin_numero,
                    page_source=page_num,
                    publication_id=publication_id,
                    resolver=resolver,
                )

                stats["resultats_extraits"] += 1
                for lot in dto.lots:
                    stats["lots_extraits"] += 1
                    for s in lot.soumissionnaires:
                        stats["soumissionnaires_extraits"] += 1
                        recon = resolver.reconcilier(s.nom_entreprise_brut, ifu_extrait=s.ifu, rccm_extrait=s.rccm)
                        if recon.est_certain:
                            stats["reconciliations_certaines"] += 1
                        elif recon.statut == "A_VERIFIER":
                            stats["a_verifier"] += 1
                        else:
                            stats["non_assignes"] += 1

        except Exception as exc:
            db.rollback()
            logger.error("Erreur lors de l'extraction de résultat sur la section %d (page %d) : %s", idx, page_num, exc)

    return stats


def extract_resultats(
    bulletin_ref: str,
    *,
    bulletin_numero_override: str | None = None,
    client_llm: Any = None,
) -> dict[str, int]:
    """Point d'entrée principal pour extraire les résultats d'un bulletin depuis MinIO, un fichier local ou Qdrant."""
    if bulletin_numero_override:
        bulletin_numero = str(bulletin_numero_override).strip()
    else:
        m = re.search(r"(\d+)", Path(bulletin_ref).stem)
        bulletin_numero = m.group(1) if m else bulletin_ref.strip()

    sections: list[dict] = []
    db = SessionLocal()

    try:
        # Récupération ou création de la publication associée
        publication = None
        if bulletin_numero:
            publication = db.query(Publication).filter(Publication.numero == str(bulletin_numero)).first()
            if publication is None:
                publication = Publication(
                    numero=str(bulletin_numero),
                    titre=f"Quotidien des Marchés Publics N° {bulletin_numero}",
                    date_publication=date.today(),
                    source="DGCMEF",
                )
                db.add(publication)
                db.commit()
                db.refresh(publication)

        # 1. Tentative d'extraction native du PDF (Local ou MinIO)
        pdf_bytes: bytes | None = None
        local_path = Path(bulletin_ref)
        if local_path.is_file():
            try:
                pdf_bytes = local_path.read_bytes()
                logger.info("Fichier PDF local trouvé et chargé : %s (%d octets)", local_path, len(pdf_bytes))
            except Exception as exc:
                logger.warning("Lecture du fichier local %s impossible : %s", local_path, exc)
        elif bulletin_ref.endswith(".pdf") or "/" in bulletin_ref or "\\" in bulletin_ref:
            logger.warning(
                "Le fichier spécifié '%s' est introuvable sur le disque du conteneur. "
                "Si vous venez de reconstruire ou redémarrer le conteneur, pensez à recopier le fichier : "
                "docker compose cp \"Quotidien N°4480.pdf\" api:/tmp/quotidien_4480.pdf",
                bulletin_ref,
            )

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

        if pdf_bytes:
            try:
                import fitz
                doc = fitz.open(stream=pdf_bytes, filetype="pdf")
                total_pages = len(doc)
                logger.info("Ouverture de %s réussie via PyMuPDF (%d pages au total).", bulletin_ref, total_pages)
                try:
                    for page_idx, page in enumerate(doc, start=1):
                        texte = page.get_text().strip()
                        if texte:
                            sections.append({"page_number": page_idx, "texte": texte})
                    logger.info("%d pages avec texte récupérées sur %d pages.", len(sections), total_pages)
                finally:
                    doc.close()
            except Exception as exc:
                logger.warning("Erreur lors de la lecture PyMuPDF de %s : %s", bulletin_ref, exc)

            # Synchronisation MinIO automatique pour affichage immédiat dans le Dashboard
            if bulletin_numero:
                try:
                    from ingestion import config as ingestion_config
                    from ingestion.config import upload_bytes
                    m_client = ingestion_config.build_minio_client()
                    target_key = f"pdf/quotidien/{bulletin_numero}.pdf"
                    upload_bytes(m_client, ingestion_config.MINIO_BUCKET, target_key, pdf_bytes, "application/pdf")
                    logger.info("PDF synchronisé dans MinIO sous '%s' (bucket: %s).", target_key, ingestion_config.MINIO_BUCKET)
                except Exception as m_exc:
                    logger.debug("Synchronisation MinIO automatique : %s", m_exc)

        # 2. Fallback vers Qdrant si aucune section récupérée du PDF
        if not sections:
            try:
                from ingestion import qdrant_store
                from api.scripts.extract_bulletin import _group_by_section
                qdrant_client = qdrant_store.get_client()
                chunks = qdrant_store.scroll_by_source(qdrant_client, bulletin_ref)
                if chunks:
                    groupes = _group_by_section(chunks)
                    sections = [{"page_number": g.page_number, "texte": g.texte} for g in groupes]
            except Exception as exc:
                logger.debug("Fallback Qdrant non disponible pour %s : %s", bulletin_ref, exc)

        logger.info(
            "Traitement des résultats d'attribution pour le bulletin n°%s (%d sections trouvées)",
            bulletin_numero,
            len(sections),
        )

        # Extraction STRICTEMENT ciblée sur les entreprises abonnées de la base de données
        # (Aucun gaspillage de tokens sur les tiers, aucun fallback, opération exacte)
        entreprises_enregistrees = db.query(Entreprise).all()
        logger.info(
            "Recherche ciblée insensible à la casse pour %d entreprise(s) de la base...",
            len(entreprises_enregistrees),
        )
        taches_client = detecter_mentions_entreprises(sections, entreprises_enregistrees)
        logger.info("%d mention(s) d'entreprises détectée(s) dans le bulletin n°%s.", len(taches_client), bulletin_numero)

        analyses_ia = executer_analyses_ia_paralleles(taches_client, client_llm=client_llm, max_workers=5)
        logger.info("%d interprétation(s) IA confirmée(s) pour les entreprises clientes.", len(analyses_ia))

        resultats_sauvegardes = 0
        for ent, section, ai_res in analyses_ia:
            try:
                sauvegarder_resultat_client(
                    db,
                    entreprise=ent,
                    section=section,
                    ai_res=ai_res,
                    bulletin_numero=bulletin_numero,
                    publication_id=publication.id if publication else None,
                )
                resultats_sauvegardes += 1
            except Exception as exc:
                db.rollback()
                logger.error("Erreur lors de la sauvegarde du résultat pour %s : %s", ent.nom, exc)

        stats = {
            "sections_examinees": len(sections),
            "mentions_entreprises_detectees": len(taches_client),
            "analyses_ia_executees": len(analyses_ia),
            "resultats_enregistres": resultats_sauvegardes,
        }
        return stats

    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(
        description="Extrait et réconcilie les résultats d'attribution d'un bulletin (DGCMEF)"
    )
    parser.add_argument(
        "bulletin_ref",
        nargs="?",
        default=None,
        help="Chemin MinIO, chemin local ou numéro du bulletin (ex: pdf/quotidien/4458.pdf ou 4458)",
    )
    parser.add_argument("--pdf", dest="pdf_path", default=None, help="Chemin vers le fichier PDF local")
    parser.add_argument("--bulletin", dest="bulletin_num", default=None, help="Numéro du bulletin (ex: 4480)")
    args = parser.parse_args()

    ref = args.pdf_path or args.bulletin_ref or args.bulletin_num
    if not ref:
        parser.error("Veuillez spécifier la référence du bulletin ou le chemin du fichier PDF (--pdf ou argument positionnel).")

    stats = extract_resultats(ref, bulletin_numero_override=args.bulletin_num)
    print(f"Extraction des résultats terminée pour {ref} : {stats}")


if __name__ == "__main__":
    main()
