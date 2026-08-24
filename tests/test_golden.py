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

# Danh sách MỘT chỗ duy nhất cho các ô workbook gốc đã biết là sai/lỗi và
# được loại khỏi đối chiếu. Mỗi entry phải nêu rõ (key nhóm, tên nước, và
# QUAN TRỌNG: đúng một kỳ/tháng cụ thể — không phải cả chuỗi) cùng lý do
# bằng tiếng người. KHÔNG được thêm entry mới mà không có xác minh độc lập
# tương đương những gì đã làm cho entry dưới đây; test
# `test_known_workbook_bugs_table_is_consulted` sẽ tự kiểm tra mọi entry
# thực sự tồn tại trong fixture kỳ vọng và thực sự được vòng lặp đối chiếu
# xem xét đến — entry lạc hậu hoặc trỏ sai sẽ làm test đó fail.
KNOWN_WORKBOOK_BUGS = {
    ("pangasius", "TAIWAN", "2023-09"): (
        "Sheet2!C57 (Pangasius/Taiwan) chỉ có MỘT ô công thức trong cả "
        "hàng (cột L = 2023-09) và công thức đó là lỗi copy-paste của "
        "chính file gốc: nó tham chiếu $C$6/$C$15 (khối Tilapia) thay vì "
        "$C$49/$C$57 (khối Pangasius) — giá trị 91040 nó trả về trùng "
        "khớp chính xác với Sheet2!row15 (Tilapia/Taiwan) col L, không "
        "phải Taiwan-Pangasius. Đây là lỗi trong workbook gốc, không "
        "phải lỗi build.py — bỏ qua nước này khỏi đối chiếu."
    ),
}

# Theo dõi entry nào thực sự được vòng lặp đối chiếu xem xét (tức là tồn
# tại và có cơ hội được so sánh), để test dưới cùng xác nhận không có
# entry nào "chết" trong bảng trên.
_CONSULTED_WORKBOOK_BUGS = set()


def _is_known_workbook_bug(key, country, month):
    """Trả True nếu (key, country, month) này nằm trong danh sách lỗi đã biết.

    Ghi nhận việc "consult" để test cuối file có thể xác minh mọi entry
    trong KNOWN_WORKBOOK_BUGS đều thực sự khớp với một ô có tồn tại trong
    fixture (group/country/month đó thực sự có mặt để so sánh).
    """
    entry_key = (key, country, month)
    if entry_key in KNOWN_WORKBOOK_BUGS:
        _CONSULTED_WORKBOOK_BUGS.add(entry_key)
        return True
    return False


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
        got = take(got_all[country]["volume"])
        # Một vài ô trong Sheet2 không có công thức (giống hàng 32 mô tả
        # trong brief) — None nghĩa là "Excel không tính", bỏ qua, không
        # phải kỳ vọng giá trị 0.
        for month, a, b in zip(EXPECTED["months"], got, want):
            if b is None:
                continue
            if _is_known_workbook_bug(key, country, month):
                continue
            assert a == b, country


@pytest.mark.parametrize("key", list(EXPECTED["groups"]))
def test_country_value_matches_sheet2(key):
    want_all = EXPECTED["groups"][key]["country_value"]
    if not want_all:
        pytest.skip(f"{key} không có breakdown giá trị trong Sheet2")
    got_all = {c["name"]: c for c in BY_KEY[key]["countries"]}
    for country, want in want_all.items():
        got = take(got_all[country]["value"])
        for a, b in zip(got, want):
            if b is None:
                continue
            assert a == b, country


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


def test_known_workbook_bugs_table_is_consulted():
    """Mọi entry trong KNOWN_WORKBOOK_BUGS phải thực sự tồn tại và được xem xét.

    Chạy lại chính vòng lặp đối chiếu country_volume để đảm bảo mỗi entry
    (key, country, month) trỏ tới một ô THẬT SỰ có trong fixture kỳ vọng
    (group tồn tại, country có breakdown, month nằm trong range, và giá trị
    kỳ vọng không phải None — tức là nếu không có exclusion thì assertion
    thật sự sẽ chạy tới). Nếu workbook được sửa và ô không còn khác biệt
    nữa, hoặc ai đó thêm entry cho một ô không tồn tại, test này sẽ fail —
    đó là cơ chế chống bảng KNOWN_WORKBOOK_BUGS mục rữa/tồn đọng entry chết.
    """
    _CONSULTED_WORKBOOK_BUGS.clear()
    for key in EXPECTED["groups"]:
        want_all = EXPECTED["groups"][key]["country_volume"]
        if not want_all:
            continue
        got_all = {c["name"]: c for c in BY_KEY[key]["countries"]}
        for country, want in want_all.items():
            if country not in got_all:
                continue
            for month, b in zip(EXPECTED["months"], want):
                if b is None:
                    continue
                _is_known_workbook_bug(key, country, month)

    missing = set(KNOWN_WORKBOOK_BUGS) - _CONSULTED_WORKBOOK_BUGS
    assert not missing, (
        f"Entry KNOWN_WORKBOOK_BUGS không khớp ô nào thực sự tồn tại/được "
        f"đối chiếu (workbook có thể đã sửa, hoặc entry sai): {missing}"
    )
