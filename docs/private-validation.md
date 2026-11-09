# 実Gemini・非公開Cloud Run検証

プロジェクト：`chartbridge-gdgoc-2026` / リージョン：`asia-northeast1`

サービスURL：[ChartBridge（IAM非公開）](https://chartbridge-gqe6dtznpq-an.a.run.app)

通常の未認証ブラウザでは403になる。これは意図したアクセス制御である。
初回はGoogle IAMの許可ユーザーで検証した。現在はFirebaseの実教員ログインへ移行し、Cloud Run IAMは引き続き外側のアクセス制御として使っている。最新手順は[教員→学生ワークフロー](teacher-student-workflow.md)を参照。

## 非公開画面を操作する

gcloudでデプロイ時の許可アカウントにログインし、作業フォルダで次を実行する。

```powershell
.\.venv\Scripts\python.exe scripts/private_proxy.py --url https://chartbridge-gqe6dtznpq-an.a.run.app --gcloud "C:\Users\PC_User\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" --port 8085
```

[認証付きローカル入口](http://127.0.0.1:8085/)を開く。コンテンツと解析APIはCloud Run上で動き、localhostは認証ヘッダーを付与するプロキシにすぎない。
プロキシはloopbackにbindし、Host／Origin／cross-siteリクエストを検証する。Google ID tokenはプロキシのメモリだけで扱い、ブラウザへの配布やログ出力をしない。
Cloud Run IAM認証に加え、アプリでも別ヘッダーの完全なGoogle ID tokenを署名・issuer・audience・期限・verified email・許可リストで検証する。
許可ユーザー追加は`IAM_TEACHER_EMAILS`とCloud Run IAMの両方を管理者が設定する。環境変数で認証を無効化するモードは設けない。

## 実Geminiの再検証

サーバープロセスだけにGeminiキーを渡す。現在のWindowsユーザー環境変数を読み込む場合：

```powershell
$env:GEMINI_API_KEY = [Environment]::GetEnvironmentVariable('GEMINI_API_KEY','User')
$env:GEMINI_MODEL = 'gemini-3.8-flash'
.\.venv\Scripts\python.exe scripts/verify_gemini.py
```

キー値をechoしない。試験対象は個人情報のない自作PNG／JPEG／不鮮明ラベル画像のみ。結果は`docs/verification/gemini-live.json`に保存する。
選択モデルは実APIのモデル一覧で利用可能を確認し、画像理解・構造化出力の両方を実リクエストで確認した。[モデル仕様](https://aistudio.google.com/docs/models/gemini-3.8-flash)

## クラウドの再検証

上記プロキシを起動した状態で：

```powershell
cd frontend
node node_modules/@playwright/test/cli.js test --config playwright.live.config.ts
```

`cloud-live.json`と`cloud-live.png`に実際の画面・解析・保存・承認の検証証跡を保存する。一般のE2Eテストは`tests/`、実APIを呼ぶ試験は`live-tests/`に分離し、通常テストで意図せずAPI課金を発生させない。
`scripts/verify_cloud_security.py`は非公開IAM・Secret Manager参照・未認証拒否・キーの非露出を読み取り検査する。ログ検査は取得した時間範囲／件数に限定され、全期間を保証するものではない。

## リソースと費用

ユーザー承認に基づき課金を紐付けた。最小インスタンス0、最大1、1 CPU、512 MiB、同時リクエスト2、timeout 60秒。
Cloud Build、Artifact Registry、Secret Manager、Firestore、Gemini、Cloud Run利用量には料金が発生し得る。この設定は課金額の上限ではない。
GeminiキーはSecret Manager `chartbridge-gemini`の固定バージョン参照。build args・Dockerfile・ブラウザへキー値を渡さない。
ビルドは`chartbridge-builder`、実行は`chartbridge-runtime`の専用サービスアカウント。実行者には対象secretの読み取りとFirestoreデータ操作権限を付与。

## Day 2の保存モデル

元のAI抽出結果と教員の編集データを分け、教員による修正をAIの根拠表記として偽装しない。
`chartbridge_drafts`にowner UID、version、未承認データを保存。読み取り・更新・承認・承認版確認をすべて認証・owner確認する。
更新時はversionを検証し、古いデータでの上書きは409。承認はトランザクション内で独立した`chartbridge_snapshots`をcreateし、draftをロックする。
数値・単位のnullは保持する。タイトル・項目名の欠損と確認チェックなしでは承認しない。
承認版の更新・削除APIや、未認証での教材配信APIは作っていない。スナップショットはアプリAPI経由では変更不能だが、プロジェクト管理者の直接DB操作まで防ぐものではない。
FirestoreはNative mode・東京リージョン。サーバーSDKのみ使用し、ブラウザからFirestoreへ直接接続しない。

残作業：Firebaseの実教員運用、保存済み教材を再開する一覧／元画像の再照合導線、クライアントSecurity Rulesの明示・検証、学生用の承認版GET・共有URLと比較操作、NVDA試験、18グラフの固定評価。一般公開は別途承認が必要。
