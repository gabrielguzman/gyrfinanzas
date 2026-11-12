"""movimientos que ya estaban reflejados en el saldo de la cuenta

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-12 13:45:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columnas = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('movimiento')}
    if 'fuera_de_saldo' not in columnas:
        with op.batch_alter_table('movimiento') as b:
            b.add_column(sa.Column('fuera_de_saldo', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('movimiento') as b:
        b.drop_column('fuera_de_saldo')
