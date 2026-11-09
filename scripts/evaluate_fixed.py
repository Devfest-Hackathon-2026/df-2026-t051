"""One-shot held-out Gemini evaluation, with immutable inputs and honest failures."""
import asyncio
import hashlib
import json
import os
import statistics
import sys
import time
import unicodedata
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.extraction import extract_chart
from app.main import normalize_image


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(text):return ''.join(unicodedata.normalize('NFKC',text).casefold().split()) if text is not None else None


async def main():
    directory=ROOT/'evaluation/fixed-v1'
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    output=ROOT/'evaluation/results/fixed-v1-first-run.json'
    if output.exists():raise SystemExit('Existing first-run output will not be overwritten. Use a separately named follow-up, not an independent test.')
    for case in manifest['cases']:assert sha(directory/case['image'])==case['sha256']
    run={'started_at':datetime.now(timezone.utc).isoformat(),'model':os.environ.get('GEMINI_MODEL'),'manifest_sha256':sha(directory/'manifest.json'),
         'extractor_sha256':sha(ROOT/'backend/app/extraction.py'),'models_sha256':sha(ROOT/'backend/app/models.py'),'evaluator_sha256':sha(Path(__file__)),
         'timing_scope':'local normalization + real Gemini + schema validation; no Cloud Run or persistence','cases':[]}
    output.parent.mkdir(parents=True,exist_ok=True)
    for case in manifest['cases']:
        start=time.perf_counter()
        record={'id':case['id'],'difficulty':case['difficulty'],'image_sha256':case['sha256'],'expected_count':len(case['expected']['categories'])}
        try:
            image=normalize_image((directory/case['image']).read_bytes(),case['mime'])
            result=await extract_chart(image)
            record['result']=result.model_dump()
            record['schema_valid']=True
            predicted=result.categories if result.supported else []
            expected=case['expected']['categories']
            record['numeric_correct']=sum(i<len(predicted) and predicted[i].value is not None and Decimal(str(predicted[i].value))==Decimal(str(c['value'])) for i,c in enumerate(expected))
            record['category_correct']=sum(i<len(predicted) and norm(predicted[i].label)==norm(c['label']) for i,c in enumerate(expected))
            record['unit_correct']=result.supported and norm(result.unit)==norm(case['expected']['unit'])
            record['title_correct']=result.supported and norm(result.title)==norm(case['expected']['title'])
            record['null_values']=sum(c.value is None for c in predicted)
            record['extra_categories']=max(0,len(predicted)-len(expected))
            record['complete_match']=bool(result.supported and len(predicted)==len(expected) and record['numeric_correct']==len(expected) and record['category_correct']==len(expected) and record['unit_correct'] and record['title_correct'])
        except Exception as exc:
            record.update(schema_valid=False,error_type=type(exc).__name__,provider_status=getattr(exc,'code',None),numeric_correct=0,category_correct=0,unit_correct=False,title_correct=False,null_values=0,extra_categories=0,complete_match=False)
        record['seconds']=round(time.perf_counter()-start,3)
        run['cases'].append(record)
        output.write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:record[k] for k in ('id','numeric_correct','category_correct','unit_correct','complete_match','seconds')}),flush=True)
    rows=run['cases'];total=sum(r['expected_count'] for r in rows);seconds=[r['seconds'] for r in rows]
    run['summary']={'images':len(rows),'expected_cells':total,'numeric_correct':sum(r['numeric_correct'] for r in rows),'category_correct':sum(r['category_correct'] for r in rows),
                    'unit_correct':sum(r['unit_correct'] for r in rows),'title_correct':sum(r['title_correct'] for r in rows),'complete_images':sum(r['complete_match'] for r in rows),
                    'schema_failures':sum(not r['schema_valid'] for r in rows),'null_values':sum(r['null_values'] for r in rows),'extra_categories':sum(r['extra_categories'] for r in rows),
                    'mean_seconds':round(statistics.mean(seconds),3),'median_seconds':round(statistics.median(seconds),3),'max_seconds':max(seconds),'total_seconds':round(sum(seconds),3)}
    run['completed_at']=datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(run,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(run['summary']),flush=True)


if __name__=='__main__':asyncio.run(main())
