"""One-shot evaluation of six genuine MAFF educational chart images."""
import asyncio
import hashlib
import json
import os
import statistics
import sys
import time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.extraction import extract_chart
from app.main import normalize_image
from evaluate_fixed import norm,sha


def unit_scale(unit):
    name=norm(unit)
    if name is None:return None
    name=name.replace('(','').replace(')','')
    return {'t':1,'トン':1,'千t':1000,'千トン':1000,'万t':10000,'万トン':10000}.get(name)


async def main():
    manifest_path=ROOT/'evaluation/real-v1/manifest.json'
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    target=ROOT/'evaluation/real-v1/first-run.json'
    if target.exists():raise SystemExit('Will not overwrite the first run.')
    run={'started_at':datetime.now(timezone.utc).isoformat(),'model':os.environ.get('GEMINI_MODEL'),'manifest_sha256':sha(manifest_path),'extractor_sha256':sha(ROOT/'backend/app/extraction.py'),'cases':[]}
    for case in manifest['cases']:
        path=ROOT/case['cache'];assert sha(path)==case['sha256']
        start=time.perf_counter();expected=case['expected'];count=len(expected['categories'])
        record={'id':case['id'],'compound_notation':case['mixed_japanese_number_notation'],'expected_cells':count}
        try:
            result=await extract_chart(normalize_image(path.read_bytes(),'image/png'))
            record['result']=result.model_dump()
            predicted=result.categories if result.supported else []
            record['schema_valid']=True
            record['numeric_correct']=sum(i<len(predicted) and predicted[i].value is not None and Decimal(str(predicted[i].value))==Decimal(str(c['value'])) for i,c in enumerate(expected['categories']))
            record['category_correct']=sum(i<len(predicted) and norm(predicted[i].label)==norm(c['label']) for i,c in enumerate(expected['categories']))
            record['title_correct']=result.supported and norm(result.title)==norm(expected['title'])
            record['unit_correct']=result.supported and norm(result.unit)==norm(expected['unit'])
            factor=unit_scale(result.unit);expected_factor=unit_scale(expected['unit'])
            record['ton_equivalent_correct']=sum(i<len(predicted) and predicted[i].value is not None and factor is not None and Decimal(str(predicted[i].value))*factor==Decimal(str(c['value']))*expected_factor for i,c in enumerate(expected['categories']))
            record['null_values']=sum(c.value is None for c in predicted)
            record['complete_match']=bool(result.supported and len(predicted)==count and record['numeric_correct']==count and record['category_correct']==count and record['title_correct'] and record['unit_correct'])
        except Exception as exc:
            record.update(schema_valid=False,error_type=type(exc).__name__,status_code=getattr(exc,'code',None),numeric_correct=0,category_correct=0,title_correct=False,unit_correct=False,ton_equivalent_correct=0,null_values=0,complete_match=False)
        record['seconds']=round(time.perf_counter()-start,3);run['cases'].append(record)
        target.write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:record[k] for k in ('id','numeric_correct','category_correct','unit_correct','ton_equivalent_correct','complete_match','seconds')}),flush=True)
    rows=run['cases'];times=[r['seconds'] for r in rows]
    run['summary']={'images':len(rows),'expected_cells':sum(r['expected_cells'] for r in rows),**{key:sum(r[key] for r in rows) for key in ('numeric_correct','category_correct','title_correct','unit_correct','ton_equivalent_correct','null_values','complete_match')},'schema_failures':sum(not r['schema_valid'] for r in rows),'mean_seconds':round(statistics.mean(times),3),'median_seconds':round(statistics.median(times),3),'max_seconds':max(times)}
    run['completed_at']=datetime.now(timezone.utc).isoformat();target.write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(run['summary']),flush=True)


if __name__=='__main__':asyncio.run(main())
