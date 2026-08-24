# Tab "Tổng hợp" và nút tải dữ liệu trên chart — Thiết kế

Ngày: 2026-08-24
Trạng thái: đã duyệt, chờ lập kế hoạch triển khai

## 1. Mục tiêu

Thêm một tab tổng hợp so sánh cả 6 nhóm sản phẩm cạnh nhau, phục vụ luận điểm thay thế:
người mua Mỹ chuyển giữa các loài cá thịt trắng theo chênh lệch giá, nên câu hỏi cần trả
lời là **cá tra đang rẻ hơn từng loài còn lại bao nhiêu USD/kg, và khoảng cách đó đang nới
hay thu hẹp**.

Kèm theo: mỗi chart có nút tải dữ liệu đang vẽ ra CSV, thay vì chỉ có một nút ở bảng
số liệu như hiện nay.

## 2. Ràng buộc quan trọng: không đụng tới backend

`data/dashboard.json` đã chứa `volume`, `value`, `asp` của cả 6 nhóm theo đủ 42 tháng.
Toàn bộ tab này tính được ở phía trình duyệt.

Không sửa `scripts/build.py`, `scripts/fetch.py`, `scripts/noaa.py`, `products.yml`, và
không kéo lại dữ liệu NOAA. Golden test đối chiếu với workbook gốc không bị ảnh hưởng.

Đây là ràng buộc thiết kế có chủ ý, không phải tình cờ: phần tính số đã được golden test
bảo vệ, nên tính năng hiển thị mới không có lý do gì để chạm vào nó.

## 3. Tab "Tổng hợp"

`key` là `master`, nhãn `Tổng hợp`. Đứng **trước** 6 tab nhóm và là tab mặc định khi mở
trang, thay cho Tilapia hiện tại.

Tab này không đến từ `products.yml` — nó không phải một nhóm sản phẩm. Nó được dựng trong
`assets/app.js` từ 6 nhóm có sẵn trong `dashboard.json`.

### 3.1 Bảng tóm tắt

Sáu dòng, một dòng mỗi nhóm. Dòng Pangasius được tô nhấn vì là mốc so sánh của cả tab.

| Cột | Nội dung |
|---|---|
| Nhóm | nhãn nhóm |
| Sản lượng | `volume` của kỳ mới nhất, kg |
| Sản lượng %MoM | so tháng liền trước |
| Sản lượng %YoY | so cùng kỳ 12 tháng trước |
| ASP | `asp` kỳ mới nhất, USD/kg |
| ASP %MoM | so tháng liền trước |
| ASP %YoY | so cùng kỳ 12 tháng trước |
| Chênh lệch ASP vs cá tra | `asp[nhóm] − asp[pangasius]` tại kỳ mới nhất, USD/kg |

Cột cuối là cột mang thông tin chính: nhìn phát thấy ngay cod và salmon đang đắt hơn cá
tra bao nhiêu.

### 3.2 Chart ASP tuyệt đối

Sáu đường, đơn vị USD/kg thật.

ASP giữa các loài lệch tới 4,8 lần (tháng 4/2026: cá tra 3,06 · salmon 14,61), nên ba loài
rẻ bị nén ở đáy. Chấp nhận điều này có chủ ý: đây là mức giá cần trích dẫn khi lập luận,
và chart 3.3 mới là chart giải quyết vấn đề thang đo.

### 3.3 Chart chênh lệch ASP so với cá tra

Năm đường (trừ chính Pangasius), giá trị `asp[nhóm] − asp[pangasius]` theo từng tháng.
Có một đường 0 nằm ngang làm mốc, gán nhãn là Pangasius.

Đường đi lên nghĩa là loài đó đang đắt lên tương đối so với cá tra, tức lợi thế giá của cá
tra đang nới rộng. Đây là chart mang luận điểm.

Vì mọi giá trị đều quy về cùng một gốc, chart này không có vấn đề thang đo.

### 3.4 Màu

Mỗi nhóm có một màu **cố định, dùng chung cho cả hai chart** của tab — Pangasius ở chart
ASP và ở chart chênh lệch phải cùng một màu, nếu không người đọc phải học lại bảng màu khi
chuyển mắt giữa hai chart.

Bảng màu lấy từ token có sẵn. Repo hiện có `--data-1` đến `--data-9` (trong đó `--data-8`,
`--data-9` được thêm ở `assets/dashboard.css`), đủ cho 6 nhóm. Không thêm màu mới.

Pangasius vẽ dày hơn các đường còn lại ở cả hai chart, vì nó là mốc.

### 3.5 Điều tab master không có

Không có chart thị phần theo nước — tab master so sánh giữa các loài, phần chia theo nước
đã nằm ở tab của từng nhóm.

Khi tab master đang mở, các khối dành riêng cho một nhóm phải được ẩn: hàng KPI, ba chart
của tab nhóm, ghi chú về dòng "Other", và bảng "Số liệu chi tiết". Ngược lại, khi chuyển
sang một tab nhóm thì hai chart và bảng tóm tắt của master phải được ẩn. Không được để sót
nội dung của tab trước trên màn hình — đây chính là loại lỗi đã từng xảy ra ở repo này với
ghi chú "Other" còn lại sau khi chuyển sang nhóm không có breakdown.

Chân trang giữ nguyên ở mọi tab, gồm cả ghi chú không bao gồm thuế nhập khẩu.

## 4. Nút tải CSV trên chart

Mỗi chart có nút tải riêng, xuất đúng dữ liệu đang vẽ trên chart đó. Áp dụng cho cả 5
chart: ba chart của tab nhóm (sản lượng, ASP, thị phần theo nước) và hai chart của tab
master.

Định dạng giữ nguyên như hàm xuất CSV hiện có: có BOM UTF-8 để Excel không lỗi font tiếng
Việt, mọi ô đều bọc ngoặc kép, ngoặc kép bên trong nhân đôi, giá trị `null` xuất thành ô
trống chứ không phải chữ `null`, và số xuất ở dạng thô chứ không phải chuỗi đã định dạng
theo locale.

Tên file phải phân biệt được: gồm tên nhóm và tên chart, ví dụ
`nhap-khau-my-pangasius-asp.csv`, `nhap-khau-my-tong-hop-chenh-lech.csv`.

Nút "Tải CSV" hiện có ở bảng số liệu giữ nguyên, không bỏ.

## 5. Các trường hợp biên

| Tình huống | Hành vi |
|---|---|
| `asp` là `null` (tháng nhóm đó không có hàng) | Chart để đứt đoạn, không nối liền qua chỗ trống. Bảng hiện gạch ngang. CSV để ô trống. |
| Tính %YoY khi chưa đủ 12 tháng lịch sử | Gạch ngang, không phải 0. Áp dụng cho 12 tháng đầu chuỗi. |
| Mẫu số bằng 0 hoặc `null` khi tính %MoM / %YoY | Gạch ngang. Không bao giờ chia cho 0, không bao giờ hiện `NaN` hay `Infinity`. |
| Chênh lệch khi một trong hai đầu thiếu ASP | Ô trống, điểm đứt trên chart. |
| Chênh lệch của Pangasius với chính nó | Bằng 0 ở mọi tháng — dùng làm phép kiểm tra ngược trong test. |

## 6. Kiểm thử

Phần tính toán tách thành hàm thuần, không đụng DOM, để test được. Chạy qua đúng bộ khung
Node đã có sẵn ở `tests/test_chart_colors.py` — gọi hàm thật export từ `assets/app.js`,
`skipif` khi máy không có Node.

Bắt buộc có:

- Chênh lệch của Pangasius với chính nó bằng 0 ở cả 42 tháng, chạy trên `dashboard.json` thật.
- Một tháng có `asp` là `null` cho ra ô trống, không phải `NaN`.
- %YoY của 12 tháng đầu là gạch ngang, tháng thứ 13 có giá trị và bằng đúng công thức.
- %MoM với mẫu số 0 cho ra gạch ngang, không phải `Infinity`.
- Màu của mỗi nhóm giống nhau giữa chart ASP và chart chênh lệch.
- CSV xuất ra từ một chart có đúng số dòng và số cột như dữ liệu đang vẽ, và ô `null` là ô trống.

## 7. Ngoài phạm vi

- Thị phần Việt Nam theo từng nhóm. Hữu ích cho VHC nhưng là câu hỏi khác ("ai bán"), và
  cần sửa `build.py` vì Haddock và Salmon hiện không tách Việt Nam.
- Chart sản lượng 6 nhóm chồng nhau.
- Xuất `.xlsx` thật nhiều sheet. Đã cân nhắc và loại: trang chạy thuần không thư viện ngoài
  và bị cấm CDN, nên sẽ phải tự viết bộ ghi zip + XML. CSV kèm BOM đã mở được bằng Excel.
- Mọi thay đổi ở `build.py`, `fetch.py`, `noaa.py`, `products.yml` hay dữ liệu.
