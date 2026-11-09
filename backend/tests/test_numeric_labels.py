from decimal import Decimal
import pytest
from app.numeric_labels import parse_label,value_in_axis_unit


@pytest.mark.parametrize('text,expected',[
 ('6万4千','64000'),('六万四千','64000'),('一億二千万','120000000'),('1.2万','12000'),
 ('三百二十','320'),('二〇二四','2024'),('０','0'),('零','0'),('−2.5','-2.5'),
 ('1,234,567','1234567'),('0.001','0.001'),('１２万３,４００','123400'),
])
def test_exact_decimal_and_japanese_numerals(text,expected):
    assert parse_label(text).value==Decimal(expected)


@pytest.mark.parametrize('text',['1,2','1,23,456','1..2','3〜5','約12','12以上','<3','3±1','一万万','百千','一億億','1.2e3','NaN','Infinity','9007199254740993','1.00000000000000001','A: 12','12 34'])
def test_ambiguous_or_unrepresentable_labels_stay_unknown(text):
    parsed=parse_label(text)
    assert parsed is None or value_in_axis_unit(parsed,'人') is None


@pytest.mark.parametrize('text,axis,expected',[
 ('6万4千t','千t','64'),('6.4万トン','千t','64'),('64000 kg','t','64'),
 ('12人','万人','0.0012'),('12','千t','12'),('六万四千','t','64000'),
 ('6万4千','千t',None),('6万4千',None,None),('12人','円',None),
 ('12K','t',None),('12%','人',None),('0','%','0'),
])
def test_conversion_only_when_unit_relation_is_unique(text,axis,expected):
    parsed=parse_label(text);assert parsed is not None
    value=value_in_axis_unit(parsed,axis)
    assert value==(Decimal(expected) if expected is not None else None)
