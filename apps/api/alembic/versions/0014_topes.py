"""topes de gasto por categoría

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-13 10:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table('tope_categoria'):
        return
    op.create_table(
        'tope_categoria',
        sa.Column('categoria_id', sa.Uuid(), sa.ForeignKey('categoria.id', ondelete='CASCADE'), nullable=False),
        sa.Column('monto', sa.Numeric(14, 2), nullable=False),
        sa.Column('creado', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('categoria_id'),
    )


def downgrade() -> None:
    op.drop_table('tope_categoria')
