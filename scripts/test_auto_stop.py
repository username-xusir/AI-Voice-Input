"""Test silence endpoint detection without a microphone."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtWidgets import QApplication  # noqa: E402

import main as app_main  # noqa: E402
from config import load_config  # noqa: E402


def main() -> int:
    app = QApplication([])
    cfg = load_config()
    cfg["auto_stop"] = True
    ui = app_main.VoxaApp(app, cfg)
    calls: list[float] = []
    ui._finish_and_close = lambda: calls.append(time.monotonic())  # type: ignore[method-assign]
    ui.state = "recording"
    ui.auto_stop_enabled = True

    # Speech for ~0.3s, then 1.9s of silence -> auto stop.
    ui.recorder._level = 0.5
    for _ in range(4):
        ui._on_tick()
        time.sleep(0.08)
    ui.recorder._level = 0.0
    time.sleep(1.9)
    ui._on_tick()
    ok_after_speech = len(calls) == 1

    # No speech at all -> no auto stop.
    calls.clear()
    ui._auto_voice_ticks = 0
    ui._auto_voice_started = 0.0
    ui._auto_last_voice = 0.0
    ui.recorder._level = 0.0
    time.sleep(1.9)
    ui._on_tick()
    ok_no_speech = len(calls) == 0

    print("auto stop after speech", "PASS" if ok_after_speech else "FAIL", calls)
    print("no speech no stop", "PASS" if ok_no_speech else "FAIL", calls)
    ui.pill.hide()
    ui.settings.hide()
    ui.tray.hide()
    app.quit()
    return 0 if ok_after_speech and ok_no_speech else 1


if __name__ == "__main__":
    raise SystemExit(main())
