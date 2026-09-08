"""Tests unitaires du service de Réconciliation d'Entités (Entity Resolution).

Valide la Règle d'Or n°2 :
- Niveau 1 : Exactitude IFU / RCCM
- Niveau 2 : Normalisation canonique stricte (suppression SARL, ETS, accents, etc.)
- Niveau 3 : Similarité trigramme >= 0.85
- Arbitrage d'ambiguïté et statut 'A_VERIFIER'
- Tolérance zéro aux faux positifs
"""

from types import SimpleNamespace

try:
    import pytest
except ImportError:
    pytest = None

from api.services.entity_resolution import (
    EntityResolver,
    normaliser_identifiant,
    normaliser_nom_canonique,
    similarite_trigramme,
)


def test_normalisation_identifiant():
    assert normaliser_identifiant("00012345 X") == "00012345X"
    assert normaliser_identifiant("BF-OUA-2021-B-1234") == "BFOUA2021B1234"
    assert normaliser_identifiant(None) is None
    assert normaliser_identifiant("   ") is None


def test_normalisation_nom_canonique():
    assert normaliser_nom_canonique("FZ SERVICES SARL") == "fz services"
    assert normaliser_nom_canonique("Éts Wend-Panga & Frères") == "wend panga freres"
    assert normaliser_nom_canonique("SOCIETE BURKINABE DE TECHNOLOGIE SA") == "burkinabe de technologie"
    assert normaliser_nom_canonique("GROUPE FASO TECH SUARL") == "groupe faso tech"


def test_similarite_trigramme():
    # Même chaîne
    assert similarite_trigramme("fz services", "fz services") == 1.0
    # Petite faute de frappe
    score_proche = similarite_trigramme("fz services", "fz service")
    assert score_proche >= 0.85
    # Chaînes totalement différentes
    assert similarite_trigramme("fz services", "boulangerie centrale") < 0.2


class FakeDB:
    def __init__(self, entreprises):
        self._entreprises = entreprises

    def query(self, model):
        class FakeQuery:
            def __init__(self, items):
                self._items = items

            def all(self):
                return self._items

        return FakeQuery(self._entreprises)


def test_reconciliation_niveau_1_ifu():
    e1 = SimpleNamespace(id=1, nom="FZ SERVICES SARL", numero_identification="00012345X", rccm="BF1234")
    e2 = SimpleNamespace(id=2, nom="AUTRE BOUTIQUE", numero_identification="00099999Y", rccm="BF9999")
    db = FakeDB([e1, e2])
    resolver = EntityResolver(db)

    # Recherche avec le bon IFU même si le nom extrait diffère légèrement
    res = resolver.reconcilier("FZ SERVICE INFORMATIQUE", ifu_extrait="00012345 X")
    assert res.entreprise_id == 1
    assert res.methode == "IFU_EXACT"
    assert res.statut == "EXACT"
    assert res.est_certain is True


def test_reconciliation_niveau_1_rccm():
    e1 = SimpleNamespace(id=1, nom="COMPTOIR COMMERCIAL", numero_identification="00011111A", rccm="BF-OUA-2022-B-4321")
    db = FakeDB([e1])
    resolver = EntityResolver(db)

    res = resolver.reconcilier("COMPTOIR COMMERCIAL SARL", rccm_extrait="BF-OUA-2022-B-4321")
    assert res.entreprise_id == 1
    assert res.methode == "RCCM_EXACT"
    assert res.statut == "EXACT"
    assert res.est_certain is True


def test_reconciliation_niveau_2_canonique_exact():
    e1 = SimpleNamespace(id=10, nom="SOCIETE BURKINABE D'ENERGIE SOLAIRE SA", numero_identification=None, rccm=None)
    db = FakeDB([e1])
    resolver = EntityResolver(db)

    # Nom extrait dans le bulletin : "Éts Burkinabé d'Energie Solaire SARL"
    # Les deux se réduisent à "burkinabe d energie solaire"
    res = resolver.reconcilier("Éts Burkinabé d'Energie Solaire SARL")
    assert res.entreprise_id == 10
    assert res.methode == "CANONICAL_EXACT"
    assert res.statut == "EXACT"
    assert res.est_certain is True


def test_reconciliation_niveau_3_trigramme():
    e1 = SimpleNamespace(id=20, nom="AFRIQUE PRESTATION SERVICES", numero_identification=None, rccm=None)
    db = FakeDB([e1])
    resolver = EntityResolver(db)

    # Nom extrait avec variation mineure
    res = resolver.reconcilier("AFRIQUE PRESTATIONS SERVICES SARL")
    assert res.entreprise_id == 20
    assert res.methode == "TRIGRAMME"
    assert res.statut == "PROBABLE"
    assert res.score >= 0.85
    assert res.est_certain is True


def test_reconciliation_ambiguite_flague_a_verifier():
    # Deux entreprises inscrites avec des noms très proches
    e1 = SimpleNamespace(id=30, nom="BURKINA CONSTRUCTION 1", numero_identification=None, rccm=None)
    e2 = SimpleNamespace(id=31, nom="BURKINA CONSTRUCTION 2", numero_identification=None, rccm=None)
    db = FakeDB([e1, e2])
    resolver = EntityResolver(db)

    res = resolver.reconcilier("BURKINA CONSTRUCTION")
    assert res.entreprise_id is None  # Tolérance zéro faux positif !
    assert res.statut == "A_VERIFIER"
    assert res.est_certain is False


def test_reconciliation_aucun_match():
    e1 = SimpleNamespace(id=40, nom="PHARMACIE DE LA PAIX", numero_identification="123", rccm="456")
    db = FakeDB([e1])
    resolver = EntityResolver(db)

    res = resolver.reconcilier("TOTAL ENERGIES BURKINA")
    assert res.entreprise_id is None
    assert res.statut == "NON_ASSIGNE"
    assert res.est_certain is False
