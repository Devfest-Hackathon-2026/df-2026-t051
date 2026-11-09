# Day 1 実装報告 — 2026-11-05

## 完了したこと

- 公式リポジトリのREADME、LICENSE、初期ファイル一覧を確認。公式側は変更していない。
- React / TypeScript / Vite / Tailwind CSS画面とFastAPI APIを新規作成。
- PNG/JPEG選択、元画像preview、Gemini SDK構造化抽出、未承認の表・JSON表示。
- 型・サイズ・画像実体・画素数・静止画検証、null保持、timeout、同時実行制限、機密を含まないエラー。
- Firebase ID tokenの検証とteacher claim認可。実接続の試験は未実施。
- ローカル専用の固定デモ。Cloud Run／非local環境でのデモ起動拒否。
- DockerfileとCloud Runデプロイ手順、環境変数見本、JSON Schema、ライセンス記録を追加。

## 実行した検証

| 検証 | 結果 |
|---|---|
| pytest ユニット・API | 21 passed |
| TypeScript `tsc --noEmit` | 成功 |
| Vite production build | 成功 |
| 固定lockfileでのoffline install / pip check | 成功 |
| FastAPIからのproduction静的HTML＋health APIスモーク | 成功 |
| Chromium Playwright E2E | 2 passed |
| axe-core（デモ結果表示画面） | 違反0件 |

API試験はmockを使ったteacher認可、失効・不正tokenのエラー処理、null保持、不正数値、欠損根拠、画像形式偽装、ファイル／stream上限、対応外結果、Gemini timeout・例外、SDK呼出し契約、公開API不在を確認。
E2Eはskip linkのキーボード操作、ファイル選択後のEnter実行、結果へのフォーカス、未承認／未確定表示、不正画像時のエラーフォーカスと再試行を確認。
OSのファイル選択ダイアログそのものは自動試験していない。認証系APIはmock試験であり実Firebase疎通ではない。

## 未実施・必要な設定

- Gemini実API：キーと利用可能なモデル設定がないため未実施。抽出精度は未測定。
- Firebase実認証：web設定、プロジェクト、ADC、教員アカウントとteacher claimが必要。
- Cloud Run：gcloudがなく、Google Cloudプロジェクト・実行権限未設定。Dockerエンジンも停止中。ビルド／デプロイは未実施、公開URLなし。
- `chartbridge-dev` private remote：接続GitHubツールに新規repo作成機能がなく、ghもない。ローカルGitのみで管理。
- 18グラフ評価、NVDA実機試験、Firestore、承認・公開snapshot、学生の比較機能は後続日程。

## 発見した技術的問題

- Windows標準のpythonはStore aliasで、利用可能なPythonはCodex同梱版。pnpmも同梱CLIを使用。一般環境ではPython 3.12 / Node 22 / pnpmを別途用意する。
- sandboxの一時フォルダでensurepipが失敗したため、workspaceの`.tmp`を使用してvenvを作成。
- 通常sandbox内ではTestClientが停止した。許可された実行環境では21テストが0.85秒で完了。
- StarletteのTestClientはhttpx利用の非推奨警告を1件出力。現行のAPIテストは成功している。将来httpx2対応時に追随する。
- 初回pnpm installは依存build scriptの未承認を報告。実ビルドは成功。esbuildだけ許可し、Firebase util / protobufjsのinstall hookは無効にする設定を明示した。
- 現状の同時解析制限はインスタンス内のみ。公開運用に向けてユーザー別制限・課金保護を追加検討する。

Day 2の実装順と不変条件は[day2-checklist.md](day2-checklist.md)を参照。
