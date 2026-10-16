from alembic import context
from kintsugi.db import Base, engine
from kintsugi import models

def run():
    with engine.connect() as connection:
        context.configure(connection=connection,target_metadata=Base.metadata,compare_type=True)
        with context.begin_transaction():context.run_migrations()
run()
