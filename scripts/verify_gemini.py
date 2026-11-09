"""Real, opt-in Gemini smoke test. Only synthetic fixtures are logged."""
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.extraction import extract_chart
from app.main import normalize_image


async def main():
    records = []
    for name,mime,expected in [('sample.png','image/png',[12,18]),('sample.jpg','image/jpeg',[12,18]),('uncertain.png','image/png',[12,None])]:
        path = ROOT / 'backend/tests/fixtures' / name
        image = path.read_bytes()
        record = {'timestamp': datetime.now(timezone.utc).isoformat(),
                  'model': os.environ.get('GEMINI_MODEL'), 'source': 'real-gemini-api',
                  'fixture': path.name, 'sha256': hashlib.sha256(image).hexdigest()}
        try:
            result = await extract_chart(normalize_image(image, mime))
            record['extraction'] = result.model_dump()
            assert result.supported and len(result.categories) == 2
            assert [c.value for c in result.categories] == expected
            # Title and unit are recorded, never replaced with expected data.
            record.update(success=True, schema_valid=True)
        except Exception as exc:
            # SDK errors can contain request data: log class/status only.
            record.update(success=False, error_type=type(exc).__name__, status_code=getattr(exc, 'code', None))
        records.append(record)
    target = ROOT / 'docs/verification/gemini-live.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(records, ensure_ascii=False, indent=2))
    if not all(record['success'] for record in records):
        raise SystemExit(1)


asyncio.run(main())
