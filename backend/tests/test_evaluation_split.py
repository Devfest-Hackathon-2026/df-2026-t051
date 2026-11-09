"""Audit frozen manifests without opening sealed holdout gold or images."""
import hashlib
import json
from pathlib import Path
from decimal import Decimal

ROOT=Path(__file__).resolve().parents[2]/'evaluation/real-v2'


def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))


def test_development_manifest_still_matches_preregistered_hash():
    assert hashlib.sha256((ROOT/'development.json').read_bytes()).hexdigest()==read('split-lock.json')['development_sha256']


def test_split_has_no_statistical_source_family_or_image_overlap():
    dev=read('development.json')['cases'];held=read('holdout-index.json')['cases']
    assert len(dev)==60 and len(held)==25
    assert not {c['source_group'] for c in dev}&{c['source_group'] for c in held}
    assert not {c['image_sha256'] for c in dev}&{c['image_sha256'] for c in held}
    assert len({c['image_sha256'] for c in dev+held})==85


def test_gold_values_are_copied_from_separate_published_csv_not_predictions():
    for case in read('development.json')['cases']:
        assert case['table_url']!=case['image_url'] and case['redistribute'] is False
        assert 2<=len(case['gold']['categories'])<=12
        assert len(case['rows'])==len(case['gold']['categories'])
        for (label,value),expected in zip(case['rows'],case['gold']['categories']):
            assert label==expected['label']
            assert Decimal(value)==Decimal(str(expected['value']))


def test_anomalies_never_enter_positive_accuracy_population():
    anomalies=read('anomalies.json')['cases'];positives=read('development.json')['cases']+read('holdout-index.json')['cases']
    assert len(anomalies)==15 and all(c['gold']['supported'] is False and c['gold']['categories']==[] for c in anomalies)
    assert not {c['image_sha256'] for c in anomalies}&{c['image_sha256'] for c in positives}
