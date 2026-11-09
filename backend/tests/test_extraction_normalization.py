import pytest
from app.models import Extraction
from app.safety import normalize_extraction
from app.extraction import generation_config,parse_extraction_response
from pydantic import ValidationError


def sample(evidence,value,unit):
    return Extraction(supported=True,reason=None,title='Unit review',unit=unit,categories=[{'label':'A','value':value,'evidence':evidence},{'label':'B','value':None,'evidence':None}],warnings=[])


@pytest.mark.parametrize('evidence,value,unit,expected',[
 ('6万4千t',64000,'千t',64),('6万4千t',64,'千t',64),
 ('六万四千',64000,'t',64000),('6万4千',64000,'千t',None),
 ('12',13,'人',None),('12人',13,'人',None),('64000kg',99,'t',None),
 ('約12',12,'人',None),('12人',12,'円',None),('12%',12,'% of GDP',12),
 ('12%',12,'Percentage of GDP',12),('12%',12,'Annual growth rate (%)',12),
 ('12%',12,'Percentage points',None),('0',0,None,0),('-2.5',-2.5,'Ratio',-2.5),
])
def test_only_consistent_unambiguous_values_are_retained(evidence,value,unit,expected):
    original=sample(evidence,value,unit);result=normalize_extraction(original)
    assert result.categories[0].value==expected
    assert result.categories[1].value is None
    assert original.categories[0].value==value
    assert result.unit==unit


def test_normalizer_never_promotes_model_unknown_from_evidence():
    assert normalize_extraction(sample('12',None,'人')).categories[0].value is None


def test_normalization_is_idempotent_and_caps_warning_list():
    original=sample('6万4千',64000,'千t');original.warnings=['existing']*12
    result=normalize_extraction(original)
    assert normalize_extraction(result)==result and len(result.warnings)==12


def test_generation_config_bounds_reasoning_and_response_budget():
    config=generation_config()
    assert config.max_output_tokens==8192
    assert str(config.thinking_config.thinking_level).endswith('LOW')
    assert config.response_json_schema==Extraction.model_json_schema()


def test_malformed_or_truncated_json_is_never_repaired_into_a_value():
    with pytest.raises(ValidationError):parse_extraction_response('{"supported": true, "categories": [')


def test_api_applies_unit_validation_before_saving_an_image(monkeypatch):
    from unittest.mock import AsyncMock
    from fastapi.testclient import TestClient
    from app import auth
    from app.main import create_app
    from test_api import image_bytes
    monkeypatch.setenv('GEMINI_API_KEY','test-only');monkeypatch.setenv('GEMINI_MODEL','test-only');monkeypatch.delenv('IMAGE_BUCKET',raising=False)
    app=create_app(False);app.dependency_overrides[auth.teacher]=lambda:'teacher'
    app.state.extractor=AsyncMock(return_value=sample('12人',12,'円'))
    with TestClient(app) as client:
        response=client.post('/api/analyze',files={'file':('chart.png',image_bytes(),'image/png')})
        assert response.status_code==200 and response.json()['status']=='unreviewed'
        assert response.json()['extraction']['categories'][0]['value'] is None
        assert response.json()['extraction']['categories'][0]['evidence']=='12人'
