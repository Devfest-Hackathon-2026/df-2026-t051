"""Reacquire original sources by frozen URLs/hashes; never overwrite the cache."""
import hashlib
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'evaluation/japanese-v3/source-provenance.json').read_text(encoding='utf-8'))
with httpx.Client(timeout=45) as client:
    for source in manifest['sources']:
        target=(ROOT/source['cache']).resolve()
        if not target.is_relative_to((ROOT/'.tmp/final-audit').resolve()):raise SystemExit('Unsafe cache path')
        if target.exists():data=target.read_bytes()
        else:
            response=client.get(source['url']);response.raise_for_status()
            data=response.text.encode('utf-8') if target.name=='wakayama-source.txt' else response.content
        if hashlib.sha256(data).hexdigest()!=source['sha256']:raise SystemExit('Publisher content changed; do not silently replace frozen evaluation: '+target.name)
        if not target.exists():
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as f:f.write(data)
print(f"Verified {len(manifest['sources'])} frozen source files; originals stay outside Git.")
