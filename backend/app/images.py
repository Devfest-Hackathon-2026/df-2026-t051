"""Private source images; bytes are served only after owner authorization."""
import os
from functools import lru_cache
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from google.cloud import storage
from .auth import teacher
from .materials import repository


@lru_cache
def storage_client():
    return storage.Client()


def save_image(data: bytes, uid: str, store):
    bucket=os.environ.get('IMAGE_BUCKET')
    if not bucket:
        return None
    identifier=uuid4().hex
    path=f'sources/{identifier}.png'
    storage_client().bucket(bucket).blob(path).upload_from_string(data,content_type='image/png',if_generation_match=0,timeout=30)
    store.client.collection('chartbridge_images').document(identifier).create({'owner':uid,'path':path})
    return identifier


router=APIRouter(prefix='/api/images')


@router.get('/{identifier}')
def source_image(identifier:str,uid:str=Depends(teacher),store=Depends(repository)):
    from .materials import owned,validate_id
    validate_id(identifier)
    metadata=owned(store.client.collection('chartbridge_images').document(identifier).get(),uid)
    bucket=os.environ.get('IMAGE_BUCKET')
    if not bucket:
        raise HTTPException(503,'画像保存先が設定されていません。')
    data=storage_client().bucket(bucket).blob(metadata['path']).download_as_bytes(timeout=30)
    return Response(data,media_type='image/png',headers={'Cache-Control':'no-store'})
