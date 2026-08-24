from scripts import console


class _NoReconfigure:
    """Giả lập stream không có reconfigure (vd. pytest capture object)."""


class _FakeReconfigurable:
    """Giả lập stream có reconfigure, ghi lại tham số được gọi."""

    def __init__(self):
        self.calls = []

    def reconfigure(self, **kwargs):
        self.calls.append(kwargs)


def test_fix_console_encoding_ignores_stream_without_reconfigure():
    """Không được raise khi stream (vd. capture object của pytest) thiếu
    reconfigure."""
    stream = _NoReconfigure()

    console.fix_console_encoding(stream)  # không raise là đủ


def test_fix_console_encoding_applies_utf8_with_replace_errors():
    stream = _FakeReconfigurable()

    console.fix_console_encoding(stream)

    assert stream.calls == [{"encoding": "utf-8", "errors": "replace"}]
