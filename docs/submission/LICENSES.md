# OSS・素材・データの利用条件

| 対象 | 条件・出典 | 使用状況 |
|---|---|---|
| ChartBridge独自コード | MIT、ルートLICENSE | 2026-11-05 10:00 JST以降に新規実装 |
| React / Vite / Tailwind / FastAPI / Pydantic等 | MIT、[配布メタデータ](../THIRD_PARTY.md)参照 | runtime／build |
| Firebase SDK / Google GenAI SDK / TypeScript / Playwright等 | Apache-2.0 | runtime／test |
| Uvicorn / Starlette / HTTPX等 | BSD系 | runtime／test |
| Pillow | MIT-CMU | 入力検証・自作評価画像 |
| axe-core / Lightning CSS / certifi等 | MPL-2.0 | ソース改変なし |
| caniuse-lite | CC-BY-4.0 | build推移依存 |
| 合成18グラフ | 自作、ChartBridge評価用。画像と正解を同梱 | Windows Meiryoで描画。フォント本体は配布しない |
| 実教材6グラフ | 農林水産省、[教育ページ](https://www.maff.go.jp/j/kids/kodomo_kasumi/2024/content/toukei.html)、[PDL1.0既定の利用条件と例外](https://www.maff.go.jp/j/use/link.html)を確認（2026-11-06） | 原図を評価目的で取得。原画像はリポジトリに再配布せず、URL・ハッシュ・出典・結果だけを記録 |
| その他のPDF候補 | 総務省統計局「日本の統計2026」、新潟県の家計資料 | 全数値ラベルがないため採点対象外。PDF原本は提出物へ同梱しない |
| ロゴ・写真・アイコン | ChartBridgeの文字ロゴ・CSS・文字記号 | 外部ロゴや人物写真を採用しない |

実教材の引用表記：出典：農林水産省「統計データを使いこなして自由研究を攻略しよう！」2024掲載版（URLは各manifest）。原図・加工なし、2026-11-06取得。評価結果はChartBridgeの分析であり、同省の作成・保証ではない。
PDLの第三者権利の例外は維持する。公式キャラクター・ロゴ・写真を製品素材として転用していない。画像から取り出した数値も独自MITライセンスで第三者の権利を上書きしない。

全依存リストは`docs/python-licenses.json`、`docs/node-licenses.json`、著作権・NOTICEは`docs/third-party-notices.txt`。Linuxの配布イメージではプラットフォーム別依存が変わるため提出前の再確認が必要。クラウド・Geminiのサービス利用規約はOSSのライセンスとは別。

## 追加評価・2026-11-06

新規日本語21枚の出典・独立正解・再配布制限は [評価仕様](../../evaluation/japanese-v3/PROTOCOL.md) を参照。農林水産省20枚は原PDF切り抜き、和歌山県1枚は原JPEG。元画像・元Excel・PDFを提出物へ同梱しない。
評価専用にxlrd2.0.2（BSD系2許諾）を追加。本番依存には追加していない。[ライセンス全文](../final-audit/licenses/xlrd-2.0.2-LICENSE.txt)を保持する。

## 2026-11-10 公開範囲・未確認事項の補足

農水省・和歌山県の統計数値・単純なラベル・期待データ・評価結果は公開しています。原画像・PDF・Excelの非同梱とは区別します。画像の切り出し、値の換算・丸め、ラベル整形、西暦補正は独自加工です。原画像の個別許諾まで確認済みとはしていません。ChartQA／OECD由来の表本体・期待値・再現出力はmainの到達可能な全履歴から縮小しましたが、旧URL・キャッシュ等は残る可能性があります。[詳細な条件と残存リスク](../../evaluation/real-v2/LICENSE_DATA.md)。
