import numpy as np

from api.scripts.match_and_alert import MAX_MATCHES_PAR_ENTREPRISE, _selectionner_marches_pertinents


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
