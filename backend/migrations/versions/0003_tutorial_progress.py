"""Saved DIY guide progress."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('projects',sa.Column('tutorial_steps',sa.JSON(),nullable=False,server_default='[]'))

def downgrade():
    op.drop_column('projects','tutorial_steps')
