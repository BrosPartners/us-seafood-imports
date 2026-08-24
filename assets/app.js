/* Dashboard nhập khẩu thủy sản vào Mỹ.
   Đọc data/dashboard.json (tĩnh), vẽ 3 biểu đồ và 1 bảng.
   Không gọi API lúc chạy — mọi số đã tính sẵn lúc build. */

// Màu cho các quốc gia được đặt tên (không gồm "Other"). 8 màu đủ cho nhóm
// nhiều quốc gia nhất hiện có (Cod, Pollock: 8 quốc gia đặt tên + "Other").
const COUNTRY_COLORS = ["--data-1", "--data-2", "--data-3", "--data-4",
                        "--data-5", "--data-6", "--data-7", "--data-8"];
// Đường tổng ("Toàn nhóm") trong biểu đồ ASP dùng màu riêng, tách khỏi
// palette quốc gia để không bao giờ trùng màu với quốc gia nào.
const TOTAL_COLOR = "--data-9";
// "Other" nghĩa là "phần còn lại" — luôn hiển thị bằng màu xám trung tính,
// không bao giờ chiếm một slot màu của palette quốc gia.
const OTHER_COLOR = "--trend-flat";

const state = { data: null, activeKey: null, charts: {} };

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Gán màu cho danh sách quốc gia theo tên (đầu vào là mảng tên, đúng thứ
 * tự xuất hiện trong group.countries). Hàm thuần: không đọc DOM, không có
 * side effect ngoài console.warn khi palette không đủ.
 *
 * - "Other" luôn nhận OTHER_COLOR và không tiêu tốn slot palette.
 * - Các quốc gia khác được gán tuần tự từ COUNTRY_COLORS theo thứ tự xuất
 *   hiện (không tính "Other").
 * - Nếu số quốc gia đặt tên vượt quá số màu trong palette, việc lặp màu là
 *   có thật (không phải bug ẩn) — hàm cảnh báo ra console để việc này lộ ra
 *   khi phát triển, nhưng vẫn trả về một màu hợp lệ để trang không vỡ.
 *
 * Trả về mảng cùng độ dài với countryNames, mỗi phần tử là tên biến CSS.
 */
function assignCountryColors(countryNames) {
  let namedIndex = 0;
  return countryNames.map((name) => {
    if (name === "Other") return OTHER_COLOR;
    if (namedIndex >= COUNTRY_COLORS.length) {
      console.warn(
        `assignCountryColors: ${countryNames.length} quốc gia đặt tên vượt ` +
        `quá ${COUNTRY_COLORS.length} màu trong palette — màu sẽ bị lặp lại.`
      );
    }
    const color = COUNTRY_COLORS[namedIndex % COUNTRY_COLORS.length];
    namedIndex += 1;
    return color;
  });
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
    borderColor: cssVar(TOTAL_COLOR),
    backgroundColor: cssVar(TOTAL_COLOR),
    borderWidth: 2.5,
    pointRadius: 0,
    tension: 0.25,
  }];
  const colors = assignCountryColors(group.countries.map((c) => c.name));
  group.countries.forEach((country, i) => {
    if (country.name === "Other") return;
    datasets.push({
      label: country.name,
      data: country.asp,
      borderColor: cssVar(colors[i]),
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

/**
 * Quyết định thuần cho vòng đời chart-share: nhóm không có quốc gia nào thì
 * phải destroy chart cũ (nếu có) và xoá khỏi state.charts, không được để
 * lại instance cũ gắn với canvas đã ẩn.
 */
function shouldHideShareChart(group) {
  return !group.countries.length;
}

function renderShareChart() {
  const group = activeGroup();
  const card = document.getElementById("share-card");
  if (shouldHideShareChart(group)) {
    card.hidden = true;
    if (state.charts["chart-share"]) {
      state.charts["chart-share"].destroy();
      delete state.charts["chart-share"];
    }
    return;
  }
  card.hidden = false;

  const options = baseOptions("kg");
  options.scales.y.stacked = true;
  options.scales.x.stacked = true;

  const colors = assignCountryColors(group.countries.map((c) => c.name));
  drawChart("chart-share", {
    type: "bar",
    data: {
      labels: state.data.months,
      datasets: group.countries.map((country, i) => ({
        label: country.name,
        data: country.volume,
        backgroundColor: cssVar(colors[i]),
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

  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
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

if (typeof window !== "undefined") {
  init();
}

// Xuất các hàm thuần để test từ Node (xem tests/test_chart_colors.py), không
// ảnh hưởng khi chạy trong trình duyệt (không có `module` trong global đó).
if (typeof module !== "undefined" && module.exports) {
  module.exports = { assignCountryColors, shouldHideShareChart, renderShareChart,
                      state, COUNTRY_COLORS, TOTAL_COLOR, OTHER_COLOR };
}
