# FocusStack 0.4 — bộ nạp ảnh song song

## Chạy và đóng gói

```sh
python -m pip install -e ".[test,desktop]"
python -m pytest -q
python -m focus_stacker.main
python -m PyInstaller --noconfirm FocusStack.spec
```

macOS: `dist/FocusStack.app`; Windows: `dist/FocusStack/FocusStack.exe` cùng toàn bộ thư mục. Build riêng cho từng OS. Bản macOS cài tại chỗ dùng chữ ký ad-hoc, chưa có Developer ID/notarization.

## Quy trình sử dụng

1. Trong Capture One, chọn cả bộ ảnh, bật **Image → Edit All Selected Variants**. Xuất/Edit With thành **TIFF RGB 16-bit, cùng ICC, cùng kích thước, không alpha**. TIFF chứa pixel đã áp dụng chỉnh sửa; FocusStack không đọc chỉnh sửa từ sidecar của RAW.
2. Thêm RAW hoặc TIFF/JPG/PNG/BMP/WebP vào FocusStack. Chọn số luồng nạp ảnh (mặc định 2). Chỉ bật đổi kích thước nếu chấp nhận nội suy ảnh về kích thước ảnh đầu tiên. Với TIFF đã xuất từ Capture One, bật **Capture One: chỉ TIFF RGB 16-bit có ICC**. RAW được phát triển cục bộ sang sRGB, cùng WB lấy từ ảnh đầu; không áp dụng chỉnh sửa Capture One. Để giữ chỉnh sửa Capture One, xuất TIFF 16-bit cùng ICC. Không trộn RAW và ảnh đã render trong một stack.
3. Kiểm tra nhãn **Đã nhận N ảnh · chọn ghép M ảnh** và dấu tích bên cạnh từng ảnh. Ảnh mới tự được đánh dấu; bấm tên ảnh để xem trước mà không đổi lựa chọn ghép. Bỏ dấu tích để loại ảnh khỏi stack, hoặc bấm **Chọn tất cả để ghép**. **Bỏ ảnh đã chọn khỏi danh sách** xóa các dòng đang chọn. Nếu chỉ nhận một ảnh từ Capture One, kiểm tra lại lựa chọn và thiết lập Capture One; app không tự tìm ảnh chưa được gửi.
4. **Ghép stack M ảnh đã chọn**: kiểm tra ngay định dạng (TIFF RGB 16-bit, có ICC) và báo rõ file sai trước khi chạy; sau đó căn chỉnh (nếu bật), đo năng lượng Laplacian, chọn vùng nét, ghép, ghi TIFF rồi đọc lại kiểm tra pixel 16-bit, kích thước và ICC. Ảnh được ghép theo thứ tự tên file. Thanh tiến độ hiển thị giai đoạn/ảnh và thời gian; đây là tiến độ theo công đoạn, không phải ước lượng thời gian còn lại. Hủy dừng worker riêng. Click xem ảnh nguồn sau khi ghép không xóa kết quả chưa lưu.
5. Sau khi ghép, xem TIFF kết quả, bản đồ vùng lấy nét và tỷ lệ đóng góp từng ảnh. Lưới 8×8 chỉ tóm tắt vùng cần kiểm tra; thuật toán chọn pixel ở độ phân giải gốc. Bước quét riêng đã bỏ khỏi giao diện (CLI vẫn có `--scan-only`).
6. **Lưu TIFF + báo cáo** tạo hai file mới: `stack.tif` và `stack.tif.focusstack.json`. Không ghi đè ảnh nguồn/file có sẵn. Báo cáo có checksum, nguồn, tham số, % đóng góp, vùng chưa rõ nét. Nhập TIFF đã lưu trở lại Capture One; chưa có round-trip tự động.

## Giới hạn của kiểm tra chất lượng và lịch sử

- ICC và pixel của TIFF được ghi/đọc lại có thể kiểm chứng. Không thể bảo đảm chất lượng thị giác tuyệt đối: căn chỉnh nội suy, lựa chọn pixel và median có thể tạo seam/halo. Xem TIFF đầy đủ ở 100% trong Capture One.
- Nếu chỉ một nguồn đóng góp pixel, app cảnh báo thay vì tuyên bố đã tăng vùng nét.
- Vùng ít chênh lệch năng lượng nét có thể là nền trơn hoặc mờ; bản đồ không xác định chắc chắn nơi cần lấy nét lại.
- TIFF do phiên bản này ghép chứa metadata FocusStack. Thiếu metadata không chứng minh ảnh chưa từng stack; metadata cũng không phải bằng chứng chống sửa đổi. JSON kèm checksum giúp đối chiếu đúng file đã xuất.
- Preview/thumbnail được giải mã ở nền, chuyển ICC sang sRGB và thu nhỏ tối đa 1600 px; không thay đổi TIFF. TIFF nén được hỗ trợ qua imagecodecs. Preview thu nhỏ không thay thế kiểm tra 100% file gốc.
- Ảnh đến trong lúc ghép được xếp hàng chờ; bấm **Thêm ảnh đang chờ** sau khi hoàn tất. Không thêm âm thầm vào tác vụ đang chạy.
- Phân tích độ nét là thuật toán ảnh cục bộ, **không phải AI/Agents API**. Chưa có kết nối AI hay tải ảnh lên dịch vụ bên ngoài.
- Giữ toàn bộ stack đã căn chỉnh trong RAM; chưa có xử lý tile/GPU, retouch hoặc Method B/C.

## Kiểm thử giao diện đóng gói trên macOS

Nếu môi trường Python không tìm thấy Qt platform plugin, có thể kiểm thử đúng môi trường đóng gói bằng runner riêng:

```sh
python -m PyInstaller --noconfirm --onedir --windowed --name FocusStackQA --paths src --paths tests --distpath /tmp/focusstack-qa-dist --workpath /tmp/focusstack-qa-build --specpath /tmp tests/desktop_probe.py
/tmp/focusstack-qa-dist/FocusStackQA.app/Contents/MacOS/FocusStackQA
```

Kết quả ở `/tmp/focusstack-ui-check-results.json`. Runner kiểm tra nhiều FileOpen events, chống trùng, nhập và ghép RAW, thumbnail/preview, số ảnh chọn, thêm ảnh nhiều lần, ghép/xuất/hủy và hàng chờ. Đây không thay thế kiểm thử Capture One xuất ảnh thật.
