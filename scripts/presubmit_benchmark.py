"""Bounded submission audit; immutable product and append-only result files."""
import argparse
import asyncio
import hashlib
import json
import math
import os
import secrets
import shutil
import statistics
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import httpx
from google import genai
from google.genai import types
from cloud_api import PROJECT,GCLOUD,client,checked
from eval_core import Ledger,summarize,digest
import run_large_evaluation as shared

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/pre-submit-20261109';EVAL=ROOT/'evaluation/pre-submit-20261109';URL='https://chartbridge-gqe6dtznpq-an.a.run.app';ID='6e24c58117ad4a6e88d610b9b09bb47c'
EVAL.mkdir(exist_ok=True)

def save(path,obj):
    with path.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
def budget():
    path=EVAL/'usage-ledger.json'
    if not path.exists():shutil.copyfile(ROOT/'evaluation/japanese-v3/usage-ledger.json',path)
    return Ledger(path,max_generation=260,max_counts=261,max_usd='5')
def stats(rows,key):
    values=sorted(r[key] for r in rows if key in r);fail=sum(not r.get('success',r.get('status')==200) for r in rows)
    return {'samples':len(rows),'timed_samples':len(values),'mean_ms':round(statistics.mean(values),2) if values else None,'p95_ms':round(values[math.ceil(.95*len(values))-1],2) if values else None,'max_ms':round(max(values),2) if values else None,'failed':fail,'failure_rate':fail/len(rows) if rows else None}
def snapshots(after=False):
    hashes={};token=None
    with client() as api:
        while True:
            data=checked(api.get(f'https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/chartbridge_snapshots',params={'pageSize':1000,**({'pageToken':token} if token else {})}))
            for doc in data.get('documents',[]):hashes[doc['name'].rsplit('/',1)[1]]=hashlib.sha256(json.dumps(doc,sort_keys=True).encode()).hexdigest()
            token=data.get('nextPageToken')
            if not token:break
    if not after:save(OUT/'snapshots-before.json',{'hashes':hashes,'count':len(hashes)})
    else:
        old=json.loads((OUT/'snapshots-before.json').read_text(encoding='utf-8'))['hashes'];changed=[k for k,v in old.items() if hashes.get(k)!=v]
        save(OUT/'snapshots-after.json',{'old_count':len(old),'current_count':len(hashes),'old_unchanged':not changed,'changed_or_missing_count':len(changed)});assert not changed

async def http_load():
    rows=[];semaphore=asyncio.Semaphore(3)
    async with httpx.AsyncClient(timeout=30,limits=httpx.Limits(max_connections=3)) as api:
        async def one(kind,index):
            async with semaphore:
                path='/' if kind=='page' else '/api/materials/'+ID;t=time.perf_counter();row={'kind':kind,'index':index,'started_at':datetime.now(timezone.utc).isoformat(),'series':'sequential' if index<6 else 'concurrent_3'}
                try:
                    r=await api.get(URL+path);row.update(status=r.status_code,success=r.status_code==200)
                    if kind=='material' and r.status_code==200:assert [x['value'] for x in r.json()['data']['categories']]==[12,18]
                except Exception as e:row.update(success=False,error_type=type(e).__name__)
                row['elapsed_ms']=round((time.perf_counter()-t)*1000,2);rows.append(row)
        for kind in ('page','material'):
            for index in range(6):await one(kind,index)
        await asyncio.gather(*(one(kind,index) for kind in ('page','material') for index in range(6,15)))
    save(OUT/'http-load.json',{'max_concurrency':3,'request_limit':30,'actual_requests':len(rows),'rows':rows,'page':stats([r for r in rows if r['kind']=='page'],'elapsed_ms'),'material':stats([r for r in rows if r['kind']=='material'],'elapsed_ms')})
    print(json.dumps({'http_requests':len(rows),'failures':sum(not r['success'] for r in rows)}))

def browsers():
    ledger=budget();reservations=[]
    for i in range(5):reservations.append({'generation':ledger.reserve('generation',f'public-browser-audit/{i+1}'),'count':ledger.reserve('count',f'public-browser-audit/{i+1}')})
    save(OUT/'browser-api-reservations.json',{'maximum_generations':5,'maximum_counts':5,'indices':reservations,'note':'Four planned analyses plus a conservative reserve for a quota probe. Rejected probe is not claimed as a real model generation.'})
    web=json.loads((ROOT/'.tmp/firebase-web.json').read_text());created=[];users={}
    with client() as admin:
        base=f'https://identitytoolkit.googleapis.com/v1/projects/{PROJECT}'
        try:
            for role in ('teacherA','teacherB','student'):
                uid='cb-perf-'+uuid4().hex;email=uid+'@example.test';password=secrets.token_urlsafe(32)+'Aa1!'
                checked(admin.post(base+'/accounts',json={'localId':uid,'email':email,'password':password}));created.append(uid)
                if role!='student':checked(admin.post(base+'/accounts:update',json={'localId':uid,'customAttributes':json.dumps({'teacher':True})}))
                response=httpx.post('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',params={'key':web['apiKey']},json={'email':email,'password':password,'returnSecureToken':True},timeout=30)
                if response.status_code!=200:raise RuntimeError('Temporary account sign-in failed; credentials redacted')
                users[role]={'uid':uid,'email':email,'password':password,'token':response.json()['idToken']}
            env=os.environ.copy();env.update(CHARTBRIDGE_TEST_USERS=json.dumps(users),CHARTBRIDGE_LIVE_URL=URL,CHARTBRIDGE_AUDIT_DIR=str(OUT))
            r=subprocess.run(['node','node_modules/@playwright/test/cli.js','test','--config','playwright.audit.config.ts'],cwd=ROOT/'frontend',env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
            output=r.stdout+r.stderr
            for u in users.values():
                for name in ('password','token'):output=output.replace(u[name],'[REDACTED]')
            for key in (os.environ.get('GEMINI_API_KEY'),web['apiKey']):
                if key:output=output.replace(key,'[REDACTED]')
            (OUT/'browser-test-log.txt').write_text(output,encoding='utf-8');print(output)
            if (OUT/'browser-performance.json').exists():
                data=json.loads((OUT/'browser-performance.json').read_text())
                save(OUT/'browser-summary.json',{'student_page':stats(data['student'],'elapsed_ms'),'client_comparison':stats(data['comparison'],'elapsed_ms'),'selection_to_render':stats(data['analysis'],'selection_to_render_ms'),'analysis_api':stats(data['analysis'],'api_ms'),'mixed_get':stats(data['mixed'],'elapsed_ms'),'cloud_requests_observed_in_pages':data['cloudRequests'],'student_analyze_requests':data['studentAnalyzeRequests'],'errors':data['errors'],'note':'Browser automation timings include driver and rendering overhead; n=4 analysis is a small sample.'})
                for i,row in enumerate(data['analysis']):
                    if i<len(reservations):
                        for kind,index in reservations[i].items():ledger.settle(index,status='cloud_response_'+str(row.get('status','unknown'))+'_usage_unavailable')
                save(OUT/'browser-fixture-users-cleanup-plan.json',{'created_temporary_users':len(created),'private_images_created':sum(bool(row.get('image_id')) for row in data['analysis']),'existing_material_writes':0})
            if r.returncode:raise SystemExit(r.returncode)
        finally:
            for uid in created:checked(admin.post(base+'/accounts:delete',json={'localId':uid}))
            save(OUT/'temporary-users-cleanup.json',{'created':len(created),'deleted':len(created),'existing_accounts_modified':0})
            print(f'Deleted {len(created)} temporary accounts; existing accounts untouched.')

async def evaluate(which):
    from app.extraction import PROMPT
    source=ROOT/'evaluation/japanese-v3/development.json' if which=='regression' else EVAL/('new-scope-cases.json' if which=='scope' else 'new-scope-native-jpeg-cases.json')
    data=json.loads(source.read_text(encoding='utf-8'));path=EVAL/which
    if path.exists():raise SystemExit('Evaluation already exists; no overwrite')
    path.mkdir();ledger=budget();before={k:ledger.data[k] for k in ('generation_attempts','count_attempts','charged_or_reserved_usd')}
    import run_japanese_audit as frozen
    freeze=json.loads((ROOT/'evaluation/japanese-v3/freeze.json').read_text())
    if frozen.hashes()!=freeze['code']:raise SystemExit('Product/scoring freeze changed; no API requests')
    key=os.environ.get('GEMINI_API_KEY')
    if not key:raise SystemExit('Gemini key absent')
    async with genai.Client(api_key=key,http_options=types.HttpOptions(timeout=45000,retry_options=types.HttpRetryOptions(attempts=1))).aio as api:
        runner=shared.Runner(SimpleNamespace(name='presubmit-'+which,mode='candidate',interval=5.1),ledger,api)
        rows=[r for r in await asyncio.gather(*(runner.one(c,path) for c in data['cases'])) if r]
    result=summarize(rows);result.update(usage_before=before,usage_after={k:ledger.data[k] for k in before})
    save(path/'summary.json',result);save(path/'metadata.json',{'started_after_code_freeze':True,'frozen_code_hashes':frozen.hashes(),'dataset_sha256':digest(source),'model':'gemini-3.8-flash','independent_normal_accuracy':False,'purpose':'Repeated development regression' if which=='regression' else 'New source out-of-scope rejection only','planned_cases':len(data['cases']),'completed_cases':len(rows),'stopped':runner.stop});print(json.dumps(result,indent=2))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8',errors='replace');p=argparse.ArgumentParser();p.add_argument('phase',choices=['before','after','http','browser','regression','scope','scope-native-jpeg']);a=p.parse_args()
    if a.phase in ('before','after'):snapshots(a.phase=='after')
    elif a.phase=='http':asyncio.run(http_load())
    else:
        lock=ROOT/'.tmp/pre-submit-20261109/model-phase.lock'
        handle=lock.open('x')
        try:
            if a.phase=='browser':browsers()
            else:asyncio.run(evaluate(a.phase))
        finally:
            handle.close();lock.unlink()
