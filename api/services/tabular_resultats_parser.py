"""Moteur d'analyse tabulaire géométrique et déterministe des résultats de marchés.

Règle d'Or n°1 : Déterminisme d'abord, IA en complément ciblé.
Ce module analyse les structures tabulaires (colonnes, lignes, en-têtes) et les
formulations administratives types de la DGCMEF (Quotidien des marchés publics) :
- Détection des délibérations et procès-verbaux de jugement
- Extraction des métadonnées d'en-tête (organisme, référence dossier, objet, date)
- Découpage par lots (multi-lots et lot unique)
- Extraction déterministe des soumissionnaires (attributaires ET écartés avec motif)
- Fallback automatique et ciblé vers le LLM si la structure déterministe est absente.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Sequence

from llm_service.extraction_resultats_prompts import (
    ResultatExtractionSchema,
    extraire_resultats_avec_llm,
    parse_llm_date,
)

logger = logging.getLogger(__name__)

# --- Marqueurs de détection de résultats (Règle n°1) ---
_MARQUEURS_RESULTAT_TITRE = re.compile(
    r"resultats?\s+(?:provisoires?|definitifs?|de\s+la\s+|des\s+|du\s+)?|"
    r"(?:demande\s+de\s+prix|depouillement|jugement|deliberation|l.ami|consultation|marche)|"
    r"proces-verbal\s+d.attribution|deliberation\s+de\s+la\s+cam|"
    r"commission\s+d.attribution\s+des\s+marches|"
    r"attribution\s+(?:provisoire|definitive)|classement\s+des\s+offres|"
    r"synthese\s+des\s+resultats|fiche\s+de\s+synthese|"
    r"date\s+de\s+deliberation|date\s+d.ouverture\s+des\s+plis",
    re.IGNORECASE,
)

_MARQUEURS_DECISION_ATTRIBUTAIRE = re.compile(
    r"\b(?:attributaire|retenu[es]?|adjudicataire|1er\s+retenu|conforme\s+et\s+moins\s+disant|gagnant)\b",
    re.IGNORECASE,
)

_MARQUEURS_DECISION_ECARTE = re.compile(
    r"\b(?:non\s+conforme|ecarte[es]?|rejet[es]?|elimine[es]?|incomplet[es]?|non\s+recevable|infructueux|hors\s+budget|offre\s+anormale|non\s+classe)\b",
    re.IGNORECASE,
)

_MARQUEURS_DECISION_NON_RETENU = re.compile(
    r"\b(?:retenu\s+non\s+attributaire|2eme\s+retenu|3eme\s+retenu|conforme\s+non\s+retenu|non\s+retenu)\b",
    re.IGNORECASE,
)

_DELIMITEUR_MARCHE = re.compile(
    r"\n(?=(?:MINIST[EÈ]RE|DIRECTION|CENTRE\s+NATIONAL|UNIVERSIT[EÉ]|COMMUNE|MAIRIE|AGENCE|SOCI[EÉ]T[EÉ]|FONDS|CHU|SECR[EÉ]TARIAT)\s+)"
    r"|\n(?=(?:Demande\s+de\s+(?:prix|propositions?|renseignements?)|Avis\s+d.appel\s+d.offres?|Manifestation\s+d.int[eé]r[eê]t|Consultation)\s+n[°ºo]?\s*[:\s]*[0-9A-Z/\-_]{3,})"
    r"|\n(?=R[EÉ]SULTATS?\s+(?:DE|DES|DU|PROVISOIRES?)\b)",
    re.IGNORECASE,
)

_IFU_PATTERN = re.compile(r"\b(\d{8}\s?[A-Z])\b", re.IGNORECASE)
_RCCM_PATTERN = re.compile(r"\b(BF\s*[-/]?\s*[A-Z]{3}\s*[-/]?\s*\d{4}\s*[-/]?\s*[A-Z]\s*[-/]?\s*\d+)\b", re.IGNORECASE)

_DATE_PATTERN = re.compile(r"(\d{1,2})\s+(janvier|fevrier|février|mars|avril|mai|juin|juillet|aout|août|septembre|octobre|novembre|decembre|décembre)\s+(\d{4})", re.IGNORECASE)

_MOIS_FR = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "août": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}


def _sans_accents(texte: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


def _nettoyer_montant(valeur_brute: str | None) -> Decimal | None:
    """Transforme '24 500 000 FCFA' ou '12.500.000' en Decimal('24500000.00')."""
    if not valeur_brute:
        return None
    # Supprime 'FCFA', 'F CFA', espaces, points de milliers
    val = re.sub(r"(?i)f\s*cfa|fcfa", "", valeur_brute).strip()
    val = re.sub(r"[\s\u00a0\u202f]", "", val)
    # Remplacer virgule décimale par point
    val = val.replace(",", ".")
    # Si des points séparaient les milliers (ex 12.500.000)
    parties = val.split(".")
    if len(parties) > 2:
        val = "".join(parties)
    elif len(parties) == 2 and len(parties[1]) == 3 and not parties[1].startswith("00"):
        # Probable séparateur de milliers
        val = "".join(parties)

    try:
        dec = Decimal(val)
        # Un montant réaliste de marché public est inférieur à 1 000 milliards de FCFA (10^12)
        # Tout nombre >= 10^12 est un numéro de compte, téléphone, référence ou concaténation
        if dec <= 0 or dec >= Decimal("1000000000000"):
            return None
        return dec
    except Exception:
        return None


# --- Structures de Données Unifiées (DTOs) ---


@dataclass
class SoumissionnaireDTO:
    nom_entreprise_brut: str
    nom_entreprise_normalise: str
    ifu: str | None = None
    rccm: str | None = None
    est_attributaire: bool = False
    statut: str = "ECARTE"  # ATTRIBUTAIRE, ECARTE, RETENU_NON_ATTRIBUTAIRE
    rang_classement: int | None = None
    montant_lu: Decimal | None = None
    montant_corrige: Decimal | None = None
    delai_execution: str | None = None
    motif_rejet: str | None = None


@dataclass
class LotResultatDTO:
    numero_lot: str = "1"
    intitule_lot: str | None = None
    montant_estime: Decimal | None = None
    statut_lot: str = "ATTRIBUE"  # ATTRIBUE, INFRUCTUEUX, ANNULE
    soumissionnaires: list[SoumissionnaireDTO] = field(default_factory=list)


@dataclass
class ResultatExtractionDTO:
    autorite_contractante: str
    reference_dossier: str | None
    objet: str
    date_attribution: date | None
    statut_deliberation: str
    lots: list[LotResultatDTO] = field(default_factory=list)
    methode_extraction: str = "DETERMINISTE"  # DETERMINISTE ou LLM_FALLBACK
    snippet_source: str = ""


# --- Parser Déterministe ---


class TabularResultatsParser:
    """Parser déterministe pour extraire les résultats des bulletins DGCMEF."""

    @classmethod
    def est_section_resultat(cls, texte: str) -> bool:
        """Détecte avec certitude si le texte correspond à une délibération de marché."""
        texte_norm = _sans_accents(texte).lower()
        # Ne pas confondre avec un simple avis d'appel d'offres sans délibération
        if ("avis de demande de prix" in texte_norm or "avis d'appel d'offres" in texte_norm) and not any(
            m in texte_norm for m in ("attributaire", "deliberation", "depouillement", "soumissionnaire", "retenu pour la negociation", "classement")
        ):
            return False

        has_signal = any(
            m in texte_norm
            for m in (
                "attributaire",
                "soumissionnaire",
                "deliberation",
                "depouillement",
                "classement",
                "moins disant",
                "adjudicataire",
                "fiche de synthese",
                "synthese des resultats",
                "note technique",
                "montant lu",
                "montant corrige",
            )
        )
        return has_signal

    @classmethod
    def extraire_en_tete(cls, texte: str) -> dict[str, Any]:
        """Extrait l'autorité contractante, la référence du dossier, l'objet et la date."""
        autorite = "Autorité contractante inconnue"
        lignes = [ligne.strip() for ligne in texte.split("\n") if ligne.strip()]

        # 1. Autorité contractante : première ligne en majuscules (Ministère, Direction, Société)
        for ligne in lignes[:6]:
            sans_acc = _sans_accents(ligne).upper()
            if any(mot in sans_acc for mot in ("MINISTERE", "DIRECTION", "MAIRIE", "COMMUNE", "SECRETARIAT", "AGENCE", "SOCIETE", "FONDS", "UNIVERSITE", "CHU")):
                autorite = ligne
                break
        if autorite == "Autorité contractante inconnue" and lignes:
            autorite = lignes[0]

        # 2. Référence du dossier (Demande de prix n°..., Marché n°..., Dossier n°...)
        ref_match = re.search(
            r"(?:demande\s+de\s+(?:prix|propositions?)[^\n\d]*|dossier|avis|marche|marches|ami)\s*(?:n[°ºo]|N[°ºo]|numero)?\s*[:\s]*([0-9A-Z/\-_]{4,})",
            texte,
            re.IGNORECASE,
        )
        reference_dossier = ref_match.group(1).strip() if ref_match else None

        # 3. Objet du marché
        objet = "Objet non spécifié"
        objet_match = re.search(
            r"(?:objet\s*:\s*|portant\s+sur\s+|relative?\s+a\s+|pour\s+)(.+?)(?=\n\n|financement\s*:|date\s*:|lot\s*1|lot\s+unique|tableau|$)",
            texte,
            re.IGNORECASE | re.DOTALL,
        )
        if objet_match:
            objet = re.sub(r"\s+", " ", objet_match.group(1)).strip()
        else:
            # Recherche de ligne commençant par 'Acquisition', 'Travaux', 'Fourniture', 'Prestation', 'Recrutement'
            for ligne in lignes:
                sans_acc = _sans_accents(ligne).lower()
                if any(sans_acc.startswith(debut) for debut in ("acquisition", "fourniture", "travaux", "prestation", "recrutement", "realisation")):
                    objet = ligne
                    break

        # 4. Date de délibération / signature
        date_attribution = None
        date_match = _DATE_PATTERN.search(texte)
        if date_match:
            jour, mois_str, annee = date_match.groups()
            mois_num = _MOIS_FR.get(mois_str.lower())
            if mois_num:
                try:
                    date_attribution = date(int(annee), mois_num, int(jour))
                except ValueError:
                    pass

        # 5. Statut délibération global
        statut = "ATTRIBUE"
        if re.search(r"\b(infructueux|sans\s+suite)\b", texte, re.IGNORECASE):
            statut = "INFRUCTUEUX"
        elif re.search(r"\b(annule|annulation)\b", texte, re.IGNORECASE):
            statut = "ANNULE"

        return {
            "autorite_contractante": autorite[:255],
            "reference_dossier": reference_dossier[:255] if reference_dossier else None,
            "objet": objet,
            "date_attribution": date_attribution,
            "statut_deliberation": statut,
        }

    @classmethod
    def extraire_soumissionnaire_ligne(cls, ligne: str) -> SoumissionnaireDTO | None:
        """Tente d'extraire un soumissionnaire depuis une ligne de tableau ou de liste."""
        ligne_strip = ligne.strip()
        if not ligne_strip or len(ligne_strip) < 4:
            return None

        ligne_norm = _sans_accents(ligne_strip).lower()
        # Ignorer en-têtes
        if any(h in ligne_norm for h in ("note technique/100", "tableau d'analyse", "observations pays", "classement observations")):
            return None
        if ligne_norm in ("soumissionnaires", "soumissionnaire", "candidats", "candidat", "entreprises", "lots"):
            return None
        # Ignorer métadonnées administratives et seuils de tolérance / formules
        if any(h in ligne_norm for h in (
            "date de depouillement", "date de deliberation", "nombre de plis",
            "methode de selection", "financement", "reference publication",
            "reference de la convocation", "note minimale", "budget", "imputation",
            "seuil de tolerance", "borne inferieur", "borne superieur",
            "francs cfa", "taux de", "estimation", "offre anormalement",
        )):
            return None

        # 1. Extraction des montants
        montants_matches = re.findall(
            r"\b(\d{1,3}(?:[\s\u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d{5,}(?:[.,]\d+)?)\b(?:\s*F\s*CFA|\s*FCFA|\s*TTC|\s*HT)?",
            ligne_strip,
            re.IGNORECASE,
        )
        montants_valides: list[Decimal] = []
        for m_str in montants_matches:
            val_dec = _nettoyer_montant(m_str)
            if val_dec and val_dec >= Decimal("10000"):
                montants_valides.append(val_dec)

        montant_lu = montants_valides[0] if len(montants_valides) >= 1 else None
        montant_corrige = montants_valides[1] if len(montants_valides) >= 2 else montant_lu

        # 2. Extraction du rang (1er, 2è, 3e, etc.)
        rang_match = re.search(r"\b(\d+)\s*(?:er|ere|ère|è|e|ème|ieme)\b", ligne_norm)
        rang = int(rang_match.group(1)) if rang_match else None

        # 3. Détermination statut
        est_attributaire = False
        motif = None
        if rang == 1 or _MARQUEURS_DECISION_ATTRIBUTAIRE.search(ligne_norm):
            if not _MARQUEURS_DECISION_NON_RETENU.search(ligne_norm) and not _MARQUEURS_DECISION_ECARTE.search(ligne_norm):
                statut = "ATTRIBUTAIRE"
                est_attributaire = True
            else:
                statut = "RETENU_NON_ATTRIBUTAIRE"
                motif = "Classé non attributaire"
        elif rang and rang > 1:
            statut = "RETENU_NON_ATTRIBUTAIRE"
            motif = f"Classé {rang}e"
        elif _MARQUEURS_DECISION_ECARTE.search(ligne_norm) or "non classe" in ligne_norm:
            statut = "ECARTE"
            motif = "Non classé ou non conforme"
        elif montants_valides:
            statut = "RETENU_NON_ATTRIBUTAIRE"
            motif = "Offre examinée"
        else:
            return None

        # 4. Extraction du nom de l'entreprise
        ligne_propre = ligne_strip
        ligne_propre = re.sub(r"^[0-9❖•\-\*]+\s*[.)\-]?\s*", "", ligne_propre)
        for m_str in montants_matches:
            ligne_propre = re.sub(r"\b" + re.escape(m_str) + r"\b(?:\s*F\s*CFA|\s*FCFA|\s*TTC|\s*HT)?", " ", ligne_propre, flags=re.IGNORECASE)
        ligne_propre = re.sub(r"\b\d+\s*(?:er|ere|ère|è|e|ème|ieme|eme)\b", " ", ligne_propre, flags=re.IGNORECASE)
        ligne_propre = re.sub(
            r"\b(?:Burkina\s+Faso|RAS|R\.A\.S|Conforme|Non\s+conforme|Non\s+class[eé]e?|Erreur\s+de\s+calcul[^\n]*|Offre\s+anormalement[^\n]*|Moins\s+disant[^\n]*)\b",
            " ",
            ligne_propre,
            flags=re.IGNORECASE,
        )
        ligne_propre = re.sub(r"\b(?:Note\s+technique\s*[:\s]*)?\d{1,2}(?:[.,]\d+)?(?:\s*/\s*100)?\b", " ", ligne_propre, flags=re.IGNORECASE)
        ligne_propre = re.sub(r"\b\d+\s+(?:jours?|mois)\b", " ", ligne_propre, flags=re.IGNORECASE)
        ligne_propre = re.sub(r"\s+\d+\s*(?:er|ere|ère|è|e|ème|ieme|eme)?$", "", ligne_propre, flags=re.IGNORECASE)

        # Nettoyage des identifiants et métadonnées d'adresse pour ne pas fausser le nom de l'entreprise
        ifu = None
        rccm = None
        ifu_m = _IFU_PATTERN.search(ligne_strip)
        if ifu_m:
            ifu = ifu_m.group(1).replace(" ", "")
            ligne_propre = re.sub(r"\b(?:ifu|n[°ºo]?\s*ifu)\b[^,\n;]*", " ", ligne_propre, flags=re.IGNORECASE)
        rccm_m = _RCCM_PATTERN.search(ligne_strip)
        if rccm_m:
            rccm = rccm_m.group(1)
            ligne_propre = re.sub(r"\b(?:rccm|n[°ºo]?\s*rccm)\b[^,\n;]*", " ", ligne_propre, flags=re.IGNORECASE)
        ligne_propre = re.sub(r"\b(?:0[1-9]\s*)?bp\b\s*[:.]?\s*[0-9\s/+\-]*\s*(?:ouaga(?:dougou)?|bobo(?:[- ]dioulasso)?|koudougou|banfora)?", " ", ligne_propre, flags=re.IGNORECASE)
        ligne_propre = re.sub(r"\b(?:t[ée]l|cel|fax)\b\s*[:.]?\s*[0-9\s/+\-]*", " ", ligne_propre, flags=re.IGNORECASE)
        ligne_propre = re.sub(r"\b(?:ouagadougou|ouaga|bobo-dioulasso|bobo dioulasso|koudougou|banfora|burkina\s*faso)\b", " ", ligne_propre, flags=re.IGNORECASE)
        ligne_propre = re.sub(r"\b(?:pour un montant de|pour un montant|pour un|montant|f\s*cfa|fcfa)\b", " ", ligne_propre, flags=re.IGNORECASE)

        nom_candidat = re.sub(r"\s+", " ", ligne_propre).strip(" |-\t;:,./")
        if len(nom_candidat) < 3 or not any(c.isalpha() for c in nom_candidat):
            return None
        if any(nom_candidat.lower().startswith(b) for b in (
            "conclusion", "attributaire", "financement", "date de", "nombre de",
            "methode", "soumissionnaires", "montant", "seuil", "borne", "francs cfa", "offre"
        )):
            return None

        # Rejet des suites de nombres ou codes administratifs (ex: 413 928 688... ou 775 380 643...)
        if re.match(r"^\d{3,}", nom_candidat) or re.match(r"^\d{2,}\s+\d{2,}", nom_candidat):
            return None
        if sum(c.isdigit() for c in nom_candidat) / max(len(nom_candidat), 1) > 0.25:
            return None

        from api.services.entity_resolution import normaliser_nom_canonique
        nom_canonique_temp = normaliser_nom_canonique(nom_candidat)
        if any(nom_canonique_temp.startswith(p) for p in (
            "seuil", "borne", "francs cfa", "montant", "offre", "total", "note", "rabais", "sous total", "taux", "prix"
        )):
            return None

        return SoumissionnaireDTO(
            nom_entreprise_brut=nom_candidat[:255],
            nom_entreprise_normalise=nom_canonique_temp[:255],
            ifu=ifu,
            rccm=rccm,
            est_attributaire=est_attributaire,
            statut=statut,
            rang_classement=rang,
            montant_lu=montant_lu,
            montant_corrige=montant_corrige,
            motif_rejet=motif,
        )

    @classmethod
    def parser_texte_resultat(cls, texte: str) -> ResultatExtractionDTO | None:
        """Parse le texte de résultat de manière 100% déterministe."""
        if not cls.est_section_resultat(texte):
            return None

        en_tete = cls.extraire_en_tete(texte)

        # Découpage par lots : "Lot 1", "Lot 2", "Lot unique"
        lignes = texte.split("\n")
        lots_dict: dict[str, LotResultatDTO] = {}
        lot_courant = "1"
        lots_dict[lot_courant] = LotResultatDTO(numero_lot=lot_courant, intitule_lot="Lot principal")

        for ligne in lignes:
            ligne_strip = ligne.strip()
            # Détection d'un changement de lot
            lot_match = re.search(r"\b(?:lot|lot\s+n[°ºo]?)\s*[:\s]*(\d+|unique)\b(?:\s*[:-]\s*(.+))?", ligne_strip, re.IGNORECASE)
            if lot_match:
                lot_num = lot_match.group(1).upper()
                intitule = lot_match.group(2) if lot_match.group(2) else f"Lot {lot_num}"
                lot_courant = lot_num
                if lot_courant not in lots_dict:
                    lots_dict[lot_courant] = LotResultatDTO(numero_lot=lot_courant, intitule_lot=intitule.strip())
                continue

            soum = cls.extraire_soumissionnaire_ligne(ligne_strip)
            if soum:
                lots_dict[lot_courant].soumissionnaires.append(soum)

        # Vérification d'une conclusion ou mention explicite d'attribution
        from api.services.entity_resolution import normaliser_nom_canonique
        patterns_attribution = [
            r"(?:conclusion|attributaire\s*(?:provisoire)?|adjudicataire|entreprise\s+retenue|candidat\s+retenu|retenu\s+pour\s+la\s+negociation|proposition\s+d.attribution)\s*[:\s]*([A-Z0-9\s\.\-_/&]+?)(?:,|\.|\n|bp\b|tel\b|ifu\b|rccm\b|montant|pour\s+un\s+montant|$)",
            r"([A-Z0-9\s\.\-_/&]{3,40})\s+(?:est\s+d[eé]clar[eé]e?\s+attributaire|est\s+retenue?|est\s+adjudicataire)",
            r"(?:attribution\s*[:\s]*)([A-Z0-9\s\.\-_/&]+?)(?:,|\.|\n|bp\b|tel\b|ifu\b|rccm\b|montant|$)",
        ]
        gagnants_detectes: list[str] = []
        for pat in patterns_attribution:
            for match in re.finditer(pat, texte, re.IGNORECASE):
                nom_raw = match.group(1).strip()
                if len(nom_raw) >= 3 and not any(k in nom_raw.lower() for k in ("marche", "lot", "dossier", "rapport", "tableau", "date")):
                    gagnants_detectes.append(normaliser_nom_canonique(nom_raw))

        for lot in lots_dict.values():
            for s in lot.soumissionnaires:
                if any(g in s.nom_entreprise_normalise or s.nom_entreprise_normalise in g for g in gagnants_detectes if g):
                    s.est_attributaire = True
                    s.statut = "ATTRIBUTAIRE"
                    s.motif_rejet = None

            # Si le lot ne compte qu'un seul soumissionnaire et que le statut global est ATTRIBUE
            # et que le texte mentionne l'attribution sans rejet pour cette entreprise
            if len(lot.soumissionnaires) == 1 and not any(s.est_attributaire for s in lot.soumissionnaires):
                s_unique = lot.soumissionnaires[0]
                if s_unique.statut != "ECARTE" and en_tete["statut_deliberation"] == "ATTRIBUE":
                    if any(mot in texte.lower() for mot in ("attributaire", "retenu", "adjudicataire", "deliberation", "attribution")):
                        s_unique.est_attributaire = True
                        s_unique.statut = "ATTRIBUTAIRE"
                        s_unique.motif_rejet = None

        lots_valides = [l for l in lots_dict.values() if l.soumissionnaires]
        if not lots_valides:
            return None

        return ResultatExtractionDTO(
            autorite_contractante=en_tete["autorite_contractante"],
            reference_dossier=en_tete["reference_dossier"],
            objet=en_tete["objet"],
            date_attribution=en_tete["date_attribution"],
            statut_deliberation=en_tete["statut_deliberation"],
            lots=lots_valides,
            methode_extraction="DETERMINISTE",
            snippet_source=texte[:2000],
        )

    @classmethod
    def decouper_en_marches(cls, texte: str) -> list[str]:
        """Découpe un texte de page en sous-marchés distincts si plusieurs délibérations figurent sur la même page."""
        morceaux = _DELIMITEUR_MARCHE.split(texte)
        morceaux_valides = [m.strip() for m in morceaux if m and len(m.strip()) > 60]
        return morceaux_valides if len(morceaux_valides) > 1 else [texte]

    @classmethod
    def extraire_resultats_section(
        cls, texte: str, *, client_llm: Any = None
    ) -> list[ResultatExtractionDTO]:
        """Extrait toutes les délibérations de marché d'une page/section (support multi-marchés par page)."""
        resultats: list[ResultatExtractionDTO] = []
        marches = cls.decouper_en_marches(texte)

        for m_texte in marches:
            if not cls.est_section_resultat(m_texte):
                continue
            dto = cls.extraire_resultat_hybride(m_texte, client_llm=client_llm)
            if dto and dto.lots:
                resultats.append(dto)

        return resultats

    @classmethod
    def extraire_resultat_hybride(
        cls, texte: str, *, client_llm: Any = None
    ) -> ResultatExtractionDTO | None:
        """Point d'entrée hybride : Déterministe d'abord, LLM en fallback ciblé (Règle d'Or n°1)."""
        # 1. Tentative déterministe pure
        res_det = cls.parser_texte_resultat(texte)
        if res_det is not None and res_det.lots and sum(len(l.soumissionnaires) for l in res_det.lots) > 0:
            logger.info(
                "Extraction de résultat réussie par méthode DÉTERMINISTE (%d lot(s), %d soumissionnaire(s))",
                len(res_det.lots),
                sum(len(l.soumissionnaires) for l in res_det.lots),
            )
            return res_det

        # 2. Vérification s'il s'agit bien d'une section résultat avant de solliciter le LLM
        if not cls.est_section_resultat(texte):
            return None

        # 3. Fallback ciblé LLM (Règle n°1)
        logger.info("Structure tabulaire déterministe incomplète, basculement sur le FALLBACK LLM ciblé.")
        res_llm: ResultatExtractionSchema | None = extraire_resultats_avec_llm(texte, client=client_llm)
        if not res_llm or not res_llm.lots:
            return None

        from api.services.entity_resolution import normaliser_nom_canonique

        # Conversion du schéma LLM vers le DTO unifié
        lots_dto: list[LotResultatDTO] = []
        for lot_l in res_llm.lots:
            soum_dtos: list[SoumissionnaireDTO] = []
            for s in lot_l.soumissionnaires:
                montant_lu_dec = Decimal(str(s.montant_lu)) if s.montant_lu else None
                montant_corr_dec = Decimal(str(s.montant_corrige)) if s.montant_corrige else None
                soum_dtos.append(
                    SoumissionnaireDTO(
                        nom_entreprise_brut=s.nom_entreprise[:255],
                        nom_entreprise_normalise=normaliser_nom_canonique(s.nom_entreprise)[:255],
                        ifu=s.ifu,
                        rccm=s.rccm,
                        est_attributaire=s.est_attributaire,
                        statut=s.statut,
                        rang_classement=s.rang_classement,
                        montant_lu=montant_lu_dec,
                        montant_corrige=montant_corr_dec,
                        delai_execution=s.delai_execution,
                        motif_rejet=s.motif_rejet,
                    )
                )

            lots_dto.append(
                LotResultatDTO(
                    numero_lot=lot_l.numero_lot,
                    intitule_lot=lot_l.intitule_lot,
                    montant_estime=Decimal(str(lot_l.montant_estime)) if lot_l.montant_estime else None,
                    statut_lot=lot_l.statut_lot,
                    soumissionnaires=soum_dtos,
                )
            )

        return ResultatExtractionDTO(
            autorite_contractante=res_llm.autorite_contractante[:255],
            reference_dossier=res_llm.reference_dossier[:255] if res_llm.reference_dossier else None,
            objet=res_llm.objet,
            date_attribution=parse_llm_date(res_llm.date_attribution),
            statut_deliberation=res_llm.statut_deliberation,
            lots=lots_dto,
            methode_extraction="LLM_FALLBACK",
            snippet_source=texte[:2000],
        )
