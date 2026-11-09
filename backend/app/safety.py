"""Do not silently reconcile Japanese place-value labels and axis units."""
import re
from decimal import Decimal
from .models import Extraction
from .numeric_labels import parse_label,value_in_axis_unit


def hold_compound_labels(extraction: Extraction) -> Extraction:
    result=extraction.model_copy(deep=True)
    held=False
    for category in result.categories:
        if category.value is not None and category.evidence and re.search('[千万億兆]',category.evidence):
            category.value=None
            held=True
    if held:
        warning='数値ラベルに千・万・億などの桁表記が含まれています。自動換算せず未確定にしました。元画像の軸単位と照合し、教員が修正してください。'
        result.warnings=(result.warnings[:11]+[warning])
    return result


def normalize_extraction(extraction: Extraction) -> Extraction:
    """Keep nulls; verify transcription consistency; convert only explicit units.

    The legacy hold_compound_labels remains unchanged for frozen baseline runs.
    No confidence score, axis-height reading, or expected dataset values are used.
    """
    result=extraction.model_copy(deep=True);ambiguous=False;inconsistent=False
    for category in result.categories:
        if category.value is None:continue
        parsed=parse_label(category.evidence)
        value=value_in_axis_unit(parsed,result.unit) if parsed else None
        if value is None:
            category.value=None;ambiguous=True;continue
        raw=Decimal(str(category.value))
        # A model may supply the literal coefficient or already-converted value.
        # A third, inconsistent value is held rather than overwritten as correct.
        if raw not in (parsed.value,value):
            category.value=None;inconsistent=True;continue
        category.value=float(value)
    added=[]
    if ambiguous:added.append('数値表記または単位との対応を一意に確認できない項目を未確定にしました。元画像と軸の単位を照合してください。')
    if inconsistent:added.append('数値ラベルの表記とAIの抽出値が一致しない項目を未確定にしました。推測で補わず、元画像を確認してください。')
    if added:result.warnings=result.warnings[:12-len(added)]+added
    return result
