"""Post-freeze reporting only. Does not call a model or alter extraction/scoring."""
import json
from pathlib import Path
import sys
from decimal import Decimal
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'evaluation/real-v2'
sys.path.insert(0,str(ROOT/'scripts'))
from run_large_evaluation import code_hashes


def load(path):return json.loads(path.read_text(encoding='utf-8'))


def main():
    freeze=load(OUT/'candidate-freeze.json')
    assert code_hashes()==freeze['hashes'],'Frozen implementation changed after final evaluation'
    metadata=load(OUT/'runs/final-once/metadata.json')
    assert metadata['completed_cases']==25 and metadata['stopped'] is False
    consumed=load(OUT/'holdout-consumed.json');assert consumed['name']=='final-once'
    ledger=load(OUT/'usage-ledger.json');attempts=ledger['attempts']
    assert Decimal(ledger['charged_or_reserved_usd'])<=5
    assert ledger['generation_attempts']<=300 and ledger['count_attempts']<=300
    assert all(a['state']!='pending_or_unknown' for a in attempts)
    summaries={name:load(OUT/'runs'/name/'summary.json') for name in ('development-baseline','development-cycle1','final-once','anomaly-baseline','anomaly-cycle1','legacy-baseline','legacy-cycle1')}
    final_gold={c['id']:c for c in load(ROOT/'.tmp/large-eval/holdout-sealed.json')['cases']}
    rows=[json.loads(line) for line in (OUT/'runs/final-once/cases.jsonl').read_text(encoding='utf-8').splitlines()]
    final_mismatches=[{'id':r['id'],'expected_unit':final_gold[r['id']]['gold']['unit'],'returned_unit':r['result']['unit'],'observation':'測定単位は保持され、対象集団・Total等の付帯情報が追加された。固定の厳密一致では不一致。評価後の調整は行わない。'} for r in rows if not r['score']['complete_match']]
    usage={'generation_attempts':ledger['generation_attempts'],'count_sdk_attempts':ledger['count_attempts'],'count_local_sdk_failures':sum(a['kind']=='count' and a['state']=='ValueError' for a in attempts),'metadata_model_reads_before_experiment':1,'http_429':sum(a['state']=='HTTP_429' for a in attempts),'prompt_tokens':sum(a.get('usage',{}).get('prompt_token_count',0) for a in attempts),'candidate_tokens':sum(a.get('usage',{}).get('candidates_token_count',0) or 0 for a in attempts),'thinking_tokens':sum(a.get('usage',{}).get('thoughts_token_count',0) or 0 for a in attempts),'estimated_usd':ledger['charged_or_reserved_usd'],'unknown_generation_reservations':sum(a['kind']=='generation' and 'estimated_usd' not in a for a in attempts),'approved_max_usd':5,'tax_fx_and_other_services_excluded':True,'pricing_usd_per_million':{'input':.75,'output_including_thinking':3.75}}
    record={'reported_at':datetime.now(timezone.utc).isoformat(),'candidate_freeze_commit':freeze['commit'],'cycles':1,'summaries':summaries,'final_mismatches':final_mismatches,'usage':usage,'automated_tests':{'python':134,'math':4,'playwright':16,'deployed_rules':45,'passed':199,'failed':0,'typescript':'passed','production_build':'passed','current_cloud_e2e':'not rerun; candidate not deployed'},'anomaly_scoring_erratum':'Original baseline records model rejection 14/14 and one pre-model input error; adapter initially counted the 422 as failure. Separate input-filter-check proves safe 422; final scores count validation rejection as correct. Original logs preserved.','scope_limitations':['Positive set is English OECD charts with 2-5 categories, shared renderer/publisher','Source-family disjoint only; not publisher-disjoint; model pretraining exposure unknown','No independently sourced Japanese/compound-place-value/native JPEG/blur/negative/zero/missing-field positive accuracy established','No expected nulls in positive gold: null precision/recall undefined, not 100 percent','Teacher review remains mandatory; no general accuracy guarantee'],'deployment':'unchanged, private; no production approval exercised'}
    with (OUT/'final-report.json').open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
    print(json.dumps({'final_complete':summaries['final-once']['complete_match'],'final_images':25,'final_values':summaries['final-once']['numeric_correct'],'usage':usage},ensure_ascii=False,indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
