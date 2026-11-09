# 実接続・Cloud Run初回デプロイ報告（2026-11-05）

## 実際に確認した結果

Gemini実接続とCloud Run初回デプロイは成功。
プロジェクトは`chartbridge-gdgoc-2026`、Cloud Runは`asia-northeast1`、サービス名は`chartbridge`。
URL：[https://chartbridge-gqe6dtznpq-an.a.run.app](https://chartbridge-gqe6dtznpq-an.a.run.app)

非公開サービスなので、直接の未認証アクセスは403になる。[認証付きプロキシ](private-validation.md)経由で画面を利用する。
ローカルDockerエンジンは使わず、`gcloud run deploy --source .`でDockerfileをCloud Buildに渡した。

## Gemini実測

実モデル一覧の問い合わせで利用可能だった`gemini-3.8-flash`を選択。
個人情報のない自作PNGとJPEGから、タイトル「Students by class」、単位「people」、カテゴリA／Bと数値12／18を取得。
Bのラベルを不鮮明にした試験画像ではBのvalueとevidenceがnullとなった。
すべて既存Pydanticスキーマで検証し、推測値への置換はしていない。
これは3種類のスモーク試験であり、18グラフでの精度評価や一般的な成功率を示すものではない。
証跡：`verification/gemini-live.json`。

## クラウド上の実動作

最終リビジョン`chartbridge-00002-gwt`でReact表示、health応答、PNG／JPEGの実Gemini解析、不鮮明値の未確定表示をPlaywrightで確認（1 passed）。
証跡：`verification/cloud-live.json`、`verification/cloud-live.png`。
配信物はFastAPIから提供し、同一サービスの解析APIを呼んでいる。

セキュリティ検証ではCloud Run invoker IAMが有効でpublic IAM bindingがないこと、Secret Manager参照、未認証403、アプリ認証情報の欠損401を確認した。
GeminiキーがGit管理ファイル・本番ビルド・クラウド配信HTML/JS/CSS・取得したログに含まれないことを値を出力せず検査する。
証跡の検査件数と時刻は`verification/cloud-security.json`に記録。
外部のPublic GitHubリポジトリへのpushは行っていない。

## クラウド設定の変更

初回確認時には課金未紐付け、必要API未有効、gcloudはPATH外、キーはUserスコープのみでプロセスへ継承されていなかった。
gcloudの実パスを使用し、キー値を表示せずユーザー環境変数から必要な子プロセスだけへ渡した。
ユーザーの明示承認後、「My Billing Account」を対象プロジェクトへ紐付け、必要APIを有効化。
専用ビルド／実行サービスアカウントとSecret Managerの固定バージョンを作成。最小0・最大1インスタンス、非公開IAMを維持。
Firestore Nativeデータベースは東京リージョンに作成した。

## Day 2への着手

- AIの元抽出結果とは別の教員編集データ表を追加。
- Firestoreにowner付き未承認draftを保存。
- 保存時の版番号を検証し、古い版による上書きを409で拒否。
- タイトル／項目名の確認と明示チェックを承認に必須化。
- 承認トランザクションで独立snapshotをcreateし、draftを変更不能にする。
- 未確定の数値／単位はnullを保持。承認版を変更するAPIと未承認教材の公開APIは設けていない。

実Cloud Run／Firestoreでも、画面から数値修正→未承認保存→再修正保存→確認チェック→承認の操作に成功。
未承認での承認版GETは404、確認なし承認は422、古いversionの更新は409、承認後の更新／再承認も409。
承認済みスナップショットを再取得し、修正値13と未確定値nullが変わらないことを確認した。
これらの数値変更は編集機能の試験操作であり、画像の正解値として扱わない。元のAI抽出は12のまま別途保存される。
試験用の未承認draftと承認snapshotはFirestoreに残しており、実ユーザー情報は含まない。

サーバーSDKのみを使用。`firestore.rules`にはクライアントdeny-allを記録したが、Firebase Rulesサービスへの反映・実検証は未実施。
Firebase Authenticationの実教員アカウント・claim設定も未完了で、Google IAMによる許可ユーザー検証を使用している。

## テスト

- ユニット・API：31 passed（Starletteのhttpx非推奨警告1件）。
- 既存デモE2E：2 passed。
- TypeScript型チェックとVite本番ビルド：成功。
- 実クラウドE2E：Day 2反映後1 passed（38.0秒）。実Geminiと実Firestoreを使用。
- axe：実解析画面・承認後画面の自動検査で違反0件。
- NVDAと18グラフ評価：未実施。

## 残作業

Firebase教員認証の本運用、保存済み教材の再開導線・元画像照合、明示Security Rulesの反映と試験、学生用共有URL／承認済みGET／比較計算、NVDA・固定評価。
一般公開はしておらず、公開設定を変更する場合は別途ユーザー承認が必要。
Gitでの履歴をローカル管理し、private repository作成は今回の作業の前提にしていない。

## 発見・修正した問題

- gcloudはPATH外、Geminiキーは起動済みプロセスに未継承だった。実パスとUserスコープの安全な読込で解決。
- Firebaseの設定がないため既存の教員認証のままでは実解析を操作できなかった。Firebaseの本番運用を省略せず、非公開検証に限定してIAM＋Google ID token＋許可ユーザー確認を追加。
- 検証プロキシのPUT転送漏れでDay 2の更新試験が一度501になった。PUTを追加して再起動し、同じ実クラウドE2Eが成功。
- StarletteのTestClientからhttpx非推奨警告が1件ある。テストは成功。移行は後続保守事項。
