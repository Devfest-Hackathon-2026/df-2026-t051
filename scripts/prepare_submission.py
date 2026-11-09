"""Create a reviewable source-only ZIP, without Git history or local credentials."""
import hashlib
import argparse
import json
import os
import re
import subprocess
import zipfile
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
parser.add_argument('--output',default=f'output/submission/chartbridge-review-{stamp}.zip')
parser.add_argument('--record',default=f'docs/final-audit/submission-package-{stamp}.json')
args=parser.parse_args()
target=(ROOT/args.output).resolve();record_path=(ROOT/args.record).resolve()
if not target.is_relative_to((ROOT/'output/submission').resolve()) or not record_path.is_relative_to((ROOT/'docs/final-audit').resolve()):
    raise SystemExit('Keep archive and record inside the review artifact directories')
if target.exists() or record_path.exists():raise SystemExit('Review artifacts already exist; will not overwrite history')
paths=subprocess.run(['git','ls-files','-z'],cwd=ROOT,capture_output=True,check=True).stdout.decode('utf-8').split('\0')
patterns=[re.compile(rb'AIza[0-9A-Za-z_-]{35}'),re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(rb'eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}')]
secret=os.environ.get('GEMINI_API_KEY','').encode()
files=[];rejected=[]
for relative in paths:
    if not relative or relative=='docs/verification/submission-package.json':continue
    path=ROOT/relative
    if not path.is_file():continue
    parts=Path(relative).parts
    if any(p in {'.git','.tmp','.venv','node_modules','dist','static','__pycache__','test-results','test-results-live'} for p in parts):
        raise SystemExit('Excluded artifact was tracked: '+relative)
    if Path(relative).name.startswith('.env') and not relative.endswith('.env.example'):
        raise SystemExit('Unexpected tracked environment file: '+relative)
    data=path.read_bytes()
    if (secret and secret in data) or any(p.search(data) for p in patterns):rejected.append(relative)
    files.append({'path':relative,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
if rejected:raise SystemExit('Credential-like content detected in files (values not displayed): '+', '.join(rejected))
target.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED) as archive:
    for item in files:archive.write(ROOT/item['path'],item['path'])
    archive.writestr('SUBMISSION_MANIFEST.json',json.dumps({'created_at':datetime.now(timezone.utc).isoformat(),'files':files,'includesGitHistory':False,'secretPatternFindings':0},ensure_ascii=False,indent=2))
record={'archive':target.relative_to(ROOT).as_posix(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'files':len(files),'bytes':target.stat().st_size,'gitHistoryIncluded':False,'secretPatternFindings':0,'geminiKeyMatch':False,'publicRepositoryPush':False}
with record_path.open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
print(json.dumps(record,indent=2))
