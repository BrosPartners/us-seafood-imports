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
from collections import defaultdict
from dataclasses import dataclass, field

import yaml

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


def load_config(path):
    with open(path, encoding="utf8") as fh:
        raw = yaml.safe_load(fh)
    return [Group(key=item["key"], label=item["label"],
                  product=item["product"],
                  countries=list(item.get("countries") or []))
            for item in raw]


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


def build(rows, groups, generated_at):
    months = sorted({f"{r['year']}-{r['month']}" for r in rows})
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
    parser = argparse.ArgumentParser(description="Dựng dashboard.json.")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    rows = read_rows(args.input)
    groups = load_config(args.config)
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
