from copy import deepcopy
from datetime import datetime,timezone,timedelta
from threading import RLock
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock,AsyncMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app import auth,materials,limits
from app.main import create_app
from app.materials import Snapshot
from test_api import image_bytes,chart


class DB:
    def __init__(self):self.docs={};self.lock=RLock()
    def collection(self,name):
        db=self
        class Collection:
            def document(self,key):
                class Ref:
                    def get(self,transaction=None):
                        data=deepcopy(db.docs.get((name,key)))
                        class Value:
                            exists=data is not None
                            def to_dict(self):return data
                        return Value()
                ref=Ref();ref.key=(name,key);return ref
        return Collection()
    def transaction(self):
        db=self
        class Tx:
            def __init__(self):self.pending=[];self.lock=db.lock
            def set(self,ref,value):self.pending.append((ref.key,value))
            def commit(self):
                for key,value in self.pending:db.docs[key]=deepcopy(value)
        return Tx()


@pytest.fixture
def quota(monkeypatch):
    def transactional(fn):
        def run(tx):
            with tx.lock:
                result=fn(tx);tx.commit();return result
        return run
    monkeypatch.setattr(limits.firestore,'transactional',transactional)
    return limits.UsageQuotas(DB())


def test_same_teacher_minute_limit_reserves_exactly_two(quota):
    now=datetime(2026,11,6,1,tzinfo=timezone.utc)
    quota.reserve('teacher','analysis',now);quota.reserve('teacher','analysis',now)
    with pytest.raises(HTTPException) as error:quota.reserve('teacher','analysis',now)
    assert error.value.status_code==429 and error.value.headers['Retry-After']=='60'
    assert len(quota.client.docs)==2


def test_concurrent_reservations_do_not_exceed_teacher_cap(quota):
    now=datetime(2026,11,6,1,tzinfo=timezone.utc)
    def take(_):
        try:quota.reserve('teacher','analysis',now);return True
        except HTTPException:return False
    with ThreadPoolExecutor(max_workers=8) as pool:assert sum(pool.map(take,range(20)))==2


def test_daily_limit_survives_new_quota_object(quota):
    now=datetime(2026,11,6,1,tzinfo=timezone.utc)
    for i in range(10):quota.reserve('teacher','analysis',now+timedelta(minutes=i))
    again=limits.UsageQuotas(quota.client)
    with pytest.raises(HTTPException):again.reserve('teacher','analysis',now+timedelta(minutes=20))


def test_global_daily_limit_across_different_teachers(quota):
    now=datetime(2026,11,6,1,tzinfo=timezone.utc)
    for i in range(30):quota.reserve('teacher-'+str(i),'analysis',now)
    with pytest.raises(HTTPException):quota.reserve('another','analysis',now)


def test_day_resets_at_japan_midnight_not_utc_midnight(quota):
    now=datetime(2026,11,6,14,59,tzinfo=timezone.utc)
    quota.reserve('teacher','analysis',now);quota.reserve('teacher','analysis',now)
    quota.reserve('teacher','analysis',now+timedelta(minutes=1))
    global_days={value['day'] for key,value in quota.client.docs.items() if 'global' in key[1]}
    assert global_days=={'2026-11-06','2026-11-07'}


def test_write_budget_is_separate_from_analysis_budget(quota,monkeypatch):
    monkeypatch.setenv('WRITE_PER_MINUTE','1');now=datetime.now(timezone.utc)
    quota.reserve('teacher','write',now)
    with pytest.raises(HTTPException):quota.reserve('teacher','write',now)
    quota.reserve('teacher','analysis',now)


def test_window_expiration_and_concurrency():
    clock=[0.];window=limits.RequestWindow(2,clock=lambda:clock[0])
    assert window.take() and window.take() and not window.take()
    clock[0]=60;assert window.take()


def test_snapshot_cache_is_bounded_and_does_not_share_mutable_values():
    clock=[0.];cache=limits.SnapshotCache(maximum=1,clock=lambda:clock[0])
    data={'title':'checked','unit':None,'categories':[{'label':'A','value':1},{'label':'B','value':None}]}
    one=Snapshot(id='a'*32,status='approved',approved_at='now',data=data)
    cache.put(one.id,one);got=cache.get(one.id);got.data.title='mutated'
    assert cache.get(one.id).data.title=='checked'
    two=one.model_copy(update={'id':'b'*32});cache.put(two.id,two)
    assert cache.get(one.id) is None
    clock[0]=61;assert cache.get(two.id) is None


def test_production_quota_unavailable_blocks_gemini_without_call(monkeypatch):
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('FIRESTORE_PROJECT_ID','test-only');monkeypatch.setenv('GEMINI_API_KEY','test-only');monkeypatch.setenv('GEMINI_MODEL','test-only')
    app=create_app(False);app.dependency_overrides[auth.teacher]=lambda:'teacher'
    app.state.usage_quotas=Mock();app.state.usage_quotas.reserve.side_effect=RuntimeError('private backend details')
    app.state.extractor=AsyncMock(return_value=chart())
    with TestClient(app) as client:
        response=client.post('/api/analyze',files={'file':('a.png',image_bytes(),'image/png')})
        assert response.status_code==503 and 'private backend' not in response.text
        app.state.extractor.assert_not_awaited()


def test_production_quota_limit_is_429_not_model_error(monkeypatch):
    monkeypatch.setenv('APP_ENV','production');monkeypatch.setenv('FIRESTORE_PROJECT_ID','test-only');monkeypatch.setenv('GEMINI_API_KEY','test-only');monkeypatch.setenv('GEMINI_MODEL','test-only')
    app=create_app(False);app.dependency_overrides[auth.teacher]=lambda:'teacher'
    app.state.usage_quotas=Mock();app.state.usage_quotas.reserve.side_effect=HTTPException(429,'limit',headers={'Retry-After':'10'})
    app.state.extractor=AsyncMock()
    with TestClient(app) as client:
        response=client.post('/api/analyze',files={'file':('a.png',image_bytes(),'image/png')})
        assert response.status_code==429 and response.headers['Retry-After']=='10'
        app.state.extractor.assert_not_awaited()


def test_public_materials_only_cache_approved_payload_and_throttle(monkeypatch):
    monkeypatch.setenv('PUBLIC_READ_PER_MINUTE','2');app=create_app(False)
    payload=Snapshot(id='a'*32,status='approved',approved_at='now',data={'title':'checked','unit':None,'categories':[{'label':'A','value':1},{'label':'B','value':None}]})
    store=Mock();store.public.return_value=payload;app.dependency_overrides[materials.repository]=lambda:store
    with TestClient(app) as client:
        for _ in range(2):
            response=client.get('/api/materials/'+'a'*32);assert response.status_code==200
            assert set(response.json())=={'id','status','approved_at','data'}
        assert store.public.call_count==1
        assert client.get('/api/materials/'+'a'*32).status_code==429


def test_failed_public_lookup_never_populates_cache():
    app=create_app(False);store=Mock();store.public.side_effect=HTTPException(404,'not approved');app.dependency_overrides[materials.repository]=lambda:store
    with TestClient(app) as client:
        for _ in range(2):assert client.get('/api/materials/'+'a'*32).status_code==404
    assert store.public.call_count==2 and app.state.snapshot_cache.get('a'*32) is None


@pytest.mark.parametrize('path',['/docs','/redoc','/openapi.json'])
def test_production_does_not_expose_api_documentation(monkeypatch,path):
    monkeypatch.setenv('APP_ENV','production')
    with TestClient(create_app(False)) as client:assert client.get(path).status_code==404


@pytest.mark.parametrize('name,value',[('ANALYSIS_GLOBAL_DAY','0'),('ANALYSIS_PER_MINUTE','invalid'),('ANALYSIS_PER_TEACHER_DAY','10000')])
def test_invalid_quota_config_fails_closed(monkeypatch,name,value):
    monkeypatch.setenv(name,value)
    with pytest.raises(RuntimeError):
        with TestClient(create_app(False)):pass
