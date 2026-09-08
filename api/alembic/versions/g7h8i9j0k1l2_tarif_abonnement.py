"""tarif abonnement en base

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7h8i9j0k1l2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tarifs_abonnement',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('prix_annuel', sa.Numeric(12, 2), nullable=False),
        sa.Column('devise', sa.String(length=3), nullable=False, server_default='XOF'),
        sa.Column('essai_gratuit_jours', sa.Integer(), nullable=False),
    )

    # Ligne unique de seed - reprend les valeurs qui vivaient jusqu'ici dans .env
    # (ABONNEMENT_PRIX_ANNUEL/ESSAI_GRATUIT_JOURS) : toujours des PLACEHOLDER, a corriger via le
    # site d'administration (/admin) une fois le vrai tarif connu, pas en modifiant cette
    # migration a posteriori.
    op.execute(
        "INSERT INTO tarifs_abonnement (prix_annuel, devise, essai_gratuit_jours) "
        "VALUES (50000, 'XOF', 30)"
    )


def downgrade() -> None:
    op.drop_table('tarifs_abonnement')
