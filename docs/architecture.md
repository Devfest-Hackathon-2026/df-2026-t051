# ChartBridge — Day 1 設計記録

2026-11-05に新規作成。既存PoC・製品コードは使用していない。

この文書はDay 1初期設計の記録。実接続・IAM非公開検証・Firestore承認実装の現在の構成は[private-validation.md](private-validation.md)を参照。

## 構成と境界

React 19 / TypeScript / Vite / Tailwind CSS → 同一originのFastAPI → Google GenAI SDK。
Firebase AuthenticationのID tokenをAdmin SDKで失効確認付き検証し、`teacher: true` のcustom claimを必須とする。
教員自身がこのclaimを付与できるAPIは設けない。管理者の信頼された環境からのみ設定する。

Cloud RunはReactの静的成果物とAPIを単一コンテナで配信する。CORSを開放しない。
解析APIは画像をメモリ内でデコードし、メタデータを除去したPNGだけをGeminiに送る。
画像・抽出結果・ID tokenを永続化／アプリログ出力しない。Google側のデータ利用条件は利用する契約・プロジェクトで確認する。

## 信頼モデル

Gemini構造化出力にもPydanticで再検証を行う。スキーマ準拠は数値の正確性を保証しない。
画像内の指示は信頼せず、印字数値のみ転記するようプロンプトで制約する。
数値には原表記を必須とするが、原表記そのものもモデル出力なので未検証。
`null`は欠損値として保つ。全結果の状態は`unreviewed`固定。公開・承認・計算APIはまだ存在しない。
未承認データを計算・公開する機能をDay 1に追加しない。

本番では認証・権限チェックを迂回できない。`LOCAL_DEMO=true`は`APP_ENV=local`かつCloud Run以外でのみ起動可能、接続元もloopbackに制限する。デモは固定データであり精度試験には使用しない。

## 実装上の制限

- 5 MiBのファイル上限、multipart全体にも上限。PNG/JPEGの実データ形式、ピクセル数、最小サイズ、静止画を検証。
- Geminiの待機は50秒、SDKのHTTP timeoutは45秒。アプリ単位で同時解析は2件、超過は429。課金上限やユーザー別レート制限は未設定。
- 共有・保存がないのでFirestoreはDay 2に導入。画像比較は選択ファイルのブラウザ内previewを使用。
- Geminiモデルは環境変数必須。プロジェクトの提供モデルを確認して設定し、利用不能なモデルに勝手にfallbackしない。
- Firebaseメール／パスワード認証を採用。Google popupを追加せず同一origin配信・CSPを簡素化した。アカウント作成UIはない。

## Day 2で守る永続化設計

draftにowner UIDを保存し、取得・更新・承認すべてでownerとteacher権限を確認する。
承認トランザクションでreviewedデータの独立したimmutable snapshotを作り、そのIDのみ公開URLに使う。
学生用GETは公開snapshotに限定し、draft・元画像・教員情報を返さない。
公開snapshotを編集するAPIは設けない。教員確認と公開snapshot作成を同時に行いTOCTOUを防ぐ。
Firestore client security rulesはdeny-allとし、Admin SDKからの操作はAPI側で認可する。

## 確認した公式仕様

- [大会README](https://github.com/Devfest-Hackathon-2026/df-2026-t051/blob/main/README.md)（初期ファイル：README.md / LICENSE / .gitignore）
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Firebase token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens)
- [Cloud Run secrets](https://docs.cloud.google.com/run/docs/configuring/services/secrets)
