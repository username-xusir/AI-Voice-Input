"""Verify the three palettes are independent and icon contrast is correct."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from PySide6.QtGui import QColor  # noqa: E402

from ui import PALETTES, c, set_theme  # noqa: E402


def hex_colors(palette: dict) -> list[QColor]:
    colors = []
    for key, value in palette.items():
        # Error text is intentionally red in every palette.
        if key == "error":
            continue
        if isinstance(value, str) and value.startswith("#"):
            colors.append(QColor(value))
    return colors


def main() -> int:
    ok = True
    for theme in ("light", "dark"):
        saturated = []
        for color in hex_colors(PALETTES[theme]):
            if max(color.red(), color.green(), color.blue()) - min(
                color.red(), color.green(), color.blue()
            ) > 12:
                saturated.append(color.name())
        print(theme, "saturated colors:", saturated)
        if saturated:
            ok = False

    for theme, want_dark_icon in (("teal", True), ("light", True), ("dark", False)):
        glyph = QColor(PALETTES[theme]["glyph"])
        close = QColor(PALETTES[theme]["close_glyph"])
        glyph_luma = 0.2126 * glyph.red() + 0.7152 * glyph.green() + 0.0722 * glyph.blue()
        close_luma = 0.2126 * close.red() + 0.7152 * close.green() + 0.0722 * close.blue()
        print(theme, "glyph", glyph.name(), round(glyph_luma), "close", close.name(), round(close_luma))
        if want_dark_icon and (glyph_luma > 100 or close_luma > 100):
            ok = False
        if not want_dark_icon and (glyph_luma < 150 or close_luma < 150):
            ok = False

    # CSS rgba() must be parsed with alpha; an opaque black hover was the
    # "X button turns black" bug.
    for theme in ("teal", "light", "dark"):
        set_theme(theme)
        hover = c("hover")
        print(theme, "hover", hover.name(), hover.alpha())
        if not hover.isValid() or hover.alpha() >= 100:
            print(theme, "hover is invalid/opaque")
            ok = False

    # The teal palette must remain the original cyan/teal family.
    teal = PALETTES["teal"]
    if teal["pill1"].lower() != "#0097a7" or teal["accent"].lower() != "#00bcd4":
        print("teal palette changed unexpectedly")
        ok = False

    set_theme("teal")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
