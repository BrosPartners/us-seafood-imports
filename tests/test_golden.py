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
        if key == "pangasius" and country == "TAIWAN":
            # Sheet2!C57 (Pangasius/Taiwan) chỉ có MỘT ô công thức trong cả
            # hàng (cột L = 2023-09) và công thức đó là lỗi copy-paste của
            # chính file gốc: nó tham chiếu $C$6/$C$15 (khối Tilapia) thay vì
            # $C$49/$C$57 (khối Pangasius) — giá trị 91040 nó trả về trùng
            # khớp chính xác với Sheet2!row15 (Tilapia/Taiwan) col L, không
            # phải Taiwan-Pangasius. Đây là lỗi trong workbook gốc, không
            # phải lỗi build.py — bỏ qua nước này khỏi đối chiếu.
            continue
        got = take(got_all[country]["volume"])
        # Một vài ô trong Sheet2 không có công thức (giống hàng 32 mô tả
        # trong brief) — None nghĩa là "Excel không tính", bỏ qua, không
        # phải kỳ vọng giá trị 0.
        for a, b in zip(got, want):
            if b is None:
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
