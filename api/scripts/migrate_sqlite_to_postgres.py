"""Migration ponctuelle des donnees de db.sqlite3 (app Django) vers Postgres (schema Alembic).

Preserve les PK entieres d'origine (necessaire pour que les FK deja coherentes en SQLite le
restent), puis recale les sequences Postgres sur le max(id) migre. Le mot de passe Django
(deja hache PBKDF2) est copie tel quel dans password_hash - aucune reinitialisation necessaire
(cf. api/security.py, schemes=["bcrypt", "django_pbkdf2_sha256"]).

Le champ `entreprise_id` de authentication_utilisateur (distinct de `active_entreprise_id`) n'a
pas d'equivalent dans le schema FastAPI (redondant avec active_entreprise_id, deja signale comme
ambigu dans un commentaire du modele Django d'origine) - non migre, a signaler si des donnees
significatives y etaient stockees.

Usage : python -m api.scripts.migrate_sqlite_to_postgres [chemin_vers_db.sqlite3]
"""

import sqlite3
import sys
import uuid
from pathlib import Path

from sqlalchemy import text

from api.database import engine

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[2] / "db.sqlite3"


def _rows(sqlite_conn: sqlite3.Connection, table: str) -> list[sqlite3.Row]:
    sqlite_conn.row_factory = sqlite3.Row
    return sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608 - table figee, pas d'entree utilisateur


def _bool(value) -> bool:
    """SQLite n'a pas de type booleen natif - Django y stocke bool comme 0/1 (int)."""
    return bool(value)


def _reset_sequence(pg_conn, table: str, pk_column: str = "id") -> None:
    pg_conn.execute(
        text(
            f"SELECT setval(pg_get_serial_sequence(:table, :pk), "  # noqa: S608
            f"COALESCE((SELECT MAX({pk_column}) FROM {table}), 1))"
        ),
        {"table": table, "pk": pk_column},
    )


def migrate(sqlite_path: Path) -> None:
    sqlite_conn = sqlite3.connect(str(sqlite_path))

    with engine.begin() as pg_conn:
        # 1. Domaine / SecteurActivite (aucune dependance)
        for row in _rows(sqlite_conn, "entreprise_domaine"):
            pg_conn.execute(
                text("INSERT INTO domaines (id, libelle, description) VALUES (:id, :libelle, :description)"),
                dict(row),
            )
        for row in _rows(sqlite_conn, "entreprise_secteuractivite"):
            pg_conn.execute(
                text("INSERT INTO secteurs_activite (id, nom, description) VALUES (:id, :nom, :description)"),
                dict(row),
            )

        # 2. Utilisateur (active_entreprise_id mis a NULL pour l'instant : Entreprise n'existe pas
        # encore - meme contrainte circulaire que dans le schema, cf. migration Alembic initiale).
        for row in _rows(sqlite_conn, "authentication_utilisateur"):
            data = dict(row)
            pg_conn.execute(
                text(
                    """
                    INSERT INTO utilisateurs (
                        id, email, password_hash, repnom, repprenom, telephone,
                        notifications_actives, is_active, is_staff, is_superuser,
                        is_email_verified, activation_token, activation_token_created_at,
                        active_entreprise_id, date_joined, last_login
                    ) VALUES (
                        :id, :email, :password, :repnom, :repprenom, :telephone,
                        :notifications_actives, :is_active, :is_staff, :is_superuser,
                        :is_email_verified, :activation_token, :activation_token_created_at,
                        NULL, :date_joined, :last_login
                    )
                    """
                ),
                {
                    **data,
                    "activation_token": str(uuid.UUID(hex=data["activation_token"])),
                    "notifications_actives": _bool(data["notifications_actives"]),
                    "is_active": _bool(data["is_active"]),
                    "is_staff": _bool(data["is_staff"]),
                    "is_superuser": _bool(data["is_superuser"]),
                    "is_email_verified": _bool(data["is_email_verified"]),
                },
            )

        # 3. Entreprise (owner_id -> utilisateurs, deja migres)
        for row in _rows(sqlite_conn, "entreprise_entreprise"):
            pg_conn.execute(
                text(
                    """
                    INSERT INTO entreprises (
                        id, nom, numero_identification, siret, adresse, telephone, email,
                        date_creation, description, repnom, repprenom, rccm, owner_id
                    ) VALUES (
                        :id, :nom, :numero_identification, :siret, :adresse, :telephone, :email,
                        :date_creation, :description, :repnom, :repprenom, :rccm, :owner_id
                    )
                    """
                ),
                dict(row),
            )

        # 4. Recale active_entreprise_id maintenant que les deux tables existent.
        for row in _rows(sqlite_conn, "authentication_utilisateur"):
            if row["active_entreprise_id"] is not None:
                pg_conn.execute(
                    text("UPDATE utilisateurs SET active_entreprise_id = :entreprise_id WHERE id = :id"),
                    {"entreprise_id": row["active_entreprise_id"], "id": row["id"]},
                )

        # 5. Tables de jointure Entreprise <-> Domaine/Secteur
        for row in _rows(sqlite_conn, "entreprise_entreprisedomaine"):
            pg_conn.execute(
                text(
                    "INSERT INTO entreprise_domaines (id, entreprise_id, domaine_id) "
                    "VALUES (:id, :entreprise_id, :domaine_id)"
                ),
                dict(row),
            )
        for row in _rows(sqlite_conn, "entreprise_entreprisesecteur"):
            pg_conn.execute(
                text(
                    "INSERT INTO entreprise_secteurs (id, entreprise_id, secteur_id) "
                    "VALUES (:id, :entreprise_id, :secteur_id)"
                ),
                dict(row),
            )

        # 6. Publications / TypeProcedure / PublicationDomaine
        for row in _rows(sqlite_conn, "backend_publication"):
            pg_conn.execute(
                text(
                    """
                    INSERT INTO publications (id, titre, numero, date_publication, source, source_url, type_publication)
                    VALUES (:id, :titre, :numero, :date_publication, :source, :source_url, :type_publication)
                    """
                ),
                dict(row),
            )
        for row in _rows(sqlite_conn, "backend_typeprocedure"):
            pg_conn.execute(
                text("INSERT INTO types_procedure (id, libelle, description) VALUES (:id, :libelle, :description)"),
                dict(row),
            )
        for row in _rows(sqlite_conn, "backend_publicationdomaine"):
            pg_conn.execute(
                text(
                    "INSERT INTO publication_domaines (id, publication_id, domaine_id) "
                    "VALUES (:id, :publication_id, :domaine_id)"
                ),
                dict(row),
            )

        # 7. Marche -> AppelOffre/Resultat (heritage multi-table) -> Lot
        for row in _rows(sqlite_conn, "backend_marche"):
            pg_conn.execute(
                text(
                    """
                    INSERT INTO marches (id, publication_id, type_procedure_id, ministere, region, objet, budget_min, budget_max)
                    VALUES (:id, :publication_id, :type_procedure_id, :ministere, :region, :objet, :budget_min, :budget_max)
                    """
                ),
                dict(row),
            )
        for row in _rows(sqlite_conn, "backend_appeloffre"):
            data = dict(row)
            data["marche_id"] = data.pop("marche_ptr_id")
            pg_conn.execute(
                text(
                    """
                    INSERT INTO appels_offre (
                        marche_id, "dateDepot", "referenceDossier", "lieuDepot",
                        "conditionsParticipation", "criteresSelection", cautionnement, "dureeValiditeOffres"
                    ) VALUES (
                        :marche_id, :dateDepot, :referenceDossier, :lieuDepot,
                        :conditionsParticipation, :criteresSelection, :cautionnement, :dureeValiditeOffres
                    )
                    """
                ),
                data,
            )
        for row in _rows(sqlite_conn, "resultat"):
            pg_conn.execute(
                text(
                    """
                    INSERT INTO resultats (
                        marche_id, date_attribution, entreprise_attributaire_id, montant_attribue,
                        reference_decision, nombre_offres_recues, delai_execution, motif_rejet_autres_offres
                    ) VALUES (
                        :marche_id, :date_attribution, :entreprise_attributaire_id, :montant_attribue,
                        :reference_decision, :nombre_offres_recues, :delai_execution, :motif_rejet_autres_offres
                    )
                    """
                ),
                dict(row),
            )
        for row in _rows(sqlite_conn, "lot"):
            pg_conn.execute(
                text(
                    "INSERT INTO lots (id, marche_id, numero_lot, description, montant) "
                    "VALUES (:id, :marche_id, :numero_lot, :description, :montant)"
                ),
                dict(row),
            )

        # 8. Alerte
        for row in _rows(sqlite_conn, "alerte"):
            pg_conn.execute(
                text(
                    """
                    INSERT INTO alertes (id, entreprise_id, publication_id, type_alerte, date_alerte, contenu_alerte, canal_alerte)
                    VALUES (:id, :entreprise_id, :publication_id, :type_alerte, :date_alerte, :contenu_alerte, :canal_alerte)
                    """
                ),
                dict(row),
            )

        # 9. Sequences Postgres rebasees sur le max(id) migre, sinon la prochaine insertion via
        # l'API (nextval) percuterait un ID deja pris par une ligne migree.
        for table, pk in [
            ("domaines", "id"), ("secteurs_activite", "id"), ("utilisateurs", "id"),
            ("entreprises", "id"), ("entreprise_domaines", "id"), ("entreprise_secteurs", "id"),
            ("publications", "id"), ("types_procedure", "id"), ("publication_domaines", "id"),
            ("marches", "id"), ("lots", "id"), ("alertes", "id"),
        ]:
            _reset_sequence(pg_conn, table, pk)

    sqlite_conn.close()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SQLITE_PATH
    if not path.exists():
        raise SystemExit(f"Fichier introuvable : {path}")
    migrate(path)
    print(f"Migration terminee depuis {path}")
