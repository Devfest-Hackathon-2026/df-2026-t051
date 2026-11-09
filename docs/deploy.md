# Cloud Runデプロイ手順（未実施）

前提：gcloud、稼働するDocker Engine、Google Cloudプロジェクト、課金・Cloud Run・Artifact Registry・Cloud Buildの利用設定。
既存の課金設定・IAM・本番secretは本作業で変更していない。

1. FirebaseでEmail/Passwordを有効化、教員アカウントを用意し、管理者が`teacher: true`のcustom claimを付与する。
2. 実行用サービスアカウントを用意し、Firebase失効チェックに必要な権限を付与する。プロジェクト全体のOwner等は使わない。
3. Secret ManagerにGeminiキーを登録し、このサービスアカウントに対象secretだけのSecret Accessorを付与する。キー値をコマンド引数やログに残さない。
4. コンテナをビルドする。`VITE_FIREBASE_*`は公開web設定。Geminiキーをbuild argにしない。

```powershell
docker build -t REGION-docker.pkg.dev/PROJECT/REPOSITORY/chartbridge:day1 --build-arg VITE_FIREBASE_API_KEY=PUBLIC_WEB_KEY --build-arg VITE_FIREBASE_PROJECT_ID=PROJECT --build-arg VITE_FIREBASE_AUTH_DOMAIN=PROJECT.firebaseapp.com .
docker push REGION-docker.pkg.dev/PROJECT/REPOSITORY/chartbridge:day1
gcloud run deploy chartbridge --image REGION-docker.pkg.dev/PROJECT/REPOSITORY/chartbridge:day1 --project PROJECT --region asia-northeast1 --service-account SERVICE_ACCOUNT --no-allow-unauthenticated --max-instances 1 --concurrency 2 --memory 512Mi --timeout 60 --set-env-vars APP_ENV=production,LOCAL_DEMO=false,FIREBASE_PROJECT_ID=PROJECT,GEMINI_MODEL=VERIFIED_MODEL --set-secrets GEMINI_API_KEY=chartbridge-gemini:1
```

5. 初回はIAM保護のまま`gcloud run services proxy`等で確認する。外部教員がFirebaseログインで使う段階ではCloud Run入口の公開設定が別途必要（解析APIのFirebase認可は維持）。一般公開は実認証・権限・課金制限の確認後に行う。
6. `/api/health`、本物の教員ID tokenでの解析、権限なし403、未認証401、対応外画像、secret非露出を確認する。Cloud Runログに秘密・画像・抽出本文がないことを確認する。

学生向け公開APIはDay 3の対象。現在は共有教材URLを提供しない。
Docker base imageはtag指定。提出前に稼働確認したdigestへ固定し、Linuxで依存関係とイメージ脆弱性を再確認する。
