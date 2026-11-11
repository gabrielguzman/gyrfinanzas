"""gastos fijos, reglas de categorías y notificaciones push

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-11 12:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gasto_fijo',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('nombre', sa.String(length=120), nullable=False),
        sa.Column('clave', sa.String(length=160), nullable=False),
        sa.Column('monto', sa.Numeric(14, 2), nullable=False, server_default='0'),
        sa.Column('dia', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('categoria_id', sa.Uuid(), sa.ForeignKey('categoria.id', ondelete='SET NULL'), nullable=True),
        sa.Column('medio_pago_id', sa.Uuid(), sa.ForeignKey('medio_pago.id', ondelete='SET NULL'), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('ultimo_periodo', sa.String(length=7), nullable=True),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('clave'),
    )
    with op.batch_alter_table('movimiento') as b:
        b.add_column(sa.Column('fijo_id', sa.Uuid(), nullable=True))
        b.create_foreign_key('fk_movimiento_fijo', 'gasto_fijo', ['fijo_id'], ['id'], ondelete='SET NULL')
        b.create_index('ix_movimiento_fijo_id', ['fijo_id'])
    op.create_table(
        'regla_categoria',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('texto', sa.String(length=80), nullable=False),
        sa.Column('categoria_id', sa.Uuid(), sa.ForeignKey('categoria.id', ondelete='CASCADE'), nullable=False),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('texto'),
    )
    op.create_table(
        'push_suscripcion',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('endpoint', sa.String(length=1000), nullable=False),
        sa.Column('p256dh', sa.String(length=200), nullable=False),
        sa.Column('auth', sa.String(length=100), nullable=False),
        sa.Column('dispositivo', sa.String(length=120), nullable=False, server_default=''),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('endpoint'),
    )
    op.create_table(
        'aviso_enviado',
        sa.Column('clave', sa.String(length=200), nullable=False),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('clave'),
    )


def downgrade() -> None:
    op.drop_table('aviso_enviado')
    op.drop_table('push_suscripcion')
    op.drop_table('regla_categoria')
    with op.batch_alter_table('movimiento') as b:
        b.drop_index('ix_movimiento_fijo_id')
        b.drop_constraint('fk_movimiento_fijo', type_='foreignkey')
        b.drop_column('fijo_id')
    op.drop_table('gasto_fijo')
