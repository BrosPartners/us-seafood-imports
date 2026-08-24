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


def test_months_are_sorted_and_contiguous_from_earliest_to_latest():
    """Trục tháng phải liền mạch từ tháng sớm nhất tới muộn nhất có dữ liệu,
    kể cả khi input không theo thứ tự — không chỉ liệt kê các tháng có mặt."""
    data = rows(
        ("2024", "01", TILAPIA, "CHINA", 1, 1),
        ("2023", "12", TILAPIA, "CHINA", 1, 1),
        ("2023", "02", TILAPIA, "CHINA", 1, 1),
    )

    out = build.build(data, [group(countries=[])], "2026-08-24")

    assert out["months"] == [
        "2023-02", "2023-03", "2023-04", "2023-05", "2023-06", "2023-07",
        "2023-08", "2023-09", "2023-10", "2023-11", "2023-12", "2024-01",
    ]
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


def test_load_config_reads_known_absent():
    groups = build.load_config("products.yml")
    by_key = {g.key: g for g in groups}

    assert by_key["pangasius"].known_absent == ["TAIWAN"]
    assert set(by_key["pollock"].known_absent) == {
        "UNITED KINGDOM", "ECUADOR", "GREENLAND"}
    assert by_key["tilapia"].known_absent == []


def test_interior_month_missing_from_data_still_appears_zeroed_on_axis():
    """NOAA bỏ tháng 03 giữa 02 và 04 — tháng đó phải vẫn xuất hiện trên
    trục thời gian, khối lượng = 0, asp = None (khoảng trống thấy được),
    không phải biến mất khỏi biểu đồ."""
    data = rows(
        ("2023", "02", TILAPIA, "CHINA", 100, 400),
        ("2023", "04", TILAPIA, "CHINA", 50, 200),
    )

    out = build.build(data, [group(countries=[])], "2026-08-24")

    assert out["months"] == ["2023-02", "2023-03", "2023-04"]
    tilapia = out["groups"][0]
    assert tilapia["volume"] == [100, 0, 50]
    assert tilapia["asp"][1] is None


def test_validate_config_fails_on_product_not_in_data():
    data = rows(("2023", "01", TILAPIA, "CHINA", 1, 1))
    bad_group = group(product="NO SUCH PRODUCT")

    with pytest.raises(build.ConfigValidationError, match="NO SUCH PRODUCT"):
        build.validate_config(data, [bad_group])


def test_validate_config_fails_on_country_missing_from_data():
    data = rows(("2023", "01", TILAPIA, "CHINA", 1, 1))
    bad_group = group(countries=["HONDURAS"])

    with pytest.raises(build.ConfigValidationError, match="HONDURAS"):
        build.validate_config(data, [bad_group])


def test_validate_config_allows_known_absent_country():
    data = rows(("2023", "01", TILAPIA, "CHINA", 1, 1))
    ok_group = group(countries=["CHINA", "HONDURAS"])
    ok_group.known_absent = ["HONDURAS"]

    build.validate_config(data, [ok_group])  # không raise


def test_validate_config_fails_when_known_absent_actually_has_data():
    data = rows(("2023", "01", TILAPIA, "HONDURAS", 1, 1))
    stale_group = group(countries=["HONDURAS"])
    stale_group.known_absent = ["HONDURAS"]

    with pytest.raises(build.ConfigValidationError, match="HONDURAS"):
        build.validate_config(data, [stale_group])


def test_validate_config_fails_when_known_absent_not_in_countries():
    data = rows(("2023", "01", TILAPIA, "CHINA", 1, 1))
    bad_group = group(countries=["CHINA"])
    bad_group.known_absent = ["HONDURAS"]

    with pytest.raises(build.ConfigValidationError, match="HONDURAS"):
        build.validate_config(data, [bad_group])


def test_validate_config_passes_against_real_committed_data():
    rows_real = build.read_rows("data/trade_imports.csv")
    groups_real = build.load_config("products.yml")

    build.validate_config(rows_real, groups_real)  # không raise
