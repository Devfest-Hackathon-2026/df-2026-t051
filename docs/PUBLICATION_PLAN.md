> この文書は以前の時点の記録です。2026-11-06の一般公開後の状態・追加日本語評価・操作確認は [PRODUCTION_AUDIT.md](PRODUCTION_AUDIT.md) を参照してください。過去の数値と当時の公開状態は履歴として保持しています。

# 審査用公開の具体案（未実施・承認待ち）

## 現在

Cloud Run `chartbridge` はIAM非公開。Firebase認証・teacher claim・owner確認、Firestore deny-all、GCS公開防止を維持している。一般公開設定と課金アカウントはこの作業で変更していない。
通常ブラウザでCloud Run URLを開くと403。GoogleにログインしただけではCloud RunのBearer tokenは付かないので、単に審査員へInvokerを付与するだけではブラウザ体験は完成しない。

## 推奨：同一サービスの外側入口だけを限定期間公開

審査員が追加CLIなしで利用する最小変更は、`chartbridge` のサービス単位で `allUsers` に `roles/run.invoker` を付与すること。プロジェクト全体へのIAM付与やFirestore／GCSの公開はしない。実行サービスアカウントとSecret Manager権限も変えない。
外側入口への未認証アクセスを許すだけで、教員APIは引き続きFastAPIのFirebase検証で保護する。

| 経路 | 公開後の条件 | 公開されるもの |
|---|---|---|
| `/`・静的ファイル | ブラウザ閲覧可 | UIとFirebase公開Web設定（Geminiキーではない） |
| `/learn/{snapshot}` / `GET /api/materials/{snapshot}` | 閲覧可、承認版のみ | 承認値・タイトル・単位・承認日時 |
| `POST /api/analyze` | Firebase有効token＋teacher claim＋利用枠 | 認証済み教員だけが実解析 |
| `/api/drafts/**` | 上記＋owner確認 | 本人の未承認／承認教材だけ |
| `/api/images/**` | 上記＋画像owner確認 | 本人の元画像だけ |
| Firestore／GCS直接アクセス | 既存Rules／IAMのまま拒否 | 元画像や未承認データは公開しない |

学生の表示と比較にGeminiは使わない。Firebaseに自己登録できてもteacher claimは本人が付与できず、解析権限は得られない。審査用教員は管理者が招待したアカウントだけにする。共有パスワードを公開READMEへ載せない。

## 公開前の必須対策（現状のまま即時公開は推奨しない）

- Firestoreトランザクション等でUIDごとの解析予約枠を強制する。初期案は1UIDあたり1分2回・JST1日10回、全体1日30回。モデル呼出前に予約し、上限時は429・保存先障害時は安全停止。値はユーザー承認後に確定する。
- 現行の同時解析2件、max instances 1、min 0を維持。ただしこれは請求額の上限ではない。
- Geminiプロジェクトの実クォータを確認し、予算アラートを設定する場合も別途承認を得る。アラートは自動停止や支払上限ではない。
- 公開snapshotの読取にもDBアクセス・Cloud Run料金がかかる。immutableな承認データだけをキャッシュし、必要ならLB／Cloud Armor等で外部レート制御する。これらは追加リソース・費用があるため無断導入しない。
- productionのOpenAPI UIを閉じる、Firebase WebキーのAPI制限・許可ドメインを確認する。
- 未認証／学生／他教員／所有者の負の試験、元画像・draftの非露出、null、承認後不変性、キー非露出、quota超過を公開候補リビジョンで再試験する。
- 公開終了予定時刻、障害時に入口を非公開へ戻す担当者、利用停止手順を決める。

利用枠制限・キャッシュ・外部レート制御はこのDay 5では未実装。公開せずに審査する場合は、現状の認証付きプロキシでの同席デモ／録画を使う。IAPのブラウザ認証ゲートを追加する案もあるが、追加のIAM・構成変更と検証を要する。

## ユーザーへ求める承認（まだ求めていない／変更していない）

1. 審査期間中、上記サービスだけに`allUsers:roles/run.invoker`を付けること。
2. 招待する教員アカウント、解析のUID／全体上限、公開終了時刻。
3. 追加の予算通知・WAF／LB等を使う場合の具体的な費用方針。

リスク：認証で解析を制限しても、公開ページ・GET・認証失敗へのアクセス自体には実行費がかかる。招待教員の認証情報漏えい、共有URLの第三者転送、原図の権利・個人情報、モデルの桁誤りは別の対策を要する。
承認は上記の公開・費用方針に対するもので、承認を得た後でも未実装の安全対策を先に実装・検証し、その結果を確認してから切り替える。

## 変更・復旧の対象（承認前は実行しない）

```powershell
# 公開：対策実装・検証と明示承認の後だけ実行
gcloud run services add-iam-policy-binding chartbridge --member=allUsers --role=roles/run.invoker --region=asia-northeast1 --project=chartbridge-gdgoc-2026
# 復旧：公開入口を閉じる（アプリ側認証は常に維持）
gcloud run services remove-iam-policy-binding chartbridge --member=allUsers --role=roles/run.invoker --region=asia-northeast1 --project=chartbridge-gdgoc-2026
```

参考：[Cloud Run公開アクセス](https://docs.cloud.google.com/run/docs/authenticating/public)、[認証概要](https://docs.cloud.google.com/run/docs/authenticating/overview)。
