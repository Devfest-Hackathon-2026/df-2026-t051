import type {ReviewPhase} from './ReviewEditor';
export function Workflow({ready,authenticated,hasFile,hasResult,phase,operation,demo}:{ready:boolean;authenticated:boolean;hasFile:boolean;hasResult:boolean;phase:ReviewPhase;operation:'analyze'|'open'|null;demo:boolean}) {
  const current=phase==='approved'?4:phase==='ready'?3:hasResult?2:hasFile||operation==='analyze'?1:0;
  const labels=['画像選択','AI解析','教員確認','承認','共有'];
  const message=!ready?'サーバーの接続設定を確認しています。':!authenticated?'次に：教員としてログインしてください。':operation==='open'?'保存済みの教材と元画像を読み込んでいます。':operation==='analyze'?'Geminiで画像を読み取っています。結果は教員確認前の抽出データです。':demo&&hasResult?'操作確認用データを表示しています。実サービスでは教員確認・保存・承認へ進めます。':phase==='approved'?'承認済み教材を表示しています。次に学生向け教材を開いて配布内容を確認してください。':phase==='ready'?'照合確認済みです。次に承認版を作成してください。承認後は変更できません。':hasResult?(phase==='saved'?'未承認の教材を保存済みです。次に照合確認チェックを付けてください。':'次に：元画像と項目・数値・単位を照合し、教員確認データを保存してください。'):hasFile?'画像を選択済みです。次に「グラフを読み取る」を実行してください。':'次に：数値ラベル付きの縦棒グラフ画像を選択してください。';
  return <><ol className="steps workflow" aria-label="教材作成の流れ">{labels.map((label,index)=><li key={label} className={index<current?'complete':index===current?'active':''} aria-current={index===current?'step':undefined}><b>{String(index+1).padStart(2,'0')}</b>{label}<span>{index<current?'完了':index===current?'現在':'次の工程'}</span></li>)}</ol><p className="workflow-message">{message}</p></>;
}
