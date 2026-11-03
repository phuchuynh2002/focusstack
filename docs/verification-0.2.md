# Kiểm chứng bản FocusStack 0.2.0 — 2026-11-02

Đã cài `/Applications/FocusStack.app`. Bản trước được giữ tại
`~/Library/Application Support/FocusStack/backups/before-v02-tou2w3zf/FocusStack.app`.

## Đã đạt

- 42 test xử lý/IO/RAW/workflow: `tests/test_m1.py`, `tests/test_desktop_core.py`, `tests/test_raw.py`, `tests/test_workflow.py`.
- Hai kịch bản tích hợp GUI chạy trong bundle PyInstaller: nhận nhiều FileOpen events, chống trùng, hỏi khi nhận RAW, đếm ảnh tick, thumbnail/preview, quét không tạo kết quả, ghép/kiểm chứng, xuất TIFF + JSON, chống ghi đè nguồn, hủy, xếp hàng ảnh đến khi đang xử lý.
- Kiểm tra trực tiếp GUI macOS trên bộ TIFF tổng hợp: nhận 2/2 ảnh, hiển thị thumbnail và preview; tắt căn chỉnh vì ảnh thử đã thẳng hàng; ghép đạt 100%, hai ảnh đóng góp lần lượt 50.125% và 49.875%; hiển thị bản đồ vùng nét và báo cáo.
- Bản release kiểm tra chữ ký ad-hoc bằng `codesign --verify --deep --strict`, mở GUI thành công; đăng ký Launch Services sau khi cài.

## Chưa xác minh / chưa triển khai

- Không chạy bộ ảnh khách hàng hay kiểm chứng Capture One xuất nhiều TIFF thực tế trong lượt này; không tuyên bố round-trip native hoàn tất.
- GUI yêu cầu chọn TIFF đã xuất, không tự điều khiển Capture One để render RAW. Chỉnh sửa trong Capture One phải được áp dụng vào TIFF trước khi ghép.
- AI/Agents API chưa kết nối; không có ảnh nào được gửi tới OpenAI. Phân tích vùng nét là thuật toán cục bộ, không phải AI.
- Không thể xác định chắc chắn ảnh bất kỳ từng stack hay chưa nếu không có provenance. Metadata FocusStack và báo cáo checksum giúp nhận biết kết quả do app tạo; không phải chứng nhận chống giả mạo.
- Môi trường Python nguồn vẫn gặp lỗi tìm Qt `offscreen`; đã dùng môi trường bundle riêng để chạy kiểm thử GUI thật. Không sửa cấu hình Qt toàn hệ thống.
- Giữ ICC/16-bit và xác minh pixel ghi ra không bảo đảm không có seam/halo; cần xem ảnh thật ở 100% trong Capture One.
