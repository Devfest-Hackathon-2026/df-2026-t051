# OSSライセンス確認（2026-11-05）

実画像拡張評価（2026-11-06）のChartQA由来の期待データと、OECD／OWID／統計局の画像は[別の権利一覧](../evaluation/real-v2/LICENSE_DATA.md)を参照。画像・元CSVは同梱せず、データのGPL-3.0表記と製品コードのMITを区別する。新しいランタイム依存は追加していない。

インストール済みパッケージの配布メタデータを確認し、全件の識別情報を`python-licenses.json`と`node-licenses.json`に記録した。
正確な依存バージョンは`backend/requirements.txt`と`frontend/pnpm-lock.yaml`に固定。

| 主な依存 | ライセンス |
|---|---|
| React / React DOM / Vite / Tailwind CSS / FastAPI / Pydantic | MIT |
| TypeScript / Firebase JS SDK / Firebase Admin / Google GenAI SDK / Playwright / python-multipart | Apache-2.0 |
| Uvicorn / Starlette / HTTPX | BSD-3-Clause |
| Pillow | MIT-CMU |
| axe-core / @axe-core/playwright / Lightning CSS / certifi | MPL-2.0 |
| caniuse-lite | CC-BY-4.0 |

推移依存にはISC、BSD、PSF-2.0、MIT-0等も含む。MPL対象ライブラリのソースは改変していない。
第三者の著作権・ライセンス文は削除せず、配布物に同梱する。`third-party-notices.txt`は現在の環境の配布物から収集したもの。
Linux Dockerではプラットフォーム別依存が変わるため、最終イメージでもライセンス・NOTICEを再収集する。
CC-BY対象はcaniuse-lite配布物の出典と著作権表示を維持する。依存OSSのライセンスを本アプリのMITで上書きしない。

GoogleのAPI・クラウドサービスはOSSライセンスとは別に各サービス利用条件が適用される。
初期試験画像・合成18枚はPillowで自作。2026-11-06の追加評価では農林水産省の原図6枚を利用した。出典・条件はsubmission/LICENSES.mdとevaluation/real-v1/manifest.jsonに記録し、原画像は再配布しない。既存PoCは流用していない。

## 2026-11-10 公開範囲の是正

ChartQA／OECD由来の表本体・期待値・再現出力は現行版から縮小しました。mainの到達可能な履歴を縮小しましたが、旧URL・キャッシュ等は残る可能性があります。GPL表記は第三者画像・元データの包括許諾ではありません。[是正記録](submission/RIGHTS_REMEDIATION.md)を現在の公開範囲の説明として参照してください。
