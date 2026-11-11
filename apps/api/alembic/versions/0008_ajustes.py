"""ajustes (plan: cobro, ingreso, ahorro)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-10 15:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'ajuste',
        sa.Column('clave', sa.String(length=60), nullable=False),
        sa.Column('valor', sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint('clave'),
    )


def downgrade() -> None:
    op.drop_table('ajuste')
