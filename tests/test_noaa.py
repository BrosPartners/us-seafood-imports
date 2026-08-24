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
