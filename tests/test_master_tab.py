"""Test các hàm thuần của tab Tổng hợp, gọi qua Node vào chính assets/app.js.

Không có framework test JS trong repo và ràng buộc cấm thêm dependency, nên
ta gọi hàm thật qua Node thay vì viết lại logic bằng Python (viết lại thì
test chỉ chứng minh chính nó).
"""

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import textwrap

import pytest

ROOT = pathlib.Path(__file__).parent.parent
APP_JS = ROOT / "assets" / "app.js"
DASHBOARD = ROOT / "data" / "dashboard.json"

NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node không có trên PATH")


def run_node(body):
    """Chạy một đoạn JS có sẵn biến `app` (module app.js) và in JSON ra stdout."""
    script = textwrap.dedent(f"""
        const app = require({json.dumps(str(APP_JS))});
        const DASHBOARD = require({json.dumps(str(DASHBOARD))});
        {body}
    """)
    with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf8",
                                     delete=False) as fh:
        fh.write(script)
        path = fh.name
    try:
        result = subprocess.run([NODE, path], capture_output=True, text=True,
                                encoding="utf8", timeout=60)
        if result.returncode != 0:
            raise AssertionError(f"node lỗi:\n{result.stderr}")
        return json.loads(result.stdout)
    finally:
        os.unlink(path)


def test_pct_change_returns_null_when_previous_is_zero():
    """Chia cho 0 phải ra null, không phải Infinity."""
    out = run_node("console.log(JSON.stringify(app.pctChange(5, 0)));")

    assert out is None


def test_pct_change_returns_null_when_either_side_is_missing():
    out = run_node("""
        console.log(JSON.stringify([
          app.pctChange(null, 10),
          app.pctChange(10, null),
          app.pctChange(null, null),
        ]));
    """)

    assert out == [None, None, None]


def test_pct_change_computes_a_normal_increase():
    out = run_node("console.log(JSON.stringify(app.pctChange(110, 100)));")

    assert out == pytest.approx(0.10)


def test_change_at_with_lag_twelve_is_null_for_the_first_twelve_months():
    """%YoY cần 12 tháng trước đó — 12 tháng đầu phải là null, không phải 0."""
    out = run_node("""
        const series = Array.from({length: 14}, (_, i) => 100 + i);
        console.log(JSON.stringify(
          series.map((_, i) => app.changeAt(series, i, 12))));
    """)

    assert out[:12] == [None] * 12
    assert out[12] == pytest.approx(12 / 100)
    assert out[13] == pytest.approx(12 / 101)


def test_change_at_with_lag_one_is_null_for_the_first_month():
    out = run_node("""
        console.log(JSON.stringify(app.changeAt([100, 150], 0, 1)));
    """)

    assert out is None


def test_spread_series_is_zero_against_itself():
    """Chênh lệch của một chuỗi với chính nó phải bằng 0 ở mọi tháng."""
    out = run_node("""
        const p = DASHBOARD.groups.find(g => g.key === "pangasius");
        console.log(JSON.stringify(app.spreadSeries(p.asp, p.asp)));
    """)

    assert out == [0] * len(out)
    assert len(out) == 42


def test_spread_series_is_null_where_either_side_is_null():
    out = run_node("""
        console.log(JSON.stringify(
          app.spreadSeries([5, null, 7, 8], [2, 3, null, 8])));
    """)

    assert out == [3, None, None, 0]


def test_spread_series_matches_real_data_for_cod_in_the_latest_month():
    """Cod đắt hơn cá tra — dấu dương theo đúng quy ước của spec."""
    out = run_node("""
        const cod = DASHBOARD.groups.find(g => g.key === "cod");
        const pan = DASHBOARD.groups.find(g => g.key === "pangasius");
        const i = DASHBOARD.months.length - 1;
        const s = app.spreadSeries(cod.asp, pan.asp);
        console.log(JSON.stringify(
          {spread: s[i], cod: cod.asp[i], pan: pan.asp[i]}));
    """)

    assert out["spread"] == pytest.approx(out["cod"] - out["pan"])
    assert out["spread"] > 0


def test_master_summary_has_one_row_per_group_in_order():
    out = run_node("console.log(JSON.stringify(app.masterSummaryRows(DASHBOARD)));")

    assert [r["key"] for r in out] == [g["key"] for g in
                                       json.loads(DASHBOARD.read_text(encoding="utf8"))["groups"]]
    assert len(out) == 6


def test_master_summary_pangasius_spread_is_zero():
    out = run_node("console.log(JSON.stringify(app.masterSummaryRows(DASHBOARD)));")

    row = next(r for r in out if r["key"] == "pangasius")
    assert row["spread"] == 0


def test_master_summary_reports_latest_month_volume():
    out = run_node("""
        const rows = app.masterSummaryRows(DASHBOARD);
        const i = DASHBOARD.months.length - 1;
        console.log(JSON.stringify(rows.map(r => ({
          key: r.key,
          fromRow: r.volume,
          fromData: DASHBOARD.groups.find(g => g.key === r.key).volume[i],
        }))));
    """)

    for entry in out:
        assert entry["fromRow"] == entry["fromData"], entry["key"]


def test_assign_group_colors_is_stable_and_distinct():
    """Mỗi nhóm một màu cố định, và cùng một map dùng cho cả hai chart."""
    out = run_node("""
        const keys = DASHBOARD.groups.map(g => g.key);
        const a = app.assignGroupColors(keys);
        const b = app.assignGroupColors(keys);
        console.log(JSON.stringify({a, b, values: Object.values(a)}));
    """)

    assert out["a"] == out["b"]
    assert len(set(out["values"])) == len(out["values"])
    assert len(out["values"]) == 6
