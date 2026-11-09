"""Release deny-all client Rules independently of Firebase Auth setup."""
import json
from pathlib import Path
from cloud_api import PROJECT,checked,client

ROOT=Path(__file__).resolve().parents[1]
source={'files':[{'name':'firestore.rules','content':(ROOT/'firestore.rules').read_text(encoding='utf-8')}]}
with client() as api:
    base=f'https://firebaserules.googleapis.com/v1/projects/{PROJECT}'
    ruleset=checked(api.post(base+'/rulesets',json={'source':source}))
    release={'name':f'projects/{PROJECT}/releases/cloud.firestore','rulesetName':ruleset['name']}
    current=api.get(base+'/releases/cloud.firestore')
    if current.status_code==404:
        checked(api.post(base+'/releases',json=release))
    else:
        checked(current)
        checked(api.patch(base+'/releases/cloud.firestore',json={'release':release,'updateMask':'rulesetName'}))
    fetched=checked(api.get(base+'/releases/cloud.firestore'))
    assert fetched['rulesetName']==ruleset['name']
    record={'project':PROJECT,'ruleset':ruleset['name'],'releaseVerified':True,'policy':'deny-all direct client access'}
    (ROOT/'docs/verification/firestore-rules.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
