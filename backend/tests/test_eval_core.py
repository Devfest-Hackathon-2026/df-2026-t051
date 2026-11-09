"""Scoring and budget invariants; no external API calls."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
from eval_core import BudgetStop,Ledger,score,summarize


def example():
    return {'supported':True,'title':'Test','unit':'% of GDP','categories':[{'label':'A','value':0},{'label':'B','value':-2},{'label':'C','value':None}]}


def test_exact_zero_negative_and_null():
    gold=example();s=score(gold,gold)
    assert s['complete_match'] and s['numeric_correct']==2 and s['appropriate_null']==1


def test_missing_values_never_disappear_from_denominator():
    s=score(example(),None,'ValidationError')
    assert s['expected_cells']==3 and s['expected_known']==2
    assert s['numeric_correct']==0 and s['missing_cells']==3
    assert s['findings'][0]['class']=='D'


def test_wrong_unit_with_correct_numbers_is_not_complete():
    gold=example();predicted={**gold,'unit':'% of earnings'};s=score(gold,predicted)
    assert s['numeric_correct']==2 and not s['complete_match']
    assert s['unit_mismatch_confirmed_cells']==2


def test_unknown_unit_not_mistaken_for_a_confirmed_wrong_unit():
    s=score(example(),{**example(),'unit':None})
    assert not s['unit_correct'] and s['unit_mismatch_confirmed_cells']==0


def test_null_abstention_is_not_numeric_accuracy():
    gold=example();predicted={**gold,'categories':[{'label':'A','value':None},{'label':'B','value':None},{'label':'C','value':None}]}
    s=score(gold,predicted);assert s['numeric_correct']==0 and s['unnecessary_null']==2 and s['appropriate_null']==1
    summary=summarize([{'score':s,'seconds':1}])
    assert summary['numeric_accuracy']==0 and summary['abstention_rate']==1


def test_no_expected_null_reports_undefined_recall():
    gold={**example(),'categories':[{'label':'A','value':1}]}
    summary=summarize([{'score':score(gold,gold),'seconds':1}])
    assert summary['null_recall'] is None and summary['null_precision'] is None


def test_false_confirmed_and_category_order_are_detected():
    gold=example();p={**gold,'categories':[{'label':'B','value':-2},{'label':'A','value':0},{'label':'C','value':None}]}
    s=score(gold,p);assert s['wrong_confirmed']==2 and s['category_correct']==1
    assert len([f for f in s['findings'] if f['class']=='C'])==2


def test_abnormal_set_has_no_numeric_denominator():
    gold={'supported':False,'title':None,'unit':None,'categories':[]}
    s=score(gold,example());assert s['expected_cells']==0 and not s['scope_correct']


def test_oversized_abnormal_input_is_safely_rejected_before_model_call():
    gold={'supported':False,'title':None,'unit':None,'categories':[]}
    s=score(gold,None,'HTTPException',422)
    assert s['scope_correct'] and s['complete_match'] and s['input_validation_rejected']
    assert not s['schema_valid']
    assert not score(example(),None,'HTTPException',422)['complete_match']


def test_p95_nearest_rank_is_declared_and_correct():
    s=score(example(),example());result=summarize([{'score':s,'seconds':i} for i in range(1,21)])
    assert result['p95_seconds']==19 and result['median_seconds']==10.5


def test_budget_reservation_survives_restart_and_failure(tmp_path):
    path=tmp_path/'ledger.json';ledger=Ledger(path,max_generation=1,max_usd=1)
    ledger.reserve('generation','case')
    again=Ledger(path,max_generation=1,max_usd=1)
    assert again.data['charged_or_reserved_usd']=='0.036864'
    with pytest.raises(BudgetStop):again.reserve('generation','retry')


def test_estimated_cost_includes_thinking_tokens(tmp_path):
    ledger=Ledger(tmp_path/'ledger.json');index=ledger.reserve('generation','case')
    ledger.settle(index,{'prompt_token_count':100,'candidates_token_count':10,'thoughts_token_count':90,'total_token_count':200})
    assert ledger.data['charged_or_reserved_usd']=='0.000450'


def test_two_reservations_cannot_overrun_budget(tmp_path):
    ledger=Ledger(tmp_path/'ledger.json',max_usd=.05);ledger.reserve('generation','first')
    with pytest.raises(BudgetStop):ledger.reserve('generation','second')
    assert ledger.data['generation_attempts']==1


def test_count_requests_have_their_own_cap(tmp_path):
    ledger=Ledger(tmp_path/'ledger.json',max_counts=1);ledger.reserve('count','first')
    with pytest.raises(BudgetStop):ledger.reserve('count','second')


def test_provider_excess_stops_further_work(tmp_path):
    ledger=Ledger(tmp_path/'ledger.json');index=ledger.reserve('generation','case')
    with pytest.raises(BudgetStop):ledger.settle(index,{'prompt_token_count':1,'total_token_count':10000})
    assert json.loads(ledger.path.read_text())['attempts'][0]['usage']['total_token_count']==10000
