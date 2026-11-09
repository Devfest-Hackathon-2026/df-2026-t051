import asyncio
import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.testclient import TestClient
from google.api_core.exceptions import ServiceUnavailable
from PIL import Image

from app import auth,materials
from app.main import create_app,normalize_image
from test_api import chart,image_bytes


def test_firebase_cold_start_is_safe_for_concurrent_requests(monkeypatch):
    import firebase_admin
    monkeypatch.setenv('FIREBASE_PROJECT_ID','chartbridge-test-only')
    auth.firebase_app.cache_clear()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            apps=list(pool.map(lambda _:auth.firebase_app(),range(24)))
        assert len({id(app) for app in apps})==1
        assert apps[0].project_id=='chartbridge-test-only'
    finally:
        try:firebase_admin.delete_app(firebase_admin.get_app('chartbridge'))
        except ValueError:pass
        auth.firebase_app.cache_clear()


def test_animated_png_is_not_a_static_chart():
    out=io.BytesIO()
    Image.new('RGB',(64,64),'white').save(out,format='PNG',save_all=True,append_images=[Image.new('RGB',(64,64),'black')])
    with pytest.raises(Exception) as error:
        normalize_image(out.getvalue(),'image/png')
    assert error.value.status_code==422


def test_decompression_bomb_is_rejected(monkeypatch):
    monkeypatch.setattr(Image,'MAX_IMAGE_PIXELS',100)
    with pytest.raises(Exception) as error:
        normalize_image(image_bytes(),'image/png')
    assert error.value.status_code==422


def test_provider_concurrency_limit_does_not_call_a_third_model(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','test-only')
    monkeypatch.setenv('GEMINI_MODEL','test-only')
    monkeypatch.delenv('IMAGE_BUCKET',raising=False)
    async def run():
        app=create_app(False);app.dependency_overrides[auth.teacher]=lambda:'teacher'
        entered=asyncio.Event();release=asyncio.Event();calls=0
        async def extract(data):
            nonlocal calls
            calls+=1
            if calls==2:entered.set()
            await release.wait()
            return chart()
        app.state.extractor=extract
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            def upload():return client.post('/api/analyze',files={'file':('test.png',image_bytes(),'image/png')})
            first=asyncio.create_task(upload());second=asyncio.create_task(upload())
            await asyncio.wait_for(entered.wait(),5)
            try:
                third=await upload();assert third.status_code==429
                assert calls==2
            finally:release.set()
            assert all(result.status_code==200 for result in await asyncio.gather(first,second))
    asyncio.run(run())


def test_storage_outage_has_accessible_non_disclosing_message():
    app=create_app(False);app.dependency_overrides[auth.teacher]=lambda:'teacher'
    class Store:
        def read(self,*args):raise ServiceUnavailable('internal private storage details')
    app.dependency_overrides[materials.repository]=lambda:Store()
    with TestClient(app) as client:
        result=client.get('/api/drafts/'+'a'*32)
        assert result.status_code==503
        assert 'detail' in result.json() and 'private' not in result.text
