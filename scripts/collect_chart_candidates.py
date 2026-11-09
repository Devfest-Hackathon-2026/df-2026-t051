"""Cache publisher charts/tables for human curation, never infer gold with an LLM.

ChartQA repository code is not imported. Its GPL declaration does not relicense
publisher images. All downloaded originals/tables remain in ignored .tmp.
"""
import concurrent.futures
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.parse import quote

import httpx
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / '.tmp/large-eval'
BASE = 'https://raw.githubusercontent.com/vis-nlp/ChartQA/'


def main():
    tree = json.loads((CACHE/'chartqa-tree.txt').read_text(encoding='utf-8'))
    # Pin the actual tree, not a moving branch, for every image/table pair.
    revision = tree['sha']
    sources = [e['path'] for e in tree['tree'] if '/tables/OECD_' in e['path'] and e['path'].endswith('.csv')]
    out = CACHE/'oecd';out.mkdir(parents=True,exist_ok=True)

    def fetch(path):
        dest=out/(path.split('/')[1]+'-'+Path(path).name)
        if not dest.exists():
            response=httpx.get(BASE+revision+'/'+quote(path),timeout=40)
            response.raise_for_status();dest.write_bytes(response.content)
        return dest

    def inspect(path):
        table=fetch(path)
        rows=list(csv.reader(io.StringIO(table.read_text(encoding='utf-8-sig'))))
        positive=len(rows)>2 and len(rows)<=13 and all(len(r)==2 for r in rows)
        # Only metadata/shape filtering. Humans must check vertical orientation,
        # numeric label coverage, units and CSV quality before acceptance.
        if not positive:return None
        png_path=path.replace('/tables/','/png/').removesuffix('.csv')+'.png'
        image=fetch(png_path)
        return {'source_group':'OECD','dataset_revision':revision,'table_url':BASE+revision+'/'+quote(path),'image_url':BASE+revision+'/'+quote(png_path),'table_cache':str(table.relative_to(ROOT)).replace('\\','/'),'cache':str(image.relative_to(ROOT)).replace('\\','/'),'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'table_sha256':hashlib.sha256(table.read_bytes()).hexdigest(),'header':rows[0],'rows':rows[1:],'review':'unreviewed','redistribute':False}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records=[r for r in pool.map(inspect,sources) if r is not None]
    (CACHE/'oecd-candidates.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    for start in range(0,len(records),12):
        sheet=Image.new('RGB',(1600,4*320),'white');draw=ImageDraw.Draw(sheet)
        for i,r in enumerate(records[start:start+12]):
            image=Image.open(ROOT/r['cache']).convert('RGB');image.thumbnail((520,280))
            x=i%3*533;y=i//3*320;sheet.paste(image,(x,y+32));draw.text((x+4,y+4),f"{start+i:03d} {r['header'][1][:53]}",fill='black')
        sheet.save(CACHE/f'oecd-sheet-{start:03d}.png')
    print(json.dumps({'cached_candidates':len(records),'revision':revision,'originals_public_commit':False}))


if __name__=='__main__':main()
