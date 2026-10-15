"""Initial normalized project database."""
from alembic import op
from app.database import Base
from app import models

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    Base.metadata.create_all(bind)


def downgrade():
    Base.metadata.drop_all(op.get_bind())
