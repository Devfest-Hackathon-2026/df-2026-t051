"""Read-only security smoke checks. Do not print secrets or tokens."""
import argparse
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx
from cloud_api import client as admin_client, checked

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--gcloud',required=True)
parser.add_argument('--url')
parser.add_argument('--output',default='docs/final-audit/cloud-security.json')
args=parser.parse_args()
deployment=json.loads((ROOT/'docs/verification/cloud-deployment.json').read_text())
if args.url:deployment['url']=args.url


def cloud(*parts):
    result=subprocess.run([args.gcloud,*parts,'--project',deployment['project'],'--format=json'],capture_output=True,text=True,encoding='utf-8',errors='replace',check=True)
    return json.loads(result.stdout)


policy=cloud('run','services','get-iam-policy','chartbridge','--region',deployment['region'])
public=any(member in {'allUsers','allAuthenticatedUsers'} for binding in policy.get('bindings',[]) for member in binding['members'])
service=cloud('run','services','describe','chartbridge','--region',deployment['region'])
annotations=service['metadata'].get('annotations',{})
invoker_disabled=annotations.get('run.googleapis.com/invoker-iam-disabled')=='true'
container=service['spec']['template']['spec']['containers'][0]
env={item['name']:item for item in container.get('env',[])}
secret_reference='valueFrom' in env.get('GEMINI_API_KEY',{}) and 'value' not in env.get('GEMINI_API_KEY',{})
unauth=httpx.get(deployment['url']+'/api/health',timeout=30)
token=subprocess.run([args.gcloud,'auth','print-identity-token'],capture_output=True,text=True,check=True).stdout.strip()
headers={'Authorization':f'Bearer {token}'}
html=httpx.get(deployment['url']+'/',headers=headers,timeout=30)
asset_paths=re.findall(r'(?:src|href)="(/assets/[^"\s]+)"',html.text)
remote_assets=[httpx.get(deployment['url']+path,headers=headers,timeout=30).content for path in asset_paths]
public_config=httpx.get(deployment['url']+'/api/config',headers=headers,timeout=30)
# Platform identity alone does not bypass application teacher validation.
missing_app_identity=httpx.post(deployment['url']+'/api/analyze',headers=headers,files={'file':('test.png',b'bad','image/png')},timeout=30)

key=os.environ.get('GEMINI_API_KEY')
if not key:
    raise SystemExit('GEMINI_API_KEY required for non-disclosing leak checks')
tracked=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True).stdout.decode().split('\0')
files=[ROOT/p for p in tracked if p]
files+=list((ROOT/'frontend/dist').rglob('*'))
leaks=[str(p.relative_to(ROOT)) for p in files if p.is_file() and key.encode() in p.read_bytes()]
logs=cloud('logging','read','resource.type="cloud_run_revision" AND resource.labels.service_name="chartbridge"','--freshness=1h','--limit=200')
with admin_client() as api:
    bucket=checked(api.get('https://storage.googleapis.com/storage/v1/b/chartbridge-gdgoc-2026-sources',params={'fields':'iamConfiguration'}))['iamConfiguration']
log_leak=key in json.dumps(logs)
remote_leak=key.encode() in html.content or key.encode() in public_config.content or any(key.encode() in asset for asset in remote_assets)
record={'timestamp':datetime.now(timezone.utc).isoformat(),'url':deployment['url'],
        'noPublicIamBinding':not public,'invokerIamEnabled':not invoker_disabled,
        'secretManagerReference':secret_reference,'unauthenticatedStatus':unauth.status_code,
        'revisionScaling':service['spec']['template']['metadata'].get('annotations',{}),
        'missingApplicationIdentityStatus':missing_app_identity.status_code,
        'keyAbsentFromTrackedAndBuiltFiles':not leaks,'keyAbsentFromInspectedLogs':not log_leak,
        'keyAbsentFromCloudHtmlAndAssets':not remote_leak,'cloudAssetsInspected':len(remote_assets),
        'logEntriesInspected':len(logs)}
record['gcsPublicAccessPrevention']=bucket.get('publicAccessPrevention')
record['gcsUniformBucketLevelAccess']=bucket.get('uniformBucketLevelAccess',{}).get('enabled')
record['success']=all([not public,not invoker_disabled,secret_reference,unauth.status_code in {401,403},missing_app_identity.status_code==401,not leaks,not log_leak,not remote_leak,html.status_code==200,len(remote_assets)>0,record['gcsPublicAccessPrevention']=='enforced',record['gcsUniformBucketLevelAccess'] is True])
(ROOT/args.output).write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
if not record['success']:
    raise SystemExit(1)
