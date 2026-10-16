"""Private generated repair concepts and independently versioned preview jobs."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('projects',sa.Column('preview',sa.JSON(),nullable=True))
    op.add_column('projects',sa.Column('preview_revision',sa.Integer(),nullable=False,server_default='0'))

def downgrade():
    op.drop_column('projects','preview_revision')
    op.drop_column('projects','preview')
