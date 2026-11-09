"""Prepare a reviewable private, zero-traffic source deployment. No IAM writes.

Default is read-only. --execute requires the user-approved plan hash and an
unchanged Git tree, current revision, traffic, IAM and settings.
"""
import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path
from cloud_api import GCLOUD,PROJECT

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.tmp/final-audit'
parser=argparse.ArgumentParser()
parser.add_argument('--execute',action='store_true')
parser.add_argument('--approved-plan-sha256')
args=parser.parse_args()

def command(*parts):
    result=subprocess.run([GCLOUD,*parts,'--project',PROJECT,'--quiet'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace')
    if result.returncode:raise RuntimeError('Cloud command failed: '+result.stderr[:1200])
    return result.stdout

def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()

sha=(json.loads((OUT/'candidate-plan.json').read_text(encoding='utf-8'))['git_sha'] if args.execute else subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip())
dirty=subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
if dirty and not args.execute:raise SystemExit('Commit reviewed changes before preparing a deployment')
service=json.loads(command('run','services','describe','chartbridge','--region','asia-northeast1','--format=json'))
iam=json.loads(command('run','services','get-iam-policy','chartbridge','--region','asia-northeast1','--format=json'))
if any(member in ('allUsers','allAuthenticatedUsers') for binding in iam.get('bindings',[]) for member in binding.get('members',[])):raise SystemExit('Expected IAM-private service')
template=service['spec']['template'];container=template['spec']['containers'][0]
env={v['name']:v['value'] for v in container.get('env',[]) if 'value' in v}
if env.get('AUTH_MODE')!='firebase' or env.get('APP_ENV')!='production':raise SystemExit('Unexpected authentication/environment')
secrets={v['name']:v['valueFrom']['secretKeyRef'] for v in container.get('env',[]) if 'valueFrom' in v}
env.update(PUBLIC_ACCESS='false',RELEASE_GIT_SHA=sha,ANALYSIS_PER_MINUTE='2',ANALYSIS_PER_TEACHER_DAY='10',ANALYSIS_GLOBAL_DAY='30',PUBLIC_READ_PER_MINUTE='60',API_REQUESTS_PER_MINUTE='240')
tag='review-'+sha[:8]
plan={'git_sha':sha,'previous_revision':service['status']['latestReadyRevisionName'],'previous_traffic':service['status'].get('traffic'),'settings_sha256':digest(service['spec']),'iam_sha256':digest(iam),'target':'chartbridge','region':'asia-northeast1','tag':tag,'traffic_to_candidate':0,'public':False,'environment_changes':{key:env[key] for key in ('PUBLIC_ACCESS','RELEASE_GIT_SHA','ANALYSIS_PER_MINUTE','ANALYSIS_PER_TEACHER_DAY','ANALYSIS_GLOBAL_DAY','PUBLIC_READ_PER_MINUTE','API_REQUESTS_PER_MINUTE')},'retained_secret_references':secrets,'runtime_service_account':template['spec']['serviceAccountName'],'iam_changes':[],'rollback':'Route 100% to previous_revision; remove candidate tag. No public IAM binding is added.'}
OUT.mkdir(parents=True,exist_ok=True)
if not args.execute:
    (OUT/'candidate-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
    (OUT/'service-before.json').write_text(json.dumps(service,indent=2),encoding='utf-8')
    print(json.dumps({'plan':plan,'approval_sha256':digest(plan)},indent=2));raise SystemExit(0)
saved=json.loads((OUT/'candidate-plan.json').read_text(encoding='utf-8'))
if saved!=plan or args.approved_plan_sha256!=digest(plan):raise SystemExit('Plan/current settings differ from the approved hash')
envfile=OUT/'candidate-env.yaml';envfile.write_text('\n'.join(f'{key}: {json.dumps(value)}' for key,value in env.items())+'\n',encoding='utf-8')
secret_args=','.join(f"{key}={value['name']}:{value['key']}" for key,value in secrets.items())
source=OUT/('source-'+sha)
if source.exists():raise SystemExit('Source staging already exists; inspect previous deployment before retry')
archive=subprocess.run(['git','archive','--format=zip',sha],cwd=ROOT,capture_output=True,check=True).stdout
with zipfile.ZipFile(io.BytesIO(archive)) as package:
    for name in package.namelist():
        if not (source/name).resolve().is_relative_to(source.resolve()):raise SystemExit('Unsafe archive path')
    package.extractall(source)
result=json.loads(command('run','deploy','chartbridge','--source',str(source), '--region','asia-northeast1','--no-traffic','--tag',tag,'--service-account',template['spec']['serviceAccountName'],'--build-service-account',f'projects/{PROJECT}/serviceAccounts/chartbridge-builder@{PROJECT}.iam.gserviceaccount.com','--min-instances','0','--max-instances','1','--concurrency','2','--memory','512Mi','--cpu','1','--timeout','60','--env-vars-file',str(envfile),'--set-secrets',secret_args,'--labels','git-sha='+sha,'--format=json'))
(OUT/'candidate-deployed.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({'revision':result['status']['latestReadyRevisionName'],'traffic':result['status']['traffic'],'git_sha':sha},indent=2))
