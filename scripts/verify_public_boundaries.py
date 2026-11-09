"""Bounded public abuse/authorization probes: zero Gemini generations."""
import json
import secrets
from pathlib import Path
from uuid import uuid4
import httpx
from cloud_api import client,checked,PROJECT

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'docs/final-audit';URL='https://chartbridge-gqe6dtznpq-an.a.run.app'
web=json.loads((ROOT/'.tmp/firebase-web.json').read_text(encoding='utf-8'))
live=json.loads((OUT/'live-public/firebase-full-flow.json').read_text(encoding='utf-8'))
uid='cb-boundary-'+uuid4().hex;email=uid+'@example.test';password=secrets.token_urlsafe(32)+'Aa1!';created=False;record={'model_generations':0,'checks':[]}
with client() as admin:
    base=f'https://identitytoolkit.googleapis.com/v1/projects/{PROJECT}'
    try:
        checked(admin.post(base+'/accounts',json={'localId':uid,'email':email,'password':password}));created=True
        response=httpx.post('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',params={'key':web['apiKey']},json={'email':email,'password':password,'returnSecureToken':True},timeout=30)
        if response.status_code!=200:raise RuntimeError('Disposable sign-in failed; no credential values logged')
        headers={'Authorization':'Bearer '+response.json()['idToken']}
        with httpx.Client(timeout=30) as api:
            for method,path in [('POST','/api/drafts/'+'a'*32+'/approve'),('PUT','/api/drafts/'+'a'*32),('GET','/api/drafts'),('GET','/api/images/'+'a'*32)]:
                r=api.request(method,URL+path,headers=headers,json={'expected_version':1,'confirmed':True,'data':{}} if method!='GET' else None)
                record['checks'].append({'method':method,'path':path,'status':r.status_code});assert r.status_code==403
            for identifier in ('not-a-material','A'*32,'a'*31,'a'*33):
                r=api.get(URL+'/api/materials/'+identifier);assert r.status_code==404
            statuses=[]
            for _ in range(61):
                r=api.get(URL+'/api/materials/'+live['comparisonSnapshotId']);statuses.append(r.status_code)
                if r.status_code==429:
                    assert r.headers.get('Retry-After') and r.headers.get('X-Content-Type-Options')=='nosniff';break
                assert r.status_code==200
            record['public_read_probe']={'maximum_requests':61,'actual_requests':len(statuses),'ok_responses':statuses.count(200),'limited_responses':statuses.count(429),'retry_after_present':bool(r.headers.get('Retry-After'))}
            assert 429 in statuses,'No public rate limit observed within bounded probe; do not retry unboundedly'
        record['success']=True
    finally:
        if created:checked(admin.post(base+'/accounts:delete',json={'localId':uid}))
        record['disposable_account_deleted']=created
with (OUT/'public-boundaries.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
print(json.dumps(record,indent=2))
