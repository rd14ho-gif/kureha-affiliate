"""楽天の商品データから「1kgあたり実質価格」などの独自データを計算する。

商品名・価格などの楽天のデータは書き換えず、そのまま表示用に残す。
計算した値（容量・1kg単価・実質価格・タグ）は別のフィールドとして足す。
"""
from __future__ import annotations

import re
import statistics
import unicodedata
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

_KG = r"(\d+(?:\.\d+)?)\s*(?:kg|キロ|キログラム)"
_G = r"(\d{3,5})\s*g(?![a-z])"
_MULT = r"\s*[x×\*]\s*(\d{1,2})\s*(?:袋|個|セット|点|p|パック)?"
RE_TOTAL = re.compile(r"(?:合計|計|総量)\s*" + _KG)
RE_KG_MULT = re.compile(_KG + _MULT)
RE_KG = re.compile(_KG)
RE_G_MULT = re.compile(_G + _MULT)
RE_REIWA = re.compile(r"(?:令和|r)\s*(\d{1,2})\s*年?\s*(?:産|度産)")
RE_YEAR = re.compile(r"(20\d{2})\s*年\s*(?:産|度産)")


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").lower()


def parse_weight_kg(name: str) -> float | None:
    """商品名から合計の重さ(kg)を読み取る。候補が食い違うときは None（除外）にする。"""
    t = nfkc(name)
    m = RE_TOTAL.search(t)
    if m:
        return float(m.group(1))
    totals: set[float] = set()
    spans: list[tuple[int, int]] = []
    for m in RE_KG_MULT.finditer(t):
        totals.add(round(float(m.group(1)) * int(m.group(2)), 2))
        spans.append(m.span())
    for m in RE_G_MULT.finditer(t):
        totals.add(round(int(m.group(1)) / 1000 * int(m.group(2)), 2))
        spans.append(m.span())
    singles: set[float] = set()
    for m in RE_KG.finditer(t):
        if any(a <= m.start() < b for a, b in spans):
            continue
        singles.add(round(float(m.group(1)), 2))
    if totals:
        # 「10kg(5kg×2)」のように単独表記と掛け算が一致すれば採用
        if len(totals) == 1:
            total = next(iter(totals))
            if not singles or singles <= {total} or max(singles) == total:
                return total
            return None
        return None
    if len(singles) == 1:
        return next(iter(singles))
    return None  # 「5kg/10kg 選べる」など複数あるものは単価が決まらないので除外


def _active_point_rate(item: dict, now: datetime) -> int:
    rate = int(item.get("pointRate") or 1)
    if rate <= 1:
        return 1
    start, end = item.get("pointRateStartTime"), item.get("pointRateEndTime")
    try:
        if start and datetime.strptime(start[:16], "%Y-%m-%d %H:%M").replace(tzinfo=JST) > now:
            return 1
        if end and datetime.strptime(end[:16], "%Y-%m-%d %H:%M").replace(tzinfo=JST) < now:
            return 1
    except ValueError:
        return 1
    return rate


def crop_year(name: str, now: datetime) -> int | None:
    t = nfkc(name)
    m = RE_YEAR.search(t)
    if m:
        y = int(m.group(1))
        return y if 2015 <= y <= now.year + 1 else None
    m = RE_REIWA.search(t)
    if m:
        y = 2018 + int(m.group(1))
        return y if 2019 <= y <= now.year + 1 else None
    return None


def enrich(items: list[dict], cat: dict, now: datetime | None = None) -> tuple[list[dict], dict]:
    """除外・計算をして表示用の商品リストと、除外理由の集計を返す。"""
    now = now or datetime.now(JST)
    lo, hi = cat["weight_kg_range"]
    excl = [nfkc(w) for w in cat["exclude_words"]]
    reasons = {"exclude_word": 0, "weight_unknown": 0, "weight_out_of_range": 0, "no_price": 0, "no_postage": 0}
    out = []
    for it in items:
        name = it.get("itemName", "")
        t = nfkc(name)
        if any(w in t for w in excl):
            reasons["exclude_word"] += 1
            continue
        price = int(it.get("itemPrice") or 0)
        if price <= 0:
            reasons["no_price"] += 1
            continue
        if int(it.get("postageFlag", 1)) != 0:
            # postageFlag: 0=送料込み/無料, 1=送料別
            reasons["no_postage"] += 1
            continue
        kg = parse_weight_kg(name)
        if kg is None:
            reasons["weight_unknown"] += 1
            continue
        if not (lo <= kg <= hi):
            reasons["weight_out_of_range"] += 1
            continue
        rate = _active_point_rate(it, now)
        effective = price * (1 - rate / 100)
        types = [k for k, v in cat["types"].items() if any(nfkc(w) in t for w in v["words"])]
        if "genmai" in types and ("白米" in t or "精米" in t):
            types = [x for x in types if x != "genmai"] + ["selectable"]
        brands = [b["slug"] for b in cat["brands"] if any(nfkc(w) in t for w in b["words"])]
        origins = [o for o in cat["origins"] if nfkc(o) in t]
        year = crop_year(name, now)
        imgs = it.get("mediumImageUrls") or []
        img = imgs[0] if imgs and isinstance(imgs[0], str) else (imgs[0].get("imageUrl") if imgs else "")
        out.append({
            "code": it.get("itemCode"),
            "name": name,
            "shop": it.get("shopName", ""),
            "price": price,
            "kg": kg,
            "yen_per_kg": round(price / kg),
            "point_rate": rate,
            "effective_yen_per_kg": round(effective / kg),
            "review_avg": float(it.get("reviewAverage") or 0),
            "review_count": int(it.get("reviewCount") or 0),
            "url": it.get("affiliateUrl") or it.get("itemUrl", ""),
            "is_affiliate": bool(it.get("affiliateUrl")),
            "image": img,
            "types": types,
            "brands": brands,
            "origins": origins,
            "year": year,
            "is_new_crop": year == now.year,
        })
    out.sort(key=lambda x: (x["effective_yen_per_kg"], -x["review_count"]))
    return out, reasons


def summarize(items: list[dict], now: datetime) -> dict:
    """その日の相場（1kgあたり実質価格の中央値など）をまとめる。生データではなく集計値だけを残す。"""
    def med(xs):
        return round(statistics.median(xs)) if xs else None

    def q(xs, p):
        if len(xs) < 4:
            return None
        return round(statistics.quantiles(xs, n=4)[p])

    eff = [i["effective_yen_per_kg"] for i in items]
    by_type = {}
    for key in ("musenmai", "genmai"):
        xs = [i["effective_yen_per_kg"] for i in items if key in i["types"]]
        by_type[key] = med(xs)
    hakumai = [i["effective_yen_per_kg"] for i in items if not ({"musenmai", "genmai"} & set(i["types"]))]
    by_type["hakumai"] = med(hakumai)
    return {
        "date": now.strftime("%Y-%m-%d"),
        "count": len(items),
        "median": med(eff),
        "p25": q(eff, 0),
        "p75": q(eff, 2),
        "min": min(eff) if eff else None,
        "by_type": by_type,
    }
