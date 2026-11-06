"""Render the pill and settings card to tests/ui_*.png."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from ui import PillWindow, QuickSettingsPanel, SettingsPanel, make_icon, set_theme  # noqa: E402


def main() -> None:
    app = QApplication([])
    out = ROOT / "tests"
    out.mkdir(exist_ok=True)
    set_theme("teal")

    pill = PillWindow()
    pill.show_pill()
    cases = [
        ("recording", "正在聆听…", 3.2, "ui_pill_recording.png"),
        ("recording", "你好，这是一个语音输入测试，今天天气不错。", 7.8, "ui_pill_preview.png"),
        ("paused", "你好，这是一个语音输入测试。", 12.0, "ui_pill_paused.png"),
        ("finishing", "正在生成文字…", 15.0, "ui_pill_finishing.png"),
        ("error", "没有检测到声音", 0.0, "ui_pill_error.png"),
    ]
    for state, text, seconds, name in cases:
        if state == "recording" and text == "正在聆听…":
            pill.set_text("")
        else:
            pill.set_text(text)
        pill.set_state(state, text if state in ("finishing", "error") else None)
        pill.set_timer(seconds)
        pill.set_level(0.42 if state == "recording" else 0.0)
        app.processEvents()
        path = out / name
        pill.grab().save(str(path))
        print("saved", path)

    for theme in ("teal", "light", "dark"):
        set_theme(theme)
        pill.apply_theme()
        settings = SettingsPanel()
        settings.set_values(
            True,
            True,
            False,
            "zh",
            auto_punctuation=True,
            theme=theme,
            auto_stop=True,
            silence_ms=1800,
            device="CPU",
            autostart=True,
        )
        settings.show()
        quick = QuickSettingsPanel()
        quick.set_values(True, True, True, True, theme)
        quick.show()
        pill.set_state("recording")
        pill.set_level(0.42)
        app.processEvents()
        path = out / f"ui_settings_{theme}.png"
        settings.grab().save(str(path))
        print("saved", path)
        quick.grab().save(str(out / f"ui_quick_{theme}.png"))
        pill.grab().save(str(out / f"ui_pill_{theme}.png"))
        pill.set_state("ready", "这是最终识别结果，浮窗保持打开。")
        app.processEvents()
        pill.grab().save(str(out / f"ui_pill_result_{theme}.png"))
        settings.hide()
        quick.hide()
        settings.deleteLater()
        quick.deleteLater()

    set_theme("teal")
    icon_path = out / "tray_icon.png"
    make_icon().pixmap(64, 64).save(str(icon_path))
    print("saved", icon_path)

    pill.hide()


if __name__ == "__main__":
    main()
