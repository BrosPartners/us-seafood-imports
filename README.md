# US Seafood Imports

Dashboard sản lượng, giá trị và giá bình quân (ASP) hàng thủy sản nhập khẩu vào Mỹ,
dữ liệu NOAA Fisheries, cập nhật tự động hằng ngày.

Thay cho file `giá cá nhập khẩu US - (final).xlsx` trước đây cập nhật tay.

URL production: chưa deploy (xem mục "Deploy" bên dưới) — repo hiện chỉ ở local/GitHub,
chưa bật Pages và chưa gắn vào BP Data Portal.

## Nguồn dữ liệu

NOAA ODS `trade_data`: https://apps-st.fisheries.noaa.gov/ods/foss/trade_data/

Công khai, không cần API key. Bắt buộc gửi header `User-Agent`, thiếu là bị trả 403.

Lọc cố định `source=IMP` và `edible_code=E`. Grain sau khi gộp:
year × month × product × country.

Nhóm sản phẩm khai báo ở `products.yml` (Tilapia, Pangasius, Haddock, Salmon, Cod, Pollock).
Xem mục "Thêm một nhóm sản phẩm mới" bên dưới.

**Không có số liệu thuế.** API không cung cấp trường Calculated Duty, nên dashboard
không có `ASP after tariff` và `% tariff estimated` như file Excel cũ. Duty chỉ tồn tại
trên giao diện web FOSS, mà giao diện đó chặn IP datacenter nên không tự động lấy được.

Dữ liệu hiện đang commit trong repo: 2023-01 → 2026-06 (42 tháng), 93.140 dòng,
642 sản phẩm phân biệt trong `data/trade_imports.csv`.

## Chạy local

```bash
pip install -r requirements.txt
python -m scripts.fetch     # ~3 phút, kéo lại toàn bộ từ 2023-01
python -m scripts.build     # nhanh
python -m http.server 8021 --directory .
```

## Thêm một nhóm sản phẩm mới

Thêm một mục vào `products.yml` rồi chạy `python -m scripts.build`. Không cần sửa code
và không cần kéo lại dữ liệu — `data/trade_imports.csv` đã chứa cả 500+ sản phẩm của NOAA.

`product` phải trùng tuyệt đối trường `name` của NOAA. Tra tên đúng bằng:

```bash
python -c "import csv;print(sorted({r['product'] for r in csv.DictReader(open('data/trade_imports.csv',encoding='utf8'))}))" | tr ',' '\n' | grep -i shrimp
```

**Lưu ý quan trọng:** `scripts.build` chỉ đọc `data/trade_imports.csv`, không tự chạy
trong job hằng ngày trừ khi CSV thay đổi (xem mục "Tự động cập nhật"). Nếu bạn chỉ sửa
`products.yml` mà không có dữ liệu NOAA mới, hãy tự chạy `python -m scripts.build` và
commit `data/dashboard.json` — job hằng ngày sẽ KHÔNG làm việc này giúp bạn.

## Test

```bash
python -m pytest -v
```

Hiện tại: 74 passed, 11 skipped. 11 test skip là do cấu trúc dữ liệu — một số ô của
workbook gốc đơn giản là không có công thức để đối chiếu, không phải lỗi.

`tests/test_golden.py` là chốt chặn quan trọng nhất của dự án: input lấy từ Sheet1 của
file Excel gốc, expected lấy từ kết quả công thức đã cache sẵn ở Sheet2 — nghĩa là
`build.py` phải tự tái tạo được đúng logic SUMIFS của workbook bằng code của mình, không
phải chỉ copy số liệu. Test này fail nghĩa là logic tính đã lệch khỏi file gốc — **sửa
code, đừng sửa fixture**.

File này còn có bảng `KNOWN_WORKBOOK_BUGS`, hiện có đúng một entry, dùng để loại trừ những
ô mà bản thân workbook gốc bị lỗi (xem mục "Lỗi trong workbook gốc" bên dưới) ra khỏi vòng
đối chiếu. Có kèm một test riêng đảm bảo mọi entry trong bảng đó thực sự được xem xét —
nếu sau này sửa fixture mà entry trong bảng không còn khớp ô nào nữa, test sẽ fail để
báo bảng đã lỗi thời.

Sinh lại fixture (chỉ khi file Excel gốc được cập nhật):

```bash
pip install openpyxl
python tests/make_golden.py "<đường dẫn tới file xlsx>"
```

`openpyxl` cố ý KHÔNG có trong `requirements.txt` vì chỉ công cụ sinh fixture một lần này
cần đến, CI không cần cài nó.

Một số test trong `tests/test_chart_colors.py` gọi ra Node để chạy trực tiếp các hàm
export từ `assets/app.js`. Các test này tự động skip nếu máy không có Node. Node không
cần thiết để chạy pipeline dữ liệu, chỉ cần để chạy nhóm test đó.

## Lỗi trong workbook gốc

Trong lúc dựng test golden, phát hiện một lỗi có sẵn trong file Excel gốc: Sheet2 dòng 57
được gắn nhãn Taiwan trong khối Pangasius, nhưng ô công thức duy nhất trong cả dòng đó
(cột L, ứng với 2023-09) lại tham chiếu `$C$6`/`$C$15` — tức khối Tilapia — và trả về
91.040, đúng bằng số Tilapia/Taiwan chứ không phải Pangasius/Taiwan. Đối chiếu ngược lại
Sheet1 thì Pangasius+Taiwan không hề có dòng nào trong suốt 40+ tháng dữ liệu. `build.py`
tính đúng và trả về 0 cho ô này; workbook gốc sai. Entry này được ghi lại trong
`KNOWN_WORKBOOK_BUGS` ở `tests/test_golden.py` để loại khỏi đối chiếu, không phải để che
giấu.

Một khác biệt nữa, nhưng là chủ ý của dự án này chứ không phải bug: dòng `Total volume`
của workbook gốc chỉ cộng 5 nhóm, bỏ sót Pollock. Dashboard này cộng đủ cả 6 nhóm.

## Tự động cập nhật

`.github/workflows/update.yml` chạy 22:00 UTC hằng ngày (05:00 giờ Việt Nam).
Chạy hằng ngày chứ không hằng tháng vì NOAA công bố trễ khoảng 1,5 tháng và không có
ngày cố định. Không có dữ liệu mới thì không commit.

Mỗi lần chạy kéo lại **toàn bộ** lịch sử, không kéo tăng dần, vì NOAA hiệu chỉnh lại
số của các tháng đã công bố.

Chặn an toàn: nếu NOAA trả về ít hơn 80% số dòng lần trước, `fetch.py` dừng và không
ghi đè. Test golden chạy trước bước commit nên dữ liệu hỏng không lên được dashboard.

Job quyết định "có gì thay đổi không" bằng cách diff duy nhất `data/trade_imports.csv`,
không phải toàn bộ thư mục `data/`. Lý do: `build.py` luôn ghi `generated_at` là ngày
chạy hiện tại vào `data/dashboard.json`, nên file này lúc nào cũng khác giữa hai lần
chạy và không dùng được làm tín hiệu "có thay đổi thật". Hệ quả: nếu bạn tự sửa
`products.yml` và tự build/commit `data/dashboard.json` (mục trên), việc đó độc lập với
job hằng ngày — job sẽ không đụng tới file bạn vừa commit trừ khi NOAA có số liệu CSV mới.

## Deploy

Chưa deploy. Khi được duyệt:

- Bật GitHub Pages phục vụ thẳng nhánh `main` từ thư mục gốc, không có bước build riêng.
- Vì Pages sẽ phục vụ ở đường dẫn con `/us-seafood-imports/`, mọi link nội bộ phải là
  đường dẫn tương đối kèm đuôi `.html`.
- Gắn vào BP Data Portal (`../bp-data-portal`) là một bước riêng, làm sau khi có
  URL Pages thật và được xác nhận.

## Ngoài phạm vi

- Nạp Duty thủ công và các chỉ tiêu sau thuế (`ASP after tariff`, `% tariff estimated`).
- Dữ liệu xuất khẩu (`source=EXP`/`REX`).
- Hàng không ăn được (`edible_code` khác `E`).
- Bộ lọc động cho toàn bộ 500+ sản phẩm trên giao diện.
- Sửa hay ghi ngược vào file Excel gốc.
