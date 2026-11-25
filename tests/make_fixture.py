"""動作確認用のサンプルデータ（架空の商品）を作る。本番では使わない。"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(7)
ROOT = Path(__file__).resolve().parent.parent
brands = ["新潟県産コシヒカリ", "秋田県産あきたこまち", "北海道産ゆめぴりか", "山形県産つや姫", "宮城県産ひとめぼれ",
          "北海道産ななつぼし", "熊本県産ヒノヒカリ", "国産ブレンド米", "複数原料米", "岩手県産ひとめぼれ"]
forms = ["{b} 5kg 令和8年産 送料無料", "{b} 10kg（5kg×2袋） 令和8年産", "【無洗米】{b} 5kg 令和7年産 送料無料",
         "{b} 玄米 10kg 令和8年産 新米", "{b} 精米 2kg×3袋 計6kg", "{b} 20kg 業務用 送料無料", "{b} 5kg/10kg 選べる",
         "米粉 {b} 1kg", "{b} 3kg 令和8年産", "{b} 白米/玄米 選べる 10kg"]
items = []
n = 0
for b in brands:
    for f in forms:
        n += 1
        name = f.format(b=b)
        kg = 5
        for k in (20, 10, 6, 5, 3, 2, 1):
            if f"{k}kg" in name or f"計{k}kg" in name:
                kg = k
                break
        base = random.randint(560, 980) if "ブレンド" not in b and "複数" not in b else random.randint(470, 620)
        price = int(base * kg / 10) * 10 + random.choice([0, 80, 180])
        items.append({
            "itemName": name, "itemCode": f"sample-shop{n % 9}:{n}", "itemPrice": price,
            "itemUrl": f"https://item.rakuten.co.jp/sample-shop{n % 9}/{n}/",
            "affiliateUrl": "", "shopName": f"サンプル米店{n % 9 + 1}号", "shopCode": f"sample-shop{n % 9}",
            "postageFlag": 0 if n % 11 else 1, "pointRate": random.choice([1, 1, 1, 2, 5, 10]),
            "pointRateStartTime": "2026-11-01 00:00", "pointRateEndTime": "2026-12-31 23:59",
            "reviewAverage": round(random.uniform(3.4, 4.8), 2), "reviewCount": random.choice([0, 3, 12, 48, 230, 1800]),
            "mediumImageUrls": [], "availability": 1,
        })
(ROOT / "fixtures/sample_rice.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

hist = []
d0 = date(2026, 11, 1)
m = 640
for k in range(24):
    m += random.randint(-12, 10)
    hist.append({"date": (d0 + timedelta(days=k)).isoformat(), "count": 300 + k, "median": m, "p25": m - 60, "p75": m + 70,
                 "min": m - 180, "by_type": {"hakumai": m, "musenmai": m + 30, "genmai": m - 40}})
(ROOT / "fixtures/sample_history.json").write_text(json.dumps(hist, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(items), "items")
