"""Deterministic scoring and a fail-closed, persistent experiment budget."""
import hashlib
import json
import math
import re
import statistics
import unicodedata
from decimal import Decimal
from pathlib import Path


def norm(value):
    if value is None:return None
    return re.sub(r'\s+','',unicodedata.normalize('NFKC',value).casefold())


def unit_norm(value):
    result=norm(value)
    if result is None:return None
    # Frozen lexical aliases only: no physical conversion or dropped denominators.
    for old,new in [('percentage','%'),('percent','%'),('percapita','/capita'),('squaremetres','m2'),('squaremeters','m2'),('tonnes','t'),('kilograms','kg')]:result=result.replace(old,new)
    return result


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal_number(a,b):
    if a is None or b is None:return a is b
    return Decimal(str(a))==Decimal(str(b))


def score(gold,result,error=None,status_code=None):
    """All expected cells stay in the denominator after rejection/schema failure.

    Labels are compared in order. A wrong number at a correct label is observed
    as F; OCR cause A is NOT guessed from numerical mismatch alone.
    """
    expected=gold['categories'];predicted=(result or {}).get('categories',[]) if (result or {}).get('supported') else []
    row={'schema_valid':result is not None,'expected_cells':len(expected),'expected_known':sum(c['value'] is not None for c in expected),'expected_null':sum(c['value'] is None for c in expected),'numeric_correct':0,'category_correct':0,'returned_null':0,'appropriate_null':0,'unnecessary_null':0,'wrong_confirmed':0,'missing_cells':0,'extra_cells':max(0,len(predicted)-len(expected)),'unit_mismatch_confirmed_cells':0,'findings':[]}
    if not gold['supported']:
        if result is None and error=='HTTPException' and status_code in (413,415,422):
            row.update(scope_correct=True,title_correct=None,unit_correct=None,complete_match=True,input_validation_rejected=True)
            return row
        row.update(scope_correct=result is not None and result['supported'] is False,title_correct=None,unit_correct=None,complete_match=result is not None and result['supported'] is False)
        if result is not None and result['supported']:row['findings'].append({'class':'G','observation':'Out-of-scope image accepted','cause':'原因未特定'})
        elif result is None:row['findings'].append({'class':'D' if error=='ValidationError' else 'G','observation':error or 'no result','cause':'原因未特定'})
        return row
    row['scope_correct']=result is not None and result['supported'] is True
    row['title_correct']=result is not None and norm(result['title'])==norm(gold['title'])
    row['unit_correct']=result is not None and unit_norm(result['unit'])==unit_norm(gold['unit'])
    row['unit_exact']=result is not None and norm(result['unit'])==norm(gold['unit'])
    for i,e in enumerate(expected):
        if i>=len(predicted):row['missing_cells']+=1;continue
        p=predicted[i];row['category_correct']+=norm(p['label'])==norm(e['label'])
        if p['value'] is None:
            row['returned_null']+=1
            if e['value'] is None:row['appropriate_null']+=1
            else:row['unnecessary_null']+=1;row['findings'].append({'class':'E','cell':i,'observation':'Readable gold value held as null','cause':'原因未特定'})
        elif e['value'] is None or not equal_number(p['value'],e['value']):
            row['wrong_confirmed']+=1
            matches=[j for j,c in enumerate(expected) if j!=i and equal_number(p['value'],c['value']) and norm(p['label'])!=norm(e['label'])]
            row['findings'].append({'class':'C' if matches else 'F','cell':i,'observation':'Wrong non-null value returned','cause':'対応ずれの候補' if matches else '原因未特定'})
        else:row['numeric_correct']+=1
        if p['value'] is not None and result['unit'] is not None and not row['unit_correct']:
            row['unit_mismatch_confirmed_cells']+=1
    if row['unit_mismatch_confirmed_cells']:
        row['findings'].append({'class':'B','observation':'Non-null values accompanied by nonmatching unit; critical potential unit accident (includes lexical mismatch)','cause':'意味上の単位不一致か表記差かは要調査'})
    if result is None:row['findings'].append({'class':'D' if error=='ValidationError' else 'G','observation':error or 'No result','cause':'原因未特定'})
    elif not result['supported']:row['findings'].append({'class':'G','observation':'In-scope chart rejected','cause':'原因未特定'})
    elif row['category_correct']!=len(expected):row['findings'].append({'class':'A','observation':'Category transcription mismatch (symptom only)','cause':'原因未特定'})
    if result is not None and result['supported'] and not row['title_correct']:row['findings'].append({'class':'G','observation':'Title mismatch','cause':'原因未特定'})
    row['complete_match']=bool(row['scope_correct'] and len(predicted)==len(expected) and row['numeric_correct']==row['expected_known'] and row['appropriate_null']==row['expected_null'] and row['category_correct']==len(expected) and row['title_correct'] and row['unit_correct'])
    return row


def summarize(rows):
    scores=[r['score'] for r in rows];times=sorted(r['seconds'] for r in rows)
    keys=('expected_cells','expected_known','expected_null','numeric_correct','category_correct','returned_null','appropriate_null','unnecessary_null','wrong_confirmed','missing_cells','extra_cells','unit_mismatch_confirmed_cells')
    totals={key:sum(s.get(key,0) for s in scores) for key in keys}
    totals.update(images=len(scores),schema_valid=sum(s['schema_valid'] for s in scores),complete_match=sum(s['complete_match'] for s in scores),title_correct=sum(s.get('title_correct') is True for s in scores),unit_correct=sum(s.get('unit_correct') is True for s in scores),scope_correct=sum(s['scope_correct'] for s in scores),mean_seconds=round(statistics.mean(times),3) if times else None,median_seconds=round(statistics.median(times),3) if times else None,p95_seconds=times[max(0,math.ceil(.95*len(times))-1)] if times else None)
    totals['null_recall']=totals['appropriate_null']/totals['expected_null'] if totals['expected_null'] else None
    totals['null_precision']=totals['appropriate_null']/totals['returned_null'] if totals['returned_null'] else None
    totals['numeric_accuracy']=totals['numeric_correct']/totals['expected_known'] if totals['expected_known'] else None
    totals['abstention_rate']=totals['returned_null']/totals['expected_cells'] if totals['expected_cells'] else None
    totals['failure_observations']={code:sum(f['class']==code for s in scores for f in s['findings']) for code in 'ABCDEFG'}
    totals['model_responses']=sum('raw_text' in r for r in rows)
    totals['json_pydantic_valid_responses']=sum(bool(r.get('raw_schema_valid')) for r in rows)
    totals['json_pydantic_success_rate']=totals['json_pydantic_valid_responses']/totals['model_responses'] if totals['model_responses'] else None
    totals['input_validation_rejections']=sum(s.get('input_validation_rejected',False) for s in scores)
    api_times=sorted(r['generation_request_seconds'] for r in rows if any(t['kind']=='generation' for t in r.get('request_timings',[])))
    totals['generation_request_latency']={'cases_with_generation':len(api_times),'mean_seconds':round(statistics.mean(api_times),3) if api_times else None,'median_seconds':round(statistics.median(api_times),3) if api_times else None,'p95_seconds':api_times[max(0,math.ceil(.95*len(api_times))-1)] if api_times else None,'includes_failed_attempts':True,'excludes_queue_count_tokens_and_backoff':True}
    return totals


class BudgetStop(RuntimeError):pass


class Ledger:
    """One runner owns the file lock. Reserve BEFORE issuing each request.

    An interrupted/failed call retains its conservative cost reservation. Usage
    without thinking-token accounting can never silently lower a reservation.
    """
    def __init__(self,path,max_generation=300,max_counts=300,max_usd=12):
        self.path=Path(path);self.max_generation=max_generation;self.max_counts=max_counts;self.max_usd=Decimal(str(max_usd))
        self.data=json.loads(self.path.read_text()) if self.path.exists() else {'generation_attempts':0,'count_attempts':0,'charged_or_reserved_usd':'0','attempts':[]}
        self.save()

    def save(self):
        temp=self.path.with_suffix('.new');temp.write_text(json.dumps(self.data,indent=2),encoding='utf-8');temp.replace(self.path)

    @staticmethod
    def price(input_tokens,output_tokens):return (Decimal(input_tokens)*Decimal('.75')+Decimal(output_tokens)*Decimal('3.75'))/Decimal(1000000)

    def reserve(self,kind,case,output_tokens=8192):
        if kind not in ('generation','count'):raise ValueError('Unknown request kind')
        key=kind+'_attempts';maximum=self.max_generation if kind=='generation' else self.max_counts
        amount=self.price(8192,output_tokens) if kind=='generation' else Decimal(0)
        if self.data[key]>=maximum or Decimal(self.data['charged_or_reserved_usd'])+amount>self.max_usd:raise BudgetStop('Experiment budget reached; no request issued')
        self.data[key]+=1;self.data['charged_or_reserved_usd']=str(Decimal(self.data['charged_or_reserved_usd'])+amount)
        self.data['attempts'].append({'kind':kind,'case':case,'reserved_usd':str(amount),'state':'pending_or_unknown'})
        self.save();return len(self.data['attempts'])-1

    def settle(self,index,usage=None,status='completed'):
        item=self.data['attempts'][index];item['state']=status
        if usage is not None and usage.get('prompt_token_count') is not None and usage.get('total_token_count') is not None:
            inputs=usage['prompt_token_count'];outputs=max((usage.get('candidates_token_count') or 0)+(usage.get('thoughts_token_count') or 0),usage['total_token_count']-inputs)
            actual=self.price(inputs,outputs)
            self.data['charged_or_reserved_usd']=str(Decimal(self.data['charged_or_reserved_usd'])-Decimal(item['reserved_usd'])+actual)
            item.update(usage=usage,estimated_usd=str(actual))
            if inputs>8192 or outputs>8192:
                self.save();raise BudgetStop('Provider usage exceeded declared per-call envelope; stopping')
        self.save()
