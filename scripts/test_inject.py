"""Verify clipboard-paste and Unicode-typing text insertion into a Qt window."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QPlainTextEdit  # noqa: E402

from injector import insert_text  # noqa: E402

TEXT = "声入测试 hello 123"


def run_case(mode: str) -> str:
    app = QApplication.instance() or QApplication([])
    w = QPlainTextEdit()
    w.resize(420, 160)
    w.show()
    w.activateWindow()
    w.setFocus()
    app.processEvents()
    time.sleep(0.25)
    hwnd = int(w.winId())
    insert_text(TEXT, target_hwnd=hwnd, mode=mode, restore_clipboard=True)
    app.processEvents()
    time.sleep(0.35)
    result = w.toPlainText()
    w.close()
    app.processEvents()
    return result


def main() -> int:
    app = QApplication([])
    results = {}
    for mode in ("paste", "type"):
        results[mode] = run_case(mode)
        print(mode, "->", repr(results[mode]))
    ok = all(TEXT in value for value in results.values())
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
