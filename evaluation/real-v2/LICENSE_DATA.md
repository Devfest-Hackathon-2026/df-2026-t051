# 評価データの権利と出典

ChartQA：Ahmed Masry, Do Long, Jia Qing Tan, Shafiq Joty, Enamul Hoque (2022),
“ChartQA: A Benchmark for Question Answering about Charts with Visual and Logical Reasoning.”
[論文](https://aclanthology.org/2022.findings-acl.177/)・[作成者公開リポジトリ](https://github.com/vis-nlp/ChartQA)。

ChartQA公開CSVから得た期待データについては、元リポジトリのGPL-3.0表記と[原文](CHARTQA_LICENSE.txt)を保持する。独自に作成したChartBridge製品コード・評価プログラムはルートMITのまま。GPLのプログラムを製品へ取り込んでいない。原CSVそのものは同梱しない。

画像の権利は元の各出版社に残る。ChartQAのライセンスを第三者画像の包括的な許諾と解釈しない。OECDの図とデータは[同機関の利用条件](https://www.oecd.org/en/about/terms-conditions.html)、OWID図は図中のCC BY表記と[第三者素材の条件](https://ourworldindata.org/faqs)、日本の統計局教材は[利用規約](https://www.stat.go.jp/info/riyou.html)と第三者権利の例外を維持する。

原図・原CSV・候補一覧のキャッシュ・封印した最終正解は`.tmp/large-eval`にのみ保存し、Public GitHubへ送らない。採用manifestに出典、URL、hash、利用条件、帰属表記を記録する。結果はChartBridge独自の分析であり、各提供者の保証・推薦を意味しない。Statista／Pew等、必要な権利が確認できない候補は採用しない。
