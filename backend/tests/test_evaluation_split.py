"""Audit frozen manifests without opening sealed holdout gold or images."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]/'evaluation/real-v2'


def read(name):return json.loads((ROOT/name).read_text(encoding='utf-8'))


def test_public_index_distinguishes_original_freeze_from_redacted_bytes():
    publication=read('PUBLICATION.json')
    entry=next(f for f in publication['redacted_files'] if f['path']=='evaluation/real-v2/development.json')
    assert publication['original_development_sha256']==read('split-lock.json')['development_sha256']
    assert entry['original_sha256']==publication['original_development_sha256']
    assert hashlib.sha256((ROOT/'development.json').read_bytes()).hexdigest()==entry['public_sha256']
    assert entry['public_sha256']!=entry['original_sha256']
    assert read('development.json')['publication']['table_content_omitted'] is True


def test_split_has_no_statistical_source_family_or_image_overlap():
    dev=read('development.json')['cases'];held=read('holdout-index.json')['cases']
    assert len(dev)==60 and len(held)==25
    assert not {c['source_group'] for c in dev}&{c['source_group'] for c in held}
    assert not {c['image_sha256'] for c in dev}&{c['image_sha256'] for c in held}
    assert len({c['image_sha256'] for c in dev+held})==85


def test_public_records_do_not_republish_source_tables_or_model_responses():
    publication=read('PUBLICATION.json')
    for case in read('development.json')['cases']:
        assert case['table_url']!=case['image_url']
        assert set(case)<=set(publication['source_index_fields'])
    for entry in publication['redacted_files']:
        path=ROOT.parents[1]/entry['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==entry['public_sha256']
        if path.name!='cases.jsonl':continue
        for line in path.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            assert set(row)<=set(publication['case_record_fields'])
            assert not {'raw_text','result','gold','expected','header','rows'}&set(row)
            assert isinstance(row['raw_response_recorded'],bool)
            score=row['score']
            assert set(score)<=set(publication['score_fields'])
            assert all(set(f)=={'class'} and f['class'] in 'ABCDEFG' for f in score['findings'])


def test_anomalies_never_enter_positive_accuracy_population():
    anomalies=read('anomalies.json')['cases'];positives=read('development.json')['cases']+read('holdout-index.json')['cases']
    assert len(anomalies)==15 and all(c['gold']['supported'] is False and c['gold']['categories']==[] for c in anomalies)
    assert not {c['image_sha256'] for c in anomalies}&{c['image_sha256'] for c in positives}
