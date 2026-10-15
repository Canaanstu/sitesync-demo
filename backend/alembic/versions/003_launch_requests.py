"""Private launch interest storage."""
from alembic import op
import sqlalchemy as sa
revision='003'
down_revision='002'
branch_labels=None
depends_on=None

def upgrade():
    if not sa.inspect(op.get_bind()).has_table('launch_requests'):
        op.create_table('launch_requests',sa.Column('id',sa.String(36),primary_key=True),sa.Column('created_at',sa.String()),sa.Column('email_hash',sa.String(64),nullable=False),sa.Column('email_encrypted',sa.Text(),nullable=False),sa.Column('company_encrypted',sa.Text(),nullable=False),sa.Column('interest',sa.String(),nullable=False),sa.Column('consent_version',sa.String(),nullable=False),sa.UniqueConstraint('email_hash','interest'))

def downgrade():
    op.drop_table('launch_requests')
