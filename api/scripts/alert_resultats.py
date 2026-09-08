"""Script d'exécution des alertes pour les résultats d'attribution d'un bulletin.

Règles d'Or appliquées :
- Règle 2 : Tolérance Zéro aux faux positifs (seules les réconciliations EXACT ou PROBABLE >= 0.85 sont notifiées).
- Règle 3 : Idempotence absolue (rejeu sans duplication ni réémission d'alerte).
- Règle 4 : Rétrocompatibilité et préservation du code existant.
- Règle 5 : Traçabilité complète et auditabilité des alertes émises.
- Règle 6 : Gestion défensive des erreurs par entreprise.
"""

from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

from api.database import SessionLocal
from api.services.resultats_notifier import notifier_tous_resultats_bulletin

logger = logging.getLogger(__name__)


def _extract_numero_publication(bulletin_ref: str) -> str:
    m = re.search(r"(\d+)", Path(bulletin_ref).stem)
    return m.group(1) if m else bulletin_ref.strip()


def _fetch_pdf_optional(bulletin_ref: str):
    """Télécharge le PDF depuis MinIO ou le disque local si disponible (best-effort)."""
    try:
        import fitz
    except ImportError:
        return None

    # 1. Vérifier si c'est un chemin local direct ou dans /tmp
    for candidate in [
        Path(bulletin_ref),
        Path(f"/tmp/quotidien_{bulletin_ref}.pdf"),
        Path(f"/tmp/bulletin_{bulletin_ref}.pdf"),
        Path(f"/tmp/{bulletin_ref}.pdf"),
    ]:
        if candidate.exists() and candidate.is_file():
            try:
                return fitz.open(candidate)
            except Exception:
                pass

    # 2. Vérifier MinIO
    try:
        from ingestion import config as ingestion_config
        client = ingestion_config.build_minio_client()
        object_name = Path(bulletin_ref).name
        response = client.get_object(ingestion_config.MINIO_BUCKET, object_name)
        try:
            return fitz.open(stream=response.read(), filetype="pdf")
        finally:
            response.close()
            response.release_conn()
    except Exception as exc:
        logger.debug("PDF non récupéré pour %s : %s", bulletin_ref, exc)
        return None


def alert_resultats(bulletin_ref: str, dry_run: bool = False) -> dict[str, int]:
    """Déclenche l'envoi des notifications d'attribution pour un bulletin donné."""
    # Extraire le numéro de bulletin (ex: "bulletin_4458.pdf" -> "4458", ou "4458" -> "4458")
    numero_match = _extract_numero_publication(bulletin_ref)
    numero_bulletin = numero_match if numero_match else bulletin_ref.strip()

    db = SessionLocal()
    pdf_doc = _fetch_pdf_optional(bulletin_ref) if not dry_run else None

    try:
        logger.info(
            "Démarrage des alertes résultats pour le bulletin n°%s (dry_run=%s)",
            numero_bulletin,
            dry_run,
        )
        stats = notifier_tous_resultats_bulletin(
            db,
            numero_bulletin,
            dry_run=dry_run,
            pdf_doc=pdf_doc,
        )
        return stats
    finally:
        db.close()
        if pdf_doc is not None:
            pdf_doc.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(
        description="Notifie les entreprises inscrites des résultats d'attribution parus au bulletin (DGCMEF)"
    )
    parser.add_argument(
        "bulletin_ref",
        nargs="?",
        default=None,
        help="Numéro du bulletin (ex: 4458) ou nom de fichier (ex: bulletin_4458.pdf)",
    )
    parser.add_argument(
        "--bulletin",
        dest="bulletin_num",
        default=None,
        help="Numéro du bulletin (ex: 4480)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche les alertes qui seraient envoyées sans émettre de message ni écrire d'AlerteResultat",
    )
    args = parser.parse_args()

    ref = args.bulletin_num or args.bulletin_ref
    if not ref:
        parser.error("Veuillez spécifier le numéro de bulletin (ex: 4480 ou --bulletin 4480).")

    stats = alert_resultats(ref, dry_run=args.dry_run)

    print("\n--- Synthèse des alertes d'attribution ---")
    print(f"Numéro de bulletin : {ref}")
    print(f"Mode : {'DRY-RUN (simulation)' if args.dry_run else 'ENVOI RÉEL'}")
    print(f"Résultats traités : {stats.get('resultats_traites', 0)}")
    print(f"Victoires notifiées : {stats.get('victoires_envoyees', 0)}")
    print(f"Échecs (REX) notifiés : {stats.get('echecs_envoyes', 0)}")
    print(f"Ignorés car A_VERIFIER (Règle n°2) : {stats.get('ignores_a_verifier', 0)}")
    print(f"Échecs d'envoi réseau/SMTP : {stats.get('echoues', 0)}")


if __name__ == "__main__":
    main()
