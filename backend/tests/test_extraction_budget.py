import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app import extraction
from test_api import chart


@pytest.mark.parametrize('tokens',[None,6145,100000])
def test_count_limit_prevents_generation(monkeypatch,tokens):
    run(monkeypatch,tokens,False)


def test_count_limit_accepts_boundary(monkeypatch):
    run(monkeypatch,6144,True)


def run(monkeypatch,tokens,allowed):
    monkeypatch.setenv('GEMINI_API_KEY','test-only');monkeypatch.setenv('GEMINI_MODEL','test-only')
    models=SimpleNamespace(count_tokens=AsyncMock(return_value=SimpleNamespace(total_tokens=tokens)),generate_content=AsyncMock(return_value=SimpleNamespace(text=chart().model_dump_json())))
    class Context:
        async def __aenter__(self):return SimpleNamespace(models=models)
        async def __aexit__(self,*args):pass
    monkeypatch.setattr(extraction.genai,'Client',lambda **kwargs:SimpleNamespace(aio=Context()))
    if allowed:
        assert asyncio.run(extraction.extract_chart(b'image'))==chart()
        models.generate_content.assert_awaited_once()
    else:
        with pytest.raises(ValueError):asyncio.run(extraction.extract_chart(b'image'))
        models.generate_content.assert_not_awaited()
