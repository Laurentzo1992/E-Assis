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
  (domaines + secteurs de l'entreprise, un score par libelle plutot qu'un profil concatene en une
  seule chaine - cf. `_traiter_appels_offre`), restreinte aux `Marche` qui n'ont PAS de `Resultat`
  associe (donc jamais un tableau d'attribution) et comparee au texte structure `Marche.objet`
  (issu de l'extraction LLM, donc deja nettoye) plutot qu'au chunk brut. Chaque candidat retenu
  par le score est ensuite juge individuellement par `llm_service.matching_prompts.verifier_pertinence`
  avant redaction/envoi - un score cosinus eleve ne garantit pas une pertinence reelle (meme
  phenomene que ci-dessus, applique cette fois aux appels d'offres plutot qu'aux resultats).

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
import re
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
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
from api.scripts.extract_bulletin import _sans_accents
from api.whatsapp_client import WhatsAppSendError, send_whatsapp_template
from ingestion import config as ingestion_config
from ingestion import qdrant_store
from llm_service.matching_prompts import VerificationEchouee, verifier_pertinence
from llm_service.traduction_prompts import traduire_texte
from llm_service.whatsapp_prompts import RedactionEchouee, _troncature_mot, resumer_objet

logger = logging.getLogger(__name__)

# Nombre max d'alertes "marche" (appel d'offre) envoyees a une meme entreprise pour un meme
# bulletin - garde-fou anti-spam au cas ou de tres nombreux marches depasseraient le seuil pour un
# profil tres large, tout en couvrant tous les cas reels observes (jamais plus de 2-3 candidats
# au-dessus du seuil sur les bulletins testes).
MAX_MATCHES_PAR_ENTREPRISE = 5

# Budget separe pour les marches "rescapes" par proximite lexicale (cf.
# _rescapes_par_proximite_lexicale) - une categorie de signal differente (plus rare, mais aussi
# moins fiable que le score semantique de phrase), qui ne doit jamais evincer un match semantique
# fort du plafond principal.
MAX_RESCAPES_MOT_CLE = 3

# Score de PHRASE ENTIERE minimal pour qu'un marche soit meme candidat au rescape lexical -
# empeche un mot isole de matcher par coincidence sur un marche completement hors-sujet (score de
# phrase proche de zero), cf. _rescapes_par_proximite_lexicale.
MOTS_CLES_SCORE_PLANCHER = 0.25

# Score MOT A MOT minimal (embedding d'un mot de l'objet contre embedding d'un libelle de
# profil) pour rescaper un marche - plus eleve que le seuil de phrase car la comparaison mot a mot
# est plus permissive (des mots isoles sans rapport direct scorent deja ~0.4, ex. "cabinet" vs
# "systeme") ; calibre sur le cas reel qui a motive cette fonctionnalite : "application" vs
# "logiciel" score 0.73.
LEXICAL_SEUIL_MOT = 0.55

# Fenetre de recherche du rattrapage (cf. rattraper_profils_modifies) : un marche publie plus tot
# que ca a tres probablement deja depasse sa date limite de depot, meme sans Resultat publie -
# aucun champ de date-limite n'est encore extrait (AppelOffre.dateDepot jamais rempli, cf.
# extract_bulletin.py) pour trancher plus precisement.
RATTRAPAGE_FENETRE_JOURS = 30


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


def _libelles_profil(entreprise: Entreprise) -> list[str]:
    return [d.libelle for d in entreprise.domaines] + [s.nom for s in entreprise.secteurs]


# Mots vides frequents dans les objets de marche - exclus des candidats a la comparaison lexicale
# (cf. _mots_significatifs) : sans valeur discriminante, leur embedding ajouterait juste du bruit
# et du cout de calcul inutile.
_MOTS_VIDES_FR = frozenset({
    "pour", "avec", "dans", "sous", "chez", "vers", "sans", "cette", "leurs", "leur", "elle",
    "elles", "ainsi", "alors", "apres", "avant", "meme", "tout", "tous", "toute", "toutes",
    "plus", "moins", "tres", "peut", "doit", "sera", "sont", "etre", "avoir", "fait", "faire",
    "lots", "lot", "marche", "marches", "profit", "cadre",
})


def _mots_significatifs(texte: str, longueur_min: int = 4) -> list[str]:
    """Mots normalises (sans accents/casse, >= longueur_min caracteres, hors mots vides), dans
    l'ordre de premiere apparition et dedoublonnes - candidats pour le rescape par proximite
    lexicale mot-a-mot (cf. _rescapes_par_proximite_lexicale)."""
    texte_normalise = _sans_accents(texte).lower()
    mots_bruts = re.findall(r"[a-z]+", texte_normalise)
    mots: list[str] = []
    for mot in mots_bruts:
        if len(mot) >= longueur_min and mot not in _MOTS_VIDES_FR and mot not in mots:
            mots.append(mot)
    return mots


def _rescapes_par_proximite_lexicale(
    embed_texts_fn,
    marches: list[Marche],
    similarites: np.ndarray,
    libelles_profil: list[str],
    deja_selectionnes: set[int],
) -> list[int]:
    """Marches sous le seuil semantique principal mais "rescapes" parce qu'au moins UN mot de leur
    objet est lexicalement tres proche d'au moins UN libelle de domaine/secteur du profil - filet
    de secours pour les avis dont le score de PHRASE ENTIERE est dilue par du vocabulaire metier
    client (constate en reel sur un marche CARFO de "recrutement d'un cabinet pour la mise en
    place d'une application mobile de controle de vie et de paiement des pensionnes", score de
    phrase 0.28, sous le seuil de 0.35, alors que "application" seul contre "logiciel" seul score
    0.73 - le mot-cle pertinent existe bel et bien, juste noye dans une longue phrase administrative).

    Une simple sous-chaine exacte du libelle ("logiciel" dans le texte) ne suffit PAS ici : le
    profil utilise des categories ("logiciel", "developement") quand l'objet utilise des termes
    concrets ("application") - synonymes, pas la meme chaine. D'ou la comparaison par embedding
    mot a mot plutot qu'un simple "in".

    Deux garde-fous contre le bruit (la comparaison mot a mot est plus permissive que la phrase
    entiere - "cabinet" seul contre "systeme" seul score deja 0.41) :
    - LEXICAL_SEUIL_MOT eleve (0.55) : ne retient que les rapprochements forts comme
      application/logiciel, pas les faux amis comme cabinet/systeme.
    - MOTS_CLES_SCORE_PLANCHER sur le score de PHRASE : le marche doit deja avoir un minimum de
      pertinence globale avant meme d'etre candidat, pas juste un mot isole qui matche par hasard
      sur un marche par ailleurs totalement hors sujet."""
    candidats = [
        i for i in range(len(marches)) if i not in deja_selectionnes and similarites[i] >= MOTS_CLES_SCORE_PLANCHER
    ]
    if not candidats or not libelles_profil:
        return []

    mots_par_marche = {i: _mots_significatifs(marches[i].objet) for i in candidats}
    tous_les_mots = sorted({mot for mots in mots_par_marche.values() for mot in mots})
    if not tous_les_mots:
        return []

    vecteurs_mots = np.array(embed_texts_fn(tous_les_mots))
    vecteurs_labels = np.array(embed_texts_fn(libelles_profil))
    index_mot = {mot: idx for idx, mot in enumerate(tous_les_mots)}

    # Meilleur score par MOT (contre tous les libelles) calcule une seule fois pour tout le
    # vocabulaire, plutot que par candidat : un mot partage par plusieurs marches (ex.
    # "informatique") voyait son produit scalaire contre vecteurs_labels recalcule une fois par
    # marche qui le contient - un seul matmul suffit, chaque candidat n'a plus qu'a lire dedans.
    scores_par_mot = (vecteurs_mots @ vecteurs_labels.T).max(axis=1)

    scores_lexicaux: dict[int, float] = {}
    for i in candidats:
        mots = mots_par_marche[i]
        if not mots:
            continue
        meilleur = float(max(scores_par_mot[index_mot[mot]] for mot in mots))
        if meilleur >= LEXICAL_SEUIL_MOT:
            scores_lexicaux[i] = meilleur

    # Trie par score LEXICAL (pas le score de phrase) : le budget doit revenir aux rapprochements
    # mot-a-mot les plus forts, pas a n'importe quel candidat qui a par ailleurs une phrase
    # globalement mieux notee - sinon plusieurs marches "matériel informatique" (deja bien notes en
    # phrase, meme sans etre selectionnes en principal) monopolisent le budget avant un vrai
    # rescape comme "application"/"logiciel" (0.73), qui a justement un score de phrase plus bas.
    return sorted(scores_lexicaux, key=lambda i: scores_lexicaux[i], reverse=True)[:MAX_RESCAPES_MOT_CLE]


def _conditions_eligibilite(maintenant: datetime):
    # Le telephone n'est plus requis ici : l'email (canal toujours disponible, adresse deja
    # verifiee a l'activation du compte) prend le relais quand WhatsApp n'est pas configurable.
    # Abonnement : essai gratuit ou abonnement paye encore valide uniquement (cf.
    # api/routers/paiement.py) - une entreprise sans essai/abonnement en cours ne doit jamais etre
    # alertee, meme si ses notifications sont actives. Partage entre _active_entreprises (un
    # bulletin, toutes les entreprises) et rattraper_profils_modifies (les entreprises marquees
    # profil_a_rattraper) pour ne jamais laisser les deux definitions diverger.
    return [
        Utilisateur.notifications_actives.is_(True),
        or_(
            Abonnement.date_fin_essai > maintenant,
            and_(Abonnement.statut == "actif", Abonnement.date_fin_abonnement > maintenant),
        ),
    ]


def _active_entreprises(db: Session) -> list[Entreprise]:
    maintenant = datetime.now(timezone.utc)
    return (
        db.query(Entreprise)
        .join(Utilisateur, Entreprise.owner_id == Utilisateur.id)
        # Abonnement est PAR COMPTE (Utilisateur), pas par Entreprise (cf. api/models/abonnement.py) -
        # .distinct() car un compte avec plusieurs entreprises heritees de l'ancien modele peut
        # temporairement avoir plusieurs lignes Abonnement (consolidation manuelle en cours depuis
        # /admin) : sans deduplication, une meme Entreprise apparaitrait plusieurs fois si plus d'un
        # de ces abonnements herites la rend eligible, doublant ses alertes pour rien.
        .join(Abonnement, Abonnement.utilisateur_id == Utilisateur.id)
        .filter(*_conditions_eligibilite(maintenant))
        .distinct()
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


def _marches_ouverts_recents(db: Session, jours: int) -> list[Marche]:
    """Comme _marches_appel_offre, mais sur TOUS les bulletins des `jours` derniers jours plutot
    qu'un seul - perimetre du rattrapage (cf. rattraper_profils_modifies) : une entreprise qui
    vient de completer son profil doit pouvoir recevoir les alertes qu'elle aurait recues si son
    profil avait ete a jour au moment de la publication, pas seulement pour le bulletin du jour."""
    depuis = date.today() - timedelta(days=jours)
    return (
        db.query(Marche)
        .join(Publication, Publication.id == Marche.publication_id)
        .outerjoin(Resultat, Resultat.marche_id == Marche.id)
        .filter(Resultat.marche_id.is_(None), Publication.date_publication >= depuis)
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


# Gabarits en dur (pas de LLM, cf. docstring de _resume_resultat) par langue de contenu d'alerte.
# Traduction moore best-effort (LLM), non verifiee par un locuteur natif - a valider avant mise en
# production reelle (meme reserve que llm_service/whatsapp_prompts.py:SYSTEM_PROMPT_MOS).
_GABARIT_RESUME_RESULTAT: dict[str, str] = {
    "fr": "Attributaire retenu pour : {objet} ({montant})",
    "en": "Winning bidder for: {objet} ({montant})",
    "mos": "Sẽn deeg tʋʋmda: {objet} ({montant})",
}


def _resume_resultat(resultat: Resultat, marche: Marche, langue: str = "fr") -> str:
    """Pas de LLM ici : l'objet et le montant viennent directement de l'extraction structuree -
    aucune reformulation, donc aucun risque de distorsion sur un fait deja etabli. `langue`
    selectionne juste le gabarit de phrase en dur (repli francais si langue inconnue)."""
    objet = _troncature_mot(marche.objet, 180)
    gabarit = _GABARIT_RESUME_RESULTAT.get(langue, _GABARIT_RESUME_RESULTAT["fr"])
    return gabarit.format(objet=objet, montant=_format_montant(resultat.montant_attribue))


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
    langue: str = "fr",
) -> bool:
    canaux_reussis: list[str] = []

    if entreprise.telephone:
        try:
            send_whatsapp_template(entreprise.telephone, parameters=[entreprise.nom, resume, organisme])
            canaux_reussis.append("whatsapp")
        except WhatsAppSendError as exc:
            logger.warning("Envoi WhatsApp echoue pour l'entreprise %s : %s", entreprise.id, exc)

    # L'email (et le contenu enregistre pour l'historique/tableau de bord, cf. Alerte.contenu_alerte
    # plus bas) n'ont AUCUNE contrainte de longueur, contrairement a la variable de gabarit WhatsApp
    # (300 caracteres, cf. llm_service/whatsapp_prompts.py) : pour un appel d'offre, on reprend
    # l'objet complet du marche (deja extrait, fiable) plutot que `resume`, tronque pour WhatsApp -
    # constate en reel, des libelles coupes en plein milieu d'un mot dans les emails et le tableau
    # de bord ("Offre de materiel bureau et informatique pour le Ministere de l'Economie, des
    # Finances et des Affair"). Pour un resultat, `resume` est deja une phrase synthetique complete
    # (cf. _resume_resultat), pas de raison de la remplacer.
    # `marche.objet` est toujours en francais (langue de l'extraction LLM depuis le bulletin
    # DGCMEF) - traduit integralement ici si l'entreprise veut ses alertes dans une autre langue
    # (cf. llm_service/traduction_prompts.py). `resume` (cas resultat) est deja dans la bonne
    # langue, cf. _resume_resultat appele avec `langue` par l'appelant.
    if type_alerte == "marche":
        contenu_complet = traduire_texte(marche.objet, langue) if langue != "fr" else marche.objet
    else:
        contenu_complet = resume

    try:
        send_alert_email(
            # Toujours l'email de contact de l'entreprise, jamais celui du compte qui l'a inscrite
            # (ex. gerant delegue la creation du compte a un tiers mais veut recevoir les alertes
            # lui-meme) - garanti non-vide par create_entreprise (pre-rempli avec l'email du
            # compte a la creation, modifiable ensuite), donc plus de repli conditionnel ici.
            entreprise.email,
            entreprise.nom,
            contenu_complet,
            organisme,
            numero_bulletin=publication.numero,
            date_bulletin=publication.date_publication.strftime("%d/%m/%Y"),
            page_number=page_number,
            page_image=_render_page_png(pdf_doc, page_number),
            langue=langue,
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
            contenu_alerte=contenu_complet,
            canal_alerte="+".join(canaux_reussis),
        )
    )
    db.commit()
    return True


def _decrire_match(
    entreprise, marche, type_alerte: str, resume: str, score: float | None, deja_alerte: bool,
    origine: str = "semantique",
) -> str:
    score_txt = f"score={score:.2f}" if score is not None else "resultat direct"
    statut = "deja alerte precedemment" if deja_alerte else "nouveau"
    origine_txt = ", rescape par mot-cle" if origine == "mot-cle" else ""
    return f"[{type_alerte}] {entreprise.nom} <- {marche.objet[:100]!r} ({score_txt}, {statut}{origine_txt})\n    resume: {resume}"


def _traiter_appels_offre(
    db: Session,
    entreprise: Entreprise,
    marches: list[Marche],
    marche_vectors_np: np.ndarray,
    embed_texts_fn,
    resoudre_publication: Callable[[Marche], Publication],
    resoudre_page_number: Callable[[Marche, int], int | None],
    pdf_doc: "fitz.Document | None",
    dry_run: bool,
) -> tuple[int, bool]:
    """Selectionne (score semantique + rescape lexical), redige et envoie (ou affiche en
    dry-run) les correspondances "appel_offre" d'une entreprise contre une liste de marches
    candidats - factorise entre match_and_alert() (un bulletin, avec dry-run/piece jointe email)
    et rattraper_profils_modifies() (plusieurs bulletins, sans piece jointe), qui dupliquaient
    ~20 lignes quasi identiques avant ce refactor, avec un risque reel de derive entre les deux
    copies (constate : seule celle de rattraper_profils_modifies n'attachait jamais de piece
    jointe, une des rares differences intentionnelles - desormais explicite via les parametres
    plutot qu'implicite par copie divergente).

    `resoudre_publication`/`resoudre_page_number` abstraient les deux seules etapes qui different
    reellement entre les deux appelants (une Publication unique pour tout le bulletin vs une par
    marche ; un repli `_locate_page` disponible seulement quand `object_name` est connu).

    Deux filtres de precision successifs avant redaction/envoi d'un candidat :
    - score semantique/lexical (ci-dessous) : mesure une proximite de sens, calcule libelle par
      libelle (pas un profil concatene en une seule chaine) - un profil a plusieurs domaines
      ("Informatique, BTP, Restauration") se diluait en un seul vecteur moyen qui ne matchait fort
      avec aucun des trois pris isolement ; on garde desormais le MEILLEUR score par marche, parmi
      tous les libelles du profil.
    - verification LLM (`verifier_pertinence`) : le score semantique seul ne distingue pas une
      vraie correspondance d'un faux positif partageant juste du vocabulaire (cf. docstring de
      module) - chaque candidat est encore juge individuellement avant d'etre redige/envoye.

    Retourne `(nb_alertes_envoyees, echec)` - `echec` est True si au moins un match trouve n'a pu
    etre ni redige ni envoye (utilise par rattraper_profils_modifies pour decider de retenter au
    prochain passage plutot que de perdre l'opportunite silencieusement, cf. son propre docstring)."""
    libelles_profil = _libelles_profil(entreprise)
    if not libelles_profil:
        return 0, False

    # Langue du CONTENU de l'alerte (pas la langue de l'interface du compte, cf.
    # Entreprise.langue_alertes) - getattr avec repli "fr" pour rester compatible avec les tests
    # qui construisent une entreprise factice (SimpleNamespace) sans cet attribut.
    langue = getattr(entreprise, "langue_alertes", None) or "fr"

    libelle_vectors = np.array(embed_texts_fn(libelles_profil))
    similarites = (marche_vectors_np @ libelle_vectors.T).max(axis=1)

    principaux = _selectionner_marches_pertinents(similarites, settings.whatsapp_min_match_score)
    rescapes = _rescapes_par_proximite_lexicale(
        embed_texts_fn, marches, similarites, libelles_profil, set(principaux)
    )
    rescapes_set = set(rescapes)

    nb_alertes = 0
    echec = False
    for idx in principaux + rescapes:
        marche = marches[idx]
        publication = resoudre_publication(marche)
        deja_alerte = _already_alerted(db, entreprise.id, publication.id, marche.id)
        if not dry_run and deja_alerte:
            continue

        try:
            pertinent = verifier_pertinence(libelles_profil, marche.objet)
        except VerificationEchouee as exc:
            logger.warning(
                "Verification de pertinence indisponible pour le marche %s / entreprise %s, "
                "candidat garde par defaut (fail-open) : %s", marche.id, entreprise.id, exc,
            )
            pertinent = True
        if not pertinent:
            logger.info(
                "Marche %s ecarte pour l'entreprise %s : score semantique suffisant mais juge non "
                "pertinent par la verification LLM", marche.id, entreprise.id,
            )
            continue

        try:
            resume = resumer_objet(marche.objet, langue=langue)
        except RedactionEchouee as exc:
            logger.warning("Redaction WhatsApp echouee pour l'entreprise %s : %s", entreprise.id, exc)
            echec = True
            continue

        if dry_run:
            origine = "mot-cle" if idx in rescapes_set else "semantique"
            print(_decrire_match(entreprise, marche, "marche", resume, float(similarites[idx]), deja_alerte, origine))
            nb_alertes += 1
            continue

        organisme = marche.ministere or "DGCMEF"
        page_number = resoudre_page_number(marche, idx)
        if _envoyer_alerte(
            db, entreprise, publication, marche, "marche", resume, organisme, page_number, pdf_doc, langue=langue
        ):
            nb_alertes += 1
        else:
            echec = True

    return nb_alertes, echec


def match_and_alert(object_name: str, dry_run: bool = False) -> int:
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
        # En dry-run, aucun email/whatsapp n'est envoye : inutile de telecharger le PDF (piece
        # jointe email uniquement) ni d'ouvrir une connexion MinIO pour une revue en lecture seule.
        pdf_doc = _fetch_bulletin_pdf(object_name) if not dry_run else None

        marches_appel_offre = _marches_appel_offre(db, publication.id)
        marche_vectors = embed_texts([m.objet for m in marches_appel_offre]) if marches_appel_offre else []
        marche_vectors_np = np.array(marche_vectors) if marche_vectors else None

        for entreprise in _active_entreprises(db):
            # 1. Resultats : le nom prime, deja resolu a l'extraction - pas de recherche semantique.
            langue = getattr(entreprise, "langue_alertes", None) or "fr"
            for resultat in _resultats_gagnes(db, publication.id, entreprise.id):
                marche = resultat.marche
                deja_alerte = _already_alerted(db, entreprise.id, publication.id, marche.id)
                resume = _resume_resultat(resultat, marche, langue=langue)

                if dry_run:
                    # Revue : on affiche TOUS les matches, meme deja alertes, pour juger de la
                    # pertinence du premier passage - l'idempotence normale (skip si deja alerte)
                    # ne s'applique qu'a l'envoi reel, jamais a la revue.
                    print(_decrire_match(entreprise, marche, "resultat", resume, None, deja_alerte))
                    nb_alertes += 1
                    continue
                if deja_alerte:
                    continue
                organisme = marche.ministere or "DGCMEF"
                page_number = marche.page_number or _locate_page(
                    qdrant_client, object_name, embed_texts([marche.objet])[0]
                )
                if _envoyer_alerte(
                    db, entreprise, publication, marche, "resultat", resume, organisme, page_number, pdf_doc,
                    langue=langue,
                ):
                    nb_alertes += 1

            # 2. Appels d'offres : recherche semantique par profil + rescape lexical (factorise,
            # cf. _traiter_appels_offre - partage avec rattraper_profils_modifies).
            if marche_vectors_np is None:
                continue
            nb, _ = _traiter_appels_offre(
                db, entreprise, marches_appel_offre, marche_vectors_np, embed_texts,
                resoudre_publication=lambda marche: publication,
                resoudre_page_number=lambda marche, idx: marche.page_number or _locate_page(
                    qdrant_client, object_name, marche_vectors[idx]
                ),
                pdf_doc=pdf_doc,
                dry_run=dry_run,
            )
            nb_alertes += nb
    finally:
        db.close()
        if pdf_doc is not None:
            pdf_doc.close()

    return nb_alertes


def rattraper_profils_modifies(jours: int = RATTRAPAGE_FENETRE_JOURS) -> int:
    """Tache DAG quotidienne independante (ne depend pas d'un nouveau bulletin, cf.
    dag_kbbot_quotidien.py) : reanalyse chaque entreprise marquee `profil_a_rattraper` (mise a
    jour de ses domaines/secteurs, cf. api/routers/entreprise.py:update_entreprise) contre tous
    les marches encore ouverts et recents, tous bulletins confondus - contrairement a
    match_and_alert qui ne regarde qu'UN bulletin a la fois. Ne rejoue jamais les Resultats (le
    rattachement d'un attributaire depend du nom/RCCM/IFU extraits, jamais des domaines/secteurs -
    cf. extract_bulletin._find_entreprise_attributaire - donc sans rapport avec un changement de
    profil).

    Idempotent via _already_alerted comme le reste du pipeline : une entreprise deja alertee sur
    un marche donne (ex. lors d'un bulletin ou son profil matchait deja) ne le sera jamais deux
    fois, meme rattrapee plusieurs fois de suite. Le flag `profil_a_rattraper` n'est efface que si
    _traiter_appels_offre n'a signale aucun echec d'envoi - une redaction ou un envoi rate reste
    marque pour retry au prochain passage plutot que de perdre l'opportunite silencieusement."""
    from ingestion.embed import embed_texts

    db = SessionLocal()
    nb_alertes = 0
    try:
        entreprises = db.query(Entreprise).filter(Entreprise.profil_a_rattraper.is_(True)).all()
        if not entreprises:
            return 0

        marches = _marches_ouverts_recents(db, jours)
        if not marches:
            for entreprise in entreprises:
                entreprise.profil_a_rattraper = False
            db.commit()
            return 0

        marche_vectors_np = np.array(embed_texts([m.objet for m in marches]))

        # Eligibilite des entreprises marquees, calculee en UNE requete plutot qu'un
        # _est_eligible(db, entreprise.id) - donc un aller-retour DB - par entreprise dans la
        # boucle ci-dessous.
        maintenant = datetime.now(timezone.utc)
        ids_eligibles = {
            id_
            for (id_,) in db.query(Entreprise.id)
            .join(Utilisateur, Entreprise.owner_id == Utilisateur.id)
            .join(Abonnement, Abonnement.utilisateur_id == Utilisateur.id)
            .filter(Entreprise.profil_a_rattraper.is_(True), *_conditions_eligibilite(maintenant))
        }

        for entreprise in entreprises:
            if entreprise.id not in ids_eligibles:
                # Reste marque "a rattraper" : retente au prochain passage (ex. essai pas encore
                # commence, abonnement expire) plutot que de perdre silencieusement le changement
                # de profil si l'entreprise redevient eligible plus tard sans re-modifier son
                # profil entre-temps.
                continue

            nb, echec = _traiter_appels_offre(
                db, entreprise, marches, marche_vectors_np, embed_texts,
                resoudre_publication=lambda marche: marche.publication,
                # Pas de repli _locate_page ici (contrairement a match_and_alert) : un rattrapage
                # peut couvrir des marches de plusieurs bulletins differents, sans object_name
                # unique a interroger dans Qdrant.
                resoudre_page_number=lambda marche, idx: marche.page_number,
                # Pas de piece jointe PDF ici non plus : un telechargement MinIO par marche serait
                # couteux pour un simple bonus visuel de l'email - best effort deja gere par
                # _render_page_png (pdf_doc=None -> pas de piece jointe).
                pdf_doc=None,
                dry_run=False,
            )
            nb_alertes += nb
            entreprise.profil_a_rattraper = echec
            db.commit()
    finally:
        db.close()

    return nb_alertes


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse un bulletin et alerte les entreprises correspondantes")
    parser.add_argument("object_name")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "N'envoie rien (ni WhatsApp ni email) et n'enregistre aucune Alerte : affiche juste "
            "les correspondances trouvees (score, entreprise, resume) pour revoir la pertinence "
            "du matching sans redemarrer l'extraction ni spammer les entreprises."
        ),
    )
    args = parser.parse_args()
    n = match_and_alert(args.object_name, dry_run=args.dry_run)
    if args.dry_run:
        print(f"{n} correspondances trouvees (revue seule, rien envoye) pour {args.object_name}")
    else:
        print(f"{n} alertes envoyees (WhatsApp et/ou email) pour {args.object_name}")


if __name__ == "__main__":
    main()
