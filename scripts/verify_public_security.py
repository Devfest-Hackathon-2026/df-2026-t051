"""Read-only audit of the intentionally public service, without IAM proxies."""
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime,timezone
from pathlib import Path
import httpx
from cloud_api import GCLOUD,PROJECT,client,checked

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/final-audit'
def cloud(*parts):return json.loads(subprocess.run([GCLOUD,*parts,'--project',PROJECT,'--format=json'],capture_output=True,text=True,encoding='utf-8',check=True).stdout)
s=cloud('run','services','describe','chartbridge','--region','asia-northeast1');iam=cloud('run','services','get-iam-policy','chartbridge','--region','asia-northeast1')
revision=s['status']['latestReadyRevisionName'];r=cloud('run','revisions','describe',revision,'--region','asia-northeast1');env={e['name']:e.get('value') for e in r['spec']['containers'][0].get('env',[])}
key=os.environ.get('GEMINI_API_KEY')
if not key:raise SystemExit('GEMINI_API_KEY needed for non-disclosing leak check')
names=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z'],capture_output=True,check=True).stdout.decode().split('\0')
files={ROOT/name for name in names if name}|set((ROOT/'frontend/dist').rglob('*'))
leaks=[p for p in files if p.is_file() and key.encode() in p.read_bytes()]
logs=cloud('logging','read','resource.type="cloud_run_revision" AND resource.labels.service_name="chartbridge"','--freshness=1h','--limit=300')
url=s['status']['url'];live=json.loads((OUT/'live-public/firebase-full-flow.json').read_text(encoding='utf-8'));snapshot=live['comparisonSnapshotId']
checks=[];remote=[]
with httpx.Client(timeout=30) as api:
    for method,path,expected in [('GET','/',200),('GET','/api/health',200),('GET','/api/config',200),('GET','/api/me',401),('GET','/api/drafts',401),('POST','/api/analyze',401),('POST','/api/drafts',401),('GET','/api/images/'+'a'*32,401),('GET','/docs',404),('GET','/.env',404)]:
        response=api.request(method,url+path);checks.append({'method':method,'path':path,'status':response.status_code});remote.append(response.content);assert response.status_code==expected
    html=api.get(url+'/');assets=re.findall(r'(?:src|href)="(/assets/[^"\s]+)"',html.text)
    for asset in assets:remote.append(api.get(url+asset).content)
    payload=api.get(url+'/api/materials/'+snapshot).json();assert set(payload)=={'id','status','approved_at','data'}
    remote.append(json.dumps(payload).encode())
    assert api.get(url+'/learn/'+snapshot).status_code==200
    assert api.get(f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/chartbridge_snapshots/{snapshot}').status_code==403
    assert api.get('https://storage.googleapis.com/chartbridge-gdgoc-2026-sources/sources/test.png').status_code==403
with client() as api:bucket=checked(api.get('https://storage.googleapis.com/storage/v1/b/chartbridge-gdgoc-2026-sources',params={'fields':'iamConfiguration'}))['iamConfiguration']
record={'timestamp':datetime.now(timezone.utc).isoformat(),'url':url,'revision':revision,'git_sha':env['RELEASE_GIT_SHA'],'image_digest':r['status']['imageDigest'],'traffic':s['status']['traffic'],'service_public_invoker_binding':any(b.get('role')=='roles/run.invoker' and 'allUsers' in b.get('members',[]) for b in iam.get('bindings',[])),'invoker_check_not_disabled':s['metadata'].get('annotations',{}).get('run.googleapis.com/invoker-iam-disabled')!='true','firebase_teacher_authentication':env['AUTH_MODE']=='firebase','public_access_flag':env['PUBLIC_ACCESS']=='true','secret_is_reference':any(e['name']=='GEMINI_API_KEY' and 'valueFrom' in e for e in r['spec']['containers'][0]['env']),'key_absent_from_tracked_untracked_build_files':not leaks,'key_absent_from_inspected_logs':key not in json.dumps(logs),'key_absent_from_public_responses_assets':not any(key.encode() in b for b in remote),'files_inspected':sum(p.is_file() for p in files),'log_entries_inspected':len(logs),'public_assets_inspected':len(assets),'gcs_public_access_prevention':bucket.get('publicAccessPrevention'),'gcs_uniform_access':bucket.get('uniformBucketLevelAccess',{}).get('enabled'),'anonymous_firestore_status':403,'anonymous_gcs_status':403,'private_teacher_api_checks':checks,'daily_analysis_limit':env['ANALYSIS_GLOBAL_DAY'],'teacher_day_limit':env['ANALYSIS_PER_TEACHER_DAY']}
record['success']=all(record[k] for k in ('service_public_invoker_binding','invoker_check_not_disabled','firebase_teacher_authentication','public_access_flag','secret_is_reference','key_absent_from_tracked_untracked_build_files','key_absent_from_inspected_logs','key_absent_from_public_responses_assets','gcs_uniform_access')) and bucket.get('publicAccessPrevention')=='enforced' and all(t.get('revisionName')==revision and t.get('percent')==100 and 'tag' not in t for t in s['status']['traffic'])
with (OUT/'public-security.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
print(json.dumps(record,indent=2));assert record['success']
