"""Sửa encoding của console trên Windows.

Trên console Windows mặc định (chưa bật UTF-8), encoding của sys.stdout/
sys.stderr thường là cp1252, không biểu diễn được tiếng Việt có dấu. Khi đó
print() các thông báo tiến trình/lỗi tiếng Việt sẽ raise UnicodeEncodeError,
khiến script thoát với mã lỗi dù công việc thật đã hoàn thành thành công.

Module này KHÔNG phụ thuộc biến môi trường (vd. PYTHONUTF8) — người dùng
không cần nhớ set gì cả, script tự sửa encoding của chính nó khi chạy.
"""


def fix_console_encoding(stream):
    """Chuyển `stream` sang UTF-8, ký tự không hiển thị được thì thay thế
    thay vì raise.

    An toàn khi `stream` không có `reconfigure` (vd. đã bị thay bằng object
    capture của pytest) — khi đó bỏ qua, không làm gì cả.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    reconfigure(encoding="utf-8", errors="replace")


def fix_stdio_encoding():
    """Áp dụng fix_console_encoding cho cả sys.stdout và sys.stderr."""
    import sys

    fix_console_encoding(sys.stdout)
    fix_console_encoding(sys.stderr)
