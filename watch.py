#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Weekly Torob price watch for HANDMADE soaps of the same kinds Arface makes.

Scope (owner's rule): only handmade soaps, only in Arface's own seven kinds —
snail, activated charcoal, clay, loofah, pomegranate, silk cocoon, glycerin.
Industrial/brand soaps, pharmacies and soap-making raw materials are excluded.

Reads Torob's public search API, keeps dated snapshots + a history CSV,
and writes a clean Persian report (report.md) with week-over-week changes.
Standard library only.
"""
import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SNAP_DIR = DATA / "snapshots"
API = "https://api.torob.com/v4/base-product/search/?query={q}&page=0"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

# (key, category title, Torob search query, words the product name MUST contain,
#  Arface's own soap name, own site price in Toman)
CATEGORIES = [
    ("snail", "صابون حلزون", "صابون دست ساز حلزون", ["حلزون"],
     "صابون حلزون آرفیس (پوست چرب و خشک)", 269000),
    ("charcoal", "صابون زغال فعال", "صابون دست ساز زغال فعال", ["زغال"],
     "صابون زغال فعال آرفیس", 258000),
    ("clay", "صابون خاک رس", "صابون دست ساز خاک رس", ["خاک رس", "خاک‌رس"],
     "صابون خاک رس آرفیس", 257000),
    ("loofah", "صابون لوفا", "صابون دست ساز لوفا", ["لوفا"],
     "صابون لوفا آرفیس", 242000),
    ("pomegranate", "صابون انار و عسل", "صابون دست ساز انار", ["انار"],
     "صابون انار و عسل آرفیس", 244000),
    ("silk", "صابون پیله ابریشم", "صابون دست ساز پیله ابریشم", ["پیله", "ابریشم"],
     "صابون پیله ابریشم آرفیس", 242000),
    ("glycerin", "صابون گلیسیرینه", "صابون دست ساز گلیسیرینه", ["گلیسیرین"],
     None, None),
]
# A listing counts as handmade only if one of these appears in its name or shop name.
HANDMADE_ANY = ["دست‌ساز", "دستساز", "دست ساز", "گیاهی", "طبیعی", "ارگانیک", "سنتی", "خانگی"]
# Industrial / mass brands and pharmacy products are not Arface's field.
BRAND_BLOCK = ["فیروز", "دیترون", "داو", "نیوآ", "لوکس", "جانسون", "صحت", "گلرنگ",
               "داروگر", "ایروکس", "هیدرودرم", "سینره", "کامان", "لپیور", "دکتر بیز"]
# Raw materials and soap-making supplies are not competitors.
EXCLUDE = ["پایه صابون", "مواد اولیه", "قالب صابون", "پارافین", "کیلویی",
           "اسانس", "رنگ صابون", "سود سوزآور", "شمع سازی", "شمع‌سازی"]
TOP_N = 5


def fa(n):
    return f"{n:,}"


def fetch(query):
    url = API.format(q=urllib.parse.quote(query))
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def clean_items(payload, must_words):
    items = []
    for it in payload.get("results", []):
        name = (it.get("name1") or "").strip()
        price = it.get("price") or 0
        shop = (it.get("shop_text") or "").strip()
        if shop.startswith("در "):
            shop = shop[3:].strip()
        if not name or not price:
            continue
        if not any(w in name for w in must_words):
            continue  # not this kind of soap
        haystack = name + " " + shop
        if not any(w in haystack for w in HANDMADE_ANY):
            continue  # not handmade
        if any(x in name for x in EXCLUDE) or any(x in name for x in BRAND_BLOCK):
            continue
        if "داروخانه" in shop:
            continue
        items.append({"name": name, "price": int(price), "shop": shop})
    items.sort(key=lambda x: x["price"])
    seen, out = set(), []
    for it in items:
        k = (it["name"], it["shop"])
        if k in seen:
            continue
        seen.add(k)
        out.append(it)
    return out[:TOP_N]


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    DATA.mkdir(exist_ok=True)
    SNAP_DIR.mkdir(exist_ok=True)
    latest_path = DATA / "latest.json"
    prev = {}
    if latest_path.exists():
        try:
            prev = json.loads(latest_path.read_text(encoding="utf-8")).get("categories", {})
        except Exception:
            prev = {}

    snapshot = {"date": today, "categories": {}}
    changes = []
    body = []
    hist_rows = []

    for key, title, query, must_words, own_name, own_price in CATEGORIES:
        try:
            items = clean_items(fetch(query), must_words)
            err = None
        except Exception as e:  # keep going; report the failure for this category
            items, err = [], str(e)
        snapshot["categories"][key] = {
            "title": title, "own_price": own_price, "items": items, "error": err,
        }
        body.append(f"## {title}")
        if own_name:
            body.append(f"- قیمت خودت (سایت آرفیس): {own_name} — {fa(own_price)} تومان")
        if err:
            body.append(f"- این هفته خوانده نشد (خطا: {err})")
        elif not items:
            body.append("- صابون دست‌ساز مشابهی این هفته پیدا نشد")
        else:
            cheap = items[0]
            body.append(
                f"- ارزان‌ترین دست‌ساز مشابه در ترب: {cheap['name']} — {fa(cheap['price'])} تومان — فروشگاه: {cheap['shop']}"
            )
            for i, it in enumerate(items, 1):
                body.append(f"{i}. {it['name']} — {fa(it['price'])} تومان — {it['shop']}")
                hist_rows.append([today, key, it["name"], it["shop"], it["price"]])
        p_items = (prev.get(key) or {}).get("items") or []
        if p_items and items and p_items[0]["price"] != items[0]["price"]:
            old, new = p_items[0]["price"], items[0]["price"]
            arrow = "ارزان‌تر شد" if new < old else "گران‌تر شد"
            changes.append(
                f"- {title}: ارزان‌ترین قیمت از {fa(old)} به {fa(new)} تومان رسید "
                f"({arrow}، {fa(abs(new - old))} تومان)"
            )
        body.append("")

    head = [f"# گزارش هفتگی پایش قیمت صابون دست‌ساز در ترب — {today}", ""]
    if changes:
        head += ["## تغییرهای این هفته نسبت به هفته قبل", ""] + changes + [""]
    elif prev:
        head += ["نسبت به هفته قبل، ارزان‌ترین قیمت هیچ دسته‌ای عوض نشده است.", ""]
    else:
        head += ["این اولین اجراست؛ قیمت‌های امروز مبنای مقایسه هفته‌های بعد شدند.", ""]

    (SNAP_DIR / f"{today}.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    latest_path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=1), encoding="utf-8")
    hist = DATA / "history.csv"
    new_file = not hist.exists()
    with hist.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["date", "category", "product", "shop", "price_toman"])
        w.writerows(hist_rows)
    (ROOT / "report.md").write_text("\n".join(head + body) + "\n", encoding="utf-8")
    total = sum(len(c["items"]) for c in snapshot["categories"].values())
    print(f"done {today}: {total} items, {len(changes)} changes")


if __name__ == "__main__":
    main()
