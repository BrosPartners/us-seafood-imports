import io
import json
import pathlib
import urllib.error
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


def _fake_response(body):
    """Trả về context-manager giả lập urlopen() thành công."""
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return body

    return _Resp()


def _no_sleep(calls):
    """Ghi lại số giây backoff được yêu cầu, không thực sự chờ."""
    def sleep(seconds):
        calls.append(seconds)

    return sleep


def test_default_opener_surfaces_403_immediately_with_status_and_no_retry():
    attempts = []

    def urlopen(req, timeout):
        attempts.append(1)
        raise urllib.error.HTTPError(
            req.full_url, 403, "Forbidden", hdrs=None, fp=io.BytesIO(b"missing user-agent")
        )

    sleep_calls = []

    with pytest.raises(urllib.error.HTTPError) as excinfo:
        noaa._default_opener("http://example.test", urlopen=urlopen, sleep=_no_sleep(sleep_calls))

    assert excinfo.value.code == 403
    assert len(attempts) == 1
    assert sleep_calls == []


def test_default_opener_retries_transient_failure_then_succeeds():
    attempts = []

    def urlopen(req, timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise urllib.error.URLError("connection refused")
        return _fake_response(b'{"items": [], "hasMore": false}')

    sleep_calls = []

    result = noaa._default_opener("http://example.test", urlopen=urlopen, sleep=_no_sleep(sleep_calls))

    assert result == b'{"items": [], "hasMore": false}'
    assert len(attempts) == 2
    assert sleep_calls == [1]


def test_default_opener_raises_after_three_attempts_and_chains_original_exception():
    attempts = []
    original = urllib.error.URLError("timed out")

    def urlopen(req, timeout):
        attempts.append(1)
        raise original

    sleep_calls = []

    with pytest.raises(RuntimeError) as excinfo:
        noaa._default_opener("http://example.test", urlopen=urlopen, sleep=_no_sleep(sleep_calls))

    assert len(attempts) == 3
    assert "http://example.test" in str(excinfo.value)
    assert excinfo.value.__cause__ is original
    assert sleep_calls == [1, 2, 4]


def test_default_opener_does_not_retry_programming_errors():
    attempts = []

    def urlopen(req, timeout):
        attempts.append(1)
        raise TypeError("bug inside transport")

    sleep_calls = []

    with pytest.raises(TypeError):
        noaa._default_opener("http://example.test", urlopen=urlopen, sleep=_no_sleep(sleep_calls))

    assert len(attempts) == 1
    assert sleep_calls == []
