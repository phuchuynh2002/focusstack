# Milestone và nghiệm thu

## M1 — CLI depth map

- Chạy test tự động thành công; đọc ít nhất hai ảnh RGB 8/16-bit cùng kích thước; xuất TIFF/PNG 16-bit hoặc JPG 8-bit và depth map tùy chọn.
- ECC căn chỉnh affine nhiều tầng, có `--no-align`; nếu không hội tụ phải báo lỗi. Depth map chọn pixel nguồn và median làm mượt chỉ số, không chọn vùng rỗng sau warp.
- Test thực tế: chụp 10–30 ảnh một sản phẩm cố định, exposure/WB cố định, tên số tăng dần, lấy nét bao phủ toàn bộ vật. Xuất một bộ TIFF 16-bit sRGB và đặt trong thư mục riêng. Chạy lệnh trong README; mở TIFF ở 100%, kiểm tra cả mặt trước/sau, viền, vùng texture thấp, mép ảnh; so với từng ảnh nguồn. Thử `--no-align`, `--radius 2` hoặc `5`, `--smoothing 3` hoặc `7`. Quan sát depth map; ghi lại ảnh lỗi và tham số. Đạt khi vùng cần nét được cải thiện, không có vùng đen do warp và sai màu rõ rệt; halo/seam còn lại được ghi nhận cho M2/M4. Chạy thêm RAW thực tế của máy ảnh nếu cần, so sánh màu và exposure giữa các frame.

## M2 — Fusion B/C

Nghiệm thu: thêm Laplacian pyramid và weighted average, cùng input/output với M1; test reconstruction, weight normalization và biên ảnh. Chạy cùng bộ M1 và so sánh 100% ở texture, viền sáng/tối, tóc/chi tiết mỏng và thời gian; lưu các thông số và kết quả để so sánh. Không tuyên bố tương đương Helicon nếu chưa benchmark.

## M3 — Desktop UI

Nghiệm thu: kéo/thả, thumbnails và chọn ảnh; chạy worker ngoài UI, progress/cancel; preview zoom/pan và so sánh nguồn; báo lỗi. Test với bộ M1, đổi tham số, hủy khi đang xử lý, xác nhận giao diện vẫn phản hồi và xuất lại kết quả.

## M4 — Retouch, batch, preset

Nghiệm thu: brush lấy từ ảnh nguồn đã căn chỉnh, undo/redo; batch nhiều thư mục có báo lỗi riêng; preset lưu/nạp được. Test sửa halo trên bộ M1 ở nhiều mức zoom, lưu/mở preset và chạy hai thư mục, trong đó một thư mục cố ý có lỗi.

## M5 — Hiệu năng và đóng gói

Nghiệm thu: tile có overlap đủ cho bộ lọc, preview giảm độ phân giải, đo RAM/thời gian; multiprocessing và GPU tùy khả năng, có CPU fallback; build PyInstaller trên Windows và kiểm tra máy sạch. Test bộ ảnh 24–60 MP thực tế, so sánh đường nối tile ở 100%, kiểm tra cancel và RAW/định dạng, ghi cấu hình máy cùng peak RAM và thời gian. Mức tài nguyên mục tiêu cần chốt sau benchmark thực tế.
