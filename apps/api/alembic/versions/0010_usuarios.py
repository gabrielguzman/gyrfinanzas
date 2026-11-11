"""Identidades, invitaciones y sesiones revocables."""
from alembic import op, context
from app.accounts_models import AuthBase

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade():
    if context.config.attributes.get('tenant_schema', 'public') == 'public':
        AuthBase.metadata.create_all(op.get_bind())


def downgrade():
    if context.config.attributes.get('tenant_schema', 'public') == 'public':
        AuthBase.metadata.drop_all(op.get_bind())
