"""Provision Firebase web configuration and release backend-only Firestore Rules."""
import json
import time
from pathlib import Path
from cloud_api import PROJECT,checked,client

ROOT=Path(__file__).resolve().parents[1]
with client() as api:
    base=f'https://firebase.googleapis.com/v1beta1/projects/{PROJECT}'
    response=api.get(base)
    if response.status_code==404:
        operation=checked(api.post(base+':addFirebase',json={}))
        for _ in range(12):
            result=checked(api.get('https://firebase.googleapis.com/v1beta1/'+operation['name']))
            if result.get('done'):
                if 'error' in result:
                    raise RuntimeError('Firebase project setup requires attention: '+result['error'].get('message',''))
                break
            time.sleep(2)
        else:
            raise RuntimeError('Firebase setup still pending; retry to inspect existing state')
    else:
        checked(response)
    auth_base=f'https://identitytoolkit.googleapis.com/admin/v2/projects/{PROJECT}/config'
    config=api.get(auth_base)
    if config.status_code==404:
        checked(api.post(f'https://identitytoolkit.googleapis.com/v2/projects/{PROJECT}/identityPlatform:initializeAuth',json={}))
        config=api.get(auth_base)
    checked(config)
    checked(api.patch(auth_base,params={'updateMask':'signIn.email.enabled,signIn.email.passwordRequired'},
                      json={'signIn':{'email':{'enabled':True,'passwordRequired':True}}}))
    apps=checked(api.get(base+'/webApps')).get('apps',[])
    app=next((a for a in apps if a.get('displayName')=='ChartBridge'),None)
    if app is None:
        operation=checked(api.post(base+'/webApps',json={'displayName':'ChartBridge'}))
        for _ in range(12):
            result=checked(api.get('https://firebase.googleapis.com/v1beta1/'+operation['name']))
            if result.get('done'):
                if 'error' in result:
                    raise RuntimeError('Firebase web app setup failed')
                app=result['response']
                break
            time.sleep(2)
        else:
            raise RuntimeError('Web app setup pending; retry')
    web=checked(api.get('https://firebase.googleapis.com/v1beta1/'+app['name']+'/config'))
    # Public Firebase web identification; Gemini secret is never included.
    public={k:web[k] for k in ('apiKey','authDomain','projectId','appId')}
    target=ROOT/'.tmp/firebase-web.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(public),encoding='utf-8')
    source=(ROOT/'firestore.rules').read_text(encoding='utf-8')
    rulesbase=f'https://firebaserules.googleapis.com/v1/projects/{PROJECT}'
    ruleset=checked(api.post(rulesbase+'/rulesets',json={'source':{'files':[{'name':'firestore.rules','content':source}]}}))
    release={'name':f'projects/{PROJECT}/releases/cloud.firestore','rulesetName':ruleset['name']}
    current=api.get(rulesbase+'/releases/cloud.firestore')
    if current.status_code==404:
        checked(api.post(rulesbase+'/releases',json=release))
    else:
        checked(current)
        checked(api.patch(rulesbase+'/releases/cloud.firestore',json={'release':release,'updateMask':'rulesetName'}))
    record={'project':PROJECT,'emailPasswordEnabled':True,'webAppRegistered':True,'ruleset':ruleset['name'],'release':release['name'],'rules':'deny all direct client access'}
    (ROOT/'docs/verification/firebase-setup.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
