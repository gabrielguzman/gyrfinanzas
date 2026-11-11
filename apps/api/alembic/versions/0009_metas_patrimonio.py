"""metas, inversiones y patrimonio

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-10 16:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MONEDA = sa.Enum('ARS', 'USD', native_enum=False, length=32)


def upgrade() -> None:
    op.create_table(
        'meta',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=80), nullable=False),
        sa.Column('emoji', sa.String(length=16), nullable=False, server_default='🎯'),
        sa.Column('objetivo', sa.Numeric(14, 2), nullable=False),
        sa.Column('moneda', MONEDA, nullable=False, server_default='ARS'),
        sa.Column('fecha_objetivo', sa.Date(), nullable=True),
        sa.Column('aporte_mensual', sa.Numeric(14, 2), nullable=True),
        sa.Column('cuenta_id', sa.Uuid(), nullable=True),
        sa.Column('archivada', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cuenta_id'], ['cuenta.id'], name='fk_meta_cuenta_id_cuenta', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'aporte_meta',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('meta_id', sa.Uuid(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('monto', sa.Numeric(14, 2), nullable=False),
        sa.Column('nota', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['meta_id'], ['meta.id'], name='fk_aporte_meta_meta_id_meta', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_aporte_meta_meta_id', 'aporte_meta', ['meta_id'])
    op.create_table(
        'inversion',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=80), nullable=False),
        sa.Column('tipo', sa.Enum('plazo_fijo', 'fci', 'cripto', 'acciones', 'bonos', 'otro', native_enum=False, length=32),
                  nullable=False, server_default='otro'),
        sa.Column('moneda', MONEDA, nullable=False, server_default='ARS'),
        sa.Column('capital', sa.Numeric(16, 2), nullable=False),
        sa.Column('tna', sa.Numeric(7, 2), nullable=True),
        sa.Column('fecha_inicio', sa.Date(), nullable=False),
        sa.Column('vence', sa.Date(), nullable=True),
        sa.Column('valor_actual', sa.Numeric(16, 2), nullable=True),
        sa.Column('actualizado', sa.Date(), nullable=True),
        sa.Column('cerrada', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('notas', sa.String(length=200), nullable=False, server_default=''),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'foto_patrimonio',
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('neto_ars', sa.Numeric(16, 2), nullable=False),
        sa.Column('neto_usd', sa.Numeric(16, 2), nullable=True),
        sa.Column('cotizacion', sa.Numeric(12, 2), nullable=True),
        sa.PrimaryKeyConstraint('fecha'),
    )


def downgrade() -> None:
    op.drop_table('foto_patrimonio')
    op.drop_table('inversion')
    op.drop_index('ix_aporte_meta_meta_id', table_name='aporte_meta')
    op.drop_table('aporte_meta')
    op.drop_table('meta')
