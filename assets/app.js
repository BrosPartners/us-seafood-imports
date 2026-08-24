/* Dashboard nhập khẩu thủy sản vào Mỹ.
   Đọc data/dashboard.json (tĩnh), vẽ 3 biểu đồ và 1 bảng.
   Không gọi API lúc chạy — mọi số đã tính sẵn lúc build. */

const SERIES_COLORS = ["--data-1", "--data-2", "--data-3", "--data-4",
                       "--data-5", "--data-6", "--data-7"];

const state = { data: null, activeKey: null, charts: {} };

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
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
    borderColor: cssVar("--data-1"),
    backgroundColor: cssVar("--data-1"),
    borderWidth: 2.5,
    pointRadius: 0,
    tension: 0.25,
  }];
  group.countries.forEach((country, i) => {
    if (country.name === "Other") return;
    datasets.push({
      label: country.name,
      data: country.asp,
      borderColor: cssVar(SERIES_COLORS[(i + 1) % SERIES_COLORS.length]),
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

function renderShareChart() {
  const group = activeGroup();
  const card = document.getElementById("share-card");
  if (!group.countries.length) {
    card.hidden = true;
    return;
  }
  card.hidden = false;

  const options = baseOptions("kg");
  options.scales.y.stacked = true;
  options.scales.x.stacked = true;

  drawChart("chart-share", {
    type: "bar",
    data: {
      labels: state.data.months,
      datasets: group.countries.map((country, i) => ({
        label: country.name,
        data: country.volume,
        backgroundColor: cssVar(SERIES_COLORS[i % SERIES_COLORS.length]),
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

init();
