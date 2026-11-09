"""Deploy an IAM-private validation service; run only after billing approval.

Reads Gemini secret from the environment, sends it via stdin, never logs its value.
"""
import argparse
import base64
import json
import os
import subprocess
from pathlib import Path

PROJECT = 'chartbridge-gdgoc-2026'
REGION = 'asia-northeast1'
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--gcloud', required=True)
parser.add_argument('--prepare-only', action='store_true')
parser.add_argument('--firebase', action='store_true')
args = parser.parse_args()


def cloud(*parts, data=None, check=True):
    result = subprocess.run([args.gcloud,*parts,'--project',PROJECT,'--quiet'],
                            input=data,capture_output=True,text=True,encoding='utf-8',errors='replace',cwd=ROOT)
    if check and result.returncode:
        # gcloud commands here never receive key values in their arguments.
        print(result.stderr)
        raise SystemExit(result.returncode)
    return result


runtime = f'chartbridge-runtime@{PROJECT}.iam.gserviceaccount.com'
builder = f'chartbridge-builder@{PROJECT}.iam.gserviceaccount.com'
for name,email in [('chartbridge-runtime',runtime),('chartbridge-builder',builder)]:
    if cloud('iam','service-accounts','describe',email,check=False).returncode:
        cloud('iam','service-accounts','create',name,'--display-name',name)
cloud('projects','add-iam-policy-binding',PROJECT,'--member',f'serviceAccount:{builder}','--role','roles/run.builder','--condition=None')

secret='chartbridge-gemini'
if cloud('secrets','describe',secret,check=False).returncode:
    cloud('secrets','create',secret,'--replication-policy','automatic')
    key=os.environ.get('GEMINI_API_KEY')
    if not key:
        raise SystemExit('GEMINI_API_KEY missing; no value was printed')
    version=json.loads(cloud('secrets','versions','add',secret,'--data-file=-','--format=json',data=key).stdout)['name'].rsplit('/',1)[1]
else:
    versions=json.loads(cloud('secrets','versions','list',secret,'--filter=state:ENABLED','--format=json').stdout)
    if not versions:
        raise SystemExit('Existing secret has no enabled version; explicit secret setup required')
    version=max((v['name'].rsplit('/',1)[1] for v in versions),key=int)
cloud('secrets','add-iam-policy-binding',secret,'--member',f'serviceAccount:{runtime}','--role','roles/secretmanager.secretAccessor','--condition=None')

identity=cloud('auth','print-identity-token').stdout.strip()
claims=json.loads(base64.urlsafe_b64decode(identity.split('.')[1]+'=='))
email=claims['email']
env={'APP_ENV':'production','LOCAL_DEMO':'false','AUTH_MODE':'google_iam','FIRESTORE_PROJECT_ID':PROJECT,
     'GEMINI_MODEL':'gemini-3.8-flash','IAM_TOKEN_AUDIENCE':claims['aud'],'IAM_TEACHER_EMAILS':email,
     'IMAGE_BUCKET':PROJECT+'-sources','SERVICE_BASE_URL':'https://chartbridge-gqe6dtznpq-an.a.run.app'}
if args.firebase:
    web=json.loads((ROOT/'.tmp/firebase-web.json').read_text(encoding='utf-8'))
    env.update(AUTH_MODE='firebase',FIREBASE_PROJECT_ID=PROJECT,FIREBASE_WEB_API_KEY=web['apiKey'],FIREBASE_AUTH_DOMAIN=web['authDomain'])
temp=ROOT/'.tmp/cloud-run-env.yaml'
temp.parent.mkdir(exist_ok=True)
temp.write_text('\n'.join(f'{key}: {json.dumps(value)}' for key,value in env.items())+'\n',encoding='utf-8')
print('Dedicated runtime/build service accounts and pinned secret version ready.',flush=True)
if args.prepare_only:
    raise SystemExit(0)

print('Starting source build and private deployment...',flush=True)
result=cloud('run','deploy','chartbridge','--source','.', '--region',REGION,
             '--service-account',runtime,'--build-service-account',f'projects/{PROJECT}/serviceAccounts/{builder}',
             '--no-allow-unauthenticated','--min-instances','0','--max-instances','1','--concurrency','2',
             '--memory','512Mi','--cpu','1','--timeout','60','--env-vars-file',str(temp),
             '--set-secrets',f'GEMINI_API_KEY={secret}:{version}','--format=json',check=False)
if result.returncode:
    print(result.stderr)
    raise SystemExit(result.returncode)
service=json.loads(result.stdout)
record={'project':PROJECT,'region':REGION,'service':'chartbridge','url':service['status']['url'],
        'readyRevision':service['status'].get('latestReadyRevisionName'),'secretVersion':version,
        'runtimeServiceAccount':runtime,'buildServiceAccount':builder,'public':False}
(ROOT/'docs/verification/cloud-deployment.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps(record,indent=2))
