import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine,inspect,text

def test_migrations_preserve_legacy_pieces_and_remove_incentives(tmp_path):
    root=Path(__file__).resolve().parents[2]
    url='sqlite:///'+str(tmp_path/'migration.db')
    env={**os.environ,'DATABASE_URL':url}
    command=[sys.executable,'-m','alembic','-c','backend/alembic.ini','upgrade']
    result=subprocess.run(command+['0001'],cwd=root,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    engine=create_engine(url)
    with engine.begin() as db:
        db.execute(text("INSERT INTO users (id,email,name,password,created_at) VALUES ('legacy','legacy@example.com','Legacy','hash',0)"))
        db.execute(text("INSERT INTO projects (id,user_id,title,status,image_key,image_hash,image_phash,width,height,revision,settings,created_at,updated_at) VALUES ('piece','legacy','Old jacket','uploaded','test.jpg','sha','phash',320,260,0,'{}',0,0)"))
    result=subprocess.run(command+['head'],cwd=root,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    schema=inspect(engine)
    assert 'credits' not in schema.get_table_names() and 'unlocks' not in schema.get_table_names()
    assert 'makers' in schema.get_table_names() and 'repair_services' in schema.get_table_names()
    with engine.connect() as db:
        assert db.execute(text("SELECT category FROM projects WHERE id='piece'")).scalar_one()=='textile'
        assert db.execute(text("SELECT role FROM users WHERE id='legacy'")).scalar_one()=='customer'
    result=subprocess.run([sys.executable,'-m','alembic','-c','backend/alembic.ini','check'],cwd=root,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
