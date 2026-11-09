"""Conservative decimal parsing. Never derive a value from bar height/context.

Evidence is still model transcription, not independent OCR verification.
Ambiguous omitted units between Japanese place values and a scaled axis are
intentionally unresolved. No chart-specific labels or expected values live here.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
import unicodedata

DIGITS=str.maketrans('〇零一二三四五六七八九','00123456789')
SMALL={'十':10,'百':100,'千':1000}
BIG={'万':10_000,'億':100_000_000,'兆':1_000_000_000_000}
NUMBER=r'(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'


@dataclass(frozen=True)
class LabelNumber:
    value: Decimal
    suffix: str
    compound: bool


def _small(text):
    if not text:return Decimal(0)
    parts=re.findall(rf'({NUMBER})?([千百十])|({NUMBER})',text)
    if ''.join((n or '')+u+(tail or '') for n,u,tail in parts)!=text:return None
    total=Decimal(0);last=10000
    for i,(n,unit,tail) in enumerate(parts):
        if tail:
            if i!=len(parts)-1:return None
            total+=Decimal(tail.replace(',',''))
        else:
            scale=SMALL[unit]
            if scale>=last:return None
            total+=Decimal((n or '1').replace(',',''))*scale;last=scale
    return total


def parse_label(text: str | None) -> LabelNumber | None:
    if not text or len(text)>120:return None
    clean=unicodedata.normalize('NFKC',text).strip().replace('−','-')
    # Approximation, inequalities, intervals, uncertainty and multiple numbers
    # are not repaired to a single confirmed number.
    if any(c in clean for c in ('約','未満','以上','以下','±','~','～','<','>','?','？','…')):return None
    match=re.fullmatch(r'([+-]?)([0-9〇零一二三四五六七八九十百千万億兆,.]+)\s*([^0-9]*)',clean)
    if not match:return None
    sign,number,suffix=match.groups();translated=number.translate(DIGITS)
    try:
        total=Decimal(0);last=10**16;start=0
        for m in re.finditer('[万億兆]',translated):
            scale=BIG[m.group()]
            if scale>=last:return None
            part=_small(translated[start:m.start()])
            if part is None or not translated[start:m.start()]:return None
            total+=part*scale;last=scale;start=m.end()
        part=_small(translated[start:])
        if part is None:return None
        total+=part
        if sign=='-':total=-total
        if not total.is_finite() or abs(total)>Decimal(2**53-1):return None
        # No silently rounded values cross the JSON/JavaScript boundary.
        if Decimal(str(float(total)))!=total:return None
        return LabelNumber(total,suffix.strip(),bool(re.search('[十百千万億兆]',number)))
    except (InvalidOperation,OverflowError,ValueError):return None


def unit_signature(unit):
    """Only a small, explicit set of physical/count unit aliases is convertible."""
    if unit is None:return None
    name=re.sub(r'\s+','',unicodedata.normalize('NFKC',unit)).casefold()
    if name.startswith('percentageof'):name='%of'+name[len('percentageof'):]
    elif name.startswith('percentof'):name='%of'+name[len('percentof'):]
    percent_descriptor=name.endswith('(%)')
    name=name.strip('()（）')
    scales={'兆':Decimal(10)**12,'億':Decimal(10)**8,'万':Decimal(10)**4,'千':Decimal(10)**3}
    scale=Decimal(1)
    if name and name[0] in scales:scale=scales[name[0]];name=name[1:]
    aliases={'t':'mass-t','トン':'mass-t','tonnes':'mass-t','kg':'mass-t','キログラム':'mass-t','g':'mass-t','グラム':'mass-t','人':'people','people':'people','persons':'people','円':'jpy','jpy':'jpy','件':'cases','個':'items','%':'percent','パーセント':'percent','percentage':'percent','percent':'percent'}
    dimension=aliases.get(name)
    if dimension is None and name.startswith('%of'):dimension='percent:'+name[3:]
    if dimension is None and percent_descriptor:dimension='percent:'+name
    if dimension is None:return None
    if name in ('kg','キログラム'):scale/=1000
    if name in ('g','グラム'):scale/=1_000_000
    return dimension,scale


def value_in_axis_unit(parsed: LabelNumber, unit: str | None) -> Decimal | None:
    axis=unit_signature(unit)
    if parsed.suffix:
        printed=unit_signature(parsed.suffix)
        if not axis or not printed or (axis[0]!=printed[0] and not (printed[0]=='percent' and axis[0].startswith('percent:'))):return None
        value=parsed.value*printed[1]/axis[1]
    elif parsed.compound:
        # 6万4千 with 千t could mean 64千t or 64000千t. Neither is chosen.
        if not axis or axis[1]!=1:return None
        value=parsed.value
    else:value=parsed.value
    if not value.is_finite() or abs(value)>Decimal(2**53-1) or Decimal(str(float(value)))!=value:return None
    return value
