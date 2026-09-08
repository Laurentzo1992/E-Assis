from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from api.database import SessionLocal
from api.models.backend import Alerte, Marche, Publication
from api.models.entreprise import Entreprise
from api.scripts.match_and_alert import (
    LEXICAL_SEUIL_MOT,
    MAX_MATCHES_PAR_ENTREPRISE,
    MAX_RESCAPES_MOT_CLE,
    MOTS_CLES_SCORE_PLANCHER,
    VerificationEchouee,
    _decrire_match,
    _envoyer_alerte,
    _mots_significatifs,
    _resume_resultat,
    _rescapes_par_proximite_lexicale,
    _selectionner_marches_pertinents,
    _traiter_appels_offre,
    rattraper_profils_modifies,
)
from tests.conftest import register_and_activate
from tests.test_entreprise import PASSWORD, _login_headers


def test_garde_tous_les_matches_au_dessus_du_seuil_pas_seulement_le_meilleur():
    # Cas reel : LOGO SERVICES matchait un marche SONABHY SOC/SAAS a 0.61 et un marche materiels
    # informatiques a 0.63 - les deux largement au-dessus du seuil (0.35), mais l'ancien code
    # (argmax) ne retenait que le second, ignorant silencieusement le premier.
    similarites = np.array([0.6303, 0.6096, 0.10])
    assert _selectionner_marches_pertinents(similarites, seuil=0.35) == [0, 1]


def test_ignore_les_scores_sous_le_seuil():
    similarites = np.array([0.5, 0.2, 0.34])
    assert _selectionner_marches_pertinents(similarites, seuil=0.35) == [0]


def test_aucun_match_si_tout_est_sous_le_seuil():
    similarites = np.array([0.1, 0.2, 0.3])
    assert _selectionner_marches_pertinents(similarites, seuil=0.35) == []


def test_plafonne_a_max_matches():
    similarites = np.array([0.9, 0.8, 0.7, 0.6, 0.5, 0.4])
    resultat = _selectionner_marches_pertinents(similarites, seuil=0.35, max_matches=3)
    assert resultat == [0, 1, 2]
    assert len(resultat) <= MAX_MATCHES_PAR_ENTREPRISE


def test_ordre_decroissant_par_score():
    similarites = np.array([0.4, 0.9, 0.6])
    assert _selectionner_marches_pertinents(similarites, seuil=0.35) == [1, 2, 0]


# --- _mots_significatifs / _rescapes_par_proximite_lexicale (rescape lexical mot-a-mot) --------


def test_mots_significatifs_normalise_filtre_les_mots_vides_et_courts():
    mots = _mots_significatifs("Conception d'une Application Mobile de Contrôle")
    assert "application" in mots
    assert "mobile" in mots
    assert "controle" in mots  # accents supprimes
    assert "une" not in mots  # trop court
    assert "de" not in mots  # mot vide


def test_mots_significatifs_dedoublonne_en_gardant_lordre():
    mots = _mots_significatifs("logiciel systeme logiciel base")
    assert mots == ["logiciel", "systeme", "base"]


def _fake_embed_carfo(texts):
    # "application" et "logiciel" sont synonymes (memes coordonnees) ; "administration" et tout le
    # reste sont mutuellement sans rapport (coordonnees orthogonales) - reproduit le cas reel :
    # score de phrase entiere dilue (0.28) mais score mot-a-mot fort (application ~ logiciel).
    vecteurs = []
    for t in texts:
        if t in ("application", "logiciel"):
            vecteurs.append([1.0, 0.0, 0.0])
        elif t == "administration":
            vecteurs.append([0.0, 1.0, 0.0])
        else:
            vecteurs.append([0.0, 0.0, 1.0])
    return vecteurs


def test_rescapes_par_proximite_lexicale_cas_reel_carfo():
    # Cas reel qui a motive cette fonctionnalite : marche CARFO "recrutement d'un cabinet pour la
    # mise en place d'une application mobile de controle de vie et de paiement des pensionnes"
    # score de phrase 0.28 (sous le seuil de 0.35, vocabulaire domine par le contexte pension) -
    # rescape car le mot "application" de l'objet est lexicalement tres proche du libelle
    # "logiciel" du profil, meme si aucun des deux textes ne contient litteralement l'autre.
    marches = [
        SimpleNamespace(
            objet="Recrutement d'un cabinet pour la mise en place d'une application mobile de "
            "controle de vie et de paiement des pensionnes"
        ),
        SimpleNamespace(objet="Travaux de rehabilitation du poste electrique"),
    ]
    similarites = np.array([0.28, 0.26])
    rescapes = _rescapes_par_proximite_lexicale(
        _fake_embed_carfo, marches, similarites, ["logiciel", "administration"], deja_selectionnes=set()
    )
    assert rescapes == [0]


def test_rescapes_par_proximite_lexicale_exclut_les_deja_selectionnes():
    marches = [SimpleNamespace(objet="Fourniture de logiciel et application de gestion")]
    similarites = np.array([0.9])
    rescapes = _rescapes_par_proximite_lexicale(
        _fake_embed_carfo, marches, similarites, ["logiciel"], deja_selectionnes={0}
    )
    assert rescapes == []


def test_rescapes_par_proximite_lexicale_exige_le_score_plancher_de_phrase():
    # Meme avec un mot parfaitement synonyme, un marche dont le score de PHRASE est trop bas
    # n'est jamais candidat au rescape - protege contre un mot isole matchant par hasard sur un
    # marche par ailleurs completement hors sujet.
    marches = [SimpleNamespace(objet="Fourniture de logiciel et application de gestion")]
    similarites = np.array([MOTS_CLES_SCORE_PLANCHER - 0.01])
    rescapes = _rescapes_par_proximite_lexicale(
        _fake_embed_carfo, marches, similarites, ["logiciel"], deja_selectionnes=set()
    )
    assert rescapes == []


def test_rescapes_par_proximite_lexicale_rejette_les_correspondances_mot_a_mot_faibles():
    # "cabinet" et "systeme" n'ont rien a voir malgre un score mot-a-mot non nul (~0.41 en reel,
    # sous le seuil de 0.55) - doit rester ignore, sinon la comparaison mot-a-mot (plus permissive
    # que la phrase entiere) redevient trop bruitee pour etre utile.
    def fake_embed_faible(texts):
        vecteurs = []
        for t in texts:
            if t == "cabinet":
                vecteurs.append([0.41, (1 - 0.41**2) ** 0.5])
            elif t == "systeme":
                vecteurs.append([1.0, 0.0])
            else:
                vecteurs.append([0.0, 1.0])
        return vecteurs

    marches = [SimpleNamespace(objet="Recrutement d'un cabinet de conseil juridique")]
    similarites = np.array([0.30])
    rescapes = _rescapes_par_proximite_lexicale(
        fake_embed_faible, marches, similarites, ["systeme"], deja_selectionnes=set()
    )
    assert rescapes == []


def test_rescapes_par_proximite_lexicale_plafonne_et_trie_par_score_lexical_pas_score_de_phrase():
    # Le classement/plafonnage doit se faire sur le score LEXICAL (le signal qui justifie le
    # rescape), pas sur le score de phrase - sinon un marche au score de phrase par ailleurs
    # correct mais au rapprochement lexical faible pourrait evincer un rescape plus fort comme
    # "application"/"logiciel" (0.73), qui a justement un score de phrase plus bas (0.28) - c'est
    # exactement le probleme que ce mecanisme est cense corriger.
    scores_mot = {"alpha": 0.60, "beta": 0.75, "gamma": 0.58, "delta": 0.65, "epsilon": 0.90}

    def fake_embed(texts):
        vecteurs = []
        for t in texts:
            if t == "logiciel":
                vecteurs.append([1.0, 0.0])
            elif t in scores_mot:
                s = scores_mot[t]
                vecteurs.append([s, (1 - s**2) ** 0.5])
            else:
                vecteurs.append([0.0, 1.0])
        return vecteurs

    mots_ordonnes = list(scores_mot)
    marches = [SimpleNamespace(objet=f"Fourniture {mot}") for mot in mots_ordonnes]
    # Score de phrase IDENTIQUE pour tous : seul le score lexical peut donc expliquer le classement.
    similarites = np.full(len(marches), 0.30)

    rescapes = _rescapes_par_proximite_lexicale(fake_embed, marches, similarites, ["logiciel"], deja_selectionnes=set())

    attendu = sorted(range(len(marches)), key=lambda i: scores_mot[mots_ordonnes[i]], reverse=True)[:MAX_RESCAPES_MOT_CLE]
    assert rescapes == attendu


# --- Calibration des seuils lexicaux contre le VRAI modele d'embedding -------------------------
#
# Tous les tests ci-dessus mockent embed_texts avec des vecteurs synthetiques choisis pour
# reproduire des scores connus - ils prouvent que l'arithmetique de _rescapes_par_proximite_lexicale
# est correcte, jamais que LEXICAL_SEUIL_MOT/MOTS_CLES_SCORE_PLANCHER sont eux-memes bien calibres
# contre le modele reellement utilise en production. Ce test appelle le vrai embed_texts (donc
# necessite torch/sentence-transformers, indisponible sur ce poste Windows - se saute proprement
# ici, tourne reellement dans le conteneur ingest et en CI) sur le cas reel qui a motive cette
# fonctionnalite (CARFO, "application" vs "logiciel") et un cas de bruit connu ("cabinet" vs
# "systeme"), pour detecter une derive si le modele d'embedding change un jour.


def test_seuil_lexical_calibre_contre_le_vrai_modele(monkeypatch):
    try:
        import sentence_transformers  # noqa: F401
    except (ImportError, OSError) as exc:
        pytest.skip(f"sentence-transformers/torch indisponible sur cet hote : {exc}")

    from ingestion.embed import embed_texts

    vecteurs = np.array(embed_texts(["application", "logiciel", "cabinet", "systeme"]))
    v_application, v_logiciel, v_cabinet, v_systeme = vecteurs

    score_vrai_rapprochement = float(v_application @ v_logiciel)
    score_faux_ami = float(v_cabinet @ v_systeme)

    # Cas reel CARFO : doit rester au-dessus du seuil pour continuer a etre rescape.
    assert score_vrai_rapprochement >= LEXICAL_SEUIL_MOT, (
        f"'application' vs 'logiciel' score {score_vrai_rapprochement:.3f}, sous LEXICAL_SEUIL_MOT "
        f"({LEXICAL_SEUIL_MOT}) - le cas reel qui a motive le rescape lexical ne serait plus rattrape."
    )
    # Faux ami connu : doit rester sous le seuil pour ne jamais generer de faux positif.
    assert score_faux_ami < LEXICAL_SEUIL_MOT, (
        f"'cabinet' vs 'systeme' score {score_faux_ami:.3f}, au-dessus de LEXICAL_SEUIL_MOT "
        f"({LEXICAL_SEUIL_MOT}) - risque de faux positifs sur des marches sans rapport."
    )


# --- _traiter_appels_offre : profil multi-libelles + verification LLM de pertinence -----------


def _entreprise_factice(libelles_domaines, libelles_secteurs=()):
    return SimpleNamespace(
        id=1, nom="Boite Test",
        domaines=[SimpleNamespace(libelle=lib) for lib in libelles_domaines],
        secteurs=[SimpleNamespace(nom=lib) for lib in libelles_secteurs],
    )


def _appeler_traiter_appels_offre(entreprise, marches, marche_vectors, fake_embed, **kwargs):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    publication = SimpleNamespace(id=99)
    return _traiter_appels_offre(
        db, entreprise, marches, np.array(marche_vectors), fake_embed,
        resoudre_publication=lambda marche: publication,
        resoudre_page_number=lambda marche, idx: None,
        pdf_doc=None,
        dry_run=True,
        **kwargs,
    )


def test_traiter_appels_offre_matche_via_le_meilleur_libelle_pas_un_profil_dilue(monkeypatch):
    # Cas motivant le passage a un score par libelle (pas un profil concatene en une seule
    # chaine embeddee) : un profil "BTP, Informatique" se diluait en un vecteur moyen qui ne
    # matchait fort avec aucun des deux domaines pris isolement. Ici seul "Informatique" est
    # proche du marche - doit quand meme matcher grace au MEILLEUR score parmi les libelles.
    def fake_embed(texts):
        return [[1.0, 0.0] if t == "Informatique" or "materiel informatique" in t.lower() else [0.0, 1.0] for t in texts]

    monkeypatch.setattr("api.scripts.match_and_alert.resumer_objet", lambda objet, langue="fr": "resume court")
    monkeypatch.setattr("api.scripts.match_and_alert.verifier_pertinence", lambda libelles, objet: True)

    entreprise = _entreprise_factice(["BTP", "Informatique"])
    marches = [SimpleNamespace(id=42, objet="Fourniture de materiel informatique", ministere=None, page_number=None)]

    nb, echec = _appeler_traiter_appels_offre(entreprise, marches, [[1.0, 0.0]], fake_embed)

    assert nb == 1
    assert echec is False


def test_traiter_appels_offre_ecarte_un_candidat_juge_non_pertinent_par_le_llm(monkeypatch):
    # Le score semantique seul ne suffit pas (cas reel documente dans le module : un profil
    # "informatique/securite" matchant un tableau d'evaluation de scanners sans rapport) - la
    # verification LLM doit pouvoir ecarter un candidat malgre un score eleve.
    fake_embed = lambda texts: [[1.0, 0.0] for _ in texts]  # noqa: E731

    monkeypatch.setattr("api.scripts.match_and_alert.resumer_objet", lambda objet, langue="fr": "resume court")
    monkeypatch.setattr("api.scripts.match_and_alert.verifier_pertinence", lambda libelles, objet: False)

    entreprise = _entreprise_factice(["Informatique"])
    marches = [SimpleNamespace(id=42, objet="Marche hors sujet malgre un score eleve", ministere=None, page_number=None)]

    nb, echec = _appeler_traiter_appels_offre(entreprise, marches, [[1.0, 0.0]], fake_embed)

    assert nb == 0
    assert echec is False


def test_traiter_appels_offre_garde_le_candidat_si_la_verification_llm_echoue(monkeypatch):
    # Fail-open : un hoquet du LLM (Ollama indisponible, reponse invalide meme apres retry) ne
    # doit jamais faire perdre silencieusement une opportunite reelle - le candidat est garde par
    # defaut, pas ecarte.
    fake_embed = lambda texts: [[1.0, 0.0] for _ in texts]  # noqa: E731

    def verification_qui_echoue(libelles, objet):
        raise VerificationEchouee("Ollama injoignable (simule)")

    monkeypatch.setattr("api.scripts.match_and_alert.resumer_objet", lambda objet, langue="fr": "resume court")
    monkeypatch.setattr("api.scripts.match_and_alert.verifier_pertinence", verification_qui_echoue)

    entreprise = _entreprise_factice(["Informatique"])
    marches = [SimpleNamespace(id=42, objet="Marche informatique", ministere=None, page_number=None)]

    nb, echec = _appeler_traiter_appels_offre(entreprise, marches, [[1.0, 0.0]], fake_embed)

    assert nb == 1
    assert echec is False


def test_traiter_appels_offre_passe_la_langue_alertes_a_resumer_objet(monkeypatch):
    # entreprise.langue_alertes (contenu des alertes, cf. api/models/entreprise.py) doit se
    # propager jusqu'a resumer_objet - c'est ce qui garantit un resume WhatsApp redige dans la
    # bonne langue pour une entreprise non francophone.
    captured = {}

    def fake_resumer_objet(objet, langue="fr"):
        captured["langue"] = langue
        return "resume"

    fake_embed = lambda texts: [[1.0, 0.0] for _ in texts]  # noqa: E731

    monkeypatch.setattr("api.scripts.match_and_alert.resumer_objet", fake_resumer_objet)
    monkeypatch.setattr("api.scripts.match_and_alert.verifier_pertinence", lambda libelles, objet: True)

    entreprise = _entreprise_factice(["Informatique"])
    entreprise.langue_alertes = "en"
    marches = [SimpleNamespace(id=42, objet="Marche informatique", ministere=None, page_number=None)]

    nb, echec = _appeler_traiter_appels_offre(entreprise, marches, [[1.0, 0.0]], fake_embed)

    assert nb == 1
    assert echec is False
    assert captured["langue"] == "en"


def test_traiter_appels_offre_sans_langue_alertes_retombe_sur_fr(monkeypatch):
    # Une entreprise sans langue_alertes explicite (attribut absent, comme les entreprises
    # factices des autres tests de ce fichier, ou valeur None comme avant tout choix explicite en
    # base) doit tout de meme fonctionner, avec un repli sur le francais.
    captured = {}

    def fake_resumer_objet(objet, langue="fr"):
        captured["langue"] = langue
        return "resume"

    fake_embed = lambda texts: [[1.0, 0.0] for _ in texts]  # noqa: E731

    monkeypatch.setattr("api.scripts.match_and_alert.resumer_objet", fake_resumer_objet)
    monkeypatch.setattr("api.scripts.match_and_alert.verifier_pertinence", lambda libelles, objet: True)

    entreprise = _entreprise_factice(["Informatique"])  # pas de langue_alertes du tout
    marches = [SimpleNamespace(id=42, objet="Marche informatique", ministere=None, page_number=None)]

    _appeler_traiter_appels_offre(entreprise, marches, [[1.0, 0.0]], fake_embed)

    assert captured["langue"] == "fr"


# --- _decrire_match (revue --dry-run) --------------------------------------------------------


def test_decrire_match_appel_offre_affiche_le_score():
    entreprise = SimpleNamespace(nom="LOGO SERVICES")
    marche = SimpleNamespace(objet="Fourniture de materiel informatique")
    texte = _decrire_match(entreprise, marche, "marche", "resume court", score=0.63, deja_alerte=False)
    assert "LOGO SERVICES" in texte
    assert "score=0.63" in texte
    assert "nouveau" in texte


def test_decrire_match_resultat_sans_score_indique_resultat_direct():
    entreprise = SimpleNamespace(nom="FZ SERVICES SARL")
    marche = SimpleNamespace(objet="Marche deja attribue")
    texte = _decrire_match(entreprise, marche, "resultat", "resume", score=None, deja_alerte=True)
    assert "resultat direct" in texte
    assert "deja alerte precedemment" in texte


# --- _envoyer_alerte : choix du destinataire email ---------------------------------------------


def _publication_marche_factices(objet="Objet complet du marche, pas tronque"):
    publication = SimpleNamespace(id=1, numero="4464", date_publication=date(2026, 8, 12))
    marche = SimpleNamespace(id=100, objet=objet)
    return publication, marche


def test_envoyer_alerte_utilise_toujours_lemail_de_lentreprise(monkeypatch):
    # Cas reel qui a motive ce correctif : "LOGO SERVICES" a l'email de contact
    # laurent.nikiema@logo-services.com, mais ses 15 premieres alertes partaient sur l'email du
    # compte (celui qui a cree l'entreprise), jamais consulte par l'entreprise elle-meme.
    # Depuis, entreprise.email n'a plus de repli sur owner.email dans _envoyer_alerte : il est
    # garanti non-vide des la creation par create_entreprise (cf. tests/test_entreprise.py),
    # pre-rempli avec l'email du compte mais modifiable ensuite - _envoyer_alerte n'a donc plus
    # jamais besoin de regarder owner.email, meme s'il est present sur l'objet.
    captures = {}
    monkeypatch.setattr(
        "api.scripts.match_and_alert.send_alert_email",
        lambda destinataire, *a, **k: captures.setdefault("destinataire", destinataire),
    )
    entreprise = SimpleNamespace(
        id=10, nom="LOGO SERVICES", telephone=None,
        email="laurent.nikiema@logo-services.com",
        owner=SimpleNamespace(email="vuneemtech@gmail.com"),
    )
    publication, marche = _publication_marche_factices()

    ok = _envoyer_alerte(MagicMock(), entreprise, publication, marche, "marche", "resume", "DGCMEF", None, None)

    assert ok is True
    assert captures["destinataire"] == "laurent.nikiema@logo-services.com"


# --- _envoyer_alerte : email/contenu_alerte jamais tronques pour un appel d'offre --------------


def test_envoyer_alerte_marche_utilise_lobjet_complet_pas_le_resume_whatsapp_tronque(monkeypatch):
    # Cas reel qui a motive ce correctif : resumer_objet() tronque a 100 caracteres pour la
    # contrainte de gabarit WhatsApp (cf. llm_service/whatsapp_prompts.py) - mais ce meme texte
    # tronque etait aussi envoye dans l'email et enregistre dans Alerte.contenu_alerte (affiche au
    # tableau de bord), qui n'ont pourtant aucune contrainte de longueur.
    objet_complet = "Objet du marche largement plus long que la limite WhatsApp de cent caracteres, jamais tronque en email"
    resume_whatsapp_tronque = objet_complet[:50] + "..."

    captures = {}
    monkeypatch.setattr(
        "api.scripts.match_and_alert.send_alert_email",
        lambda destinataire, nom, contenu, *a, **k: captures.setdefault("contenu_email", contenu),
    )
    entreprise = SimpleNamespace(
        id=12, nom="Boite Test", telephone=None, email="contact@example.com",
        owner=SimpleNamespace(email="compte@example.com"),
    )
    publication, marche = _publication_marche_factices(objet=objet_complet)
    db = MagicMock()

    ok = _envoyer_alerte(db, entreprise, publication, marche, "marche", resume_whatsapp_tronque, "DGCMEF", None, None)

    assert ok is True
    assert captures["contenu_email"] == objet_complet
    alerte_enregistree = db.add.call_args.args[0]
    assert alerte_enregistree.contenu_alerte == objet_complet


def test_envoyer_alerte_resultat_garde_le_resume_synthetique(monkeypatch):
    # Pour un resultat, `resume` est deja une phrase synthetique complete (cf. _resume_resultat) -
    # pas de raison de la remplacer par marche.objet brut, contrairement au cas "marche".
    captures = {}
    monkeypatch.setattr(
        "api.scripts.match_and_alert.send_alert_email",
        lambda destinataire, nom, contenu, *a, **k: captures.setdefault("contenu_email", contenu),
    )
    entreprise = SimpleNamespace(
        id=13, nom="Boite Test", telephone=None, email="contact@example.com",
        owner=SimpleNamespace(email="compte@example.com"),
    )
    publication, marche = _publication_marche_factices()
    resume_resultat = "Attributaire retenu pour : Objet quelconque (12 000 000 FCFA)"

    ok = _envoyer_alerte(MagicMock(), entreprise, publication, marche, "resultat", resume_resultat, "DGCMEF", None, None)

    assert ok is True
    assert captures["contenu_email"] == resume_resultat


# --- _resume_resultat : gabarits en dur par langue (pas de LLM) --------------------------------


def test_resume_resultat_gabarit_francais_par_defaut():
    resultat = SimpleNamespace(montant_attribue=12_000_000)
    marche = SimpleNamespace(objet="Fourniture de materiel informatique")
    assert _resume_resultat(resultat, marche) == "Attributaire retenu pour : Fourniture de materiel informatique (12 000 000 FCFA)"


def test_resume_resultat_gabarit_anglais():
    resultat = SimpleNamespace(montant_attribue=12_000_000)
    marche = SimpleNamespace(objet="Fourniture de materiel informatique")
    resume = _resume_resultat(resultat, marche, langue="en")
    assert resume.startswith("Winning bidder for: Fourniture de materiel informatique")


def test_resume_resultat_gabarit_langue_inconnue_retombe_sur_le_francais():
    resultat = SimpleNamespace(montant_attribue=None)
    marche = SimpleNamespace(objet="Objet quelconque")
    resume = _resume_resultat(resultat, marche, langue="xx")
    assert resume.startswith("Attributaire retenu pour :")


# --- _envoyer_alerte : traduction du contenu email pour une langue non francaise ----------------


def test_envoyer_alerte_traduit_lobjet_pour_une_entreprise_non_francophone(monkeypatch):
    # marche.objet est toujours redige en francais (extraction LLM depuis le bulletin DGCMEF) -
    # une entreprise dont langue_alertes != "fr" doit recevoir une version traduite dans l'email,
    # via llm_service.traduction_prompts.traduire_texte (cf. api/scripts/match_and_alert.py).
    captures = {}
    monkeypatch.setattr(
        "api.scripts.match_and_alert.traduire_texte",
        lambda texte, langue_cible: f"[{langue_cible}] {texte}",
    )
    monkeypatch.setattr(
        "api.scripts.match_and_alert.send_alert_email",
        lambda destinataire, nom, contenu, *a, **k: captures.update({"contenu": contenu, "langue": k.get("langue")}),
    )
    entreprise = SimpleNamespace(
        id=14, nom="Boite EN", telephone=None, email="contact@example.com",
        owner=SimpleNamespace(email="compte@example.com"), langue_alertes="en",
    )
    publication, marche = _publication_marche_factices(objet="Objet en francais")

    ok = _envoyer_alerte(
        MagicMock(), entreprise, publication, marche, "marche", "resume", "DGCMEF", None, None, langue="en"
    )

    assert ok is True
    assert captures["contenu"] == "[en] Objet en francais"
    assert captures["langue"] == "en"


def test_envoyer_alerte_langue_fr_ne_traduit_pas(monkeypatch):
    # Court-circuit documente (cf. traduire_texte) : pas d'appel LLM de traduction pour une
    # entreprise francophone (langue par defaut, "fr" explicite ou omis) - un mock qui leve une
    # exception s'il est appele prouve que traduire_texte n'est jamais sollicite dans ce cas.
    def traduire_texte_qui_ne_doit_jamais_etre_appele(texte, langue_cible):
        raise AssertionError("traduire_texte ne doit pas etre appele pour une entreprise francophone")

    monkeypatch.setattr("api.scripts.match_and_alert.traduire_texte", traduire_texte_qui_ne_doit_jamais_etre_appele)
    captures = {}
    monkeypatch.setattr(
        "api.scripts.match_and_alert.send_alert_email",
        lambda destinataire, nom, contenu, *a, **k: captures.update({"contenu": contenu}),
    )
    entreprise = SimpleNamespace(
        id=15, nom="Boite FR", telephone=None, email="contact@example.com",
        owner=SimpleNamespace(email="compte@example.com"),
    )
    publication, marche = _publication_marche_factices(objet="Objet en francais")

    ok = _envoyer_alerte(MagicMock(), entreprise, publication, marche, "marche", "resume", "DGCMEF", None, None)

    assert ok is True
    assert captures["contenu"] == "Objet en francais"


def test_envoyer_alerte_resultat_ne_traduit_jamais_le_resume(monkeypatch):
    # Pour un resultat, `resume` est deja dans la bonne langue au moment de l'appel (cf.
    # _resume_resultat appele avec `langue` par l'appelant) - _envoyer_alerte ne doit jamais le
    # faire passer par traduire_texte, meme pour une entreprise non francophone.
    def traduire_texte_qui_ne_doit_jamais_etre_appele(texte, langue_cible):
        raise AssertionError("traduire_texte ne doit pas etre appele pour un resultat")

    monkeypatch.setattr("api.scripts.match_and_alert.traduire_texte", traduire_texte_qui_ne_doit_jamais_etre_appele)
    captures = {}
    monkeypatch.setattr(
        "api.scripts.match_and_alert.send_alert_email",
        lambda destinataire, nom, contenu, *a, **k: captures.update({"contenu": contenu}),
    )
    entreprise = SimpleNamespace(
        id=16, nom="Boite EN Resultat", telephone=None, email="contact@example.com",
        owner=SimpleNamespace(email="compte@example.com"), langue_alertes="en",
    )
    publication, marche = _publication_marche_factices()
    resume_deja_en_anglais = "Winning bidder for: Some object (12 000 000 FCFA)"

    ok = _envoyer_alerte(
        MagicMock(), entreprise, publication, marche, "resultat", resume_deja_en_anglais, "DGCMEF", None, None,
        langue="en",
    )

    assert ok is True
    assert captures["contenu"] == resume_deja_en_anglais


# --- _troncature_mot -----------------------------------------------------------------------------


def test_troncature_mot_coupe_au_dernier_espace_pas_au_milieu_dun_mot():
    from api.scripts.match_and_alert import _troncature_mot

    texte = "Offre de materiel bureau et informatique pour le Ministere de l'Economie, des Finances et des Affaires"
    resultat = _troncature_mot(texte, 100)
    assert resultat.endswith("...")
    assert len(resultat) <= 103
    # Ne doit jamais couper en plein milieu d'un mot comme "Affair" au lieu de "Affaires".
    dernier_mot = resultat[:-3].rsplit(" ", 1)[-1]
    assert texte.startswith(resultat[:-3])
    assert dernier_mot in texte.split()


def test_troncature_mot_ne_touche_pas_un_texte_deja_assez_court():
    from api.scripts.match_and_alert import _troncature_mot

    texte = "Texte court"
    assert _troncature_mot(texte, 100) == texte


# --- rattraper_profils_modifies (integration) -------------------------------------------------


def test_rattraper_profils_modifies_alerte_apres_maj_domaines(client, unique_email, monkeypatch):
    # sentence-transformers (donc torch) est requis pour importer ingestion.embed et le patcher -
    # indisponible sur ce poste Windows de dev (VC++ Redistributable manquant, cf. les commentaires
    # de match_and_alert.py : torch echoue au chargement de ses DLL, pas seulement a l'import,
    # d'ou le OSError attrape en plus de l'ImportError habituel de pytest.importorskip) : le test
    # tourne reellement dans le conteneur ingest (Linux, torch installe correctement) et en CI,
    # mais se saute proprement ici plutot que de faire echouer toute la suite.
    try:
        import sentence_transformers  # noqa: F401
    except (ImportError, OSError) as exc:
        pytest.skip(f"sentence-transformers/torch indisponible sur cet hote : {exc}")

    # La base de test (Postgres partagee, cf. conftest.py) accumule des Marche d'autres tests -
    # embed_texts est mocke pour ne faire matcher QUE le marche de ce test (marqueur unique dans
    # le libelle du domaine ET l'objet du marche -> vecteur [1, 0], tout le reste -> [0, 1],
    # orthogonal donc similarite nulle) : le test reste fiable quel que soit le nombre de marches
    # deja presents en base, sans dependre du plafond MAX_MATCHES_PAR_ENTREPRISE.
    marqueur = unique_email

    def fake_embed_texts(texts):
        return [[1.0, 0.0] if marqueur in t else [0.0, 1.0] for t in texts]

    monkeypatch.setattr("ingestion.embed.embed_texts", fake_embed_texts)
    monkeypatch.setattr("api.scripts.match_and_alert.resumer_objet", lambda objet, langue="fr": f"resume de {objet[:30]}")
    monkeypatch.setattr("api.scripts.match_and_alert.verifier_pertinence", lambda libelles, objet: True)
    emails_envoyes = []
    monkeypatch.setattr(
        "api.scripts.match_and_alert.send_alert_email",
        lambda *a, **k: emails_envoyes.append((a, k)),
    )

    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite Rattrapage Test", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    entreprise_id = created.json()["id"]

    domaine = client.post(
        "/api/entreprise/domaines/", headers=headers, json={"libelle": f"Informatique {marqueur}"}
    )
    domaine_id = domaine.json()["id"]

    # Cette mise a jour de profil active reellement le flag (comportement deja verifie dans
    # tests/test_entreprise.py) - on ne le pose pas "a la main" pour tester le vrai parcours.
    maj = client.put(
        f"/api/entreprise/entreprises/{entreprise_id}/",
        headers=headers,
        json={"domaine_ids": [domaine_id], "secteur_ids": []},
    )
    assert maj.status_code == 200

    db = SessionLocal()
    try:
        publication = Publication(
            titre="Quotidien test rattrapage",
            numero=f"RATTRAPAGE-{marqueur}",
            date_publication=date.today(),
            source="DGCMEF",
            type_publication="quotidien",
        )
        db.add(publication)
        db.commit()
        db.refresh(publication)

        marche = Marche(
            publication_id=publication.id,
            ministere="Ministere Test",
            objet=f"Fourniture de materiel informatique {marqueur}",
            page_number=3,
        )
        db.add(marche)
        db.commit()
        db.refresh(marche)
        marche_id = marche.id
    finally:
        db.close()

    n = rattraper_profils_modifies(jours=30)
    assert n >= 1
    assert len(emails_envoyes) >= 1

    db = SessionLocal()
    try:
        alerte = (
            db.query(Alerte)
            .filter(Alerte.entreprise_id == entreprise_id, Alerte.marche_id == marche_id)
            .one_or_none()
        )
        assert alerte is not None
        assert alerte.type_alerte == "marche"
        assert "email" in alerte.canal_alerte

        entreprise = db.get(Entreprise, entreprise_id)
        assert entreprise.profil_a_rattraper is False
    finally:
        db.close()


def test_rattraper_profils_modifies_garde_le_flag_si_lenvoi_echoue(client, unique_email, monkeypatch):
    # Cas reel qui a motive ce correctif : profil_a_rattraper etait remis a False AVANT meme de
    # tenter l'envoi (email/whatsapp) - un echec transitoire (SMTP injoignable, ici simule) perdait
    # alors l'opportunite pour de bon, sans aucun retry au prochain passage quotidien.
    try:
        import sentence_transformers  # noqa: F401
    except (ImportError, OSError) as exc:
        pytest.skip(f"sentence-transformers/torch indisponible sur cet hote : {exc}")

    marqueur = unique_email

    def fake_embed_texts(texts):
        return [[1.0, 0.0] if marqueur in t else [0.0, 1.0] for t in texts]

    monkeypatch.setattr("ingestion.embed.embed_texts", fake_embed_texts)
    monkeypatch.setattr("api.scripts.match_and_alert.resumer_objet", lambda objet, langue="fr": f"resume de {objet[:30]}")
    monkeypatch.setattr("api.scripts.match_and_alert.verifier_pertinence", lambda libelles, objet: True)
    # Entreprise sans telephone (whatsapp jamais tente) + email qui echoue systematiquement -
    # aucun canal ne reussit, comme un SMTP indisponible en conditions reelles.
    monkeypatch.setattr(
        "api.scripts.match_and_alert.send_alert_email",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("SMTP injoignable (simule)")),
    )

    register_and_activate(client, unique_email, PASSWORD)
    headers = _login_headers(client, unique_email)
    created = client.post(
        "/api/entreprise/entreprises/",
        headers=headers,
        json={"nom": "Boite Rattrapage Echec", "numero_identification": f"ID-{unique_email}", "rccm": unique_email[:20]},
    )
    entreprise_id = created.json()["id"]

    domaine = client.post(
        "/api/entreprise/domaines/", headers=headers, json={"libelle": f"Informatique {marqueur}"}
    )
    domaine_id = domaine.json()["id"]

    maj = client.put(
        f"/api/entreprise/entreprises/{entreprise_id}/",
        headers=headers,
        json={"domaine_ids": [domaine_id], "secteur_ids": []},
    )
    assert maj.status_code == 200

    db = SessionLocal()
    try:
        publication = Publication(
            titre="Quotidien test rattrapage echec",
            numero=f"RATTRAPAGE-ECHEC-{marqueur}",
            date_publication=date.today(),
            source="DGCMEF",
            type_publication="quotidien",
        )
        db.add(publication)
        db.commit()
        db.refresh(publication)

        marche = Marche(
            publication_id=publication.id,
            ministere="Ministere Test",
            objet=f"Fourniture de materiel informatique {marqueur}",
            page_number=3,
        )
        db.add(marche)
        db.commit()
        db.refresh(marche)
        marche_id = marche.id
    finally:
        db.close()

    n = rattraper_profils_modifies(jours=30)
    assert n == 0

    db = SessionLocal()
    try:
        alerte = (
            db.query(Alerte)
            .filter(Alerte.entreprise_id == entreprise_id, Alerte.marche_id == marche_id)
            .one_or_none()
        )
        assert alerte is None

        # Le coeur du correctif : le flag reste True pour que le prochain passage retente,
        # au lieu d'etre efface inconditionnellement avant meme de savoir si l'envoi a reussi.
        entreprise = db.get(Entreprise, entreprise_id)
        assert entreprise.profil_a_rattraper is True
    finally:
        db.close()
