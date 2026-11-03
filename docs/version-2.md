# FocusStack 2.0

Ứng dụng tích hợp yêu cầu trong mã tham khảo: nhập JPG/JPEG, PNG, WebP, BMP, TIFF 8/16-bit và RAW; chọn/bỏ chọn từng ảnh hoặc toàn bộ; xem preview trong quá trình căn chỉnh và ghép; xuất TIFF 16-bit, PNG 16-bit hoặc JPEG 8-bit cùng báo cáo JSON. Preview trung gian ghép từng ảnh, trước median smoothing, nên có thể khác ảnh kết quả. Hiệu ứng quét và vòng xoay chỉ biểu thị đang xử lý, không phải tiến độ đo thực tế. Thanh tiến độ vẫn biểu thị các công đoạn.

Đo nét dùng năng lượng Laplacian và Sobel ở hai thang, Gaussian smoothing, chọn vùng và lọc median, có thể căn chỉnh ECC. Báo cáo đưa phần trăm đóng góp của từng ảnh và vùng có độ tin cậy thấp; vùng gần biên giữa hai nguồn có độ tin cậy thấp là khu vực có thể cần kiểm tra seam/halo, không phải xác nhận lỗi. Không có cam kết mọi ảnh sẽ sắc nét hoặc không bị halo. Kiểm tra kết quả ở 100%.

Ảnh nguồn cần cùng kích thước trừ khi bật tùy chọn resize. Ảnh raster phải cùng ICC (hoặc đều không gắn ICC); RAW không trộn với raster để tránh giả định màu. RAW được phát triển cục bộ sang sRGB với WB ảnh đầu, không áp dụng chỉnh sửa Capture One. TIFF một trang 8/16-bit, không hỗ trợ TIFF float, nhiều trang, premultiplied alpha hay ICC không phải RGB. Alpha thẳng được bỏ và ghi vào báo cáo. JPEG là nén mất dữ liệu; PNG/TIFF xuất 16-bit, giữ pixel và ICC; ảnh 8-bit không có thêm chi tiết khi lưu 16-bit. Báo cáo xác minh JPEG theo kích thước và ICC, không tuyên bố pixel giống bản gốc.

Dự án vẫn chạy worker riêng, có thể hủy, không dùng AI/API. Các phép đo và hiệu ứng preview không bảo đảm tốc độ 60 FPS hoặc chất lượng thương mại trên mọi máy.
