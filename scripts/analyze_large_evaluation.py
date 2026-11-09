"""Reproducible symptom/cause report; never invent OCR causes from mismatches."""
import argparse
import json
from pathlib import Path
import sys
from eval_core import norm,unit_norm,summarize

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evaluation/real-v2'
sys.path.insert(0,str(ROOT/'backend'))
from app.models import Extraction
from eval_core import score


def analyze(name):
    run=OUT/'runs'/name
    metadata=json.loads((run/'metadata.json').read_text(encoding='utf-8'))
    if metadata['split']=='holdout':raise SystemExit('Holdout analysis uses its run output only after final evaluation, not this development tool')
    source=OUT/{'development':'development.json','anomaly':'anomalies.json','legacy-diagnostic':'legacy-diagnostic.json'}[metadata['split']]
    gold={c['id']:c for c in json.loads(source.read_text(encoding='utf-8'))['cases']}
    rows=[json.loads(line) for line in (run/'cases.jsonl').read_text(encoding='utf-8').splitlines()]
    failures=[];raw_rows=[]
    for row in rows:
        raw=None
        try:raw=Extraction.model_validate_json(row.get('raw_text','')).model_dump()
        except Exception:pass
        raw_rows.append({**row,'score':score(gold[row['id']]['gold'],raw,row.get('error_type'))})
        if row['score']['complete_match']:continue
        expected=gold[row['id']]['gold'];predicted=row['result'];findings=row['score']['findings']
        diagnoses=[]
        if predicted and predicted['unit'] and not row['score']['unit_correct']:
            gu=unit_norm(expected['unit']);pu=unit_norm(predicted['unit'])
            if gu and pu=='%' and gu.startswith('%of'):
                diagnoses.append({'class':'B','cause':'単位の分母・対象が出力で省略された','evidence':{'printed_unit_gold':expected['unit'],'returned_unit':predicted['unit']},'certainty':'出力上の欠落は確認。モデル内部の原因は未特定'})
            else:diagnoses.append({'class':'B','cause':'原因未特定（表記差か意味差かの個別照合が必要）','evidence':{'printed_unit_gold':expected['unit'],'returned_unit':predicted['unit']}})
        errors=row.get('validation_errors',[])
        if errors:
            if any('MAX_TOKENS' in s for s in row.get('finish_reasons',[])) and any(e['type']=='json_invalid' and ('EOF' in e['message'] or 'end' in e['message']) for e in errors):
                diagnoses.append({'class':'D','cause':'出力上限到達とJSON途中切断を確認','evidence':{'finish_reasons':row['finish_reasons'],'validation':errors,'raw_length':len(row.get('raw_text','')),'usage':row.get('usage')}})
            else:diagnoses.append({'class':'D','cause':'原因未特定','evidence':{'finish_reasons':row.get('finish_reasons'),'validation':errors}})
        failures.append({'id':row['id'],'input_url':gold[row['id']]['image_url'],'input_sha256':gold[row['id']]['image_sha256'],'expected':expected,'returned':predicted,'observations':findings,'diagnoses':diagnoses,'unexplained_observations':[f for f in findings if f['class'] not in {d['class'] for d in diagnoses}]})
    record={'run':name,'completed_cases':len(rows),'summary':summarize(rows),'raw_model_summary_before_safety':summarize(raw_rows),'diagnostic_only':metadata['split']=='legacy-diagnostic','failed_images':len(failures),'failures':failures,'classification_note':'Observations can overlap. B includes lexical mismatches and is not automatically a proven physical-unit accident. A/C are symptoms/candidates, not proven internal mechanisms.'}
    dest=run/'analysis.json'
    if dest.exists():raise SystemExit('Analysis already exists; no overwrite')
    dest.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'run':name,'cases':len(rows),'failed_images':len(failures),'observations':record['summary']['failure_observations']},ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('name');args=parser.parse_args();analyze(args.name)
