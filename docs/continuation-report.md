# 教員認証・保存再開・学生教材の実装記録（2026-11-05）

## 実装

- Firebaseの実Email/Passwordログイン。runtime APIからFirebase公開Web設定を配信（Geminiキーとは別）。
- FastAPIでFirebase ID tokenの署名・issuer・audience・期限・失効／無効化状態を検証し、teacher claimを必須化。
- 教材・元画像はowner UIDを追加検証。別教員の教材を404として扱い、自己昇格APIは置かない。
- Firestore deny-all Rulesを実反映。反映済みreleaseのソースで45通りのdenyテスト成功。
- 元画像をメタデータ除去済みPNGとして非公開GCSバケットに保存し、認可APIからだけ取得。
- 自分の保存教材一覧と再開導線。再読込後にも保存データ・AI原文・元画像を再取得。
- 承認snapshotだけを返す読み取り専用GETと`/learn/{snapshot_id}`共有画面。
- 学生用セマンティック表、同値を含む最大・最小、キーボードとlive regionによる2値比較。
- nullは計算から除外し、全値未確定なら計算不能を表示。0・負数・小数・微小値を扱う。
- 小数差分は10進表記をBigIntで揃えて減算し、有限な表示値に変換。二進浮動小数の差分ノイズと微小値の0への丸めを避ける。

Cloud RunのIAM一般公開設定は変更していない。ブラウザでの検証はloopback専用プロキシから行う。
共有URLは実装済みだが、今は共有相手にもCloud Run IAMアクセスまたは検証プロキシが必要。
最終リビジョンは`chartbridge-00005-7bx`。

## 変更・検証したクラウド設定

Firebase API初期化が403だったため、ユーザー本人がFirebaseコンソールで既存プロジェクトの追加を完了。その後RESTでEmail/PasswordとWebアプリ設定を作成した。
Cloud Run runtimeにはFirebaseユーザー読取のViewer権限を付与。教員claimの管理権限はruntimeに付けていない。
GCS専用バケットは東京リージョン、uniform bucket-level accessとpublic access preventionを有効化。runtimeはobjectCreator／objectViewerのみ。
FirestoreサーバーSDKはRulesをバイパスするので、既存のAPI認可・owner確認・承認トランザクションを維持した。
課金アカウント・Cloud Run一般公開設定の変更は行っていない。

## 回帰試験

- Python API／ユニット：32 passed。
- 学生計算：3 passed（null、全null、0、負数、同値、インデックス不正、小数、微小値）。
- 既存アップロードE2E：2 passed。
- TypeScript型チェック、Vite本番ビルド、pip check：成功。
- 反映済みRulesのソースに対するRules RESTテスト：45/45 SUCCESS。
- 実Firebase・Cloud Run・GCS・Firestoreの一連のE2E：1 passed（52.5秒）。一時アカウントは試験後に削除。
- 指定された普段使うFirebaseアカウントへのteacher claim付与：成功。本人のパスワードではログインを代行していない。

実E2Eでは教員ログイン200、教員claimなし403、他ownerの取得／更新／承認404、元画像の再読込、GCS匿名アクセス403、Firestoreへの直接アクセス（教員／学生）403を確認。
承認済みGETは200、承認後の変更は409、失効させた実Firebase tokenは401。
学生画面では未確定値を除外し、確定した12と18のキーボード比較で差6を表示した。学生の閲覧・比較時に解析APIへのリクエストは0回。
教員画面・学生画面ともaxe自動検査の違反0件。証跡は`verification/firebase-full-flow.json`と`verification/student-live.png`。

## 修正した問題

- Firebase初回追加APIの403：本人によるコンソール初期登録で解決。
- Cloud Run IAMとFirebaseでAuthorizationが衝突：IAMは`X-Serverless-Authorization`、Firebaseは`Authorization`に分離。
- 比較selectの入れ子labelにoption文字列が混ざり、試験から名前を特定できなかった。選択欄に明示的なアクセシブル名を設定。
- 実Gemini試験に一律15秒の待機上限が適用され、API応答前に試験が終了した。解析レスポンスだけ65秒待機に調整（SDK／API側のtimeoutは維持）。
- Windows cp932でPlaywrightの記号が出力できなかった。検証スクリプトの標準出力をUTF-8に設定。
- ログアウト後に画面内に残る教材状態を消去するよう修正。

## 制約・次の作業

- 普段使う教員アカウントのパスワード設定は本人操作。登録後、管理者が指定メールにteacher claimを付与し、再ログインする。
- 旧IAM検証教材のownerは旧subjectのまま保つ。Firebase UIDへの自動移管はしない。以前に画像未保存の教材は元画像未保存と表示する。
- 一覧は本人の教材を最大100件。大量教材のページ送りや削除・画像保管期限はMVP後の検討事項。
- セキュリティルールとAPI試験は自動検証。NVDAでの非視認手動操作と18グラフ固定評価は未実施。
- 学生用に元画像・教員情報・AI原文を返さず、閲覧／比較時にはGeminiを呼ばない。
- 一般公開は別途承認後に実施する。
