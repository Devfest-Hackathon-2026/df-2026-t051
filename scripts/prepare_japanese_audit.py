"""Freeze native Japanese chart crops and independently tabulated gold.

Only crops of the publisher's PDF are used, never redrawn charts. Originals stay
in the ignored cache. xlrd 2.0.2 (BSD) is evaluation-only, not a server dependency.
"""
import hashlib
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from decimal import Decimal,ROUND_HALF_UP
from pathlib import Path
import xlrd

ROOT=Path(__file__).resolve().parents[1];CACHE=ROOT/'.tmp/final-audit';OUT=ROOT/'evaluation/japanese-v3'
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
PDF='https://www.maff.go.jp/j/kids/kodomo_kasumi/2024/content/pdf/jiten_2024.pdf'
TABLE='https://www.maff.go.jp/j/kids/kodomo_kasumi/2024/content/xls/oyaku_data.xlsx'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):
    text=json.dumps(value,ensure_ascii=False,indent=2)
    if path.exists():assert path.read_text(encoding='utf-8')==text,'Frozen record changed'
    else:path.write_text(text,encoding='utf-8')
def rounded(value,scale):return int((Decimal(str(value))/scale).quantize(Decimal(1),rounding=ROUND_HALF_UP))

def xlsx_rows(number):
    with zipfile.ZipFile(CACHE/'maff2024-data.xlsx') as z:
        strings=[''.join(t.text or '' for t in list(si.findall('m:t',NS))+list(si.findall('m:r/m:t',NS))) for si in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        rows=[]
        for row in ET.fromstring(z.read(f'xl/worksheets/sheet{number}.xml')).findall('.//m:row',NS):
            values={re.sub(r'\d+','',c.attrib['r']):strings[int(c.findtext('m:v',default='0',namespaces=NS))] if c.attrib.get('t')=='s' else c.findtext('m:v',default='',namespaces=NS) for c in row.findall('m:c',NS)}
            rows.append((row.attrib['r'],values))
        return rows

def crop(page,box,name):
    path=CACHE/'jp-crops'/f'{name}-v2.png';path.parent.mkdir(exist_ok=True)
    if not path.exists():subprocess.run(['pdftoppm','-f',str(page),'-l',str(page),'-r','150','-x',str(box[0]),'-y',str(box[1]),'-W',str(box[2]),'-H',str(box[3]),'-singlefile','-png',str(CACHE/'maff-jiten2024.pdf'),str(path.with_suffix(''))],check=True,capture_output=True)
    return path

def make_case(name,path,title,unit,labels,values,evidence):
    assert 2<=len(values)<=12 and len(labels)==len(values)
    return {'id':name,'source_group':'maff-jiten-2024','source_url':PDF,'gold_source_url':TABLE,'cache':path.relative_to(ROOT).as_posix(),'image_sha256':sha(path),'gold_evidence':evidence,'gold':{'supported':True,'title':title,'unit':unit,'categories':[{'label':k,'value':v} for k,v in zip(labels,values)]}}

def main():
    OUT.mkdir(parents=True,exist_ok=True);cases=[]
    # All chart years are printed; year labels are transcribed before inference.
    years=[2000,2005,2010,2015,2017,2018,2019,2020,2021,2022]
    labels=['平成12年','17','22','27','29','30','令和元','2','3','4']
    historical=[(6,'だいこん','000040470474'),(7,'キャベツ','000040470534'),(8,'ピーマン','000040470594'),(9,'トマト','000040470594'),(10,'なす','000040470594'),(11,'にんじん','000040470474'),(12,'じゃがいも','000040470474'),(13,'みかん','000040421665'),(14,'りんご','000040421905')]
    for page,name,table in historical:
        file=CACHE/('estat-yasai-national.xlsx' if table=='000040470474' else f'estat-{table}.xls');sheet=xlrd.open_workbook(file).sheet_by_index(0)
        lookup='ばれいしょ' if name=='じゃがいも' else name
        col=sheet.row_values(4).index(lookup)+1
        assert sheet.cell_value(5,col)=='収穫量' and sheet.cell_value(6,col)=='t'
        data={int(m[1]):(i,sheet.cell_value(i,col)) for i in range(7,sheet.nrows) if (m:=re.search(r'\((\d{4})\)',str(sheet.cell_value(i,0))))}
        values=[rounded(data[y][1],10000) for y in years]
        nameid=f'JP-H{page:02}';path=crop(page,(38,970,640,430),nameid)
        # Different page types move the graph vertically; final boxes are visually
        # reviewed and recorded in the manifest before any model request.
        evidence={'table_url':f'https://www.e-stat.go.jp/stat-search/file-download?statInfId={table}&fileKind=0','table_sha256':sha(file),'column_zero_based':col,'rows_zero_based':[data[y][0] for y in years],'raw_tonnes':[data[y][1] for y in years],'rounding':'tonnes / 10000, integer ROUND_HALF_UP'}
        cases.append(make_case(nameid,path,name+'のとれた量','万t',labels,values,evidence))
    # Eleven previously unused small charts, excluding the original six cases.
    specifications=[(0,5,'だいこん','万t'),(1,6,'キャベツ','万t'),(2,7,'ピーマン','千t'),(3,8,'トマト','万t'),(4,9,'なす','千t'),(5,10,'にんじん','万t'),(6,11,'じゃがいも','万t'),(7,12,'はくさい','万t'),(8,13,'きゅうり','千t'),(10,15,'ねぎ','千t'),(11,16,'ほうれんそう','千t')]
    for index,number,name,unit in specifications:
        rows=[]
        for row,d in xlsx_rows(number):
            if re.fullmatch(r'\d+',d.get('A','')) and d.get('B') and d.get('E','').isdigit():rows.append((d['B'],Decimal(d['E']),row))
        top=sorted(rows,key=lambda r:r[1],reverse=True)[:5];scale=1000 if unit=='千t' else 10000
        labels2=[r[0] if r[0]=='北海道' else re.sub(r'[都府県]$','',r[0]) for r in top];values=[rounded(r[1],scale) for r in top]
        nameid=f'JP-P{index:02}';path=crop(16,(88+(index%4)*267,200+(index//4)*222,267,222),nameid)
        cases.append(make_case(nameid,path,name+'生産量',unit,labels2,values,{'sheet_number':number,'cells':['E'+r[2] for r in top],'raw_tonnes':[str(r[1]) for r in top],'rounding':f'tonnes / {scale}, integer ROUND_HALF_UP'}))
    write(OUT/'development.json',{'cases':cases})
    print(json.dumps({'development':len(cases),'cells':sum(len(c['gold']['categories']) for c in cases),'values':{c['id']:[p['value'] for p in c['gold']['categories']] for c in cases}},ensure_ascii=False))

if __name__=='__main__':main()
