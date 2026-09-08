"""abonnement par utilisateur (pas par entreprise)

Revision ID: o5p6q7r8s9t0
Revises: n4o5p6q7r8s9
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'o5p6q7r8s9t0'
down_revision: Union[str, None] = 'n4o5p6q7r8s9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable le temps du backfill (pas de valeur par defaut sensee pour une ligne existante).
    op.add_column('abonnements', sa.Column('utilisateur_id', sa.Integer(), nullable=True))

    # Un abonnement herite l'owner_id de l'entreprise a laquelle il etait rattache - un compte
    # avec plusieurs entreprises (donc plusieurs abonnements herites de l'ancien modele) se
    # retrouve ici avec plusieurs lignes Abonnement pointant vers le meme utilisateur_id : PAS
    # consolide automatiquement ici (delibere, cf. docstring du modele) - a nettoyer manuellement
    # depuis /admin avant qu'une future migration puisse ajouter la contrainte unique.
    op.execute(
        """
        UPDATE abonnements
        SET utilisateur_id = entreprises.owner_id
        FROM entreprises
        WHERE entreprises.id = abonnements.entreprise_id
        """
    )

    op.alter_column('abonnements', 'utilisateur_id', nullable=False)
    op.create_foreign_key(
        'fk_abonnements_utilisateur_id', 'abonnements', 'utilisateurs', ['utilisateur_id'], ['id'], ondelete='CASCADE'
    )

    op.drop_constraint('abonnements_entreprise_id_key', 'abonnements', type_='unique')
    op.drop_column('abonnements', 'entreprise_id')


def downgrade() -> None:
    op.add_column('abonnements', sa.Column('entreprise_id', sa.Integer(), nullable=True))
    op.drop_constraint('fk_abonnements_utilisateur_id', 'abonnements', type_='foreignkey')
    op.drop_column('abonnements', 'utilisateur_id')
