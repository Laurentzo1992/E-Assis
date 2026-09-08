"""Service de Réconciliation d'Entités (Entity Resolution).

Régit la réconciliation entre les noms et identifiants d'entreprises extraits des
bulletins officiels (DGCMEF) et les entreprises inscrites dans la plateforme.

Respecte scrupuleusement la Règle d'Or n°2 :
- Tolérance zéro aux faux positifs d'attribution.
- Hiérarchie stricte en 3 niveaux :
  1. Concordance exacte sur identifiant fiscal / légal (IFU, RCCM)
  2. Normalisation canonique stricte (formes juridiques, accents, casse, ponctuation)
  3. Similarité trigramme (pg_trgm) avec seuil strict >= 0.85
- En cas de doute ou d'ambiguïté, flagué 'A_VERIFIER' sans émission d'alerte.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from api.models.entreprise import Entreprise

logger = logging.getLogger(__name__)

SEUIL_TRIGRAMME_STRICT = 0.85
MARGE_AMBIGUITE_TRIGRAMME = 0.04  # Si 2 candidats ont un écart < 4%, considérer ambigu

# Formes juridiques courantes à élaguer pour la forme canonique
_FORMES_JURIDIQUES = re.compile(
    r"\b("
    r"sarl\s*u|suarl|sarl|sa|sas|sasu|gie|ets|etablissement|etablissements|"
    r"ste|societe|cie|compagnie|snc|scs"
    r")\b",
    re.IGNORECASE,
)

# Localités et mentions géographiques courantes attachées aux raisons sociales dans les PV
_LOCALITES_REGEX = re.compile(
    r"\b("
    r"ouagadougou|ouaga|bobo\s*dioulasso|bobo|koudougou|banfora|burkina\s*faso"
    r")\b",
    re.IGNORECASE,
)

# Caractères non alphanumériques
_PONCTUATION_REGEX = re.compile(r"[^\w\s]", re.UNICODE)
_ESPACES_MULTIPLES = re.compile(r"\s+")


def sans_accents(texte: str) -> str:
    """Supprime les accents d'une chaîne de caractères."""
    return "".join(c for c in unicodedata.normalize("NFKD", texte) if not unicodedata.combining(c))


def normaliser_identifiant(identifiant: str | None) -> str | None:
    """Normalise un numéro IFU ou RCCM (supprime espaces, tirets et met en majuscules)."""
    if not identifiant:
        return None
    nettoye = re.sub(r"[\s\-_/.]", "", identifiant).strip().upper()
    return nettoye if nettoye else None


def normaliser_nom_canonique(nom: str | None) -> str:
    """Produit une forme canonique stricte du nom d'entreprise.

    1. Dé-accentuation
    2. Mise en minuscules
    3. Suppression des formes juridiques (SARL, SA, ETS, SUARL, GIE, etc.)
    4. Suppression de la ponctuation et caractères spéciaux
    5. Normalisation des espaces
    """
    if not nom:
        return ""

    texte = sans_accents(nom).lower()
    texte = _FORMES_JURIDIQUES.sub(" ", texte)
    texte = _LOCALITES_REGEX.sub(" ", texte)
    texte = _PONCTUATION_REGEX.sub(" ", texte)
    texte = _ESPACES_MULTIPLES.sub(" ", texte).strip()
    return texte


def generer_trigrammes(chaine: str) -> set[str]:
    """Génère l'ensemble des trigrammes d'une chaîne (aligné sur le comportement de pg_trgm).

    pg_trgm ajoute 2 espaces en préfixe et 1 espace en suffixe pour capturer les bords.
    """
    if not chaine:
        return set()
    chaine_cadree = f"  {chaine} "
    return {chaine_cadree[i : i + 3] for i in range(len(chaine_cadree) - 2)}


def similarite_trigramme(s1: str, s2: str) -> float:
    """Calcule le coefficient de similarité de trigrammes (Sørensen-Dice / pg_trgm).

    Score entre 0.0 et 1.0.
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    t1 = generer_trigrammes(s1)
    t2 = generer_trigrammes(s2)
    if not t1 or not t2:
        return 0.0

    intersection = len(t1 & t2)
    score = (2.0 * intersection) / (len(t1) + len(t2))
    return round(score, 4)


@dataclass(frozen=True)
class ReconciliationResult:
    """Résultat auditable d'une réconciliation d'entité."""

    entreprise_id: int | None
    nom_entreprise_trouve: str | None
    score: float
    methode: str  # IFU_EXACT, RCCM_EXACT, CANONICAL_EXACT, TRIGRAMME, AUCUNE
    statut: str  # EXACT, PROBABLE, A_VERIFIER, NON_ASSIGNE
    details: str

    @property
    def est_certain(self) -> bool:
        """Indique si la réconciliation est suffisamment certaine pour déclencher une notification."""
        return self.statut in ("EXACT", "PROBABLE") and self.entreprise_id is not None


class EntityResolver:
    """Moteur de résolution d'entités en mémoire et en base de données."""

    def __init__(self, db: Session):
        self.db = db
        self._entreprises_cache: list[Entreprise] | None = None
        self._cache_canoniques: dict[int, str] = {}

    def recharger_entreprises(self) -> None:
        """Charge ou rafraîchit la liste des entreprises inscrites."""
        try:
            from api.models.entreprise import Entreprise
            model = Entreprise
        except ImportError:
            model = "Entreprise"
        self._entreprises_cache = self.db.query(model).all()
        self._cache_canoniques = {
            e.id: normaliser_nom_canonique(e.nom) for e in self._entreprises_cache
        }

    def _obtenir_entreprises(self) -> list[Entreprise]:
        if self._entreprises_cache is None:
            self.recharger_entreprises()
        return self._entreprises_cache or []

    def reconcilier(
        self,
        nom_extrait: str,
        *,
        ifu_extrait: str | None = None,
        rccm_extrait: str | None = None,
    ) -> ReconciliationResult:
        """Applique la hiérarchie stricte en 3 niveaux pour réconcilier une entreprise.

        Niveau 1 : IFU exact ou RCCM exact
        Niveau 2 : Concordance canonique exacte
        Niveau 3 : Similarité trigramme (seuil >= 0.85 avec contrôle d'ambiguïté)
        """
        entreprises = self._obtenir_entreprises()
        if not entreprises:
            return ReconciliationResult(
                entreprise_id=None,
                nom_entreprise_trouve=None,
                score=0.0,
                methode="AUCUNE",
                statut="NON_ASSIGNE",
                details="Aucune entreprise inscrite en base de données.",
            )

        ifu_norm = normaliser_identifiant(ifu_extrait)
        rccm_norm = normaliser_identifiant(rccm_extrait)

        # --- NIVEAU 1 : Concordance exacte sur IFU ou RCCM ---
        if ifu_norm:
            for e in entreprises:
                e_ifu = normaliser_identifiant(e.numero_identification)
                if e_ifu and e_ifu == ifu_norm:
                    return ReconciliationResult(
                        entreprise_id=e.id,
                        nom_entreprise_trouve=e.nom,
                        score=1.0,
                        methode="IFU_EXACT",
                        statut="EXACT",
                        details=f"Concordance exacte sur IFU : {ifu_norm}",
                    )

        if rccm_norm:
            for e in entreprises:
                e_rccm = normaliser_identifiant(e.rccm)
                if e_rccm and e_rccm == rccm_norm:
                    return ReconciliationResult(
                        entreprise_id=e.id,
                        nom_entreprise_trouve=e.nom,
                        score=1.0,
                        methode="RCCM_EXACT",
                        statut="EXACT",
                        details=f"Concordance exacte sur RCCM : {rccm_norm}",
                    )

        nom_canonique_cible = normaliser_nom_canonique(nom_extrait)
        if not nom_canonique_cible:
            return ReconciliationResult(
                entreprise_id=None,
                nom_entreprise_trouve=None,
                score=0.0,
                methode="AUCUNE",
                statut="NON_ASSIGNE",
                details="Nom d'entreprise extrait vide ou inexploitable après normalisation.",
            )

        # --- NIVEAU 2 : Concordance canonique stricte ---
        candidats_canoniques: list[Entreprise] = []
        for e in entreprises:
            e_canonique = self._cache_canoniques.get(e.id, "")
            if e_canonique and e_canonique == nom_canonique_cible:
                candidats_canoniques.append(e)

        if len(candidats_canoniques) == 1:
            e = candidats_canoniques[0]
            return ReconciliationResult(
                entreprise_id=e.id,
                nom_entreprise_trouve=e.nom,
                score=1.0,
                methode="CANONICAL_EXACT",
                statut="EXACT",
                details=f"Concordance canonique exacte : '{nom_canonique_cible}' == '{self._cache_canoniques[e.id]}'",
            )
        elif len(candidats_canoniques) > 1:
            # Cas rare d'homonymie canonique entre deux entreprises inscrites
            return ReconciliationResult(
                entreprise_id=None,
                nom_entreprise_trouve=candidats_canoniques[0].nom,
                score=1.0,
                methode="CANONICAL_EXACT",
                statut="A_VERIFIER",
                details=f"Ambiguïté : {len(candidats_canoniques)} entreprises ont la même forme canonique '{nom_canonique_cible}'",
            )

        # --- NIVEAU 3 : Similarité trigramme stricte (>= 0.85) ---
        scores_trigrammes: list[tuple[float, Entreprise]] = []
        for e in entreprises:
            e_canonique = self._cache_canoniques.get(e.id, "")
            if not e_canonique:
                continue
            sim = similarite_trigramme(nom_canonique_cible, e_canonique)
            if sim >= SEUIL_TRIGRAMME_STRICT:
                scores_trigrammes.append((sim, e))

        if not scores_trigrammes:
            return ReconciliationResult(
                entreprise_id=None,
                nom_entreprise_trouve=None,
                score=0.0,
                methode="AUCUNE",
                statut="NON_ASSIGNE",
                details=f"Aucune correspondance trouvée au seuil trigramme strict de {SEUIL_TRIGRAMME_STRICT}",
            )

        scores_trigrammes.sort(key=lambda item: item[0], reverse=True)
        meilleur_score, meilleure_entreprise = scores_trigrammes[0]

        # Contrôle d'ambiguïté : si le 2ème candidat est trop proche du 1er
        if len(scores_trigrammes) > 1:
            deuxieme_score, deuxieme_entreprise = scores_trigrammes[1]
            if (meilleur_score - deuxieme_score) < MARGE_AMBIGUITE_TRIGRAMME:
                logger.warning(
                    "Ambiguïté de réconciliation trigramme pour '%s' : %s (%.2f) vs %s (%.2f)",
                    nom_extrait,
                    meilleure_entreprise.nom,
                    meilleur_score,
                    deuxieme_entreprise.nom,
                    deuxieme_score,
                )
                return ReconciliationResult(
                    entreprise_id=None,
                    nom_entreprise_trouve=meilleure_entreprise.nom,
                    score=meilleur_score,
                    methode="TRIGRAMME",
                    statut="A_VERIFIER",
                    details=(
                        f"Ambiguïté entre '{meilleure_entreprise.nom}' ({meilleur_score:.2f}) "
                        f"et '{deuxieme_entreprise.nom}' ({deuxieme_score:.2f})"
                    ),
                )

        return ReconciliationResult(
            entreprise_id=meilleure_entreprise.id,
            nom_entreprise_trouve=meilleure_entreprise.nom,
            score=meilleur_score,
            methode="TRIGRAMME",
            statut="PROBABLE",
            details=f"Correspondance trigramme satisfaisante (score={meilleur_score:.2f} >= {SEUIL_TRIGRAMME_STRICT})",
        )
