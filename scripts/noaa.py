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
