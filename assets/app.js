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

function formatInt(value) {
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
    ["Sản lượng (kg)", formatInt(volume)],
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

const OTHER_LABEL = "Other";

/**
 * Tooltip callback (Chart.js `plugins.tooltip.callbacks.afterBody`) cho
 * chart-share. Khi lát đang hover có một dataset "Other", nối thêm vài
 * dòng liệt kê top nước ẩn trong Other cho đúng tháng đó (đã tính sẵn
 * trong other.top_unlisted lúc build). Không hover vào Other -> [] (không
 * thêm dòng nào), giữ nguyên tooltip mặc định của Chart.js.
 */
function shareTooltipAfterBody(tooltipItems) {
  const otherItem = tooltipItems.find((item) => item.dataset.label === OTHER_LABEL);
  if (!otherItem) return [];
  const group = activeGroup();
  const other = group.countries.find((c) => c.name === OTHER_LABEL);
  if (!other || !other.top_unlisted) return [];
  const top = other.top_unlisted[otherItem.dataIndex] || [];
  if (!top.length) return [];
  return ["Trong Other, lớn nhất chưa liệt kê riêng:",
          ...top.map((e) => `${e.name}: ${formatInt(e.volume)} kg`)];
}

/**
 * Nước lớn nhất còn ẩn trong Other tại `monthIndex`, NẾU volume của nó
 * vượt qua nước được đặt tên nhỏ nhất trong nhóm — đây chính là điều kiện
 * "đáng để nhắc nhà phân tích xem lại danh sách nước". Trả về null khi
 * không có breakdown, Other rỗng tháng đó, hoặc không có nước ẩn nào vượt
 * ngưỡng (kể cả khi group không có "Other" chút nào, ví dụ salmon).
 * Hàm thuần: không đọc DOM, dễ test độc lập.
 */
function findOtherOutlier(group, monthIndex) {
  if (!group.countries.length) return null;
  const other = group.countries.find((c) => c.name === OTHER_LABEL);
  if (!other || !other.top_unlisted) return null;
  const top = other.top_unlisted[monthIndex] || [];
  if (!top.length) return null;

  const namedVolumes = group.countries
    .filter((c) => c.name !== OTHER_LABEL)
    .map((c) => c.volume[monthIndex]);
  if (!namedVolumes.length) return null;
  const minNamed = Math.min(...namedVolumes);

  const biggest = top[0];
  return biggest.volume > minNamed ? biggest : null;
}

/**
 * Render (hoặc gỡ bỏ) ghi chú dưới chart-share cho tháng mới nhất. Không
 * có outlier -> gỡ hẳn phần tử ra khỏi DOM (không để lại thẻ rỗng).
 */
function renderOtherNote() {
  const existing = document.getElementById("other-note");
  if (existing) existing.remove();

  const group = activeGroup();
  if (shouldHideShareChart(group)) return;
  const monthIndex = state.data.months.length - 1;
  const outlier = findOtherOutlier(group, monthIndex);
  if (!outlier) return;

  const note = document.createElement("p");
  note.id = "other-note";
  note.className = "other-note";
  note.textContent =
    `Lưu ý: trong mục "Other" của ${group.label} tháng ` +
    `${state.data.months[monthIndex]}, ${outlier.name} chiếm ` +
    `${formatInt(outlier.volume)} kg — lớn hơn nước được liệt kê riêng ` +
    "nhỏ nhất trong nhóm. Có thể danh sách nước cần cập nhật.";
  document.getElementById("share-card").appendChild(note);
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
    const stale = document.getElementById("other-note");
    if (stale) stale.remove();
    return;
  }
  card.hidden = false;

  const options = baseOptions("kg");
  options.scales.y.stacked = true;
  options.scales.x.stacked = true;
  options.plugins = { tooltip: { callbacks: { afterBody: shareTooltipAfterBody } } };

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
  renderOtherNote();
}

function tableMatrix() {
  const group = activeGroup();
  const header = ["Chỉ tiêu", ...state.data.months];
  const rows = [
    ["Sản lượng (kg)", ...group.volume.map(formatInt)],
    ["Giá trị (USD)", ...group.value.map(formatInt)],
    ["ASP (USD/kg)", ...group.asp.map(formatUsdPerKg)],
  ];
  group.countries.forEach((country) => {
    rows.push([`${country.name} — sản lượng (kg)`,
               ...country.volume.map(formatInt)]);
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
  const blob = new Blob(["﻿" + toCsv(rows)],
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

// NOAA công bố trễ khoảng 1,5 tháng, nên 75 ngày mới đáng báo động (gấp
// rưỡi độ trễ công bố thông thường — quá ngưỡng này nghĩa là job cập nhật
// hằng ngày có khả năng đã hỏng, không chỉ là độ trễ công bố bình thường).
const STALENESS_THRESHOLD_DAYS = 75;

/**
 * True nếu latest_period (chuỗi "YYYY-MM") cách thời điểm gọi (mặc định
 * "bây giờ") quá STALENESS_THRESHOLD_DAYS ngày. Hàm thuần, nhận `now` làm
 * tham số để test được mà không phải mock Date toàn cục.
 */
function isDataStale(latestPeriod, now = new Date()) {
  if (!latestPeriod) return false;
  const [year, month] = latestPeriod.split("-").map(Number);
  // Đếm từ NGÀY CUỐI của tháng dữ liệu mới nhất (= ngày đầu tháng kế tiếp),
  // không phải ngày đầu tháng đó — tháng chỉ thực sự "trôi qua" khi đã kết
  // thúc. Dùng ngày đầu sẽ báo động giả ngay cả khi dữ liệu vẫn đang trong
  // độ trễ công bố bình thường của NOAA (~1,5 tháng).
  const periodEnd = new Date(year, month, 1);
  const diffDays = (now - periodEnd) / (1000 * 60 * 60 * 24);
  return diffDays > STALENESS_THRESHOLD_DAYS;
}

function renderStalenessBanner() {
  const existing = document.getElementById("staleness-banner");
  if (existing) existing.remove();
  if (!isDataStale(state.data.latest_period)) return;

  const banner = document.createElement("div");
  banner.id = "staleness-banner";
  banner.className = "staleness-banner";
  banner.textContent =
    `Cảnh báo: dữ liệu mới nhất là ${state.data.latest_period}, đã hơn ` +
    `${STALENESS_THRESHOLD_DAYS} ngày chưa được cập nhật. Có thể job cập ` +
    "nhật tự động đang gặp sự cố — số liệu hiển thị bên dưới có thể đã cũ.";
  document.querySelector("main").prepend(banner);
}

function renderLoadErrorCard(detail) {
  const card = document.createElement("div");
  card.id = "load-error-card";
  card.className = "load-error-card";
  card.innerHTML =
    "<strong>Không tải được dữ liệu.</strong> Dashboard hiện không có số " +
    "liệu để hiển thị. Vui lòng thử tải lại trang; nếu vẫn lỗi, báo cho " +
    `người quản trị.<br>Chi tiết kỹ thuật: ${detail}`;
  document.body.prepend(card);
}

/* ============================================================
   Tab "Tổng hợp" — phần tính toán thuần, không đụng DOM.
   Tách riêng để test được qua Node (xem tests/test_master_tab.py).
   ============================================================ */

const MASTER_KEY = "master";
const MASTER_LABEL = "Tổng hợp";

// Nhóm mốc của cả tab: mọi chênh lệch đều tính so với cá tra.
const BASE_GROUP_KEY = "pangasius";

// Bảy màu cố định cho các nhóm. Dùng CHUNG cho cả chart ASP và chart
// chênh lệch — nếu hai chart tô khác nhau thì người đọc phải học lại bảng
// màu mỗi lần chuyển mắt. 7 màu đủ cho 6 nhóm hiện có và chừa một chỗ
// trước khi phải lặp màu nếu products.yml thêm nhóm thứ 7.
const GROUP_COLORS = ["--data-1", "--data-2", "--data-3",
                      "--data-4", "--data-5", "--data-6", "--data-7"];

/**
 * Gán màu cho danh sách nhóm theo thứ tự trong data.groups. Hàm thuần,
 * cùng quy ước với assignCountryColors: nếu số nhóm vượt quá số màu trong
 * palette, việc lặp màu là có thật — cảnh báo ra console để lộ ra khi phát
 * triển (vd thêm nhóm thứ 8 trong products.yml), nhưng vẫn trả về màu hợp
 * lệ cho mọi nhóm để trang không vỡ.
 */
function assignGroupColors(groupKeys) {
  const map = {};
  groupKeys.forEach((key, i) => {
    if (i >= GROUP_COLORS.length) {
      console.warn(
        `assignGroupColors: ${groupKeys.length} nhóm vượt quá ` +
        `${GROUP_COLORS.length} màu trong palette — màu sẽ bị lặp lại.`
      );
    }
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

/**
 * Loài (khác cá tra) có chênh lệch giá TUYỆT ĐỐI nhỏ nhất so với cá tra ở
 * tháng mới nhất — tức đối thủ cạnh tranh giá gần cá tra nhất. Nhóm không
 * có ASP tháng mới nhất bị bỏ qua (không được chọn dù chênh lệch cũ nhỏ).
 * Trả null khi không có nhóm cá tra hoặc không nhóm nào có chênh lệch hợp
 * lệ ở tháng mới nhất. Trường `yearAgoSpread` CHỈ có mặt khi đã đủ 13
 * tháng dữ liệu và giá trị 12 tháng trước không null — thiếu thì bỏ hẳn
 * trường này (không phải null/dấu gạch) để gọi nơi hiển thị dễ kiểm tra.
 * Hàm thuần, theo cùng phong cách với findOtherOutlier.
 */
function findClosestSpreadCompetitor(data) {
  const base = data.groups.find((g) => g.key === BASE_GROUP_KEY);
  if (!base) return null;
  const last = data.months.length - 1;

  let best = null;
  data.groups.forEach((group) => {
    if (group.key === BASE_GROUP_KEY) return;
    const series = spreadSeries(group.asp, base.asp);
    const latest = series[last];
    if (latest === null || latest === undefined) return;
    if (best === null || Math.abs(latest) < Math.abs(best.latestSpread)) {
      best = { key: group.key, label: group.label, latestSpread: latest, series };
    }
  });
  if (best === null) return null;

  const result = { key: best.key, label: best.label, latestSpread: best.latestSpread };
  const yearAgoIndex = last - 12;
  if (yearAgoIndex >= 0) {
    const yearAgo = best.series[yearAgoIndex];
    if (yearAgo !== null && yearAgo !== undefined) {
      result.yearAgoSpread = yearAgo;
    }
  }
  return result;
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

/**
 * Dựng dữ liệu cho hai chart của tab master. Hàm thuần, không đụng DOM —
 * vì vậy borderColor/backgroundColor ở đây là TÊN biến CSS (vd "--data-1"),
 * giống quy ước của assignCountryColors, chứ không phải màu đã resolve
 * (resolve cần getComputedStyle, tức cần document — không có trong Node).
 * renderMasterCharts() sẽ gọi cssVar() để resolve trước khi vẽ.
 */
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
        // Mảnh và đứt nét (không phải nét liền dày) — mốc 0 không được
        // nuốt mất các đường chênh lệch gần 0 (vd tilapia ~0,09) vẽ đè
        // lên nó. Vẫn giữ nhãn/màu riêng để chú giải còn giải thích được.
        borderWidth: 1,
        borderDash: [4, 3],
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
  const data = state.data;
  const hasBase = Boolean(data.groups.find((g) => g.key === BASE_GROUP_KEY));
  const rows = masterSummaryRows(data);
  const header = ["Nhóm", "Sản lượng (kg)", "SL %MoM", "SL %YoY",
                  "ASP (USD/kg)", "ASP %MoM", "ASP %YoY"];
  // Không có nhóm cá tra thì mọi giá trị "spread" đều là null — thay vì
  // hiện cả cột toàn dấu gạch không giải thích được, ẩn hẳn cột này.
  if (hasBase) header.push("Chênh lệch vs cá tra");

  const body = rows.map((row) => {
    const cells = [
      row.label,
      formatInt(row.volume),
      formatPct(row.volumeMom),
      formatPct(row.volumeYoy),
      formatUsdPerKg(row.asp),
      formatPct(row.aspMom),
      formatPct(row.aspYoy),
    ];
    if (hasBase) cells.push(formatSpread(row.spread));
    const cls = row.key === BASE_GROUP_KEY ? ' class="row-base"' : "";
    return `<tr${cls}>${cells.map((c) => `<td>${c}</td>`).join("")}</tr>`;
  }).join("");

  document.getElementById("master-table").innerHTML =
    `<thead><tr>${header.map((h) => `<th>${h}</th>`).join("")}</tr></thead>` +
    `<tbody>${body}</tbody>`;

  // Hide the static hint when spread column is not present, show it when present.
  const hintEl = document.getElementById("master-spread-hint");
  if (hintEl) {
    hintEl.hidden = !hasBase;
  }
}

/** Resolve tên biến CSS trong dataset thành màu thật, tại thời điểm vẽ. */
function resolveDatasetColors(datasets) {
  return datasets.map((ds) => ({
    ...ds,
    borderColor: cssVar(ds.borderColor),
    backgroundColor: cssVar(ds.backgroundColor),
  }));
}

/**
 * Ghi chú giải thích khi thiếu nhóm cá tra (nhóm mốc) — hiện ở khu vực
 * chung của tab thay cho chart-master-spread rỗng. Không thiếu -> gỡ hẳn
 * phần tử cũ, không để lại thẻ rỗng (cùng quy ước với renderOtherNote).
 */
function renderMasterSpreadMissingNote(hasBase) {
  const existing = document.getElementById("master-spread-missing-note");
  if (existing) existing.remove();
  if (hasBase) return;

  const note = document.createElement("p");
  note.id = "master-spread-missing-note";
  note.className = "master-hint";
  note.textContent =
    "Không thể tính chênh lệch giá so với cá tra: nhóm cá tra (mốc so " +
    "sánh) hiện không có trong dữ liệu. Biểu đồ và cột chênh lệch tương " +
    "ứng đã được ẩn.";
  document.getElementById("master-summary-card").appendChild(note);
}

/**
 * Câu tính sẵn dưới chart-master-spread: loài nào đang cạnh tranh giá gần
 * cá tra nhất, và so với 12 tháng trước ra sao (nếu có đủ dữ liệu).
 * Không có cá tra hoặc không tính được -> gỡ hẳn phần tử.
 */
function renderMasterSpreadNote(hasBase) {
  const existing = document.getElementById("master-spread-note");
  if (existing) existing.remove();
  if (!hasBase) return;

  const info = findClosestSpreadCompetitor(state.data);
  if (!info) return;

  let text = `Đối thủ cạnh tranh giá gần cá tra nhất hiện nay là ` +
    `${info.label}, chênh lệch ${formatSpread(info.latestSpread)} USD/kg.`;
  if (Object.prototype.hasOwnProperty.call(info, "yearAgoSpread")) {
    text += ` Cùng kỳ năm trước, chênh lệch này là ` +
      `${formatSpread(info.yearAgoSpread)} USD/kg.`;
  }

  const note = document.createElement("p");
  note.id = "master-spread-note";
  note.className = "master-hint";
  note.textContent = text;
  document.getElementById("master-spread-card").appendChild(note);
}

function renderMasterCharts() {
  const data = masterChartData(state.data);
  const hasBase = data.spreadDatasets.length > 0;

  drawChart("chart-master-asp", {
    type: "line",
    data: { labels: data.labels, datasets: resolveDatasetColors(data.aspDatasets) },
    options: baseOptions("USD/kg"),
  });

  renderMasterSpreadMissingNote(hasBase);

  const spreadCard = document.getElementById("master-spread-card");
  if (!hasBase) {
    spreadCard.hidden = true;
    if (state.charts["chart-master-spread"]) {
      state.charts["chart-master-spread"].destroy();
      delete state.charts["chart-master-spread"];
    }
    renderMasterSpreadNote(false);
    return;
  }
  spreadCard.hidden = false;

  const spreadOptions = baseOptions("Chênh lệch so với cá tra (USD/kg)");
  // Đường 0 là mốc cá tra — vẽ đậm hơn lưới thường để mắt bắt được ngay.
  spreadOptions.scales.y.grid = {
    color: (ctx) => (ctx.tick.value === 0
      ? cssVar("--border-strong") : cssVar("--border-hairline")),
  };
  drawChart("chart-master-spread", {
    type: "line",
    data: { labels: data.labels, datasets: resolveDatasetColors(data.spreadDatasets) },
    options: spreadOptions,
  });
  renderMasterSpreadNote(true);
}

function renderMaster() {
  renderMasterTable();
  renderMasterCharts();
}

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

async function init() {
  let response;
  try {
    response = await fetch("./data/dashboard.json");
  } catch (err) {
    renderLoadErrorCard(`fetch thất bại (${err.message})`);
    return;
  }
  if (!response.ok) {
    renderLoadErrorCard(`HTTP ${response.status}`);
    return;
  }
  try {
    state.data = await response.json();
  } catch (err) {
    renderLoadErrorCard(`JSON không hợp lệ (${err.message})`);
    return;
  }
  if (!state.data || !Array.isArray(state.data.groups) || !state.data.groups.length) {
    renderLoadErrorCard("dashboard.json không có nhóm dữ liệu nào");
    return;
  }
  state.activeKey = MASTER_KEY;

  document.getElementById("meta-line").textContent =
    `Dữ liệu tới ${state.data.latest_period} · cập nhật lần cuối ${state.data.generated_at}`;
  document.getElementById("export-csv").addEventListener("click", exportCsv);
  document.querySelectorAll(".btn-chart-csv").forEach((button) => {
    button.addEventListener("click",
      () => exportChartCsv(button.dataset.chart));
  });

  renderStalenessBanner();
  render();
}

if (typeof window !== "undefined") {
  init();
}

// Xuất các hàm thuần để test từ Node (xem tests/test_chart_colors.py), không
// ảnh hưởng khi chạy trong trình duyệt (không có `module` trong global đó).
if (typeof module !== "undefined" && module.exports) {
  module.exports = { assignCountryColors, shouldHideShareChart, renderShareChart,
                      state, COUNTRY_COLORS, TOTAL_COLOR, OTHER_COLOR,
                      isDataStale, STALENESS_THRESHOLD_DAYS,
                      shareTooltipAfterBody, findOtherOutlier, renderOtherNote,
                      activeGroup,
                      MASTER_KEY, MASTER_LABEL, BASE_GROUP_KEY, GROUP_COLORS,
                      assignGroupColors, pctChange, changeAt, spreadSeries,
                      masterSummaryRows, findClosestSpreadCompetitor,
                      formatPct, formatSpread, isMasterActive,
                      masterChartData, renderMaster, renderMasterCharts,
                      renderMasterTable, renderMasterSpreadNote,
                      renderMasterSpreadMissingNote,
                      toCsv, chartCsvRows, downloadCsv, exportChartCsv };
}
