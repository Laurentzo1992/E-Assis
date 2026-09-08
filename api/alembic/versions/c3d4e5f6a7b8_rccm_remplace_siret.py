"""rccm remplace siret

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Elargit la colonne AVANT le backfill : certains siret existants (>15 caracteres) depasseraient
    # sinon la taille actuelle de rccm et feraient echouer l'UPDATE.
    op.alter_column('entreprises', 'rccm', existing_type=sa.String(length=15), type_=sa.String(length=30))

    # Recupere les entreprises existantes sans rccm renseigne avant de retirer siret, pour ne pas
    # perdre leur seul identifiant connu (le SIRET, francais, n'a plus lieu d'etre pour des
    # entreprises du Burkina Faso, mais on ne jette pas la donnee deja saisie).
    op.execute("UPDATE entreprises SET rccm = siret WHERE rccm IS NULL")

    op.alter_column('entreprises', 'rccm', existing_type=sa.String(length=30), nullable=False)
    op.create_unique_constraint('uq_entreprises_rccm', 'entreprises', ['rccm'])

    op.drop_constraint('entreprises_siret_key', 'entreprises', type_='unique')
    op.drop_column('entreprises', 'siret')


def downgrade() -> None:
    op.add_column('entreprises', sa.Column('siret', sa.String(length=20), nullable=True))
    op.execute("UPDATE entreprises SET siret = rccm")
    op.alter_column('entreprises', 'siret', existing_type=sa.String(length=20), nullable=False)
    op.create_unique_constraint('entreprises_siret_key', 'entreprises', ['siret'])

    op.drop_constraint('uq_entreprises_rccm', 'entreprises', type_='unique')
    op.alter_column('entreprises', 'rccm', existing_type=sa.String(length=30), nullable=True)
    op.alter_column('entreprises', 'rccm', existing_type=sa.String(length=30), type_=sa.String(length=15))
