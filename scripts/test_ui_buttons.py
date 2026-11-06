"""Click/drag tests for the pill and the full settings card."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui import PillWindow, QuickSettingsPanel, SettingsPanel, set_theme  # noqa: E402


def main() -> int:
    app = QApplication([])
    set_theme("teal")
    pill = PillWindow()
    pill.show()
    app.processEvents()

    events = {"mic": 0, "settings": 0, "close": 0}
    pill.mic_clicked.connect(lambda: events.__setitem__("mic", events["mic"] + 1))
    pill.settings_clicked.connect(lambda: events.__setitem__("settings", events["settings"] + 1))
    pill.close_clicked.connect(lambda: events.__setitem__("close", events["close"] + 1))

    QTest.mouseClick(pill.mic, Qt.LeftButton)
    QTest.mouseClick(pill.settings_btn, Qt.LeftButton)
    QTest.mouseClick(pill.close_btn, Qt.LeftButton)
    app.processEvents()
    print("pill clicks", events)

    before = pill.pos()
    start = QPoint(pill.width() // 2, pill.height() // 2)
    end = start + QPoint(100, 35)
    QTest.mousePress(pill, Qt.LeftButton, pos=start)
    QTest.mouseMove(pill, end)
    QTest.mouseRelease(pill, Qt.LeftButton, pos=end)
    app.processEvents()
    moved = pill.pos() != before
    print("drag moved", moved, before, "->", pill.pos())

    settings = SettingsPanel()
    settings.set_values(
        True,
        True,
        True,
        "zh",
        auto_punctuation=True,
        theme="teal",
        auto_stop=True,
        silence_ms=1800,
        device="CPU",
        autostart=True,
    )
    settings.show()
    app.processEvents()
    live_values = []
    high_values = []
    languages = []
    punct_values = []
    themes = []
    silences = []
    auto_stops = []
    settings.live_preview_toggled.connect(live_values.append)
    settings.high_accuracy_toggled.connect(high_values.append)
    settings.language_selected.connect(languages.append)
    settings.auto_punctuation_toggled.connect(punct_values.append)
    settings.theme_selected.connect(themes.append)
    settings.silence_changed.connect(silences.append)
    settings.auto_stop_toggled.connect(auto_stops.append)

    QTest.mouseClick(settings.live_switch, Qt.LeftButton)
    QTest.mouseClick(settings.high_switch, Qt.LeftButton)
    QTest.mouseClick(settings.lang_buttons["en"], Qt.LeftButton)
    QTest.mouseClick(settings.auto_punct_switch, Qt.LeftButton)
    QTest.mouseClick(settings.theme_buttons["light"], Qt.LeftButton)
    settings.silence_slider.setValue(2600)
    QTest.qWait(320)
    QTest.mouseClick(settings.auto_stop_switch, Qt.LeftButton)
    app.processEvents()
    print(
        "live", live_values,
        "high", high_values,
        "langs", languages,
        "punct", punct_values,
        "themes", themes,
        "silence", silences,
        "autostop", auto_stops,
    )

    quick = QuickSettingsPanel()
    quick.set_values(True, True, True, True, "teal")
    quick.show()
    app.processEvents()
    quick_punct = []
    quick_themes = []
    quick_auto_stop = []
    quick.auto_punctuation_toggled.connect(quick_punct.append)
    quick.theme_selected.connect(quick_themes.append)
    quick.auto_stop_toggled.connect(quick_auto_stop.append)
    QTest.mouseClick(quick.auto_punct_switch, Qt.LeftButton)
    QTest.mouseClick(quick.theme_buttons["dark"], Qt.LeftButton)
    QTest.mouseClick(quick.auto_stop_switch, Qt.LeftButton)
    app.processEvents()
    print("quick", quick_punct, quick_themes, quick_auto_stop)

    ok = (
        events == {"mic": 1, "settings": 1, "close": 1}
        and moved
        and live_values == [False]
        and high_values == [False]
        and languages == ["en"]
        and punct_values == [False]
        and themes == ["light"]
        and silences == [2600]
        and auto_stops == [False]
        and settings.silence_slider.isEnabled() is False
        and quick_punct == [False]
        and quick_themes == ["dark"]
        and quick_auto_stop == [False]
    )
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
