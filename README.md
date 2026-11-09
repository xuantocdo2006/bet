# Phần mềm thu thập & phân tích bóng đá

Dashboard web (Streamlit) thu thập dữ liệu trận đấu từ football-data.org, lưu vào SQLite và phân tích:
bảng xếp hạng, phong độ, đối đầu (H2H), thống kê chi tiết, dự đoán kết quả (Poisson + Elo) và kiểm chứng mô hình.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Chạy

```bash
streamlit run app.py
```

Mở trình duyệt tại http://localhost:8501.

## Lấy dữ liệu

1. Đăng ký key miễn phí: https://www.football-data.org/client/register
2. Trong thanh bên của ứng dụng: nhập API key, chọn giải + mùa, bấm **Thu thập dữ liệu**.
   (Hoặc dùng dòng lệnh: `FOOTBALL_DATA_API_KEY=xxx python collector.py PL 2025 2024`)
3. Chưa có key? Bấm **Tạo dữ liệu demo** để thử ngay với giải đấu giả lập (mã `DEMO`).

Gói miễn phí giới hạn 10 request/phút (phần mềm tự giãn cách) và chỉ có một số giải lớn.

## Cấu trúc

| File | Vai trò |
|---|---|
| `collector.py` | Gọi API football-data.org, xử lý giới hạn tốc độ và lỗi |
| `db.py` | Lưu/đọc trận đấu bằng SQLite (`football.db`) |
| `analysis.py` | Toàn bộ logic phân tích và dự đoán |
| `demo_data.py` | Sinh dữ liệu giả lập để thử |
| `app.py` | Giao diện dashboard |

## Giới hạn cần biết

- Dữ liệu miễn phí chỉ có tỷ số (cả trận + hiệp 1) và lịch đấu. **Không có** số cú sút, kiểm soát bóng, thẻ phạt, xG.
  Muốn các chỉ số đó cần nguồn khác (API trả phí) và thêm cột vào `db.py`.
- Mô hình dự đoán chỉ dựa trên tỷ số lịch sử, không biết chấn thương, đội hình, lịch thi đấu dày.
  Hãy xem tab **Kiểm chứng mô hình** để biết nó hơn đoán ngẫu nhiên bao nhiêu trên dữ liệu thật.
- Kết quả dự đoán là xác suất ước lượng, không phải cam kết kết quả.
