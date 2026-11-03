# FocusStack

# Tải FocusStack cho macOS

Tải [FocusStack 3.0.0 cho Mac Apple Silicon](https://github.com/phuchuynh2002/focusstack/releases/latest) (chip M1, M2, M3 và các thế hệ Apple Silicon). Bản tải này chưa hỗ trợ Mac Intel hoặc Windows.

1. Mở trang tải, trong mục **Assets** chọn `FocusStack-3.0.0-macOS-Apple-Silicon.zip`.
2. Mở file ZIP đã tải, kéo `FocusStack.app` vào thư mục **Applications (Ứng dụng)** và mở ứng dụng.
3. Bản này chưa được Apple công chứng, nên macOS có thể chặn khi mở lần đầu. Nếu tin tưởng nguồn tải, sau khi thử mở ứng dụng, vào **System Settings → Privacy & Security → Open Anyway**, rồi xác nhận. Xem [hướng dẫn của Apple](https://support.apple.com/en-us/102445).

## Dành cho nhà phát triển

**Cấu trúc mã nguồn:** xem [core / workers / ui / utils](docs/architecture.md). Package chính là `focus_stacker`; tên `focusstack` cũ được giữ bằng lớp tương thích.

**Desktop 0.4:** GUI nhận RAW trực tiếp, TIFF/JPG/PNG/BMP/WebP với kiểm tra ICC, nạp ảnh song song, có chế độ tự chọn tham số cục bộ và ước lượng RAM. RAW không áp dụng chỉnh sửa Capture One; xuất TIFF trước nếu cần giữ các chỉnh sửa đó. Xem [workflow](docs/desktop.md).

**Desktop preview added:** see [build/run instructions](docs/desktop.md) and [Capture One status](docs/capture-one.md). TIFF now uses tifffile and preserves a shared ICC profile; mixed profiles are rejected. Tagged sources currently require TIFF output. The orientation, EXIF sorting and warp-border issues from review have been corrected. These changes supersede the older M1 limitations below where applicable. The native Capture One SDK plugin and vendor approval are still pending.

Thông tin về các giai đoạn phát triển trước đây: [lộ trình và nghiệm thu](docs/milestones.md).

## Cài đặt

Python 3.11 trở lên trên Windows/macOS. Trong thư mục dự án:

```bash
python -m venv .venv
```

macOS: `source .venv/bin/activate`; Windows PowerShell: `.venv\Scripts\Activate.ps1`.

```bash
python -m pip install -e ".[test]"
python -m pytest -q
python -m focus_stacker.cli --help
```

## Chạy stack

**RAW đầu vào:** nhận CRW/CR2/CR3 (Canon), NEF/NRW (Nikon), ARW/SR2/SRF
(Sony), RAF (Fujifilm), ORF (Olympus/OM System), RW2/RAW (Panasonic),
PEF (Pentax), RWL (Leica), SRW (Samsung), X3F (Sigma), 3FR/FFF
(Hasselblad), IIQ (Phase One), MOS (Leaf), MEF (Mamiya), MRW (Minolta),
ERF (Epson), DCR/KDC (Kodak) và DNG. Nhận cả đuôi viết hoa/viết thường
qua CLI và GUI.
Đây là danh sách đuôi được nhận; khả năng giải mã từng máy và kiểu nén phụ thuộc
[LibRaw](https://www.libraw.org/supported-cameras). File `.raw` phải là ảnh máy ảnh
có cấu trúc được LibRaw nhận diện, không phải dữ liệu nhị phân tùy ý.

RAW được phát triển bằng camera WB sang RGB sRGB 16-bit rồi ghép; **kết quả
lưu TIFF, không ghi RAW**. Các chỉnh sửa Capture One không được áp dụng khi mở
RAW trực tiếp. Muốn giữ màu/chỉnh sửa từ Capture One, xuất bộ TIFF 16-bit cùng ICC
trước khi ghép. GUI có thể ghép RAW gốc, nhưng không đọc chỉnh sửa Capture One.

```bash
python -m focus_stacker.cli /path/to/stack -o /path/to/result.tif --depth /path/to/depth.png
```

Hoặc truyền nhiều file: `python -m focus_stacker.cli a.tif b.tif -o result.tif`. Tên file được sắp xếp theo thứ tự từ điển, nên dùng `001`, `002`... `--sort time` dùng EXIF DateTimeOriginal/DateTime nếu tất cả file có thời gian đọc được; RAW có thể không có EXIF đọc được bằng Pillow. `--no-align` tắt căn chỉnh; `--radius 3` chỉnh sigma làm mượt năng lượng nét; `--smoothing 5` là kích thước cửa sổ median lẻ của depth map. `--quality 95` áp dụng cho JPG. PNG/TIFF xuất RGB 16-bit, JPG 8-bit; depth map là chỉ số ảnh chuẩn hóa, không phải khoảng cách vật lý.

Đặt output ngoài thư mục input để tránh đưa kết quả của lần chạy trước vào stack. CLI từ chối ghi đè ảnh nguồn nhưng có thể ghi đè output cũ. Mặc định ảnh phải cùng kích thước; có thể bật nội suy về kích thước ảnh đầu tiên. Nhận RGB, ảnh xám và alpha 8/16-bit; ảnh xám chuyển sang RGB, alpha bị bỏ và được ghi trong báo cáo. Đọc RAW dùng camera WB và tắt auto-brightening, xuất sRGB 16-bit; mức hỗ trợ CR3 và từng máy phụ thuộc LibRaw/rawpy. Dùng WB/exposure cố định trong quá trình chụp. EXIF orientation của ảnh thông thường được áp dụng.

**Màu:** các ảnh phải có ICC giống nhau (hoặc tất cả không có ICC). ICC RGB được giữ khi xuất TIFF; profile không phải RGB bị từ chối. RAW là phép phát triển cơ bản, không tương đương các chỉnh sửa Capture One. TIFF có báo cáo được đọc lại để xác minh pixel và ICC. Không chép toàn bộ EXIF sang output.

**Giới hạn:** M1 giữ toàn bộ ảnh đã căn chỉnh trong RAM, không có tile, GPU hay multiprocessing. ECC affine hiệu quả với dịch chuyển/rotation/scale vừa phải nhưng không sửa được parallax hoặc cảnh chuyển động; lỗi hội tụ sẽ dừng thay vì âm thầm xuất ảnh. Viền không hợp lệ được loại khỏi lựa chọn focus, song ở vùng chỉ có ảnh tham chiếu thì ảnh đó có thể bị mờ. Median depth và chọn pixel cứng có thể tạo seam/halo; kiểm tra 100% và thử tham số. Sắp xếp theo depth chụp liên tục có ý nghĩa khi dùng median depth.

## Bộ nạp ảnh từ notebook Image Loader

Tích hợp ý tưởng từ [notebook người dùng cung cấp](https://colab.research.google.com/drive/1Ns5Z7Ui3uLP7MrO9cx91YgPjTPrv7q0h): nạp song song nhưng giữ thứ tự nguồn, thêm BMP/WebP, chuẩn hóa 8/16-bit và tùy chọn đổi kích thước. Luồng mới: kiểm tra → nạp/chuẩn hóa → căn chỉnh → quét độ nét → ghép → ghi và xác minh TIFF.

GUI có **Luồng nạp ảnh** (mặc định 2; tối đa 8), **Cho phép đổi kích thước về ảnh đầu tiên** (mặc định tắt), và **Capture One: chỉ TIFF RGB 16-bit có ICC**. Với Capture One, xuất TIFF đã áp dụng chỉnh sửa trước và bật chế độ này. Kiểm tra định dạng/ICC không chứng minh được lịch sử chỉnh sửa của file.

CLI tương ứng: `--load-workers 2`, `--resize-mismatched`, `--rendered-only`. Báo cáo ghi dtype/kích thước gốc, các phép chuyển đổi và hash nguồn. Nội bộ luôn dùng RGB float32, giữ xử lý orientation TIFF và ICC của ứng dụng; không sao chép quy ước BGR của notebook. Không tự đổi kích thước nếu chưa bật tùy chọn. Nạp song song tăng bộ nhớ đệm giải mã; giảm còn 1 luồng nếu thiếu RAM. Chưa đo hiệu năng để khẳng định tăng tốc 3–5 lần. Đây là cải tiến nhập ảnh, không phải thuật toán stacking hay AI mới.
