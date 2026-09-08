"""nom brut de l'attributaire sur resultat

Revision ID: m3n4o5p6q7r8
Revises: g7h8i9j0k1l2
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'm3n4o5p6q7r8'
down_revision: Union[str, None] = 'g7h8i9j0k1l2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('resultats', sa.Column('entreprise_attributaire_nom', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('resultats', 'entreprise_attributaire_nom')
