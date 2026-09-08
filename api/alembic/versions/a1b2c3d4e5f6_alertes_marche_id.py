"""alertes.marche_id

Revision ID: a1b2c3d4e5f6
Revises: f3aad55f1bb3
Create Date: 2026-08-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f3aad55f1bb3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('alertes', sa.Column('marche_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_alertes_marche_id', 'alertes', 'marches', ['marche_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('fk_alertes_marche_id', 'alertes', type_='foreignkey')
    op.drop_column('alertes', 'marche_id')
