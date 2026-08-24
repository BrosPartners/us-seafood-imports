"""Kéo toàn bộ lịch sử nhập khẩu thủy sản từ NOAA và ghi ra CSV.

Mỗi lần chạy kéo lại từ 2023-01 tới tháng hiện tại, vì NOAA hiệu chỉnh lại
số của các tháng đã công bố.
"""

import argparse
import csv
import datetime
import os
import sys
from collections import defaultdict

from scripts import console, noaa

CSV_HEADER = ["year", "month", "product", "country", "volume_kg", "value_usd"]
START_YEAR = 2023
START_MONTH = 1
DEFAULT_OUTPUT = os.path.join("data", "trade_imports.csv")
SHRINK_TOLERANCE = 0.20


def month_range(end_year, end_month):
    """Trả list ("YYYY", "MM") từ 2023-01 tới end_year/end_month, đã zero-pad."""
    months = []
    year, month = START_YEAR, START_MONTH
    while (year, month) <= (end_year, end_month):
        months.append((str(year), f"{month:02d}"))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return months


def aggregate(items):
    """Gộp bỏ chiều cảng nhập, về grain (product, country)."""
    agg = defaultdict(lambda: [0, 0])
    for item in items:
        key = (item["name"], item["cntry_name"])
        agg[key][0] += item["kilos"] or 0
        agg[key][1] += item["val"] or 0
    return {k: (v[0], v[1]) for k, v in agg.items()}


def to_rows(year, month, agg):
    """Đổi dict gộp thành dòng CSV, sắp xếp để diff git ổn định."""
    return [[year, month, product, country, volume, value]
            for (product, country), (volume, value) in sorted(agg.items())]


def shrank_too_much(old_row_count, new_row_count, tolerance=SHRINK_TOLERANCE):
    """True nếu dữ liệu mới teo quá ngưỡng — dấu hiệu NOAA trả dữ liệu lỗi."""
    if old_row_count == 0:
        return False
    return new_row_count < old_row_count * (1 - tolerance)


def count_existing_rows(path):
    """Đếm số dòng DỮ LIỆU (không tính header) bằng csv.reader, không đếm
    newline vật lý — field bị quote có thể chứa newline nhúng bên trong,
    khiến đếm dòng vật lý ra sai số. Đọc theo stream để không load cả file
    (5.5 MB) vào bộ nhớ."""
    if not os.path.exists(path):
        return 0
    with open(path, newline="", encoding="utf8") as fh:
        reader = csv.reader(fh)
        row_count = sum(1 for _ in reader)
    return max(row_count - 1, 0)


def write_csv(path, rows):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", newline="", encoding="utf8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


def main(argv=None):
    console.fix_stdio_encoding()
    parser = argparse.ArgumentParser(description="Kéo dữ liệu NOAA về CSV.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    today = datetime.date.today()
    all_rows = []
    empty_months = []
    for year, month in month_range(today.year, today.month):
        items = noaa.fetch_month(year, month)
        if not items:
            empty_months.append(f"{year}-{month}")
            continue
        all_rows.extend(to_rows(year, month, aggregate(items)))
        print(f"{year}-{month}: {len(items)} dòng thô", file=sys.stderr)

    if not all_rows:
        print("LỖI: NOAA không trả về dòng nào cho bất kỳ tháng nào.",
              file=sys.stderr)
        return 1

    previous = count_existing_rows(args.output)
    if shrank_too_much(previous, len(all_rows)):
        print(f"LỖI: dữ liệu teo bất thường ({previous} -> {len(all_rows)} dòng). "
              "Không ghi đè.", file=sys.stderr)
        return 1

    write_csv(args.output, all_rows)
    print(f"Đã ghi {len(all_rows)} dòng vào {args.output}. "
          f"Tháng chưa có số: {', '.join(empty_months) or 'không'}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
