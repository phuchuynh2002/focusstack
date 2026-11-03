# FocusStack 3.0 — tích hợp notebook Focus Stacker App

Nguồn tham khảo: notebook [Focus Stacker App](https://colab.research.google.com/drive/1x9z_sLiapDrIs5kPGyvcNf_yj625KdqS). Mã được điều chỉnh cho kiến trúc worker riêng và quản lý màu của ứng dụng; không chạy nguyên notebook hoặc tuyên bố tương đương Photoshop/Helicon.

Khi nhập ít nhất hai ảnh, tác vụ nền nạp và căn chỉnh ở độ phân giải gốc. Thư mục Capture One, thư mục khác, file và Open With đều đi qua cùng luồng. Có thể bật tự ghép sau khi căn chỉnh hoặc hủy căn chỉnh khi nhập; việc hủy chờ tác vụ giải mã/căn chỉnh hiện tại kết thúc. Kết quả tạm được dùng lại khi ghép nếu danh sách, checksum và tùy chọn tương thích; nếu chưa sẵn sàng hoặc lựa chọn thay đổi thì căn chỉnh lại trong worker ghép. Tệp gốc không thay đổi. RAW dùng WB của ảnh đầu và không áp dụng sidecar Capture One.

Căn chỉnh dùng ORB/RANSAC khi đủ điểm tin cậy để khởi tạo, sau đó ECC affine và nội suy Lanczos. Vùng phản chiếu ngoài ảnh được đánh dấu không hợp lệ và không được chọn làm pixel nguồn. Không tự thay đổi kích thước trừ khi bật tùy chọn resize. Một số cảnh thiếu chi tiết, có chuyển động hoặc parallax vẫn không thể căn chính xác.

Ghép dùng bản đồ nét Laplacian/Sobel và lọc median, sau đó hòa trộn tháp Laplacian tối đa 5 tầng. Phần trăm trong báo cáo là diện tích chọn theo bản đồ winner, không phải tỷ trọng chính xác sau khi hòa trộn. Bản đồ vùng biên rủi ro là gợi ý kiểm tra, không chứng minh hay loại trừ halo. Hòa trộn có thể tạo mờ, bóng hoặc seam; cần xem ở 100%.

Preview ảnh nguồn và kết quả giữ kích thước pixel gốc, có fit, zoom 100/200/400% và kéo. Màn hình chuyển sang RGB 8-bit sRGB để xem, không làm giảm độ sâu của dữ liệu xuất. Sau ghép, ảnh động phát lại các vùng chọn trên nền caro là minh họa từ ảnh kết quả và winner map; không phải lịch sử từng phép toán pyramid. Nút phát lại cho phép xem lại. Preview trong lúc chạy là ảnh thu nhỏ.

TIFF xuất 16-bit không nén; PNG 16-bit nén lossless; JPEG 8-bit quality 100, 4:4:4 vẫn là nén mất dữ liệu. ICC được giữ. Ảnh đầu vào 8-bit không có thêm chi tiết khi xuất 16-bit. Bộ đệm, ảnh gốc và pyramid có thể dùng nhiều RAM và dung lượng tạm; các số trong app chỉ là ước lượng. Chưa bảo đảm kết quả hoàn hảo hoặc FPS cố định.
