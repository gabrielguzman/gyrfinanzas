"""garantías

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-10 15:10:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'garantia',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('producto', sa.String(length=120), nullable=False),
        sa.Column('comercio', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('serie', sa.String(length=80), nullable=False, server_default=''),
        sa.Column('fecha_compra', sa.Date(), nullable=False),
        sa.Column('meses', sa.Integer(), nullable=False, server_default='12'),
        sa.Column('vence', sa.Date(), nullable=False),
        sa.Column('en_reparacion_desde', sa.Date(), nullable=True),
        sa.Column('dias_reparacion', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('notas', sa.String(length=400), nullable=False, server_default=''),
        sa.Column('movimiento_id', sa.Uuid(), nullable=True),
        sa.Column('archivo_id', sa.Uuid(), nullable=True),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['movimiento_id'], ['movimiento.id'], name='fk_garantia_movimiento_id_movimiento', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['archivo_id'], ['archivo.id'], name='fk_garantia_archivo_id_archivo', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_garantia_vence', 'garantia', ['vence'])
    op.create_index('ix_garantia_movimiento_id', 'garantia', ['movimiento_id'])


def downgrade() -> None:
    op.drop_index('ix_garantia_movimiento_id', table_name='garantia')
    op.drop_index('ix_garantia_vence', table_name='garantia')
    op.drop_table('garantia')
