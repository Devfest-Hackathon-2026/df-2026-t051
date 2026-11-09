> これは2026-11-05時点の旧開発READMEを保存した履歴資料です。最新の審査案内はルートREADME、現在の確認項目はDAY5_REVIEW.mdを参照してください。

# ChartBridge

グラフを、学びの架け橋に。視覚障害のある学生の自立したデータ探索を、画像解析→教員確認→承認済み教材の配布で支援します。

Day 3・4統合検証の結果、起動方法、教員／学生画面、最後にまとめて行うNVDA手動チェックは[最終確認ガイド](FINAL_REVIEW.md)に集約しています。固定18グラフの実測は[evaluation/RESULTS.md](../evaluation/RESULTS.md)。

## 実接続・クラウド検証

Firebase教員ログイン、非公開元画像の保存・教材再開、承認済み共有URL、学生用の表・最大最小・2値比較を追加しています。
Cloud RunはIAM非公開を維持しています。現在の操作・権限設計は[教員→学生ワークフロー](teacher-student-workflow.md)を参照してください。

実Gemini（`gemini-3.8-flash`）でPNG・JPEG解析と不明数値のnull保持を確認済み。
[Cloud Run](https://chartbridge-gqe6dtznpq-an.a.run.app)へソースデプロイ済み。IAM非公開のため通常アクセスは403です。
[認証付きプロキシの操作手順](private-validation.md)を使ってクラウド上の画面を操作できます。
教員編集表、Firestoreへの未承認保存、版番号による競合検知、承認時の独立snapshot作成を追加しています。
Firebase教員アカウントには管理者によるteacher claimが必要です。学生向け共有もIAM保護内での利用で、一般公開していません。
最新の検証結果は[教員・学生フローの実装報告](continuation-report.md)、初回配備の記録は[実接続・デプロイ報告](live-deployment-report.md)を参照してください。

## 初期実装：Day 1（2026-11-05）

PNG/JPEGアップロード、Gemini構造化抽出アダプター、タイトル・単位・カテゴリ・数値の未承認表示、元画像preview、JSON表示、入力検証とアクセシブルなエラー処理を実装。
対応は全数値ラベル付きの単系列縦棒グラフ・2〜12カテゴリ。読み取れない値は`null`です。
Firebase教員認可を実装。Firebase実認証は未確認で、現在のクラウド検証はGoogle IAMの許可ユーザーで行っています。
Day 1当初は学生向け共有・比較は未実装でした。現在は上記のワークフローとして実装・検証しています。

## 起動（Python 3.12 / Node.js 22 / pnpm 11.25.0）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
cd frontend
pnpm install --frozen-lockfile
cd ..
.\scripts\dev.ps1 -Demo
```

別ターミナルで：

```powershell
.\scripts\dev-web.ps1
```

[ローカル画面](http://127.0.0.1:5173) を開きます。デモでは有効な画像をアップロードすると固定データを表示します。Geminiによる画像解析結果ではありません。
試験画像は`backend/tests/fixtures/sample.png`です。

### 実Gemini／Firebase接続

1. `frontend/.env.example`を`frontend/.env.local`にコピーしてFirebase公開web設定を入力。
2. FirebaseでEmail/Passwordを有効にし、管理者が教員アカウントに`teacher: true` custom claimを付与。再ログインしてtokenを更新。
3. サーバープロセスに`GEMINI_API_KEY`、`GEMINI_MODEL`、`FIREBASE_PROJECT_ID`を安全に設定。ローカルのAdmin SDKにはADC（Application Default Credentials）も必要。キー値を履歴やコミットに残さないこと。
4. `scripts/dev.ps1`を`-Demo`なしで実行。フロントエンドのViteを再起動。

`.env.example`は設定項目の見本で、自動読込はしていません。Geminiキーを`VITE_`変数に置かないでください。

## テスト

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'backend')
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
pnpm build
pnpm exec playwright install chromium
# 別ターミナルでローカルデモAPIを起動しておく
pnpm test:e2e
```

実行結果・未検証範囲は[Day 1報告](day1-report.md)、設計は[architecture.md](architecture.md)、Cloud Runの準備は[deploy.md](deploy.md)を参照。
`docs/extraction.schema.json`はPydanticモデルから生成した解析JSON Schemaです。

## 開発と提出

大会公式：[Devfest-Hackathon-2026/df-2026-t051](https://github.com/Devfest-Hackathon-2026/df-2026-t051)。公式READMEは[原文](competition-readme.md)を保管。
公式リポジトリは最終提出用の公開リポジトリで、GitHub Actions・GitHub Pagesは使用禁止。
開発用private repository `chartbridge-dev` は未作成。現在はローカルGitで管理しています。公式リポジトリへのpushは未実施です。
2026-11-05 10:00 JST以降に新規実装しました。既存PoC／製品コードは流用していません。

提出は11月10日17:00 JSTまで。元の大会READMEのルールを保持し、コード・資料・実デプロイURLを配置してください。
開発履歴をそのまま公開リポジトリへpushせず、secret scan後に最終成果物だけを提出用checkoutへコピーします。

## ライセンス

本コードはMIT。依存OSSとライセンス確認は[THIRD_PARTY.md](THIRD_PARTY.md)を参照。
