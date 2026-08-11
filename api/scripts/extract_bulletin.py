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
from api.models.backend import AppelOffre, Marche, Publication, Resultat, TypeProcedure
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


# Detecte les tableaux administratifs (repertoire de fournisseurs, evaluation de recevabilite)
# dont le nom d'une entreprise est mal identifie comme titre d'avis par le chunking (cf.
# ingestion/chunking.py, _is_heading), et que le LLM, prive de tout avis reel a en extraire,
# invente de toutes pieces plutot que de repondre par un tableau vide comme demande - constate
# deux fois en reel sur les bulletins n°4459/4460, avec deux avis totalement fabriques
# ("Fourniture de materiel informatique pour les services de la primature", "Avis de marche pour
# la fourniture de materiel informatique", aucun des deux ne correspondant a un texte reel).
# Le numero IFU (8 chiffres + 1 lettre, parfois separe par une espace insecable du PDF, ex.
# "00223311 U" au lieu de "00223311U") est un signal distinctif : present dans les deux cas reels
# rencontres, absent des tableaux d'evaluation technique/prix (ex. celui qui a produit avec succes
# le resultat FZ SERVICES SARL sur le bulletin n°4458 - pas de colonne IFU dans ce format-la).
# Volontairement PAS de detection par vocabulaire "Conforme"/"Retenu" seul : ce vocabulaire
# apparait aussi dans des resultats legitimes a plusieurs lots (dont FZ SERVICES SARL), qu'on ne
# veut surtout pas exclure de l'extraction.
_IFU_PATTERN = re.compile(r"\b\d{8}\s?[A-Z]\b")
_SEUIL_REPERTOIRE = 2


def _semble_repertoire_fournisseurs(texte: str) -> bool:
    return len(_IFU_PATTERN.findall(texte)) >= _SEUIL_REPERTOIRE


# Constate en reel sur les bulletins n°4459 et n°4460 : certaines sections issues du regroupement
# par blocs contigus (cf. _group_by_section) ne contiennent QUE l'en-tete de page repete sur
# chaque page du bulletin ("N°3827 - lundi 04 Mars 2024 / {page} / N°4460 - ... / www.dgcmef...
# www.finances...") - constate entre 64 et 151 caracteres selon les variantes d'espacement du
# gabarit, aucun contenu reel. Prive de tout avis a extraire, le LLM en a invente un de toutes
# pieces au lieu de repondre par un tableau vide, alors que ce n'est meme pas un tableau
# administratif (donc invisible a _semble_repertoire_fournisseurs) : juste du vide. Seuil fixe a
# 200 avec une marge large au-dessus des variantes d'en-tete observees (151 max) : un avis reel
# (organisme + objet + reference + financement) tient toujours sur plusieurs centaines de
# caracteres au minimum.
_LONGUEUR_MIN_SECTION = 200


def _semble_trop_courte(texte: str) -> bool:
    return len(texte.strip()) < _LONGUEUR_MIN_SECTION


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


# Vocabulaire DGCMEF constate en reel (bulletin n°4458) comme fiable et systematique pour
# distinguer un resultat d'un appel d'offres - contrairement a la classification du LLM sur le
# *sens* du texte (qui peut halluciner un avis absent, ou mal trancher sur une section ambigue),
# ces formulations sont des marqueurs administratifs quasi-fixes du gabarit DGCMEF.

_MARQUEURS_RESULTAT = re.compile(
    r"a ete declaree? attributaire|attributaire|"
    r"resultats? (provisoires?|definitifs?)|resultats? de l.(ami|consultation)|"
    r"proces-verbal d.attribution|non conforme|"
    r"ecartee du classement",
    re.IGNORECASE,
)

# Volontairement PAS de "demande de prix n°..." ici (retire suite a l'audit du 09/08/2026) : ce
# gabarit sert de citation d'en-tete IDENTIQUE dans les DEUX types d'avis - un resultat cite
# systematiquement "Demande de prix n°XXX du DATE pour/relative a <objet>" pour rappeler de quel
# appel il presente le resultat, exactement comme le fait un nouvel appel. Le garder ici rendait
# "ambigu" (donc laisse a la merci du LLM) la quasi-totalite des vrais resultats de demande de
# prix, qui contiennent pourtant deja un marqueur resultat fiable (attributaire, non conforme...)
# neutralise par cette fausse ambiguite - cause reelle de ~15 marches de resultat mal classes en
# appel d'offre sur les bulletins 4457-4461, dont deux ayant deja genere de fausses alertes.
_MARQUEURS_APPEL_OFFRE = re.compile(
    r"avis d.appel d.offres?|avis a manifestation d.interet|"
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


def _find_entreprise_attributaire(db: Session, avis: AvisExtrait) -> Entreprise | None:
    """Rapproche l'attributaire d'un resultat avec une Entreprise inscrite, par ordre de fiabilite
    decroissante : RCCM et IFU (identifiants officiels uniques, quasi jamais presents dans le
    texte mais une preuve quasi certaine quand ils le sont) avant le nom (correspondance
    approximative ILIKE, peut confondre deux entreprises au nom proche) et le telephone (dernier
    recours, le moins fiable - un numero peut changer ou etre partage). S'arrete au premier champ
    disponible qui trouve une correspondance plutot que d'essayer tous les champs, pour ne jamais
    laisser un champ moins fiable contredire un champ plus fiable deja tranche. Ne cree jamais
    d'entreprise tierce (cf. plan : Entreprise exige un owner, pas de place pour un tiers
    non-inscrit). `.first()` plutot que `.one_or_none()` : le telephone et le nom n'ont pas de
    contrainte d'unicite en base, une correspondance en double ne doit jamais faire planter
    l'extraction."""
    if avis.entreprise_attributaire_rccm:
        entreprise = (
            db.query(Entreprise).filter(Entreprise.rccm == avis.entreprise_attributaire_rccm).first()
        )
        if entreprise is not None:
            return entreprise

    if avis.entreprise_attributaire_ifu:
        entreprise = (
            db.query(Entreprise)
            .filter(Entreprise.numero_identification == avis.entreprise_attributaire_ifu)
            .first()
        )
        if entreprise is not None:
            return entreprise

    if avis.entreprise_attributaire_nom:
        entreprise = (
            db.query(Entreprise).filter(Entreprise.nom.ilike(f"%{avis.entreprise_attributaire_nom}%")).first()
        )
        if entreprise is not None:
            return entreprise

    if avis.entreprise_attributaire_telephone:
        entreprise = (
            db.query(Entreprise)
            .filter(Entreprise.telephone == avis.entreprise_attributaire_telephone)
            .first()
        )
        if entreprise is not None:
            return entreprise

    return None


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
            entreprise = _find_entreprise_attributaire(db, avis)
            resultat = Resultat(
                marche_id=marche.id,
                date_attribution=parse_llm_date(avis.date_avis),
                entreprise_attributaire_nom=avis.entreprise_attributaire_nom,
                entreprise_attributaire_id=entreprise.id if entreprise else None,
                montant_attribue=avis.montant_attribue,
            )
            db.add(resultat)
            db.commit()
    elif avis.type_avis == "appel_offre":
        # AvisExtrait ne capture pas encore les champs specifiques a l'appel d'offre (date de
        # depot, reference du dossier...) - seule la ligne d'extension existe pour l'instant, afin
        # que le marche soit au moins correctement marque comme "appel d'offre" plutot que de
        # rester une simple ligne Marche sans extension (ce qui laissait la table appels_offre et
        # le site admin vides malgre des marches bien extraits).
        appel_offre = db.query(AppelOffre).filter(AppelOffre.marche_id == marche.id).one_or_none()
        if appel_offre is None:
            db.add(AppelOffre(marche_id=marche.id))
            db.commit()

    return marche


def extract_bulletin(object_name: str) -> int:
    qdrant_client = qdrant_store.get_client()
    chunks = qdrant_store.scroll_by_source(qdrant_client, object_name)
    if not chunks:
        raise ValueError(f"Aucun chunk trouve dans Qdrant pour {object_name!r} - bulletin pas encore vectorise ?")

    tous_les_groupes = _group_by_section(chunks)
    groups = [
        s
        for s in tous_les_groupes
        if not _semble_ligne_de_tableau(s.label)
        and not _semble_repertoire_fournisseurs(s.texte)
        and not _semble_trop_courte(s.texte)
    ]
    nb_ignorees = len(tous_les_groupes) - len(groups)
    if nb_ignorees:
        print(f"{nb_ignorees} sections ignorees (tableaux/repertoires/sections trop courtes detectees avant tout appel LLM)")

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
