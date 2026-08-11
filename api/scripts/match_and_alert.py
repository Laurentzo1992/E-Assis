"""Etape 2 du pipeline d'analyse : deux mecanismes distincts selon la nature de l'avis matche.

- Resultats (attribution de marche) : priorite absolue au nom. `extract_bulletin.py` a deja
  resolu, a l'extraction, si l'entreprise attributaire nommee dans le PDF correspond a une
  entreprise inscrite (`Resultat.entreprise_attributaire_id`, ILIKE sur le nom). Aucune recherche
  semantique n'intervient ici : soit l'entreprise est explicitement designee gagnante, soit elle
  n'est pas alertee sur ce resultat. Raison : une recherche par similarite de profil sur un
  tableau de resultats (texte dense, plein de vocabulaire technique du secteur) matche sur le
  *sujet* du marche, pas sur qui l'a remporte - constate en reel sur le bulletin n°4458, ou le
  profil "informatique/securite" de LOGO SERVICES matchait un tableau d'evaluation de scanners
  dont l'attributaire (FZ SERVICES SARL) n'avait aucun rapport avec l'entreprise alertee.

- Appels d'offres (nouvelles offres a soumissionner) : recherche semantique par profil
  (domaines + secteurs de l'entreprise), comme avant, mais desormais restreinte aux `Marche` qui
  n'ont PAS de `Resultat` associe (donc jamais un tableau d'attribution) et comparee au texte
  structure `Marche.objet` (issu de l'extraction LLM, donc deja nettoye) plutot qu'au chunk brut.

Deux canaux d'envoi, chacun best-effort (l'echec de l'un n'empeche jamais l'autre) : WhatsApp
(Meta Cloud API, necessite un modele approuve - cf. api/whatsapp_client.py) et email (canal
interim en attendant cette approbation, cf. api/email_utils.py). Une `Alerte` n'est enregistree
que si au moins un canal a reellement reussi, avec `canal_alerte` listant lequel/lesquels.

Idempotent par (entreprise, publication, marche) : un meme marche ne redeclenche jamais un
second envoi pour la meme entreprise si la tache est rejouee (retry Airflow), mais une entreprise
peut recevoir plusieurs alertes distinctes pour plusieurs marches du meme bulletin.
"""

import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from qdrant_client.http import models as qmodels
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.config import settings
from api.email_utils import send_alert_email
from api.models.abonnement import Abonnement
from api.models.backend import Alerte, Marche, Publication, Resultat
from api.models.entreprise import Entreprise
from api.models.utilisateur import Utilisateur
from api.whatsapp_client import WhatsAppSendError, send_whatsapp_template
from ingestion import config as ingestion_config
from ingestion import qdrant_store
from llm_service.whatsapp_prompts import RedactionEchouee, resumer_objet

logger = logging.getLogger(__name__)

# Nombre max d'alertes "marche" (appel d'offre) envoyees a une meme entreprise pour un meme
# bulletin - garde-fou anti-spam au cas ou de tres nombreux marches depasseraient le seuil pour un
# profil tres large, tout en couvrant tous les cas reels observes (jamais plus de 2-3 candidats
# au-dessus du seuil sur les bulletins testes).
MAX_MATCHES_PAR_ENTREPRISE = 5


def _selectionner_marches_pertinents(similarites: np.ndarray, seuil: float, max_matches: int = MAX_MATCHES_PAR_ENTREPRISE) -> list[int]:
    """Indices (dans `similarites`) des marches a alerter pour une entreprise : tous ceux au-dessus
    de `seuil`, tries par score decroissant, plafonnes a `max_matches` - pas seulement le meilleur
    (argmax), qui ignorait silencieusement d'autres marches tout aussi pertinents (cf. docstring de
    module et cas reel SONABHY SOC/SAAS)."""
    top_indices = np.argsort(similarites)[::-1][:max_matches]
    return [int(idx) for idx in top_indices if similarites[idx] >= seuil]


def _fetch_bulletin_pdf(object_name: str) -> "fitz.Document | None":
    """Telecharge le PDF du bulletin depuis MinIO pour en extraire les pages jointes aux emails
    d'alerte. Best-effort : sans PDF, les emails partent quand meme, juste sans piece jointe."""
    # Importe ici (pas au niveau module) pour que ce fichier reste importable - et donc testable -
    # sur un environnement ou pymupdf n'est pas installe/fonctionnel (ex. venv hote Windows sans
    # les DLL requises), sans affecter l'usage reel (conteneur ingest, ou pymupdf fonctionne).
    import fitz  # pymupdf

    try:
        client = ingestion_config.build_minio_client()
        response = client.get_object(ingestion_config.MINIO_BUCKET, object_name)
        try:
            return fitz.open(stream=response.read(), filetype="pdf")
        finally:
            response.close()
            response.release_conn()
    except Exception as exc:
        logger.warning("Impossible de recuperer %s depuis MinIO pour la piece jointe email : %s", object_name, exc)
        return None


def _render_page_png(pdf_doc: "fitz.Document | None", page_number: int | None) -> bytes | None:
    if pdf_doc is None or page_number is None or not (1 <= page_number <= pdf_doc.page_count):
        return None
    pixmap = pdf_doc[page_number - 1].get_pixmap(dpi=200)
    return pixmap.tobytes("png")


def _build_profile_text(entreprise: Entreprise) -> str:
    libelles = [d.libelle for d in entreprise.domaines] + [s.nom for s in entreprise.secteurs]
    return ", ".join(libelles)


def _active_entreprises(db: Session) -> list[Entreprise]:
    # Le telephone n'est plus requis ici : l'email (canal toujours disponible, adresse deja
    # verifiee a l'activation du compte) prend le relais quand WhatsApp n'est pas configurable.
    # Abonnement : essai gratuit ou abonnement paye encore valide uniquement (cf.
    # api/routers/paiement.py) - une entreprise sans essai/abonnement en cours ne doit jamais etre
    # alertee, meme si ses notifications sont actives.
    maintenant = datetime.now(timezone.utc)
    return (
        db.query(Entreprise)
        .join(Utilisateur, Entreprise.owner_id == Utilisateur.id)
        .join(Abonnement, Abonnement.entreprise_id == Entreprise.id)
        .filter(
            Utilisateur.notifications_actives.is_(True),
            or_(
                Abonnement.date_fin_essai > maintenant,
                and_(Abonnement.statut == "actif", Abonnement.date_fin_abonnement > maintenant),
            ),
        )
        .all()
    )


def _marches_appel_offre(db: Session, publication_id: int) -> list[Marche]:
    """Marches de ce bulletin sans Resultat associe - jamais un tableau d'attribution, seules
    eligibles au matching semantique par profil d'entreprise."""
    return (
        db.query(Marche)
        .outerjoin(Resultat, Resultat.marche_id == Marche.id)
        .filter(Marche.publication_id == publication_id, Resultat.marche_id.is_(None))
        .all()
    )


def _resultats_gagnes(db: Session, publication_id: int, entreprise_id: int) -> list[Resultat]:
    return (
        db.query(Resultat)
        .join(Marche, Marche.id == Resultat.marche_id)
        .filter(Marche.publication_id == publication_id, Resultat.entreprise_attributaire_id == entreprise_id)
        .all()
    )


def _already_alerted(db: Session, entreprise_id: int, publication_id: int, marche_id: int) -> bool:
    return (
        db.query(Alerte)
        .filter(
            Alerte.entreprise_id == entreprise_id,
            Alerte.publication_id == publication_id,
            Alerte.marche_id == marche_id,
        )
        .first()
        is not None
    )


def _locate_page(client, object_name: str, vector: list[float]) -> int | None:
    """Repli uniquement : les `Marche` extraits depuis ce correctif ont deja leur `page_number`
    connu avec certitude a l'extraction (cf. extract_bulletin._Section). Cette recherche
    semantique independante n'est utilisee que pour les marches extraits avant son introduction
    (page_number NULL en base) - elle peut se tromper de page sur un bulletin dense en vocabulaire
    de marches publics repete, constate en reel (page localisee sans rapport avec l'objet)."""
    results = client.query_points(
        collection_name=ingestion_config.COLLECTION_NAME,
        query=vector,
        query_filter=qmodels.Filter(
            must=[qmodels.FieldCondition(key="source_file", match=qmodels.MatchValue(value=object_name))]
        ),
        limit=1,
    ).points
    return results[0].payload.get("page_number") if results else None


def _format_montant(montant) -> str:
    if montant is None:
        return "montant non precise"
    return f"{montant:,.0f} FCFA".replace(",", " ")


def _resume_resultat(resultat: Resultat, marche: Marche) -> str:
    """Pas de LLM ici : l'objet et le montant viennent directement de l'extraction structuree -
    aucune reformulation, donc aucun risque de distorsion sur un fait deja etabli."""
    objet = marche.objet if len(marche.objet) <= 180 else marche.objet[:177] + "..."
    return f"Attributaire retenu pour : {objet} ({_format_montant(resultat.montant_attribue)})"


def _envoyer_alerte(
    db: Session,
    entreprise: Entreprise,
    publication: Publication,
    marche: Marche,
    type_alerte: str,
    resume: str,
    organisme: str,
    page_number: int | None,
    pdf_doc: "fitz.Document | None",
) -> bool:
    canaux_reussis: list[str] = []

    if entreprise.telephone:
        try:
            send_whatsapp_template(entreprise.telephone, parameters=[entreprise.nom, resume, organisme])
            canaux_reussis.append("whatsapp")
        except WhatsAppSendError as exc:
            logger.warning("Envoi WhatsApp echoue pour l'entreprise %s : %s", entreprise.id, exc)

    try:
        send_alert_email(
            entreprise.owner.email,
            entreprise.nom,
            resume,
            organisme,
            numero_bulletin=publication.numero,
            date_bulletin=publication.date_publication.strftime("%d/%m/%Y"),
            page_number=page_number,
            page_image=_render_page_png(pdf_doc, page_number),
        )
        canaux_reussis.append("email")
    except Exception as exc:  # SMTP injoignable, credentials invalides... jamais fatal
        logger.warning("Envoi email echoue pour l'entreprise %s : %s", entreprise.id, exc)

    if not canaux_reussis:
        return False

    db.add(
        Alerte(
            entreprise_id=entreprise.id,
            publication_id=publication.id,
            marche_id=marche.id,
            type_alerte=type_alerte,
            date_alerte=datetime.now(timezone.utc),
            contenu_alerte=resume,
            canal_alerte="+".join(canaux_reussis),
        )
    )
    db.commit()
    return True


def match_and_alert(object_name: str) -> int:
    # Importe ici (pas au niveau module) pour les memes raisons que `import fitz` dans
    # _fetch_bulletin_pdf : sentence-transformers/torch sont lourds et indisponibles sur certains
    # environnements hote (ex. VC++ Redistributable manquant sous Windows) - cette fonction reste
    # la seule a en avoir reellement besoin dans ce fichier.
    from ingestion.embed import embed_texts

    numero = Path(object_name).stem
    db = SessionLocal()
    nb_alertes = 0
    pdf_doc = None
    try:
        publication = db.query(Publication).filter(Publication.numero == numero).one_or_none()
        if publication is None:
            raise ValueError(
                f"Aucune Publication trouvee pour le numero {numero!r} - extract_bulletin.py a-t-il tourne avant ?"
            )

        qdrant_client = qdrant_store.get_client()
        pdf_doc = _fetch_bulletin_pdf(object_name)

        marches_appel_offre = _marches_appel_offre(db, publication.id)
        marche_vectors = embed_texts([m.objet for m in marches_appel_offre]) if marches_appel_offre else []
        marche_vectors_np = np.array(marche_vectors) if marche_vectors else None

        for entreprise in _active_entreprises(db):
            # 1. Resultats : le nom prime, deja resolu a l'extraction - pas de recherche semantique.
            for resultat in _resultats_gagnes(db, publication.id, entreprise.id):
                marche = resultat.marche
                if _already_alerted(db, entreprise.id, publication.id, marche.id):
                    continue
                resume = _resume_resultat(resultat, marche)
                organisme = marche.ministere or "DGCMEF"
                page_number = marche.page_number or _locate_page(
                    qdrant_client, object_name, embed_texts([marche.objet])[0]
                )
                if _envoyer_alerte(db, entreprise, publication, marche, "resultat", resume, organisme, page_number, pdf_doc):
                    nb_alertes += 1

            # 2. Appels d'offres : recherche semantique par profil (domaines + secteurs).
            if marche_vectors_np is None:
                continue
            profile_text = _build_profile_text(entreprise)
            if not profile_text:
                continue
            profile_vector = np.array(embed_texts([profile_text])[0])
            similarites = marche_vectors_np @ profile_vector

            for idx in _selectionner_marches_pertinents(similarites, settings.whatsapp_min_match_score):
                marche = marches_appel_offre[idx]
                if _already_alerted(db, entreprise.id, publication.id, marche.id):
                    continue

                try:
                    resume = resumer_objet(marche.objet)
                except RedactionEchouee as exc:
                    logger.warning("Redaction WhatsApp echouee pour l'entreprise %s : %s", entreprise.id, exc)
                    continue

                organisme = marche.ministere or "DGCMEF"
                page_number = marche.page_number or _locate_page(qdrant_client, object_name, marche_vectors[idx])
                if _envoyer_alerte(db, entreprise, publication, marche, "marche", resume, organisme, page_number, pdf_doc):
                    nb_alertes += 1
    finally:
        db.close()
        if pdf_doc is not None:
            pdf_doc.close()

    return nb_alertes


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse un bulletin et alerte les entreprises correspondantes")
    parser.add_argument("object_name")
    args = parser.parse_args()
    n = match_and_alert(args.object_name)
    print(f"{n} alertes envoyees (WhatsApp et/ou email) pour {args.object_name}")


if __name__ == "__main__":
    main()
