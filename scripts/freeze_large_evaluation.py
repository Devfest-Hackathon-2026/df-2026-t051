"""Curated source-family split. Gold is read from published CSV, never Gemini.

Run before any model improvements. Originals stay local; holdout gold is sealed
in .tmp and its SHA256 is committed. No regeneration/overwrite is permitted.
"""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'evaluation/real-v2'
CACHE=ROOT/'.tmp/large-eval'
HELD={4,10,21,24,25,26,29,48,68,69,78,93,118,120,14,34,72,80,84,86,92,98,109,123,124}
EXCLUDED={1,7,20,32,35,38,40,43,44,46,47,49,51,61,83,85,95,100,107,110,112,114,115,116,117,122,125,12,70}
UNITS={0:'% of median disposable income',2:'% of previous in-work income',3:'Square metres per capita',4:'Per 100 000 persons',5:'% of earnings',6:'% of foreign-born labour force',8:'Multiple of annual gross earnings',9:'2015=100',10:'Deaths/1 000 live births',11:'Percentage',13:'Ratio',14:'Years',15:'% of GDP',16:'% of GDP',17:'Annual growth rate (%)',18:'Percentage',19:'Percentage',21:'Litres/capita',22:'Percentage',23:'Percentage',24:'% of children',25:'Per 1 000 inhabitants',26:'Per 1 000 000 inhabitants',27:'Tonnes/hectare',28:'Percentage',29:'Per 1 000 inhabitants',30:'Annual growth rate (%)',31:'% of total population',33:'% in same age group',34:'% in same age group',36:'% of GDP',37:'% of earnings',39:'% of foreign-born population',41:'% of GDP',42:'% of GDP',45:'Million US dollars',48:'Per 1 000 inhabitants',50:'% of net disposable income',52:'% of household disposable income',53:'% of household disposable income',54:'Percentage',55:'Percentage',56:'% of value added',57:'Gini coefficient',58:'2015=100',59:'Annual growth rate (%)',60:'Annual growth rate (%)',62:'% of all households',63:'% of total inventors',64:'% of GFCF',65:'Annual growth rate (%)',66:'Percentage',67:'% of unemployed',68:'Per 1 000 000 inhabitants',69:'Per 1 000 000 inhabitants',71:'Tonnes/capita',72:'Mean score',73:'Kilograms/capita',74:'2015=100',75:'Percentage',76:'% of native-born labour force',77:'% of pre-retirement earnings',78:'Per 1 000 inhabitants',79:'% of GDP',80:'% in same age group',81:'Ratio',82:'Toe/1 000 US dollars',84:'% of GDP',86:'Mean score',87:'% of employment',88:'Percentage',89:'2015=100',90:'Index',91:'% of total employed',92:'Ratio',93:'Per 100 000 persons',94:'% of labour cost',96:'% of dependent employment',97:'Ratio',98:'Percentage',109:'% of 25-64 year-olds',118:'Days',120:'Per 1 000 inhabitants',123:'% of GDP',124:'Mean score'}
# Documents/statistical source families are grouped together, including related
# metrics. All Health Statistics and Education/TALIS/PISA are held out.
GROUPS={
 'land-resources':{3},
 'health-statistics':{4,10,21,24,25,26,29,47,48,49,68,69,78,93,118,120},
 'education-statistics':{14,34,72,80,84,86,92,95,98,109,123,124},
 'benefits-and-wages':{0,2,5,37},'migration-labour':{6,39,76},
 'pensions-at-a-glance':{8,77,113},'prices':{9,59},'regional-statistics':{11,75,105},
 'income-distribution':{13,57,81},'revenue-statistics':{15,16},
 'economic-outlook':{17,30,53,60,117},'gender-institutions':{18,28,90},
 'government-at-a-glance':{19},'data-warehouse':{12,22,23,63,70,88,126},
 'agricultural-outlook':{27},'labour-statistics':{31,33,67,96,103,104,108},
 'fdi-statistics':{35,36,116},'national-accounts':{41,42,46,50,51,52,64,97},
 'aid-statistics':{45,100,122},'well-being':{54,102},'ict-factbook':{55,56},
 'industrial-production':{58},'ict-household-access':{62},
 'productivity':{65},'green-growth':{66},'material-resources':{71},
 'waste':{73},'finance':{44,74,89,111,119,127},'social-expenditure':{79},
 'energy':{82},'gender-entrepreneurship':{87,91},'taxing-wages':{94},
}


def dump(path,value):
    data=json.dumps(value,ensure_ascii=False,indent=2).encode('utf-8')
    with path.open('xb') as f:f.write(data)
    return hashlib.sha256(data).hexdigest()


def main():
    if (OUT/'split-lock.json').exists():raise SystemExit('Split already frozen. Will not overwrite.')
    records=json.loads((CACHE/'oecd-candidates.json').read_text(encoding='utf-8'))
    development=[i for i in range(len(records)) if i not in HELD|EXCLUDED][:60]
    cases=[]
    for i in development+sorted(HELD):
        r=records[i];group=next((name for name,indices in GROUPS.items() if i in indices),None)
        assert group and i in UNITS
        cases.append({**r,'id':f'O{i:03d}','split':'holdout' if i in HELD else 'development','source_group':group,
          'publisher':'OECD','source_page':'https://github.com/vis-nlp/ChartQA','terms_url':'https://www.oecd.org/en/about/terms-conditions.html',
          'attribution':'OECD, indicator and statistical source as printed in chart; archived by Masry et al., ChartQA (2022). Evaluation by ChartBridge; no OECD endorsement.',
          'gold_provenance':'ChartQA authors published underlying CSV, separately downloaded and visually cross-checked before model calls. Not an LLM answer. Original statistical microdata not re-audited.',
          'review':'numeric labels, order, unit and CSV cross-checked; no K/M/G abbreviated cases admitted',
          'gold':{'supported':True,'title':r['header'][1],'unit':UNITS[i],'categories':[{'label':label,'value':float(value)} for label,value in r['rows']]}})
    dev=[c for c in cases if c['split']=='development'];held=[c for c in cases if c['split']=='holdout']
    assert len(dev)==60 and len(held)==25
    assert not ({c['source_group'] for c in dev}&{c['source_group'] for c in held})
    assert len({c['image_sha256'] for c in cases})==85
    OUT.mkdir(parents=True,exist_ok=True)
    dev_hash=dump(OUT/'development.json',{'version':'real-v2','cases':dev})
    held_hash=dump(CACHE/'holdout-sealed.json',{'version':'real-v2','cases':held})
    public_held=[{k:c[k] for k in ('id','source_group','image_sha256','table_sha256','image_url','table_url')} for c in held]
    dump(OUT/'holdout-index.json',{'cases':public_held,'gold_sha256':held_hash})
    dump(OUT/'screening.json',{'candidates_with_two_column_csv':len(records),'excluded_indices':sorted(EXCLUDED),
      'excluded_reasons':{'12':'not all bars have printed labels','70':'loading state; title/source incomplete','others':'K/M/G abbreviation and CSV magnitude/precision unresolved; gold insufficient'},
      'unselected': [i for i in range(len(records)) if i not in development and i not in HELD],
      'license_notes':'No original publisher images/CSV are redistributed. ChartQA repository GPL-3.0 declaration is not treated as a universal license to underlying publisher images. Do not use Statista or Pew candidates without suitable permission.',
      'limitations':'Positive set is English OECD platform only. Source-family disjoint, not publisher/style disjoint. Japanese, negative/zero and native poor-quality cases are not covered by this positive set.'})
    dump(OUT/'split-lock.json',{'version':'real-v2','development':60,'holdout':25,'development_sha256':dev_hash,'holdout_gold_sha256':held_hash,
      'groups_development':sorted({c['source_group'] for c in dev}),'groups_holdout':sorted({c['source_group'] for c in held}),
      'holdout_policy':'Do not open sealed gold or original images during improvement. Open only once after code/prompt freeze; no subsequent tuning on this set.',
      'grouping_unit':'Statistical source document/family printed in chart; OECD publisher/rendering platform shared. Not publisher-disjoint.'})
    print('Frozen: development 60 / holdout 25; no group overlap. Originals remain ignored.')


if __name__=='__main__':main()
