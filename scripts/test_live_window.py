"""End-to-end: live preview must type into a real focused text box.

Run with VOICEIN_TEST_WAV pointing at the 8-second Chinese fixture.
This opens a real window and sends real Unicode keystrokes to it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import Qt, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QTextEdit  # noqa: E402

import main as app_main  # noqa: E402
from config import load_config, setup_logging  # noqa: E402
from injector import force_foreground, foreground_window  # noqa: E402


def main() -> int:
    setup_logging()
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)

    target = QTextEdit()
    target.setWindowTitle("声入实时输入测试")
    target.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    target.resize(520, 180)
    target.show()
    target.raise_()
    target.activateWindow()
    target.setFocus()
    app.processEvents()
    target_hwnd = int(target.winId())
    force_foreground(target_hwnd)
    app.processEvents()
    print("target hwnd", target_hwnd, "foreground", foreground_window(), flush=True)

    config = load_config()
    config["high_accuracy"] = False
    config["live_preview"] = True
    config["language"] = "zh"
    ui = app_main.VoxaApp(app, config)
    focus_timer = QTimer()
    focus_timer.setInterval(100)
    focus_timer.timeout.connect(
        lambda: force_foreground(target_hwnd) if ui.state in ("recording", "finishing") else None
    )

    print("loading models...", flush=True)
    ui.engine.load()
    ui.state = "ready"
    ui.tray.set_status("就绪 · 测试")
    print("models ready", flush=True)

    def start() -> None:
        target.raise_()
        target.activateWindow()
        target.setFocus()
        force_foreground(target_hwnd)
        app.processEvents()
        ui._start_session()
        focus_timer.start()
        print("started, target", ui.target_hwnd, flush=True)

    def finish() -> None:
        print("finishing, field before:", repr(target.toPlainText()), flush=True)
        ui._finish_and_close()

    def report() -> None:
        focus_timer.stop()
        text = target.toPlainText()
        expected = "你好,这是一个语音输入测试。今天天气不错,我们开始工作吧。"
        print("field after:", repr(text), flush=True)
        ok = expected.replace(",", "，") in text or expected in text
        if not ok:
            # Final model may choose full-width punctuation.
            ok = "语音输入测试" in text and "今天天气不错" in text
        print("PASS" if ok else "FAIL", flush=True)
        ui.pill.hide()
        ui.settings.hide()
        ui.tray.hide()
        target.close()
        app.exit(0 if ok else 1)

    QTimer.singleShot(600, start)
    QTimer.singleShot(7200, finish)
    QTimer.singleShot(22000, report)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
