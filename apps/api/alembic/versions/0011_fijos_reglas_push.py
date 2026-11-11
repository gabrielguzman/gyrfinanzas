"""Compatibilidad: fijos/reglas/push y cuentas provinieron de dos versiones 0010.

Se conserva 0010 para las identidades desplegadas. Este puente también reconoce
bases que ya aplicaron la 0010 de fijos y crea las identidades que les faltan.
"""
from alembic import op, context
import sqlalchemy as sa
from app.accounts_models import AuthBase

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if context.config.attributes.get('tenant_schema', 'public') == 'public':
        AuthBase.metadata.create_all(bind)
    if not sa.inspect(bind).has_table('gasto_fijo'):
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
    if "fijo_id" not in {c["name"] for c in sa.inspect(bind).get_columns("movimiento")}:
        with op.batch_alter_table('movimiento') as b:
            b.add_column(sa.Column('fijo_id', sa.Uuid(), nullable=True))
            b.create_foreign_key('fk_movimiento_fijo', 'gasto_fijo', ['fijo_id'], ['id'], ondelete='SET NULL')
            b.create_index('ix_movimiento_fijo_id', ['fijo_id'])
    if not sa.inspect(bind).has_table('regla_categoria'):
        op.create_table(
            'regla_categoria',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('texto', sa.String(length=80), nullable=False),
            sa.Column('categoria_id', sa.Uuid(), sa.ForeignKey('categoria.id', ondelete='CASCADE'), nullable=False),
            sa.Column('creado', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('texto'),
        )
    if not sa.inspect(bind).has_table('push_suscripcion'):
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
    if not sa.inspect(bind).has_table('aviso_enviado'):
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
