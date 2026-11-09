"""Run real Firebase + Cloud Run E2E with disposable accounts.

Credentials/tokens stay in process memory and child environment, never files/logs.
"""
import json
import argparse
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
from cloud_api import PROJECT,checked,client

ROOT=Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding='utf-8',errors='replace')
web=json.loads((ROOT/'.tmp/firebase-web.json').read_text())
parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8086');parser.add_argument('--output-dir',default='docs/final-audit/live');args=parser.parse_args()
output_dir=ROOT/args.output_dir;output_dir.mkdir(parents=True,exist_ok=True)
if (output_dir/'firebase-full-flow.json').exists():raise SystemExit('Evidence exists; choose a new output directory')
created=[]
users={}
with client() as api:
    base=f'https://identitytoolkit.googleapis.com/v1/projects/{PROJECT}'
    try:
        for role in ('teacher','other_teacher','student'):
            uid='cb-e2e-'+uuid4().hex
            email=uid+'@example.test'
            password=secrets.token_urlsafe(32)+'Aa1!'
            checked(api.post(base+'/accounts',json={'localId':uid,'email':email,'password':password}))
            created.append(uid)
            if role!='student':
                checked(api.post(base+'/accounts:update',json={'localId':uid,'customAttributes':json.dumps({'teacher':True})}))
            response=httpx.post('https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword',params={'key':web['apiKey']},json={'email':email,'password':password,'returnSecureToken':True},timeout=30)
            if response.status_code!=200:
                raise RuntimeError(f'Real Firebase sign-in failed: HTTP {response.status_code}')
            users[role]={'uid':uid,'email':email,'password':password,'token':response.json()['idToken']}
        env=os.environ.copy()
        env['CHARTBRIDGE_TEST_USERS']=json.dumps(users)
        env['CHARTBRIDGE_LIVE_URL']=args.url
        env['CHARTBRIDGE_EVIDENCE_DIR']=str(output_dir)
        result=subprocess.run(['node','node_modules/@playwright/test/cli.js','test','--config','playwright.live.config.ts','firebase.spec.ts'],cwd=ROOT/'frontend',env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        output=result.stdout+result.stderr
        for user in users.values():
            for name in ('password','token'):
                output=output.replace(user[name],'[REDACTED]')
        print(output)
        if result.returncode:
            raise SystemExit(result.returncode)
        checked(api.post(base+'/accounts:update',json={'localId':users['teacher']['uid'],'validSince':str(int(time.time())+1)}))
        revoked=httpx.get(args.url+'/api/me',headers={'Authorization':'Bearer '+users['teacher']['token']},timeout=30)
        assert revoked.status_code==401, 'Revoked Firebase token was not rejected'
        path=output_dir/'firebase-full-flow.json'
        record=json.loads(path.read_text(encoding='utf-8'))
        record['revokedTokenStatus']=revoked.status_code
        path.write_text(json.dumps(record,indent=2),encoding='utf-8')
    finally:
        for uid in created:
            checked(api.post(base+'/accounts:delete',json={'localId':uid}))
        print(f'Deleted {len(created)} disposable Firebase test accounts.')
