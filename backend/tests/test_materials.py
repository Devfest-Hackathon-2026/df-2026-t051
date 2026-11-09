from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from app import auth, materials
from app.main import create_app


class Ref:
    def __init__(self, db, key):
        self.db,self.key=db,key

    def get(self, transaction=None):
        data=deepcopy(self.db.docs.get(self.key))
        class Snapshot:
            exists=data is not None
            def to_dict(self):
                return deepcopy(data)
        return Snapshot()

    def create(self, data):
        assert self.key not in self.db.docs
        self.db.docs[self.key]=deepcopy(data)


class Transaction:
    def __init__(self,db):
        self.db,self.pending=db,[]

    def update(self,ref,data):
        self.pending.append(('update',ref,data))

    def create(self,ref,data):
        self.pending.append(('create',ref,data))

    def commit(self):
        for method,ref,data in self.pending:
            if method=='create':
                ref.create(data)
            else:
                self.db.docs[ref.key].update(deepcopy(data))


class DB:
    def __init__(self):
        self.docs={}

    def collection(self,name):
        db=self
        class Collection:
            def document(self,identifier):
                return Ref(db,(name,identifier))
        return Collection()

    def transaction(self):
        return Transaction(self)


@pytest.fixture
def context(monkeypatch):
    def transactional(fn):
        def wrapped(tx):
            result=fn(tx)
            tx.commit()
            return result
        return wrapped
    monkeypatch.setattr(materials.firestore,'transactional',transactional)
    db=DB()
    app=create_app(False)
    identity=['teacher-one']
    app.dependency_overrides[auth.teacher]=lambda:identity[0]
    app.dependency_overrides[materials.repository]=lambda:materials.FirestoreMaterials(db)
    with TestClient(app) as client:
        yield client,db,identity


def payload():
    return {'original':{'supported':True,'reason':None,'title':'Original','unit':'people',
                        'categories':[{'label':'A','value':12,'evidence':'12'},{'label':'B','value':None,'evidence':None}], 'warnings':[]},
            'data':{'title':'Checked','unit':None,'categories':[{'label':'A','value':12},{'label':'B','value':None}]}}


def test_draft_approval_and_snapshot_are_immutable(context):
    client,db,_=context
    create=client.post('/api/drafts',json=payload())
    assert create.status_code==201
    draft=create.json()
    path='/api/drafts/'+draft['id']
    assert client.get(path+'/approved').status_code==404
    data=payload()['data']
    data['categories'][0]['value']=14
    update=client.put(path,json={'expected_version':1,'data':data})
    assert update.status_code==200 and update.json()['version']==2
    assert client.put(path,json={'expected_version':1,'data':data}).status_code==409
    assert client.post(path+'/approve',json={'expected_version':1,'confirmed':True}).status_code==409
    approved=client.post(path+'/approve',json={'expected_version':2,'confirmed':True})
    assert approved.status_code==200
    frozen=approved.json()
    assert frozen['data']['categories'][1]['value'] is None
    assert client.get(path).json()['status']=='approved'
    data['categories'][0]['value']=999
    assert client.put(path,json={'expected_version':3,'data':data}).status_code==409
    assert client.post(path+'/approve',json={'expected_version':3,'confirmed':True}).status_code==409
    assert client.get(path+'/approved').json()==frozen
    public=client.get('/api/materials/'+frozen['id'])
    assert public.status_code==200 and public.json()==frozen
    assert 'owner' not in public.json() and 'original' not in public.json()
    assert client.put('/api/materials/'+frozen['id'],json={'data':data}).status_code in {404,405}
    assert client.get('/api/materials/'+draft['id']).status_code==404
    assert len([key for key in db.docs if key[0]=='chartbridge_snapshots'])==1


def test_other_teacher_cannot_read_edit_or_approve(context):
    client,_,identity=context
    draft=client.post('/api/drafts',json=payload()).json()
    path='/api/drafts/'+draft['id']
    identity[0]='teacher-two'
    assert client.get(path).status_code==404
    assert client.put(path,json={'expected_version':1,'data':payload()['data']}).status_code==404
    assert client.post(path+'/approve',json={'expected_version':1,'confirmed':True}).status_code==404
    assert client.get(path+'/approved').status_code==404


def test_original_image_ownership_cannot_be_forged(context):
    client,db,identity=context
    identifier='a'*32
    db.docs[('chartbridge_images',identifier)]={'owner':'teacher-two','path':'private'}
    data=payload()
    data['image_id']=identifier
    assert client.post('/api/drafts',json=data).status_code==404
    assert client.get('/api/images/'+identifier).status_code==404
    db.docs[('chartbridge_images',identifier)]['owner']=identity[0]
    response=client.post('/api/drafts',json=data)
    assert response.status_code==201
    assert client.get('/api/drafts/'+response.json()['id']).json()['image_id']==identifier


def test_confirmation_and_complete_labels_required(context):
    client,db,_=context
    initial=payload()
    initial['data']['categories'][1]['label']='   '
    draft=client.post('/api/drafts',json=initial).json()
    path='/api/drafts/'+draft['id']
    assert client.post(path+'/approve',json={'expected_version':1,'confirmed':False}).status_code==422
    assert client.post(path+'/approve',json={'expected_version':1,'confirmed':True}).status_code==422
    assert not any(key[0]=='chartbridge_snapshots' for key in db.docs)
    assert client.get(path).json()['status']=='unreviewed'


def test_untrusted_state_and_non_numeric_values_rejected(context):
    client,_,_=context
    data=payload()
    data['owner']='attacker'
    assert client.post('/api/drafts',json=data).status_code==422
    for value in ('12',True):
        data=payload()
        data['data']['categories'][0]['value']=value
        assert client.post('/api/drafts',json=data).status_code==422


def test_draft_requires_authentication():
    with TestClient(create_app(False)) as client:
        assert client.post('/api/drafts',json=payload()).status_code==401


def test_demo_data_cannot_be_persisted(monkeypatch):
    monkeypatch.setenv('APP_ENV','local')
    with TestClient(create_app(True)) as client:
        assert client.post('/api/drafts',json=payload()).status_code==503
