"""Validate deny-all policy with teacher/student/anonymous Rules contexts."""
import json
import argparse
from pathlib import Path
from cloud_api import PROJECT,checked,client

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--output',default='docs/final-audit/firestore-rules-tests.json');args=parser.parse_args()
with client() as api:
    base=f'https://firebaserules.googleapis.com/v1/projects/{PROJECT}'
    release=checked(api.get(base+'/releases/cloud.firestore'))
    ruleset=checked(api.get('https://firebaserules.googleapis.com/v1/'+release['rulesetName']))
    tests=[]
    for auth in (None,{'uid':'test-student','token':{}},{'uid':'test-teacher','token':{'teacher':True}}):
        for collection in ('chartbridge_drafts','chartbridge_snapshots','chartbridge_images','chartbridge_usage'):
            for method in ('get','list','create','update','delete'):
                tests.append({'expectation':'DENY','request':{'auth':auth,'method':method,'path':f'/databases/(default)/documents/{collection}/test-document','time':'2026-11-05T00:00:00Z'},'resource':{'data':{'owner':'test-teacher','status':'approved'}}})
    result=checked(api.post(base+':test',json={'source':ruleset['source'],'testSuite':{'testCases':tests}}))
    results=result.get('testResults',[])
    record={'release':release['name'],'ruleset':release['rulesetName'],'testCount':len(tests),'states':[r.get('state') for r in results],'issues':result.get('issues',[])}
    record['success']=len(results)==len(tests) and all(r.get('state')=='SUCCESS' for r in results)
    (ROOT/args.output).write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))
    assert record['success']
