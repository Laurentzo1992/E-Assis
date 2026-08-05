"""Etape 1 du pipeline d'analyse : extrait les avis de marche/resultat d'un bulletin deja
vectorise dans Qdrant, et les enregistre en Postgres (Publication/Marche/TypeProcedure/Resultat).

Regroupe les chunks du bulletin par `section_title` (proxy d'un avis - cf. ingestion/chunking.py)
avant de les passer au LLM, plutot qu'un appel par chunk (445 chunks/bulletin serait la fois trop
lent et trop couteux en tokens pour peu de gain, un avis tenant generalement sur 2-3 chunks).
"""

import argparse
import logging
import re
import unicodedata
from datetime import date
from typing import Literal

from sqlalchemy.orm import Session

from api.database import SessionLocal
from api.models.backend import Marche, Publication, Resultat, TypeProcedure
from api.models.entreprise import Entreprise
from ingestion import qdrant_store
from llm_service.extraction_prompts import AvisExtrait, ExtractionEchouee, extraire_avis, parse_llm_date

logger = logging.getLogger(__name__)

# Filtre les sections dont le titre est une ligne de classement d'entreprises mal identifiee
# comme un titre d'avis (ex. "89 BEN MOUSTAPHA 7 SERVICES", "249 SCOOPS ALHMARIA") - constate en
# reel sur le bulletin n°4456 : ces sections representaient une bonne part des echecs
# d'extraction (le LLM tente quand meme d'y trouver un avis). Toutes commencent par un numero de
# ligne de tableau, jamais un vrai titre d'avis (organisme ou type de procedure).
_LIGNE_DE_TABLEAU = re.compile(r"^\d+\s")


def _semble_ligne_de_tableau(section_title: str | None) -> bool:
    return bool(section_title) and bool(_LIGNE_DE_TABLEAU.match(section_title))


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


# Vocabulaire DGCMEF constate en reel (bulletin n°4458) comme fiable et systematique pour
# distinguer un resultat d'un appel d'offres - contrairement a la classification du LLM sur le
# *sens* du texte (qui peut halluciner un avis absent, ou mal trancher sur une section ambigue),
# ces formulations sont des marqueurs administratifs quasi-fixes du gabarit DGCMEF.
_MARQUEURS_RESULTAT = re.compile(
    r"a ete declaree? attributaire|attributaire (provisoire|definitif)|"
    r"resultats? (provisoires?|definitifs?)|proces-verbal d.attribution|non conforme|"
    r"ecartee du classement",
    re.IGNORECASE,
)
_MARQUEURS_APPEL_OFFRE = re.compile(
    r"avis d.appel d.offres?|demande de prix n|avis a manifestation d.interet|"
    r"dossier d.appel d.offres?|appel a manifestation d.interet",
    re.IGNORECASE,
)


def _detecter_type_avis(texte: str) -> Literal["resultat", "appel_offre"] | None:
    """Detecte le type d'avis a partir de marqueurs textuels fixes, independamment de toute
    interpretation LLM. Retourne None si le texte est ambigu (les deux familles de marqueurs
    presentes, ex. une page qui enchaine un tableau de resultats puis un nouvel avis - frequent
    dans ce bulletin) ou si aucun marqueur n'est trouve - dans ces cas, on fait confiance au LLM."""
    texte_normalise = _sans_accents(texte)
    a_resultat = bool(_MARQUEURS_RESULTAT.search(texte_normalise))
    a_appel_offre = bool(_MARQUEURS_APPEL_OFFRE.search(texte_normalise))
    if a_resultat and not a_appel_offre:
        return "resultat"
    if a_appel_offre and not a_resultat:
        return "appel_offre"
    return None


def _corriger_type_avis(avis: AvisExtrait, texte_section: str, section_label: str) -> AvisExtrait:
    detecte = _detecter_type_avis(texte_section)
    if detecte is not None and detecte != avis.type_avis:
        logger.warning(
            "Type d'avis corrige pour la section %r : LLM a dit %r, marqueurs textuels indiquent %r",
            section_label, avis.type_avis, detecte,
        )
        avis = avis.model_copy(update={"type_avis": detecte})
    return avis


class _Section:
    __slots__ = ("label", "texte", "page_number")

    def __init__(self, label: str, texte: str, page_number: int):
        self.label = label
        self.texte = texte
        self.page_number = page_number


def _group_by_section(chunks: list[dict]) -> list[_Section]:
    """Regroupe les chunks en blocs *contigus* de meme section_title, jamais par titre global.

    Un dict classique (`grouped.setdefault(section_title, []).append(...)`) fusionnerait tous les
    chunks partageant le meme titre ou tous les chunks sans titre (`None`) en un seul groupe,
    meme s'ils sont separes de plusieurs pages et n'ont rien a voir - constate en reel sur le
    bulletin n°4458 : 44 chunks sans titre detecte, repartis sur 15 pages differentes, fusionnes
    en un seul bloc de ~40 000 caracteres passe au LLM en un seul appel - le resultat d'attribution
    de la page 10 (FZ SERVICES SARL) etait noye dedans et n'a jamais ete extrait. Meme probleme
    pour des organismes qui publient plusieurs avis distincts sous le meme intitule (ex. SONABHY,
    vu 5 fois a des endroits differents du bulletin) ou un titre generique repete par l'heuristique
    de detection de section (ex. "CRITERES DE SELECTION ET D'ATTRIBUTION", vu 7 fois).

    Chaque section garde la page de son premier chunk : c'est cette page, connue avec certitude a
    l'extraction, qui est ensuite stockee sur le `Marche` (cf. `_upsert_avis`) plutot que
    retrouvee plus tard par une recherche semantique independante - celle-ci peut se tromper de
    page des lors que le bulletin contient beaucoup de vocabulaire de marches publics repete
    (constate en reel : `match_and_alert.py` avait retrouve la page 28 - un avis SONABHY sans
    rapport - pour un marche dont l'objet n'apparaissait nulle part dans le bulletin, cf.
    hallucination LLM distincte, et la page 59 pour un autre marche etait correcte mais seulement
    par coincidence de vocabulaire).
    """
    ordered = sorted(chunks, key=lambda c: (c["page_number"], c["chunk_index"]))

    runs: list[tuple[str | None, list[str], int]] = []
    for chunk in ordered:
        title = chunk.get("section_title")
        if not runs or runs[-1][0] != title:
            runs.append((title, [], chunk["page_number"]))
        runs[-1][1].append(chunk["text"])

    occurrences: dict[str | None, int] = {}
    sections: list[_Section] = []
    for title, texts, page_number in runs:
        occurrences[title] = occurrences.get(title, 0) + 1
        label = title or "sans-titre"
        key = label if occurrences[title] == 1 else f"{label} #{occurrences[title]}"
        sections.append(_Section(key, "\n\n".join(texts), page_number))
    return sections


def _get_or_create_publication(db: Session, chunks: list[dict]) -> Publication:
    doc_number = chunks[0].get("doc_number") or "inconnu"
    doc_date_str = chunks[0].get("doc_date")
    publication = db.query(Publication).filter(Publication.numero == doc_number).one_or_none()
    if publication is not None:
        return publication

    date_publication = _parse_date_bulletin(doc_date_str) or date.today()
    publication = Publication(
        titre=f"Quotidien n°{doc_number}",
        numero=doc_number,
        date_publication=date_publication,
        source="DGCMEF",
        source_url=None,
        type_publication="quotidien",
    )
    db.add(publication)
    db.commit()
    db.refresh(publication)
    return publication


_MOIS_FR = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}
_DATE_BULLETIN_PATTERN = re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})")


def _parse_date_bulletin(doc_date_str: str | None) -> date | None:
    """doc_date vient de ingestion.extract.parse_doc_metadata, format 'Vendredi 31 juillet 2026'
    (capture deterministe, cf. le regex de parse_doc_metadata). Retourne None si absent ou
    inattendu plutot que de lever - une date de publication approximative (aujourd'hui) est
    preferable a l'echec complet de l'extraction pour ce seul champ."""
    if not doc_date_str:
        return None
    match = _DATE_BULLETIN_PATTERN.search(doc_date_str)
    if not match:
        return None
    jour, mois_nom, annee = match.groups()
    mois = _MOIS_FR.get(mois_nom.lower())
    if mois is None:
        return None
    try:
        return date(int(annee), mois, int(jour))
    except ValueError:
        return None


def _get_or_create_type_procedure(db: Session, libelle: str | None) -> TypeProcedure | None:
    if not libelle:
        return None
    type_procedure = db.query(TypeProcedure).filter(TypeProcedure.libelle == libelle).one_or_none()
    if type_procedure is None:
        type_procedure = TypeProcedure(libelle=libelle)
        db.add(type_procedure)
        db.commit()
        db.refresh(type_procedure)
    return type_procedure


def _find_entreprise_by_name(db: Session, nom: str) -> Entreprise | None:
    """Recherche approximative (insensible a la casse, correspondance partielle dans les deux
    sens) - ne cree jamais d'entreprise tierce, se contente de lier si un compte existant
    correspond (cf. plan : Entreprise exige un owner, pas de place pour un tiers non-inscrit)."""
    return (
        db.query(Entreprise)
        .filter(Entreprise.nom.ilike(f"%{nom}%"))
        .one_or_none()
    )


def _upsert_avis(db: Session, publication: Publication, avis: AvisExtrait, page_number: int) -> Marche:
    type_procedure = _get_or_create_type_procedure(db, avis.type_procedure)

    marche = (
        db.query(Marche)
        .filter(Marche.publication_id == publication.id, Marche.objet == avis.objet)
        .one_or_none()
    )
    if marche is None:
        marche = Marche(
            publication_id=publication.id,
            type_procedure_id=type_procedure.id if type_procedure else None,
            ministere=avis.organisme,
            objet=avis.objet,
            budget_min=avis.montant_min,
            budget_max=avis.montant_max,
            page_number=page_number,
        )
        db.add(marche)
        db.commit()
        db.refresh(marche)

    if avis.type_avis == "resultat":
        resultat = db.query(Resultat).filter(Resultat.marche_id == marche.id).one_or_none()
        if resultat is None:
            entreprise = (
                _find_entreprise_by_name(db, avis.entreprise_attributaire_nom)
                if avis.entreprise_attributaire_nom
                else None
            )
            resultat = Resultat(
                marche_id=marche.id,
                date_attribution=parse_llm_date(avis.date_avis),
                entreprise_attributaire_id=entreprise.id if entreprise else None,
                montant_attribue=avis.montant_attribue,
            )
            db.add(resultat)
            db.commit()

    return marche


def extract_bulletin(object_name: str) -> int:
    qdrant_client = qdrant_store.get_client()
    chunks = qdrant_store.scroll_by_source(qdrant_client, object_name)
    if not chunks:
        raise ValueError(f"Aucun chunk trouve dans Qdrant pour {object_name!r} - bulletin pas encore vectorise ?")

    tous_les_groupes = _group_by_section(chunks)
    groups = [s for s in tous_les_groupes if not _semble_ligne_de_tableau(s.label)]
    nb_ignorees = len(tous_les_groupes) - len(groups)
    if nb_ignorees:
        print(f"{nb_ignorees} sections ignorees (lignes de tableau detectees avant tout appel LLM)")

    db = SessionLocal()
    nb_marches = 0
    try:
        publication = _get_or_create_publication(db, chunks)
        for i, section in enumerate(groups, start=1):
            print(f"[{i}/{len(groups)}] extraction : {section.label!r}")
            try:
                avis_list = extraire_avis(section.texte)
                for avis in avis_list:
                    avis = _corriger_type_avis(avis, section.texte, section.label)
                    if avis.type_avis == "autre":
                        continue
                    _upsert_avis(db, publication, avis, section.page_number)
                    nb_marches += 1
            except ExtractionEchouee as exc:
                logger.warning("Extraction echouee pour la section %r : %s", section.label, exc)
            except Exception as exc:
                # Filet de securite : une erreur totalement imprevue sur une seule section (ex. un
                # element de reponse LLM d'une forme inattendue non couverte par _valider_avis) ne
                # doit jamais faire perdre le travail deja fait sur les autres sections - constate
                # en reel sur un bulletin de 181 sections ou une AttributeError non rattrapee sur
                # la section 70 a fait planter toute l'extraction, perdant les 69 sections deja
                # traitees (le retry Airflow repart de zero, pas de la section en echec).
                logger.error("Erreur inattendue pour la section %r : %s", section.label, exc)
    finally:
        db.close()

    return nb_marches


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrait les avis de marche d'un bulletin vectorise")
    parser.add_argument("object_name")
    args = parser.parse_args()
    n = extract_bulletin(args.object_name)
    print(f"{n} marches/resultats extraits et enregistres depuis {args.object_name}")


if __name__ == "__main__":
    main()
