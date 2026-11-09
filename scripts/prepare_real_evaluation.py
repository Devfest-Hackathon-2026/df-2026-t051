"""Fetch published MAFF educational charts without redrawing them."""
import hashlib
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evaluation/real-v1'
CACHE=ROOT/'.tmp/real-materials'
PAGE='https://www.maff.go.jp/j/kids/kodomo_kasumi/2024/content/toukei.html'
TERMS='https://www.maff.go.jp/j/use/link.html'
CASES=[
 ('R01',12,'こめの生産量上位5都道府県','万t',['新潟','北海道','秋田','山形','宮城'],[59,54,46,36,34],False),
 ('R02',39,'うめの生産量上位5都道府県','千t',['和歌山','群馬','山梨','三重','福井'],[64,4,2,2,1],True),
 ('R03',40,'ミニトマトの生産量上位5都道府県','千t',['熊本','愛知','北海道','宮崎','茨城'],[41,16,15,9,8],True),
 ('R04',15,'レタスの生産量上位5都道府県','万t',['長野','茨城','群馬','長崎','静岡'],[18,9,6,4,3],False),
 ('R05',41,'ブロッコリーの生産量上位5都道府県','千t',['北海道','埼玉','愛知','香川','徳島'],[28,16,15,13,12],True),
 ('R06',16,'たまごの生産量上位5都道府県','万t',['茨城','鹿児島','広島','岡山','千葉'],[23,18,14,13,13],False),
]
CACHE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
records=[]
for identifier,number,title,unit,labels,values,compound in CASES:
    url=f'https://www.maff.go.jp/j/kids/kodomo_kasumi/2024/content/attach/img/toukei-{number}.png'
    path=CACHE/f'maff-{number}.png'
    if not path.exists():
        response=httpx.get(url,timeout=30);response.raise_for_status();path.write_bytes(response.content)
    records.append({'id':identifier,'source_page':PAGE,'image_url':url,'cache':str(path.relative_to(ROOT)).replace('\\','/'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'rights_url':TERMS,'attribution':'出典：農林水産省「統計データを使いこなして自由研究を攻略しよう！」2024掲載版。原図・加工なし。',
                    'mvp_structure':True,'mixed_japanese_number_notation':compound,'expected':{'title':title,'unit':unit,'categories':[{'label':label,'value':value} for label,value in zip(labels,values)]}})
manifest={'version':'real-v1','retrieved_at':'2026-11-06','publisher':'農林水産省','source_type':'published educational charts, not ChartBridge-generated',
          'license':'PDL1.0 default content policy; third-party rights exceptions remain applicable. Original images are not redistributed in this repository.',
          'terms_url':TERMS,'cases':records,
          'screened_out':[{'source':'https://www.stat.go.jp/data/nihon/pdf/26nihon.pdf','figure':'図12 海外経済協力','reason':'単系列縦棒だが全数値ラベルがなく、対応条件外。精度分母に含めない。'},
                          {'source':'https://www.pref.niigata.lg.jp/uploaded/attachment/441964.pdf','figure':'品目別ランキング冒頭図','reason':'全棒ではなく一部のみ数値ラベル。対応条件外。精度分母に含めない。'}]}
target=OUT/'manifest.json'
if target.exists():
    assert json.loads(target.read_text(encoding='utf-8'))==manifest,'Frozen real set changed'
else:target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('Six original published charts verified; 30 cells. SHA256 manifest:',hashlib.sha256(target.read_bytes()).hexdigest())
