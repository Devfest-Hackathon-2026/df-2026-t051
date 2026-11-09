"""Mock transport only; bounded retry tests never contact Gemini."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from google.genai import types

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scripts'))
import run_large_evaluation as runner
from eval_core import Ledger,BudgetStop


class Limited(Exception):code=429
class Invalid(Exception):code=400


def setup(tmp_path,side_effect):
    client=SimpleNamespace(models=SimpleNamespace(generate_content=AsyncMock(side_effect=side_effect)))
    obj=runner.Runner(SimpleNamespace(name='mock'),Ledger(tmp_path/'ledger.json'),client)
    return obj,client.models.generate_content


def test_non429_errors_are_never_retried(tmp_path):
    obj,generate=setup(tmp_path,Invalid())
    with pytest.raises(Invalid):asyncio.run(obj.request('generation','case',[],types.GenerateContentConfig(max_output_tokens=4096)))
    assert generate.await_count==1 and obj.ledger.data['generation_attempts']==1
    assert obj.ledger.data['attempts'][0]['state']=='HTTP_400'


def test_budget_prevents_transport_call(tmp_path):
    obj,generate=setup(tmp_path,Invalid());obj.ledger.max_generation=0
    with pytest.raises(BudgetStop):asyncio.run(obj.request('generation','case',[],types.GenerateContentConfig(max_output_tokens=4096)))
    assert generate.await_count==0


def test_429_is_limited_to_three_total_attempts(tmp_path,monkeypatch):
    obj,generate=setup(tmp_path,Limited())
    # Advance the monotonic test clock on sleep; production uses actual waits.
    clock=[0.0]
    monkeypatch.setattr(runner.time,'monotonic',lambda:clock[0])
    async def advance(seconds):clock[0]+=seconds
    monkeypatch.setattr(runner.asyncio,'sleep',advance)
    with pytest.raises(Limited):asyncio.run(obj.request('generation','case',[],types.GenerateContentConfig(max_output_tokens=4096)))
    assert generate.await_count==3 and obj.ledger.data['generation_attempts']==3
    assert clock[0]>=60
    assert all(a['state']=='HTTP_429' for a in obj.ledger.data['attempts'])


def test_missing_usage_keeps_full_reservation(tmp_path):
    response=SimpleNamespace(usage_metadata=None)
    obj,generate=setup(tmp_path,[response])
    assert asyncio.run(obj.request('generation','case',[],types.GenerateContentConfig(max_output_tokens=4096))) is response
    assert obj.ledger.data['charged_or_reserved_usd']=='0.021504'


def test_secret_redaction_never_logs_real_key(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','local-test-secret')
    assert runner.safe_text('text local-test-secret')=='text [REDACTED]'


def test_count_endpoint_does_not_send_unsupported_generation_config(tmp_path):
    obj,_=setup(tmp_path,Invalid());count=AsyncMock(return_value=SimpleNamespace(total_tokens=100))
    obj.client.models.count_tokens=count
    result=asyncio.run(obj.request('count','case',[],types.GenerateContentConfig(max_output_tokens=4096)))
    assert result.total_tokens==100 and 'config' not in count.call_args.kwargs


def test_complete_baseline_case_pipeline_has_no_missing_normalizer(tmp_path):
    import json
    from eval_core import digest
    obj,_=setup(tmp_path,Invalid());obj.args.mode='baseline'
    result={'supported':True,'reason':None,'title':'sample','unit':'people','categories':[{'label':'A','value':12,'evidence':'12'},{'label':'B','value':18,'evidence':'18'}],'warnings':[]}
    response=SimpleNamespace(text=json.dumps(result),usage_metadata=None,candidates=[])
    obj.request=AsyncMock(side_effect=[SimpleNamespace(total_tokens=100),response])
    path='backend/tests/fixtures/sample.png'
    case={'id':'offline','cache':path,'image_sha256':digest(runner.ROOT/path),'gold':result}
    row=asyncio.run(obj.one(case,tmp_path))
    assert row.get('error_type') is None and row['score']['complete_match']
