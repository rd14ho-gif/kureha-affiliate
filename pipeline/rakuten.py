"""楽天市場 商品検索API（2026-07-01版）から商品を取得する。

認証：applicationId + accessKey。Web型アプリは登録したサイトURLからの
リクエストのみ受け付けるため、Referer/Origin にサイトURLを付ける。
取得した生データはリポジトリに保存しない（楽天ウェブサービス規約 第10条）。
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

ENDPOINT = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
ELEMENTS = ",".join([
    "itemName", "itemCode", "itemPrice", "itemUrl", "affiliateUrl", "shopName", "shopCode",
    "postageFlag", "pointRate", "pointRateStartTime", "pointRateEndTime",
    "reviewAverage", "reviewCount", "mediumImageUrls", "availability",
])


class RakutenError(RuntimeError):
    pass


def _credentials() -> dict:
    app_id = os.environ.get("RAKUTEN_APP_ID", "").strip()
    access_key = os.environ.get("RAKUTEN_ACCESS_KEY", "").strip()
    if not app_id or not access_key:
        raise RakutenError("RAKUTEN_APP_ID / RAKUTEN_ACCESS_KEY が設定されていません")
    return {
        "app_id": app_id,
        "access_key": access_key,
        "affiliate_id": os.environ.get("RAKUTEN_AFFILIATE_ID", "").strip(),
    }


def _request(params: dict, referer: str, retries: int = 4) -> dict:
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    headers = {
        "User-Agent": "kureha-affiliate/1.0 (+%s)" % referer,
        "Referer": referer.rstrip("/") + "/",
        "Origin": referer.split("/", 3)[0] + "//" + referer.split("/", 3)[2],
        "Accept": "application/json",
    }
    delay = 2.0
    for attempt in range(retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise RakutenError(f"HTTP {e.code}: {body}") from e
        except urllib.error.URLError as e:
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
                continue
            raise RakutenError(f"接続エラー: {e}") from e
    raise RakutenError("リトライ上限に達しました")


def fetch_category(cat: dict, referer: str, sleep_sec: float = 1.2) -> list[dict]:
    """カテゴリ設定の queries を順に検索し、itemCode で重複を除いた商品リストを返す。"""
    cred = _credentials()
    api = cat.get("api", {})
    seen: dict[str, dict] = {}
    for q in cat["queries"]:
        for page in range(1, int(q.get("pages", 1)) + 1):
            params = {
                "applicationId": cred["app_id"],
                "accessKey": cred["access_key"],
                "keyword": q["keyword"],
                "page": page,
                "hits": api.get("hits", 30),
                "sort": api.get("sort", "standard"),
                "postageFlag": api.get("postageFlag", 1),
                "availability": api.get("availability", 1),
                "format": "json",
                "formatVersion": 2,
                "elements": ELEMENTS,
            }
            if cred["affiliate_id"]:
                params["affiliateId"] = cred["affiliate_id"]
            data = _request(params, referer)
            items = data.get("Items") or data.get("items") or []
            for it in items:
                if isinstance(it, dict) and "Item" in it:  # formatVersion 1 の形にも対応
                    it = it["Item"]
                code = it.get("itemCode")
                if code and code not in seen:
                    seen[code] = it
            page_count = int(data.get("pageCount") or 1)
            time.sleep(sleep_sec)
            if page >= page_count:
                break
    return list(seen.values())
