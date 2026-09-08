"""Tests de _upsert_avis (api/scripts/extract_bulletin.py) contre la vraie base Postgres -
verifie que chaque type_avis cree bien la ligne d'extension attendue (Resultat/AppelOffre) en
plus du Marche de base. Regression pour un bug trouve en verifiant le bulletin 4462 en reel :
aucune ligne AppelOffre n'etait jamais creee, quel que soit le type_avis retenu."""

from datetime import date, datetime, timezone

from api.database import SessionLocal
from api.models.backend import AppelOffre, Marche, Publication, Resultat
from api.scripts.extract_bulletin import _upsert_avis
from llm_service.extraction_prompts import AvisExtrait


def _publication_de_test() -> Publication:
    db = SessionLocal()
    try:
        publication = Publication(
            titre="Bulletin test",
            numero=f"upsert-test-{datetime.now(timezone.utc).timestamp()}",
            date_publication=date(2026, 1, 1),
            source="DGCMEF",
        )
        db.add(publication)
        db.commit()
        db.refresh(publication)
        return publication
    finally:
        db.close()


def test_upsert_avis_appel_offre_cree_la_ligne_extension():
    publication = _publication_de_test()
    avis = AvisExtrait(type_avis="appel_offre", organisme="Ministere Test", objet="Fourniture de test appel_offre")

    db = SessionLocal()
    try:
        marche = _upsert_avis(db, publication, avis, page_number=1)

        assert db.query(Marche).filter(Marche.id == marche.id).count() == 1
        assert db.query(AppelOffre).filter(AppelOffre.marche_id == marche.id).count() == 1
        assert db.query(Resultat).filter(Resultat.marche_id == marche.id).count() == 0
    finally:
        db.close()


def test_upsert_avis_resultat_cree_la_ligne_extension():
    publication = _publication_de_test()
    avis = AvisExtrait(type_avis="resultat", organisme="Ministere Test", objet="Fourniture de test resultat")

    db = SessionLocal()
    try:
        marche = _upsert_avis(db, publication, avis, page_number=1)

        assert db.query(Resultat).filter(Resultat.marche_id == marche.id).count() == 1
        assert db.query(AppelOffre).filter(AppelOffre.marche_id == marche.id).count() == 0
    finally:
        db.close()


def test_upsert_avis_resultat_conserve_le_nom_brut_sans_correspondance():
    # Regression : entreprise_attributaire_nom (texte brut extrait par le LLM) doit rester
    # renseigne meme quand aucune Entreprise inscrite ne correspond - c'est le cas de la grande
    # majorite des resultats reels (les attributaires ne sont presque jamais des clients kbbot).
    # Avant ce correctif, le nom extrait etait silencieusement perdu des qu'il ne matchait rien.
    publication = _publication_de_test()
    avis = AvisExtrait(
        type_avis="resultat",
        organisme="Ministere Test",
        objet="Fourniture de test nom conserve",
        entreprise_attributaire_nom="Entreprise Totalement Inconnue SARL",
    )

    db = SessionLocal()
    try:
        marche = _upsert_avis(db, publication, avis, page_number=1)
        resultat = db.query(Resultat).filter(Resultat.marche_id == marche.id).one()

        assert resultat.entreprise_attributaire_nom == "Entreprise Totalement Inconnue SARL"
        assert resultat.entreprise_attributaire_id is None
    finally:
        db.close()


def test_upsert_avis_appel_offre_idempotent():
    publication = _publication_de_test()
    avis = AvisExtrait(type_avis="appel_offre", organisme="Ministere Test", objet="Fourniture de test idempotent")

    db = SessionLocal()
    try:
        marche_1 = _upsert_avis(db, publication, avis, page_number=1)
        marche_2 = _upsert_avis(db, publication, avis, page_number=1)

        assert marche_1.id == marche_2.id
        assert db.query(AppelOffre).filter(AppelOffre.marche_id == marche_1.id).count() == 1
    finally:
        db.close()
