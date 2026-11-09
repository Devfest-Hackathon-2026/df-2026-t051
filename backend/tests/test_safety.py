import pytest
from app.models import Extraction
from app.safety import hold_compound_labels


@pytest.mark.parametrize('evidence',['6万4千','1億','1200万円','12千t'])
def test_compound_numeric_label_is_held_without_changing_raw_input(evidence):
    original=Extraction(supported=True,reason=None,title='桁の照合',unit='千t',categories=[{'label':'A','value':64000,'evidence':evidence},{'label':'B','value':4,'evidence':'4'}],warnings=[])
    held=hold_compound_labels(original)
    assert original.categories[0].value==64000
    assert held.categories[0].value is None
    assert held.categories[0].evidence==evidence
    assert held.categories[1].value==4
    assert '軸単位' in held.warnings[-1]
    Extraction.model_validate(held.model_dump())


def test_plain_labels_and_category_names_are_not_held():
    source=Extraction(supported=True,reason=None,title='値',unit='万t',categories=[{'label':'千葉','value':23,'evidence':'23'},{'label':'A','value':1200,'evidence':'1,200'}],warnings=[])
    assert hold_compound_labels(source)==source


def test_api_holds_place_value_without_promoting_or_publishing(monkeypatch):
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    from app import auth
    from app.main import create_app
    from test_api import image_bytes
    monkeypatch.setenv('GEMINI_API_KEY','test-only');monkeypatch.setenv('GEMINI_MODEL','test-only')
    monkeypatch.delenv('IMAGE_BUCKET',raising=False)
    raw=Extraction(supported=True,reason=None,title='単位照合',unit='千t',categories=[{'label':'A','value':64000,'evidence':'6万4千'},{'label':'B','value':4,'evidence':'4'}],warnings=[])
    app=create_app(False);app.dependency_overrides[auth.teacher]=lambda:'teacher';app.state.extractor=AsyncMock(return_value=raw)
    with TestClient(app) as client:
        response=client.post('/api/analyze',files={'file':('chart.png',image_bytes(),'image/png')})
        assert response.status_code==200
        assert response.json()['status']=='unreviewed'
        assert response.json()['extraction']['categories'][0]['value'] is None
        assert response.json()['extraction']['categories'][0]['evidence']=='6万4千'
        assert raw.categories[0].value==64000
