# 教員から学生までの利用と検証

Cloud Runは引き続きIAM非公開。通常のブラウザからサービスURLを開くと403になる。
Firebase ID tokenはアプリの教員確認に使用し、Cloud Run IAM tokenとは分けて扱う。

## 操作する入口

```powershell
.\.venv\Scripts\python.exe scripts/private_proxy.py --url https://chartbridge-gqe6dtznpq-an.a.run.app --gcloud "C:\Users\PC_User\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd" --port 8086
```

[認証付き入口](http://127.0.0.1:8086/)を開く。Cloud RunのIAM認証はプロキシがサーバー側で行う。教員のFirebaseログインは画面上で本人が行う。
プロキシはブラウザのFirebase `Authorization`を維持し、Google IAM tokenは`X-Serverless-Authorization`に付与する。キー・パスワード・ID tokenはログ出力しない。

## 普段使う教員アカウント

1. Firebaseコンソール → `chartbridge-gdgoc-2026` → Authentication → ユーザー →「ユーザーを追加」で、ご本人がメールとパスワードを設定する。パスワードをチャットへ送らない。
2. プロジェクト管理者が、意図したアカウントにだけ教員claimを付与する。

```powershell
.\.venv\Scripts\python.exe scripts/grant_teacher.py --email YOUR_EMAIL
```

3. ログインし直して新しいID tokenを取得する。Firebaseに登録しただけでは教員権限は付かない。
4. 画面でグラフ画像を登録し、未承認として保存する。

FastAPIはFirebase Admin SDKで署名・発行者・audience・期限・失効／無効化状態を検証し、teacher custom claimを確認する。教材・元画像はさらにowner UIDを照合する。
runtimeサービスアカウントにはユーザー読取権限だけを付与し、claim付与は管理者のスクリプトだけで行う。アプリに自己昇格APIはない。

## 保存・再開・承認

解析が成功した画像はメタデータ除去済みPNGとして専用非公開GCSバケットに保存する。画像の公開URLは作らない。
所有者だけが画像APIで取得でき、ブラウザでは認証付きfetchで取得したblobを表示する。
教材を保存すると元画像ID、AI原文、教員編集データを関連付ける。「保存済みの教材を開く」からブラウザ再読み込み後にも再開できる。
以前のIAM試験で作った教材はGoogle IAM subjectがownerであり、新しいFirebase UIDに自動移管しない。
元画像を保存していなかった既存教材に、後から元画像を捏造して補うことはしない。元画像未保存と表示する。

教員は画像と表を照合し、確認チェック後に承認する。承認時に独立したsnapshotを作成し、その版はAPI経由で変更できない。

## 学生の操作

承認後の「学生向け教材を開く」から`/learn/{snapshot_id}`へ移動する。共有URLはCloud Run URLを使う。
現時点ではIAM非公開のため、配布先もIAMアクセスまたは検証プロキシが必要。Cloud Runの一般公開設定は変更していない。

- 学生用GETは承認snapshotだけを返し、元画像・owner・AI原文を返さない。
- 書き込み・編集・承認APIは学生向けに設けない。
- セマンティックなHTML表で数値を読み、最大・最小（同値の全項目を含む）を確認する。
- 2項目を選択し、キーボードで比較ボタンを実行する。結果はlive regionで通知する。
- nullは表で「未確定」と表示し、最大・最小から除外する。nullを含む2値比較は拒否する。確定値が0である場合は除外しない。
- 学生画面の表示・計算は同じsnapshotデータを使い、Geminiを呼ばない。

## Firestore Security Rules

Firestoreクライアントからの全コレクションへのread/writeをdeny-allで反映する。学生の読取もAPIのみを使用する。
サーバーSDKはRulesをバイパスするので、APIの教員・owner認可を維持する。
反映済みreleaseのソースに対し、匿名・学生・教員 × draft/snapshot/image × get/list/create/update/deleteの45通りをRules RESTテストで確認。
実Firebaseの教員・学生ID tokenによる直接Firestore REST読取も、クラウドE2Eで403になることを検証する。

## 試験

```powershell
$env:PYTHONPATH = (Join-Path $PWD 'backend')
.\.venv\Scripts\python.exe -m pytest backend/tests -q
node --experimental-strip-types --test frontend/tests/math.test.ts
.\.venv\Scripts\python.exe scripts/test_rules.py
.\.venv\Scripts\python.exe scripts/verify_firebase_flow.py
```

最後の試験はプロキシ8086を必要とする。実Firebaseに一時教員2名と学生1名を作り、ランダムパスワード・tokenはメモリと子プロセス環境だけで扱う。試験後にアカウントを削除する。実メールは送信しない。
試験用画像・教材・承認snapshotは個人情報のない合成データで、検証の証拠としてクラウドに残る。
Rules REST試験と実API試験は少量の課金対象操作を含む。

未実施：NVDAでの非視認手動操作、18グラフ固定評価。共有URLの一般公開には別途承認が必要。
