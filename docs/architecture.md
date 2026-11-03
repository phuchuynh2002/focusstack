# Cấu trúc dự án

Áp dụng sơ đồ `my_focus_stacker/` trong thư mục dự án hiện có; không tạo một bản sao mã nguồn lồng bên trong.

```text
<project>/
├── pyproject.toml
├── FocusStack.spec
├── desktop_entry.py
├── assets/
│   ├── README.md
│   └── theme.qss
├── src/
│   ├── focus_stacker/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── cli.py
│   │   ├── mac_test.py
│   │   ├── core/
│   │   │   ├── align/ecc.py
│   │   │   ├── focus/measure.py
│   │   │   ├── fusion/depth.py
│   │   │   ├── io/{images,formats}.py
│   │   │   ├── pipeline.py
│   │   │   ├── task.py
│   │   │   └── workflow.py
│   │   ├── workers/
│   │   │   ├── preview.py
│   │   │   └── process.py
│   │   ├── ui/
│   │   │   ├── main_window.py
│   │   │   └── canvas.py
│   │   └── utils/
│   │       ├── settings.py
│   │       ├── cache.py
│   │       ├── logging.py
│   │       ├── assets.py
│   │       └── resources.py
│   └── focusstack/          # lớp tương thích import/lệnh cũ
└── tests/
```

- `main.py`: tạo QApplication, xử lý các FileOpen events macOS, nạp QSettings/theme/logging, mở MainWindow. `--worker` chuyển sang CLI mà không tạo cửa sổ.
- `core`: xử lý ảnh và cấu hình StackTask/RenderSettings, độc lập với PySide6. Các thuật toán hiện có: ECC affine, năng lượng Laplacian, depth-map fusion. Không thay đổi hành vi RAW/TIFF của bản 0.3.0 trong lần refactor này.
- `workers/preview.py`: QRunnable giải mã preview, gửi QImage về UI bằng signal. `workers/process.py`: QProcess chạy pipeline trong tiến trình riêng để hủy được; chủ động giữ mô hình này thay vì đổi stack thành QThread.
- `ui/main_window.py`: thư viện ảnh, lựa chọn, tham số, điều phối worker, hiển thị tiến độ và kết quả. `ui/canvas.py`: zoom/pan/xem ảnh; không chứa thuật toán ghép.
- `utils/settings.py`: QSettings lưu/khôi phục hình học cửa sổ. Tham số ghép vẫn lấy trực tiếp từ UI như trước; không tự khôi phục một bộ tham số cũ.
- `utils/cache.py`: thư mục tạm riêng cho mỗi tác vụ, chỉ xóa cache của tác vụ đó.
- `utils/logging.py`: CLI log ra console; desktop ghi log worker theo vòng xoay tối đa 2 MiB/file, giữ 3 bản cũ trong AppLocalDataLocation/logs.
- `utils/assets.py`: tìm theme ở source, wheel (`share/focusstack/assets`) hoặc PyInstaller (`assets`). Theme hiện không đổi giao diện native.

Pyramid fusion, Brush/retouch, icon tùy biến và splash screen chưa được triển khai. Không có module rỗng giả làm thuật toán hoàn chỉnh.

## Lệnh chạy

```sh
python -m pip install -e ".[test,desktop]"
python -m focus_stacker.main
python -m focus_stacker.cli --help
python -m pytest -q
python -m PyInstaller --noconfirm FocusStack.spec
```

Các lệnh `focusstack`, `focusstack-app`, `focus-stacker`, `python -m focusstack.cli` và `python -m focusstack.ui.app` vẫn được giữ tương thích. Bundle ID vẫn là `local.focusstack.desktop` để không tạo ứng dụng khác trong Capture One.

## Kết quả kiểm chứng — 2026-11-03

- 49 test không dùng GUI đạt, gồm pipeline/RAW/ICC và tương thích CLI/import cũ.
- 6 kịch bản GUI trong bundle PyInstaller đạt, gồm preview, FileOpen, chọn nhiều ảnh, ghép/hủy/xuất, RAW tự động/thủ công và QSettings.
- Kiểm thử GUI trực tiếp từ virtualenv bị Qt abort khi khởi tạo QApplication; chưa sửa lỗi môi trường này. Bài thử QSettings đã được điều chỉnh kích thước để nằm trong màn hình offscreen, tránh việc Qt tự thu cửa sổ khi restore.
- Wheel đã build và kiểm tra có package chính, lớp tương thích và theme.
- Bản macOS tại `dist/layout/FocusStack.app` vượt kiểm tra chữ ký ad-hoc và khởi động smoke test. Không thay thế bản đang cài trong `/Applications` trong lượt refactor này.
- AST của các module thuật toán/IO được đối chiếu với bản trước refactor: chỉ thay vị trí import; không đổi nội dung xử lý.
