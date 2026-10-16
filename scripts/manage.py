"""Local operator bootstrap. An ordinary registration cannot choose this role."""
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv
root=Path(__file__).resolve().parents[1]
load_dotenv(root/'.env');sys.path.insert(0,str(root/'backend'))
from sqlalchemy import select
from kintsugi.db import transaction
from kintsugi.models import User
parser=argparse.ArgumentParser(description='Manage Kintsugi operator access')
parser.add_argument('action',choices=['grant-operator','revoke-operator'])
parser.add_argument('email')
args=parser.parse_args()
with transaction() as db:
    user=db.scalar(select(User).where(User.email==args.email.strip().lower()))
    if not user:raise SystemExit('Register this account in the app first.')
    user.role='operator' if args.action=='grant-operator' else 'customer'
print('Operator access updated. Refresh the app to load the role.')
