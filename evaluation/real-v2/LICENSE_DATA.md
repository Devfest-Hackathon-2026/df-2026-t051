# 評価データの出典・公開範囲・残存リスク

2026-11-10。これは公開範囲の是正記録であり、権利確認完了の証明ではありません。

## 現行版と過去版

現行版では、ChartQA／OECD由来の原画像・原CSVに加え、元表の見出し・全行・期待値・表を再現するモデル出力を公開ファイルから除外しています。出典URL、取得元revision、資料単位のSHA256、評価分割、採点件数、処理時間、API使用量、独自の集計結果を保持します。具体的な対象と原本・縮小版のハッシュは [PUBLICATION.json](PUBLICATION.json) に記録します。

書換え前の公開コミットには、60表のCSVの見出し・全行をJSON化したデータ、期待値、予測出力が含まれていました。「原CSVファイルがない」ことは内容を再配布していないことを意味しません。git-filter-repoでmainから到達可能な全履歴を縮小する是正を行いました。元履歴は非公開ローカルに保全し、公開バックアップ参照は作りません。GitHubの旧コミットURL・キャッシュ・外部コピーには旧データが残る可能性があります。過去分の権利問題が解消したとは主張しません。大会運営への相談は本人による対応事項で、実施・承認済みとはしていません。

## ChartQA

出典：Ahmed Masry, Do Long, Jia Qing Tan, Shafiq Joty, Enamul Hoque (2022), “ChartQA: A Benchmark for Question Answering about Charts with Visual and Logical Reasoning.” [論文](https://aclanthology.org/2022.findings-acl.177/)、[公開リポジトリ](https://github.com/vis-nlp/ChartQA)。取得元revisionは `044eabfc306abfe9340c5741f0093aefc5973d06` です。

元リポジトリのGPL-3.0表記と [原文](CHARTQA_LICENSE.txt) を保持します。GPLの適用対象となる外部由来部分を、独自コードのMITで上書きしません。反対に、個々の統計的事実まで一律にGPL対象であるとも断定しません。ChartQAの表記を、元出版社の画像・データの包括的な許諾とは解釈しません。

## OECD

[OECD公式利用条件](https://www.oecd.org/en/about/terms-conditions.html) のData節は、個別データの追加制限・第三者権利の確認と帰属表示を要求します。全85図の元データセット・年・DOI等、個別条件を全件確認済みとはしていません。このため現行版では、図別表データ・期待値・再現出力を除外し、資料URL・ハッシュと独自の採点・集計を公開します。OECDおよびChartQAによる保証・推薦を意味しません。原画像の解析利用に関する根拠にも未確認事項が残り、現行版の縮小だけで過去の利用を適法化するものではありません。

## 農林水産省

出典：[統計データを使いこなして自由研究を攻略しよう！2024掲載版](https://www.maff.go.jp/j/kids/kodomo_kasumi/2024/content/toukei.html)、[統計のわかっちゃう事典2024](https://www.maff.go.jp/j/kids/kodomo_kasumi/2024/content/pdf/jiten_2024.pdf)、同ページの統計表・e-Stat。各資料URLとハッシュは `evaluation/real-v1/manifest.json` と `evaluation/japanese-v3/development.json` 等に記録しています。

一般的な根拠は [農水省の利用条件](https://www.maff.go.jp/j/use/link.html) と [PDL1.0](https://www.digital.go.jp/resources/open_data/public_data_license_v1.0) です。数値・簡単な表等と、第三者の写真・イラスト・キャラクター等を区別します。原画像・PDF・Excelは同梱せず、統計数値・単純なラベル・期待データ・評価結果を公開します。画像の切り出し、値の単位換算・丸め、ラベル整形はChartBridgeによる加工です。原画像中の第三者素材の個別許諾まで確認済みとはしていません。評価結果は独自の分析であり、省の作成・保証ではありません。

## 和歌山県

出典：[統計グラフを作ってみよう](https://www.pref.wakayama.lg.jp/prefg/020300/kids/graph.html)、原ページ記載の総務省「国勢調査」。[県公開情報利用規約](https://www.pref.wakayama.lg.jp/prefg/000200/opendata/hpopendatakiyaku.html) の数値データ・簡単な表等の規定を、原JPEGの利用条件と分けて扱います。原JPEGは非同梱で、人口数値・年ラベルと評価結果を公開します。原表の西暦誤記について和暦に基づく補正を行っており、県が作成した未加工データとは表示しません。原JPEGの個別許諾は確認済みとしていません。

## 再現性と未確認事項

集計値、採点基準、抽出コード、過去の凍結記録は変更しません。原本SHA256と縮小版SHA256を区別します。公開版だけでは元表を必要とする再採点・誤読の個別検証を完全再現できません。評価用スクリプトの完全実行には、法令・提供元の条件を確認して準備した非公開原本が必要です。独立最終評価をやり直したことにはしません。

原画像の技術試験・情報解析に許諾または法定例外が適用されるかは、利用目的・範囲等に基づく別の確認事項です。公開していないことだけで解決済みとはしません。署名・非侵害等の誓約は本人が再確認します。
