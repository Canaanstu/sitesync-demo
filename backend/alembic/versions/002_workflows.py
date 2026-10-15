"""Schedule plans, inspections, packages, RFI drafts and reviewable outbound mail."""
from alembic import op
import sqlalchemy as sa

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade():
    # Initial installations may already include this table through the original metadata migration.
    if not sa.inspect(op.get_bind()).has_table('workflows'):
        op.create_table('workflows', sa.Column('id', sa.String(36), primary_key=True), sa.Column('created_at', sa.String()), sa.Column('project_id', sa.String(), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False), sa.Column('kind', sa.String(), nullable=False), sa.Column('key', sa.String(), nullable=False), sa.Column('status', sa.String()), sa.Column('data', sa.JSON()), sa.Column('updated_at', sa.String()), sa.UniqueConstraint('project_id', 'kind', 'key'))
        op.create_index('ix_workflows_project_id', 'workflows', ['project_id'])
        op.create_index('ix_workflows_kind', 'workflows', ['kind'])


def downgrade():
    op.drop_table('workflows')
