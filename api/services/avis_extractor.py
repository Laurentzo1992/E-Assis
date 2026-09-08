"""Service d'extraction et de classification des Avis d'Appels d'Offres (DGCMEF).

Règles d'Or appliquées :
- Règle 1 : Déterminisme d'abord, IA en complément ciblé (analyse Sommaire page 2 + découpage par entêtes).
- Règle 2 : Tolérance zéro aux faux positifs (alertes ciblées strictement sur les entreprises du Domaine).
- Règle 3 : Idempotence absolue des pipelines (pas de doublons sur N réexécutions).
- Règle 4 : Préservation du code existant et rétrocompatibilité (aucun impact sur les résultats d'attribution).
- Règle 5 : Traçabilité complète et auditabilité (page_number exact conservé).
- Règle 6 : Gestion défensive des erreurs (aucun crash si aucun domaine trouvé ou si l'IA échoue).
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any

try:
    from sqlalchemy.orm import Session
    from api.models.backend import Alerte, AppelOffre, Marche, Publication
    from api.models.entreprise import Domaine, Entreprise, EntrepriseDomaine
except ImportError:
    Session = Any  # type: ignore
    Alerte = AppelOffre = Marche = Publication = Any  # type: ignore
    Domaine = Entreprise = EntrepriseDomaine = Any  # type: ignore

if TYPE_CHECKING:
    import fitz

logger = logging.getLogger(__name__)

# Entêtes de rubriques principales d'avis dans le Quotidien DGCMEF
_CATEGORIES_AVIS = [
    "Marchés de fournitures et services courants",
    "Fournitures et services courants",
    "Fournitures et services",
    "Marchés de travaux",
    "Travaux",
    "Marchés de prestations intellectuelles",
    "Prestations intellectuelles",
]

_PATTERN_CATEGORIE = re.compile(
    r"^(?:•\s*)?(March[eé]s?\s+de\s+fournitures\s+et\s+services\s+courants|Fournitures\s+et\s+services\s+courants|Fournitures\s+et\s+services|March[eé]s?\s+de\s+travaux|Travaux|March[eé]s?\s+de\s+prestations\s+intellectuelles|Prestations\s+intellectuelles)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Formulations annonçant le démarrage d'un avis d'appel d'offres
_PATTERN_DEBUT_AVIS = re.compile(
    r"(?:\bAvis\s+de\s+demande\s+de\s+prix\b|"
    r"\bAvis\s+d['’]appel\s+d['’]offres?\b|"
    r"\bAvis\s+[aà]\s+manifestation\s+d['’]int[eé]r[eê]t\b|"
    r"\bDemande\s+de\s+cotation\b|"
    r"\bAvis\s+de\s+pr[eé]-?qualification\b|"
    r"\bConsultation\s+de\s+consultants\b|"
    r"\bAvis\s+de\s+consultation\b)",
    re.IGNORECASE,
)

# Entêtes institutionnelles courantes au Burkina Faso
_PATTERN_AUTORITE_HEADER = re.compile(
    r"^(?:MINIST[EÈ]RE|COMMUNE\s+DE|R[EÉ]GION\s+DU|SOCI[EÉ]T[EÉ]\s+NATIONALE|AGENCE|DIRECTION\s+G[EÉ]N[EÉ]RALE|FONDS|AUTORIT[EÉ]|UNIVERSIT[EÉ]|CENTRE\s+HOSPITALIER|OFFICE)\b",
    re.IGNORECASE,
)

# Lignes récurrentes d'en-tête / pied de page du bulletin à filtrer
_PATTERN_PAGE_HEADER_FOOTER = re.compile(
    r"N°\s*\d+.*?(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche).*?www\.dgcmef\.gov\.bf|"
    r"www\.dgcmef\.gov\.bf.*?N°\s*\d+|"
    r"^\s*Quotidien\s+des\s+march[eé]s\s+publics\s*$",
    re.IGNORECASE,
)


@dataclass
class AvisMarcheDTO:
    """Représentation structurée d'un appel d'offres extrait du bulletin."""

    page_number: int
    categorie: str | None
    titre_ou_entete: str
    texte_complet: str
    autorite_contractante: str | None = None
    objet: str = ""
    reference_dossier: str | None = None
    date_depot: date | None = None
    budget_max: Decimal | None = None
    domaine_id: int | None = None
    domaine_nom: str | None = None


def sans_accents(texte: str) -> str:
    """Supprime les accents pour fiabiliser les comparaisons regex."""
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


# --- 1. Détection de la page de démarrage des Avis via le Sommaire (Page 2) ---


def detecter_page_debut_avis(
    texte_page_sommaire: str,
    client_llm: Any = None,
) -> int:
    """Détecte la page où démarre la section des AVIS d'appels d'offres.

    Applique d'abord une analyse déterministe par regex sur la page 2 (Règle 1).
    En cas d'échec ou d'ambiguïté, sollicite l'IA avec un prompt ciblé (Règle 1).
    Fallback de sécurité si tout échoue : page 70 par défaut.
    """
    if not texte_page_sommaire or not texte_page_sommaire.strip():
        logger.warning("Texte de sommaire vide. Utilisation du repli par défaut (page 70).")
        return 70

    # 1. Approche déterministe (Règle 1) : recherche du bloc "AVIS" dans le sommaire
    # Exemple observé dans les Quotidien DGCMEF :
    # "AVIS" suivi de "• Marchés de fournitures et services courants P. 70"
    match_avis_direct = re.search(
        r"\bAVIS\b[\s\S]*?(?:March[eé]s?\s+de\s+[^P\n]+|[•\-\*]\s*[^P\n]+)?P(?:age)?\.?\s*(\d+)",
        texte_page_sommaire,
        re.IGNORECASE,
    )
    if match_avis_direct:
        try:
            page_candidate = int(match_avis_direct.group(1))
            if 3 <= page_candidate <= 1000:
                logger.info("Détection déterministe de la page de début des avis : page %d", page_candidate)
                return page_candidate
        except (ValueError, TypeError):
            pass

    # Alternative déterministe : chercher directement le premier "Marchés de fournitures / travaux ... P. XX"
    match_rubrique = re.search(
        r"March[eé]s?\s+de\s+(?:fournitures|travaux|prestations)[^P\n]*P(?:age)?\.?\s*(\d+)",
        texte_page_sommaire,
        re.IGNORECASE,
    )
    if match_rubrique:
        try:
            page_candidate = int(match_rubrique.group(1))
            if 3 <= page_candidate <= 1000:
                logger.info("Détection déterministe par rubrique : page %d", page_candidate)
                return page_candidate
        except (ValueError, TypeError):
            pass

    # 2. Fallback IA ciblé : soumettre le texte de la page 2 au LLM (Règle 1)
    logger.info("Tentative de détection de la page de début des avis via le LLM...")
    try:
        from llm_service.llm_client import call_llm

        system_prompt = (
            "Tu es un assistant spécialisé dans l'analyse du Quotidien des marchés publics du Burkina Faso (DGCMEF). "
            "À partir du texte de sommaire (page 2), identifie le numéro de page EXACT où démarre la section des "
            "AVIS d'appels d'offres (fournitures, travaux ou prestations intellectuelles). "
            "Réponds UNIQUEMENT par un nombre entier (ex: 70), sans aucun mot, ponctuation ou explication supplémentaire. "
            "Si tu ne trouves pas, réponds UNIQUEMENT: null"
        )
        user_prompt = (
            f"TEXTE DU SOMMAIRE (PAGE 2) :\n```text\n{texte_page_sommaire[:3000].strip()}\n```\n\n"
            "Numéro de page exact où démarrent les AVIS :"
        )

        response = call_llm(
            task="extraction",
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
            client=client_llm,
        )
        content = (response.message.content or "").strip()
        match_digits = re.search(r"\b(\d+)\b", content)
        if match_digits:
            page_ia = int(match_digits.group(1))
            if 3 <= page_ia <= 1000:
                logger.info("Détection par IA réussie : page %d", page_ia)
                return page_ia
    except Exception as exc:
        logger.warning("Échec de l'appel LLM pour le sommaire : %s", exc)

    logger.warning("Impossible de déterminer la page exacte. Utilisation du repli par défaut (page 70).")
    return 70


# --- 2. Découpage unitaire des avis d'appels d'offres ---


def _est_debut_de_marche(ligne: str, lignes_suivantes: list[str]) -> bool:
    """Détermine si une ligne (et son contexte immédiat) marque le début d'un appel d'offres."""
    ligne_clean = ligne.strip()
    if not ligne_clean or len(ligne_clean) < 4:
        return False

    # Marqueur direct : "Avis de demande de prix", "Avis d'appel d'offres", etc.
    if _PATTERN_DEBUT_AVIS.search(ligne_clean):
        return True

    # Entête d'autorité suivie très rapidement (dans les 4 lignes suivantes) d'un titre d'avis ou objet
    if _PATTERN_AUTORITE_HEADER.search(ligne_clean):
        contexte = " ".join(lignes_suivantes[:4])
        if _PATTERN_DEBUT_AVIS.search(contexte) or re.search(r"\bObjet\s*:\b", contexte, re.IGNORECASE):
            return True

    return False


def _extraire_champs_heuristiques(lignes: list[str]) -> tuple[str, str | None, str | None, Decimal | None]:
    """Extrait l'objet, l'autorité, la référence et le budget max à partir des lignes de l'avis."""
    texte_joint = "\n".join(lignes)

    # 1. Autorité contractante
    autorite = None
    for ligne in lignes[:8]:
        l_str = ligne.strip()
        if _PATTERN_AUTORITE_HEADER.search(l_str):
            autorite = l_str
            break

    # 2. Objet du marché
    objet = ""
    # Cherche une mention explicite "Objet :"
    match_objet = re.search(r"\bObjet\s*:\s*([^\n]+(?:\n(?!\s*[A-ZÀ-ÖØ-ß]{3,}\b)[^\n]+)*)", texte_joint, re.IGNORECASE)
    if match_objet:
        objet = " ".join(match_objet.group(1).split())
    else:
        # Sinon prend les 2 à 4 premières lignes significatives (après l'autorité)
        lignes_utiles = [
            l.strip() for l in lignes[:10]
            if l.strip() and not _PATTERN_PAGE_HEADER_FOOTER.search(l) and not _PATTERN_DEBUT_AVIS.search(l)
        ]
        objet = " ".join(lignes_utiles[:3]) if lignes_utiles else "Appel d'offres sans titre spécifié"

    if len(objet) > 500:
        objet = objet[:497] + "…"

    # 3. Référence dossier
    reference = None
    match_ref = re.search(r"(?:R[eé]f[eé]rence|R[eé]f\.?|N°)\s*:?\s*([0-9A-Z\-_/]{4,30})", texte_joint, re.IGNORECASE)
    if match_ref:
        reference = match_ref.group(1).strip()

    # 4. Budget max si mentionné
    budget = None
    match_budget = re.search(r"(?:montant|budget|co[uû]t)\s*(?:estim[eé]|pr[eé]visionnel|plafond)?\s*:?\s*([\d\s.,]+)\s*(?:F\s*CFA|FCFA)", texte_joint, re.IGNORECASE)
    if match_budget:
        val_str = match_budget.group(1).replace(" ", "").replace(".", "").replace(",", "")
        try:
            budget = Decimal(val_str)
        except Exception:
            budget = None

    return objet, autorite, reference, budget


def decouper_avis_marches(
    doc: fitz.Document,
    page_debut: int,
    page_fin: int | None = None,
) -> list[AvisMarcheDTO]:
    """Parcourt les pages du document à partir de page_debut et segmente les appels d'offres.

    Principe de découpage (spécifié par l'utilisateur) :
    "un marché finit là où un autre commence, donc dès que la section des appels d'offres commence,
    entre deux entêtes de marché c'est un marché complet."
    """
    total_pages = len(doc)
    start_idx = max(0, page_debut - 1)
    end_idx = min(total_pages, page_fin) if page_fin else total_pages

    # Si la dernière page est une couverture de dos, on la conserve sauf si elle est quasi vide
    logger.info("Découpage des avis d'appels d'offres de la page %d à la page %d", start_idx + 1, end_idx)

    # Accumulateur d'étapes
    marches: list[AvisMarcheDTO] = []
    current_categorie: str | None = None
    current_page: int = page_debut
    current_lines: list[str] = []

    def _cloturer_marche_courant():
        nonlocal current_lines, current_page, current_categorie
        if not current_lines:
            return

        # Filtrer les lignes vides
        lignes_valides = [l for l in current_lines if l.strip() and not _PATTERN_PAGE_HEADER_FOOTER.search(l)]
        if len(lignes_valides) < 3:
            current_lines = []
            return

        # Extraire les 10 à 15 premières lignes pour le titre/entête
        titre_entete = "\n".join(lignes_valides[:15])
        texte_complet = "\n".join(lignes_valides)
        objet, autorite, ref, budget = _extraire_champs_heuristiques(lignes_valides)

        dto = AvisMarcheDTO(
            page_number=current_page,
            categorie=current_categorie,
            titre_ou_entete=titre_entete,
            texte_complet=texte_complet,
            autorite_contractante=autorite,
            objet=objet,
            reference_dossier=ref,
            budget_max=budget,
        )
        marches.append(dto)
        current_lines = []

    for page_idx in range(start_idx, end_idx):
        num_page_bulletin = page_idx + 1
        page = doc[page_idx]
        text = page.get_text("text") or ""
        lines = text.split("\n")

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Vérifier si c'est un changement de catégorie majeure (bannière de section)
            match_cat = _PATTERN_CATEGORIE.match(line)
            if match_cat:
                lignes_existantes = [l for l in current_lines if l.strip() and not _PATTERN_PAGE_HEADER_FOOTER.search(l)]
                if len(lignes_existantes) >= 3:
                    _cloturer_marche_courant()
                current_categorie = match_cat.group(1)
                i += 1
                continue

            # Vérifier si c'est le début d'un nouveau marché
            lignes_suivantes = [l.strip() for l in lines[i + 1 : i + 6] if l.strip()]
            if _est_debut_de_marche(line, lignes_suivantes):
                lignes_existantes = [l for l in current_lines if l.strip() and not _PATTERN_PAGE_HEADER_FOOTER.search(l)]
                # Un nouveau marché ne commence que si le précédent a au moins quelques lignes significatives
                if len(lignes_existantes) >= 3:
                    _cloturer_marche_courant()
                    current_page = num_page_bulletin
                elif not current_lines:
                    current_page = num_page_bulletin

            current_lines.append(line)
            i += 1

    # Clôturer le tout dernier marché
    _cloturer_marche_courant()

    logger.info("Nombre total de marchés d'appels d'offres découpés : %d", len(marches))
    return marches


# --- 3. Classification sémantique par l'IA parmi les Domaines en DB ---


def classifier_marche_par_domaine(
    titre_ou_entete: str,
    domaines: list[dict[str, Any]],
    client_llm: Any = None,
) -> int | None:
    """Interroge l'IA pour sélectionner précisément le domaine en DB correspondant au marché.

    RÈGLE ABSOLUE (Gestion défensive - Règle 6) :
    Si aucun domaine ne correspond, ou si l'IA renvoie null / échoue / génère une erreur,
    cette fonction renvoie None et NE DOIT JAMAIS FAIRE PLANTER le traitement.
    """
    if not domaines:
        logger.info("Aucun domaine d'activité configuré en base de données.")
        return None

    if not titre_ou_entete or not titre_ou_entete.strip():
        return None

    from llm_service.llm_client import call_llm

    # Préparer la liste compacte des domaines
    liste_domaines_str = json.dumps(
        [{"id": d["id"], "libelle": d["libelle"]} for d in domaines],
        ensure_ascii=False,
    )

    system_prompt = (
        "Tu es un expert senior en classification des marchés publics au Burkina Faso (DGCMEF).\n"
        "Ton rôle est d'associer un appel d'offres au DOMAINE D'ACTIVITÉ le plus pertinent parmi la liste fournie par l'administrateur.\n"
        "RÈGLES STRICTES :\n"
        "1. Tu dois choisir UNIQUEMENT un identifiant 'id' présent dans la liste fournie.\n"
        "2. Si AUCUN domaine de la liste ne correspond avec une certitude raisonnable, renvoie null pour 'domaine_id'.\n"
        "3. Ne force JAMAIS une correspondance douteuse : il vaut mieux renvoyer null que d'alerter une entreprise par erreur.\n"
        "4. Réponds STRICTEMENT au format JSON valide :\n"
        '{"domaine_id": <id ou null>, "justification": "<court motif>"}'
    )

    user_prompt = (
        f"LISTE DES DOMAINES DISPONIBLES EN BASE :\n{liste_domaines_str}\n\n"
        f"PREMIÈRES LIGNES DU MARCHÉ À CLASSIFIER :\n```text\n{titre_ou_entete.strip()}\n```\n\n"
        "Sélectionne l'id du domaine approprié (ou null si aucun) :"
    )

    try:
        response = call_llm(
            task="extraction",
            messages=[{"role": "user", "content": user_prompt}],
            system=system_prompt,
            client=client_llm,
        )
        content = (response.message.content or "").strip()
        # Extraction du bloc JSON
        match_json = re.search(r"\{[\s\S]*\}", content)
        if match_json:
            data = json.loads(match_json.group(0))
            dom_id = data.get("domaine_id")
            if dom_id is not None:
                try:
                    dom_id_int = int(dom_id)
                    ids_valides = {d["id"] for d in domaines}
                    if dom_id_int in ids_valides:
                        logger.info(
                            "Marché classifié avec succès dans le domaine ID %d (justification: %s)",
                            dom_id_int,
                            data.get("justification", ""),
                        )
                        return dom_id_int
                    else:
                        logger.warning("L'IA a renvoyé un domaine_id (%s) hors liste DB. Traité comme null.", dom_id)
                        return None
                except (ValueError, TypeError):
                    return None
            return None
        return None
    except Exception as exc:
        # Règle 6 : Gestion défensive des erreurs, jamais de plantage
        logger.warning("Échec de la classification IA du domaine (traité comme None sans erreur) : %s", exc)
        return None


# --- 4. Enregistrement idempotent et génération des alertes ciblées ---


def sauvegarder_marche_et_appel_offre(
    db: Session,
    dto: AvisMarcheDTO,
    publication: Publication,
) -> Marche:
    """Enregistre de manière strictement idempotente le Marché et son AppelOffre lié."""
    # Vérification d'unicité par publication_id + page_number + début de l'objet
    cle_objet = dto.objet[:80].strip().lower()
    marche_existant = (
        db.query(Marche)
        .filter(
            Marche.publication_id == publication.id,
            Marche.page_number == dto.page_number,
        )
        .all()
    )

    for m in marche_existant:
        if m.objet and m.objet[:80].strip().lower() == cle_objet:
            # Idempotence : marché déjà existant
            if dto.domaine_id and not m.domaine_id:
                m.domaine_id = dto.domaine_id
                db.commit()
                db.refresh(m)
            return m

    # Création du nouveau Marché
    nouveau_marche = Marche(
        publication_id=publication.id,
        page_number=dto.page_number,
        objet=dto.objet,
        ministere=dto.autorite_contractante,
        domaine_id=dto.domaine_id,
        budget_max=dto.budget_max,
    )
    db.add(nouveau_marche)
    db.flush()  # Pour obtenir nouveau_marche.id

    # Création de l'AppelOffre lié
    appel_offre = AppelOffre(
        marche_id=nouveau_marche.id,
        referenceDossier=dto.reference_dossier,
        dateDepot=dto.date_depot,
    )
    db.add(appel_offre)
    db.commit()
    db.refresh(nouveau_marche)

    logger.info(
        "Marché ID %d enregistré (page %d, domaine_id=%s) : %s",
        nouveau_marche.id,
        nouveau_marche.page_number,
        nouveau_marche.domaine_id,
        nouveau_marche.objet[:60],
    )
    return nouveau_marche


def alerter_entreprises_pour_marche(
    db: Session,
    marche: Marche,
    publication: Publication,
) -> list[Alerte]:
    """Génère les alertes pour toutes les entreprises du domaine associé au marché.

    Règles d'Or appliquées :
    - Règle 2 : Aucune alerte émise si le marché n'a aucun domaine_id (tolérance zéro aux faux positifs).
    - Règle 3 : Idempotence stricte (aucun doublon d'alerte pour une même entreprise sur le même marché).
    """
    if not marche.domaine_id:
        logger.info("Marché ID %d sans domaine_id : aucune alerte émise.", marche.id)
        return []

    # Recherche des entreprises inscrites dans ce domaine
    entreprises = (
        db.query(Entreprise)
        .join(EntrepriseDomaine, Entreprise.id == EntrepriseDomaine.entreprise_id)
        .filter(EntrepriseDomaine.domaine_id == marche.domaine_id)
        .all()
    )

    if not entreprises:
        logger.info("Aucune entreprise inscrite dans le domaine ID %d.", marche.domaine_id)
        return []

    alertes_creees: list[Alerte] = []
    for ent in entreprises:
        # Vérification d'idempotence (Règle 3)
        alerte_existante = (
            db.query(Alerte)
            .filter(
                Alerte.entreprise_id == ent.id,
                Alerte.publication_id == publication.id,
                Alerte.marche_id == marche.id,
            )
            .first()
        )
        if alerte_existante:
            continue

        page_str = f" (Page {marche.page_number})" if marche.page_number else ""
        contenu = f"Nouvel appel d'offres : {marche.objet}{page_str}"
        nouvelle_alerte = Alerte(
            entreprise_id=ent.id,
            publication_id=publication.id,
            marche_id=marche.id,
            type_alerte="marche",
            date_alerte=datetime.now(timezone.utc),
            contenu_alerte=contenu,
            canal_alerte="plateforme",
            lu=False,
        )
        db.add(nouvelle_alerte)
        alertes_creees.append(nouvelle_alerte)

    if alertes_creees:
        db.commit()
        logger.info(
            "%d alerte(s) créée(s) pour le marché ID %d auprès des entreprises du domaine ID %d.",
            len(alertes_creees),
            marche.id,
            marche.domaine_id,
        )

    return alertes_creees
