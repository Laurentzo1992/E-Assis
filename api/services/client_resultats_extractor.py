"""Extracteur ciblé et interpréteur IA asynchrone / parallèle des résultats pour les entreprises abonnées.

Ce module implémente la nouvelle approche 'Client-Centric' :
1. Détection déterministe ultra-rapide (< 50ms) et insensible à la casse de la présence
   des entreprises inscrites sur chaque page / section de résultat du bulletin.
2. Découpage du bloc contextuel complet du marché (en-tête, tableau, conclusion).
3. Interprétation asynchrone et parallèle par le LLM (Gemini 3.1 Flash Lite) ciblée
   spécifiquement sur l'entreprise (victoire, échec, rang, notes, montants, motifs).
4. Génération d'une synthèse personnalisée prête pour le Dashboard et les notifications WhatsApp/Email.
5. Enregistrement idempotent et traçable (page source, extrait brut, délibération).
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Sequence

from pydantic import BaseModel, Field, model_validator

from api.models.backend import Publication
from api.models.entreprise import Entreprise
from api.models.resultats_attribution import (
    AlerteResultat,
    LotResultat,
    ResultatAttribution,
    SoumissionnaireResultat,
)
from llm_service.extraction_resultats_prompts import (
    _extraire_json_de_reponse,
    parse_llm_date,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

TASK = "extraction"


def _sans_accents(texte: str) -> str:
    """Supprime les accents pour une comparaison insensible à la casse et aux diacritiques."""
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


# --- Schéma d'interprétation IA pour une entreprise cible ---


class ResultatEntrepriseAI(BaseModel):
    """Interprétation chirurgicale d'un résultat pour une entreprise cliente."""

    concerne_entreprise: bool = Field(
        default=True,
        description="true si l'entreprise cible est effectivement candidate, soumissionnaire ou attributaire sur ce marché",
    )
    autorite_contractante: str = Field(
        default="Autorité contractante non spécifiée",
        description="Ministère, Mairie, Direction ou Institution publique émettrice",
    )
    reference_dossier: str | None = Field(
        default=None,
        description="Numéro officiel de la consultation, demande de prix ou dossier (ex: 2026-079/MEF/SG/DMP)",
    )
    objet: str = Field(
        default="Objet du marché non spécifié",
        description="Objet précis et complet du marché",
    )
    date_attribution: str | None = Field(
        default=None,
        description="Date de délibération ou de signature au format AAAA-MM-JJ si disponible",
    )
    numero_lot: str = Field(
        default="1",
        description="Numéro du lot concerné (ex: '1', '2', ou 'Lot unique')",
    )
    intitule_lot: str | None = Field(
        default=None,
        description="Description ou intitulé du lot s'il est mentionné",
    )
    est_attributaire: bool = Field(
        default=False,
        description="true si l'entreprise cible a gagné le lot, est retenue pour négociation ou désignée adjudicataire",
    )
    statut: str = Field(
        default="CLASSE_NON_RETENU",
        description="ATTRIBUTAIRE, CLASSE_NON_RETENU, ECARTE ou REJETE",
    )
    rang_classement: int | None = Field(
        default=None,
        description="Classement obtenu (1 pour 1er, 2 pour 2e, 3 pour 3e...)",
    )
    note_technique: str | None = Field(
        default=None,
        description="Note technique ou score obtenu si spécifié (ex: '89/100', '99')",
    )
    montant_propose: float | None = Field(
        default=None,
        description="Montant soumis ou corrigé par l'entreprise cible (en FCFA)",
    )
    montant_attributaire: float | None = Field(
        default=None,
        description="Montant retenu pour l'attributaire gagnant si l'entreprise cible n'a pas gagné (en FCFA)",
    )
    nom_attributaire: str | None = Field(
        default=None,
        description="Nom de l'entreprise ayant remporté le marché si l'entreprise cible n'a pas gagné",
    )
    delai_execution: str | None = Field(
        default=None,
        description="Délai d'exécution mentionné (ex: '30 jours', '2 mois')",
    )
    motif_rejet: str | None = Field(
        default=None,
        description="Raison de non-attribution, observation ou classement (ex: 'Classé 3ème avec note 89/100, montant plus élevé que le 1er retenu')",
    )
    analyse_synthese: str = Field(
        default="",
        description="Synthèse personnalisée en 2 ou 3 phrases destinées à l'abonné pour son tableau de bord et sa notification",
    )

    @model_validator(mode="before")
    @classmethod
    def sanitize_fields(cls, data: Any) -> Any:
        """Nettoie et coerce les données envoyées par le LLM pour éviter tout échec de validation."""
        if not isinstance(data, dict):
            return data

        # 1. numero_lot : accepter null, int, float, ou str
        num_lot = data.get("numero_lot")
        if num_lot is None or str(num_lot).strip().lower() in ("none", "null", ""):
            data["numero_lot"] = "1"
        else:
            data["numero_lot"] = str(num_lot).strip()

        # 2. rang_classement : extraire l'entier si envoyé sous forme "3e", "3ème", "3", etc.
        rang = data.get("rang_classement")
        if rang is not None:
            if isinstance(rang, str):
                match = re.search(r"\d+", rang)
                data["rang_classement"] = int(match.group(0)) if match else None
            elif not isinstance(rang, int):
                try:
                    data["rang_classement"] = int(rang)
                except (ValueError, TypeError):
                    data["rang_classement"] = None

        # 3. montants : nettoyer les chaînes avec espaces séparateurs (ex: "19 092 400")
        for key in ("montant_propose", "montant_attributaire"):
            val = data.get(key)
            if val is not None:
                if isinstance(val, (int, float)):
                    data[key] = float(val)
                elif isinstance(val, str):
                    val_clean = re.sub(r"[^\d.]", "", val)
                    try:
                        data[key] = float(val_clean) if val_clean else None
                    except ValueError:
                        data[key] = None

        # 4. booléens
        if "concerne_entreprise" in data and isinstance(data["concerne_entreprise"], str):
            data["concerne_entreprise"] = data["concerne_entreprise"].strip().lower() in ("true", "1", "yes", "oui")
        if "est_attributaire" in data and isinstance(data["est_attributaire"], str):
            data["est_attributaire"] = data["est_attributaire"].strip().lower() in ("true", "1", "yes", "oui")

        # 5. chaînes par défaut
        if not data.get("autorite_contractante"):
            data["autorite_contractante"] = "Autorité contractante non spécifiée"
        if not data.get("objet"):
            data["objet"] = "Objet du marché non spécifié"
        if not data.get("statut"):
            data["statut"] = "ATTRIBUTAIRE" if data.get("est_attributaire") else "CLASSE_NON_RETENU"
        if not data.get("analyse_synthese"):
            data["analyse_synthese"] = data.get("motif_rejet") or ""

        return data


# --- Signatures d'entreprises pour recherche insensible à la casse ---


@dataclass
class EnterpriseSignature:
    entreprise_id: int
    nom: str
    patterns: list[re.Pattern]
    ifu: str | None = None
    rccm: str | None = None

    def correspond(self, texte_sans_acc: str) -> bool:
        """Vérifie si l'entreprise apparaît dans le texte (recherche insensible à la casse et aux accents)."""
        # Vérification par identifiants légaux en priorité (Niveau 1)
        if self.ifu:
            ifu_clean = re.sub(r"\s+", "", self.ifu)
            if ifu_clean and ifu_clean.lower() in texte_sans_acc:
                return True

        if self.rccm:
            rccm_clean = re.sub(r"[\s\-_/]+", "", self.rccm.lower())
            texte_compresse = re.sub(r"[\s\-_/]+", "", texte_sans_acc)
            if rccm_clean and rccm_clean in texte_compresse:
                return True

        # Vérification par motifs regex insensibles à la casse (Niveau 2)
        for pat in self.patterns:
            if pat.search(texte_sans_acc):
                return True

        return False


def construire_signatures_entreprises(entreprises: Sequence[Entreprise]) -> list[EnterpriseSignature]:
    """Construit pour chaque entreprise une liste de regex optimisées insensibles à la casse."""
    signatures: list[EnterpriseSignature] = []

    # Mots juridiques ou suffixes à dépouiller pour trouver le cœur du nom
    suffixes_juridiques = [
        r"\bsarl\b", r"\bs\.a\.r\.l\.?\b",
        r"\bsa\b", r"\bs\.a\.?\b",
        r"\bets\b", r"\b[eé]tablissements?\b",
        r"\bsuarl\b", r"\bgie\b", r"\bltd\b",
        r"\bsoci[eé]t[eé]\b", r"\bcompagnie\b",
        r"\bburkina\b", r"\bbf\b",
    ]

    for ent in entreprises:
        patterns: list[re.Pattern] = []
        nom_sans_acc = _sans_accents(ent.nom).strip().lower()

        # 1. Nom complet échappé avec espaces flexibles
        nom_mots = [re.escape(m) for m in re.split(r"[\s\-_/]+", nom_sans_acc) if m]
        if nom_mots:
            pat_complet = r"\b" + r"[\s\-_/]+".join(nom_mots) + r"\b"
            patterns.append(re.compile(pat_complet, re.IGNORECASE))

        # 2. Nom sans les formes juridiques (ex: 'LOGO SERVICES SARL' -> 'LOGO SERVICES')
        nom_epure = nom_sans_acc
        for suf in suffixes_juridiques:
            nom_epure = re.sub(suf, " ", nom_epure, flags=re.IGNORECASE)
        nom_epure = re.sub(r"\s+", " ", nom_epure).strip()

        if nom_epure and len(nom_epure) >= 3 and nom_epure != nom_sans_acc:
            mots_epures = [re.escape(m) for m in re.split(r"[\s\-_/]+", nom_epure) if m]
            if mots_epures:
                pat_epure = r"\b" + r"[\s\-_/]+".join(mots_epures) + r"\b"
                patterns.append(re.compile(pat_epure, re.IGNORECASE))

        # 3. Variantes avec / sans 's' final sur le dernier mot (ex: 'LOGO SERVICE' vs 'LOGO SERVICES')
        if nom_epure and nom_epure.endswith("s"):
            nom_singulier = nom_epure[:-1]
            if len(nom_singulier) >= 3:
                mots_sing = [re.escape(m) for m in re.split(r"[\s\-_/]+", nom_singulier) if m]
                pat_sing = r"\b" + r"[\s\-_/]+".join(mots_sing) + r"\b"
                patterns.append(re.compile(pat_sing, re.IGNORECASE))

        signatures.append(
            EnterpriseSignature(
                entreprise_id=ent.id,
                nom=ent.nom,
                patterns=patterns,
                ifu=ent.numero_identification,
                rccm=ent.rccm,
            )
        )

    return signatures


# --- Découpage contextuel des marchés sur une page ---


@dataclass
class MarketSection:
    page_number: int
    texte: str


def decouper_page_en_marches(page_number: int, texte_page: str) -> list[MarketSection]:
    """Découpe le texte d'une page en sections autonomes si plusieurs marchés distincts y figurent."""
    texte_clean = texte_page.strip()
    if not texte_clean:
        return []

    # Séparateurs types de délibérations / marchés sur une même page
    delimiteurs = re.split(
        r"\n(?=(?:Demande\s+de\s+(?:propositions?|prix|renseignements?)|Avis\s+d.appel\s+d.offres?|Manifestation\s+d.int[eé]r[eê]t|Consultation)\s+n[°ºo]?\s*[:\s]*[0-9A-Z/\-_]{3,})"
        r"|\n(?=R[EÉ]SULTATS?\s+(?:DE|DES|DU|PROVISOIRES?)\b)",
        texte_clean,
        flags=re.IGNORECASE,
    )

    sections: list[MarketSection] = []
    for part in delimiteurs:
        part_str = part.strip()
        if len(part_str) > 60:
            sections.append(MarketSection(page_number=page_number, texte=part_str))

    if not sections:
        sections.append(MarketSection(page_number=page_number, texte=texte_clean))

    return sections


# --- Interprétation IA par Gemini ---


SYSTEM_PROMPT_ANALYSE_ENTREPRISE = """Tu es un expert senior des marchés publics au Burkina Faso (DGCMEF / Quotidien des marchés publics).
Ton rôle est d'analyser un extrait de délibération ou de dépouillement SPÉCIFIQUEMENT pour une ENTREPRISE CIBLE.

Tu dois répondre UNIQUEMENT par un objet JSON valide, sans balise superflue.

RÈGLES D'INTERPRÉTATION :
1. "concerne_entreprise" : true si l'entreprise cible apparaît comme candidate, soumissionnaire, retenue ou attributaire. Si son nom n'apparaît pas ou s'il s'agit d'une simple mention hors de la liste des soumissionnaires, renvoie false.
2. "est_attributaire" : true UNIQUEMENT si l'entreprise cible est désignée attributaire, adjudicataire ou expressément retenue pour la négociation/le marché.
3. "statut" :
   - "ATTRIBUTAIRE" si elle a remporté le lot.
   - "CLASSE_NON_RETENU" si elle est classée (2e, 3e, etc.) mais devancée par le moins-disant retenu.
   - "ECARTE" si son offre a été rejetée pour motif technique, financier ou administratif.
4. "rang_classement" : nombre entier correspondant au rang obtenu (1, 2, 3...) ou null si non classée.
5. "montant_propose" : montant de l'offre de l'entreprise cible (nombre en FCFA).
6. "montant_attributaire" : montant de l'offre gagnante (nombre en FCFA).
7. "nom_attributaire" : nom de l'entreprise qui a remporté le lot (si l'entreprise cible n'a pas gagné).
8. "analyse_synthese" : Rédige une synthèse claire, polie et directe de 2 à 3 phrases adressée à l'entreprise pour son dashboard. Mentionne l'autorité contractante, l'objet, le rang, le montant, et le vainqueur si applicable.
"""


def prompt_schema_exemple() -> str:
    return """{
  "concerne_entreprise": true,
  "autorite_contractante": "Ministère de l'Économie et des Finances / SG / DMP",
  "reference_dossier": "2026-079/MEF/SG/DMP",
  "objet": "Recrutement d'un consultant chargé de l'interfaçage du système informatisé de lutte contre la fraude",
  "date_attribution": "2026-08-18",
  "numero_lot": "1",
  "intitule_lot": null,
  "est_attributaire": false,
  "statut": "CLASSE_NON_RETENU",
  "rang_classement": 3,
  "note_technique": "89/100",
  "montant_propose": 19092400,
  "montant_attributaire": 16781353,
  "nom_attributaire": "SWITCH MAKER SARL",
  "delai_execution": null,
  "motif_rejet": "Classé 3ème avec note 89/100, montant plus élevé que le 1er retenu SWITCH MAKER SARL",
  "analyse_synthese": "Sur la consultation n°2026-079 de la DMP/MEF, votre offre de 19 092 400 FCFA a obtenu une note technique de 89/100, vous classant au 3ème rang. Le marché a été attribué à SWITCH MAKER SARL (16 781 353 FCFA, 1er avec 99/100)."
}"""


def analyser_marche_pour_entreprise(
    texte_marche: str,
    nom_entreprise: str,
    page_number: int,
    client_llm: Any = None,
) -> ResultatEntrepriseAI | None:
    """Interroge Gemini pour analyser précisément la décision concernant une entreprise donnée."""
    from llm_service.llm_client import call_llm

    user_prompt = (
        f"ENTREPRISE CIBLE À ANALYSER : \"{nom_entreprise}\"\n"
        f"PAGE DU BULLETIN : {page_number}\n\n"
        f"EXTRAIT DE LA DÉLIBÉRATION / DU MARCHÉ :\n"
        f"```text\n{texte_marche.strip()}\n```\n\n"
        f"Formate ta réponse STRICTEMENT selon ce format JSON (aucun texte additionnel) :\n"
        f"{prompt_schema_exemple()}"
    )

    try:
        response = call_llm(
            task=TASK,
            messages=[{"role": "user", "content": user_prompt}],
            system=SYSTEM_PROMPT_ANALYSE_ENTREPRISE,
            client=client_llm,
        )
        contenu = response.message.content or ""
        json_propre = _extraire_json_de_reponse(contenu)
        data = json.loads(json_propre)

        if not isinstance(data, dict):
            return None

        ai_res = ResultatEntrepriseAI.model_validate(data)
        return ai_res
    except Exception as exc:
        logger.error("Erreur lors de l'analyse IA du résultat pour '%s' (page %d) : %s", nom_entreprise, page_number, exc)
        return None


# --- Pipeline Asynchrone & Parallèle pour l'ensemble des entreprises ---


@dataclass
class DetectionTache:
    entreprise: Entreprise
    section: MarketSection


def detecter_mentions_entreprises(
    pages_texte: list[dict],
    entreprises: list[Entreprise],
) -> list[DetectionTache]:
    """Scanne ultra-rapidement l'intégralité des pages pour repérer chaque mention d'une entreprise abonnée."""
    signatures = construire_signatures_entreprises(entreprises)
    ent_by_id = {e.id: e for e in entreprises}

    taches: list[DetectionTache] = []

    for page_info in pages_texte:
        page_num = page_info.get("page_number", 1)
        raw_text = page_info.get("texte") or page_info.get("text") or ""
        if not raw_text.strip():
            continue

        texte_sans_acc = _sans_accents(raw_text).lower()

        # Filtrage rapide : si la page ne contient aucun terme de résultat/dépouillement, on passe
        signaux_resultat = (
            "attributaire", "soumissionnaire", "deliberation", "depouillement",
            "classement", "moins disant", "adjudicataire", "retenu", "note", "montant lu"
        )
        if not any(sig in texte_sans_acc for sig in signaux_resultat):
            continue

        # Découpe la page en marchés distincts
        marches_page = decouper_page_en_marches(page_num, raw_text)

        for marche in marches_page:
            marche_sans_acc = _sans_accents(marche.texte).lower()
            for sig in signatures:
                if sig.correspond(marche_sans_acc):
                    ent = ent_by_id[sig.entreprise_id]
                    taches.append(DetectionTache(entreprise=ent, section=marche))

    return taches


def executer_analyses_ia_paralleles(
    taches: list[DetectionTache],
    client_llm: Any = None,
    max_workers: int = 5,
) -> list[tuple[Entreprise, MarketSection, ResultatEntrepriseAI]]:
    """Exécute les appels Gemini en parallèle pour chaque mention détectée."""
    if not taches:
        return []

    logger.info(
        "Lancement de %d analyses IA ciblées en parallèle (max_workers=%d)...",
        len(taches),
        max_workers,
    )

    resultats: list[tuple[Entreprise, MarketSection, ResultatEntrepriseAI]] = []

    def _worker(t: DetectionTache):
        res_ai = analyser_marche_pour_entreprise(
            texte_marche=t.section.texte,
            nom_entreprise=t.entreprise.nom,
            page_number=t.section.page_number,
            client_llm=client_llm,
        )
        return t.entreprise, t.section, res_ai

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_worker, tache) for tache in taches]
        for future in concurrent.futures.as_completed(futures):
            try:
                ent, sec, ai_res = future.result()
                if ai_res and ai_res.concerne_entreprise:
                    resultats.append((ent, sec, ai_res))
                    logger.info(
                        "Analyse IA réussie pour '%s' (Page %d) : %s (Attributaire=%s, Rang=%s)",
                        ent.nom,
                        sec.page_number,
                        ai_res.statut,
                        ai_res.est_attributaire,
                        ai_res.rang_classement,
                    )
            except Exception as exc:
                logger.error("Erreur dans le thread d'analyse IA : %s", exc)

    return resultats


def sauvegarder_resultat_client(
    db: Session,
    *,
    entreprise: Entreprise,
    section: MarketSection,
    ai_res: ResultatEntrepriseAI,
    bulletin_numero: str,
    publication_id: int | None = None,
) -> SoumissionnaireResultat:
    """Enregistre de manière strictement idempotente le résultat analysé pour l'entreprise."""
    # 1. Recherche ou création idempotente du ResultatAttribution
    query_res = db.query(ResultatAttribution).filter(
        ResultatAttribution.bulletin_numero == str(bulletin_numero)
    )
    if ai_res.reference_dossier:
        query_res = query_res.filter(ResultatAttribution.reference_dossier == ai_res.reference_dossier)
    else:
        query_res = query_res.filter(ResultatAttribution.objet == ai_res.objet)

    res_db = query_res.first()
    date_attr = parse_llm_date(ai_res.date_attribution)

    if res_db is None:
        res_db = ResultatAttribution(
            publication_id=publication_id,
            bulletin_numero=str(bulletin_numero),
            page_source=section.page_number,
            autorite_contractante=ai_res.autorite_contractante[:255],
            reference_dossier=ai_res.reference_dossier[:255] if ai_res.reference_dossier else None,
            objet=ai_res.objet,
            date_attribution=date_attr,
            statut_deliberation="ATTRIBUE" if ai_res.est_attributaire or ai_res.nom_attributaire else "INFRUCTUEUX",
            raw_source_snippet=section.texte[:5000],
        )
        db.add(res_db)
        db.flush()
    else:
        res_db.page_source = section.page_number
        if publication_id:
            res_db.publication_id = publication_id
        if date_attr:
            res_db.date_attribution = date_attr

    # 2. Recherche ou création du Lot
    num_lot = ai_res.numero_lot or "1"
    lot_db = (
        db.query(LotResultat)
        .filter(
            LotResultat.resultat_attribution_id == res_db.id,
            LotResultat.numero_lot == num_lot,
        )
        .first()
    )
    if lot_db is None:
        lot_db = LotResultat(
            resultat_attribution_id=res_db.id,
            numero_lot=num_lot,
            intitule_lot=ai_res.intitule_lot,
            statut_lot="ATTRIBUE",
        )
        db.add(lot_db)
        db.flush()

    # 3. Enregistrement ou mise à jour du SoumissionnaireResultat pour l'entreprise
    soum_db = (
        db.query(SoumissionnaireResultat)
        .filter(
            SoumissionnaireResultat.lot_resultat_id == lot_db.id,
            SoumissionnaireResultat.entreprise_id == entreprise.id,
        )
        .first()
    )

    montant_dec = Decimal(str(ai_res.montant_propose)) if ai_res.montant_propose else None
    synth_motif = ai_res.analyse_synthese or ai_res.motif_rejet

    if soum_db is None:
        soum_db = SoumissionnaireResultat(
            lot_resultat_id=lot_db.id,
            entreprise_id=entreprise.id,
            nom_entreprise_brut=entreprise.nom[:255],
            nom_entreprise_normalise=_sans_accents(entreprise.nom).lower()[:255],
            ifu_extrait=entreprise.numero_identification,
            rccm_extrait=entreprise.rccm,
            est_attributaire=ai_res.est_attributaire,
            statut=ai_res.statut[:30],
            rang_classement=ai_res.rang_classement,
            montant_lu=montant_dec,
            montant_corrige=montant_dec,
            delai_execution=ai_res.delai_execution[:100] if ai_res.delai_execution else None,
            motif_rejet=synth_motif,
            score_matching=1.0,
            methode_matching="RECHERCHE_CIBLEE_IA",
            statut_reconciliation="EXACT",
        )
        db.add(soum_db)
        db.flush()
    else:
        soum_db.est_attributaire = ai_res.est_attributaire
        soum_db.statut = ai_res.statut[:30]
        soum_db.rang_classement = ai_res.rang_classement
        soum_db.montant_lu = montant_dec
        soum_db.montant_corrige = montant_dec
        soum_db.motif_rejet = synth_motif
        soum_db.score_matching = 1.0
        soum_db.methode_matching = "RECHERCHE_CIBLEE_IA"
        soum_db.statut_reconciliation = "EXACT"

    # 4. Si l'entreprise n'a pas gagné mais qu'un attributaire gagnant est désigné,
    # enregistrer l'attributaire sur le lot pour l'affichage de comparaison Dashboard
    if not ai_res.est_attributaire and ai_res.nom_attributaire:
        gagnant_existant = (
            db.query(SoumissionnaireResultat)
            .filter(
                SoumissionnaireResultat.lot_resultat_id == lot_db.id,
                SoumissionnaireResultat.est_attributaire.is_(True),
            )
            .first()
        )
        if gagnant_existant is None:
            montant_gagnant_dec = (
                Decimal(str(ai_res.montant_attributaire)) if ai_res.montant_attributaire else None
            )
            gagnant_soum = SoumissionnaireResultat(
                lot_resultat_id=lot_db.id,
                entreprise_id=None,
                nom_entreprise_brut=ai_res.nom_attributaire[:255],
                nom_entreprise_normalise=_sans_accents(ai_res.nom_attributaire).lower()[:255],
                est_attributaire=True,
                statut="ATTRIBUTAIRE",
                rang_classement=1,
                montant_lu=montant_gagnant_dec,
                montant_corrige=montant_gagnant_dec,
                motif_rejet=None,
                score_matching=1.0,
                methode_matching="IA_ATTRIBUTAIRE_LOT",
                statut_reconciliation="NON_ASSIGNE",
            )
            db.add(gagnant_soum)
            db.flush()

    db.commit()
    db.refresh(soum_db)
    return soum_db
