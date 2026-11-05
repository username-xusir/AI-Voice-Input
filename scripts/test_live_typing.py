"""Verify the live-typing bridge without sending real keystrokes."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtWidgets import QApplication  # noqa: E402

import main as app_main  # noqa: E402
from config import load_config  # noqa: E402
from injector import text_delta  # noqa: E402


def main() -> int:
    cases = [
        ("", "你好", (0, "你好")),
        ("你好", "你好世界", (0, "世界")),
        ("你好世界", "你好，世界", (2, "，世界")),
        ("你好，世界", "你好，世界", (0, "")),
        ("abc", "ab", (1, "")),
        ("你好", "", (2, "")),
    ]
    ok_delta = all(text_delta(a, b) == want for a, b, want in cases)
    print("text_delta", "PASS" if ok_delta else "FAIL")

    app = QApplication([])
    calls: list[tuple[str, str, int]] = []

    def fake_edit(old: str, new: str, target_hwnd: int = 0, allow_activate: bool = False) -> bool:
        calls.append((old, new, target_hwnd))
        return True

    app_main.send_text_edit = fake_edit  # type: ignore[assignment]
    app_main.foreground_window = lambda: 4242  # type: ignore[assignment]
    ui = app_main.VoxaApp(app, load_config())
    ui.state = "recording"
    ui.session_id = 7
    ui.live_preview_enabled = True
    ui.settings_visible = False
    ui.target_hwnd = 4242

    ui._on_preview_text("你好", 7)
    ui._on_preview_text("你好世界", 7)
    ui._on_preview_text("你好，世界", 7)
    ui._on_preview_text("你好，世界", 7)

    expected = [
        ("", "你好", 4242),
        ("你好", "你好世界", 4242),
        ("你好世界", "你好，世界", 4242),
    ]
    ok_live = calls == expected
    print("live calls", calls)
    print("live typing", "PASS" if ok_live else "FAIL")

    stopped: list[str] = []
    ui._finish_and_close = lambda: stopped.append(ui.state)  # type: ignore[method-assign]
    ui.state = "recording"
    ui._handle_event("hotkey")
    ui.state = "paused"
    ui._handle_event("hotkey")
    ok_toggle = stopped == ["recording", "paused"]
    print("Ctrl+H stop", stopped, "PASS" if ok_toggle else "FAIL")

    ui.state = "finishing"
    ui.finish_id = 1
    ui.live_typed_text = "你好，世界"
    ui.auto_paste = True
    ui._on_final_text("你好，世界。", 1)
    ok_final = calls[-1] == ("你好，世界", "你好，世界。", 4242)
    print("final call", calls[-1])
    print("final correction", "PASS" if ok_final else "FAIL")

    ui.pill.hide()
    ui.settings.hide()
    ui.tray.hide()
    app.quit()
    return 0 if ok_delta and ok_live and ok_toggle and ok_final else 1


if __name__ == "__main__":
    raise SystemExit(main())
