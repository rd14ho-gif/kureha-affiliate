# お米1kg最安ナビ（MirAI くれは事業）

楽天市場のお米を毎日自動で集めて、「送料込み・ポイント込みの1kgあたり実質価格」でランキングする静的サイトです。

- 毎日 05:17（日本時間）に GitHub Actions が自動更新
- サーバー契約なし（GitHub Pages で無料公開）
- 公開前に品質・規約チェック。失敗したら公開を止めて前日のサイトを残す
- 週1回、Claude が実行結果を見て改善し、レポートを出す

## 動かし方（手元で確認する場合）
```
python -m unittest discover -s tests -t .
python -m pipeline.run --demo
```
`dist/index.html` をブラウザで開くと、サンプルデータで作ったサイトを確認できます。

## 公開に必要な設定（ヒロがやること）
GitHub の Settings → Secrets and variables → Actions
- Secrets：`RAKUTEN_APP_ID` / `RAKUTEN_ACCESS_KEY` / `RAKUTEN_AFFILIATE_ID`
- Variables：`PUBLISH_ENABLED` = `true`（初回公開を承認するとき）

Settings → Pages → Source を「GitHub Actions」にする。

データ提供：Supported by Rakuten Developers
