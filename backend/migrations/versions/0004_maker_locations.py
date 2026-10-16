"""Opt-in approximate public maker map locations."""
from alembic import op
import sqlalchemy as sa
revision='0004'
down_revision='0003'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('makers',sa.Column('latitude',sa.Float(),nullable=True))
    op.add_column('makers',sa.Column('longitude',sa.Float(),nullable=True))
    op.create_index('ix_makers_public_location','makers',['status','accepting_work','consent_to_list','latitude','longitude'])

def downgrade():
    op.drop_index('ix_makers_public_location',table_name='makers')
    op.drop_column('makers','longitude')
    op.drop_column('makers','latitude')
