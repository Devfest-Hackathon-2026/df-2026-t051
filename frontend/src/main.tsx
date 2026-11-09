import React, { FormEvent, useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { onAuthStateChanged, signInWithEmailAndPassword, signOut, User } from 'firebase/auth';
import { auth, configureAuth } from './auth';
import { ReviewEditor, Saved, Snapshot, ReviewPhase } from './ReviewEditor';
import { SavedMaterials } from './SavedMaterials';
import { StudentView } from './StudentView';
import { Workflow } from './Workflow';
import './style.css';

type Draft = {status:'unreviewed';source:'demo'|'gemini';image_id?:string|null;extraction:{supported:boolean;reason:string|null;title:string|null;unit:string|null;categories:{label:string|null;value:number|null;evidence:string|null}[];warnings:string[]}};

function App() {
  const [demo, setDemo] = useState(false);
  const [ready, setReady] = useState(false);
  const [iam, setIam] = useState(false);
  const [persistence, setPersistence] = useState(false);
  const [user, setUser] = useState<User|null>(null);
  const [savedRecord,setSavedRecord]=useState<Saved|null>(null);
  const [savedSnapshot,setSavedSnapshot]=useState<Snapshot|null>(null);
  const [storedPreview,setStoredPreview]=useState('');
  const [refresh,setRefresh]=useState(0);
  const [serviceBaseUrl,setServiceBaseUrl]=useState('');
  const [publicAccess,setPublicAccess]=useState(false);
  const [reviewPhase,setReviewPhase]=useState<ReviewPhase>('extracted');
  const [operation,setOperation]=useState<'analyze'|'open'|null>(null);
  const [file, setFile] = useState<File|null>(null);
  const [preview, setPreview] = useState('');
  const [draft, setDraft] = useState<Draft|null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loginBusy, setLoginBusy] = useState(false);
  const resultRef = useRef<HTMLHeadingElement>(null);
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let active=true;let unsubscribe:undefined|(()=>void);
    fetch('/api/config').then(r => {if (!r.ok) throw Error(); return r.json();})
      .then(c => {if(!active)return;setDemo(c.demo === true); setIam(c.authMode === 'google_iam'); setPersistence(c.persistence === true); setServiceBaseUrl(c.serviceBaseUrl??'');setPublicAccess(c.publicAccess===true);setReady(true);const configured=configureAuth(c.firebase);if(configured)unsubscribe=onAuthStateChanged(configured,setUser);})
      .catch(() => setError('サーバーに接続できません。起動状況を確認してください。'));
    return()=>{active=false;unsubscribe?.();};
  }, []);
  useEffect(()=>()=>{if(storedPreview)URL.revokeObjectURL(storedPreview);},[storedPreview]);
  useEffect(()=>{if(!user&&!iam){setDraft(null);setFile(null);setStoredPreview('');setSavedRecord(null);setSavedSnapshot(null);setReviewPhase('extracted');}},[user,iam]);
  useEffect(() => {
    if (!file) { setPreview(''); return; }
    const url = URL.createObjectURL(file); setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => {if (draft) resultRef.current?.focus();}, [draft]);
  useEffect(() => {if (error) errorRef.current?.focus();}, [error]);
  async function login(e: FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (!auth) return;
    const form = new FormData(e.currentTarget); setLoginBusy(true); setError('');
    try {await signInWithEmailAndPassword(auth, String(form.get('email')), String(form.get('password')));}
    catch {setError('ログインできませんでした。メールアドレスとパスワードを確認してください。');}
    finally {setLoginBusy(false);}
  }
  async function analyze(e: FormEvent) {
    e.preventDefault(); setError('');setReviewPhase('extracted'); setDraft(null);setSavedRecord(null);setSavedSnapshot(null);setStoredPreview('');
    if (!file) {setError('グラフ画像を選択してください。'); return;}
    if (!['image/png','image/jpeg'].includes(file.type) || file.size > 5*1024*1024) {
      setError('PNGまたはJPEG、5 MiB以下の画像を選択してください。'); return;
    }
    setBusy(true);setOperation('analyze');
    const controller = new AbortController(); const timeout = setTimeout(() => controller.abort(), 60000);
    try {
      const body = new FormData(); body.append('file', file);
      const headers: Record<string,string> = {};
      if (user) headers.Authorization = `Bearer ${await user.getIdToken()}`;
      const res = await fetch('/api/analyze', {method:'POST', body, headers, signal:controller.signal});
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '入力内容を確認してください。');
      setDraft(data);setReviewPhase('extracted');
    } catch (err) {setError(err instanceof Error && err.name !== 'AbortError' ? err.message : '解析が時間切れになりました。再試行してください。');}
    finally {clearTimeout(timeout); setBusy(false);setOperation(null);}
  }
  async function openSaved(record:Saved) {
    setBusy(true);setOperation('open');setError('');
    try {
      const headers:Record<string,string>={};if(user)headers.Authorization=`Bearer ${await user.getIdToken()}`;
      const response=await fetch(`/api/drafts/${record.id}`,{headers});if(!response.ok)throw Error('教材を開けません。');
      const fresh:Saved=await response.json();if(!fresh.original)throw Error('元の解析結果がありません。');
      let image='';
      if(fresh.image_id){const res=await fetch(`/api/images/${fresh.image_id}`,{headers});if(!res.ok)throw Error('元画像を開けません。');image=URL.createObjectURL(await res.blob());}
      let approved:Snapshot|null=null;
      if(fresh.status==='approved'){const res=await fetch(`/api/drafts/${fresh.id}/approved`,{headers});if(!res.ok)throw Error('承認版を開けません。');approved=await res.json();}
      setFile(null);setStoredPreview(image);setSavedRecord(fresh);setSavedSnapshot(approved);setReviewPhase(approved?'approved':'saved');
      setDraft({status:'unreviewed',source:'gemini',extraction:fresh.original,image_id:fresh.image_id});
    }catch(e){setError(e instanceof Error?e.message:'教材を開けません。');}finally{setBusy(false);setOperation(null);}
  }
  return <>
    <a className="skip" href="#main">メインコンテンツへ移動</a>
    <header><a className="brand" href="/" aria-label="ChartBridge ホーム"><span className="brandmark" aria-hidden="true">▥</span> ChartBridge</a><span className="workspace">教員ワークスペース</span></header>
    <main id="main">
      <div className="eyebrow">グラフを、学びの架け橋に。</div>
      <h1>画像の向こうにある、<br/>データを届けよう。</h1>
      <p className="intro">教材のグラフを読み取り、誰もが探索できるデータへ。<br/>まずは画像をアップロードして、読み取り結果を確認しましょう。</p>
      <Workflow ready={ready} authenticated={demo||iam||!!user} hasFile={!!file} hasResult={!!draft} phase={reviewPhase} operation={operation} demo={demo}/>
      {demo && <p className="notice">ローカルデモ：固定の操作確認データを表示します。アップロード画像の解析・保存・公開は行いません。</p>}
      {iam && <p className="notice">非公開IAM検証環境です。認証付きのローカルプロキシから操作してください。実Gemini APIで画像を解析します。</p>}
      {!demo && !iam && !user && <section className="panel login" aria-labelledby="login-title"><h2 id="login-title">教員ログイン</h2>{auth ? <form onSubmit={login}><label>メールアドレス<input name="email" type="email" autoComplete="username" required/></label><label>パスワード<input name="password" type="password" autoComplete="current-password" required/></label><button disabled={loginBusy}>{loginBusy ? 'ログイン中…' : 'ログイン'}</button></form> : <p>Firebaseの接続設定が必要です。設定後に教員アカウントでログインできます。</p>}</section>}
      {user && <p>ログイン済み：{user.email} <button className="secondary" onClick={() => auth && signOut(auth).catch(() => setError('ログアウトできませんでした。'))}>ログアウト</button></p>}
      {persistence&&(iam||user)&&<SavedMaterials user={user} refresh={refresh} onOpen={openSaved}/>}
      {error && <div className="error" ref={errorRef} tabIndex={-1} role="alert"><strong>操作を完了できませんでした</strong><p>{error}</p></div>}
      <div className="layout">
        <section className="panel" aria-labelledby="upload-title"><div className="section-head"><span className="number">01</span><h2 id="upload-title">グラフ画像を選択</h2></div><p className="muted">数値ラベルが付いた、単系列の縦棒グラフに対応しています。</p>
          <form onSubmit={analyze} aria-busy={busy}>
            <div className="upload"><span className="upload-icon" aria-hidden="true">↥</span><label htmlFor="chart-file">教材のグラフ画像</label><p id="file-help">PNG / JPEG · 5 MiB以下 · 2〜12項目<br/>32px以上・1200万画素以下の静止画</p><input id="chart-file" type="file" accept="image/png,image/jpeg" aria-describedby="file-help" disabled={busy} onChange={e => {setFile(e.target.files?.[0] ?? null); setDraft(null); setSavedRecord(null);setSavedSnapshot(null);setStoredPreview('');setReviewPhase('extracted');setError('');}}/></div>
            {(storedPreview||preview) && <figure><img src={storedPreview||preview} alt="照合用の元グラフ"/><figcaption>{file?.name??'保存済みの元画像'}</figcaption></figure>}
            <button className="primary" disabled={busy || !ready || (!demo && !iam && !user)}>{busy ? '読み取り中…' : demo ? '固定デモデータを表示' : 'グラフを読み取る'}<span aria-hidden="true"> →</span></button>
            <p className="privacy">画像は解析のためGeminiへ送信します。個人情報を含む画像は使用しないでください。{persistence?'解析に成功した画像は教員本人だけが再確認できる非公開ストレージへ保存します。教材データは「保存」を選んだときFirestoreへ保存します。':'この環境では画像・結果を保存しません。'}</p>
          </form>
        </section>
        <section className="panel results" aria-labelledby="result-title" aria-busy={busy}><div className="section-head"><span className="number">02</span><h2 id="result-title" ref={resultRef} tabIndex={-1}>読み取り結果</h2>{draft && <span className="badge">AI抽出・未検証</span>}</div>
          <div role="status" aria-live="polite">{busy ? operation==='open'?'保存済みの教材と元画像を読み込んでいます。':'画像を読み取っています。最大1分ほどお待ちください。' : ''}</div>
          {draft ? <><p className="notice">AIの読み取り結果です。桁表記を含む値は安全のため未確定にする場合があります。保存・承認した教材とは別に保持します。配布する値と承認状態は、下の教員確認データで管理します。数値の桁と単位も照合してください。</p><h3>{draft.extraction.title ?? 'タイトル未確定'}</h3><p>単位：{draft.extraction.unit ?? '未確定'}</p><div className="table-wrap"><table><caption>AI抽出データ（教員確認前）</caption><thead><tr><th scope="col">項目</th><th scope="col">数値</th><th scope="col">画像内の表記</th></tr></thead><tbody>{draft.extraction.categories.map((c,i) => <tr key={i}><th scope="row">{c.label ?? `項目${i+1}：未確定`}</th><td>{c.value === null ? <span className="unknown">未確定</span> : c.value}</td><td>{c.evidence ?? '読み取れません'}</td></tr>)}</tbody></table></div>{draft.extraction.warnings.length > 0 && <ul className="warnings">{draft.extraction.warnings.map((w,i) => <li key={i}>{w}</li>)}</ul>}<details><summary>構造化JSONを確認</summary><pre>{JSON.stringify(draft, null, 2)}</pre></details>{persistence&&draft.source==='gemini'?<ReviewEditor key={savedRecord?.id??draft.image_id??"new"} extraction={draft.extraction} user={user} imageId={draft.image_id} initialSaved={savedRecord} initialSnapshot={savedSnapshot} serviceBaseUrl={serviceBaseUrl} publicAccess={publicAccess} onSaved={()=>setRefresh(r=>r+1)} onPhaseChange={setReviewPhase}/>:<p className="muted">編集・保存には接続済みの実サービス環境が必要です。</p>}</> : <div className="empty"><span aria-hidden="true">▥</span><h3>ここから、読めるデータへ。</h3><p>画像を読み取ると、タイトル・項目・数値が<br/>ここに表示されます。</p><p className="small">不明な数値は推測せず「未確定」と表示します。</p></div>}
        </section>
      </div>
      <aside className="principle"><strong>確かめてから、届ける。</strong><p>AIの読み取りは学びの出発点。教員による確認を経て、安心して使える教材につなげます。</p></aside>
    </main><footer><span>ChartBridge</span><span>GDGoC Japan Hackathon 2026 · 教員確認から学生の学びへ</span></footer>
  </>;
}
const studentPath=window.location.pathname.match(/^\/learn\/([^/]+)$/);
createRoot(document.getElementById('root')!).render(<React.StrictMode>{studentPath?<StudentView identifier={studentPath[1]}/>:<App/>}</React.StrictMode>);
