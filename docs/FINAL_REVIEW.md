> この文書は以前の時点の記録です。2026-11-06の一般公開後の状態・追加日本語評価・操作確認は [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md) を参照してください。過去の数値と当時の公開状態は履歴として保持しています。

> この文書は2026-11-05の検証記録です。最新の状態・手動確認は[DAY5_REVIEW.md](DAY5_REVIEW.md)を参照してください。現在、NVDAの再インストールは要求しません。

# ChartBridge — Day 3・Day 4 最終確認ガイド

作成日：2026-11-05（JST）。実装・自動検証は完了。下記の人手・NVDA検証は未実施で、成功と見なしていません。
Cloud Run：`chartbridge-00006-fbd`。IAM非公開を維持。課金紐付け・一般公開・重要な権限の追加変更はしていません。

## 1. 今すぐ開く画面（実クラウド）

- [教員画面](http://127.0.0.1:8086/)
- [学生画面：12と18の教材](http://127.0.0.1:8086/learn/6e82255769754683ac39e699f4e97272) — 最大18、最小12、BからAを引いた差6
- [学生画面：未確定を含む教材](http://127.0.0.1:8086/learn/ccfa65201ccd47bf9f9fdd7934dcfa83) — Aは編集試験で13へ変更、Bはnull。画像の正解とは区別する試験教材
- [本来の共有URL](https://chartbridge-gqe6dtznpq-an.a.run.app/learn/6e82255769754683ac39e699f4e97272) — 未認証の直接アクセスは403。故障ではなくIAM保護

localhostの入口はCloud RunへIAM認証を付けるプロキシです。アプリ・Gemini・Firestore・GCSはクラウドで動きます。
学生画面の検証にFirebase教員ログインは不要ですが、外側のCloud Run IAMは必要です。現状は一般の学生へ無認証配布できません。

## 2. 起動方法（PowerShell）

作業フォルダ：`C:\Users\PC_User\Documents\ChatGPT\GDGoc Japan 2026`

### 実クラウドを操作する入口

```powershell
Set-Location 'C:\Users\PC_User\Documents\ChatGPT\GDGoc Japan 2026'
.\.venv\Scripts\python.exe scripts/private_proxy.py --url https://chartbridge-gqe6dtznpq-an.a.run.app --gcloud "C:\Users\PC_User\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" --port 8086
```

既に8086が起動中なら追加起動は不要です。gcloudは許可された本人アカウントでログイン済みである必要があります。
教員画面には設定済みのFirebaseメール／パスワードでログインしてください。指定アカウントのteacher claimは前段で付与済みです。パスワードやtokenをチャット・ログへ送らないでください。

### 完全ローカルの画面確認用デモ

```powershell
.\scripts\dev.ps1 -Demo
```

別ターミナルで：

```powershell
.\scripts\dev-web.ps1
```

[ローカルデモ](http://127.0.0.1:5173/)は固定データです。Gemini・保存・承認の実検証には使いません。依存関係の新規インストール方法はREADMEを参照。

## 3. 最後に一度まとめて行う利用者確認（すべて人手未実施）

| ID | 操作 | 期待すること | 人手結果 |
|---|---|---|---|
| M01 | 教員画面へ本人がログイン | メール表示と保存教材一覧を確認 | 未実施 |
| M02 | `evaluation/fixed-v1/E03.jpg`をアップロード | タイトル・項目・数値・単位を元画像と照合 | 未実施 |
| M03 | 任意の値を一時変更→保存→再読み込み→教材を開く | 保存値と非公開元画像が復元される | 未実施 |
| M04 | 元画像の正解値へ戻して保存→確認チェック→承認 | 共有URLが現れ、その版は編集できない | 未実施 |
| M05 | 「学生向け教材を開く」 | 別URLの承認済み表が開き、表示は承認値と同一 | 未実施 |
| M06 | Tab・Shift+Tab・矢印・Enterだけで2値比較 | 選択・比較が可能で、差と項目名が表示される | 未実施 |
| M07 | 上の未確定教材でBを含む比較 | 比較を拒否。Bを0として扱わない | 未実施 |
| M08 | 同じ2項目を繰り返し比較 | 結果が再通知される（音声はNVDAで別確認） | 未実施 |
| M09 | `/learn/not-a-material`を直接開く | 日本語エラーへフォーカス。「もう一度読み込む」が操作可能 | 未実施 |
| M10 | ブラウザで200%拡大、DevToolsで320/390px | 主要操作が隠れず、ページ全体の横スクロールが不要 | 未実施 |
| M11 | ログアウト | 教材一覧・元画像・編集データが画面に残らない | 未実施 |

スマートフォン幅の自動検証はChromiumエミュレーションです。実機のiOS/Android、VoiceOver/TalkBackは未検証です。
プロキシはloopback専用なので、電話からPCのlocalhostへ直接アクセスできません。確認のために一般公開や0.0.0.0 bindへ変更しないでください。

## 4. NVDAの手動試験（すべて未確認）

この環境ではNVDAコマンドと標準インストール先を検出できず、実際のNVDA操作・音声確認は行っていません。
必要なら本人が[公式NV Accessサイト](https://www.nvaccess.org/download/)からNVDAを準備してください。
NVDAの修飾キーは設定したInsertまたはCaps Lockです。以下の操作は[公式ユーザーガイド](https://download.nvaccess.org/documentation/userGuide.html)に基づきます。

1. NVDAとChromeまたはEdgeを起動し、ブラウザ・NVDAバージョン、音声言語、キーボード配列を記録する。
2. 学生用URLを開き、見出し移動（H）で教材名、データ、最大最小、比較へ移れるか確認する。
3. 表移動（T）、Ctrl+Alt+矢印でセルを移動し、表題・項目名・数値列見出し・単位を把握できるか確認する。
4. 未確定セルが「0」でなく「未確定」と読まれるか確認する。
5. Tabで2つの選択欄へ移り、名前と選択項目が分かるか確認する。必要ならNVDA+Spaceでブラウズ／フォーカスモードを切り替える。
6. 矢印でBとAを選び、比較ボタンをEnterで実行。フォーカスを動かさず差6の通知が聞こえるか確認する。
7. 同じ比較をもう一度実行し、同じ結果も通知されるか確認する。
8. 未確定を選んだ場合の比較不能通知、同一項目を選んだ場合の案内を確認する。
9. 不正URLでエラーへフォーカスし、エラー文を読めるか確認する。再試行ボタンを操作する。
10. 教員画面でもファイル選択、表編集、保存状態、確認チェック、承認完了の読み上げを確認する。

| NVDA確認項目 | 判定 | 観測した文言・問題 |
|---|---|---|
| 見出しとランドマーク移動 | 未実施 | |
| 表題・行列見出し・単位 | 未実施 | |
| 未確定値と最大最小 | 未実施 | |
| 選択欄の名前と選択状態 | 未実施 | |
| 比較結果のlive region通知 | 未実施 | |
| 同一結果の再通知 | 未実施 | |
| エラー・再試行・復帰フォーカス | 未実施 | |
| 教員のファイル選択・編集・承認 | 未実施 | |

自動axe合格やDOM更新の確認だけでは、実際の読み上げ順序・理解しやすさ・通知を保証できません。

## 5. 自動試験の最終結果

| 区分 | 成功 | 失敗 | 試験の性質 |
|---|---:|---:|---|
| Python API・ユニット | 40 | 0 | TestClient、provider/auth/DBのfakeを含む |
| 学生計算 | 4 | 0 | 実関数。null・0・負数・同値・小数・微小値・丸め拒否 |
| ローカルブラウザE2E | 12 | 0 | 既存デモ2、学生用mock API 10。実Geminiとは別 |
| Firestore Rules | 45 | 0 | 反映済みsourceへのRules管理APIによる認証／操作コンテキスト試験 |
| 実クラウド統合E2E | 1 | 0 | 実Firebase・Gemini・GCS・Firestore・Cloud Run、58.4秒 |
| 合計（固定画像評価を除く） | 102 | 0 | 型検査・build・pip checkは件数に含めない |

TypeScript、Vite本番ビルド、pip checkも成功。StarletteのTestClientにhttpx非推奨警告が1件あり、実行失敗ではありません。
期限切れtokenのSDK例外は単体試験、無効tokenと実token失効後の拒否は実クラウドでも検証。実際に期限が切れるまで1時間待つ試験はしていません。
実Firebaseの別教員による教材・画像へのアクセスは404、教員claimなしは403、未承認GETは404、承認後の更新は409。
Firestoreへの直接アクセスは実教員・学生tokenで403。GCS匿名取得も403。API側の認可はRulesに依存せず維持しています。
学生の閲覧・比較から解析APIへの呼び出しは0回。承認版の内容が変わらないことも検証済みです。

axeは教員・学生・不正URL・320/390/1280pxの実クラウド画面と、ローカルのエラー・全null・長い12項目等の検査対象で違反0件。
[実E2E証跡](verification/firebase-full-flow.json)、[スマホ幅の画像](verification/student-live-320.png)、[セキュリティ証跡](verification/cloud-security.json)を参照。

## 6. 18グラフ固定評価（実Gemini、初回）

評価前に画像・正解・採点をローカルGitの`69e2f13`／`7b13e70`で固定しました。データは開発用fixtureから分離。
モデル`gemini-3.8-flash`、18枚・107値。PNG12・JPEG6、easy6・standard8・hard4。全数値ラベル付き単系列縦棒、2〜12項目。

| 指標 | 実測 |
|---|---|
| 数値 | 107/107 |
| カテゴリ | 107/107 |
| 単位・タイトル | 18/18・18/18 |
| 画像全体一致 | 18/18 |
| 誤認識・API失敗・スキーマ失敗 | この初回評価では0 |
| 確定値に対するnull出力 | 0 |
| 平均・中央値・最大 | 5.666・5.591・7.479秒 |
| 18件の処理時間合計 | 101.987秒 |

ネットワークとGeminiを含むローカル抽出時間で、Cloud Run／GCS保存は含みません。
抽出プロンプト・モデル選択・Extractionスキーマは結果に合わせて調整していません。画像正規化のEXIF／透明背景修正でも、この18枚のモデル入力は全てbyte-identicalと別途確認。
数値の正解はすべて確定値なので、null0件は曖昧値安全性の証明ではありません。曖昧値は別fixtureと計算／実クラウド試験で検証しました。
これは明瞭な合成データ上の結果です。実教科書、写真、手書き、強い圧縮や傾きに一般化できる成功率ではありません。
[全画像・個票・採点・時間](../evaluation/RESULTS.md)と[生の結果](../evaluation/results/fixed-v1-first-run.json)を参照。

## 7. 修正した不具合

- 学生の通信失敗時に再試行できず、英語のブラウザ例外が出る場合があった。日本語案内、20秒timeout、再試行、エラー／復帰フォーカスを追加。
- 同じ比較結果を繰り返すとDOM更新がなく通知されない可能性があった。安定したstatus領域内の内容を毎回更新。音声での最終確認は未実施。
- 極端な数値差でNumberへの変換により丸めた結果を表示し得た。正確に表現できない差を拒否。
- 不正な学生URLでJSONエラーまたは教員画面になり得た。学生用の日本語エラー画面へ統一。
- カメラJPEGのEXIF回転、透過PNGの白背景合成を修正。正規化後の元画像照合を安定化。
- Firebaseの同時cold start初期化をロックし、同じ名前付きappを再利用するよう修正。
- ブラウザテストがNodeの計算テストも副作用実行していたため、*.spec.tsだけに対象を限定。

## 8. 再実行するテスト

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'backend')
.\.venv\Scripts\python.exe -m pytest backend/tests -q
node --experimental-strip-types --test frontend/tests/math.test.ts
Push-Location frontend
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
node node_modules/@playwright/test/cli.js test
Pop-Location
.\.venv\Scripts\python.exe scripts/test_rules.py
.\.venv\Scripts\python.exe scripts/verify_firebase_flow.py
```

最後の実クラウド試験は8086プロキシ、gcloud管理者認証、`.tmp/firebase-web.json`を使います。実API操作の料金が少量発生し、一時試験アカウント3名を作成・削除します。既存本人アカウントや教材は削除しません。
固定評価の初回結果は上書き禁止です。再評価をする場合は別の結果名で保存し、同じデータの独立最終評価と呼ばないでください。

## 9. 残存リスクと次に優先すること

1. NVDA実音声・非視認操作は上記すべて未実施。自動試験で代替できない。
2. 固定評価は合成18枚に偏る。第三者作成の実教材で追加検証が必要。
3. IAM非公開のため一般学生への無認証配布は未実施。公開変更には別途承認が必要。
4. 元画像未保存の旧教材は復元不能。旧IAM ownerをFirebase UIDへ自動移管しない。
5. 一覧は100件上限。画像保管期限・削除導線・アカウント運用、ユーザー別課金保護は今後の運用課題。最大1インスタンスは課金額の上限ではない。
6. 数値はJSON Numberの有限精度を持つ。正確に表現できない差は拒否するが、科学技術計算用の任意精度基盤ではない。
7. ログのキー検査は取得した直近200件等の範囲であり、全期間の保証ではない。GeminiキーはSecret Manager参照を維持。

公式提出リポジトリへのpushは行っていません。最終Git情報はこの文書と同じ変更のコミットを`git log`で参照できます。
