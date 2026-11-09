"""Bounded, append-only real Gemini experiments, separate from web/cloud state.

Run development phases first. Holdout requires a committed code/prompt freeze
record; the runner consumes its one-shot marker before opening sealed gold.
"""
import argparse
import asyncio
import importlib
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import ValidationError

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.models import Extraction
from app.safety import hold_compound_labels
from eval_core import Ledger,BudgetStop,digest,score,summarize

OUT=ROOT/'evaluation/real-v2';CACHE=ROOT/'.tmp/large-eval'


def now():return datetime.now(timezone.utc).isoformat()


def code_hashes():
    return {p:digest(ROOT/p) for p in ('backend/app/extraction.py','backend/app/models.py','backend/app/safety.py','backend/app/numeric_labels.py','backend/app/main.py','scripts/eval_core.py','scripts/run_large_evaluation.py')}


def safe_text(text):
    key=os.environ.get('GEMINI_API_KEY')
    if key:text=text.replace(key,'[REDACTED]')
    return re.sub(r'AIza[0-9A-Za-z_-]{35}','[REDACTED]',text)


class Runner:
    def __init__(self,args,ledger,client):
        self.args=args;self.ledger=ledger;self.client=client
        self.semaphore=asyncio.Semaphore(2);self.pace=asyncio.Lock();self.next_start=0.;self.stop=False;self.timings={}

    async def request(self,kind,case,contents,config):
        for attempt in range(3):
            if self.stop:raise BudgetStop('Stopped before next request')
            async with self.pace:
                while self.next_start>time.monotonic():await asyncio.sleep(self.next_start-time.monotonic())
                self.next_start=time.monotonic()+getattr(self.args,'interval',5.1)
            if self.stop:raise BudgetStop('Stopped during pacing wait')
            index=self.ledger.reserve(kind,self.args.name+'/'+case,config.max_output_tokens if kind=='generation' else 8192)
            request_start=time.perf_counter()
            try:
                if kind=='count':
                    # Developer API cannot accept CountTokens.generation_config.
                    # Count contents and keep the predeclared 2048-token schema reserve.
                    result=await self.client.models.count_tokens(model='gemini-3.8-flash',contents=contents)
                    self.ledger.settle(index,status='completed');return result
                response=await self.client.models.generate_content(model='gemini-3.8-flash',contents=contents,config=config)
                usage=response.usage_metadata.model_dump(exclude_none=True) if response.usage_metadata else None
                self.ledger.settle(index,usage=usage);return response
            except BudgetStop:
                self.stop=True;raise
            except Exception as exc:
                status=getattr(exc,'code',None);self.ledger.settle(index,status=f'HTTP_{status}' if status else type(exc).__name__)
                if status!=429 or attempt==2:raise
                # Global backoff, SDK retries disabled. Never exceed two retries.
                delay=20*(2**attempt)+random.uniform(0,1)
                self.next_start=max(self.next_start,time.monotonic()+delay)
                print(json.dumps({'case':case,'event':'429_backoff','seconds':round(delay,2),'attempt':attempt+1}),flush=True)
            finally:
                self.timings.setdefault(case,[]).append({'kind':kind,'attempt':attempt+1,'seconds':round(time.perf_counter()-request_start,3)})
        raise AssertionError('unreachable')

    async def one(self,case,phase_path):
        async with self.semaphore:
            if self.stop:return None
            start=time.perf_counter();row={'id':case['id'],'started_at':now(),'result':None}
            try:
                from app.main import normalize_image
                path=ROOT/case['cache']
                if digest(path)!=case['image_sha256']:raise ValueError('Image hash mismatch')
                mime='image/jpeg' if path.suffix.lower() in ('.jpg','.jpeg') else 'image/png'
                data=normalize_image(path.read_bytes(),mime)
                module=importlib.import_module('app.extraction')
                if self.args.mode=='baseline':
                    baseline=json.loads((OUT/'baseline-code.json').read_text(encoding='utf-8'))
                    prompt=baseline['prompt'];config=types.GenerateContentConfig(response_mime_type='application/json',response_json_schema=baseline['schema'],temperature=0,max_output_tokens=4096)
                else:
                    prompt=module.PROMPT;config=module.generation_config()
                contents=[types.Part.from_bytes(data=data,mime_type='image/png'),prompt]
                counted=await self.request('count',case['id'],contents,config)
                row['counted_input_tokens']=counted.total_tokens
                if counted.total_tokens is None or counted.total_tokens>6144:raise ValueError('Input token cap reached (2048 schema reserve)')
                response=await self.request('generation',case['id'],contents,config)
                row['raw_text']=safe_text(response.text or '')
                row['usage']=response.usage_metadata.model_dump(exclude_none=True) if response.usage_metadata else None
                row['finish_reasons']=[str(c.finish_reason) for c in response.candidates or []]
                if self.args.mode=='baseline':result=Extraction.model_validate_json(response.text or '')
                else:result=module.parse_extraction_response(response.text or '')
                row['raw_schema_valid']=True
                if self.args.mode=='baseline':result=hold_compound_labels(result)
                else:
                    from app.safety import normalize_extraction
                    result=normalize_extraction(result)
                row['result']=result.model_dump()
            except BudgetStop as exc:
                self.stop=True;row['error_type']='BudgetStop'
            except ValidationError as exc:
                row.update(error_type='ValidationError',validation_errors=[{'type':e['type'],'loc':e['loc'],'message':safe_text(e['msg'])} for e in exc.errors(include_input=False,include_url=False)])
            except Exception as exc:
                row.update(error_type=type(exc).__name__,status_code=getattr(exc,'code',None) or getattr(exc,'status_code',None))
                if isinstance(exc,(ValueError,TypeError)):row['local_error_detail']=safe_text(str(exc))[:500]
                if getattr(exc,'code',None)==429:self.stop=True
            row['seconds']=round(time.perf_counter()-start,3)
            row['request_timings']=self.timings.get(case['id'],[])
            row['generation_request_seconds']=round(sum(t['seconds'] for t in row['request_timings'] if t['kind']=='generation'),3)
            row['score']=score(case['gold'],row['result'],row.get('error_type'),row.get('status_code'))
            if row.get('validation_errors') and any('MAX_TOKENS' in r for r in row.get('finish_reasons',[])):
                row['score']['findings'].append({'class':'D','observation':'Provider MAX_TOKENS plus schema validation failure','cause':'出力予算到達。途中切断の有無はraw_textと検証箇所を確認する'})
            with (phase_path/'cases.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
            print(json.dumps({'id':case['id'],'error':row.get('error_type'),'numeric':row['score']['numeric_correct'],'complete':row['score']['complete_match'],'seconds':row['seconds']},ensure_ascii=False),flush=True)
            return row


async def main(args):
    if args.split=='holdout' and (args.mode!='candidate' or args.limit):raise SystemExit('Only a full candidate holdout is permitted; seal not consumed.')
    approval_path=OUT/'budget-approval.json'
    if not approval_path.exists():raise SystemExit('No recorded user budget approval; no API request issued.')
    approval=json.loads(approval_path.read_text(encoding='utf-8'));assert approval['approved'] is True
    lock=CACHE/'runner.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    try:handle=lock.open('x')
    except FileExistsError:raise SystemExit('Another runner owns the lock; no request issued.')
    try:
        phase_path=OUT/'runs'/args.name
        if phase_path.exists():raise SystemExit('Experiment already exists; will not overwrite/repeat.')
        phase_path.mkdir(parents=True)
        split_lock=json.loads((OUT/'split-lock.json').read_text())
        if args.split=='holdout':
            freeze=json.loads((OUT/'candidate-freeze.json').read_text())
            if code_hashes()!=freeze['hashes']:raise SystemExit('Code changed since candidate freeze')
            if digest(CACHE/'holdout-sealed.json')!=split_lock['holdout_gold_sha256']:raise SystemExit('Sealed gold hash mismatch')
            with (OUT/'holdout-consumed.json').open('x') as f:json.dump({'opened_at':now(),'name':args.name,'freeze':freeze},f,indent=2)
            source=CACHE/'holdout-sealed.json'
        else:
            source=OUT/{'development':'development.json','anomaly':'anomalies.json','legacy-diagnostic':'legacy-diagnostic.json'}[args.split]
            if args.split=='development' and digest(source)!=split_lock['development_sha256']:raise SystemExit('Development set hash mismatch')
        dataset=json.loads(source.read_text(encoding='utf-8'));cases=dataset['cases']
        if args.limit:cases=cases[:args.limit]
        metadata={'started_at':now(),'split':args.split,'mode':args.mode,'model':'gemini-3.8-flash','code':code_hashes(),'dataset_sha256':digest(source),'commit':subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip(),'sdk_retries':1,'maximum_concurrent_cases':2,'max_retries_per_request':2,'request_start_interval_seconds':args.interval}
        (phase_path/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        reserve_for_final=25*Ledger.price(8192,8192) if args.split!='holdout' and not (OUT/'holdout-consumed.json').exists() else 0
        reserve_calls=25 if reserve_for_final else 0
        metadata['reserved_for_final_usd']=str(reserve_for_final)
        ledger=Ledger(OUT/'usage-ledger.json',max_generation=approval['max_generation_attempts']-reserve_calls,max_counts=approval['max_count_attempts']-reserve_calls,max_usd=str(Decimal(str(approval['max_estimated_usd']))-reserve_for_final))
        key=os.environ.get('GEMINI_API_KEY')
        if not key:raise SystemExit('GEMINI_API_KEY missing; no value printed')
        async with genai.Client(api_key=key,http_options=types.HttpOptions(timeout=45_000,retry_options=types.HttpRetryOptions(attempts=1))).aio as client:
            runner=Runner(args,ledger,client)
            rows=[r for r in await asyncio.gather(*(runner.one(c,phase_path) for c in cases)) if r is not None]
        metadata.update(completed_at=now(),completed_cases=len(rows),planned_cases=len(cases),stopped=runner.stop)
        summary=summarize(rows);summary.update(usage_ledger_at_end={'generation_attempts':ledger.data['generation_attempts'],'count_attempts':ledger.data['count_attempts'],'charged_or_reserved_usd':ledger.data['charged_or_reserved_usd']})
        (phase_path/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
        (phase_path/'metadata.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
        print(json.dumps(summary,ensure_ascii=False,indent=2))
    finally:
        handle.close();lock.unlink()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser();parser.add_argument('--name',required=True);parser.add_argument('--mode',choices=['baseline','candidate'],required=True);parser.add_argument('--split',choices=['development','holdout','anomaly','legacy-diagnostic'],required=True);parser.add_argument('--limit',type=int);parser.add_argument('--interval',type=float,default=5.1)
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]{1,60}',args.name):raise SystemExit('Invalid experiment name')
    if not 1.1<=args.interval<=60:raise SystemExit('Request interval must be between 1.1 and 60 seconds')
    asyncio.run(main(args))
