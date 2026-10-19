"""Crew chat: messages, attachments and per-person read markers for each project."""
from alembic import op
import sqlalchemy as sa
revision='006'
down_revision='005'
branch_labels=None
depends_on=None

def upgrade():
    tables=set(sa.inspect(op.get_bind()).get_table_names())
    if 'chat_messages' not in tables:
        op.create_table('chat_messages',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('created_at',sa.String()),
            sa.Column('project_id',sa.String(),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
            sa.Column('user_id',sa.String(),sa.ForeignKey('users.id',ondelete='CASCADE'),nullable=False),
            sa.Column('body',sa.Text(),nullable=False),
            sa.Column('mentions',sa.JSON()),
            sa.Column('edited_at',sa.String()))
        op.create_index('ix_chat_messages_project_id','chat_messages',['project_id'])
    if 'chat_files' not in tables:
        op.create_table('chat_files',
            sa.Column('id',sa.String(36),primary_key=True),
            sa.Column('created_at',sa.String()),
            sa.Column('project_id',sa.String(),sa.ForeignKey('projects.id',ondelete='CASCADE'),nullable=False),
            sa.Column('message_id',sa.String(),sa.ForeignKey('chat_messages.id',ondelete='CASCADE'),nullable=False),
            sa.Column('filename',sa.String(),nullable=False),
            sa.Column('content_type',sa.String(),nullable=False),
            sa.Column('size',sa.Integer(),nullable=False),
            sa.Column('data',sa.LargeBinary(),nullable=False))
        op.create_index('ix_chat_files_project_id','chat_files',['project_id'])
        op.create_index('ix_chat_files_message_id','chat_files',['message_id'])
    if 'chat_reads' not in tables:
        op.create_table('chat_reads',
            sa.Column('project_id',sa.String(),sa.ForeignKey('projects.id',ondelete='CASCADE'),primary_key=True),
            sa.Column('user_id',sa.String(),sa.ForeignKey('users.id',ondelete='CASCADE'),primary_key=True),
            sa.Column('last_read_at',sa.String(),nullable=False))

def downgrade():
    op.drop_table('chat_reads')
    op.drop_table('chat_files')
    op.drop_table('chat_messages')
