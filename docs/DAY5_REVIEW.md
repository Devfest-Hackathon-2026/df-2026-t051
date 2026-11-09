> この文書は以前の時点の記録です。2026-11-06の一般公開後の状態・追加日本語評価・操作確認は [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md) を参照してください。過去の数値と当時の公開状態は履歴として保持しています。

# Day 5：操作・検証・提出前の確認

更新日：2026-11-06。Cloud RunはIAM非公開のまま。公式提出GitHubへのpush、一般公開、追加の課金設定変更はしていない。

## 今回の変更

- 教員画面の古いDay 1／準備中表示を更新。画像選択・AI解析・教員確認・承認・共有の5段階と次の操作を表示。
- 「AI抽出・未検証」と教材の未保存／未承認／承認済み状態を分ける。承認済み教材を開き直した場合は、新規承認と区別する。
- 既存承認版は承認データを表示し、編集不可。保存時はサーバーの正規化後データを採用する。
- 確定値1件では全体の最大・最小を表示しない。複数件でもnullが残る場合は「確認できた範囲」と明示する。
- 320／390／1280pxの表示、操作対象の大きさ、長い文の折り返しを改善。
- 実資料で観測した桁表記の不整合に対し、抽出根拠に千・万・億・兆があれば値をnullへ保留する。教員の換算・照合を必須にし、正解へ自動補正しない。
- ブラウザ回帰試験が専用APIを自動起動するよう修正。pytestの設定とfixtureパスを整備し、起動ディレクトリ依存を除いた。

## 最新の検証結果

詳細は[試験記録](verification/day5-tests.json)、[実Firebase・クラウドE2E](verification/firebase-full-flow.json)、[クラウド安全性](verification/cloud-security.json)を参照。

| 系統 | 最終結果 | 実サービスとの関係 |
|---|---|---|
| Python API・認証・不変性・入力・安全処理 | 46成功 | 外部サービスは差し替え、境界の回帰試験 |
| 学生の比較計算 | 4成功 | 通常プログラム、null除外・数値の安全性 |
| Playwright UI | 16成功 | デモAPI／モック、axe・キーボード・エラーフォーカス・幅の検証 |
| Firestore Rules | 45成功 | 現在のデプロイ済みルールに対するRulesテストAPI |
| Firebase→Gemini→保存→承認→学生比較 | 1シナリオ | 実クラウド、最終記録の時刻・結果を参照 |

合計112ケース。旧IAM教員モード専用のクラウド試験1件は、現在のFirebaseモードでは対象外としてスキップ。上のクラウド最終結果はJSON記録を正本とする。初期のブラウザ試験ではAPI未起動で2件失敗し、専用API自動起動後に全16件成功。API試験もimport／fixtureパスの起動依存を修正後に全46件成功。Starletteのhttpx非推奨警告が1件残るが、試験失敗ではない。

今回のクラウド再試験では、旧missing-label画像が422で拒否されたため全数値ラベル付き画像へ変更し、教員が数値を空欄へ戻す操作でnull経路を検証する。これはGeminiがnullを抽出した成功例とは数えない。その後、長い実ログインメールの文字が320px幅を越える不具合を検出し、折り返しを修正した。検出・原因調査中の失敗を隠さず、最終試験と区別する。

## 実測精度と制約

[合成18枚](../evaluation/RESULTS.md)：107/107値、全体18/18、平均5.666秒。
[農林水産省の実教材6枚](../evaluation/real-v1/RESULTS.md)：19/30値、カテゴリ20/30、タイトル4/6、単位4/6、全体3/6、平均18.145秒。桁・単位の不整合1枚、構造化出力の検証失敗2枚。画像・正解・採点は推論前にコミットして固定した。

実教材の原図は再配布しない。出典、利用条件、URL、ハッシュ、全個票を残した。失敗した画像も分母に含む。測定後の安全処理の効果を、この6枚で独立した精度向上として報告しない。漢字の桁を含む表記は教員の照合が必要。schemaエラーは502として停止し、利用者に再試行を案内する。精度・時間は一回の小規模試験で、一般化や性能保証をしない。

桁表記の保留処理はモデルが返すevidenceに依存する。モデルが誤った根拠表記を返す場合まで検出できず、教員の原図照合を代替しない。

## 起動・入口

### 実クラウドを本人のブラウザで使う

Google Cloud CLIにログイン済みで、Cloud Run呼び出し権限がある環境を使う。プロジェクトは`chartbridge-gdgoc-2026`。

```powershell
.\.venv\Scripts\python.exe scripts/private_proxy.py --url https://chartbridge-gqe6dtznpq-an.a.run.app --gcloud 'C:\Users\PC_User\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd' --port 8086
```

[教員画面](http://127.0.0.1:8086/)へアクセスし、登録した教員メールアドレスと本人だけが知るパスワードでログインする。パスワードをチャットやログへ送らない。
共有リンクのCloud Runホストは現在IAM非公開なので、そのまま別端末へ配布しても403になる。同じPCでの確認は、共有リンクの`/learn/教材ID`部分を`http://127.0.0.1:8086`へ付けて開く。公開済みデータだけを読むアプリAPIと、Cloud Runの入口IAM制御は別である。

### ローカルの固定データデモ

[READMEの依存導入](../README.md#ローカル起動と試験)後、別々のPowerShellで`./scripts/dev.ps1 -Demo`と`./scripts/dev-web.ps1`を実行し、[5173](http://127.0.0.1:5173/)へアクセスする。このデモはGeminiや永続保存の実試験ではない。

### 自動試験の再実行

作業フォルダをカレントにする。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
node --experimental-strip-types --test frontend/tests/math.test.ts
Push-Location frontend
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vite/bin/vite.js build
node node_modules/@playwright/test/cli.js test
Pop-Location
.\.venv\Scripts\python.exe scripts/test_rules.py
# 上の8086プロキシを別ターミナルで起動した状態で実行
.\.venv\Scripts\python.exe scripts/verify_firebase_flow.py
```

最後の2コマンドは管理者のクラウド認証・既存Firebase設定が必要。実E2EはGemini料金と保存物を発生させ、生成した一時認証ユーザーだけを終了時に削除する。本人のアカウントは変更しない。評価APIの再実行は課金・独立性への影響があるため、既存評価ログを上書きしない。

## 最後にまとめて手動確認する項目

- [ ] 教員でログインし、画像を選択して解析。進行段階と次の操作が分かるか確認する。
- [ ] 元画像のラベル・単位を見て数値を修正し、保存する。「未承認」を確認する。
- [ ] 照合チェック後に承認し、教材が編集不可になり共有URLを取得できることを確認する。
- [ ] 保存一覧から承認済み教材を開き直し、元画像と固定された値が表示されることを確認する。
- [ ] 学生URLを上記プロキシ経由で直接開き、Tab／Shift+Tab／矢印／Enterで2項目を選び比較する。見えるフォーカスと結果を確認する。
- [ ] nullがある教材で「未確定」と計算除外の説明、確定値1件で全体最大・最小を断定しない表示を確認する。
- [ ] PCと利用するスマートフォン相当の幅で文字・表・ボタンが使いやすいか確認する。
- [ ] [90秒台本](submission/DEMO_90_SECONDS.md)で説明し、必要なら動画を録画する。
- [ ] [公開案](PUBLICATION_PLAN.md)、[ライセンス](submission/LICENSES.md)、[提出ZIP](verification/submission-package.json)の内容を確認する。公式pushと一般公開は別途判断する。

## アクセシビリティの検証境界

Playwrightで見出し・表の名前、列／行見出し、選択欄、キーボード操作、比較結果のlive通知領域、未確定表示、エラー時フォーカス、直接URL、320／390／1280px表示を検証。axeの対象状態で違反0件、アクセシビリティツリーを[教員](verification/day5-teacher-live-aria.yml)と[学生](verification/day5-student-live-aria.yml)で保存する。

**NVDAなど実スクリーンリーダーの読み上げ順・音声通知・読みやすさは未検証。** ユーザーはNVDAをアンインストール済みで、再インストールを求めない。自動検証は読み上げ品質や実スマートフォンの支援技術を保証しない。視覚障害当事者による利用性試験も未実施。

## 提出物と残存リスク

審査README、[構成図とGoogle技術](submission/ARCHITECTURE.md)、[差別化](submission/DIFFERENTIATION.md)、実測資料、操作説明、90秒台本、ライセンス一覧を用意した。録画動画は未作成。
提出用ZIPは履歴・秘密情報・依存物・元画像キャッシュを除いたレビュー用スナップショットであり、公式提出済みではない。

公開前には解析利用枠、全体費用上限運用、公開GETへの対策等が残る。現状の最大インスタンス1は費用上限ではない。提案するサービス単位の公開IAM変更は、対策の実装・検証後に具体的な承認を得る。[公開計画](PUBLICATION_PLAN.md)に対象とリスクを記録した。
FirestoreのサーバーSDKはRulesを迂回するため、APIの教員claim・所有者検証が引き続き必須。公開版はアプリAPIで不変だが、プロジェクト管理者の直接変更まで防ぐ設計ではない。
