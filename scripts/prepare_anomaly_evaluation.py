"""Freeze 15 real out-of-scope images; never mix these into numeric accuracy."""
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
import httpx

ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.tmp/large-eval';OUT=ROOT/'evaluation/real-v2/anomalies.json'


def main():
    if OUT.exists():raise SystemExit('Anomaly set already frozen')
    tree=json.loads((CACHE/'chartqa-tree.txt').read_text());revision=tree['sha']
    records=[]
    for i in (1,2,3,4,5,6,7):
        path=CACHE/f'japan-4_4_{i}.png'
        records.append({'id':f'JX{i:02d}','cache':str(path.relative_to(ROOT)).replace('\\','/'),'image_url':f'https://www.stat.go.jp/naruhodo/img/picture/4_4_{i}.png','source_group':'japan-statistics-bureau-graph-tutorial','source_page':'https://www.stat.go.jp/naruhodo/4_graph/shokyu/bou-graph.html','terms_url':'https://www.stat.go.jp/info/riyou.html','reason':{1:'More than 12 categories; no printed labels on every bar',2:'Stacked multiple series',3:'Bar and line combination with two axes',4:'Table, not chart',5:'Spreadsheet insertion dialog, not a labelled standalone chart',6:'Unlabelled bars in spreadsheet screenshot',7:'Multiple charts and editing UI'}[i],'attribution':'出典：総務省統計局「なるほど統計学園・棒グラフ」。原図・加工なし。PDL1.0、第三者権利の例外は維持。'})
    owid=['00339007006077','01001540004402','01499440003158','01729694006399','02534409005100']
    for name in owid:
        path=CACHE/(name+'.png')
        records.append({'id':'OX'+name,'cache':str(path.relative_to(ROOT)).replace('\\','/'),'image_url':f'https://raw.githubusercontent.com/vis-nlp/ChartQA/{revision}/ChartQA%20Dataset/test/png/{name}.png','source_group':'our-world-in-data-horizontal','source_page':'https://github.com/vis-nlp/ChartQA','terms_url':'https://ourworldindata.org/faqs','reason':'Horizontal bars, outside current vertical-bar scope','attribution':'Our World in Data and underlying providers printed in chart; CC BY as printed in archived chart, third-party data conditions remain. Archived by ChartQA authors.'})
    paths=[e['path'] for e in tree['tree'] if e['path'].startswith('ChartQA Dataset/test/png/OECD_') and any(k in e['path'] for k in ('AIR_AND_GHG_EMISSIONS','FDI_INCOME_PAYMENTS_BY_INDUSTRY','GROSS_DIRECT_INSURANCE_PREMIUMS'))]
    for i,p in enumerate(paths):
        path=CACHE/Path(p).name
        if not path.exists():
            r=httpx.get(f'https://raw.githubusercontent.com/vis-nlp/ChartQA/{revision}/'+quote(p),timeout=30);r.raise_for_status();path.write_bytes(r.content)
        records.append({'id':f'EX{i:02d}','cache':str(path.relative_to(ROOT)).replace('\\','/'),'image_url':f'https://raw.githubusercontent.com/vis-nlp/ChartQA/{revision}/'+quote(p),'source_group':'oecd-line-'+str(i),'source_page':'https://github.com/vis-nlp/ChartQA','terms_url':'https://www.oecd.org/en/about/terms-conditions.html','reason':'Multiple line series','attribution':'OECD, indicator/source printed in chart; ChartQA archive. No endorsement.'})
    assert len(records)==15
    for r in records:r.update(image_sha256=hashlib.sha256((ROOT/r['cache']).read_bytes()).hexdigest(),gold={'supported':False,'title':None,'unit':None,'categories':[]},split='anomaly',redistribute=False)
    with OUT.open('x',encoding='utf-8') as f:json.dump({'cases':records,'note':'15 distinct files, not 15 independent source documents; related tutorial screenshots are grouped. No numeric accuracy denominator.'},f,ensure_ascii=False,indent=2)
    print('Frozen 15 out-of-scope cases; originals remain ignored.')


if __name__=='__main__':main()
