import {useEffect,useState} from 'react';
import type {User} from 'firebase/auth';
import type {Saved} from './ReviewEditor';
export function SavedMaterials({user,refresh,onOpen}:{user:User|null;refresh:number;onOpen:(record:Saved)=>void}) {
  const [records,setRecords]=useState<Saved[]>([]);
  const [error,setError]=useState('');
  useEffect(()=>{let active=true;(async()=>{
    try{const headers:Record<string,string>={};if(user)headers.Authorization=`Bearer ${await user.getIdToken()}`;
      const response=await fetch('/api/drafts',{headers});if(!response.ok)throw Error('保存済み教材を読み込めません。ログインと教員権限を確認してください。');
      const result=await response.json();if(active){setRecords(result);setError('');}}
    catch(e){if(active)setError(e instanceof Error?e.message:'読込エラー');}
  })();return()=>{active=false;};},[user,refresh]);
  return <section className="panel saved-materials" aria-labelledby="saved-title"><h2 id="saved-title">保存済みの教材を開く</h2>{error&&<p role="alert">{error}</p>}{records.length===0&&!error&&<p>保存済み教材はありません。</p>}<ul>{records.map(record=><li key={record.id}><button className="secondary" onClick={()=>onOpen(record)}>{record.data.title??'タイトル未確定'} — {record.status==='approved'?'承認済み':'未承認'}</button>{!record.image_id&&<span className="muted"> 元画像未保存（以前の教材）</span>}</li>)}</ul><p className="muted">自分の教材を最大100件表示します。教材を開くと保存時点の数値と元画像を読み込みます。</p></section>;
}
