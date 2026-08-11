"""abonnement et paiement

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'abonnements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entreprise_id', sa.Integer(), sa.ForeignKey('entreprises.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('statut', sa.String(length=20), nullable=False, server_default='essai'),
        sa.Column('date_debut_essai', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_fin_essai', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_fin_abonnement', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        'paiements',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('abonnement_id', sa.Integer(), sa.ForeignKey('abonnements.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reference', sa.String(length=100), nullable=False, unique=True),
        sa.Column('reference_fournisseur', sa.String(length=150), nullable=True),
        sa.Column('fournisseur', sa.String(length=30), nullable=False),
        sa.Column('montant', sa.Numeric(12, 2), nullable=False),
        sa.Column('devise', sa.String(length=3), nullable=False, server_default='XOF'),
        sa.Column('statut', sa.String(length=20), nullable=False, server_default='en_attente'),
        sa.Column('date_creation', sa.DateTime(timezone=True), nullable=False),
        sa.Column('date_confirmation', sa.DateTime(timezone=True), nullable=True),
    )

    # Retrofit : les entreprises deja inscrites avant l'existence de l'abonnement demarrent un
    # essai gratuit standard a partir de maintenant, comme n'importe quelle nouvelle inscription -
    # aucune ne doit se retrouver bloquee du jour au lendemain sans avoir eu droit a un essai.
    op.execute(
        """
        INSERT INTO abonnements (entreprise_id, statut, date_debut_essai, date_fin_essai)
        SELECT id, 'essai', now(), now() + interval '30 days'
        FROM entreprises
        """
    )


def downgrade() -> None:
    op.drop_table('paiements')
    op.drop_table('abonnements')
