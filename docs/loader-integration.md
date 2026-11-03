# Image Loader integration — 0.4.0

Nguồn: notebook [Image Loader](https://colab.research.google.com/drive/1Ns5Z7Ui3uLP7MrO9cx91YgPjTPrv7q0h), đọc ngày 2026-11-03. Notebook cung cấp bộ đọc/chuẩn hóa/lưu ảnh, không cung cấp thuật toán stacking mới hoặc kết quả benchmark. Không chạy nguyên notebook.

Ứng dụng tích hợp nạp song song có thứ tự, BMP/WebP, ảnh xám/alpha, chuẩn hóa 8/16-bit và tùy chọn resize. Core giữ RGB float32 thay vì BGR; giữ EXIF orientation TIFF, kiểm tra ICC, WB thống nhất cho RAW và xác minh TIFF output. Không nhận float TIFF, profile không phải RGB, TIFF nhiều trang hoặc alpha premultiplied. Không trộn RAW với raster. Chỉ resize khi người dùng bật rõ ràng; mặc định giữ nguyên kích thước nguồn và từ chối bộ khác kích thước.

`core/io/loader.py` chứa loader; `RenderSettings` chuyển tùy chọn từ GUI qua CLI tới pipeline. Tiến trình hiển thị nạp → căn chỉnh → quét vùng nét → ghép → xác minh. Báo cáo ghi hash nguồn, dtype/kích thước trước resize và các chuyển đổi. Có API tương thích tuple của notebook và helper chuyển dtype đầu ra; pipeline vẫn dùng bộ lưu TIFF hiện có để giữ ICC và xác minh.

Kiểm chứng ngày 2026-11-03:

- 53 kiểm thử lõi đạt (`pytest -q --ignore=tests/test_desktop_ui.py`).
- 7 kiểm thử giao diện trong bundle QA đạt, gồm preview, chọn nhiều ảnh, worker, hủy, RAW, lưu cấu hình, BMP/WebP và resize. QA chạy Qt offscreen; không phải đánh giá bố cục bằng mắt.
- Build `dist/loader/FocusStack.app` phiên bản 0.4.0 thành công; chữ ký ad-hoc kiểm tra `codesign --verify --deep --strict` đạt.
- Bundle chính khởi động smoke test thành công.

Chưa benchmark tăng tốc, chưa kiểm thử mọi định dạng RAW/máy ảnh, chưa chạy chuyển ảnh thực tế từ Capture One. TIFF/ICC không tự chứng minh provenance Capture One. Chưa thay bản đang cài trong `/Applications`; bản mới ở `dist/loader/FocusStack.app`.
