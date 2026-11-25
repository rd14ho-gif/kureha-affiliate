"""計算済みデータから静的サイト（HTML）を作る。"""
from __future__ import annotations

import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PR_TEXT = "【PR】当サイトは楽天アフィリエイトを利用しています。リンク先で購入されると、運営者に報酬が支払われることがあります。ランキングの順位は報酬の有無や料率では決めていません。"
CREDIT_HTML = '<a href="https://webservice.rakuten.co.jp/" target="_blank" rel="noopener">Supported by Rakuten Developers</a>'
TYPE_LABEL = {"musenmai": "無洗米", "genmai": "玄米", "selectable": "精米を選べる"}


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def yen(n) -> str:
    return "—" if n is None else f"{int(n):,}円"


def kg_label(kg: float) -> str:
    return f"{kg:g}kg"


class Site:
    def __init__(self, site: dict, cat: dict, items: list[dict], history: list[dict], now: datetime, out: Path):
        self.site, self.cat, self.items, self.history, self.now, self.out = site, cat, items, history, now, out
        self.base = site["base_url"].rstrip("/")
        self.updated = now.strftime("%Y年%-m月%-d日 %H:%M")
        self.brand_label = {b["slug"]: b["label"] for b in cat["brands"]}
        self.pages: list[str] = []

    # ---------- 共通部品 ----------
    def rel(self, depth: int) -> str:
        return "../" * depth

    def head(self, title: str, desc: str, path: str, depth: int) -> str:
        s = self.site
        ga = ""
        if s.get("ga4_measurement_id"):
            gid = e(s["ga4_measurement_id"])
            ga = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={gid}"></script>'
                  f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
                  f"gtag('js',new Date());gtag('config','{gid}');</script>")
        gsc = f'<meta name="google-site-verification" content="{e(s["search_console_verification"])}">' if s.get("search_console_verification") else ""
        r = self.rel(depth)
        return f"""<!doctype html>
<html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">
<link rel="canonical" href="{e(self.base + '/' + path)}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{e(self.base + '/' + path)}">
{gsc}<link rel="stylesheet" href="{r}assets/style.css">{ga}
</head><body>
<div class="pr" role="note">{e(PR_TEXT)}</div>
<header class="top"><a class="logo" href="{r}index.html">🍚 {e(s['site_name'])}</a>
<nav><a href="{r}index.html">総合</a><a href="{r}size/5kg.html">5kg</a><a href="{r}size/10kg.html">10kg</a><a href="{r}type/musenmai.html">無洗米</a><a href="{r}type/genmai.html">玄米</a><a href="{r}brand/index.html">銘柄</a><a href="{r}souba.html">相場推移</a><a href="{r}about.html">計算方法</a></nav></header>
<main>"""

    def foot(self, depth: int) -> str:
        r = self.rel(depth)
        return f"""</main>
<footer><p>価格・ポイント・在庫は {e(self.updated)} 時点で楽天市場から取得した情報です。最新の内容は必ず楽天市場の商品ページで確認してください。</p>
<p>実質価格は楽天市場のショップポイント倍率のみで計算しています（SPUやキャンペーンは含みません）。</p>
<p><a href="{r}about.html">運営者・ランキングの決め方</a> ・ {CREDIT_HTML}</p>
<p>© {self.now.year} {e(self.site['operator'])}</p></footer>
<script src="{r}assets/app.js" defer></script></body></html>"""

    def write(self, path: str, body: str) -> None:
        p = self.out / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        if path.endswith(".html") and path != "404.html":
            self.pages.append(path)

    # ---------- 部品 ----------
    def stats_box(self, items: list[dict], label: str) -> str:
        if not items:
            return ""
        effs = sorted(i["effective_yen_per_kg"] for i in items)
        med = effs[len(effs) // 2]
        best = items[0]
        trend = ""
        if len(self.history) >= 2 and label == "総合":
            a, b = self.history[-2]["median"], self.history[-1]["median"]
            if a and b:
                d = b - a
                arrow = "▲" if d > 0 else ("▼" if d < 0 else "→")
                trend = f'<div class="stat"><span>前日比（中央値）</span><b>{arrow} {abs(d):,}円/kg</b></div>'
        return f"""<section class="stats">
<div class="stat"><span>最安（実質・1kgあたり）</span><b>{yen(best['effective_yen_per_kg'])}</b></div>
<div class="stat"><span>中央値（実質・1kgあたり）</span><b>{yen(med)}</b></div>
<div class="stat"><span>比較した商品数</span><b>{len(items):,}件</b></div>{trend}
</section>"""

    def pick_box(self, items: list[dict]) -> str:
        good = [i for i in items if i["review_count"] >= 20 and i["review_avg"] >= 4.2]
        if not good:
            return ""
        i = good[0]
        return f"""<section class="pick"><h2>レビュー4.2以上・20件以上の中で最安</h2>
{self.card(i, 0, highlight=True)}</section>"""

    def card(self, i: dict, rank: int, highlight: bool = False) -> str:
        tags = [TYPE_LABEL[t] for t in i["types"] if t in TYPE_LABEL]
        tags += [self.brand_label[b] for b in i["brands"] if b in self.brand_label][:2]
        if i["year"]:
            tags.append(f"{i['year']}年産" + ("（新米）" if i["is_new_crop"] else ""))
        tag_html = "".join(f'<span class="tag">{e(t)}</span>' for t in tags)
        pts = f'<span class="pt">ポイント{i["point_rate"]}倍</span>' if i["point_rate"] > 1 else ""
        review = f'★{i["review_avg"]:.2f}（{i["review_count"]:,}件）' if i["review_count"] else "レビューなし"
        img = f'<img src="{e(i["image"])}" alt="" loading="lazy" width="96" height="96">' if i["image"] else '<div class="noimg"></div>'
        rank_html = f'<div class="rank">{rank}</div>' if rank else ""
        attrs = (f'data-types="{e(" ".join(i["types"]) or "hakumai")}" data-kg="{i["kg"]:g}" '
                 f'data-new="{1 if i["is_new_crop"] else 0}" data-review="{i["review_avg"]}" data-rc="{i["review_count"]}" '
                 f'data-eff="{i["effective_yen_per_kg"]}" data-price="{i["price"]}"')
        return f"""<article class="item{' hl' if highlight else ''}" {attrs}>
{rank_html}{img}<div class="body">
<h3 class="name">{e(i['name'])}</h3>
<p class="shop">{e(i['shop'])}</p><div class="tags">{tag_html}</div>
<div class="nums"><div><span>実質</span><b>{yen(i['effective_yen_per_kg'])}/kg</b></div>
<div><span>価格（送料込み）</span><b>{yen(i['price'])}</b> / {kg_label(i['kg'])}</div>
<div><span>1kgあたり</span><b>{yen(i['yen_per_kg'])}</b>{pts}</div></div>
<p class="rv">{e(review)}</p>
<a class="buy" href="{e(i['url'])}" target="_blank" rel="sponsored noopener">楽天市場で見る</a>
</div></article>"""

    def filters(self) -> str:
        return """<section class="filters" aria-label="絞り込み">
<label>種類 <select id="f-type"><option value="">すべて</option><option value="hakumai">白米</option><option value="musenmai">無洗米</option><option value="genmai">玄米</option></select></label>
<label>容量 <select id="f-kg"><option value="">すべて</option><option value="2-4.9">2〜5kg未満</option><option value="5-5">5kg</option><option value="5.1-9.9">5〜10kg</option><option value="10-10">10kg</option><option value="10.1-30">10kg超</option></select></label>
<label>並び順 <select id="f-sort"><option value="eff">実質1kg単価が安い順</option><option value="price">価格が安い順</option><option value="review">レビュー評価が高い順</option></select></label>
<label class="chk"><input type="checkbox" id="f-new"> 新米だけ</label>
<label class="chk"><input type="checkbox" id="f-rv"> レビュー4.0以上</label>
<p id="f-count" class="count"></p></section>"""

    def listing(self, items: list[dict], path: str, title: str, h1: str, lead: str, desc: str, depth: int, label: str) -> None:
        n = self.site["ranking_size"]
        shown = items[:n]
        cards = "\n".join(self.card(i, k + 1) for k, i in enumerate(shown))
        ld = {
            "@context": "https://schema.org", "@type": "ItemList", "name": h1,
            "itemListElement": [{"@type": "ListItem", "position": k + 1, "name": i["name"][:120]} for k, i in enumerate(shown[:10])],
        }
        body = (self.head(title, desc, path, depth)
                + f'<h1>{e(h1)}</h1><p class="lead">{e(lead)}</p><p class="upd">最終更新：{e(self.updated)}（毎日自動更新）</p>'
                + self.stats_box(items, label) + self.pick_box(items) + self.filters()
                + f'<section id="list" class="list">{cards}</section>'
                + f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
                + self.foot(depth))
        self.write(path, body)

    # ---------- ページ ----------
    def build_all(self) -> None:
        items = self.items
        lead = "楽天市場で送料込みのお米を毎日集めて、ショップのポイント倍率まで引いた「1kgあたりの実質価格」で並べています。"
        self.listing(items, "index.html", f"お米の最安ランキング（1kgあたり実質価格・毎日更新）｜{self.site['site_name']}",
                     "お米 1kgあたり実質最安ランキング", lead,
                     "楽天市場のお米を送料込み・ポイント込みの1kgあたり実質価格で毎日比較。5kg・10kg・無洗米・玄米・新米で絞り込めます。", 0, "総合")
        for kg in (5, 10):
            sub = [i for i in items if i["kg"] == kg]
            self.listing(sub, f"size/{kg}kg.html", f"お米{kg}kgの最安ランキング（送料込み・毎日更新）｜{self.site['site_name']}",
                         f"お米 {kg}kg 実質最安ランキング", lead + f"このページは{kg}kgの商品だけを比べています。",
                         f"楽天市場のお米{kg}kgを送料込み・ポイント込みの実質価格で毎日比較。", 1, f"{kg}kg")
        for key, label in (("musenmai", "無洗米"), ("genmai", "玄米")):
            sub = [i for i in items if key in i["types"]]
            self.listing(sub, f"type/{key}.html", f"{label}の最安ランキング（1kgあたり実質価格）｜{self.site['site_name']}",
                         f"{label} 1kgあたり実質最安ランキング", lead + f"このページは{label}だけを比べています。",
                         f"楽天市場の{label}を送料込み・ポイント込みの1kgあたり実質価格で毎日比較。", 1, label)
        for b in self.cat["brands"]:
            sub = [i for i in items if b["slug"] in i["brands"]]
            if len(sub) >= self.cat["min_items_for_brand_page"]:
                self.listing(sub, f"brand/{b['slug']}.html", f"{b['label']}の最安ランキング（1kgあたり実質価格）｜{self.site['site_name']}",
                             f"{b['label']} 1kgあたり実質最安ランキング", lead + f"このページは商品名に「{b['label']}」とあるお米だけを比べています。",
                             f"楽天市場の{b['label']}を送料込み・ポイント込みの1kgあたり実質価格で毎日比較。", 1, b["label"])
        self.build_souba()
        self.build_about()
        self.build_404()
        self.build_brand_index()
        self.build_sitemap()

    def build_brand_index(self) -> None:
        links = []
        for b in self.cat["brands"]:
            if (self.out / f"brand/{b['slug']}.html").exists():
                cnt = sum(1 for i in self.items if b["slug"] in i["brands"])
                links.append(f'<li><a href="{b["slug"]}.html">{e(b["label"])}</a>（{cnt}件）</li>')
        body = (self.head(f"銘柄から探す｜{self.site['site_name']}", "コシヒカリ・あきたこまち・ゆめぴりかなど銘柄別のお米最安ランキング。", "brand/index.html", 1)
                + "<h1>銘柄から探す</h1><ul class=\"brands\">" + "".join(links) + "</ul>" + self.foot(1))
        self.write("brand/index.html", body)

    def chart_svg(self) -> str:
        pts = [h for h in self.history if h.get("median")]
        if len(pts) < 2:
            return '<p class="note">相場の推移は、毎日のデータがたまると表示されます（2日分から）。</p>'
        W, H, P = 900, 320, 48
        vals = [h["median"] for h in pts] + [h["p25"] for h in pts if h.get("p25")] + [h["p75"] for h in pts if h.get("p75")]
        lo, hi = min(vals) * 0.95, max(vals) * 1.05
        n = len(pts)

        def x(k):
            return P + (W - 2 * P) * (k / (n - 1))

        def y(v):
            return H - P - (H - 2 * P) * ((v - lo) / (hi - lo or 1))

        line = " ".join(f"{x(k):.1f},{y(h['median']):.1f}" for k, h in enumerate(pts))
        band_pts = [(k, h) for k, h in enumerate(pts) if h.get("p25") and h.get("p75")]
        band = ""
        if len(band_pts) >= 2:
            up = " ".join(f"{x(k):.1f},{y(h['p75']):.1f}" for k, h in band_pts)
            dn = " ".join(f"{x(k):.1f},{y(h['p25']):.1f}" for k, h in reversed(band_pts))
            band = f'<polygon points="{up} {dn}" fill="#F3D9C9" opacity="0.8"/>'
        ticks = ""
        for t in range(5):
            v = lo + (hi - lo) * t / 4
            ticks += f'<line x1="{P}" x2="{W-P}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="#E7E1DA"/><text x="{P-6}" y="{y(v)+4:.1f}" text-anchor="end" font-size="12" fill="#6B5E57">{int(v):,}</text>'
        labels = f'<text x="{P}" y="{H-P+20}" font-size="12" fill="#6B5E57">{e(pts[0]["date"])}</text><text x="{W-P}" y="{H-P+20}" font-size="12" text-anchor="end" fill="#6B5E57">{e(pts[-1]["date"])}</text>'
        return (f'<svg class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="お米の1kgあたり実質価格の中央値の推移">{ticks}{band}'
                f'<polyline points="{line}" fill="none" stroke="#B0222F" stroke-width="3"/>{labels}</svg>'
                '<p class="note">赤い線：比較した商品の1kgあたり実質価格の中央値。帯：安い方から25%〜75%の範囲（円/kg）。</p>')

    def build_souba(self) -> None:
        rows = "".join(
            f"<tr><td>{e(h['date'])}</td><td>{yen(h.get('median'))}</td><td>{yen(h.get('min'))}</td>"
            f"<td>{yen(h['by_type'].get('hakumai'))}</td><td>{yen(h['by_type'].get('musenmai'))}</td><td>{yen(h['by_type'].get('genmai'))}</td><td>{h.get('count', 0):,}</td></tr>"
            for h in reversed(self.history[-30:]))
        body = (self.head(f"楽天市場のお米の相場推移（1kgあたり実質価格）｜{self.site['site_name']}",
                          "楽天市場で送料込みのお米の1kgあたり実質価格（中央値・最安値）を毎日記録した相場推移。", "souba.html", 0)
                + "<h1>楽天市場のお米 相場推移</h1><p class=\"lead\">毎日集めた送料込みのお米の、1kgあたり実質価格の中央値と最安値を記録しています。</p>"
                + self.chart_svg()
                + "<h2>直近30日の記録（円/kg）</h2><div class=\"tw\"><table><tr><th>日付</th><th>中央値</th><th>最安</th><th>白米</th><th>無洗米</th><th>玄米</th><th>商品数</th></tr>"
                + rows + "</table></div>" + self.foot(0))
        self.write("souba.html", body)

    def build_about(self) -> None:
        body = (self.head(f"運営者・ランキングの決め方｜{self.site['site_name']}", "ランキングの計算方法、実質価格の考え方、広告表示について。", "about.html", 0)
                + f"""<h1>運営者・ランキングの決め方</h1>
<h2>このサイトについて</h2><p>{e(self.site['site_name'])}は、楽天市場で売られているお米を毎日自動で集め、「送料込み・ポイント込みで、1kgあたりいくらか」で比べられるようにしたサイトです。運営：{e(self.site['operator'])}</p>
<h2>ランキングの決め方</h2><ul>
<li>楽天市場の商品検索APIで、送料込み（送料無料を含む）・在庫ありのお米を集めます。</li>
<li>商品名から合計の重さを読み取り、「価格 ÷ 重さ」で1kgあたりの価格を出します。「5kg×2袋」は10kgとして計算します。重さが読み取れない商品や、重さを選ぶ商品は除外します。</li>
<li>実質価格は「価格 ×（1 − ショップのポイント倍率%）」です。例：ポイント5倍なら5%を引きます。SPUや買いまわりなど、人によって変わるポイントは含めません。</li>
<li>米粉・パックご飯・定期便・ふるさと納税の返礼品などは比較の対象外です。</li>
<li>順位は実質1kg単価だけで決めます。アフィリエイト報酬の有無や料率で順位を変えることはありません。</li></ul>
<h2>広告について</h2><p>{e(PR_TEXT)}</p>
<h2>情報の正確さについて</h2><p>価格・ポイント・在庫は取得した時点のもので、変わっていることがあります。購入の前に必ず楽天市場の商品ページで確認してください。商品名・価格などは楽天市場の情報をそのまま表示しています。</p>
<h2>データ提供</h2><p>{CREDIT_HTML}</p>"""
                + self.foot(0))
        self.write("about.html", body)

    def build_404(self) -> None:
        body = self.head("ページが見つかりません", "", "404.html", 0) + '<h1>ページが見つかりません</h1><p><a href="index.html">トップへ戻る</a></p>' + self.foot(0)
        self.write("404.html", body)

    def build_sitemap(self) -> None:
        d = self.now.strftime("%Y-%m-%d")
        urls = "".join(f"<url><loc>{e(self.base + '/' + p)}</loc><lastmod>{d}</lastmod></url>" for p in sorted(self.pages))
        self.write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>')
        self.write("robots.txt", f"User-agent: *\nAllow: /\nSitemap: {self.base}/sitemap.xml\n")
        (self.out / ".nojekyll").write_text("", encoding="utf-8")


def build(site: dict, cat: dict, items: list[dict], history: list[dict], now: datetime, out: Path) -> list[str]:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copytree(ROOT / "site" / "assets", out / "assets")
    s = Site(site, cat, items, history, now, out)
    s.build_all()
    return s.pages
