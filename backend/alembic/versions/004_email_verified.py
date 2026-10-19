"""Email verification flag. Existing users are treated as verified."""
from alembic import op
import sqlalchemy as sa
revision='004'
down_revision='003'
branch_labels=None
depends_on=None

def upgrade():
    cols={c['name'] for c in sa.inspect(op.get_bind()).get_columns('users')}
    if 'email_verified' not in cols:
        op.add_column('users',sa.Column('email_verified',sa.Boolean(),nullable=False,server_default=sa.true()))

def downgrade():
    op.drop_column('users','email_verified')
