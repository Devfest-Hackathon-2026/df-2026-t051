"""Gated release of an already-tested immutable image; default is read-only.

Stage and publish are separate: no allUsers grant until the staged revision has
fresh real-cloud E2E evidence. Publication failures close IAM and restore old
traffic. Never creates resources, rotates secrets, or changes account roles.
"""
import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
import httpx
from cloud_api import GCLOUD,PROJECT

ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.tmp/final-audit';REGION='asia-northeast1'
p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','stage','publish']);p.add_argument('--approved-plan-sha256');p.add_argument('--evidence-dir');a=p.parse_args()
def cloud(*parts):
    r=subprocess.run([GCLOUD,*parts,'--project',PROJECT,'--quiet','--format=json'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if r.returncode:raise RuntimeError('Cloud operation failed: '+r.stderr[:1000])
    return json.loads(r.stdout) if r.stdout.strip() else {}
def digest(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True).encode()).hexdigest()
def policy():return cloud('run','services','get-iam-policy','chartbridge','--region',REGION)
def public(iam):return any(m in ('allUsers','allAuthenticatedUsers') for b in iam.get('bindings',[]) for m in b.get('members',[]))
def service():return cloud('run','services','describe','chartbridge','--region',REGION)
def save(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
provenance=json.loads((ROOT/'docs/final-audit/provenance.json').read_text(encoding='utf-8'))
planpath=CACHE/'public-plan.json'
if a.action=='prepare':
    iam=policy();current=service()
    if public(iam):raise SystemExit('Expected private IAM')
    plan={'project':PROJECT,'service':'chartbridge','region':REGION,'image_digest':provenance['image_digest'],'git_sha':provenance['git_sha'],'old_revision':'chartbridge-00009-z6n','tested_private_revision':'chartbridge-00010-lut','iam_before_sha256':digest(iam),'spec_before_sha256':digest(current['spec']),'new_environment_only':{'PUBLIC_ACCESS':'true'},'tag':'judge-ready','public_iam_addition':{'member':'allUsers','role':'roles/run.invoker'},'public_traffic_percent':100,'remove_tags_before_public':['judge-ready','review-adb182fc'],'runtime_secrets_accounts_resources':'Retain current values; no new IAM grants or billing settings','rollback':'Remove allUsers run.invoker first; route old_revision 100%. Keep old revisions and stored materials.'}
    save(planpath,plan);print(json.dumps({'plan':plan,'approval_sha256':digest(plan)},indent=2));raise SystemExit(0)
plan=json.loads(planpath.read_text(encoding='utf-8'))
if a.approved_plan_sha256!=digest(plan):raise SystemExit('Explicit approved plan hash required')
if public(policy()):raise SystemExit('Expected private IAM before staged publication')
if a.action=='stage':
    if digest(policy())!=plan['iam_before_sha256'] or digest(service()['spec'])!=plan['spec_before_sha256']:raise SystemExit('Service or IAM changed since approval plan')
    staged=cloud('run','services','update','chartbridge','--region',REGION,'--image',plan['image_digest'],'--update-env-vars','PUBLIC_ACCESS=true','--no-traffic','--tag',plan['tag'])
    record={'revision':staged['status']['latestReadyRevisionName'],'traffic':staged['status']['traffic'],'plan_sha256':digest(plan)}
    save(CACHE/'public-staged.json',record);print(json.dumps(record,indent=2));raise SystemExit(0)
staged=json.loads((CACHE/'public-staged.json').read_text(encoding='utf-8'))
if staged['plan_sha256']!=digest(plan):raise SystemExit('Staged revision does not match plan')
if not a.evidence_dir:raise SystemExit('Fresh staged cloud E2E directory is required')
evidence_path=Path(a.evidence_dir).resolve();evidence=json.loads((evidence_path/'firebase-full-flow.json').read_text(encoding='utf-8'))
context=json.loads((evidence_path/'deployment-context.json').read_text(encoding='utf-8'))
if context.get('revision')!=staged['revision'] or context.get('image_digest')!=plan['image_digest']:raise SystemExit('E2E is not bound to staged revision')
required={'cloud':True,'sourceImageReload':True,'unknownExcluded':True,'comparisonDifference':6,'studentAnalyzeCalls':0,'teacherAxe':0,'studentAxe':0,'revokedTokenStatus':401,'postApprovalUpdate':409,'otherOwner':404,'noTeacherClaim':403}
if any(evidence.get(k)!=v for k,v in required.items()):raise SystemExit('Fresh real E2E/security evidence incomplete')
revision=cloud('run','revisions','describe',staged['revision'],'--region',REGION)
env={v['name']:v.get('value') for v in revision['spec']['containers'][0].get('env',[])}
if revision['status']['imageDigest']!=plan['image_digest'] or env.get('AUTH_MODE')!='firebase' or env.get('PUBLIC_ACCESS')!='true' or env.get('RELEASE_GIT_SHA')!=plan['git_sha']:raise SystemExit('Staged image/authentication settings differ')
current=service()
if not any(t.get('revisionName')==plan['old_revision'] and t.get('percent')==100 for t in current['status']['traffic']):raise SystemExit('Unexpected pre-publication traffic')
url=current['status']['url'];record={'revision':staged['revision'],'image_digest':plan['image_digest'],'git_sha':plan['git_sha'],'url':url,'checks':[]}
try:
    cloud('run','services','update-traffic','chartbridge','--region',REGION,'--to-revisions',staged['revision']+'=100','--remove-tags',','.join(plan['remove_tags_before_public']))
    cloud('run','services','add-iam-policy-binding','chartbridge','--region',REGION,'--member','allUsers','--role','roles/run.invoker')
    with httpx.Client(timeout=30) as api:
        for attempt in range(6):
            if api.get(url+'/api/health').status_code==200:break
            time.sleep(5)
        checks=[('GET','/',200),('GET','/api/health',200),('GET','/api/me',401),('GET','/api/drafts',401),('POST','/api/analyze',401),('POST','/api/drafts',401),('GET','/api/images/'+'a'*32,401),('GET','/api/drafts/'+'a'*32,401),('POST','/api/drafts/'+'a'*32+'/approve',401),('GET','/docs',404),('GET','/openapi.json',404),('GET','/.env',404)]
        for method,path,status in checks:
            response=api.request(method,url+path);record['checks'].append({'method':method,'path':path,'status':response.status_code});assert response.status_code==status
        snapshot=evidence['comparisonSnapshotId'];response=api.get(url+'/api/materials/'+snapshot);assert response.status_code==200
        assert set(response.json())=={'id','status','approved_at','data'} and response.json()['status']=='approved'
        assert api.get(url+'/learn/'+snapshot).status_code==200
        assert api.put(url+'/api/materials/'+snapshot,json={}).status_code in (404,405)
        assert api.get(url+'/api/config').json()['publicAccess'] is True
    record['success']=True;save(ROOT/'docs/final-audit/public-release.json',record);print(json.dumps(record,indent=2))
except BaseException:
    record['success']=False
    try:
        if public(policy()):cloud('run','services','remove-iam-policy-binding','chartbridge','--region',REGION,'--member','allUsers','--role','roles/run.invoker')
        if public(policy()):raise RuntimeError('IAM still public; retain protected improved revision')
        # IAM policy propagation may lag behind get-iam-policy. The previous
        # image must not be exposed during that propagation window.
        with httpx.Client(timeout=15) as rollback_client:
            for attempt in range(6):
                if rollback_client.get(url+'/api/health').status_code in (401,403):break
                if attempt==5:raise RuntimeError('Anonymous access has not closed; keep improved revision')
                time.sleep(5)
        # The old revision lacks the new quotas: never restore it while public.
        cloud('run','services','update-traffic','chartbridge','--region',REGION,'--to-revisions',plan['old_revision']+'=100')
        record['rollback']='IAM closed; old revision traffic restored'
    except Exception as rollback_error:
        record['rollback']='Rollback incomplete; inspect IAM and keep improved revision until access is closed'
        record['rollback_error_type']=type(rollback_error).__name__
    save(ROOT/'docs/final-audit/public-release-failed.json',record);raise
