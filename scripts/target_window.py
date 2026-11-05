"""A focused text box used to verify end-to-end insertion."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QPlainTextEdit

OUT = Path(__file__).resolve().parents[1] / "logs" / "target_text.txt"
OUT.parent.mkdir(exist_ok=True)


def main() -> int:
    app = QApplication(sys.argv)
    box = QPlainTextEdit()
    box.setWindowTitle("声入测试目标")
    box.resize(520, 300)
    box.move(320, 260)
    box.setWindowFlag(Qt.WindowStaysOnTopHint, True)
    box.show()
    box.raise_()
    box.activateWindow()
    box.setFocus()

    def dump() -> None:
        OUT.write_text(box.toPlainText(), encoding="utf-8")

    box.textChanged.connect(dump)
    QTimer.singleShot(300, lambda: (box.raise_(), box.activateWindow(), box.setFocus()))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
