"""Append-only Japanese evaluation using the shared, bounded request runner."""
import argparse
import ast
import asyncio
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace
from google import genai
from google.genai import types
import run_large_evaluation as shared
from eval_core import Ledger,digest,summarize

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evaluation/japanese-v3';CACHE=ROOT/'.tmp/final-audit'
FILES=['backend/app/extraction.py','backend/app/models.py','backend/app/safety.py','backend/app/numeric_labels.py','scripts/eval_core.py','scripts/run_large_evaluation.py','scripts/run_japanese_audit.py']
def hashes():return {f:digest(ROOT/f) for f in FILES}
def exclusive(path,value):
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)

async def run(args):
    freeze=json.loads((OUT/'freeze.json').read_text(encoding='utf-8'))
    if hashes()!=freeze['code']:raise SystemExit('Frozen extraction/scorer changed')
    dataset=OUT/'development.json' if args.split=='development' else CACHE/'japanese-holdout-sealed.json'
    if digest(dataset)!=freeze[args.split+'_sha256']:raise SystemExit('Dataset changed')
    path=OUT/'runs'/args.name
    if path.exists():raise SystemExit('Run exists; no overwrite or repetition')
    if args.split=='holdout':
        if args.mode!='candidate':raise SystemExit('Holdout is candidate-only')
        exclusive(OUT/'holdout-consumed.json',{'run':args.name,'opened_at':shared.now(),'freeze':freeze})
    path.mkdir(parents=True)
    ledger_path=OUT/'usage-ledger.json'
    if not ledger_path.exists():shutil.copyfile(ROOT/'evaluation/real-v2/usage-ledger.json',ledger_path)
    ledger=Ledger(ledger_path,max_generation=300,max_counts=300,max_usd='5')
    start={k:ledger.data[k] for k in ('generation_attempts','count_attempts','charged_or_reserved_usd')}
    shared.OUT=OUT
    key=os.environ.get('GEMINI_API_KEY')
    if not key:raise SystemExit('GEMINI_API_KEY absent')
    with (ROOT/'.tmp/large-eval/runner.lock').open('x') as lock:
        try:
            async with genai.Client(api_key=key,http_options=types.HttpOptions(timeout=45000,retry_options=types.HttpRetryOptions(attempts=1))).aio as client:
                runner=shared.Runner(SimpleNamespace(name=args.name,mode=args.mode,interval=5.1),ledger,client)
                cases=json.loads(dataset.read_text(encoding='utf-8'))['cases']
                rows=[r for r in await asyncio.gather(*(runner.one(c,path) for c in cases)) if r]
            summary=summarize(rows);summary['usage_before']=start;summary['usage_after']={k:ledger.data[k] for k in start}
            exclusive(path/'summary.json',summary);exclusive(path/'metadata.json',{'code':hashes(),'freeze':freeze,'dataset_sha256':digest(dataset),'mode':args.mode,'split':args.split,'model':'gemini-3.8-flash','max_concurrency':2,'max_attempts_per_request':3,'sdk_retries':1,'stopped':runner.stop})
            print(json.dumps(summary,ensure_ascii=False,indent=2))
        finally:pass
    (ROOT/'.tmp/large-eval/runner.lock').unlink()

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8',errors='replace');p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');p.add_argument('--name');p.add_argument('--mode',choices=['baseline','candidate']);p.add_argument('--split',choices=['development','holdout']);a=p.parse_args()
    if a.freeze:
        z=zipfile.ZipFile(CACHE/'deployed-source.zip');source=z.read(next(f for f in z.namelist() if f.endswith('backend/app/extraction.py'))).decode()
        tree=ast.parse(source);prompt=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PROMPT' for t in n.targets))
        from app.models import Extraction
        exclusive(OUT/'baseline-code.json',{'prompt':prompt,'schema':Extraction.model_json_schema(),'provenance':'Cloud Build 7edd513f-f179-42f9-9fc7-431d0a99576a archived source; schema4096, legacy hold_compound_labels; SDK retries explicitly disabled for comparable billing safety'})
        exclusive(OUT/'freeze.json',{'at':shared.now(),'code':hashes(),'development_sha256':digest(OUT/'development.json'),'holdout_sha256':digest(CACHE/'japanese-holdout-sealed.json'),'note':'No extraction/prompt/scorer changes after this freeze. Baseline vs existing improved candidate, no Japanese-specific tuning.'})
    else:
        if not a.name or not a.mode or not a.split:p.error('name,mode,split required')
        asyncio.run(run(a))
