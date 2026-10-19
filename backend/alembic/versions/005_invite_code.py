"""Company invite code, so teammates can join an existing organization at sign-up."""
from alembic import op
import sqlalchemy as sa
revision='005'
down_revision='004'
branch_labels=None
depends_on=None

def upgrade():
    cols={c['name'] for c in sa.inspect(op.get_bind()).get_columns('organizations')}
    if 'invite_code' not in cols:
        op.add_column('organizations',sa.Column('invite_code',sa.String(),nullable=True))
        op.create_index('ix_organizations_invite_code','organizations',['invite_code'],unique=True)

def downgrade():
    op.drop_index('ix_organizations_invite_code',table_name='organizations')
    op.drop_column('organizations','invite_code')
