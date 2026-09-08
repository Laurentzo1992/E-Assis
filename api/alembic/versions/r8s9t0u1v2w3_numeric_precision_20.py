"""Ajustement precision montant_lu, montant_corrige, montant_estime vers Numeric(20, 2)

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-09-04 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'r8s9t0u1v2w3'
down_revision: Union[str, None] = 'q7r8s9t0u1v2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'soumissionnaires_resultats',
        'montant_lu',
        existing_type=sa.Numeric(precision=15, scale=2),
        type_=sa.Numeric(precision=20, scale=2),
        existing_nullable=True,
    )
    op.alter_column(
        'soumissionnaires_resultats',
        'montant_corrige',
        existing_type=sa.Numeric(precision=15, scale=2),
        type_=sa.Numeric(precision=20, scale=2),
        existing_nullable=True,
    )
    op.alter_column(
        'lots_resultats',
        'montant_estime',
        existing_type=sa.Numeric(precision=15, scale=2),
        type_=sa.Numeric(precision=20, scale=2),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'lots_resultats',
        'montant_estime',
        existing_type=sa.Numeric(precision=20, scale=2),
        type_=sa.Numeric(precision=15, scale=2),
        existing_nullable=True,
    )
    op.alter_column(
        'soumissionnaires_resultats',
        'montant_corrige',
        existing_type=sa.Numeric(precision=20, scale=2),
        type_=sa.Numeric(precision=15, scale=2),
        existing_nullable=True,
    )
    op.alter_column(
        'soumissionnaires_resultats',
        'montant_lu',
        existing_type=sa.Numeric(precision=20, scale=2),
        type_=sa.Numeric(precision=15, scale=2),
        existing_nullable=True,
    )
