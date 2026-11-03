"""Small native macOS launcher for trying the M1 command-line pipeline."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from focus_stacker.core.io.images import discover
from focus_stacker.core.pipeline import run


def apple(script: str, *args: str) -> str:
    return subprocess.check_output(["osascript", "-e", script, *args], text=True).strip()


def dialog(message: str) -> None:
    script = 'on run argv\ndisplay dialog (item 1 of argv) buttons {"OK"} default button "OK"\nend run'
    subprocess.run(["osascript", "-e", script, message], check=False)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        folder = apple('POSIX path of (choose folder with prompt "Chọn thư mục chứa ảnh focus stack")')
        paths = discover([folder])
        output = Path(folder).resolve().parent / (Path(folder).resolve().name + "-stack.tif")
        if output.exists():
            raise ValueError(f"File kết quả đã tồn tại: {output}. Hãy đổi tên file đó trước khi chạy lại.")
        subprocess.run(["osascript", "-e", 'display notification "Đang ghép ảnh; vui lòng chờ thông báo hoàn tất." with title "FocusStack M1"'], check=False)
        run(paths, output)
        subprocess.run(["open", "-R", str(output)], check=False)
        dialog(f"Đã ghép {len(paths)} ảnh. File kết quả:\n{output}\n\nFinder đã chọn file để bạn mở xem.")
        return 0
    except subprocess.CalledProcessError:
        return 1
    except Exception as exc:
        logging.exception("Stack failed")
        dialog(f"Không thể ghép ảnh: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
