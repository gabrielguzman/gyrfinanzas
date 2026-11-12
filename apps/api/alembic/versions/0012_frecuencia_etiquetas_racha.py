"""gastos no mensuales, etiquetas y días sin gastos

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-12 13:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    columnas = {c['name'] for c in insp.get_columns('gasto_fijo')}
    with op.batch_alter_table('gasto_fijo') as b:
        if 'cada_meses' not in columnas:
            b.add_column(sa.Column('cada_meses', sa.Integer(), nullable=False, server_default='1'))
        if 'mes_inicio' not in columnas:
            b.add_column(sa.Column('mes_inicio', sa.Integer(), nullable=True))
    if insp.has_table('etiqueta'):
        return
    op.create_table(
        'etiqueta',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=60), nullable=False),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nombre'),
    )
    op.create_table(
        'movimiento_etiqueta',
        sa.Column('movimiento_id', sa.Uuid(), sa.ForeignKey('movimiento.id', ondelete='CASCADE'), nullable=False),
        sa.Column('etiqueta_id', sa.Uuid(), sa.ForeignKey('etiqueta.id', ondelete='CASCADE'), nullable=False),
        sa.PrimaryKeyConstraint('movimiento_id', 'etiqueta_id'),
    )
    op.create_index('ix_movimiento_etiqueta_etiqueta_id', 'movimiento_etiqueta', ['etiqueta_id'])
    op.create_table(
        'dia_sin_gastos',
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint('fecha'),
    )


def downgrade() -> None:
    op.drop_table('dia_sin_gastos')
    op.drop_index('ix_movimiento_etiqueta_etiqueta_id', 'movimiento_etiqueta')
    op.drop_table('movimiento_etiqueta')
    op.drop_table('etiqueta')
    with op.batch_alter_table('gasto_fijo') as b:
        b.drop_column('mes_inicio')
        b.drop_column('cada_meses')
