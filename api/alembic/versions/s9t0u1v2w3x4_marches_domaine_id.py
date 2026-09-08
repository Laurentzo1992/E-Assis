"""Ajout de domaine_id a la table marches

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
Create Date: 2026-09-08 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 's9t0u1v2w3x4'
down_revision: Union[str, None] = 'r8s9t0u1v2w3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'marches',
        sa.Column('domaine_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_marches_domaine_id',
        'marches',
        'domaines',
        ['domaine_id'],
        ['id'],
        ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_marches_domaine_id', 'marches', type_='foreignkey')
    op.drop_column('marches', 'domaine_id')
