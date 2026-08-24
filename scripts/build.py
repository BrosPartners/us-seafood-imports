"""Dựng data/dashboard.json từ CSV thô + products.yml.

Công thức giữ nguyên như Sheet2 của file Excel gốc:
  volume = tổng volume_kg theo (tháng, sản phẩm)
  value  = tổng value_usd theo (tháng, sản phẩm)
  asp    = value / volume  (USD/kg)
Dòng "Other" = tổng nhóm trừ tổng các nước được liệt kê.

KHÔNG có Duty: NOAA ODS API không cung cấp trường Calculated Duty, nên
không tính được ASP after tariff hay % tariff estimated.
"""

import argparse
import csv
import datetime
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field

import yaml

from scripts import console
from scripts.fetch import month_range

DEFAULT_INPUT = os.path.join("data", "trade_imports.csv")
DEFAULT_CONFIG = "products.yml"
DEFAULT_OUTPUT = os.path.join("data", "dashboard.json")
OTHER_LABEL = "Other"


@dataclass
class Group:
    key: str
    label: str
    product: str
    countries: list = field(default_factory=list)
    known_absent: list = field(default_factory=list)


def load_config(path):
    with open(path, encoding="utf8") as fh:
        raw = yaml.safe_load(fh)
    return [Group(key=item["key"], label=item["label"],
                  product=item["product"],
                  countries=list(item.get("countries") or []),
                  known_absent=list(item.get("known_absent") or []))
            for item in raw]


class ConfigValidationError(ValueError):
    """products.yml có mục cấu hình không khớp dữ liệu thật.

    Raise thay vì âm thầm trả series toàn số 0 — một `product` gõ sai
    chính tả (vd. NOAA đổi tên) sẽ khiến cả nhóm biến mất khỏi dashboard
    mà không ai biết, nếu không có kiểm tra này.
    """


def validate_config(rows, groups):
    """Đối chiếu products.yml với dữ liệu thật, raise ConfigValidationError
    nêu đích danh mọi vấn đề nếu có (không dừng ở lỗi đầu tiên).

    - `product` không xuất hiện dòng nào trong dữ liệu -> lỗi.
    - Một `country` trong `countries` không có dòng nào cho `product` đó,
      xuyên suốt toàn bộ lịch sử -> lỗi, TRỪ KHI nước đó có mặt trong
      `known_absent` của chính nhóm.
    - `known_absent` liệt kê một nước không thực sự nằm trong `countries`
      -> lỗi (known_absent chỉ có nghĩa khi nước đó được tách riêng).
    - `known_absent` liệt kê một nước mà thực tế CÓ dữ liệu -> lỗi (danh
      sách known_absent đã lỗi thời, phải gỡ entry đó ra).
    """
    products_seen = {r["product"] for r in rows}
    pairs_seen = {(r["product"], r["country"]) for r in rows}

    errors = []
    for g in groups:
        if g.product not in products_seen:
            errors.append(
                f"Nhóm '{g.key}': product '{g.product}' không xuất hiện "
                "dòng nào trong dữ liệu (kiểm tra NOAA có đổi tên không).")
            continue

        for country in g.known_absent:
            if country not in g.countries:
                errors.append(
                    f"Nhóm '{g.key}': known_absent liệt kê '{country}' "
                    "nhưng nước này không có trong countries.")

        for country in g.countries:
            present = (g.product, country) in pairs_seen
            declared_absent = country in g.known_absent
            if not present and not declared_absent:
                errors.append(
                    f"Nhóm '{g.key}': country '{country}' không có dòng "
                    f"nào cho product '{g.product}' trong toàn bộ lịch sử "
                    "và không nằm trong known_absent.")
            if present and declared_absent:
                errors.append(
                    f"Nhóm '{g.key}': known_absent liệt kê '{country}' "
                    "nhưng nước này THỰC SỰ có dữ liệu — gỡ khỏi "
                    "known_absent trong products.yml.")

    if errors:
        raise ConfigValidationError("\n".join(errors))


def read_rows(path):
    with open(path, newline="", encoding="utf8") as fh:
        return [{"year": r["year"], "month": r["month"],
                 "product": r["product"], "country": r["country"],
                 "volume_kg": int(r["volume_kg"]),
                 "value_usd": int(r["value_usd"])}
                for r in csv.DictReader(fh)]


def asp(value, volume):
    """USD/kg. Volume bằng 0 thì không có giá — trả None, không chia cho 0."""
    if not volume:
        return None
    return value / volume


def top_unlisted_countries(rows, product, listed_countries, months, top_k=3):
    """Với mỗi tháng, trả về tối đa `top_k` nước KHÔNG có trong
    `listed_countries` đóng góp nhiều volume nhất vào dòng "Other" của
    `product`, sắp xếp giảm dần theo volume.

    Không nhằm liệt kê toàn bộ nước ẩn trong Other (sẽ làm phình
    dashboard.json) — chỉ lộ ra vài nước lớn nhất để nhà phân tích biết
    Other không chỉ toàn nước nhỏ lẻ.

    Trả về list độ dài len(months), mỗi phần tử là list các
    {"name": ..., "volume": ...} (có thể rỗng nếu tháng đó Other = 0 hoặc
    không có nước nào ngoài danh sách).
    """
    index = {m: i for i, m in enumerate(months)}
    n = len(months)
    listed = set(listed_countries)

    per_country = defaultdict(lambda: [0] * n)
    for r in rows:
        if r["product"] != product or r["country"] in listed:
            continue
        i = index[f"{r['year']}-{r['month']}"]
        per_country[r["country"]][i] += r["volume_kg"]

    result = []
    for i in range(n):
        entries = [(name, vols[i]) for name, vols in per_country.items()
                   if vols[i] > 0]
        entries.sort(key=lambda t: -t[1])
        result.append([{"name": name, "volume": vol}
                        for name, vol in entries[:top_k]])
    return result


def build(rows, groups, generated_at):
    present = sorted({f"{r['year']}-{r['month']}" for r in rows})
    if present:
        first_year, first_month = (int(x) for x in present[0].split("-"))
        last_year, last_month = (int(x) for x in present[-1].split("-"))
        months = [f"{y}-{m}" for y, m in
                  month_range(last_year, last_month, first_year, first_month)]
    else:
        months = []
    # Trục tháng liền mạch từ tháng sớm nhất tới muộn nhất CÓ DỮ LIỆU, kể cả
    # tháng NOAA không công bố gì ở giữa — tháng đó vẫn xuất hiện trên trục
    # với volume/value = 0 và asp = None (khoảng trống thấy được), thay vì
    # biến mất hoàn toàn khỏi biểu đồ.
    index = {m: i for i, m in enumerate(months)}
    n = len(months)

    # (product, country) -> [volume theo tháng], [value theo tháng]
    by_pair = defaultdict(lambda: ([0] * n, [0] * n))
    by_product = defaultdict(lambda: ([0] * n, [0] * n))
    for r in rows:
        i = index[f"{r['year']}-{r['month']}"]
        pair = by_pair[(r["product"], r["country"])]
        pair[0][i] += r["volume_kg"]
        pair[1][i] += r["value_usd"]
        prod = by_product[r["product"]]
        prod[0][i] += r["volume_kg"]
        prod[1][i] += r["value_usd"]

    out_groups = []
    total_volume = [0] * n
    for g in groups:
        volume, value = by_product.get(g.product, ([0] * n, [0] * n))
        volume, value = list(volume), list(value)
        for i in range(n):
            total_volume[i] += volume[i]

        countries = []
        if g.countries:
            listed_volume = [0] * n
            listed_value = [0] * n
            for name in g.countries:
                c_volume, c_value = by_pair.get((g.product, name),
                                                ([0] * n, [0] * n))
                c_volume, c_value = list(c_volume), list(c_value)
                for i in range(n):
                    listed_volume[i] += c_volume[i]
                    listed_value[i] += c_value[i]
                countries.append({
                    "name": name,
                    "volume": c_volume,
                    "value": c_value,
                    "asp": [asp(c_value[i], c_volume[i]) for i in range(n)],
                })
            other_volume = [volume[i] - listed_volume[i] for i in range(n)]
            other_value = [value[i] - listed_value[i] for i in range(n)]
            countries.append({
                "name": OTHER_LABEL,
                "volume": other_volume,
                "value": other_value,
                "asp": [asp(other_value[i], other_volume[i]) for i in range(n)],
                "top_unlisted": top_unlisted_countries(
                    rows, g.product, g.countries, months),
            })

        out_groups.append({
            "key": g.key,
            "label": g.label,
            "product": g.product,
            "volume": volume,
            "value": value,
            "asp": [asp(value[i], volume[i]) for i in range(n)],
            "countries": countries,
        })

    return {
        "generated_at": generated_at,
        "latest_period": months[-1] if months else None,
        "months": months,
        "total_volume": total_volume,
        "groups": out_groups,
    }


def main(argv=None):
    console.fix_stdio_encoding()
    parser = argparse.ArgumentParser(description="Dựng dashboard.json.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    rows = read_rows(args.input)
    groups = load_config(args.config)
    try:
        validate_config(rows, groups)
    except ConfigValidationError as exc:
        print("LỖI: products.yml không khớp dữ liệu thật:", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        return 1
    payload = build(rows, groups,
                    datetime.date.today().isoformat())

    directory = os.path.dirname(args.output)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(args.output, "w", encoding="utf8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"Đã ghi {args.output}: {len(payload['months'])} tháng, "
          f"{len(payload['groups'])} nhóm, mới nhất {payload['latest_period']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
