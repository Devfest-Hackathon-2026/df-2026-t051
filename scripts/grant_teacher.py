"""Explicit administrator-only teacher claim assignment. Never handles passwords."""
import argparse
import json
from cloud_api import PROJECT,checked,client

parser=argparse.ArgumentParser()
parser.add_argument('--email',required=True)
args=parser.parse_args()
with client() as api:
    base=f'https://identitytoolkit.googleapis.com/v1/projects/{PROJECT}'
    records=checked(api.post(base+'/accounts:lookup',json={'email':[args.email]})).get('users',[])
    if len(records)!=1:
        raise SystemExit('No unique Firebase account found; create the intended account first.')
    user=records[0]
    claims=json.loads(user.get('customAttributes','{}'))
    claims['teacher']=True
    checked(api.post(base+'/accounts:update',json={'localId':user['localId'],'customAttributes':json.dumps(claims)}))
    print('Teacher claim granted to the explicitly selected Firebase account. Sign in again to refresh the token.')
