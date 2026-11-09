"""Owner-scoped drafts and transactional, immutable approved snapshots."""
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from google.cloud import firestore
from pydantic import Field, field_validator

from .auth import teacher
from .models import Extraction, StrictModel
from .limits import reserve_usage


class ReviewCategory(StrictModel):
    label: str | None = Field(max_length=120)
    value: float | None = Field(strict=True)

    @field_validator('label')
    @classmethod
    def trim(cls, value):
        return value.strip() or None if value is not None else None


class ReviewData(StrictModel):
    title: str | None = Field(max_length=200)
    unit: str | None = Field(max_length=80)
    categories: list[ReviewCategory] = Field(min_length=2, max_length=12)

    @field_validator('title', 'unit')
    @classmethod
    def trim(cls, value):
        return value.strip() or None if value is not None else None


class CreateDraft(StrictModel):
    original: Extraction
    data: ReviewData
    image_id: str | None = None


class UpdateDraft(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    data: ReviewData


class ApproveDraft(StrictModel):
    expected_version: int = Field(ge=1, strict=True)
    confirmed: Literal[True]


class DraftRecord(StrictModel):
    id: str
    status: Literal['unreviewed','approved']
    version: int
    data: ReviewData
    snapshot_id: str | None
    original: Extraction | None = None
    image_id: str | None = None


class Snapshot(StrictModel):
    id: str
    status: Literal['approved']
    approved_at: str
    data: ReviewData


def owned(snapshot, uid):
    if not snapshot.exists:
        raise HTTPException(404, '教材が見つかりません。')
    data = snapshot.to_dict()
    # Return the same 404 for missing and somebody else's draft.
    if data['owner'] != uid:
        raise HTTPException(404, '教材が見つかりません。')
    return data


def editable(data, version):
    if data['status'] != 'unreviewed':
        raise HTTPException(409, '承認済み教材は変更できません。新しい教材を作成してください。')
    if data['version'] != version:
        raise HTTPException(409, '別の操作で更新されています。教材を読み直してください。')


def record(identifier, data):
    return DraftRecord(id=identifier, **{k:data.get(k) for k in ('status','version','data','snapshot_id','original','image_id')})


class FirestoreMaterials:
    def __init__(self, client):
        self.client = client

    def ref(self, identifier):
        return self.client.collection('chartbridge_drafts').document(identifier)

    def create(self, uid, payload):
        if not payload.original.supported:
            raise HTTPException(422, '対応範囲内の解析結果を保存してください。')
        identifier = uuid4().hex
        if payload.image_id:
            validate_id(payload.image_id)
            owned(self.client.collection('chartbridge_images').document(payload.image_id).get(),uid)
        data = {'owner':uid, 'status':'unreviewed','version':1,'data':payload.data.model_dump(),
                'original':payload.original.model_dump(),'snapshot_id':None,'image_id':payload.image_id,
                'created_at':datetime.now(timezone.utc).isoformat()}
        self.ref(identifier).create(data)
        return record(identifier,data)

    def read(self, uid, identifier):
        return record(identifier, owned(self.ref(identifier).get(),uid))

    def list(self, uid):
        # Equality filter only: no composite index requirement. Bounded response.
        from google.cloud.firestore_v1.base_query import FieldFilter
        snapshots=self.client.collection('chartbridge_drafts').where(filter=FieldFilter('owner','==',uid)).limit(100).stream()
        return [record(snapshot.id,snapshot.to_dict()) for snapshot in snapshots]

    def public(self, identifier):
        snapshot=self.client.collection('chartbridge_snapshots').document(identifier).get()
        if not snapshot.exists or snapshot.to_dict().get('status')!='approved':
            raise HTTPException(404,'承認済み教材が見つかりません。')
        return Snapshot.model_validate(snapshot.to_dict())

    def update(self, uid, identifier, payload):
        ref = self.ref(identifier)

        @firestore.transactional
        def operation(tx):
            data=owned(ref.get(transaction=tx),uid)
            editable(data,payload.expected_version)
            updates={'data':payload.data.model_dump(),'version':data['version']+1}
            tx.update(ref, updates)
            return record(identifier,{**data,**updates})

        return operation(self.client.transaction())

    def approve(self, uid, identifier, payload):
        ref=self.ref(identifier)
        snapshot_id=uuid4().hex
        snapshot_ref=self.client.collection('chartbridge_snapshots').document(snapshot_id)

        @firestore.transactional
        def operation(tx):
            data=owned(ref.get(transaction=tx),uid)
            editable(data,payload.expected_version)
            reviewed=ReviewData.model_validate(data['data'])
            if reviewed.title is None or any(c.label is None for c in reviewed.categories):
                raise HTTPException(422,'タイトルとすべての項目名を確認してください。数値・単位の未確定は明示して保持できます。')
            snapshot=Snapshot(id=snapshot_id,status='approved',approved_at=datetime.now(timezone.utc).isoformat(),data=reviewed)
            # create, never set/update: a snapshot is immutable through this API.
            tx.create(snapshot_ref,snapshot.model_dump())
            tx.update(ref,{'status':'approved','snapshot_id':snapshot_id,'version':data['version']+1})
            return snapshot

        return operation(self.client.transaction())

    def approved(self, uid, identifier):
        data=owned(self.ref(identifier).get(),uid)
        if data['status'] != 'approved' or not data['snapshot_id']:
            raise HTTPException(404,'承認済み教材がありません。')
        snapshot=self.client.collection('chartbridge_snapshots').document(data['snapshot_id']).get()
        if not snapshot.exists:
            raise HTTPException(404,'承認済み教材がありません。')
        return Snapshot.model_validate(snapshot.to_dict())


@lru_cache
def firestore_repository(project):
    return FirestoreMaterials(firestore.Client(project=project))


def repository(request: Request):
    if request.app.state.demo:
        raise HTTPException(503,'固定デモのデータは保存・承認できません。')
    project=os.environ.get('FIRESTORE_PROJECT_ID')
    if not project:
        raise HTTPException(503,'教材の保存先が設定されていません。')
    return firestore_repository(project)


router=APIRouter(prefix='/api/drafts')


@router.get('',response_model=list[DraftRecord])
def list_drafts(uid:str=Depends(teacher),store=Depends(repository)):
    return store.list(uid)


@router.post('',response_model=DraftRecord,status_code=201)
def create(request:Request,payload:CreateDraft,uid:str=Depends(teacher),store=Depends(repository)):
    reserve_usage(request,uid,'write')
    return store.create(uid,payload)


@router.get('/{identifier}',response_model=DraftRecord)
def read(identifier:str,uid:str=Depends(teacher),store=Depends(repository)):
    validate_id(identifier)
    return store.read(uid,identifier)


@router.put('/{identifier}',response_model=DraftRecord)
def update(request:Request,identifier:str,payload:UpdateDraft,uid:str=Depends(teacher),store=Depends(repository)):
    validate_id(identifier)
    reserve_usage(request,uid,'write')
    return store.update(uid,identifier,payload)


@router.post('/{identifier}/approve',response_model=Snapshot)
def approve(request:Request,identifier:str,payload:ApproveDraft,uid:str=Depends(teacher),store=Depends(repository)):
    validate_id(identifier)
    reserve_usage(request,uid,'write')
    return store.approve(uid,identifier,payload)


@router.get('/{identifier}/approved',response_model=Snapshot)
def approved(identifier:str,uid:str=Depends(teacher),store=Depends(repository)):
    validate_id(identifier)
    return store.approved(uid,identifier)


def validate_id(identifier):
    if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):
        raise HTTPException(404,'教材が見つかりません。')


public_router=APIRouter(prefix='/api/materials')


@public_router.get('/{identifier}',response_model=Snapshot)
def public_material(request:Request,identifier:str,store=Depends(repository)):
    validate_id(identifier)
    if not request.app.state.public_reads.take():
        raise HTTPException(429,'教材へのアクセスが集中しています。少し待って再試行してください。',headers={'Retry-After':'60'})
    cached=request.app.state.snapshot_cache.get(identifier)
    if cached is not None:return cached
    snapshot=store.public(identifier)
    request.app.state.snapshot_cache.put(identifier,snapshot)
    return snapshot
