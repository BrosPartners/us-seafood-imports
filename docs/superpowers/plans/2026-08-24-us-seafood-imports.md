# US Seafood Imports Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tự động kéo dữ liệu nhập khẩu thủy sản vào Mỹ từ NOAA ODS API hằng ngày và hiển thị Volume / Value / ASP của 6 nhóm cá phi lê đông lạnh trên một dashboard tĩnh chạy GitHub Pages, thay cho file Excel cập nhật tay.

**Architecture:** Ba tầng tách bạch giao tiếp qua file trên đĩa. `scripts/noaa.py` là lớp API thuần (phân trang, retry). `scripts/fetch.py` kéo toàn bộ lịch sử, gộp về grain year × month × product × country, ghi `data/trade_imports.csv`. `scripts/build.py` đọc CSV + `products.yml`, tính Volume/Value/ASP theo đúng công thức Sheet2 của file Excel gốc, ghi `data/dashboard.json`. Trang tĩnh đọc JSON đó. GitHub Actions chạy cron hằng ngày và commit khi dữ liệu đổi.

**Tech Stack:** Python 3.11 (stdlib `urllib` + PyYAML), pytest, HTML/CSS/JS thuần + Chart.js vendored, GitHub Actions, GitHub Pages.

## Global Constraints

- Endpoint NOAA duy nhất: `https://apps-st.fisheries.noaa.gov/ods/foss/trade_data/`. Không dùng `st.nmfs.noaa.gov` hay `apps-st.fisheries.noaa.gov/ords/` — cả hai đã chết.
- Mọi truy vấn lọc `source="IMP"` và `edible_code="E"`. Không lấy EXP/REX, không lấy hàng inedible.
- Khoảng thời gian bắt đầu cố định: **2023-01**. Kết thúc: tháng hiện tại.
- Grain dữ liệu: **year × month × product × country**. Luôn gộp bỏ `custom_district_name`.
- `year` và `month` trong API là **chuỗi**, month có số 0 đứng đầu (`"04"`). Excel dùng tên tháng tiếng Anh (`"April"`).
- ASP = `value / volume`, đơn vị USD/kg. `volume == 0` → `null`, không bao giờ chia cho 0.
- Không có Duty. Không tính `ASP after tariff`, không tính `% tariff estimated`.
- Không thêm dependency ngoài PyYAML và pytest. Không dùng `requests`, không dùng pandas.
- Không CDN ngoài trong trang web — vendor mọi thư viện vào `assets/`.
- User-Agent bắt buộc cho mọi request NOAA: `BrosPartners-us-seafood-imports/1.0`. Gọi API không kèm User-Agent bị trả 403.
- Toàn bộ chữ hiển thị trên dashboard bằng tiếng Việt.
- Repo: `us-seafood-imports` dưới org GitHub `BrosPartners`. Pages phục vụ nhánh `main` từ thư mục gốc, nên mọi link nội bộ phải là đường dẫn tương đối kèm đuôi `.html`.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `scripts/noaa.py` | Lớp API thuần: build URL, phân trang, retry. Không biết gì về sản phẩm hay CSV. |
| `scripts/fetch.py` | Driver: duyệt tháng, gộp district, guard co dữ liệu, ghi `data/trade_imports.csv`. |
| `scripts/build.py` | Đọc CSV + `products.yml`, tính chỉ tiêu, ghi `data/dashboard.json`. |
| `products.yml` | Cấu hình 6 nhóm sản phẩm và danh sách nước. Nguồn sự thật duy nhất về "dashboard hiển thị gì". |
| `tests/make_golden.py` | Script chạy một lần: trích Sheet1 + Sheet2 từ file Excel gốc thành fixture. |
| `tests/fixtures/sheet1_rows.csv` | Input golden — Sheet1 của 6 nhóm, đúng định dạng `fetch.py` sinh ra. |
| `tests/fixtures/sheet2_expected.json` | Expected golden — giá trị Sheet2 đã tính sẵn trong Excel. |
| `tests/fixtures/noaa_page1.json`, `noaa_page2.json` | Response NOAA đã ghi lại, dùng mock. |
| `tests/test_noaa.py` | Phân trang, retry, User-Agent. |
| `tests/test_fetch.py` | Gộp district, guard co dữ liệu, tháng rỗng, định dạng CSV. |
| `tests/test_build.py` | Dòng Other, ASP null, total_volume 6 nhóm, hình dạng JSON. |
| `tests/test_golden.py` | **Chốt chặn**: build.py khớp Sheet2 trên toàn bộ 2023-01 → 2026-04. |
| `index.html` | Khung trang. |
| `assets/app.js` | Đọc JSON, vẽ chart, render bảng, xuất CSV. |
| `assets/dashboard.css` | Style riêng của trang, dựa trên token của `portal.css`. |
| `assets/portal.css` | Sao chép từ `bp-data-portal` để đồng bộ nhận diện. |
| `assets/chart.umd.min.js` | Chart.js vendored. |
| `.github/workflows/update.yml` | Cron hằng ngày: fetch → build → commit khi đổi. |
| `README.md` | Cách chạy, cách thêm sản phẩm, cách deploy. |

---

## Task 1: Lớp API NOAA

**Files:**
- Create: `scripts/noaa.py`
- Create: `tests/test_noaa.py`
- Create: `tests/fixtures/noaa_page1.json`, `tests/fixtures/noaa_page2.json`
- Create: `.gitignore`, `requirements.txt`

**Interfaces:**
- Consumes: không có.
- Produces:
  - `noaa.BASE_URL: str`
  - `noaa.USER_AGENT: str`
  - `noaa.build_url(query: dict, limit: int, offset: int) -> str`
  - `noaa.fetch_month(year: str, month: str, opener=None) -> list[dict]` — trả về list các item thô của NOAA (mỗi item là dict có `name`, `cntry_name`, `kilos`, `val`, `custom_district_name`, …). `opener` là callable `(url: str) -> bytes`, mặc định dùng urllib; test truyền hàm giả.

- [ ] **Step 1: Tạo khung repo**

```bash
mkdir -p scripts tests/fixtures data assets .github/workflows
printf '__pycache__/\n*.pyc\n.pytest_cache/\n' > .gitignore
printf 'PyYAML>=6.0\npytest>=8.0\n' > requirements.txt
touch tests/__init__.py
```

- [ ] **Step 2: Ghi lại response thật của NOAA làm fixture**

Chạy đúng script này để tạo fixture (cần mạng, chỉ chạy một lần):

```bash
python - <<'PY'
import urllib.request, json, urllib.parse, io
UA = "BrosPartners-us-seafood-imports/1.0"
base = "https://apps-st.fisheries.noaa.gov/ods/foss/trade_data/"
q = urllib.parse.quote(json.dumps(
    {"year": "2026", "month": "04", "source": "IMP",
     "name": "TILAPIA (OREOCHROMIS SPP.) FILLET FROZEN"}))
for i, off in enumerate([0, 25], start=1):
    url = f"{base}?q={q}&limit=25&offset={off}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    data = json.load(urllib.request.urlopen(req, timeout=180))
    io.open(f"tests/fixtures/noaa_page{i}.json", "w", encoding="utf8").write(
        json.dumps(data, indent=1))
    print(f"page{i}: {len(data['items'])} items, hasMore={data.get('hasMore')}")
PY
```

Kỳ vọng in ra: `page1: 25 items, hasMore=True` và `page2: 13 items, hasMore=False`.

Nếu `page2` báo `hasMore=True`, nghĩa là NOAA đã hiệu chỉnh số và tháng đó giờ nhiều hơn 50 dòng. Sửa `limit=25` thành số nhỏ hơn cho tới khi trang 2 là trang cuối, rồi ghi lại con số thật vào Step 3.

- [ ] **Step 3: Viết test thất bại cho phân trang**

Tạo `tests/test_noaa.py`:

```python
import json
import pathlib
import urllib.parse
import pytest
from scripts import noaa

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def make_opener(pages):
    """Giả lập NOAA: trả lần lượt từng trang, ghi lại URL đã gọi."""
    calls = []

    def opener(url):
        calls.append(url)
        return json.dumps(pages[len(calls) - 1]).encode("utf8")

    opener.calls = calls
    return opener


def test_fetch_month_follows_pagination_until_has_more_is_false():
    pages = [
        json.loads((FIXTURES / "noaa_page1.json").read_text(encoding="utf8")),
        json.loads((FIXTURES / "noaa_page2.json").read_text(encoding="utf8")),
    ]
    opener = make_opener(pages)

    items = noaa.fetch_month("2026", "04", opener=opener)

    expected = len(pages[0]["items"]) + len(pages[1]["items"])
    assert len(items) == expected
    assert len(opener.calls) == 2


def test_fetch_month_stops_after_one_page_when_has_more_is_false():
    opener = make_opener([{"items": [{"kilos": 1}], "hasMore": False}])

    items = noaa.fetch_month("2026", "04", opener=opener)

    assert items == [{"kilos": 1}]
    assert len(opener.calls) == 1


def test_fetch_month_returns_empty_list_for_month_with_no_data():
    opener = make_opener([{"items": [], "hasMore": False}])

    assert noaa.fetch_month("2026", "12", opener=opener) == []


def test_build_url_filters_imports_and_edible_only():
    url = noaa.build_url({"year": "2026", "month": "04"}, limit=10, offset=0)
    decoded = urllib.parse.unquote(url)

    assert url.startswith(noaa.BASE_URL)
    assert '"source": "IMP"' in decoded
    assert '"edible_code": "E"' in decoded
    assert '"year": "2026"' in decoded
    assert '"month": "04"' in decoded
    assert "limit=10" in decoded
    assert "offset=0" in decoded


def test_build_url_percent_encodes_the_query_so_spaces_do_not_break_it():
    url = noaa.build_url({"name": "TILAPIA FILLET"}, limit=1, offset=0)

    assert " " not in url
```

- [ ] **Step 4: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_noaa.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts'` hoặc `AttributeError: module 'scripts.noaa' has no attribute 'fetch_month'`.

- [ ] **Step 5: Viết `scripts/noaa.py`**

```python
"""Lớp truy cập NOAA ODS trade_data API.

Chỉ biết cách gọi API và phân trang. Không biết gì về sản phẩm, CSV hay dashboard.
"""

import json
import time
import urllib.parse
import urllib.request

BASE_URL = "https://apps-st.fisheries.noaa.gov/ods/foss/trade_data/"
USER_AGENT = "BrosPartners-us-seafood-imports/1.0"
PAGE_SIZE = 10000

# Bộ lọc cố định cho mọi truy vấn: chỉ hàng nhập khẩu, chỉ hàng ăn được.
FIXED_FILTERS = {"source": "IMP", "edible_code": "E"}


def build_url(query, limit=PAGE_SIZE, offset=0):
    """Dựng URL truy vấn. `query` được trộn với FIXED_FILTERS."""
    merged = dict(query)
    merged.update(FIXED_FILTERS)
    q = urllib.parse.quote(json.dumps(merged))
    return f"{BASE_URL}?q={q}&limit={limit}&offset={offset}"


def _default_opener(url):
    """Gọi HTTP thật, retry 3 lần với backoff. NOAA trả 403 nếu thiếu User-Agent."""
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            })
            with urllib.request.urlopen(req, timeout=300) as resp:
                return resp.read()
        except Exception as exc:  # noqa: BLE001 - retry mọi lỗi mạng
            last = exc
            time.sleep(2 ** attempt)
    raise RuntimeError(f"NOAA API thất bại sau 3 lần thử: {url}") from last


def fetch_month(year, month, opener=None):
    """Lấy toàn bộ dòng nhập khẩu ăn được của một tháng.

    year, month là chuỗi: "2026", "04". Trả list dict thô của NOAA.
    Tháng chưa có dữ liệu trả về list rỗng — đó không phải lỗi.
    """
    opener = opener or _default_opener
    items = []
    offset = 0
    while True:
        url = build_url({"year": year, "month": month},
                        limit=PAGE_SIZE, offset=offset)
        payload = json.loads(opener(url))
        items.extend(payload.get("items", []))
        if not payload.get("hasMore"):
            return items
        offset += PAGE_SIZE
```

Tạo `scripts/__init__.py` rỗng để `from scripts import noaa` chạy được:

```bash
touch scripts/__init__.py
```

- [ ] **Step 6: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_noaa.py -v`
Expected: PASS, 5 passed.

- [ ] **Step 7: Commit**

```bash
git add scripts/ tests/ .gitignore requirements.txt
git commit -m "feat: NOAA ODS API client with pagination"
```

---

## Task 2: Kéo toàn bộ lịch sử và ghi CSV

**Files:**
- Create: `scripts/fetch.py`
- Create: `tests/test_fetch.py`
- Modify: không

**Interfaces:**
- Consumes: `noaa.fetch_month(year, month, opener=None) -> list[dict]`
- Produces:
  - `fetch.CSV_HEADER: list[str]` = `["year", "month", "product", "country", "volume_kg", "value_usd"]`
  - `fetch.START_YEAR: int` = `2023`, `fetch.START_MONTH: int` = `1`
  - `fetch.month_range(end_year: int, end_month: int) -> list[tuple[str, str]]` — trả `[("2023","01"), ...]` tới hết tháng end.
  - `fetch.aggregate(items: list[dict]) -> dict[tuple[str, str], tuple[int, int]]` — key `(product, country)`, value `(volume_kg, value_usd)`.
  - `fetch.to_rows(year: str, month: str, agg: dict) -> list[list]` — dòng CSV đã sắp xếp.
  - `fetch.shrank_too_much(old_row_count: int, new_row_count: int, tolerance: float = 0.20) -> bool`
  - `fetch.write_csv(path, rows) -> None`
  - `fetch.main(argv=None) -> int` — mã thoát 0 nếu thành công.

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_fetch.py`:

```python
import csv
import pytest
from scripts import fetch


def test_aggregate_sums_across_customs_districts():
    """NOAA trả mỗi cảng một dòng; ta phải gộp về mức nước."""
    items = [
        {"name": "TILAPIA FILLET", "cntry_name": "CHINA",
         "custom_district_name": "MIAMI, FL", "kilos": 100, "val": 500},
        {"name": "TILAPIA FILLET", "cntry_name": "CHINA",
         "custom_district_name": "SEATTLE, WA", "kilos": 250, "val": 900},
        {"name": "TILAPIA FILLET", "cntry_name": "VIETNAM",
         "custom_district_name": "MIAMI, FL", "kilos": 40, "val": 160},
    ]

    agg = fetch.aggregate(items)

    assert agg[("TILAPIA FILLET", "CHINA")] == (350, 1400)
    assert agg[("TILAPIA FILLET", "VIETNAM")] == (40, 160)
    assert len(agg) == 2


def test_aggregate_handles_empty_input():
    assert fetch.aggregate([]) == {}


def test_month_range_starts_at_january_2023_and_zero_pads():
    months = fetch.month_range(2023, 3)

    assert months == [("2023", "01"), ("2023", "02"), ("2023", "03")]


def test_month_range_spans_year_boundary():
    months = fetch.month_range(2024, 2)

    assert months[11] == ("2023", "12")
    assert months[12] == ("2024", "01")
    assert months[-1] == ("2024", "02")
    assert len(months) == 14


def test_to_rows_is_sorted_for_stable_diffs():
    """CSV phải ổn định thứ tự, nếu không git sẽ báo đổi dù số không đổi."""
    agg = {
        ("ZANDER FILLET", "PERU"): (1, 2),
        ("ALBACORE", "VIETNAM"): (3, 4),
        ("ALBACORE", "CHINA"): (5, 6),
    }

    rows = fetch.to_rows("2026", "04", agg)

    assert rows == [
        ["2026", "04", "ALBACORE", "CHINA", 5, 6],
        ["2026", "04", "ALBACORE", "VIETNAM", 3, 4],
        ["2026", "04", "ZANDER FILLET", "PERU", 1, 2],
    ]


def test_shrank_too_much_flags_a_twenty_five_percent_drop():
    assert fetch.shrank_too_much(1000, 750) is True


def test_shrank_too_much_allows_a_ten_percent_drop():
    assert fetch.shrank_too_much(1000, 900) is False


def test_shrank_too_much_allows_growth():
    assert fetch.shrank_too_much(1000, 1200) is False


def test_shrank_too_much_allows_first_run_with_no_previous_data():
    assert fetch.shrank_too_much(0, 500) is False


def test_write_csv_writes_header_and_rows(tmp_path):
    path = tmp_path / "out.csv"

    fetch.write_csv(path, [["2026", "04", "ALBACORE", "CHINA", 5, 6]])

    with open(path, newline="", encoding="utf8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == fetch.CSV_HEADER
    assert rows[1] == ["2026", "04", "ALBACORE", "CHINA", "5", "6"]
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_fetch.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.fetch'`.

- [ ] **Step 3: Viết `scripts/fetch.py`**

```python
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

from scripts import noaa

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
    if not os.path.exists(path):
        return 0
    with open(path, newline="", encoding="utf8") as fh:
        return max(sum(1 for _ in fh) - 1, 0)


def write_csv(path, rows):
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", newline="", encoding="utf8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(CSV_HEADER)
        writer.writerows(rows)


def main(argv=None):
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
```

- [ ] **Step 4: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_fetch.py -v`
Expected: PASS, 10 passed.

- [ ] **Step 5: Chạy thật một lần để sinh dữ liệu**

Run: `python -m scripts.fetch`
Expected: in ra từng tháng kèm số dòng thô (tháng 2026-04 khoảng 4.599 dòng), tháng chưa có số được liệt kê ở cuối, và tạo `data/trade_imports.csv` khoảng 88.000 dòng. Mất khoảng 3 phút.

Kiểm chứng nhanh — dòng Tilapia Việt Nam tháng 4/2026 phải đúng `640817` kg và `2853226` USD:

```bash
grep '^2026,04,"TILAPIA (OREOCHROMIS SPP.) FILLET FROZEN",VIETNAM' data/trade_imports.csv || \
grep '2026,04,TILAPIA (OREOCHROMIS SPP.) FILLET FROZEN,VIETNAM' data/trade_imports.csv
```

Expected: một dòng kết thúc bằng `,640817,2853226`.

- [ ] **Step 6: Commit**

```bash
git add scripts/fetch.py tests/test_fetch.py data/trade_imports.csv
git commit -m "feat: fetch full NOAA import history to CSV"
```

---

## Task 3: Cấu hình sản phẩm và dựng dashboard.json

**Files:**
- Create: `products.yml`
- Create: `scripts/build.py`
- Create: `tests/test_build.py`

**Interfaces:**
- Consumes: `data/trade_imports.csv` với header `fetch.CSV_HEADER`.
- Produces:
  - `build.Group` — dataclass với các field `key: str`, `label: str`, `product: str`, `countries: list[str]`.
  - `build.load_config(path) -> list[Group]`
  - `build.read_rows(path) -> list[dict]` — mỗi dict có khoá `year`, `month`, `product`, `country`, `volume_kg` (int), `value_usd` (int).
  - `build.asp(value: int, volume: int) -> float | None`
  - `build.build(rows: list[dict], groups: list[Group], generated_at: str) -> dict`
  - `build.main(argv=None) -> int`

Hình dạng `dashboard.json`:

```json
{
  "generated_at": "2026-08-24",
  "latest_period": "2026-06",
  "months": ["2023-01", "2023-02"],
  "total_volume": [123, 456],
  "groups": [
    {
      "key": "tilapia",
      "label": "Tilapia",
      "product": "TILAPIA (OREOCHROMIS SPP.) FILLET FROZEN",
      "volume": [14580033, 5888538],
      "value": [56480773, 20899429],
      "asp": [3.873844, 3.549],
      "countries": [
        {"name": "CHINA", "volume": [1, 2], "value": [3, 4], "asp": [3.0, 2.0]},
        {"name": "Other", "volume": [0, 0], "value": [0, 0], "asp": [null, null]}
      ]
    }
  ]
}
```

Mọi mảng có cùng độ dài với `months` và cùng thứ tự.

- [ ] **Step 1: Tạo `products.yml`**

```yaml
# Nguồn sự thật duy nhất về việc dashboard hiển thị nhóm nào.
# Thêm nhóm mới = thêm một mục ở đây. Không cần sửa code, không cần kéo lại
# dữ liệu, vì data/trade_imports.csv đã chứa toàn bộ 500 sản phẩm của NOAA.
#
# product  — phải trùng TUYỆT ĐỐI trường `name` của NOAA, kể cả dấu chấm và ngoặc.
# countries — danh sách nước muốn tách riêng. Phần còn lại gộp vào dòng "Other".
#             Để trống thì nhóm đó không có breakdown và không có dòng "Other".

- key: tilapia
  label: Tilapia
  product: "TILAPIA (OREOCHROMIS SPP.) FILLET FROZEN"
  countries: [CHINA, VIETNAM, TAIWAN, INDONESIA]

- key: pangasius
  label: Pangasius (cá tra)
  product: "CATFISH (PANGASIUS) FILLET FROZEN"
  countries: [VIETNAM, TAIWAN]

- key: haddock
  label: Haddock
  product: "GROUNDFISH HADDOCK FILLET FROZEN"
  countries: [CHINA, INDONESIA, NORWAY, CANADA, ICELAND]

- key: salmon
  label: Salmon Atlantic
  product: "SALMON ATLANTIC FILLET FROZEN"
  countries: []

- key: cod
  label: Cod NSPF
  product: "GROUNDFISH COD NSPF FILLET FROZEN"
  countries: [CHINA, INDONESIA, NORWAY, CANADA, ICELAND, ECUADOR, GREENLAND, VIETNAM]

- key: pollock
  label: Pollock Alaska
  product: "GROUNDFISH POLLOCK ALASKA FILLET FROZEN"
  countries: [CHINA, INDONESIA, UNITED KINGDOM, CANADA, ICELAND, ECUADOR, GREENLAND, VIETNAM]
```

- [ ] **Step 2: Viết test thất bại**

Tạo `tests/test_build.py`:

```python
import json
import pytest
from scripts import build


def rows(*tuples):
    """Helper: (year, month, product, country, volume, value) -> dict."""
    return [{"year": y, "month": m, "product": p, "country": c,
             "volume_kg": v, "value_usd": val}
            for (y, m, p, c, v, val) in tuples]


TILAPIA = "TILAPIA (OREOCHROMIS SPP.) FILLET FROZEN"


def group(key="tilapia", label="Tilapia", product=TILAPIA, countries=None):
    return build.Group(key=key, label=label, product=product,
                       countries=list(countries or []))


def test_asp_divides_value_by_volume():
    assert build.asp(56480773, 14580033) == pytest.approx(3.873844, abs=1e-6)


def test_asp_returns_none_when_volume_is_zero():
    assert build.asp(100, 0) is None


def test_group_totals_sum_all_countries_including_ones_not_listed():
    data = rows(
        ("2023", "01", TILAPIA, "CHINA", 100, 400),
        ("2023", "01", TILAPIA, "HONDURAS", 50, 250),
    )

    out = build.build(data, [group(countries=["CHINA"])], "2026-08-24")

    g = out["groups"][0]
    assert g["volume"] == [150]
    assert g["value"] == [650]


def test_other_row_is_the_remainder_after_listed_countries():
    data = rows(
        ("2023", "01", TILAPIA, "CHINA", 100, 400),
        ("2023", "01", TILAPIA, "HONDURAS", 50, 250),
        ("2023", "01", TILAPIA, "MEXICO", 30, 90),
    )

    out = build.build(data, [group(countries=["CHINA"])], "2026-08-24")

    countries = {c["name"]: c for c in out["groups"][0]["countries"]}
    assert countries["CHINA"]["volume"] == [100]
    assert countries["Other"]["volume"] == [80]
    assert countries["Other"]["value"] == [340]


def test_other_row_is_absent_when_group_has_no_country_list():
    data = rows(("2023", "01", TILAPIA, "CHILE", 10, 100))

    out = build.build(data, [group(countries=[])], "2026-08-24")

    assert out["groups"][0]["countries"] == []


def test_listed_country_with_no_imports_gets_zero_not_missing():
    """Pangasius Đài Loan tháng 4/2026 bằng 0 — phải là 0, không được biến mất."""
    data = rows(("2023", "01", TILAPIA, "VIETNAM", 10, 100))

    out = build.build(data, [group(countries=["VIETNAM", "TAIWAN"])], "2026-08-24")

    countries = {c["name"]: c for c in out["groups"][0]["countries"]}
    assert countries["TAIWAN"]["volume"] == [0]
    assert countries["TAIWAN"]["asp"] == [None]


def test_total_volume_sums_every_group():
    data = rows(
        ("2023", "01", TILAPIA, "CHINA", 100, 400),
        ("2023", "01", "COD", "NORWAY", 7, 70),
    )
    groups = [group(countries=[]),
              group(key="cod", label="Cod", product="COD", countries=[])]

    out = build.build(data, groups, "2026-08-24")

    assert out["total_volume"] == [107]


def test_months_are_sorted_and_zero_padded():
    data = rows(
        ("2024", "01", TILAPIA, "CHINA", 1, 1),
        ("2023", "12", TILAPIA, "CHINA", 1, 1),
        ("2023", "02", TILAPIA, "CHINA", 1, 1),
    )

    out = build.build(data, [group(countries=[])], "2026-08-24")

    assert out["months"] == ["2023-02", "2023-12", "2024-01"]
    assert out["latest_period"] == "2024-01"


def test_month_with_no_data_for_a_group_yields_zero_volume_and_null_asp():
    data = rows(
        ("2023", "01", TILAPIA, "CHINA", 100, 400),
        ("2023", "02", "COD", "NORWAY", 5, 50),
    )
    groups = [group(countries=[]),
              group(key="cod", label="Cod", product="COD", countries=[])]

    out = build.build(data, groups, "2026-08-24")

    tilapia = out["groups"][0]
    assert tilapia["volume"] == [100, 0]
    assert tilapia["asp"][1] is None


def test_load_config_reads_products_yml():
    groups = build.load_config("products.yml")

    keys = [g.key for g in groups]
    assert keys == ["tilapia", "pangasius", "haddock", "salmon", "cod", "pollock"]
    assert groups[0].product == TILAPIA
    assert groups[3].countries == []
    assert "VIETNAM" in groups[1].countries
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_build.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.build'`.

- [ ] **Step 4: Viết `scripts/build.py`**

```python
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
```

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_build.py -v`
Expected: PASS, 11 passed.

- [ ] **Step 6: Chạy thật**

Run: `python -m scripts.build`
Expected: `Đã ghi data/dashboard.json: 42 tháng, 6 nhóm, mới nhất 2026-06`

- [ ] **Step 7: Commit**

```bash
git add products.yml scripts/build.py tests/test_build.py data/dashboard.json
git commit -m "feat: build dashboard.json from raw CSV per Sheet2 formulas"
```

---

## Task 4: Test đối chiếu golden với file Excel gốc

Đây là chốt chặn quan trọng nhất của cả dự án: bằng chứng duy nhất cho thấy hệ thống mới thay được file cũ.

Ý tưởng: **input lấy từ Sheet1, expected lấy từ Sheet2.** Không vòng tròn, vì Sheet2 là kết quả các công thức SUMIFS mà `build.py` phải tự tính lại từ Sheet1.

**Files:**
- Create: `tests/make_golden.py`
- Create: `tests/fixtures/sheet1_rows.csv` (do script sinh)
- Create: `tests/fixtures/sheet2_expected.json` (do script sinh)
- Create: `tests/test_golden.py`

**Interfaces:**
- Consumes: `build.build`, `build.load_config`, `build.read_rows`, `fetch.CSV_HEADER`.
- Produces: không có (chỉ là test).

Bố cục Sheet2 đã bóc từ công thức trong file — cột `D` đến `AQ` là 2023-01 → 2026-04, hàng 3 là năm, hàng 5 là tên tháng:

| Nhóm | Tên SP ở ô | Volume | Value | ASP tổng | Breakdown volume | Breakdown value | ASP theo nước |
|---|---|---|---|---|---|---|---|
| tilapia | C6 | 7 | 8 | 30 | 13–16 (CN, VN, TW, ID) | 19–22 | 31, 33, 34 (CN, TW, ID) |
| pangasius | C49 | 50 | 51 | 59 | 56–57 (VN, TW) | — | — |
| haddock | C63 | 64 | 65 | 78 | 71–75 (CN, ID, NO, CA, IS) | — | — |
| salmon | C82 | 83 | 84 | 87 | — | — | — |
| cod | C91 | 92 | 93 | 107 | 98–105 (CN, ID, NO, CA, IS, EC, GL, VN) | — | — |
| pollock | C110 | 111 | 112 | 126 | 117–124 (CN, ID, UK, CA, IS, EC, GL, VN) | — | — |

Hàng 32 (ASP Việt Nam của tilapia) trong file gốc bị bỏ trống — không có công thức. Test bỏ qua hàng đó.

- [ ] **Step 1: Viết script sinh fixture**

Tạo `tests/make_golden.py`:

```python
"""Trích fixture golden từ file Excel gốc. Chạy một lần, kết quả commit vào repo.

    python tests/make_golden.py "<đường dẫn tới file giá cá nhập khẩu US - (final).xlsx>"

Input golden lấy từ Sheet1 (dữ liệu thô), expected lấy từ Sheet2 (giá trị đã
tính sẵn trong Excel). build.py phải tự đi từ cái thứ nhất tới cái thứ hai.
"""

import csv
import json
import os
import sys
from collections import defaultdict

import openpyxl

MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
MONTH_NUM = {name: f"{i + 1:02d}" for i, name in enumerate(MONTHS)}

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Bố cục Sheet2, bóc từ công thức trong file gốc.
LAYOUT = [
    {"key": "tilapia", "name_cell": 6, "volume": 7, "value": 8, "asp": 30,
     "breakdown_volume": {"CHINA": 13, "VIETNAM": 14, "TAIWAN": 15,
                          "INDONESIA": 16},
     "breakdown_value": {"CHINA": 19, "VIETNAM": 20, "TAIWAN": 21,
                         "INDONESIA": 22},
     "breakdown_asp": {"CHINA": 31, "TAIWAN": 33, "INDONESIA": 34}},
    {"key": "pangasius", "name_cell": 49, "volume": 50, "value": 51, "asp": 59,
     "breakdown_volume": {"VIETNAM": 56, "TAIWAN": 57},
     "breakdown_value": {}, "breakdown_asp": {}},
    {"key": "haddock", "name_cell": 63, "volume": 64, "value": 65, "asp": 78,
     "breakdown_volume": {"CHINA": 71, "INDONESIA": 72, "NORWAY": 73,
                          "CANADA": 74, "ICELAND": 75},
     "breakdown_value": {}, "breakdown_asp": {}},
    {"key": "salmon", "name_cell": 82, "volume": 83, "value": 84, "asp": 87,
     "breakdown_volume": {}, "breakdown_value": {}, "breakdown_asp": {}},
    {"key": "cod", "name_cell": 91, "volume": 92, "value": 93, "asp": 107,
     "breakdown_volume": {"CHINA": 98, "INDONESIA": 99, "NORWAY": 100,
                          "CANADA": 101, "ICELAND": 102, "ECUADOR": 103,
                          "GREENLAND": 104, "VIETNAM": 105},
     "breakdown_value": {}, "breakdown_asp": {}},
    {"key": "pollock", "name_cell": 110, "volume": 111, "value": 112,
     "asp": 126,
     "breakdown_volume": {"CHINA": 117, "INDONESIA": 118,
                          "UNITED KINGDOM": 119, "CANADA": 120,
                          "ICELAND": 121, "ECUADOR": 122, "GREENLAND": 123,
                          "VIETNAM": 124},
     "breakdown_value": {}, "breakdown_asp": {}},
]


def period_columns(sheet2):
    """Đọc hàng 3 (năm) và hàng 5 (tên tháng) -> {"2023-01": col_index}."""
    periods = {}
    for col in range(4, 60):
        year = sheet2.cell(3, col).value
        month = sheet2.cell(5, col).value
        if year is None or month is None:
            continue
        periods[f"{int(year)}-{MONTH_NUM[month]}"] = col
    return periods


def extract_sheet1(sheet1, products):
    """Gộp Sheet1 về grain (year, month, product, country) cho các SP quan tâm."""
    agg = defaultdict(lambda: [0, 0])
    for row in sheet1.iter_rows(min_row=3, values_only=True):
        if not row[0] or row[3] not in products:
            continue
        key = (str(row[0]), MONTH_NUM[row[1]], row[3], row[4])
        agg[key][0] += row[5] or 0
        agg[key][1] += row[6] or 0
    return agg


def cell(sheet2, row, col):
    value = sheet2.cell(row, col).value
    if isinstance(value, str):  # ô lỗi kiểu "#DIV/0!"
        return None
    return value


def main():
    path = sys.argv[1]
    book = openpyxl.load_workbook(path, data_only=True)
    sheet1, sheet2 = book["Sheet1"], book["Sheet2"]

    for spec in LAYOUT:
        spec["product"] = sheet2.cell(spec["name_cell"], 3).value

    products = {spec["product"] for spec in LAYOUT}
    periods = period_columns(sheet2)
    ordered = sorted(periods)

    os.makedirs(FIXTURES, exist_ok=True)

    agg = extract_sheet1(sheet1, products)
    csv_path = os.path.join(FIXTURES, "sheet1_rows.csv")
    with open(csv_path, "w", newline="", encoding="utf8") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(["year", "month", "product", "country",
                         "volume_kg", "value_usd"])
        for (year, month, product, country), (volume, value) in sorted(agg.items()):
            if f"{year}-{month}" in periods:
                writer.writerow([year, month, product, country, volume, value])

    expected = {"months": ordered, "groups": {}}
    for spec in LAYOUT:
        entry = {
            "product": spec["product"],
            "volume": [cell(sheet2, spec["volume"], periods[p]) for p in ordered],
            "value": [cell(sheet2, spec["value"], periods[p]) for p in ordered],
            "asp": [cell(sheet2, spec["asp"], periods[p]) for p in ordered],
            "country_volume": {}, "country_value": {}, "country_asp": {},
        }
        for field, name in (("breakdown_volume", "country_volume"),
                            ("breakdown_value", "country_value"),
                            ("breakdown_asp", "country_asp")):
            for country, row in spec[field].items():
                entry[name][country] = [cell(sheet2, row, periods[p])
                                        for p in ordered]
        expected["groups"][spec["key"]] = entry

    json_path = os.path.join(FIXTURES, "sheet2_expected.json")
    with open(json_path, "w", encoding="utf8") as fh:
        json.dump(expected, fh, ensure_ascii=False, indent=1)

    print(f"{csv_path}: {sum(1 for _ in open(csv_path, encoding='utf8')) - 1} dòng")
    print(f"{json_path}: {len(ordered)} tháng, {len(expected['groups'])} nhóm")
    print(f"Khoảng thời gian: {ordered[0]} -> {ordered[-1]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Chạy script sinh fixture**

```bash
python -m pip install openpyxl
python tests/make_golden.py "<đường dẫn tới file giá cá nhập khẩu US - (final).xlsx>"
```

Expected: khoảng `2530 dòng`, `40 tháng, 6 nhóm`, `Khoảng thời gian: 2023-01 -> 2026-04`.

Nếu số tháng khác 40, nghĩa là file Excel đã được cập nhật thêm — không sao, test tự bám theo `months` trong fixture.

`openpyxl` chỉ dùng cho script sinh fixture một lần, không phải dependency của hệ thống. Đừng thêm vào `requirements.txt`.

- [ ] **Step 3: Viết test golden**

Tạo `tests/test_golden.py`:

```python
"""Đối chiếu build.py với chính file Excel gốc.

Input: Sheet1 (dữ liệu thô). Expected: Sheet2 (giá trị Excel đã tính).
Đây là bằng chứng hệ thống mới thay được file cũ.
"""

import json
import pathlib
import pytest
from scripts import build

FIXTURES = pathlib.Path(__file__).parent / "fixtures"
ROOT = pathlib.Path(__file__).parent.parent

EXPECTED = json.loads((FIXTURES / "sheet2_expected.json").read_text(encoding="utf8"))
ROWS = build.read_rows(FIXTURES / "sheet1_rows.csv")
GROUPS = build.load_config(ROOT / "products.yml")
ACTUAL = build.build(ROWS, GROUPS, "test")

BY_KEY = {g["key"]: g for g in ACTUAL["groups"]}
# Fixture chỉ có tới 2026-04; build có thể có nhiều tháng hơn nếu ai đó
# trỏ nhầm input. Cắt về đúng các tháng của fixture.
SLICE = [ACTUAL["months"].index(m) for m in EXPECTED["months"]]


def take(series):
    return [series[i] for i in SLICE]


@pytest.mark.parametrize("key", list(EXPECTED["groups"]))
def test_product_name_matches_excel(key):
    assert BY_KEY[key]["product"] == EXPECTED["groups"][key]["product"]


@pytest.mark.parametrize("key", list(EXPECTED["groups"]))
def test_group_volume_matches_sheet2(key):
    assert take(BY_KEY[key]["volume"]) == EXPECTED["groups"][key]["volume"]


@pytest.mark.parametrize("key", list(EXPECTED["groups"]))
def test_group_value_matches_sheet2(key):
    assert take(BY_KEY[key]["value"]) == EXPECTED["groups"][key]["value"]


@pytest.mark.parametrize("key", list(EXPECTED["groups"]))
def test_group_asp_matches_sheet2(key):
    actual = take(BY_KEY[key]["asp"])
    for got, want in zip(actual, EXPECTED["groups"][key]["asp"]):
        if want is None:
            assert got is None
        else:
            assert got == pytest.approx(want, rel=1e-9)


@pytest.mark.parametrize("key", list(EXPECTED["groups"]))
def test_country_volume_matches_sheet2(key):
    want_all = EXPECTED["groups"][key]["country_volume"]
    if not want_all:
        pytest.skip(f"{key} không có breakdown trong Sheet2")
    got_all = {c["name"]: c for c in BY_KEY[key]["countries"]}
    for country, want in want_all.items():
        assert take(got_all[country]["volume"]) == want, country


@pytest.mark.parametrize("key", list(EXPECTED["groups"]))
def test_country_value_matches_sheet2(key):
    want_all = EXPECTED["groups"][key]["country_value"]
    if not want_all:
        pytest.skip(f"{key} không có breakdown giá trị trong Sheet2")
    got_all = {c["name"]: c for c in BY_KEY[key]["countries"]}
    for country, want in want_all.items():
        assert take(got_all[country]["value"]) == want, country


@pytest.mark.parametrize("key", list(EXPECTED["groups"]))
def test_country_asp_matches_sheet2(key):
    want_all = EXPECTED["groups"][key]["country_asp"]
    if not want_all:
        pytest.skip(f"{key} không có ASP theo nước trong Sheet2")
    got_all = {c["name"]: c for c in BY_KEY[key]["countries"]}
    for country, want in want_all.items():
        got = take(got_all[country]["asp"])
        for a, b in zip(got, want):
            if b is None:
                assert a is None, country
            else:
                assert a == pytest.approx(b, rel=1e-9), country


def test_other_row_closes_the_gap_to_group_total():
    """Tổng các nước liệt kê cộng Other phải bằng đúng tổng nhóm, mọi tháng."""
    for group_data in ACTUAL["groups"]:
        if not group_data["countries"]:
            continue
        for i in range(len(ACTUAL["months"])):
            parts = sum(c["volume"][i] for c in group_data["countries"])
            assert parts == group_data["volume"][i], (
                f"{group_data['key']} tháng {ACTUAL['months'][i]}")


def test_pangasius_april_2026_is_entirely_vietnamese():
    """Chốt kiểm tra thủ công: Pangasius 4/2026 100% từ Việt Nam, Other = 0."""
    i = ACTUAL["months"].index("2026-04")
    pangasius = BY_KEY["pangasius"]
    countries = {c["name"]: c for c in pangasius["countries"]}

    assert pangasius["volume"][i] == 7097924
    assert pangasius["value"][i] == 21700645
    assert countries["VIETNAM"]["volume"][i] == 7097924
    assert countries["TAIWAN"]["volume"][i] == 0
    assert countries["Other"]["volume"][i] == 0
    assert pangasius["asp"][i] == pytest.approx(3.057323, abs=1e-6)
```

- [ ] **Step 4: Chạy test golden**

Run: `python -m pytest tests/test_golden.py -v`
Expected: PASS. Khoảng 44 test (7 nhóm test × 6 nhóm SP, một số skip cho nhóm không có breakdown), cộng 2 test cuối.

Nếu có test fail, **không được sửa expected cho khớp**. Fail nghĩa là `build.py` tính sai hoặc `products.yml` liệt kê sai nước — sửa ở đó.

- [ ] **Step 5: Chạy toàn bộ test suite**

Run: `python -m pytest -v`
Expected: PASS toàn bộ.

- [ ] **Step 6: Commit**

```bash
git add tests/make_golden.py tests/test_golden.py tests/fixtures/
git commit -m "test: golden comparison against original Excel workbook"
```

---

## Task 5: Trang dashboard

**Files:**
- Create: `index.html`
- Create: `assets/app.js`
- Create: `assets/dashboard.css`
- Create: `assets/portal.css` (sao chép)
- Create: `assets/chart.umd.min.js` (vendored)
- Create: `assets/logo.png` (sao chép)

**Interfaces:**
- Consumes: `data/dashboard.json` với hình dạng đã định nghĩa ở Task 3.
- Produces: không có.

- [ ] **Step 1: Sao chép tài sản dùng chung và vendor Chart.js**

```bash
cp "../bp-data-portal/assets/portal.css" assets/portal.css
cp "../bp-data-portal/assets/logo.png" assets/logo.png
curl -L -o assets/chart.umd.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js
```

Kiểm tra file tải về là JavaScript thật, không phải trang lỗi:

```bash
head -c 100 assets/chart.umd.min.js
```

Expected: bắt đầu bằng `/*!` và có chữ `Chart.js v4.4.1`.

- [ ] **Step 2: Viết `index.html`**

```html
<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Nhập khẩu thủy sản vào Mỹ — Bros Partners</title>
<link rel="stylesheet" href="./assets/portal.css">
<link rel="stylesheet" href="./assets/dashboard.css">
</head>
<body>
<header class="page-head">
  <h1>Nhập khẩu thủy sản vào Mỹ</h1>
  <p class="subtitle">Sản lượng, giá trị và giá bình quân theo tháng — nguồn NOAA Fisheries.</p>
</header>

<nav class="group-tabs" id="group-tabs" aria-label="Chọn nhóm sản phẩm"></nav>

<main>
  <section class="kpi-row" id="kpi-row"></section>

  <section class="card">
    <h2>Sản lượng theo tháng</h2>
    <div class="chart-wrap"><canvas id="chart-volume"></canvas></div>
  </section>

  <section class="card">
    <h2>Giá bình quân (ASP, USD/kg)</h2>
    <div class="chart-wrap"><canvas id="chart-asp"></canvas></div>
  </section>

  <section class="card" id="share-card">
    <h2>Thị phần theo nước (sản lượng)</h2>
    <div class="chart-wrap"><canvas id="chart-share"></canvas></div>
  </section>

  <section class="card">
    <div class="card-head">
      <h2>Số liệu chi tiết</h2>
      <button type="button" id="export-csv" class="btn">Tải CSV</button>
    </div>
    <div class="table-wrap"><table id="data-table"></table></div>
  </section>
</main>

<footer class="page-foot">
  <p>Nguồn: <a href="https://apps-st.fisheries.noaa.gov/ods/foss/trade_data/" target="_blank" rel="noopener">NOAA Fisheries ODS — trade_data</a>. Chỉ gồm hàng nhập khẩu ăn được (IMP, edible).</p>
  <p class="warn">Số liệu <strong>không bao gồm thuế nhập khẩu</strong> — NOAA ODS API không cung cấp trường Calculated Duty. ASP là giá khai báo hải quan, chưa cộng thuế.</p>
  <p id="meta-line"></p>
</footer>

<script src="./assets/chart.umd.min.js"></script>
<script src="./assets/app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Viết `assets/dashboard.css`**

```css
/* Style riêng của dashboard. Màu, chữ, bo góc, bóng đều lấy từ token của
   portal.css để đồng bộ với các dashboard khác của Bros Partners. */

body {
  margin: 0;
  padding: var(--content-pad);
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: var(--font-sans);
  font-size: var(--text-body);
}

.page-head h1 {
  margin: 0 0 4px;
  font-size: var(--text-heading-lg);
  color: var(--accent-text);
}

.subtitle { margin: 0 0 var(--section-gap); color: var(--text-tertiary); }

.group-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: var(--section-gap);
}

.group-tabs button {
  padding: 7px 14px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-pill);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font: inherit;
  cursor: pointer;
  transition: background var(--dur-fast) var(--ease-standard);
}

.group-tabs button:hover { background: var(--bg-hover); }

.group-tabs button[aria-pressed="true"] {
  background: var(--accent-btn-bg);
  color: var(--accent-btn-fg);
  border-color: transparent;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  margin-bottom: var(--section-gap);
}

.kpi {
  background: var(--bg-surface);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--card-pad);
}

.kpi .label {
  font-size: var(--text-caption);
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--text-tertiary);
}

.kpi .value {
  font-size: var(--text-heading-lg);
  font-variant-numeric: tabular-nums;
  margin-top: 6px;
}

.card {
  background: var(--bg-surface);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow-sm);
  padding: var(--card-pad);
  margin-bottom: var(--section-gap);
}

.card h2 { margin: 0 0 14px; font-size: var(--text-heading-sm); }

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-head h2 { margin-bottom: 0; }

.chart-wrap { position: relative; height: 320px; }

.btn {
  padding: 6px 13px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--r-md);
  background: var(--bg-surface);
  color: var(--text-secondary);
  font: inherit;
  cursor: pointer;
}

.btn:hover { background: var(--bg-hover); }

/* Bảng rộng phải tự cuộn ngang, không được đẩy cả trang cuộn theo. */
.table-wrap { overflow-x: auto; margin-top: 12px; }

table { border-collapse: collapse; width: 100%; font-variant-numeric: tabular-nums; }

th, td {
  padding: 7px 10px;
  border-bottom: 1px solid var(--border-hairline);
  text-align: right;
  white-space: nowrap;
}

th:first-child, td:first-child { text-align: left; position: sticky; left: 0; background: var(--bg-surface); }

thead th { color: var(--text-tertiary); font-weight: 600; font-size: var(--text-body-sm); }

.page-foot {
  color: var(--text-tertiary);
  font-size: var(--text-body-sm);
  line-height: 1.6;
}

.page-foot a { color: var(--accent-text); }

.page-foot .warn {
  background: var(--brand-gold-soft);
  border-left: 3px solid var(--brand-gold);
  border-radius: var(--r-sm);
  padding: 9px 12px;
}
```

- [ ] **Step 4: Viết `assets/app.js`**

```javascript
/* Dashboard nhập khẩu thủy sản vào Mỹ.
   Đọc data/dashboard.json (tĩnh), vẽ 3 biểu đồ và 1 bảng.
   Không gọi API lúc chạy — mọi số đã tính sẵn lúc build. */

const SERIES_COLORS = ["--data-1", "--data-2", "--data-3", "--data-4",
                       "--data-5", "--data-6", "--data-7"];

const state = { data: null, activeKey: null, charts: {} };

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function formatKg(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("vi-VN").format(Math.round(value));
}

function formatUsdPerKg(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("vi-VN", { minimumFractionDigits: 2,
                                          maximumFractionDigits: 2 }).format(value);
}

function activeGroup() {
  return state.data.groups.find((g) => g.key === state.activeKey);
}

function renderTabs() {
  const nav = document.getElementById("group-tabs");
  nav.innerHTML = "";
  state.data.groups.forEach((group) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = group.label;
    button.setAttribute("aria-pressed", String(group.key === state.activeKey));
    button.addEventListener("click", () => {
      state.activeKey = group.key;
      render();
    });
    nav.appendChild(button);
  });
}

function renderKpis() {
  const group = activeGroup();
  const last = state.data.months.length - 1;
  const previous = last - 1;
  const volume = group.volume[last];
  const asp = group.asp[last];
  const aspPrev = previous >= 0 ? group.asp[previous] : null;
  let change = "—";
  if (asp !== null && aspPrev) {
    const pct = (asp / aspPrev - 1) * 100;
    change = `${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%`;
  }

  const cards = [
    ["Kỳ gần nhất", state.data.months[last]],
    ["Sản lượng (kg)", formatKg(volume)],
    ["ASP (USD/kg)", formatUsdPerKg(asp)],
    ["ASP so tháng trước", change],
  ];

  document.getElementById("kpi-row").innerHTML = cards.map(
    ([label, value]) =>
      `<div class="kpi"><div class="label">${label}</div>` +
      `<div class="value">${value}</div></div>`
  ).join("");
}

function drawChart(canvasId, config) {
  if (state.charts[canvasId]) state.charts[canvasId].destroy();
  state.charts[canvasId] = new Chart(
    document.getElementById(canvasId).getContext("2d"), config);
}

function baseOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index", intersect: false },
    scales: {
      y: { title: { display: true, text: yLabel },
           grid: { color: cssVar("--border-hairline") } },
      x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true } },
    },
  };
}

function renderVolumeChart() {
  const group = activeGroup();
  drawChart("chart-volume", {
    type: "bar",
    data: {
      labels: state.data.months,
      datasets: [{
        label: `${group.label} — sản lượng (kg)`,
        data: group.volume,
        backgroundColor: cssVar("--data-1"),
      }],
    },
    options: baseOptions("kg"),
  });
}

function renderAspChart() {
  const group = activeGroup();
  const datasets = [{
    label: "Toàn nhóm",
    data: group.asp,
    borderColor: cssVar("--data-1"),
    backgroundColor: cssVar("--data-1"),
    borderWidth: 2.5,
    pointRadius: 0,
    tension: 0.25,
  }];
  group.countries.forEach((country, i) => {
    if (country.name === "Other") return;
    datasets.push({
      label: country.name,
      data: country.asp,
      borderColor: cssVar(SERIES_COLORS[(i + 1) % SERIES_COLORS.length]),
      borderWidth: 1.5,
      pointRadius: 0,
      tension: 0.25,
    });
  });
  drawChart("chart-asp", {
    type: "line",
    data: { labels: state.data.months, datasets },
    options: baseOptions("USD/kg"),
  });
}

function renderShareChart() {
  const group = activeGroup();
  const card = document.getElementById("share-card");
  if (!group.countries.length) {
    card.hidden = true;
    return;
  }
  card.hidden = false;

  const options = baseOptions("kg");
  options.scales.y.stacked = true;
  options.scales.x.stacked = true;

  drawChart("chart-share", {
    type: "bar",
    data: {
      labels: state.data.months,
      datasets: group.countries.map((country, i) => ({
        label: country.name,
        data: country.volume,
        backgroundColor: cssVar(SERIES_COLORS[i % SERIES_COLORS.length]),
      })),
    },
    options,
  });
}

function tableMatrix() {
  const group = activeGroup();
  const header = ["Chỉ tiêu", ...state.data.months];
  const rows = [
    ["Sản lượng (kg)", ...group.volume.map(formatKg)],
    ["Giá trị (USD)", ...group.value.map(formatKg)],
    ["ASP (USD/kg)", ...group.asp.map(formatUsdPerKg)],
  ];
  group.countries.forEach((country) => {
    rows.push([`${country.name} — sản lượng (kg)`,
               ...country.volume.map(formatKg)]);
  });
  return { header, rows };
}

function renderTable() {
  const { header, rows } = tableMatrix();
  const table = document.getElementById("data-table");
  table.innerHTML =
    `<thead><tr>${header.map((h) => `<th>${h}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.map((r) =>
      `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

function exportCsv() {
  const group = activeGroup();
  const lines = [["Chỉ tiêu", ...state.data.months]];
  lines.push(["Sản lượng (kg)", ...group.volume]);
  lines.push(["Giá trị (USD)", ...group.value]);
  lines.push(["ASP (USD/kg)", ...group.asp.map((v) => (v === null ? "" : v))]);
  group.countries.forEach((country) => {
    lines.push([`${country.name} — sản lượng (kg)`, ...country.volume]);
    lines.push([`${country.name} — giá trị (USD)`, ...country.value]);
  });

  const csv = lines.map((row) =>
    row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(",")
  ).join("\n");

  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `nhap-khau-my-${group.key}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function render() {
  renderTabs();
  renderKpis();
  renderVolumeChart();
  renderAspChart();
  renderShareChart();
  renderTable();
}

async function init() {
  const response = await fetch("./data/dashboard.json");
  state.data = await response.json();
  state.activeKey = state.data.groups[0].key;

  document.getElementById("meta-line").textContent =
    `Dữ liệu tới ${state.data.latest_period} · cập nhật lần cuối ${state.data.generated_at}`;
  document.getElementById("export-csv").addEventListener("click", exportCsv);

  render();
}

init();
```

- [ ] **Step 5: Chạy thử trang**

Run: `python -m http.server 8021 --directory .`

Mở `http://localhost:8021/`. Kiểm tra:
- 6 tab hiện đúng nhãn tiếng Việt, tab đầu (Tilapia) đang được chọn.
- KPI hiện `2026-06`, sản lượng và ASP có số, không phải `—`.
- Ba biểu đồ vẽ ra, trục x là các tháng `2023-01` → `2026-06`.
- Bấm tab **Salmon Atlantic** → thẻ "Thị phần theo nước" biến mất (nhóm này không có breakdown).
- Bấm tab **Pangasius** → biểu đồ thị phần chỉ có Vietnam, Taiwan, Other.
- Bấm **Tải CSV** → tải về file mở bằng Excel không lỗi font tiếng Việt.
- Thu hẹp cửa sổ còn 400px → bảng tự cuộn ngang, cả trang không cuộn ngang theo.

- [ ] **Step 6: Commit**

```bash
git add index.html assets/
git commit -m "feat: static dashboard page with volume, ASP and country share"
```

---

## Task 6: Tự động hóa bằng GitHub Actions

**Files:**
- Create: `.github/workflows/update.yml`
- Create: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: `python -m scripts.fetch`, `python -m scripts.build`.
- Produces: không có.

- [ ] **Step 1: Viết workflow test**

Tạo `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [main]
  pull_request:

jobs:
  pytest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt
      - run: python -m pytest -v
```

- [ ] **Step 2: Viết workflow cập nhật dữ liệu**

Tạo `.github/workflows/update.yml`:

```yaml
name: Cập nhật dữ liệu NOAA

on:
  schedule:
    # 22:00 UTC hằng ngày = 05:00 giờ Việt Nam hôm sau.
    - cron: "0 22 * * *"
  workflow_dispatch:

concurrency:
  group: update-data
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - run: pip install -r requirements.txt

      # fetch.py tự dừng và trả mã lỗi nếu NOAA trả dữ liệu teo bất thường,
      # nên file cũ không bao giờ bị ghi đè bằng dữ liệu hỏng.
      - name: Kéo dữ liệu NOAA
        run: python -m scripts.fetch

      - name: Dựng dashboard.json
        run: python -m scripts.build

      - name: Chạy test golden
        run: python -m pytest -v

      - name: Commit nếu dữ liệu thay đổi
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          if git diff --quiet -- data/; then
            echo "Dữ liệu không đổi, không commit."
            exit 0
          fi
          LATEST=$(python -c "import json;print(json.load(open('data/dashboard.json'))['latest_period'])")
          git add data/
          git commit -m "data: cập nhật NOAA tới $LATEST"
          git push
```

Thứ tự các bước có chủ ý: **test golden chạy sau khi build, trước khi commit.** Nếu NOAA đổi tên sản phẩm hay hiệu chỉnh làm lệch số lịch sử, job fail và dữ liệu hỏng không bao giờ lên tới dashboard.

- [ ] **Step 3: Commit và đẩy lên GitHub**

```bash
git add .github/
git commit -m "ci: daily NOAA refresh and test workflows"
```

- [ ] **Step 4: Tạo repo trên org và đẩy lên**

```bash
gh repo create BrosPartners/us-seafood-imports --public --source=. --remote=origin --push
```

Nếu chưa đăng nhập `gh`, chạy `gh auth login` trước.

- [ ] **Step 5: Bật GitHub Pages**

```bash
gh api -X POST repos/BrosPartners/us-seafood-imports/pages \
  -f "source[branch]=main" -f "source[path]=/"
```

Đợi khoảng một phút rồi kiểm tra trang đã sống:

```bash
curl -sI https://brospartners.github.io/us-seafood-imports/ | head -1
curl -s https://brospartners.github.io/us-seafood-imports/data/dashboard.json | head -c 120
```

Expected: `HTTP/2 200` và JSON bắt đầu bằng `{"generated_at":`.

- [ ] **Step 6: Chạy thử workflow bằng tay**

```bash
gh workflow run "Cập nhật dữ liệu NOAA"
gh run watch
```

Expected: job xanh. Vì dữ liệu vừa mới kéo ở Task 2 nên bước cuối in `Dữ liệu không đổi, không commit.` — đó là kết quả đúng, chứng minh cơ chế chống commit rác hoạt động.

---

## Task 7: Gắn vào BP Data Portal và viết README

**Files:**
- Create: `README.md`
- Modify: `../bp-data-portal/dashboards.js`
- Create: `../bp-data-portal/nhap-khau-my.html`

**Interfaces:**
- Consumes: URL Pages `https://brospartners.github.io/us-seafood-imports/`.
- Produces: không có.

- [ ] **Step 1: Viết `README.md`**

````markdown
# US Seafood Imports

Dashboard sản lượng, giá trị và giá bình quân (ASP) hàng thủy sản nhập khẩu vào Mỹ,
dữ liệu NOAA Fisheries, cập nhật tự động hằng ngày.

URL production: https://brospartners.github.io/us-seafood-imports/

Thay cho file `giá cá nhập khẩu US - (final).xlsx` trước đây cập nhật tay.

## Nguồn dữ liệu

NOAA ODS `trade_data`: https://apps-st.fisheries.noaa.gov/ods/foss/trade_data/

Công khai, không cần API key. Bắt buộc gửi header `User-Agent`, thiếu là bị trả 403.

Lọc cố định `source=IMP` và `edible_code=E`. Grain sau khi gộp:
year × month × product × country.

**Không có số liệu thuế.** API không cung cấp trường Calculated Duty, nên dashboard
không có `ASP after tariff` và `% tariff estimated` như file Excel cũ. Duty chỉ tồn tại
trên giao diện web FOSS, mà giao diện đó chặn IP datacenter nên không tự động lấy được.

## Chạy local

```bash
pip install -r requirements.txt
python -m scripts.fetch     # ~3 phút, kéo lại toàn bộ từ 2023-01
python -m scripts.build     # nhanh
python -m http.server 8021 --directory .
```

## Thêm một nhóm sản phẩm mới

Thêm một mục vào `products.yml` rồi chạy `python -m scripts.build`. Không cần sửa code
và không cần kéo lại dữ liệu — `data/trade_imports.csv` đã chứa cả 500 sản phẩm của NOAA.

`product` phải trùng tuyệt đối trường `name` của NOAA. Tra tên đúng bằng:

```bash
python -c "import csv;print(sorted({r['product'] for r in csv.DictReader(open('data/trade_imports.csv',encoding='utf8'))}))" | tr ',' '\n' | grep -i shrimp
```

## Test

```bash
python -m pytest -v
```

`tests/test_golden.py` là chốt chặn quan trọng nhất: đối chiếu kết quả của `build.py`
với chính file Excel gốc trên toàn bộ 2023-01 → 2026-04. Input lấy từ Sheet1, expected
lấy từ Sheet2. Test này fail nghĩa là logic tính đã lệch khỏi file gốc — **sửa code,
đừng sửa fixture**.

Sinh lại fixture (chỉ khi file Excel gốc được cập nhật):

```bash
pip install openpyxl
python tests/make_golden.py "<đường dẫn tới file xlsx>"
```

## Tự động cập nhật

`.github/workflows/update.yml` chạy 22:00 UTC hằng ngày (05:00 giờ Việt Nam).
Chạy hằng ngày chứ không hằng tháng vì NOAA công bố trễ khoảng 1,5 tháng và không có
ngày cố định. Không có dữ liệu mới thì không commit.

Mỗi lần chạy kéo lại **toàn bộ** lịch sử, không kéo tăng dần, vì NOAA hiệu chỉnh lại
số của các tháng đã công bố.

Chặn an toàn: nếu NOAA trả về ít hơn 80% số dòng lần trước, `fetch.py` dừng và không
ghi đè. Test golden chạy trước bước commit nên dữ liệu hỏng không lên được dashboard.

## Deploy

GitHub Pages phục vụ thẳng nhánh `main` từ thư mục gốc. Không có bước build. Vì Pages
phục vụ ở đường dẫn con `/us-seafood-imports/`, mọi link nội bộ phải là đường dẫn
tương đối kèm đuôi `.html`.
````

- [ ] **Step 2: Commit README**

```bash
git add README.md
git commit -m "docs: README"
git push
```

- [ ] **Step 3: Thêm dashboard vào portal**

Sửa `../bp-data-portal/dashboards.js`, chèn object sau vào mảng `window.BP_DASHBOARDS`, ngay sau mục `cang-bien`:

```javascript
  {
    id: "nhap-khau-my",
    group: "Thị trường",
    icon: "trending",
    title: "Nhập khẩu thủy sản vào Mỹ",
    blurb: "Sản lượng, giá trị và giá bình quân (ASP) hàng thủy sản phi lê đông lạnh nhập vào Mỹ theo tháng — Tilapia, Pangasius, Haddock, Salmon, Cod, Pollock — kèm cơ cấu theo nước xuất khẩu. Nguồn NOAA Fisheries.",
    embedUrl: "https://brospartners.github.io/us-seafood-imports/",
    sourceUrl: "https://brospartners.github.io/us-seafood-imports/",
    cadence: "Hằng ngày lúc 05:00"
  },
```

- [ ] **Step 4: Tạo trang vỏ trong portal**

```bash
cd ../bp-data-portal
cp vi-mo.html nhap-khau-my.html
```

Trong `nhap-khau-my.html` sửa đúng ba chỗ:
1. `<title>` → `Nhập khẩu thủy sản vào Mỹ — BP Data Portal`
2. thuộc tính `data-dashboard` → `nhap-khau-my`
3. link trong `<noscript>` → `https://brospartners.github.io/us-seafood-imports/`

Kiểm tra không còn sót chuỗi cũ:

```bash
grep -n "vi-mo\|liquidity-crawler" nhap-khau-my.html
```

Expected: không in ra gì.

- [ ] **Step 5: Chạy thử portal**

```bash
python -m http.server 8020 --directory .
```

Mở `http://localhost:8020/`. Kiểm tra: mục mới hiện ở sidebar nhóm "Thị trường", bấm vào mở `nhap-khau-my.html`, dashboard hiện trong iframe và vẽ được biểu đồ.

- [ ] **Step 6: Commit portal**

```bash
git add dashboards.js nhap-khau-my.html
git commit -m "feat: add US seafood imports dashboard"
git push origin main
```

- [ ] **Step 7: Xác nhận production**

```bash
curl -sI https://brospartners.github.io/bp-data-portal/nhap-khau-my.html | head -1
```

Expected: `HTTP/2 200`.

---

## Ngoài phạm vi

Đã thống nhất trong spec, không làm ở kế hoạch này:

- Nạp Duty thủ công và các chỉ tiêu sau thuế (`ASP after tariff`, `% tariff estimated`).
- Dữ liệu xuất khẩu (`source=EXP`/`REX`).
- Hàng không ăn được (`edible_code` khác `E`).
- Bộ lọc động cho toàn bộ 500 sản phẩm trên giao diện.
- Sửa hay ghi ngược vào file Excel gốc.
