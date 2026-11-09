> 承認後の実施結果：2026-11-06、同一digestの `chartbridge-00011-suh` を非公開再試験後に一般公開し、通常URLへ100%配信済み。試験タグは削除。以下は承認時の具体案を保持したものです。現在の状態は [最終監査](../PRODUCTION_AUDIT.md) と [公開監査JSON](public-security.json) を参照してください。

# 審査用公開の承認対象

2026-11-06。**まだ一般公開していない。** 現行通常URLは旧版 `chartbridge-00009-z6n` に100%。改善候補 `chartbridge-00010-lut` はIAM非公開・タグURLだけで検証済み。

## 選定：案A（既存Cloud Run＋Firebase認証）

| 比較 | A：既存サービス公開 | B：学生専用公開サービスを追加 |
|---|---|---|
| 教員のブラウザ利用 | Firebaseログインで利用できる | 既存のIAM非公開側にブラウザ認証の別入口が必要 |
| 公開面 | UIと全APIの入口。ただし教員操作は認可必須 | 学生APIだけに限定できる |
| 変更量・費用 | 検証済み同一イメージ、サービス1つ | 追加サービス、実行ID、配信分割、追加の運用・課金確認 |
| 守るべき境界 | 全APIでFirebase・teacher・owner、DB/GCS非公開 | 左記＋公開側のサーバーSDK権限／データ分離も必要 |
| 大会までの保守 | 既存E2Eをそのまま継続できる | 2系統の配信・CORS・認証入口・テストが増える |

今回はAを推奨する。Bは公開攻撃面を狭められるが、教員まで審査員がブラウザで利用する目的を単独では満たさず、追加構成を必要とする。Aの安全性はIAMを外すこと自体で確保するのではなく、既存のAPI認可と追加利用枠で確保する。

## 具体的変更と順序

固定イメージ：`sha256:b86c44a8a99fac8ab077ae1c3cb3cd2e17cbff39c17e1ea5c9c1e43a4cfabc4f`。
製品コード：`adb182fca2fd81f1f1eb0fe67870588e4262f52b`。
Cloud Build：`d90c1796-db71-49d8-a0a0-afed1771e7fa`、SUCCESS。

1. 同一digestから公開案内フラグ `PUBLIC_ACCESS=true` だけを変更したリビジョンを作成。IAM非公開・通常URLへの配信0%・`judge-ready`タグで作成する。Firebase、Secretバージョン1、実行SA、同時2、512Mi、CPU1、timeout60、最小0・最大1を維持する。
2. そのリビジョンで実Firebase／Gemini／Firestore／GCSのE2Eを再実行。実行リビジョン・digestに証跡を結び付け、合格しなければ公開しない。
3. 通常URLを新リビジョン100%に切り替え、試験タグ2つを削除する。旧版は削除せず、通常URL・タグから到達しない状態で保持する。
4. サービス `chartbridge` だけへ `allUsers:roles/run.invoker` を追加する。他のIAMロール、プロジェクト権限、Firestore Rules、GCS、課金設定は変更しない。
5. 認証なしの実HTTPでUI／学生GETの成功、教員API401、公開APIへの書込拒否、debug404を確認する。失敗時はIAMを閉じてから旧版100%へ復旧する。

自動適用は `scripts/publish_candidate.py` の承認ハッシュ照合を必要とする。既存の本番設定が承認用計画から変化した場合は停止する。違うリビジョンのE2E証跡では公開できない。IAM閉鎖が失敗した場合は、利用枠のない旧版へトラフィックを戻さず改善版を維持し、復旧未完了として記録する。この境界を模擬テスト4件で確認した。

## 公開するURL・API、保護する内容

- 通常URL：[ChartBridge](https://chartbridge-gqe6dtznpq-an.a.run.app/)。ログイン画面・静的アセット・公開Web設定は閲覧可。
- 学生URL：`/learn/{snapshot_id}`、`GET /api/materials/{snapshot_id}`。承認版のID、日時、タイトル、単位、項目・数値だけを返す。学生閲覧ではGeminiを呼ばない。
- `GET /api/health`、`GET /api/config` は認証不要。Firebase Web設定は公開用設定でありGemini秘密キーを含まない。
- 教員専用：`GET /api/me`、`POST /api/analyze`、`/api/drafts/**`、`GET /api/images/{id}`。Firebaseの署名・期限・失効・teacher claim、教材／画像ownerを検証する。
- 未承認教材、元画像、教員メール、AI生出力は学生APIへ返さない。画像のGCS直接取得とFirestoreのクライアント直接アクセスは引き続き拒否する。
- `/docs`、`/redoc`、`/openapi.json`、`.env` はproductionで公開しない。
- 審査用教員の認証情報をREADMEや共有URLへ載せない。既存の本人アカウントを維持する。新規自己登録だけでteacher claimは得られない。

## 実装済みの不正利用・費用対策

- Firestore transactionで解析予約：UID単位の分バケット2回、JST1日10回、全体JST1日30回。モデル失敗時も予約は返却しない。保存先障害時は503で生成を止める。
- 画像サイズ、形式、画素数、正規化PNGサイズを制限。生成前の入力計測6144トークン＋schema余裕2048、出力・思考最大8192、SDK再試行1試行、全体timeout50秒。
- 全APIはプロセスあたり240回/分（healthを除く）。公開snapshotのGETは60回/分、承認版だけ最大128件・60秒キャッシュ。クライアントが偽装できるIPヘッダーに依存しない。
- 書込予約もUIDごと30回/分・200回/日、全体3000回/日。無限にFirestoreを書き込めない。
- `scripts/usage_status.py` でJST当日の実Firestore予約数を確認できる。ログの429／5xxはCloud Loggingで確認する。

Gemini 3.8 Flashの現行有料単価から、入力・出力を各8192とした30解析の保守的見積りは約 **$1.11/日**。これはGemini生成だけの目安で、税・為替・その他のGoogle Cloud料金を含まず、請求額の保証ではない。

Cloud Build、Artifact Registry、Secret Manager、Firestore、GCS、Cloud Run、ログの料金は別。最小0・最大1は請求額の上限ではない。新リビジョン試験中はタグ付きリビジョンが併存し、最大3つのリビジョンが各最大1インスタンスを持ち得る。公開前に試験タグを削除し、通常配信を1リビジョンへまとめる。

APIのプロセス内制限とキャッシュは再起動でリセットされる。大量の未認証HTTPやhealth／静的ファイルへの通信そのものの課金・妨害は完全には防げない。WAF／Load Balancer／新しい予算通知は追加しておらず、導入には別途費用と設定承認が必要。予算アラートも支払上限ではない。

## 承認前の証跡

- Python171件、Playwright18件、数値計算4件、実Rules60件成功。公開オーケストレーションの安全ゲート4件も模擬試験成功。
- 改善候補で実クラウドE2E1件成功。解析2回、教員修正13、null保留、保存後再読込、承認、学生比較の差6。
- 学生／無権限403、他教員404、失効済みtoken401、承認後更新409。Firestore直接取得403、GCS非公開。
- axe違反0（教員・学生、320/390/1280px）、学生の解析呼出し0。実スクリーンリーダー読み上げは未検証。
- 既存承認教材13件のハッシュ不変、新規の試験承認版2件だけが増加。
- IAM非公開、Secret参照、Git・ビルド・配信アセット・確認した168ログ項目にGeminiキー非露出。

## 復旧

公開を止める場合は、先に `allUsers` の `roles/run.invoker` をサービスから削除し、匿名アクセスが403となることを確認する。その後 `chartbridge-00009-z6n=100` へトラフィックを戻す。IAMを閉じずに旧版へ戻すと、新しい解析利用枠のない版が公開されるため順序を守る。

教材データと既存リビジョンを削除しない。公開の終了時期は別途ユーザーの指示に従い、無断で公開期間延長や課金設定変更をしない。

参考：[Cloud Run公開アクセス](https://docs.cloud.google.com/run/docs/authenticating/public)、[リビジョンとトラフィック](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)、[Gemini価格](https://ai.google.dev/gemini-api/docs/pricing)。
