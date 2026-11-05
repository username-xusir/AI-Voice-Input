"""Drive the new UI/state machine without external keyboard/mouse input.

Run with VOICEIN_TEST_WAV pointing at tests/fixtures/zh_test.wav.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from config import load_config, setup_logging  # noqa: E402
import main as app_main  # noqa: E402


def main() -> int:
    setup_logging()
    # Do not send real keystrokes during the automated flow test.
    app_main.send_text_edit = lambda *args, **kwargs: True  # type: ignore[assignment]
    from main import VoxaApp  # noqa: E402

    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    config = load_config()
    config["live_preview"] = True
    config["language"] = "zh"
    config["high_accuracy"] = False
    app_ui = VoxaApp(app, config)

    print("loading models...", flush=True)
    app_ui.engine.load()
    app_ui.state = "ready"
    app_ui.tray.set_status("就绪 · 测试")
    print("models ready", flush=True)

    QTimer.singleShot(300, app_ui._start_session)

    def snap_recording() -> None:
        app_ui.pill.grab().save(str(ROOT / "tests" / "app_pill_recording.png"))
        print("snap recording", app_ui.state, repr(app_ui.preview_text), flush=True)

    def pause() -> None:
        app_ui._on_mic_clicked()
        app_ui.pill.grab().save(str(ROOT / "tests" / "app_pill_paused.png"))
        print("paused", app_ui.state, flush=True)

    def resume() -> None:
        app_ui._on_mic_clicked()
        print("resumed", app_ui.state, flush=True)

    def open_settings() -> None:
        app_ui._on_settings_clicked()
        app_ui.settings.grab().save(str(ROOT / "tests" / "app_settings_live.png"))
        print("settings open", app_ui.settings_visible, app_ui.settings.isVisible(), flush=True)

    def toggle_preview() -> None:
        app_ui._on_settings_back()
        print("settings closed", flush=True)

    def finish() -> None:
        app_ui.pill.grab().save(str(ROOT / "tests" / "app_pill_before_finish.png"))
        app_ui._finish_and_close()
        print("finish requested", app_ui.state, flush=True)
        app_ui.pill.grab().save(str(ROOT / "tests" / "app_pill_finishing.png"))

    QTimer.singleShot(3600, snap_recording)
    QTimer.singleShot(4000, pause)
    QTimer.singleShot(4800, resume)
    QTimer.singleShot(5400, open_settings)
    QTimer.singleShot(6200, toggle_preview)
    QTimer.singleShot(6800, finish)
    QTimer.singleShot(55000, app.quit)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
