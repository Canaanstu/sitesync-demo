"""Project roles, change feed and daily digest preferences."""
from alembic import op
import sqlalchemy as sa
revision='007'
down_revision='006'
branch_labels=None
depends_on=None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    tables=set(inspector.get_table_names())
    if 'role' not in {c['name'] for c in inspector.get_columns('project_members')}:
        op.add_column('project_members',sa.Column('role',sa.String(),nullable=False,server_default='member'))
    user_cols={c['name'] for c in inspector.get_columns('users')}
    if 'digest' not in user_cols:
        op.add_column('users',sa.Column('digest',sa.String(),nullable=False,server_default='daily'))
    if 'digest_sent_at' not in user_cols:
        op.add_column('users',sa.Column('digest_sent_at',sa.String()))
    if 'change_events' not in tables:
        op.create_table('change_events',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('created_at',sa.String()),
            sa.Column('project_id',sa.String(),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
            sa.Column('user_id',sa.String(),sa.ForeignKey('users.id',ondelete='SET NULL')),
            sa.Column('kind',sa.String(),nullable=False),
            sa.Column('summary',sa.Text(),nullable=False),
            sa.Column('record_id',sa.String()))
        op.create_index('ix_change_events_project_id','change_events',['project_id'])
    if 'feed_reads' not in tables:
        op.create_table('feed_reads',
            sa.Column('project_id',sa.String(),sa.ForeignKey('projects.id',ondelete='CASCADE'),primary_key=True),
            sa.Column('user_id',sa.String(),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),
            sa.Column('last_read_at',sa.String(),nullable=False))

def downgrade():
    op.drop_table('feed_reads')
    op.drop_table('change_events')
    op.drop_column('users','digest_sent_at')
    op.drop_column('users','digest')
    op.drop_column('project_members','role')
