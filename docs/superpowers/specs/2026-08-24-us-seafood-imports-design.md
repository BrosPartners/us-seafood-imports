# US Seafood Imports Dashboard — Thiết kế

Ngày: 2026-08-24
Trạng thái: đã duyệt, chờ lập kế hoạch triển khai

## 1. Mục tiêu

Thay file `giá cá nhập khẩu US - (final).xlsx` (đang cập nhật thủ công) bằng một hệ thống
tự động kéo dữ liệu nhập khẩu thủy sản vào Mỹ từ NOAA và hiển thị trên dashboard web
đặt dưới org GitHub BrosPartners, nhúng vào `bp-data-portal`.

Bối cảnh sử dụng: theo dõi giá và sản lượng Pangasius Việt Nam so với các loài cá thịt
trắng cạnh tranh tại thị trường Mỹ, phục vụ phân tích VHC.

## 2. Nguồn dữ liệu

### Endpoint

    https://apps-st.fisheries.noaa.gov/ods/foss/trade_data/

NOAA đã dời ODS lên cloud; endpoint cũ `www.st.nmfs.noaa.gov/ords/foss/` và
`apps-st.fisheries.noaa.gov/ords/foss/` đều đã chết. Endpoint mới trả JSON, công khai,
không cần API key.

Metadata (21 field): https://apps-st.fisheries.noaa.gov/ods/foss/metadata-catalog/trade_data/

Truy vấn theo tham số `q` là JSON URL-encoded, phân trang bằng `limit` + `offset`,
trường `hasMore` báo còn dữ liệu.

### Đã kiểm chứng

- Kéo Tilapia fillet frozen, `source=IMP`, 2026-04: Volume và Value **khớp tuyệt đối**
  với Sheet1 ở từng nước (CHINA 3.845.424 kg / $9.357.430; VIETNAM 640.817 kg /
  $2.853.226; INDONESIA 674.135 kg / $5.866.527; TAIWAN 112.666 kg / $847.872).
- NOAA đã có số tới **2026-06**; file Excel dừng ở 2026-04.
- Một tháng `source=IMP` + `edible_code=E` = 4.599 dòng thô, tải 3,7 giây, 500 product,
  2.103 cặp product × country.

### Ánh xạ field

| Sheet1 | NOAA API |
|---|---|
| Year | `year` (chuỗi, "2026") |
| Month | `month` (chuỗi, "04") — cần đổi sang tên tháng tiếng Anh khi so với Excel |
| Trade Type | `source` ("IMP" / "EXP" / "REX") |
| Product Name | `name` |
| Country Name | `cntry_name` |
| Volume (kg) | `kilos` |
| Value (USD) | `val` |
| Edible code | `edible_code` |
| Calculated Duty (USD) | **không tồn tại** |

### Ràng buộc đã xác định: không có Duty

`Calculated Duty` không có trong bất kỳ bảng nào của FOSS ODS (đã kiểm tra cả 15 bảng
trong metadata-catalog). Đó là trường do giao diện web FOSS tự tính.

Không tái tạo được bằng bảng thuế suất: thuế biến thiên theo từng dòng HTS chứ không
đồng nhất theo nước. Ví dụ VIETNAM 2026-04, 22 dòng sản phẩm cho 12 mức duty/value khác
nhau (0% · 7,33% · 9,86% · 10% · 16% · 22,5% · 45%) — là trộn của MFN specific rate,
thuế đối ứng và AD/CVD.

Không cào được giao diện web: `fisheries.noaa.gov/foss/` chặn IP datacenter bằng Akamai
(HTTP 403 Access Denied). GitHub Actions runner cũng là IP datacenter nên phương án
Playwright bị loại.

**Quyết định: bỏ Duty.** Xem mục 5.

## 3. Kiến trúc

Repo `us-seafood-imports` dưới org BrosPartners. Không server, không database, không
API key, không bước build.

    NOAA ODS API ──(GitHub Actions, cron hằng ngày)──> fetch.py
                                                          │
                                            data/trade_imports.csv
                                                          │  build.py
                                            data/dashboard.json
                                                          │
                                      index.html + app.js ──> GitHub Pages
                                                          │
                                             bp-data-portal (iframe)

### Vì sao cron hằng ngày, không phải hằng tháng

NOAA công bố trễ khoảng 1,5 tháng và không có ngày cố định. Chạy hằng ngày rẻ; khi
không có gì mới thì không commit, nên không tạo nhiễu lịch sử git.

### Vì sao kéo lại toàn bộ mỗi lần, không kéo tăng dần

NOAA hiệu chỉnh lại số của các tháng đã công bố. Kéo full (~3 phút) đảm bảo dashboard
luôn khớp NOAA mới nhất.

## 4. Các thành phần

Ba đơn vị tách bạch, mỗi đơn vị một nhiệm vụ, giao tiếp qua file trên đĩa.

### 4.1 `fetch.py` — lấy dữ liệu thô

Đầu vào: không (tự xác định khoảng thời gian: 2023-01 → tháng hiện tại).
Đầu ra: `data/trade_imports.csv`.

- Lặp theo từng tháng, gọi API với `{"year", "month", "source": "IMP", "edible_code": "E"}`.
- Phân trang tới khi `hasMore` = false.
- Gộp bỏ chiều `custom_district_name`, cộng `kilos` và `val` để về grain
  **year × month × product × country** — đúng grain của Sheet1.
- Ghi CSV cột: `year, month, product, country, volume_kg, value_usd`.
- Tháng chưa có dữ liệu: bỏ qua, không phải lỗi.

Không biết gì về 6 nhóm sản phẩm hay về dashboard. Kéo tất cả 500 product.

### 4.2 `build.py` — dựng số liệu dashboard

Đầu vào: `data/trade_imports.csv` + `products.yml`.
Đầu ra: `data/dashboard.json`.

`products.yml`:

```yaml
- key: tilapia
  label: Tilapia
  product: "TILAPIA (OREOCHROMIS SPP.) FILLET FROZEN"
  countries: [CHINA, VIETNAM, TAIWAN, INDONESIA]
```

Sáu nhóm, đúng danh sách nước như Sheet2 đang dùng:

| key | Product Name (NOAA) | Countries |
|---|---|---|
| tilapia | TILAPIA (OREOCHROMIS SPP.) FILLET FROZEN | CHINA, VIETNAM, TAIWAN, INDONESIA |
| pangasius | CATFISH (PANGASIUS) FILLET FROZEN | VIETNAM, TAIWAN |
| haddock | GROUNDFISH HADDOCK FILLET FROZEN | CHINA, INDONESIA, NORWAY, CANADA, ICELAND |
| salmon | SALMON ATLANTIC FILLET FROZEN | (không breakdown trong Sheet2) |
| cod | GROUNDFISH COD NSPF FILLET FROZEN | CHINA, INDONESIA, NORWAY, CANADA, ICELAND, ECUADOR, GREENLAND, VIETNAM |
| pollock | GROUNDFISH POLLOCK ALASKA FILLET FROZEN | CHINA, INDONESIA, UNITED KINGDOM, CANADA, ICELAND, ECUADOR, GREENLAND, VIETNAM |

Công thức, giữ nguyên như Sheet2:

- `volume` = tổng `volume_kg` theo (year, month, product)
- `value` = tổng `value_usd` theo (year, month, product)
- `asp` = `value / volume` (USD/kg); volume = 0 → null, không chia
- Theo từng nước: cùng công thức, thêm điều kiện country
- **`Other`** = tổng nhóm trừ tổng các nước trong danh sách. Đảm bảo breakdown luôn
  cộng đủ 100%, và làm lộ ra khi có nước mới nổi lên mà danh sách chưa có. Nhóm không
  có danh sách nước (`salmon`) thì không có breakdown và không có dòng `Other`.
- `total_volume` = tổng volume của **cả 6** nhóm.

Sheet2 dòng 130 hiện cộng thiếu Pollock (chỉ 5 nhóm). Đây là lỗi trong file gốc; bản
web cộng đủ 6.

Thêm sản phẩm mới sau này = thêm một mục vào `products.yml`. Không sửa code, không cần
backfill vì CSV thô đã có sẵn toàn bộ 500 product.

### 4.3 `index.html` + `app.js` — dashboard

Trang tĩnh, đọc `data/dashboard.json`. Dùng chung CSS và logo với `bp-data-portal`.

- Chọn nhóm sản phẩm (6 tab hoặc dropdown).
- Chart 1: Volume theo tháng.
- Chart 2: ASP (USD/kg) theo tháng.
- Chart 3: Thị phần theo nước (gồm cả Other).
- Bảng số liệu, xuất được CSV.
- Chân trang: ghi rõ nguồn, thời điểm cập nhật gần nhất, và ghi chú không gồm thuế.

## 5. Khác biệt so với Sheet2

Bỏ ba chỉ tiêu, đều phái sinh từ Duty:

- `Duty`
- `ASP after tariff` = `(Value + Duty) / Volume`
- `% tariff estimated` = `ASP_after / ASP − 1`

Dashboard ghi rõ ở chân trang: *"Không bao gồm thuế nhập khẩu — NOAA ODS API không
cung cấp Calculated Duty."*

Nếu sau này cần chỉ tiêu sau thuế, đường nâng cấp là nạp Duty thủ công: thêm file
`data/duty_manual.csv` (grain year × month × product × country) và một nhánh trong
`build.py`. Kiến trúc hiện tại không cản việc đó. Ngoài phạm vi lần này.

## 6. Xử lý lỗi

| Tình huống | Hành vi |
|---|---|
| API chết hoặc đổi endpoint | Job fail, GitHub gửi mail. Dashboard giữ nguyên dữ liệu cũ, không trắng trang. |
| API trả về ít hơn lần trước >20% số dòng | Coi là dữ liệu lỗi. Dừng, không ghi đè, job fail. |
| Tháng mới chưa có số | Bỏ qua im lặng, không phải lỗi. |
| Dữ liệu không đổi so với lần chạy trước | Không commit. |
| `volume` = 0 khi tính ASP | Trả `null`, không chia cho 0. |

## 7. Kiểm thử

Chốt chặn quan trọng nhất là **test đối chiếu golden file**: dùng chính
`giá cá nhập khẩu US - (final).xlsx` làm chuẩn, khẳng định Volume / Value / ASP mà
`build.py` tính ra khớp Sheet2 trên toàn bộ 2023-01 → 2026-04, cả 6 nhóm và mọi nước
trong danh sách. Lệch thì fail. Đây là bằng chứng duy nhất cho thấy hệ thống mới thay
được file cũ.

Ngoài ra:

- `fetch.py`: test phân trang (`hasMore`), test gộp bỏ chiều district, test tháng rỗng.
  Gọi API thật được mock bằng response đã ghi lại.
- `build.py`: test dòng `Other` cộng đúng phần dư; test `volume = 0` trả null;
  test `total_volume` gồm đủ 6 nhóm.
- Guard 20%: test không ghi đè khi dữ liệu teo bất thường.

## 8. Deploy

GitHub Pages phục vụ thẳng nhánh `main` từ thư mục gốc, giống `bp-data-portal`. Không
có bước build. Vì Pages phục vụ ở đường dẫn con `/us-seafood-imports/`, mọi link nội bộ
phải là đường dẫn tương đối kèm đuôi `.html`.

Gắn vào portal: thêm một object vào `dashboards.js` của `bp-data-portal` và sao chép
một trang vỏ theo hướng dẫn trong README của repo đó. Portal không đọc dữ liệu của repo
này, chỉ nhúng iframe.

## 9. Ngoài phạm vi

- Nạp Duty thủ công và các chỉ tiêu sau thuế.
- Dữ liệu xuất khẩu (`source=EXP`/`REX`) — chỉ làm `IMP`.
- Hàng không ăn được (`edible_code` khác `E`).
- Bộ lọc động cho toàn bộ 500 product trên giao diện — dashboard cố định 6 nhóm.
- Sửa hay ghi ngược vào file Excel gốc.
