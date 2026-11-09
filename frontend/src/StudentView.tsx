import { FormEvent, useEffect, useRef, useState } from 'react';
import { Category, difference, extrema, formatNumber } from './studentMath';

type Snapshot = {id:string;status:'approved';approved_at:string;data:{title:string|null;unit:string|null;categories:Category[]}};

export function StudentView({identifier}:{identifier:string}) {
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null);
  const [error,setError]=useState('');
  const [retry,setRetry]=useState(0);
  const [left,setLeft]=useState(0),[right,setRight]=useState(1);
  const [comparison,setComparison]=useState('');
  const [announcement,setAnnouncement]=useState(0);
  const errorRef=useRef<HTMLDivElement>(null);
  const headingRef=useRef<HTMLHeadingElement>(null);

  useEffect(()=>{
    const controller=new AbortController();
    let active=true;
    const timeout=setTimeout(()=>controller.abort(),20000);
    setError('');setSnapshot(null);setComparison('');setLeft(0);setRight(1);
    (async()=>{
      try {
        const response=await fetch(`/api/materials/${encodeURIComponent(identifier)}`,{signal:controller.signal}).catch(err=>{if(err.name==='AbortError')throw err;throw Error('接続できません。ネットワークと非公開環境への接続を確認してください。');});
        if(!response.ok)throw Error(response.status===404?'教材が見つかりません。承認済み教材のURLを確認してください。':response.status===401||response.status===403?'この教材へのアクセス権がありません。非公開環境への接続を確認してください。':'教材を読み込めません。少し待って再試行してください。');
        const result:Snapshot=await response.json().catch(()=>{throw Error('教材データを読み取れません。教員に確認してください。');});
        if(result.status!=='approved'||!Array.isArray(result.data?.categories))throw Error('教材データを読み取れません。教員に確認してください。');
        if(active){setSnapshot(result);document.title=`${result.data.title??'承認済み教材'} | ChartBridge`;}
      } catch(err) {
        if(active)setError(err instanceof Error&&err.name!=='AbortError'?err.message:'読み込みが時間切れになりました。接続を確認して再試行してください。');
      } finally {clearTimeout(timeout);}
    })();
    return()=>{active=false;clearTimeout(timeout);controller.abort();};
  },[identifier,retry]);
  useEffect(()=>{if(error)errorRef.current?.focus();},[error]);
  useEffect(()=>{if(snapshot&&retry>0)headingRef.current?.focus();},[snapshot,retry]);
  const data=snapshot?.data;
  const limits=data?extrema(data.categories):null;

  function compare(event:FormEvent) {
    event.preventDefault();if(!data)return;
    const a=data.categories[left],b=data.categories[right];
    const delta=difference(data.categories,left,right);
    const message=left===right?'異なる2つの項目を選択してください。':a.value===null||b.value===null?'未確定の数値を含むため比較できません。':delta===null?'差を正確に表示できないため比較できません。教員に確認してください。':`${a.label}（${formatNumber(a.value)}）から${b.label}（${formatNumber(b.value)}）を引いた差は ${formatNumber(delta)} ${data.unit??'（単位未確定）'} です。`;
    setComparison(message);setAnnouncement(n=>n+1);
  }

  return <>
    <a className="skip" href="#main">メインコンテンツへ移動</a>
    <header><a className="brand" href="/">ChartBridge</a><span className="workspace">学生用教材</span></header>
    <main id="main">
      {!data&&<h1>承認済み教材を開く</h1>}
      {error&&<><div className="error" role="alert" tabIndex={-1} ref={errorRef}>{error}</div><button onClick={()=>setRetry(n=>n+1)}>もう一度読み込む</button></>}
      {!snapshot&&!error&&<p role="status">承認済み教材を読み込んでいます。</p>}
      {data&&<>
        <div className="eyebrow">教員確認済みのデータ</div>
        <h1 ref={headingRef} tabIndex={-1}>{data.title}</h1>
        <p>単位：{data.unit??'未確定'}</p>
        <p className="muted">未確定の数値は計算に使いません。表示と比較は同じ承認済みデータを使っています。</p>
        <section className="panel" aria-labelledby="table-heading">
          <h2 id="table-heading">データを読む</h2>
          <div className="table-wrap"><table><caption>{data.title}の承認済みデータ</caption>
            <thead><tr><th scope="col">項目</th><th scope="col">数値{data.unit?`（${data.unit}）`:''}</th></tr></thead>
            <tbody>{data.categories.map((c,i)=><tr key={i}><th scope="row">{c.label}</th><td>{c.value===null?'未確定':formatNumber(c.value)}</td></tr>)}</tbody>
          </table></div>
        </section>
        <section className="panel student-section" aria-labelledby="extrema-heading">
          <h2 id="extrema-heading">最大値・最小値を確認</h2>
          {limits?(data.categories.length-limits.excluded===1?<><p className="notice">確定している数値は1件だけです。全項目の最大値・最小値はまだ判断できません。</p><p>確認できた値：{limits.maxLabels.join('、')}、{formatNumber(limits.max)} {data.unit??'（単位未確定）'}</p></>:<>{limits.excluded>0&&<p className="notice">未確定の項目があります。全項目の最大値・最小値は確定していません。</p>}<p>{limits.excluded>0?'確認できた範囲の最大値':'最大値'}：{limits.maxLabels.join('、')}、{formatNumber(limits.max)} {data.unit??'（単位未確定）'}</p><p>{limits.excluded>0?'確認できた範囲の最小値':'最小値'}：{limits.minLabels.join('、')}、{formatNumber(limits.min)} {data.unit??'（単位未確定）'}</p><p className="muted">未確定の{limits.excluded}項目を除外した結果です。</p></>):<p>確定した数値がないため、最大値・最小値を計算できません。</p>}
        </section>
        <section className="panel student-section" aria-labelledby="compare-heading">
          <h2 id="compare-heading">2つの項目を比較</h2>
          <form onSubmit={compare}>
            <div className="comparison-controls">
              <div><label htmlFor="compare-left">比較する項目</label><select id="compare-left" value={left} onChange={e=>{setLeft(Number(e.target.value));setComparison('');}}>{data.categories.map((c,i)=><option value={i} key={i}>{c.label}{c.value===null?'（未確定）':''}</option>)}</select></div>
              <div><label htmlFor="compare-right">差し引く項目</label><select id="compare-right" value={right} onChange={e=>{setRight(Number(e.target.value));setComparison('');}}>{data.categories.map((c,i)=><option value={i} key={i}>{c.label}{c.value===null?'（未確定）':''}</option>)}</select></div>
            </div>
            <button>数値を比較する</button>
          </form>
          <p role="status" aria-atomic="true"><span key={announcement}>{comparison}</span></p>
        </section>
        <p className="muted">承認日時：<time dateTime={snapshot!.approved_at}>{new Date(snapshot!.approved_at).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo'})} JST</time>。この版は変更されません。</p>
      </>}
    </main>
  </>;
}
