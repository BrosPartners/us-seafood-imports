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


def test_count_existing_rows_counts_csv_rows_not_physical_lines(tmp_path):
    """Một field chứa newline nhúng phải tính là 1 dòng, không phải 2."""
    path = tmp_path / "embedded_newline.csv"
    fetch.write_csv(path, [
        ["2026", "04", "ALBACORE\nWITH LINE BREAK", "CHINA", 5, 6],
        ["2026", "04", "TILAPIA", "VIETNAM", 1, 2],
    ])

    assert fetch.count_existing_rows(path) == 2


def test_count_existing_rows_header_only_is_zero(tmp_path):
    path = tmp_path / "header_only.csv"
    fetch.write_csv(path, [])

    assert fetch.count_existing_rows(path) == 0


def test_count_existing_rows_missing_file_is_zero(tmp_path):
    path = tmp_path / "does_not_exist.csv"

    assert fetch.count_existing_rows(path) == 0


def test_count_existing_rows_plain_multi_row_file(tmp_path):
    path = tmp_path / "multi_row.csv"
    fetch.write_csv(path, [
        ["2026", "04", "ALBACORE", "CHINA", 5, 6],
        ["2026", "04", "TILAPIA", "VIETNAM", 1, 2],
        ["2026", "04", "ZANDER FILLET", "PERU", 3, 4],
    ])

    assert fetch.count_existing_rows(path) == 3
