# Master Tab & Per-Chart CSV Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm tab "Tổng hợp" so sánh ASP của cả 6 nhóm cá và chênh lệch giá của từng loài so với cá tra, kèm nút tải CSV trên từng chart.

**Architecture:** Toàn bộ tính toán ở phía trình duyệt từ `data/dashboard.json` đã có sẵn. Không sửa `scripts/`, `products.yml`, hay dữ liệu. Phần tính số tách thành hàm thuần, export qua `module.exports` để test bằng Node — đúng khuôn mẫu `assignCountryColors`/`isDataStale` đang dùng trong repo.

**Tech Stack:** HTML/CSS/JS thuần, Chart.js v4.4.1 đã vendored, pytest + Node harness.

## Global Constraints

- Không sửa `scripts/build.py`, `scripts/fetch.py`, `scripts/noaa.py`, `scripts/console.py`, `products.yml`, hay bất cứ thứ gì trong `data/`. Golden test đối chiếu workbook gốc phải giữ nguyên kết quả.
- Không thêm dependency nào, JS lẫn Python. Không tham chiếu CDN ngoài. Không sửa `assets/portal.css` và `assets/chart.umd.min.js`.
- Mọi chữ hiển thị bằng tiếng Việt.
- Không có dữ liệu thuế: không hiện, không ám chỉ, không để chỗ trống cho `ASP after tariff` hay `% tariff estimated`.
- `asp` có thể là `null`. Không bao giờ hiện `NaN`, `Infinity`, `null`, `undefined` hay `0` thay cho dữ liệu thiếu — luôn là gạch ngang `—` trong bảng, điểm đứt trên chart, ô trống trong CSV.
- Không bao giờ chia cho 0.
- Nhóm mốc so sánh là `pangasius`. Quy ước dấu: `spread = asp[nhóm] − asp[pangasius]`, số dương nghĩa là loài đó đắt hơn cá tra.
- Bảng màu chỉ dùng token đã có: `--data-1` … `--data-9`, `--trend-flat`. Không thêm màu mới.
- Nội dung rộng cuộn trong khung riêng; thân trang không bao giờ cuộn ngang.
- Suite hiện tại là **99 passed, 11 skipped**. Phải giữ xanh.

---

## File Structure

| File | Thay đổi |
|---|---|
| `assets/app.js` | Thêm hàm thuần tính toán, render tab master, tách hàm tải CSV dùng chung. Đây là file chịu phần lớn thay đổi. |
| `index.html` | Gán `id` cho các thẻ card hiện chưa có, thêm 3 card của tab master, thêm nút tải trên từng chart. |
| `assets/dashboard.css` | Style cho dòng nhấn trong bảng master, hàng nút trên đầu card, số âm/dương ở cột chênh lệch. |
| `tests/test_master_tab.py` | File test mới, chạy hàm thật qua Node giống `tests/test_chart_colors.py`. |

---

## Task 1: Hàm thuần tính toán cho tab master

Task này không đụng DOM và không thay đổi giao diện. Nó chỉ tạo ra các hàm mà Task 2 sẽ vẽ.

**Files:**
- Modify: `assets/app.js` (thêm hàm mới, mở rộng `module.exports` ở cuối file)
- Create: `tests/test_master_tab.py`

**Interfaces:**
- Consumes: `data/dashboard.json` với `months` (mảng chuỗi `"YYYY-MM"`), `groups` (mỗi phần tử có `key`, `label`, `volume`, `value`, `asp`, `countries`). Mọi mảng dài bằng `months`.
- Produces (export từ `assets/app.js`):
  - `MASTER_KEY: string` = `"master"`
  - `BASE_GROUP_KEY: string` = `"pangasius"`
  - `GROUP_COLORS: string[]` — mảng token màu theo thứ tự nhóm
  - `assignGroupColors(groupKeys: string[]) -> Record<string, string>`
  - `pctChange(current: number|null, previous: number|null) -> number|null`
  - `changeAt(series: (number|null)[], index: number, lag: number) -> number|null`
  - `spreadSeries(groupAsp: (number|null)[], baseAsp: (number|null)[]) -> (number|null)[]`
  - `masterSummaryRows(data: object) -> Array<{key, label, volume, volumeMom, volumeYoy, asp, aspMom, aspYoy, spread}>`

- [ ] **Step 1: Viết test thất bại**

Tạo `tests/test_master_tab.py`. Nó dựng script Node gọi thẳng hàm export từ `assets/app.js`, giống hệt cách `tests/test_chart_colors.py` đang làm.

```python
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
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_master_tab.py -v`
Expected: FAIL — `node lỗi:` kèm `TypeError: app.pctChange is not a function`.

- [ ] **Step 3: Thêm các hàm thuần vào `assets/app.js`**

Chèn khối sau vào `assets/app.js`, ngay trước hàm `render()`:

```javascript
/* ============================================================
   Tab "Tổng hợp" — phần tính toán thuần, không đụng DOM.
   Tách riêng để test được qua Node (xem tests/test_master_tab.py).
   ============================================================ */

const MASTER_KEY = "master";
const MASTER_LABEL = "Tổng hợp";

// Nhóm mốc của cả tab: mọi chênh lệch đều tính so với cá tra.
const BASE_GROUP_KEY = "pangasius";

// Sáu màu cố định cho sáu nhóm. Dùng CHUNG cho cả chart ASP và chart
// chênh lệch — nếu hai chart tô khác nhau thì người đọc phải học lại bảng
// màu mỗi lần chuyển mắt.
const GROUP_COLORS = ["--data-1", "--data-2", "--data-3",
                      "--data-4", "--data-5", "--data-6"];

function assignGroupColors(groupKeys) {
  const map = {};
  groupKeys.forEach((key, i) => {
    map[key] = GROUP_COLORS[i % GROUP_COLORS.length];
  });
  return map;
}

/** Biến động tương đối. Trả null nếu thiếu số liệu hoặc mẫu số bằng 0. */
function pctChange(current, previous) {
  if (current === null || current === undefined) return null;
  if (previous === null || previous === undefined) return null;
  if (previous === 0) return null;
  return current / previous - 1;
}

/**
 * Biến động của `series[index]` so với `series[index - lag]`.
 * lag = 1 cho MoM, lag = 12 cho YoY. Chưa đủ lịch sử thì trả null,
 * KHÔNG trả 0 — không có dữ liệu khác với không thay đổi.
 */
function changeAt(series, index, lag) {
  const previousIndex = index - lag;
  if (previousIndex < 0) return null;
  return pctChange(series[index], series[previousIndex]);
}

/** asp[nhóm] − asp[cá tra] theo từng tháng. Thiếu một đầu thì null. */
function spreadSeries(groupAsp, baseAsp) {
  return groupAsp.map((value, i) => {
    const base = baseAsp[i];
    if (value === null || value === undefined) return null;
    if (base === null || base === undefined) return null;
    return value - base;
  });
}

/** Sáu dòng của bảng tóm tắt, theo đúng thứ tự nhóm trong dashboard.json. */
function masterSummaryRows(data) {
  const last = data.months.length - 1;
  const base = data.groups.find((g) => g.key === BASE_GROUP_KEY);
  const baseAsp = base ? base.asp[last] : null;

  return data.groups.map((group) => {
    const asp = group.asp[last];
    const spread = (asp === null || asp === undefined ||
                    baseAsp === null || baseAsp === undefined)
      ? null
      : asp - baseAsp;
    return {
      key: group.key,
      label: group.label,
      volume: group.volume[last],
      volumeMom: changeAt(group.volume, last, 1),
      volumeYoy: changeAt(group.volume, last, 12),
      asp: asp,
      aspMom: changeAt(group.asp, last, 1),
      aspYoy: changeAt(group.asp, last, 12),
      spread: spread,
    };
  });
}
```

- [ ] **Step 4: Mở rộng `module.exports`**

Ở cuối `assets/app.js`, thêm các tên mới vào object đang export. Giữ nguyên những tên đã có:

```javascript
if (typeof module !== "undefined" && module.exports) {
  module.exports = { assignCountryColors, shouldHideShareChart, renderShareChart,
                     state, COUNTRY_COLORS, TOTAL_COLOR, OTHER_COLOR,
                     isDataStale, findOtherOutlier,
                     MASTER_KEY, MASTER_LABEL, BASE_GROUP_KEY, GROUP_COLORS,
                     assignGroupColors, pctChange, changeAt, spreadSeries,
                     masterSummaryRows };
}
```

Lưu ý: danh sách tên đang export ở file thật có thể khác đôi chút so với đoạn trên. Đọc dòng `module.exports` hiện tại, **giữ nguyên mọi tên đang có**, chỉ bổ sung các tên mới.

- [ ] **Step 5: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_master_tab.py -v`
Expected: PASS, 12 passed.

- [ ] **Step 6: Chạy toàn bộ suite**

Run: `python -m pytest -q`
Expected: `111 passed, 11 skipped` (99 cũ + 12 mới).

- [ ] **Step 7: Commit**

```bash
git add assets/app.js tests/test_master_tab.py
git commit -m "feat: pure calculations for the master comparison tab"
```

---

## Task 2: Hiển thị tab Tổng hợp

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/dashboard.css`
- Modify: `tests/test_master_tab.py`

**Interfaces:**
- Consumes từ Task 1: `MASTER_KEY`, `MASTER_LABEL`, `BASE_GROUP_KEY`, `assignGroupColors`, `spreadSeries`, `masterSummaryRows`.
- Produces:
  - `isMasterActive() -> boolean`
  - `formatPct(value: number|null) -> string` — `"—"` khi null, ngược lại `"+6,8%"` / `"-1,1%"`
  - `formatSpread(value: number|null) -> string` — `"—"` khi null, ngược lại `"+11,07"` / `"-0,56"`
  - `renderMaster() -> void`
  - `masterChartData(data) -> {labels, aspDatasets, spreadDatasets}` — hàm thuần dựng dữ liệu cho hai chart

- [ ] **Step 1: Gán id cho các card hiện có và thêm card của tab master vào `index.html`**

Ba `<section class="card">` hiện chưa có `id`, nên không ẩn/hiện được. Gán id cho chúng, rồi thêm ba card mới của tab master. Thay toàn bộ khối `<main>` bằng:

```html
<main>
  <section class="kpi-row" id="kpi-row"></section>

  <section class="card" id="master-summary-card">
    <h2>So sánh các nhóm — kỳ gần nhất</h2>
    <div class="table-wrap"><table id="master-table"></table></div>
    <p class="master-hint">Cột cuối là chênh lệch giá so với cá tra: số dương nghĩa là loài đó đang đắt hơn cá tra.</p>
  </section>

  <section class="card" id="master-asp-card">
    <h2>Giá bình quân theo nhóm (ASP, USD/kg)</h2>
    <div class="chart-wrap"><canvas id="chart-master-asp"></canvas></div>
  </section>

  <section class="card" id="master-spread-card">
    <h2>Chênh lệch giá so với cá tra (USD/kg)</h2>
    <div class="chart-wrap"><canvas id="chart-master-spread"></canvas></div>
  </section>

  <section class="card" id="volume-card">
    <h2>Sản lượng theo tháng</h2>
    <div class="chart-wrap"><canvas id="chart-volume"></canvas></div>
  </section>

  <section class="card" id="asp-card">
    <h2>Giá bình quân (ASP, USD/kg)</h2>
    <div class="chart-wrap"><canvas id="chart-asp"></canvas></div>
  </section>

  <section class="card" id="share-card">
    <h2>Thị phần theo nước (sản lượng)</h2>
    <div class="chart-wrap"><canvas id="chart-share"></canvas></div>
  </section>

  <section class="card" id="detail-card">
    <div class="card-head">
      <h2>Số liệu chi tiết</h2>
      <button type="button" id="export-csv" class="btn">Tải CSV</button>
    </div>
    <div class="table-wrap"><table id="data-table"></table></div>
  </section>
</main>
```

Đừng đổi `<header>`, `<nav>`, `<footer>` hay các thẻ `<script>`.

- [ ] **Step 2: Viết test thất bại cho phần tính dữ liệu chart và định dạng**

Thêm vào cuối `tests/test_master_tab.py`:

```python
def test_format_pct_shows_a_dash_for_null():
    out = run_node("console.log(JSON.stringify(app.formatPct(null)));")

    assert out == "—"


def test_format_pct_signs_both_directions():
    out = run_node("""
        console.log(JSON.stringify([app.formatPct(0.068), app.formatPct(-0.011)]));
    """)

    assert out[0].startswith("+")
    assert out[1].startswith("-")
    assert "%" in out[0]


def test_format_spread_shows_a_dash_for_null():
    out = run_node("console.log(JSON.stringify(app.formatSpread(null)));")

    assert out == "—"


def test_master_chart_data_has_one_asp_dataset_per_group():
    out = run_node("""
        const d = app.masterChartData(DASHBOARD);
        console.log(JSON.stringify({
          labels: d.labels.length,
          asp: d.aspDatasets.map(x => x.label),
          spread: d.spreadDatasets.map(x => x.label),
        }));
    """)

    assert out["labels"] == 42
    assert len(out["asp"]) == 6
    # 5 loài còn lại + đường mốc 0 mang nhãn cá tra.
    assert len(out["spread"]) == 6


def test_master_chart_data_uses_the_same_colour_for_a_group_in_both_charts():
    """Nếu hai chart tô khác màu, người đọc phải học lại bảng màu."""
    out = run_node("""
        const d = app.masterChartData(DASHBOARD);
        const byLabel = {};
        d.aspDatasets.forEach(x => { byLabel[x.label] = x.borderColor; });
        console.log(JSON.stringify(d.spreadDatasets.map(x => ({
          label: x.label, asp: byLabel[x.label], spread: x.borderColor,
        }))));
    """)

    assert out
    for entry in out:
        assert entry["asp"] == entry["spread"], entry["label"]


def test_master_chart_data_keeps_nulls_so_gaps_stay_gaps():
    """Tháng thiếu ASP phải là null trong dataset, không được thành 0."""
    out = run_node("""
        const d = app.masterChartData(DASHBOARD);
        const flat = d.aspDatasets.concat(d.spreadDatasets)
          .flatMap(x => x.data);
        console.log(JSON.stringify({
          hasNaN: flat.some(v => typeof v === "number" && Number.isNaN(v)),
          hasUndefined: flat.some(v => v === undefined),
        }));
    """)

    assert out["hasNaN"] is False
    assert out["hasUndefined"] is False
```

- [ ] **Step 3: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_master_tab.py -v -k "format or chart_data"`
Expected: FAIL — `TypeError: app.formatPct is not a function`.

- [ ] **Step 4: Thêm phần hiển thị master vào `assets/app.js`**

Chèn sau khối hàm thuần của Task 1, vẫn trước `render()`:

```javascript
/** Định dạng biến động tương đối: "—" khi thiếu, ngược lại có dấu và %. */
function formatPct(value) {
  if (value === null || value === undefined) return "—";
  const pct = value * 100;
  const sign = pct >= 0 ? "+" : "";
  return sign + new Intl.NumberFormat("vi-VN", {
    minimumFractionDigits: 1, maximumFractionDigits: 1 }).format(pct) + "%";
}

/** Định dạng chênh lệch USD/kg, luôn kèm dấu để đọc nhanh chiều lệch. */
function formatSpread(value) {
  if (value === null || value === undefined) return "—";
  const sign = value >= 0 ? "+" : "";
  return sign + new Intl.NumberFormat("vi-VN", {
    minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

function isMasterActive() {
  return state.activeKey === MASTER_KEY;
}

/** Dựng dữ liệu cho hai chart của tab master. Hàm thuần, không đụng DOM. */
function masterChartData(data) {
  const colors = assignGroupColors(data.groups.map((g) => g.key));
  const base = data.groups.find((g) => g.key === BASE_GROUP_KEY);

  const aspDatasets = data.groups.map((group) => ({
    label: group.label,
    data: group.asp,
    borderColor: colors[group.key],
    backgroundColor: colors[group.key],
    borderWidth: group.key === BASE_GROUP_KEY ? 3 : 1.6,
    pointRadius: 0,
    tension: 0.25,
    spanGaps: false,
  }));

  // Đường mốc 0 mang nhãn của chính cá tra, để legend giải thích được
  // đường ngang đó là gì thay vì bắt người đọc tự suy ra.
  const spreadDatasets = base
    ? [{
        label: base.label,
        data: base.asp.map((v) => (v === null || v === undefined ? null : 0)),
        borderColor: colors[base.key],
        backgroundColor: colors[base.key],
        borderWidth: 3,
        pointRadius: 0,
        tension: 0,
        spanGaps: false,
      }].concat(
        data.groups
          .filter((group) => group.key !== BASE_GROUP_KEY)
          .map((group) => ({
            label: group.label,
            data: spreadSeries(group.asp, base.asp),
            borderColor: colors[group.key],
            backgroundColor: colors[group.key],
            borderWidth: 1.6,
            pointRadius: 0,
            tension: 0.25,
            spanGaps: false,
          })))
    : [];

  return { labels: data.months, aspDatasets, spreadDatasets };
}

function renderMasterTable() {
  const rows = masterSummaryRows(state.data);
  const header = ["Nhóm", "Sản lượng (kg)", "SL %MoM", "SL %YoY",
                  "ASP (USD/kg)", "ASP %MoM", "ASP %YoY",
                  "Chênh lệch vs cá tra"];

  const body = rows.map((row) => {
    const cells = [
      row.label,
      formatInt(row.volume),
      formatPct(row.volumeMom),
      formatPct(row.volumeYoy),
      formatUsdPerKg(row.asp),
      formatPct(row.aspMom),
      formatPct(row.aspYoy),
      formatSpread(row.spread),
    ];
    const cls = row.key === BASE_GROUP_KEY ? ' class="row-base"' : "";
    return `<tr${cls}>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`;
  }).join("");

  document.getElementById("master-table").innerHTML =
    `<thead><tr>${header.map((h) => `<th>${h}</th>`).join("")}</tr></thead>` +
    `<tbody>${body}</tbody>`;
}

function renderMasterCharts() {
  const data = masterChartData(state.data);

  drawChart("chart-master-asp", {
    type: "line",
    data: { labels: data.labels, datasets: data.aspDatasets },
    options: baseOptions("USD/kg"),
  });

  const spreadOptions = baseOptions("USD/kg");
  // Đường 0 là mốc cá tra — vẽ đậm hơn lưới thường để mắt bắt được ngay.
  spreadOptions.scales.y.grid = {
    color: (ctx) => (ctx.tick.value === 0
      ? cssVar("--border-strong") : cssVar("--border-hairline")),
  };
  drawChart("chart-master-spread", {
    type: "line",
    data: { labels: data.labels, datasets: data.spreadDatasets },
    options: spreadOptions,
  });
}

function renderMaster() {
  renderMasterTable();
  renderMasterCharts();
}
```

- [ ] **Step 5: Cho tab master vào thanh tab và điều phối ẩn/hiện**

Sửa `renderTabs()` để chèn tab master lên đầu. Thay toàn bộ hàm bằng:

```javascript
function renderTabs() {
  const nav = document.getElementById("group-tabs");
  nav.innerHTML = "";

  const entries = [{ key: MASTER_KEY, label: MASTER_LABEL }].concat(
    state.data.groups.map((g) => ({ key: g.key, label: g.label })));

  entries.forEach((entry) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = entry.label;
    button.setAttribute("aria-pressed", String(entry.key === state.activeKey));
    button.addEventListener("click", () => {
      state.activeKey = entry.key;
      render();
    });
    nav.appendChild(button);
  });
}
```

Thay `render()` bằng bản điều phối hai chế độ. Điểm quan trọng: **huỷ chart của chế độ đang ẩn**, nếu không sẽ còn instance Chart.js sống bám vào canvas ẩn — đúng lỗi đã từng xảy ra ở repo này với `chart-share`:

```javascript
const MASTER_CARDS = ["master-summary-card", "master-asp-card",
                      "master-spread-card"];
const GROUP_CARDS = ["kpi-row", "volume-card", "asp-card", "share-card",
                     "detail-card"];
const MASTER_CANVASES = ["chart-master-asp", "chart-master-spread"];
const GROUP_CANVASES = ["chart-volume", "chart-asp", "chart-share"];

function setHidden(ids, hidden) {
  ids.forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.hidden = hidden;
  });
}

/** Huỷ chart và xoá khỏi state, để không còn instance bám canvas đang ẩn. */
function destroyCharts(canvasIds) {
  canvasIds.forEach((id) => {
    if (state.charts[id]) {
      state.charts[id].destroy();
      delete state.charts[id];
    }
  });
}

function render() {
  renderTabs();

  if (isMasterActive()) {
    setHidden(GROUP_CARDS, true);
    setHidden(MASTER_CARDS, false);
    destroyCharts(GROUP_CANVASES);
    renderMaster();
    return;
  }

  setHidden(MASTER_CARDS, true);
  setHidden(GROUP_CARDS, false);
  destroyCharts(MASTER_CANVASES);
  renderKpis();
  renderVolumeChart();
  renderAspChart();
  renderShareChart();
  renderTable();
}
```

Lưu ý: đọc `render()` bản thật trước khi thay và **giữ nguyên mọi lời gọi đang có**, chỉ bọc chúng vào đúng nhánh. Băng cảnh báo dữ liệu cũ (`renderStalenessBanner`) đang được gọi ở `init()` chứ không ở `render()` — đừng chuyển nó vào đây, nếu không nó sẽ dựng lại mỗi lần chuyển tab. `renderOtherNote()` thuộc nhánh nhóm, không thuộc nhánh master; `renderShareChart()` đang tự gọi nó thì cứ để nguyên.

- [ ] **Step 6: Đặt master làm tab mặc định**

Trong `init()`, dòng đang gán tab đầu tiên hiện là `state.activeKey = state.data.groups[0].key;`. Đổi thành:

```javascript
  state.activeKey = MASTER_KEY;
```

- [ ] **Step 7: Bổ sung export**

Thêm `formatPct`, `formatSpread`, `isMasterActive`, `masterChartData`, `renderMaster` vào `module.exports`, giữ nguyên các tên đã có.

- [ ] **Step 8: Thêm style vào `assets/dashboard.css`**

```css
/* Dòng cá tra trong bảng master là mốc so sánh của cả tab — tô nhẹ để mắt
   luôn quay về được, không tô đậm quá kẻo lấn át các dòng còn lại. */
#master-table tr.row-base td {
  background: var(--accent-soft);
  font-weight: 600;
}

.master-hint {
  margin: 10px 0 0;
  color: var(--text-tertiary);
  font-size: var(--text-body-sm);
}

/* hidden mặc định bị display:table/flex của các quy tắc khác đè mất. */
[hidden] { display: none !important; }
```

- [ ] **Step 9: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_master_tab.py -v`
Expected: PASS, 18 passed.

- [ ] **Step 10: Kiểm tra trên trình duyệt**

Run: `python -m http.server 8021 --directory .`

Mở `http://localhost:8021/` và xác nhận từng điểm:
- Thanh tab có 7 mục, **Tổng hợp** đứng đầu và đang được chọn khi vừa mở trang.
- Bảng master có 6 dòng, dòng Pangasius được tô nhấn. Cột chênh lệch: cá tra là `+0,00`, cod và salmon là số dương lớn.
- Chart ASP có 6 đường, đường cá tra dày hơn.
- Chart chênh lệch có 6 mục trong legend: 5 loài, cộng đường mốc 0 nằm ngang mang nhãn Pangasius, vẽ dày và đúng màu của cá tra ở chart trên.
- Không ô nào trong bảng hiện `NaN`, `Infinity`, `null` hay `undefined`.
- Bấm sang **Pangasius**: bảng master và hai chart master biến mất, KPI + 3 chart nhóm + bảng chi tiết hiện ra.
- Bấm ngược lại **Tổng hợp**: các khối của tab nhóm biến mất hết, không sót cái nào.
- Bấm sang **Salmon Atlantic** rồi quay lại **Tổng hợp** rồi sang **Cod NSPF**: mọi chart vẫn vẽ đúng, console không có lỗi.
- Console không có lỗi ở bất kỳ bước nào.

- [ ] **Step 11: Commit**

```bash
git add index.html assets/app.js assets/dashboard.css tests/test_master_tab.py
git commit -m "feat: master comparison tab with ASP and spread-vs-pangasius charts"
```

---

## Task 3: Nút tải CSV trên từng chart

**Files:**
- Modify: `index.html`
- Modify: `assets/app.js`
- Modify: `assets/dashboard.css`
- Modify: `tests/test_master_tab.py`

**Interfaces:**
- Consumes từ Task 2: `masterChartData`, `isMasterActive`, `MASTER_KEY`, `BASE_GROUP_KEY`.
- Produces:
  - `toCsv(rows: Array<Array<any>>) -> string` — chuỗi CSV, ô `null`/`undefined` thành rỗng
  - `chartCsvRows(chartId: string, data: object, groupKey: string) -> Array<Array<any>>`
  - `downloadCsv(filename: string, rows: Array<Array<any>>) -> void`

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `tests/test_master_tab.py`:

```python
def test_to_csv_quotes_every_cell_and_doubles_inner_quotes():
    out = run_node("""
        console.log(JSON.stringify(
          app.toCsv([["a", 'có "nháy"'], ["b,c", 1]])));
    """)

    assert out == '"a","có ""nháy"""\n"b,c","1"'


def test_to_csv_writes_an_empty_cell_for_null():
    """null phải thành ô trống, không phải chữ null."""
    out = run_node("console.log(JSON.stringify(app.toCsv([[null, undefined, 0]])));")

    assert out == '"","","0"'


def test_chart_csv_rows_for_master_spread_has_a_row_per_line_plus_header():
    out = run_node("""
        const rows = app.chartCsvRows("chart-master-spread", DASHBOARD, "master");
        console.log(JSON.stringify({
          rows: rows.length,
          cols: rows[0].length,
          first: rows[0][0],
          labels: rows.slice(1).map(r => r[0]),
        }));
    """)

    # 1 dòng tiêu đề + 6 nhóm; dòng cá tra toàn 0 và chính là mốc,
    # giữ lại trong file để người nhận thấy rõ quy ước so sánh.
    assert out["rows"] == 7
    # 1 cột nhãn + 42 tháng
    assert out["cols"] == 43
    assert out["first"] == "Nhóm"
    assert "Pangasius (cá tra)" in out["labels"]


def test_chart_csv_rows_for_master_asp_covers_all_six_groups():
    out = run_node("""
        const rows = app.chartCsvRows("chart-master-asp", DASHBOARD, "master");
        console.log(JSON.stringify({rows: rows.length, cols: rows[0].length}));
    """)

    assert out["rows"] == 7
    assert out["cols"] == 43


def test_chart_csv_rows_for_group_volume_matches_the_plotted_series():
    out = run_node("""
        const rows = app.chartCsvRows("chart-volume", DASHBOARD, "pangasius");
        const g = DASHBOARD.groups.find(x => x.key === "pangasius");
        console.log(JSON.stringify({
          rows: rows.length, cols: rows[0].length,
          same: JSON.stringify(rows[1].slice(1)) === JSON.stringify(g.volume),
        }));
    """)

    assert out["rows"] == 2
    assert out["cols"] == 43
    assert out["same"] is True


def test_chart_csv_rows_for_group_share_has_a_row_per_country():
    out = run_node("""
        const rows = app.chartCsvRows("chart-share", DASHBOARD, "cod");
        const g = DASHBOARD.groups.find(x => x.key === "cod");
        console.log(JSON.stringify({rows: rows.length, countries: g.countries.length}));
    """)

    # cod có 8 nước + Other = 9, cộng dòng tiêu đề
    assert out["rows"] == out["countries"] + 1


def test_chart_csv_rows_keeps_nulls_so_the_export_leaves_blanks():
    out = run_node("""
        const rows = app.chartCsvRows("chart-master-spread", DASHBOARD, "master");
        const csv = app.toCsv(rows);
        console.log(JSON.stringify({
          hasNullWord: csv.includes('"null"'),
          hasNaN: csv.includes("NaN"),
        }));
    """)

    assert out["hasNullWord"] is False
    assert out["hasNaN"] is False
```

- [ ] **Step 2: Chạy test, xác nhận fail**

Run: `python -m pytest tests/test_master_tab.py -v -k "csv"`
Expected: FAIL — `TypeError: app.toCsv is not a function`.

- [ ] **Step 3: Thêm hàm xuất CSV dùng chung vào `assets/app.js`**

Chèn ngay trước hàm `exportCsv()` hiện có:

```javascript
/* ============================================================
   Xuất CSV dùng chung cho mọi chart và cho bảng chi tiết.
   ============================================================ */

/** Mọi ô bọc ngoặc kép, ngoặc kép bên trong nhân đôi, null thành ô trống. */
function toCsv(rows) {
  return rows.map((row) => row.map((cell) => {
    const value = (cell === null || cell === undefined) ? "" : String(cell);
    return `"${value.replace(/"/g, '""')}"`;
  }).join(",")).join("\n");
}

/** Tải một mảng dòng xuống dưới dạng CSV. BOM để Excel không lỗi font. */
function downloadCsv(filename, rows) {
  const blob = new Blob(["\uFEFF" + toCsv(rows)],
                        { type: "text/csv;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

/**
 * Dựng đúng dữ liệu đang vẽ trên một chart thành các dòng CSV.
 * Hàm thuần: nhận dữ liệu và khoá nhóm, không đọc state, để test được.
 * Số xuất ở dạng thô — không định dạng theo locale, để dán vào model được.
 */
function chartCsvRows(chartId, data, groupKey) {
  const header = (first) => [first].concat(data.months);

  if (chartId === "chart-master-asp") {
    const rows = [header("Nhóm")];
    data.groups.forEach((g) => rows.push([g.label].concat(g.asp)));
    return rows;
  }

  if (chartId === "chart-master-spread") {
    const base = data.groups.find((g) => g.key === BASE_GROUP_KEY);
    const rows = [header("Nhóm")];
    if (!base) return rows;
    data.groups.forEach((g) => rows.push(
      [g.label].concat(spreadSeries(g.asp, base.asp))));
    return rows;
  }

  const group = data.groups.find((g) => g.key === groupKey);
  if (!group) return [header("Chỉ tiêu")];

  if (chartId === "chart-volume") {
    return [header("Chỉ tiêu"), ["Sản lượng (kg)"].concat(group.volume)];
  }

  if (chartId === "chart-asp") {
    const rows = [header("Chỉ tiêu"), ["Toàn nhóm"].concat(group.asp)];
    group.countries.forEach((c) => {
      if (c.name !== OTHER_LABEL) rows.push([c.name].concat(c.asp));
    });
    return rows;
  }

  if (chartId === "chart-share") {
    const rows = [header("Nước")];
    group.countries.forEach((c) => rows.push([c.name].concat(c.volume)));
    return rows;
  }

  return [header("Chỉ tiêu")];
}

const CHART_FILE_SLUG = {
  "chart-master-asp": "asp",
  "chart-master-spread": "chenh-lech",
  "chart-volume": "san-luong",
  "chart-asp": "asp",
  "chart-share": "thi-phan",
};

function exportChartCsv(chartId) {
  const groupKey = isMasterActive() ? MASTER_KEY : state.activeKey;
  const prefix = isMasterActive() ? "tong-hop" : groupKey;
  const rows = chartCsvRows(chartId, state.data, groupKey);
  downloadCsv(`nhap-khau-my-${prefix}-${CHART_FILE_SLUG[chartId]}.csv`, rows);
}
```

- [ ] **Step 4: Cho `exportCsv()` dùng lại hàm chung**

Hàm `exportCsv()` hiện tự dựng chuỗi CSV và tự tạo link tải — trùng lặp với `toCsv`/`downloadCsv` vừa viết. Rút gọn nó lại, giữ nguyên nội dung xuất ra:

```javascript
function exportCsv() {
  const group = activeGroup();
  const rows = [["Chỉ tiêu"].concat(state.data.months)];
  rows.push(["Sản lượng (kg)"].concat(group.volume));
  rows.push(["Giá trị (USD)"].concat(group.value));
  rows.push(["ASP (USD/kg)"].concat(group.asp));
  group.countries.forEach((country) => {
    rows.push([`${country.name} — sản lượng (kg)`].concat(country.volume));
    rows.push([`${country.name} — giá trị (USD)`].concat(country.value));
  });
  downloadCsv(`nhap-khau-my-${group.key}.csv`, rows);
}
```

- [ ] **Step 5: Thêm nút tải vào tiêu đề từng chart trong `index.html`**

Đổi phần `<h2>` của năm card chart thành khối `card-head` có nút, giống card "Số liệu chi tiết" đang có. Ví dụ với card sản lượng:

```html
  <section class="card" id="volume-card">
    <div class="card-head">
      <h2>Sản lượng theo tháng</h2>
      <button type="button" class="btn btn-chart-csv" data-chart="chart-volume">Tải CSV</button>
    </div>
    <div class="chart-wrap"><canvas id="chart-volume"></canvas></div>
  </section>
```

Làm y hệt cho bốn card còn lại, với `data-chart` lần lượt là `chart-asp`, `chart-share`, `chart-master-asp`, `chart-master-spread`. Không thêm nút cho card bảng tóm tắt master và card "Số liệu chi tiết" — card chi tiết đã có nút riêng rồi.

- [ ] **Step 6: Gắn sự kiện trong `init()`**

Thêm vào `init()`, cạnh dòng gắn sự kiện cho `export-csv` đang có:

```javascript
  document.querySelectorAll(".btn-chart-csv").forEach((button) => {
    button.addEventListener("click",
      () => exportChartCsv(button.dataset.chart));
  });
```

Các nút này nằm sẵn trong HTML tĩnh và không bị `render()` dựng lại, nên gắn một lần trong `init()` là đủ — không bị nhân đôi listener mỗi lần chuyển tab.

- [ ] **Step 7: Bổ sung export**

Thêm `toCsv`, `chartCsvRows`, `downloadCsv`, `exportChartCsv` vào `module.exports`, giữ nguyên các tên đã có.

- [ ] **Step 8: Style nút trên đầu card**

Thêm vào `assets/dashboard.css`:

```css
/* card-head đã có sẵn cho card bảng chi tiết; các card chart giờ dùng chung.
   Khoảng cách dưới bằng đúng margin cũ của h2 để bố cục không xô lệch. */
.card > .card-head { margin-bottom: 14px; }
```

- [ ] **Step 9: Chạy test, xác nhận pass**

Run: `python -m pytest tests/test_master_tab.py -v`
Expected: PASS, 25 passed.

- [ ] **Step 10: Chạy toàn bộ suite**

Run: `python -m pytest -q`
Expected: `124 passed, 11 skipped`.

- [ ] **Step 11: Kiểm tra trên trình duyệt**

Run: `python -m http.server 8021 --directory .`

Xác nhận:
- Mỗi chart có nút "Tải CSV" ở góc phải tiêu đề, năm nút tất cả.
- Ở tab **Tổng hợp**, bấm nút trên chart chênh lệch tải về `nhap-khau-my-tong-hop-chenh-lech.csv`; mở ra thấy 7 dòng, 43 cột, dòng cá tra toàn 0, không có chữ `null`, tiếng Việt không lỗi font.
- Ở tab **Cod NSPF**, bấm nút trên chart thị phần tải về file có 10 dòng (9 nước gồm Other + tiêu đề).
- Nút "Tải CSV" ở bảng "Số liệu chi tiết" vẫn hoạt động như cũ.
- Chuyển tab qua lại vài lần rồi bấm lại các nút — file tải về vẫn đúng tab đang xem, không phải tab trước.
- Console không có lỗi.

Tên file mong đợi: `nhap-khau-my-tong-hop-asp.csv`, `nhap-khau-my-tong-hop-chenh-lech.csv`, `nhap-khau-my-pangasius-san-luong.csv`, `nhap-khau-my-cod-thi-phan.csv`.

- [ ] **Step 12: Commit**

```bash
git add index.html assets/app.js assets/dashboard.css tests/test_master_tab.py
git commit -m "feat: per-chart CSV download buttons"
```

---

## Ngoài phạm vi

Đã thống nhất trong spec, không làm ở kế hoạch này:

- Thị phần Việt Nam theo từng nhóm (cần sửa `build.py` vì Haddock và Salmon không tách Việt Nam).
- Chart sản lượng 6 nhóm chồng nhau.
- Xuất `.xlsx` thật nhiều sheet.
- Mọi thay đổi ở `scripts/`, `products.yml`, hay `data/`.
