from unittest.mock import Mock
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import create_app


@pytest.mark.parametrize('claims,status', [
    ({'sub':'t','email':'teacher@example.test','email_verified':True},503),
    ({'sub':'s','email':'student@example.test','email_verified':True},403),
    ({'sub':'t','email':'teacher@example.test','email_verified':False},403),
])
def test_verified_iam_identity(monkeypatch, claims, status):
    monkeypatch.setenv('AUTH_MODE','google_iam')
    monkeypatch.setenv('IAM_TOKEN_AUDIENCE','expected-audience')
    monkeypatch.setenv('IAM_TEACHER_EMAILS','teacher@example.test')
    monkeypatch.delenv('GEMINI_API_KEY',raising=False)
    verify = Mock(return_value=claims)
    monkeypatch.setattr(auth.id_token,'verify_oauth2_token', verify)
    with TestClient(create_app(False)) as client:
        result = client.post('/api/analyze',headers={'X-ChartBridge-Identity':'full-token'},files={'file':('c.png',(Path(__file__).parent/'fixtures/sample.png').read_bytes(),'image/png')})
        assert result.status_code == status
        assert verify.call_args.kwargs['audience'] == 'expected-audience'


def test_iam_rejects_missing_and_invalid_token(monkeypatch):
    monkeypatch.setenv('AUTH_MODE','google_iam')
    monkeypatch.setenv('IAM_TOKEN_AUDIENCE','expected-audience')
    monkeypatch.setenv('IAM_TEACHER_EMAILS','teacher@example.test')
    monkeypatch.setattr(auth.id_token,'verify_oauth2_token',Mock(side_effect=ValueError('private')))
    with TestClient(create_app(False)) as client:
        for headers in ({},{'X-ChartBridge-Identity':'invalid'}):
            res=client.post('/api/analyze',headers=headers,files={'file':('a',b'bad','image/png')})
            assert res.status_code == 401
            assert 'private' not in res.text
