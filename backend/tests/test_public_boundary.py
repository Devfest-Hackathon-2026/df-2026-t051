from unittest.mock import Mock,AsyncMock
import pytest
from fastapi.testclient import TestClient
from app import materials
from app.main import create_app


@pytest.mark.parametrize('method,path',[
 ('GET','/api/me'),('GET','/api/drafts'),('POST','/api/drafts'),
 ('GET','/api/drafts/'+'a'*32),('PUT','/api/drafts/'+'a'*32),
 ('POST','/api/drafts/'+'a'*32+'/approve'),('GET','/api/drafts/'+'a'*32+'/approved'),
 ('GET','/api/images/'+'a'*32),('POST','/api/analyze'),
])
def test_unauthenticated_writes_and_private_reads_never_touch_storage(monkeypatch,method,path):
    monkeypatch.setenv('AUTH_MODE','firebase');monkeypatch.setenv('APP_ENV','production')
    app=create_app(False);store=Mock();app.dependency_overrides[materials.repository]=lambda:store;app.state.extractor=AsyncMock()
    with TestClient(app) as client:
        response=client.request(method,path,json={})
        assert response.status_code==401
        assert response.headers['X-Content-Type-Options']=='nosniff'
        assert response.headers['Cache-Control']=='no-store'
    assert not store.mock_calls;app.state.extractor.assert_not_awaited()


@pytest.mark.parametrize('method',['POST','PUT','PATCH','DELETE'])
def test_public_snapshot_has_no_write_methods(method):
    app=create_app(False);store=Mock();app.dependency_overrides[materials.repository]=lambda:store
    with TestClient(app) as client:assert client.request(method,'/api/materials/'+'a'*32,json={}).status_code in (404,405)
    assert not store.mock_calls


def test_public_flag_requires_firebase(monkeypatch):
    monkeypatch.setenv('PUBLIC_ACCESS','true');monkeypatch.setenv('AUTH_MODE','google_iam')
    with pytest.raises(RuntimeError):
        with TestClient(create_app(False)):pass


def test_config_returns_only_intended_public_settings(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','private-model-secret');monkeypatch.setenv('PUBLIC_ACCESS','true');monkeypatch.setenv('AUTH_MODE','firebase')
    with TestClient(create_app(False)) as client:
        data=client.get('/api/config').json()
        assert set(data)=={'demo','authMode','persistence','firebase','serviceBaseUrl','publicAccess'}
        assert data['publicAccess'] is True and 'private-model-secret' not in str(data)
