"""Release orchestration never restores the unthrottled old image while public."""
import hashlib
import json
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
import httpx

ROOT=Path(__file__).resolve().parents[2]
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')

def setup(tmp_path,monkeypatch,action='stage',approved=True):
    monkeypatch.syspath_prepend(str(ROOT/'scripts'))
    root=tmp_path/'release';script=root/'scripts/publish_candidate.py';script.parent.mkdir(parents=True);script.write_bytes((ROOT/'scripts/publish_candidate.py').read_bytes())
    plan={'image_digest':'immutable-image','git_sha':'a'*40,'old_revision':'old','iam_before_sha256':'before','spec_before_sha256':'before','tag':'judge-ready','remove_tags_before_public':['judge-ready','review']}
    digest=hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest()
    dump(root/'docs/final-audit/provenance.json',{});dump(root/'.tmp/final-audit/public-plan.json',plan)
    monkeypatch.setattr(sys,'argv',[str(script),action,'--approved-plan-sha256',digest if approved else 'invalid','--evidence-dir',str(root/'evidence')])
    return root,script,plan,digest


def test_missing_or_wrong_approval_never_issues_cloud_call(tmp_path,monkeypatch):
    root,script,plan,digest=setup(tmp_path,monkeypatch,approved=False)
    run=Mock();monkeypatch.setattr('subprocess.run',run)
    with pytest.raises(SystemExit,match='approved plan'):runpy.run_path(str(script),run_name='__main__')
    run.assert_not_called()


def test_existing_public_policy_blocks_staging(tmp_path,monkeypatch):
    root,script,plan,digest=setup(tmp_path,monkeypatch)
    run=Mock(return_value=SimpleNamespace(returncode=0,stdout=json.dumps({'bindings':[{'members':['allUsers']}]})))
    monkeypatch.setattr('subprocess.run',run)
    with pytest.raises(SystemExit,match='private IAM'):runpy.run_path(str(script),run_name='__main__')
    assert run.call_count==1 and 'get-iam-policy' in run.call_args.args[0]


def test_evidence_from_different_revision_cannot_publish(tmp_path,monkeypatch):
    root,script,plan,digest=setup(tmp_path,monkeypatch,'publish')
    dump(root/'.tmp/final-audit/public-staged.json',{'revision':'staged','plan_sha256':digest})
    dump(root/'evidence/firebase-full-flow.json',{});dump(root/'evidence/deployment-context.json',{'revision':'unrelated'})
    run=Mock(return_value=SimpleNamespace(returncode=0,stdout='{}'));monkeypatch.setattr('subprocess.run',run)
    with pytest.raises(SystemExit,match='bound to staged'):runpy.run_path(str(script),run_name='__main__')
    assert run.call_count==1 and 'get-iam-policy' in run.call_args.args[0]


@pytest.mark.parametrize('remove_fails',[True,False])
def test_unconfirmed_iam_closure_never_restores_old_revision(tmp_path,monkeypatch,remove_fails):
    root,script,plan,digest=setup(tmp_path,monkeypatch,'publish');state={'public':False};calls=[]
    dump(root/'.tmp/final-audit/public-staged.json',{'revision':'staged','plan_sha256':digest})
    dump(root/'evidence/deployment-context.json',{'revision':'staged','image_digest':'immutable-image'})
    dump(root/'evidence/firebase-full-flow.json',{'cloud':True,'sourceImageReload':True,'unknownExcluded':True,'comparisonDifference':6,'studentAnalyzeCalls':0,'teacherAxe':0,'studentAxe':0,'revokedTokenStatus':401,'postApprovalUpdate':409,'otherOwner':404,'noTeacherClaim':403})
    def run(args,**kwargs):
        calls.append(args)
        if 'get-iam-policy' in args:value={'bindings':[{'members':['allUsers']}]} if state['public'] else {}
        elif 'revisions' in args:value={'status':{'imageDigest':'immutable-image'},'spec':{'containers':[{'env':[{'name':k,'value':v} for k,v in {'AUTH_MODE':'firebase','PUBLIC_ACCESS':'true','RELEASE_GIT_SHA':'a'*40}.items()]}]}}
        elif 'describe' in args:value={'status':{'url':'https://example.test','traffic':[{'revisionName':'old','percent':100}]}}
        elif 'add-iam-policy-binding' in args:state['public']=True;value={}
        elif 'remove-iam-policy-binding' in args:
            if remove_fails:return SimpleNamespace(returncode=1,stderr='simulated IAM outage')
            state['public']=False;value={}
        else:value={}
        return SimpleNamespace(returncode=0,stdout=json.dumps(value))
    monkeypatch.setattr('subprocess.run',run)
    monkeypatch.setattr('time.sleep',lambda seconds:None)
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,*args):return SimpleNamespace(status_code=200)
        def request(self,*args):return SimpleNamespace(status_code=200) # unauth /api/me incorrectly succeeds
    monkeypatch.setattr(httpx,'Client',Client)
    with pytest.raises(AssertionError):runpy.run_path(str(script),run_name='__main__')
    assert state['public'] is remove_fails
    assert not any('old=100' in args for args in calls)
    record=json.loads((root/'docs/final-audit/public-release-failed.json').read_text())
    assert record['success'] is False and record['rollback_error_type']=='RuntimeError'
