"""毎日の自動更新：取得 → 計算 → サイト生成 → チェック。

使い方:
  python -m pipeline.run            # 楽天APIから取得（本番）
  python -m pipeline.run --demo     # サンプルデータで動作確認（公開しない）
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from . import build, check, normalize, rakuten

ROOT = Path(__file__).resolve().parent.parent
JST = normalize.JST


def load(p: Path, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="サンプルデータで生成する")
    ap.add_argument("--out", default="dist")
    args = ap.parse_args()

    site = load(ROOT / "config/site.json", {})
    if os.environ.get("SITE_URL"):
        site["base_url"] = os.environ["SITE_URL"]
    cat = load(ROOT / "config/rice.json", {})
    now = datetime.now(JST)
    hist_path = ROOT / "data/history/rice.json"

    if args.demo:
        raw = load(ROOT / "fixtures/sample_rice.json", [])
        history = load(ROOT / "fixtures/sample_history.json", [])
        require_aff = False
    else:
        raw = rakuten.fetch_category(cat, site["base_url"])
        history = load(hist_path, [])
        require_aff = os.environ.get("REQUIRE_AFFILIATE", "1") == "1"

    items, reasons = normalize.enrich(raw, cat, now)
    summary = normalize.summarize(items, now)
    print(f"取得 {len(raw)}件 → 比較対象 {len(items)}件 / 除外 {reasons}")
    print(f"本日の相場: {summary}")

    errs = check.check_data(items, summary, history, site, require_aff)
    if errs:
        print("データチェックで止めました:\n- " + "\n- ".join(errs), file=sys.stderr)
        return 1

    history = [h for h in history if h["date"] != summary["date"]] + [summary]
    history = history[-site["history_days"]:]

    out = ROOT / args.out
    pages = build.build(site, cat, items, history, now, out)
    errs = check.check_pages(out, pages)
    if errs:
        print("ページチェックで止めました:\n- " + "\n- ".join(errs[:30]), file=sys.stderr)
        return 1

    if not args.demo:
        hist_path.parent.mkdir(parents=True, exist_ok=True)
        hist_path.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
        report = {"date": summary["date"], "raw": len(raw), "items": len(items), "excluded": reasons,
                  "pages": len(pages), "summary": summary}
        (ROOT / "data/last_run.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK: {len(pages)}ページを生成しました → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
