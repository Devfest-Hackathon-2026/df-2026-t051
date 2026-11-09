"""Hash existing approved documents without logging their contents or owners."""
import argparse
import hashlib
import json
from pathlib import Path
from cloud_api import client,checked,PROJECT

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--after',action='store_true');p.add_argument('--prefix',default='snapshots');a=p.parse_args()
if not __import__('re').fullmatch('[a-z-]+',a.prefix):raise SystemExit('Invalid record prefix')
out=ROOT/f'docs/final-audit/{a.prefix}-before.json'
hashes={};token=None
with client() as api:
    while True:
        result=checked(api.get(f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/chartbridge_snapshots',params={'pageSize':1000,**({'pageToken':token} if token else {})}))
        for doc in result.get('documents',[]):hashes[doc['name'].rsplit('/',1)[1]]=hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest()
        token=result.get('nextPageToken')
        if not token:break
if not a.after:
    with out.open('x',encoding='utf-8') as f:json.dump({'count':len(hashes),'hashes':hashes},f,indent=2)
    print(json.dumps({'baseline_approved_documents':len(hashes)}))
else:
    before=json.loads(out.read_text(encoding='utf-8'))['hashes'];changed=[key for key,value in before.items() if hashes.get(key)!=value]
    record={'old_count':len(before),'after_count':len(hashes),'old_documents_unchanged':not changed,'changed_or_missing_count':len(changed),'new_documents':len(set(hashes)-set(before))}
    with (out.parent/f'{a.prefix}-after.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
    print(json.dumps(record));assert not changed
