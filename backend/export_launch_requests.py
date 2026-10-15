"""Run locally from backend to export captured requests; no public list endpoint."""
import argparse
import csv
from pathlib import Path
from sqlalchemy import select
from app.database import SessionLocal
from app.models import LaunchRequest
from app.security import decrypt_token

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',required=True,help='Private CSV destination')
args=parser.parse_args()
def safe(value):
    value=str(value or '')
    return "'"+value if value.startswith(('=','+','-','@','\t','\r')) else value
with SessionLocal() as db,Path(args.output).open('x',newline='',encoding='utf-8-sig') as stream:
    writer=csv.writer(stream);writer.writerow(['Company email','Company','Interest','Consent version','Created at'])
    for row in db.scalars(select(LaunchRequest).order_by(LaunchRequest.created_at)):
        writer.writerow([safe(decrypt_token(row.email_encrypted)),safe(decrypt_token(row.company_encrypted)),row.interest,row.consent_version,row.created_at])
print('Private CSV saved. Keep it outside public website assets.')
