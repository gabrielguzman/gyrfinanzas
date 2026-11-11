"""ícono y color por categoría

Revision ID: 0003
Revises: 0002
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("categoria") as b:
        b.add_column(sa.Column("icono", sa.String(length=32), nullable=False, server_default=""))
        b.add_column(sa.Column("color", sa.String(length=16), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("categoria") as b:
        b.drop_column("color")
        b.drop_column("icono")
