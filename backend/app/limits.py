"""Persistent Gemini attempt quotas plus bounded per-process public read guards.

No client-provided IP/header is trusted for a quota key. Firestore reservations
are atomic across revisions/instances. Request/cache limits are per process and
can reset on restart: they are abuse mitigation, never an invoice hard cap.
"""
import hashlib
import os
import time
from collections import OrderedDict,deque
from datetime import datetime,timedelta,timezone
from threading import Lock

from fastapi import HTTPException,Request
from google.cloud import firestore

JST=timezone(timedelta(hours=9))


def setting(name,default,maximum):
    try:value=int(os.environ.get(name,str(default)))
    except ValueError:raise RuntimeError('Invalid limit configuration') from None
    if not 1<=value<=maximum:raise RuntimeError('Invalid limit configuration')
    return value


class RequestWindow:
    def __init__(self,maximum,seconds=60,clock=time.monotonic):
        self.maximum=maximum;self.seconds=seconds;self.clock=clock;self.events=deque();self.lock=Lock()

    def take(self):
        now=self.clock()
        with self.lock:
            while self.events and self.events[0]<=now-self.seconds:self.events.popleft()
            if len(self.events)>=self.maximum:return False
            self.events.append(now);return True


class SnapshotCache:
    def __init__(self,maximum=128,seconds=60,clock=time.monotonic):
        self.maximum=maximum;self.seconds=seconds;self.clock=clock;self.values=OrderedDict();self.lock=Lock()

    def get(self,key):
        with self.lock:
            found=self.values.get(key)
            if found is None:return None
            expires,value=found
            if expires<=self.clock():del self.values[key];return None
            self.values.move_to_end(key);return value.model_copy(deep=True)

    def put(self,key,value):
        if value.status!='approved':raise ValueError('Only approved snapshots may be cached')
        with self.lock:
            self.values[key]=(self.clock()+self.seconds,value.model_copy(deep=True));self.values.move_to_end(key)
            while len(self.values)>self.maximum:self.values.popitem(last=False)


class UsageQuotas:
    def __init__(self,client):self.client=client

    def reserve(self,uid,kind,now=None):
        now=now or datetime.now(timezone.utc);day=now.astimezone(JST).date().isoformat();minute=int(now.timestamp())//60
        if kind not in ('analysis','write'):raise ValueError('Unknown usage kind')
        per_minute=setting('ANALYSIS_PER_MINUTE',2,20) if kind=='analysis' else setting('WRITE_PER_MINUTE',30,120)
        per_day=setting('ANALYSIS_PER_TEACHER_DAY',10,100) if kind=='analysis' else setting('WRITE_PER_TEACHER_DAY',200,1000)
        global_day=setting('ANALYSIS_GLOBAL_DAY',30,300) if kind=='analysis' else 3000
        hashed=hashlib.sha256(uid.encode()).hexdigest()
        user_ref=self.client.collection('chartbridge_usage').document(f'{kind}-user-{hashed}-{day}')
        global_ref=self.client.collection('chartbridge_usage').document(f'{kind}-global-{day}')

        @firestore.transactional
        def operation(tx):
            user_snapshot=user_ref.get(transaction=tx);global_snapshot=global_ref.get(transaction=tx)
            user=user_snapshot.to_dict() if user_snapshot.exists else {};global_data=global_snapshot.to_dict() if global_snapshot.exists else {}
            count=user.get('count',0);global_count=global_data.get('count',0)
            recent=user.get('minute_count',0) if user.get('minute')==minute else 0
            if count>=per_day or global_count>=global_day:
                midnight=datetime.combine(now.astimezone(JST).date()+timedelta(days=1),datetime.min.time(),JST)
                raise HTTPException(429,'本日の利用上限に達しました。翌日または管理者への確認後に再試行してください。',headers={'Retry-After':str(max(1,int((midnight-now).total_seconds())))})
            if recent>=per_minute:
                raise HTTPException(429,'操作が集中しています。少し待って再試行してください。',headers={'Retry-After':str(60-int(now.timestamp())%60)})
            # Attempts are never refunded, including model/transport errors.
            # Read both documents first, then perform writes atomically.
            tx.set(user_ref,{'count':count+1,'minute':minute,'minute_count':recent+1,'day':day})
            tx.set(global_ref,{'count':global_count+1,'day':day})
        operation(self.client.transaction())


def reserve_usage(request:Request,uid,kind):
    if request.app.state.demo:return
    if os.environ.get('APP_ENV')!='production' and not os.environ.get('K_SERVICE'):return
    project=os.environ.get('FIRESTORE_PROJECT_ID')
    if not project:raise HTTPException(503,'利用上限の確認先が設定されていません。')
    override=getattr(request.app.state,'usage_quotas',None)
    try:
        if override is None:
            from .materials import firestore_repository
            override=UsageQuotas(firestore_repository(project).client)
        override.reserve(uid,kind)
    except HTTPException:raise
    except Exception:raise HTTPException(503,'利用上限を確認できません。時間をおいて再試行してください。') from None
