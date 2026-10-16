"""Google identity binding and transactional Firestore outbox."""
from alembic import op
import sqlalchemy as sa
revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('firebase_uid',sa.String(128),nullable=True))
    op.create_index('ix_users_firebase_uid','users',['firebase_uid'],unique=True)
    op.create_table('firebase_outbox',
        sa.Column('key',sa.String(200),primary_key=True),sa.Column('collection',sa.String(80),nullable=False),
        sa.Column('document_id',sa.String(128),nullable=False),sa.Column('payload',sa.JSON(),nullable=True),
        sa.Column('payload_hash',sa.String(64),nullable=False),sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('synced_version',sa.Integer(),nullable=False),sa.Column('pending',sa.Boolean(),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False),sa.Column('next_attempt',sa.Float(),nullable=False),
        sa.Column('lease_until',sa.Float(),nullable=False),sa.Column('lock_token',sa.String(32),nullable=True),
        sa.Column('last_error',sa.String(200),nullable=True),sa.Column('synced_at',sa.Float(),nullable=True))
    op.create_index('ix_firebase_outbox_pending','firebase_outbox',['pending','next_attempt','lease_until'])

def downgrade():
    op.drop_table('firebase_outbox')
    op.drop_index('ix_users_firebase_uid',table_name='users')
    op.drop_column('users','firebase_uid')
