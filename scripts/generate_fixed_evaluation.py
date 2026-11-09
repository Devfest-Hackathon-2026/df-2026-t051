"""Deterministic synthetic held-out set, not application development fixtures."""
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evaluation/fixed-v1'
FONT=Path(r'C:\Windows\Fonts\meiryo.ttc')
CASES=[
 ('E01','easy','Library visits',None,['Mon','Tue'],[7,23]),
 ('E02','easy','Plant height','cm',['Oak','Pine','Maple'],[14,9,21]),
 ('E03','easy','学年別の参加人数','人',['１年','２年','３年','４年'],[32,45,28,39]),
 ('E04','easy','読んだ本の数','冊',['あお','あか','きいろ','みどり','しろ'],[11,17,8,24,19]),
 ('E05','easy','月別の降水量','mm',['４月','５月','６月','７月','８月','９月'],[110,95,140,125,100,155]),
 ('E06','easy','Response rate','%',['Group A','Group B','Group C'],[25,50,75]),
 ('S07','standard','収穫した実の数','個',['東','西','南','北'],[0,8,0,15]),
 ('S08','standard','朝の気温','℃',['月曜','火曜','水曜','木曜','金曜'],[-3,5,-1,8,0]),
 ('S09','standard','Bag weight','kg',['Red','Blue','Green','White'],[1.5,2.75,0.5,3.25]),
 ('S10','standard','文房具の売上','円',['ノート','ペン','定規','はさみ','のり','消しゴム'],[1200,2500,1800,3200,2100,900]),
 ('S11','standard','Travel time','minutes',['A','B','C','D','E','F','G','H'],[18,22,15,31,27,14,29,24]),
 ('S12','standard','練習の得点','点',[str(i)+'回' for i in range(1,11)],[3,8,6,11,9,5,12,7,10,4]),
 ('S13','standard','クラブの参加人数','人',[chr(65+i)+'班' for i in range(12)],[7,11,5,13,9,16,8,12,6,15,10,14]),
 ('S14','standard','同じ値を含む記録',None,['記録Ａ','記録Ｂ','記録Ｃ','記録Ｄ'],[9,9,5,5]),
 ('H15','hard','Measured length','m',['Item A','Item B','Item C','Item D','Item E','Item F'],[2.4,2.6,2.5,2.7,2.3,2.8]),
 ('H16','hard','地域別の利用人数','人',['中央図書館','北地区図書館','南地区図書館','東地区図書館','西地区図書館','駅前図書館','大学図書館','分室図書館'],[21,18,26,32,24,19,28,30]),
 ('H17','hard','観察した鳥の数','羽',['すずめ','はと','からす','つばめ','めじろ'],[12,17,9,22,15]),
 ('H18','hard','Monthly attendance','people',['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'],[9,14,8,17,12,6,19,11,15,7,18,13]),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render(case,index):
    identifier,difficulty,title,unit,labels,values=case
    width,height=(1100,720) if identifier!='H15' else (850,600)
    image=Image.new('RGB',(width,height),'#ffffff' if identifier!='H17' else '#f3f3ee')
    draw=ImageDraw.Draw(image)
    def font(size):return ImageFont.truetype(str(FONT),size)
    titlefont=font(32);labelfont=font(20 if len(labels)>8 else 23);numberfont=font(24 if identifier!='H15' else 22)
    draw.text((width/2,30),title,font=titlefont,anchor='mt',fill='#17231e')
    if unit:draw.text((75,88),unit,font=font(25),fill='#17231e')
    top,bottom,left,right=145,height-135,90,width-35
    low=min(0,min(values));high=max(values)*1.22
    if low<0:low*=1.35
    def y(value):return bottom-(value-low)/(high-low)*(bottom-top)
    for tick in range(5):
        value=low+(high-low)*tick/4
        yy=y(value)
        draw.line((left,yy,right,yy),fill='#dce2dc',width=1)
        draw.text((left-12,yy),f'{value:g}',font=font(15),anchor='rm',fill='#4a554e')
    baseline=y(0)
    draw.line((left,top,left,bottom),fill='#303b33',width=2)
    draw.line((left,baseline,right,baseline),fill='#303b33',width=2)
    step=(right-left)/len(values);bar=step*.54
    for i,(label,value) in enumerate(zip(labels,values)):
        x=left+(i+.5)*step;yy=y(value)
        if value!=0:
            draw.rectangle((x-bar/2,min(yy,baseline),x+bar/2,max(yy,baseline)),fill='#adb7ab' if identifier=='H17' else '#306d5a',outline='#203f32')
        text=f'{value:,}' if identifier=='S10' else f'{value:g}'
        draw.text((x,yy-7 if value>=0 else yy+7),text,font=numberfont,anchor='mb' if value>=0 else 'mt',fill='#17231e')
        shown=label
        if identifier=='H16':shown=label[:-3]+'\n'+label[-3:]
        draw.multiline_text((x,bottom+20),shown,font=labelfont,anchor='ma',align='center',fill='#17231e',spacing=2)
    ext='jpg' if index%3==0 else 'png'
    path=OUT/f'{identifier}.{ext}'
    image.save(path,quality=72 if identifier=='H18' else 90) if ext=='jpg' else image.save(path)
    return {'id':identifier,'difficulty':difficulty,'image':path.name,'mime':'image/jpeg' if ext=='jpg' else 'image/png','sha256':sha(path),'size':[width,height],
            'expected':{'title':title,'unit':unit,'categories':[{'label':label,'value':value} for label,value in zip(labels,values)]}}


if (OUT/'manifest.json').exists():
    raise SystemExit('Fixed manifest exists; refusing to overwrite. Create a separately versioned set instead.')
OUT.mkdir(parents=True,exist_ok=True)
records=[render(case,i) for i,case in enumerate(CASES,1)]
manifest={'version':'fixed-v1','synthetic':True,'generation':'Pillow deterministic single-series vertical bars, every bar has a printed value; no random seed needed',
          'font':{'name':'Windows Meiryo (rendered only; font file not distributed)','sha256':sha(FONT)},
          'generator_sha256':sha(Path(__file__)),'cases':records}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Frozen {len(records)} images / {sum(len(r["expected"]["categories"]) for r in records)} values. Manifest SHA256: {sha(OUT/"manifest.json")}')
