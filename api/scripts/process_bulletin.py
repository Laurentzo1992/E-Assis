"""Script unifié pour exécuter le traitement complet d'un bulletin DGCMEF :
1. Extraction & classification des Avis d'appels d'offres (avec alertes ciblées par domaine)
2. Extraction des Résultats d'attribution (avec réconciliation d'entreprises)
3. Notification des alertes de résultats d'attribution

Règles d'Or appliquées :
- Règle 1 : Déterminisme d'abord, IA en complément ciblé.
- Règle 2 : Tolérance Zéro aux faux positifs.
- Règle 3 : Idempotence absolue.
- Règle 4 : Préservation du code existant et rétrocompatibilité.
- Règle 5 : Traçabilité complète.
- Règle 6 : Gestion défensive des erreurs.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

from api.scripts.alert_resultats import main as alert_resultats_main
from api.scripts.extract_avis import extract_avis
from api.scripts.extract_resultats import extract_resultats

logger = logging.getLogger("process_bulletin")


def process_bulletin_complet(
    bulletin_ref: str,
    bulletin_numero_override: str | None = None,
    client_llm: Any = None,
    skip_avis: bool = False,
    skip_resultats: bool = False,
) -> dict[str, Any]:
    """Lance l'ensemble du traitement d'un bulletin (Avis + Résultats + Alertes)."""
    resume: dict[str, Any] = {
        "bulletin": bulletin_numero_override or bulletin_ref,
        "avis": None,
        "resultats": None,
        "alertes_resultats": None,
    }

    logger.info("======================================================================")
    logger.info("DÉMARRAGE TRAITEMENT COMPLET DU BULLETIN : %s", resume["bulletin"])
    logger.info("======================================================================")

    # 1. Pipeline AVIS d'appels d'offres
    if not skip_avis:
        logger.info("\n>>> ÉTAPE 1/3 : EXTRACTION DES AVIS D'APPELS D'OFFRES & ALERTES DOMAINES")
        try:
            resume["avis"] = extract_avis(
                bulletin_ref=bulletin_ref,
                bulletin_numero_override=bulletin_numero_override,
                client_llm=client_llm,
            )
        except Exception as exc:
            logger.error("Erreur lors de l'extraction des avis : %s", exc, exc_info=True)
            resume["avis"] = {"erreur": str(exc)}
    else:
        logger.info("\n>>> ÉTAPE 1/3 : Avis ignorés (--skip-avis)")

    # 2. Pipeline RÉSULTATS d'attribution
    if not skip_resultats:
        logger.info("\n>>> ÉTAPE 2/3 : EXTRACTION DES RÉSULTATS D'ATTRIBUTION (RÉCONCILIATION)")
        try:
            resume["resultats"] = extract_resultats(
                bulletin_ref=bulletin_ref,
                bulletin_numero_override=bulletin_numero_override,
                client_llm=client_llm,
            )
        except Exception as exc:
            logger.error("Erreur lors de l'extraction des résultats : %s", exc, exc_info=True)
            resume["resultats"] = {"erreur": str(exc)}

        logger.info("\n>>> ÉTAPE 3/3 : ÉMISSION DES ALERTES RÉSULTATS D'ATTRIBUTION")
        try:
            # Récupère le numéro de bulletin pour les alertes
            num = bulletin_numero_override
            if not num and resume.get("avis") and isinstance(resume["avis"], dict):
                num = resume["avis"].get("bulletin_numero")
            if not num:
                num = str(bulletin_ref)

            from api.services.resultats_notifier import notifier_tous_resultats_bulletin
            from api.database import SessionLocal
            with SessionLocal() as db:
                alertes_res = notifier_tous_resultats_bulletin(db, str(num))
                resume["alertes_resultats"] = {"notifications_envoyees": len(alertes_res)}
        except Exception as exc:
            logger.error("Erreur lors de l'émission des alertes de résultats : %s", exc, exc_info=True)
            resume["alertes_resultats"] = {"erreur": str(exc)}
    else:
        logger.info("\n>>> ÉTAPES 2 & 3 : Résultats ignorés (--skip-resultats)")

    logger.info("======================================================================")
    logger.info("FIN DU TRAITEMENT COMPLET DU BULLETIN : %s", resume["bulletin"])
    logger.info("Synthèse : %s", resume)
    logger.info("======================================================================")
    return resume


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Lance le traitement simultané d'un bulletin (Avis + Résultats + Alertes)"
    )
    parser.add_argument(
        "bulletin_ref",
        nargs="?",
        default=None,
        help="Chemin PDF ou référence du bulletin",
    )
    parser.add_argument("--pdf", dest="pdf_path", default=None, help="Chemin vers le fichier PDF local")
    parser.add_argument("--bulletin", "-b", dest="bulletin_num", default=None, help="Numéro du bulletin (ex: 4480)")
    parser.add_argument("--skip-avis", action="store_true", help="Ne pas traiter les avis d'appels d'offres")
    parser.add_argument("--skip-resultats", action="store_true", help="Ne pas traiter les résultats d'attribution")

    args = parser.parse_args()
    ref = args.pdf_path or args.bulletin_ref or args.bulletin_num
    if not ref:
        parser.error("Veuillez spécifier le fichier PDF ou le numéro de bulletin (--pdf ou argument positionnel).")

    res = process_bulletin_complet(
        bulletin_ref=ref,
        bulletin_numero_override=args.bulletin_num,
        skip_avis=args.skip_avis,
        skip_resultats=args.skip_resultats,
    )
    print(f"\nRésultat final : {res}")


if __name__ == "__main__":
    main()
