"""supprime publication_domaines

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Table jamais alimentee par le pipeline d'extraction automatique (un bulletin quotidien
    # couvre systematiquement de nombreux domaines a la fois, la relevance par domaine se fait au
    # niveau du Marche via recherche vectorielle, pas au niveau de la Publication) - supprimee avec
    # l'ecran "Veille & Documents" qui etait son seul consommateur.
    op.drop_table('publication_domaines')


def downgrade() -> None:
    op.create_table(
        'publication_domaines',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('publication_id', sa.Integer(), sa.ForeignKey('publications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('domaine_id', sa.Integer(), sa.ForeignKey('domaines.id', ondelete='CASCADE'), nullable=False),
        sa.UniqueConstraint('publication_id', 'domaine_id'),
    )
