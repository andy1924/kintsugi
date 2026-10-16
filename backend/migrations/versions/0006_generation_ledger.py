"""Generation ledger, idempotent submissions and pool-specific queue claims."""
from alembic import op
import sqlalchemy as sa
import uuid
import time
revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('repair_generations',
        sa.Column('id',sa.String(32),primary_key=True),
        sa.Column('project_id',sa.String(32),sa.ForeignKey('projects.id'),nullable=False),
        sa.Column('user_id',sa.String(32),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('version',sa.Integer(),nullable=False),
        sa.Column('source_revision',sa.Integer(),nullable=False),
        sa.Column('request_key',sa.String(36),nullable=True),
        sa.Column('requested_style',sa.String(30),nullable=True),
        sa.Column('state',sa.String(20),nullable=False),
        sa.Column('stage',sa.String(30),nullable=False),
        sa.Column('design',sa.JSON(),nullable=True),
        sa.Column('image_key',sa.String(255),nullable=True),
        sa.Column('error',sa.String(300),nullable=True),
        sa.Column('created_at',sa.Float(),nullable=False),
        sa.Column('updated_at',sa.Float(),nullable=False),
        sa.UniqueConstraint('project_id','version'),sa.UniqueConstraint('project_id','request_key'))
    op.create_index('ix_repair_generations_project_id','repair_generations',['project_id'])
    op.create_index('ix_repair_generations_state','repair_generations',['state'])
    op.create_index('ix_generation_user_created','repair_generations',['user_id','created_at'])
    op.create_index('ix_job_claim_kind','jobs',['kind','state','run_after','lease_until'])
    op.add_column('worker_heartbeats',sa.Column('queues',sa.JSON(),nullable=False,server_default='["analyze","compile","preview"]'))
    # Preserve concepts made before the history ledger was introduced.
    connection=op.get_bind()
    projects=sa.table('projects',sa.column('id'),sa.column('user_id'),sa.column('revision'),sa.column('preview_revision'),sa.column('preview',sa.JSON()))
    ledger=sa.table('repair_generations',*[sa.column(key,sa.JSON() if key=='design' else None) for key in ['id','project_id','user_id','version','source_revision','request_key','requested_style','state','stage','design','image_key','error','created_at','updated_at']])
    for project in connection.execute(sa.select(projects)).mappings():
        preview=project['preview']
        if not preview:continue
        state=preview.get('state','failed')
        if state not in ('queued','running','ready','failed','cancelled'):continue
        connection.execute(ledger.insert().values(id=uuid.uuid4().hex,project_id=project['id'],user_id=project['user_id'],version=project['preview_revision'],source_revision=preview.get('source_revision',project['revision']),request_key=None,requested_style=preview.get('requested_style'),state=state,stage='complete' if state=='ready' else 'design',design=preview.get('design'),image_key=preview.get('image_key'),error=preview.get('error'),created_at=time.time(),updated_at=time.time()))



def downgrade():
    op.drop_column('worker_heartbeats','queues')
    op.drop_index('ix_job_claim_kind',table_name='jobs')
    op.drop_table('repair_generations')
