"""Pipeline d'attribution : ResultatAttribution, LotResultat, SoumissionnaireResultat, AlerteResultat

Revision ID: q7r8s9t0u1v2
Revises: p6q7r8s9t0u1
Create Date: 2026-09-03 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'q7r8s9t0u1v2'
down_revision: Union[str, None] = 'p6q7r8s9t0u1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Table resultats_attribution
    op.create_table(
        'resultats_attribution',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('publication_id', sa.Integer(), nullable=True),
        sa.Column('marche_id', sa.Integer(), nullable=True),
        sa.Column('bulletin_numero', sa.String(length=100), nullable=True),
        sa.Column('page_source', sa.Integer(), nullable=True),
        sa.Column('autorite_contractante', sa.String(length=255), nullable=False),
        sa.Column('reference_dossier', sa.String(length=255), nullable=True),
        sa.Column('objet', sa.Text(), nullable=False),
        sa.Column('date_attribution', sa.Date(), nullable=True),
        sa.Column('date_extraction', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('statut_deliberation', sa.String(length=50), server_default='ATTRIBUE', nullable=False),
        sa.Column('raw_source_snippet', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['marche_id'], ['marches.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['publication_id'], ['publications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_resultats_attribution_publication_id', 'resultats_attribution', ['publication_id'])
    op.create_index('ix_resultats_attribution_marche_id', 'resultats_attribution', ['marche_id'])
    op.create_index('ix_resultats_attribution_bulletin_numero', 'resultats_attribution', ['bulletin_numero'])
    op.create_index('ix_resultats_attribution_autorite_contractante', 'resultats_attribution', ['autorite_contractante'])
    op.create_index('ix_resultats_attribution_reference_dossier', 'resultats_attribution', ['reference_dossier'])
    op.create_index('ix_res_attrib_dossier_bulletin', 'resultats_attribution', ['bulletin_numero', 'reference_dossier'])

    # 2. Table lots_resultats
    op.create_table(
        'lots_resultats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resultat_attribution_id', sa.Integer(), nullable=False),
        sa.Column('numero_lot', sa.String(length=50), server_default='1', nullable=False),
        sa.Column('intitule_lot', sa.Text(), nullable=True),
        sa.Column('montant_estime', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('statut_lot', sa.String(length=50), server_default='ATTRIBUE', nullable=False),
        sa.ForeignKeyConstraint(['resultat_attribution_id'], ['resultats_attribution.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resultat_attribution_id', 'numero_lot', name='uq_lot_par_resultat'),
    )
    op.create_index('ix_lots_resultats_resultat_attribution_id', 'lots_resultats', ['resultat_attribution_id'])

    # 3. Table soumissionnaires_resultats
    op.create_table(
        'soumissionnaires_resultats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lot_resultat_id', sa.Integer(), nullable=False),
        sa.Column('entreprise_id', sa.Integer(), nullable=True),
        sa.Column('nom_entreprise_brut', sa.String(length=255), nullable=False),
        sa.Column('nom_entreprise_normalise', sa.String(length=255), nullable=True),
        sa.Column('ifu_extrait', sa.String(length=30), nullable=True),
        sa.Column('rccm_extrait', sa.String(length=50), nullable=True),
        sa.Column('statut', sa.String(length=30), nullable=False),
        sa.Column('est_attributaire', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('rang_classement', sa.Integer(), nullable=True),
        sa.Column('montant_lu', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('montant_corrige', sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column('delai_execution', sa.String(length=100), nullable=True),
        sa.Column('motif_rejet', sa.Text(), nullable=True),
        sa.Column('score_matching', sa.Float(), nullable=True),
        sa.Column('methode_matching', sa.String(length=50), nullable=True),
        sa.Column('statut_reconciliation', sa.String(length=30), server_default='NON_ASSIGNE', nullable=False),
        sa.ForeignKeyConstraint(['entreprise_id'], ['entreprises.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lot_resultat_id'], ['lots_resultats.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_soumissionnaires_resultats_lot_resultat_id', 'soumissionnaires_resultats', ['lot_resultat_id'])
    op.create_index('ix_soumissionnaires_resultats_entreprise_id', 'soumissionnaires_resultats', ['entreprise_id'])
    op.create_index('ix_soumissionnaires_resultats_nom_entreprise_brut', 'soumissionnaires_resultats', ['nom_entreprise_brut'])
    op.create_index('ix_soumissionnaires_resultats_nom_entreprise_normalise', 'soumissionnaires_resultats', ['nom_entreprise_normalise'])
    op.create_index('ix_soumissionnaires_resultats_ifu_extrait', 'soumissionnaires_resultats', ['ifu_extrait'])
    op.create_index('ix_soumissionnaires_resultats_statut', 'soumissionnaires_resultats', ['statut'])

    # 4. Table alertes_resultats
    op.create_table(
        'alertes_resultats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entreprise_id', sa.Integer(), nullable=False),
        sa.Column('soumissionnaire_resultat_id', sa.Integer(), nullable=False),
        sa.Column('canal_alerte', sa.String(length=30), nullable=False),
        sa.Column('type_notification', sa.String(length=50), nullable=False),
        sa.Column('contenu_alerte', sa.Text(), nullable=False),
        sa.Column('date_envoi', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('statut_envoi', sa.String(length=30), server_default='SENT', nullable=False),
        sa.Column('message_hash', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['entreprise_id'], ['entreprises.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['soumissionnaire_resultat_id'], ['soumissionnaires_resultats.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'entreprise_id',
            'soumissionnaire_resultat_id',
            'type_notification',
            name='uq_alerte_resultat_par_soumissionnaire',
        ),
    )
    op.create_index('ix_alertes_resultats_entreprise_id', 'alertes_resultats', ['entreprise_id'])
    op.create_index('ix_alertes_resultats_soumissionnaire_resultat_id', 'alertes_resultats', ['soumissionnaire_resultat_id'])
    op.create_index('ix_alertes_resultats_message_hash', 'alertes_resultats', ['message_hash'])


def downgrade() -> None:
    op.drop_table('alertes_resultats')
    op.drop_table('soumissionnaires_resultats')
    op.drop_table('lots_resultats')
    op.drop_table('resultats_attribution')
