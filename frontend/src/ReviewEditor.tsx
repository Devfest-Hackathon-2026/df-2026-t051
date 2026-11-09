import { FormEvent, useEffect, useRef, useState } from 'react';
import type { User } from 'firebase/auth';

export type Extraction = {supported:boolean;reason:string|null;title:string|null;unit:string|null;categories:{label:string|null;value:number|null;evidence:string|null}[];warnings:string[]};
type Data = {title:string|null;unit:string|null;categories:{label:string|null;value:number|null}[]};
export type Saved = {id:string;status:'unreviewed'|'approved';version:number;data:Data;snapshot_id:string|null;original:Extraction;image_id:string|null};
export type Snapshot = {id:string;status:'approved';approved_at:string;data:Data};
export type ReviewPhase='extracted'|'editing'|'saved'|'ready'|'approved';

export function ReviewEditor({extraction,user,imageId,initialSaved,initialSnapshot,serviceBaseUrl,publicAccess=false,onSaved,onPhaseChange}:{extraction:Extraction;user:User|null;imageId?:string|null;initialSaved?:Saved|null;initialSnapshot?:Snapshot|null;serviceBaseUrl?:string;publicAccess?:boolean;onSaved?:()=>void;onPhaseChange?:(phase:ReviewPhase)=>void}) {
  const [data,setData] = useState<Data>(initialSnapshot?.data??initialSaved?.data??{title:extraction.title,unit:extraction.unit,categories:extraction.categories.map(({label,value})=>({label,value}))});
  const [saved,setSaved] = useState<Saved|null>(initialSaved??null);
  const [snapshot,setSnapshot] = useState<Snapshot|null>(initialSnapshot??null);
  const [dirty,setDirty] = useState(!initialSaved);
  const [confirmed,setConfirmed] = useState(false);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState('');
  const [message,setMessage] = useState('');
  const [created,setCreated]=useState(false);
  const errorRef = useRef<HTMLDivElement>(null);
  const approvedRef = useRef<HTMLHeadingElement>(null);
  useEffect(()=>{if(error)errorRef.current?.focus();},[error]);
  useEffect(()=>{if(snapshot)approvedRef.current?.focus();},[snapshot]);
  useEffect(()=>{onPhaseChange?.(snapshot?'approved':dirty?(saved?'editing':'extracted'):confirmed?'ready':'saved');},[snapshot,dirty,saved,confirmed,onPhaseChange]);
  function edit(next:Data) {setData(next);setDirty(true);setConfirmed(false);setMessage('');}
  async function api(path:string,method:string,body:unknown) {
    const headers:Record<string,string>={'Content-Type':'application/json'};
    if(user) headers.Authorization=`Bearer ${await user.getIdToken()}`;
    const response=await fetch(path,{method,headers,body:JSON.stringify(body)});
    const payload=await response.json();
    if(!response.ok)throw Error(typeof payload.detail==='string'?payload.detail:'入力内容を確認してください。');
    return payload;
  }
  async function save(e:FormEvent) {
    e.preventDefault();setBusy(true);setError('');setMessage('');
    try {
      const result:Saved=await api(saved?`/api/drafts/${saved.id}`:'/api/drafts',saved?'PUT':'POST',saved?{expected_version:saved.version,data}:{original:extraction,data,image_id:imageId??null});
      setSaved(result);setData(result.data);setDirty(false);setMessage('未承認の教材を保存しました。まだ学生には配布できません。');onSaved?.();
    } catch(err){setError(err instanceof Error?err.message:'保存できませんでした。');}
    finally{setBusy(false);}
  }
  async function approve() {
    if(!saved||dirty||!confirmed)return;
    setBusy(true);setError('');
    try {
      const result:Snapshot=await api(`/api/drafts/${saved.id}/approve`,'POST',{expected_version:saved.version,confirmed:true});
      setSnapshot(result);setData(result.data);setCreated(true);setMessage('承認済みの変更できない版を保存しました。');onSaved?.();
    } catch(err){setError(err instanceof Error?err.message:'承認できませんでした。');}
    finally{setBusy(false);}
  }
  return <section className="review" aria-labelledby="review-title"><h3 id="review-title">教員による確認・編集</h3>
    <div className={snapshot?'material-state approved-state':'material-state'}><strong>{snapshot?'教材：承認済み（配布版固定）':saved?(dirty?'教材：未承認・未保存の変更あり':'教材：未承認・保存済み'):'教材：未保存・教員確認前'}</strong><p>{snapshot?'次に：学生向け教材を開き、配布する内容を確認してください。':dirty?'次に：元画像と数値・単位を照合し、変更を保存してください。':confirmed?'次に：承認版を作成してください。承認後は変更できません。':'次に：すべての項目を照合し、確認チェックを付けてください。'}</p></div>
    <p className="muted">元画像と照合して修正してください。数値が読めない場合は空欄のままにし、「未確定」として保存します。単位が不明な場合も空欄を保持します。</p>
    {error&&<div className="error" role="alert" tabIndex={-1} ref={errorRef}>{error}</div>}
    <form onSubmit={save} aria-busy={busy}>
      <fieldset disabled={busy||!!snapshot}><legend>教員が確認するデータ</legend>
        <label className="edit-label">タイトル<input value={data.title??''} maxLength={200} onChange={e=>edit({...data,title:e.target.value||null})}/></label>
        <label className="edit-label">単位（空欄は未確定）<input value={data.unit??''} maxLength={80} onChange={e=>edit({...data,unit:e.target.value||null})}/></label>
        <div className="table-wrap"><table><caption>編集用データ表</caption><thead><tr><th scope="col">項目名</th><th scope="col">数値（空欄は未確定）</th></tr></thead><tbody>{data.categories.map((category,index)=><tr key={index}><td><input aria-label={`項目${index+1}の名前`} value={category.label??''} maxLength={120} onChange={e=>edit({...data,categories:data.categories.map((c,i)=>i===index?{...c,label:e.target.value||null}:c)})}/></td><td><input aria-label={`項目${index+1}の数値`} type="number" step="any" value={category.value??''} onChange={e=>edit({...data,categories:data.categories.map((c,i)=>i===index?{...c,value:e.target.value===''?null:e.target.valueAsNumber}:c)})}/>{category.value===null&&<span className="unknown">未確定</span>}</td></tr>)}</tbody></table></div>
        <button className="primary" disabled={busy||!!snapshot||!dirty}>{busy?'処理中…':saved?'修正を保存':'未承認として保存'}</button>
      </fieldset>
    </form>
    {saved&&!snapshot&&<div className="approval"><p className="small">保存済み教材ID：<code>{saved.id}</code></p><label className="confirm"><input type="checkbox" checked={confirmed} disabled={busy||dirty} onChange={e=>setConfirmed(e.target.checked)}/> 元画像と全項目を照合し、未確定の数値・単位を確認しました。</label><button onClick={approve} disabled={busy||dirty||!confirmed}>確認して承認版を作成</button>{dirty&&<p className="muted">変更を保存してから承認してください。</p>}</div>}
    <p role="status" aria-live="polite">{message}</p>
    {snapshot&&<div className="approved"><h3 ref={approvedRef} tabIndex={-1}>{created?'承認版を作成しました':'承認済み教材を開いています'}</h3><p>この版は変更できません。元の未承認データも編集できなくなります。</p><p className="small">承認版ID：<code>{snapshot.id}</code></p><a className="share-link" href={`/learn/${snapshot.id}`}>学生向け教材を開く</a><label className="edit-label">学生向け共有URL<input readOnly value={`${serviceBaseUrl||window.location.origin}/learn/${snapshot.id}`}/></label><p className="muted">{publicAccess?'このリンクでは承認済みの教材だけを閲覧できます。':'現在はIAM非公開です。共有先でもCloud Runのアクセス権が必要です。'}</p></div>}
  </section>;
}
