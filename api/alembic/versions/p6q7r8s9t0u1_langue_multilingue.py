"""support multilingue : utilisateurs.langue, entreprises.langue_alertes

Revision ID: p6q7r8s9t0u1
Revises: o5p6q7r8s9t0
Create Date: 2026-08-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'p6q7r8s9t0u1'
down_revision: Union[str, None] = 'o5p6q7r8s9t0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'utilisateurs',
        sa.Column('langue', sa.String(length=5), nullable=False, server_default='fr'),
    )
    # Nullable, sans server_default : pre-remplie applicativement a la creation de l'entreprise
    # (owner.langue), pas de valeur par defaut sensee a imposer en base pour les lignes existantes.
    op.add_column(
        'entreprises',
        sa.Column('langue_alertes', sa.String(length=5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('entreprises', 'langue_alertes')
    op.drop_column('utilisateurs', 'langue')
