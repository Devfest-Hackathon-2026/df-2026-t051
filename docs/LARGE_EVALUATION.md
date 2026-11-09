# 大規模実画像評価：準備・実行状態

**追記：5米ドル上限の承認後に評価を実施し、1サイクルの改善と留保25枚の一度限りの評価を完了した。最新状態は[最終報告](LARGE_EVALUATION_RESULTS.md)を正本とする。以下の「回答待ち／未実行」は準備時点の履歴。再実行して上書きしない。**

2026-11-06。ブランチ`codex/chartbridge-real-evaluation`。本番Cloud RunはDay5のrevision `chartbridge-00009-z6n`のままで、デプロイ・一般公開・新規有料リソースの作成はしていない。

## 現在の到達点

保持した過去の初回結果は、合成18枚107/107値と、実教材6枚の全一致3/6・数値19/30・schema失敗2/6。今回の開発60枚の初期精度、改善後精度、最終25枚の精度はすべて未測定であり、過去の結果を代入しない。

| 作業 | 状態 |
|---|---|
| 収集・権利・正解の照合 | ChartQAのOECD図＋CSVの128候補を確認し、85枚採用。別出典を含む異常系15枚を採用 |
| 分割 | 開発60、封印最終25、異常系15を推論前に固定。資料系列の重複なし |
| 評価基盤 | 全セルを分母にした採点、nullの別指標、A〜G診断、応答・usage・finish reason記録、平均／中央値／p95、永続費用予約・再試行上限・二重起動防止を実装 |
| 実Geminiのベースライン | **費用上限への回答待ち。今回の生成実行は0回** |
| 数値処理の改善案 | 漢数字・位取り・明示単位をDecimalで処理する試作を追加。解析APIには未接続、採用判断は実評価後 |
| 改善ループ・独立最終評価 | 未実行。最終25枚は未消費 |
| 本番反映・公開 | 未実施。別途承認が必要 |

**この100枚を「多様な日本語実教材100枚」とは扱わない。** 正常系は英語OECDプラットフォームだけであり、元統計資料系列を分けても描画様式は共通。最終評価の一般化範囲は限定される。日本語・漢数字、負数・ゼロ、ネイティブ低画質、タイトル／単位欠落を十分に網羅した正解付き実画像は未確保。これらの合成単体試験を実教材での精度と混同しない。

## 出典・利用条件・正解

- **OECD図85枚**：[ChartQA作成者の公開リポジトリ](https://github.com/vis-nlp/ChartQA)の固定revisionから原図と対応CSVを別々に取得。図とCSVのカテゴリ・数値・単位を照合。CSVがK/M/Gの倍率・精度を保持しているか確信できない例は除外した。正解はGeminiで生成していない。原統計のマイクロデータまで再監査したわけではない。
- OECDの[利用条件](https://www.oecd.org/en/about/terms-conditions.html)を確認。出典表示、第三者権利、非保証・非推薦の境界を保持する。元画像・元CSVは再配布しない。
- **異常系15ファイル**：日本の統計局教材7、OWID横棒5、OECD複数折れ線3。統計局は[PDL1.0等の利用条件](https://www.stat.go.jp/info/riyou.html)、OWIDは図に印字されたCC BYと[第三者データの条件](https://ourworldindata.org/faqs)を記録。同じ教材の関連画面を含むので、15の独立した出典ではない。
- ChartQAのGPL-3.0表記を第三者画像の包括的ライセンスとは解釈しない。コードの流用は行わない。Statista／Pewの候補は必要な権利が確認できず採用しない。
- 原ファイルはすべて`.tmp/large-eval`（Git対象外）。公開対象はURL・出典・利用条件・hash・事実としての期待値・評価コードのみ。

[開発manifest](../evaluation/real-v2/development.json)／[封印index](../evaluation/real-v2/holdout-index.json)／[分割lock](../evaluation/real-v2/split-lock.json)／[採否](../evaluation/real-v2/screening.json)／[異常系](../evaluation/real-v2/anomalies.json)。

分割は出版社単位ではなく、図に書かれた元統計の資料系列単位。医療統計と教育・TALIS・PISAを最終側へまとめ、開発の国民経済計算・税収・所得分布等と分離する。同じ描画環境・公開データセットを共有しており、モデル事前学習での既知性も不明。改善コードから未使用であることと、モデルが世界で初めて見た画像であることは別である。

## 費用と上限

公式[Gemini単価](https://ai.google.dev/gemini-api/docs/pricing)では、2026年末までGemini3.8 Flashの入力$0.75/百万token、思考を含む出力$3.75/百万token。モデルmetadataは入力1048576、出力65536の上限。試験は入力・出力を各8192以下へ絞る。プロジェクトのquotaを読み取り確認した結果は[quota-check](../evaluation/real-v2/quota-check.json)。このAPIに複数Tierの数値が出るため、適用Tierまでは断定しない。quotaの増加申請・変更はしない。

ユーザーへ提案した上限は**生成最大300試行＋token計測最大300試行、推定12米ドル以内**。入力・出力各8192の保守的見積りで300生成は$11.0592。税・為替、別プロセスや既存サービスの利用は対象外。回答なしでは実行しない。実行プログラムも承認記録なしならAPIを呼ぶ前に停止する。

同時処理2、429だけ最大2再試行（初回を含め3試行）、20秒／40秒程度の待機とジッター、永続台帳で予約してから呼び出す。SDKの内側再試行は1試行に固定。費用不明の失敗要求は保守的な予約を残す。入力token数に余裕を設け、providerの実usageが想定を越えた場合は停止する。請求のハードキャップを設定したという意味ではない。

## 再開時の順序

1. ユーザーの上限回答を`evaluation/real-v2/budget-approval.json`に記録する。承認がない現状ではこのファイルを作らない。
2. 固定済みbaseline-code.jsonを使い、開発60枚を1回評価する。
3. validation_errors、finish_reasons、raw_text、正解、コードを照合する。MAX_TOKENSでなければ切断と決めつけない。原因不明は明記。
4. 数値処理試作を採用する場合、根拠・回帰・実評価の結果を記録してから解析経路へ接続する。プロンプト・出力予算・スキーマの変更も実際の失敗に応じて最大3サイクル。
5. コードとプロンプトのhash・コミットをcandidate-freeze.jsonへ固定し、封印25枚を一度だけ評価する。その後はこのセットを使って調整しない。
6. 使用回数・usageからの費用と、不明要求の最大予約分を分けて報告。本番デプロイは実施しない。

```powershell
# 上限の承認記録・環境変数設定が済んだ後のみ
.\.venv\Scripts\python.exe scripts/run_large_evaluation.py --name development-baseline --mode baseline --split development
# 修正を採用・回帰確認した後
.\.venv\Scripts\python.exe scripts/run_large_evaluation.py --name development-cycle1 --mode candidate --split development
# コード凍結後に一度だけ
.\.venv\Scripts\python.exe scripts/run_large_evaluation.py --name final-once --mode candidate --split holdout
```

結果ディレクトリが既にあれば上書き・再実行を拒否する。台帳は全サイクル共通。最終の封印消費記録は削除してやり直さない。中断時には台帳とjournalを確認し、欠測を隠さず扱う。

## 試験と未検証

今回のオフラインAPI・採点・予算・数値処理試験は107件成功。比較計算4件、Playwright16件、現在のFirestore Rules45件を合わせ172件成功。型検査・本番ビルドも成功。既存Starlette/httpx非推奨警告は残る。
採点器はnull、誤単位、対応ずれ、schema失敗時の分母保持、p95、思考token、再起動後の予約、429再試行上限等をモックで確認した。**評価runner自体の実Gemini通信はまだ未検証**。Cloud Runの実E2Eも今回再実行していない。前回Day5の実クラウド成功記録は[別記録](verification/firebase-full-flow.json)として保持する。

`numeric_labels.py`は非接続の試作。曖昧な単位省略、近似値、範囲、不等号、浮動小数で表現できない数値は保留可能にする。モデルの根拠転記自体の誤りは検出できず、教員の照合・承認を代替しない。
