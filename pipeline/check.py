"""公開前の品質・規約チェック。1つでも失敗したら公開しない（前日のサイトがそのまま残る）。"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from .build import PR_TEXT

ALLOWED_LINK_HOSTS = {"hb.afl.rakuten.co.jp", "item.rakuten.co.jp", "www.rakuten.co.jp", "developers.rakuten.com", "webservice.rakuten.co.jp"}
BAD_STRINGS = ["None円", "undefined", "NaN円", "Traceback"]


def check_data(items: list[dict], summary: dict, history: list[dict], site: dict, require_affiliate: bool) -> list[str]:
    errs = []
    if len(items) < site["min_items_required"]:
        errs.append(f"比較できる商品が少なすぎます（{len(items)}件 < {site['min_items_required']}件）")
    lo, hi = site["price_per_kg_sane_range"]
    med = summary.get("median")
    if med is None or not (lo <= med <= hi):
        errs.append(f"1kgあたり中央値が異常です（{med}円）")
    prev = [h for h in history if h["date"] != summary["date"] and h.get("median")]
    if prev and med:
        p = prev[-1]["median"]
        change = abs(med - p) / p
        if change > site["max_daily_median_change"]:
            errs.append(f"中央値が前回から{change:.0%}変動しました（{p}→{med}円）。取得ミスの可能性があるため公開を止めます")
    if require_affiliate:
        non_aff = sum(1 for i in items if not i["is_affiliate"])
        if non_aff:
            errs.append(f"アフィリエイトリンクになっていない商品が{non_aff}件あります（RAKUTEN_AFFILIATE_ID を確認）")
    return errs


def check_pages(out: Path, pages: list[str]) -> list[str]:
    errs = []
    for p in pages:
        text = (out / p).read_text(encoding="utf-8")
        if PR_TEXT not in text:
            errs.append(f"{p}: PR表記がありません")
        if "Supported by Rakuten Developers" not in text:
            errs.append(f"{p}: 楽天のクレジット表記がありません")
        visible = re.sub(r"<script.*?</script>", "", text, flags=re.S)
        visible = re.sub(r"<[^>]+>", " ", visible)
        for bad in BAD_STRINGS:
            if bad in visible:
                errs.append(f"{p}: 表示に不正な文字列「{bad}」があります")
        for m in re.finditer(r'<a class="buy" href="([^"]+)"[^>]*rel="([^"]*)"', text):
            href, rel = m.group(1), m.group(2)
            host = urlparse(href.replace("&amp;", "&")).hostname or ""
            if host not in ALLOWED_LINK_HOSTS:
                errs.append(f"{p}: 想定外のリンク先 {host}")
            if "sponsored" not in rel:
                errs.append(f"{p}: 広告リンクに rel=sponsored がありません")
    return errs
