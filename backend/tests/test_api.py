import io
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from app import auth, extraction
from app.main import MAX_BODY, create_app, normalize_image
from app.models import Extraction


def image_bytes(fmt="PNG", size=(100, 100)):
    out = io.BytesIO()
    Image.new("RGB", size, "white").save(out, format=fmt)
    return out.getvalue()


def chart(**kwargs):
    return Extraction(supported=True, reason=None, title="Sample", unit=None,
                      categories=[{"label": "A", "value": 1, "evidence": "1"},
                                  {"label": "B", "value": None, "evidence": None}], warnings=[], **kwargs)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "local")
    with TestClient(create_app(demo=True)) as c:
        yield c


def upload(client, data=None, mime="image/png"):
    return client.post("/api/analyze", files={"file": ("chart.png", image_bytes() if data is None else data, mime)})


def test_demo_has_null_and_no_publication(client):
    res = upload(client)
    assert res.status_code == 200
    assert res.json()["status"] == "unreviewed"
    assert res.json()["source"] == "demo"
    assert res.json()["extraction"]["categories"][1]["value"] is None
    assert client.get("/api/published/123").status_code == 404
    assert client.post("/api/publish").status_code == 404
    assert res.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("data,mime,status", [(b"bad", "image/png", 422), (b"bad", "text/html", 415),
    (image_bytes("JPEG"), "image/png", 422), (image_bytes(size=(10, 10)), "image/png", 422),
    (b"x" * (5*1024*1024+1), "image/png", 413)])
def test_invalid_files(client, data, mime, status):
    assert upload(client, data, mime).status_code == status


def test_stream_limit(client):
    res = client.post("/api/analyze", content=b"x"*(MAX_BODY+1), headers={"Content-Type":"multipart/form-data; boundary=abc"})
    assert res.status_code == 413


def test_auth_required():
    with TestClient(create_app(demo=False)) as c:
        assert upload(c).status_code == 401


@pytest.mark.parametrize("claims,status", [({"uid":"student"},403), ({"uid":"teacher","teacher":True},200)])
def test_teacher_claim(monkeypatch, claims, status):
    monkeypatch.setattr(auth, "firebase_app", lambda: object())
    monkeypatch.setattr(auth.auth, "verify_id_token", lambda *a, **kw: claims)
    monkeypatch.setenv("GEMINI_API_KEY", "test-not-a-real-key")
    monkeypatch.setenv("GEMINI_MODEL", "test-model")
    app = create_app(demo=False)
    app.state.extractor = AsyncMock(return_value=chart())
    with TestClient(app) as c:
        res = c.post("/api/analyze", headers={"Authorization":"Bearer test"}, files={"file":("c.png",image_bytes(),"image/png")})
        assert res.status_code == status
        assert app.state.extractor.await_count == (1 if status == 200 else 0)
        if status == 200:
            assert res.json()["status"] == "unreviewed"
            assert res.json()["extraction"]["categories"][1]["value"] is None


def test_invalid_token(monkeypatch):
    monkeypatch.setattr(auth, "firebase_app", lambda: object())
    monkeypatch.setattr(auth.auth, "verify_id_token", Mock(side_effect=ValueError("private error")))
    with TestClient(create_app(False)) as c:
        res = c.post("/api/analyze", headers={"Authorization":"Bearer invalid"}, files={"file":("a",image_bytes(),"image/png")})
        assert res.status_code == 401
        assert "private error" not in res.text


@pytest.mark.parametrize("exception,status", [(TimeoutError(),504),(ValueError("secret"),502),(RuntimeError("secret"),502)])
def test_provider_errors(monkeypatch, exception, status):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setenv("GEMINI_MODEL", "test-only")
    app = create_app(False)
    app.dependency_overrides[auth.teacher] = lambda: "teacher"
    app.state.extractor = AsyncMock(side_effect=exception)
    with TestClient(app) as c:
        res = upload(c)
        assert res.status_code == status
        assert "secret" not in res.text


def test_missing_configuration(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    app = create_app(False)
    app.dependency_overrides[auth.teacher] = lambda: "teacher"
    with TestClient(app) as c:
        assert upload(c).status_code == 503


def test_reject_unsupported(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setenv("GEMINI_MODEL", "test-only")
    app = create_app(False)
    app.dependency_overrides[auth.teacher] = lambda: "teacher"
    app.state.extractor = AsyncMock(return_value=Extraction(supported=False, reason="line", title=None, unit=None, categories=[], warnings=[]))
    with TestClient(app) as c:
        assert upload(c).status_code == 422


@pytest.mark.parametrize("environment", [{"APP_ENV":"production"}, {"APP_ENV":"local","K_SERVICE":"cloud-run"}])
def test_demo_forbidden_outside_local(monkeypatch, environment):
    for k,v in environment.items():
        monkeypatch.setenv(k,v)
    with pytest.raises(RuntimeError):
        with TestClient(create_app(True)):
            pass


def test_schema_rejects_hallucination_and_nonfinite():
    for value,evidence in [(1,None), (float('nan'),"NaN"), (float('inf'),"inf"), (True,"1"), ("1","1"), ("abc","abc")]:
        data = chart().model_dump()
        data["categories"][0].update(value=value,evidence=evidence)
        with pytest.raises(ValidationError):
            Extraction.model_validate(data)
    data = chart().model_dump()
    data["categories"] = data["categories"][:1]
    with pytest.raises(ValidationError):
        Extraction.model_validate(data)


def test_metadata_stripped():
    data = normalize_image(image_bytes("JPEG"), "image/jpeg")
    with Image.open(io.BytesIO(data)) as img:
        assert img.format == "PNG"
        assert not img.info


def test_camera_orientation_and_transparency_are_preserved_visually():
    output=io.BytesIO()
    original=Image.new('RGB',(120,80),'white')
    exif=Image.Exif();exif[274]=6
    original.save(output,format='JPEG',exif=exif)
    with Image.open(io.BytesIO(normalize_image(output.getvalue(),'image/jpeg'))) as image:
        assert image.size==(80,120)
        assert not image.info
    output=io.BytesIO()
    Image.new('RGBA',(64,64),(0,0,0,0)).save(output,format='PNG')
    with Image.open(io.BytesIO(normalize_image(output.getvalue(),'image/png'))) as image:
        assert image.getpixel((0,0))==(255,255,255)


@pytest.mark.parametrize('error',[auth.auth.ExpiredIdTokenError('expired',None),auth.auth.RevokedIdTokenError('revoked')])
def test_expired_and_revoked_tokens_fail_closed(monkeypatch,error):
    monkeypatch.setattr(auth,'firebase_app',lambda:object())
    verify=Mock(side_effect=error)
    monkeypatch.setattr(auth.auth,'verify_id_token',verify)
    with TestClient(create_app(False)) as c:
        response=c.get('/api/me',headers={'Authorization':'Bearer expired-or-revoked'})
        assert response.status_code==401
        assert verify.call_args.kwargs['check_revoked'] is True


def test_sdk_contract(monkeypatch):
    """Exercise actual adapter with a fake transport client, not a real model call."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-only")
    monkeypatch.setenv("GEMINI_MODEL", "configured-model")
    client = Mock()
    client.models.count_tokens = AsyncMock(return_value=Mock(total_tokens=512))
    client.models.generate_content = AsyncMock(return_value=Mock(text=chart().model_dump_json()))
    manager = Mock()
    manager.__aenter__ = AsyncMock(return_value=client)
    manager.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(extraction.genai, "Client", Mock(return_value=Mock(aio=manager)))
    import asyncio
    result = asyncio.run(extraction.extract_chart(image_bytes()))
    assert result.categories[1].value is None
    args = client.models.generate_content.call_args.kwargs
    assert args["model"] == "configured-model"
    assert args["config"].response_json_schema == Extraction.model_json_schema()
