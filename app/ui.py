"""Voxa UI: compact voice pill, live waveform, and a full settings card."""

from __future__ import annotations

import math
import re
import time
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSlider,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

PALETTES = {
    "teal": {
        "pill1": "#0097A7",
        "pill2": "#008B9A",
        "pill_border": "rgba(255,255,255,26)",
        "accent": "#00BCD4",
        "dark": "#00535C",
        "ink": "#00353B",
        "text": "#001F24",
        "muted": "#025A63",
        "divider": "#038491",
        "white": "#F7FDFF",
        "card1": "#0097A7",
        "card2": "#008B9A",
        "card_border": "rgba(255,255,255,20)",
        "shadow": 9,
        "mic1": "#00BCD0",
        "mic2": "#008E9E",
        "glyph": "#00535C",
        "label": "#00353B",
        "label_muted": "#025A63",
        "button1": "#00C2D4",
        "button2": "#00A2B2",
        "button_text": "#00474F",
        "close1": "#016C78",
        "close2": "#0097A7",
        "close_glyph": "#00353B",
        "hover": "rgba(255,255,255,26)",
        "switch_on": "#00BCD4",
        "switch_off": "#007E8C",
        "knob": "#F7FDFF",
        "segment_bg": "rgba(0,188,212,55)",
        "segment_border": "rgba(255,255,255,45)",
        "segment_text": "#00353B",
        "segment_checked": "#F7FDFF",
        "segment_checked_text": "#006A75",
        "groove": "rgba(3,132,145,180)",
        "slider_fill": "#F7FDFF",
        "slider_handle": "#F7FDFF",
        "footer": "rgba(0,53,59,145)",
        "error": "#7B1C1C",
    },
    "light": {
        "pill1": "#FFFFFF",
        "pill2": "#EEF1F3",
        "pill_border": "rgba(24,28,32,32)",
        "accent": "#8C9298",
        "dark": "#1D2023",
        "ink": "#1D2023",
        "text": "#1B1E21",
        "muted": "#72787E",
        "divider": "#DDE1E5",
        "white": "#FFFFFF",
        "card1": "#FFFFFF",
        "card2": "#F3F5F6",
        "card_border": "rgba(24,28,32,30)",
        "shadow": 13,
        "mic1": "#F7F8F9",
        "mic2": "#DBDFE3",
        "glyph": "#1F2326",
        "label": "#232629",
        "label_muted": "#71777D",
        "button1": "#F6F7F8",
        "button2": "#E6E9EC",
        "button_text": "#2A2D30",
        "close1": "#F6F7F8",
        "close2": "#E2E6E9",
        "close_glyph": "#1F2326",
        "hover": "rgba(24,28,32,18)",
        "switch_on": "#777D83",
        "switch_off": "#C9CED3",
        "knob": "#FFFFFF",
        "segment_bg": "#F1F3F5",
        "segment_border": "rgba(24,28,32,24)",
        "segment_text": "#4A5056",
        "segment_checked": "#D6DADF",
        "segment_checked_text": "#1F2326",
        "groove": "#DDE1E5",
        "slider_fill": "#8A9096",
        "slider_handle": "#FFFFFF",
        "footer": "#858B91",
        "error": "#9B2C2C",
    },
    "dark": {
        "pill1": "#2E3134",
        "pill2": "#222528",
        "pill_border": "rgba(255,255,255,24)",
        "accent": "#A9AFB5",
        "dark": "#F2F3F4",
        "ink": "#F2F3F4",
        "text": "#F4F4F5",
        "muted": "#A6ABB0",
        "divider": "#3D4145",
        "white": "#FFFFFF",
        "card1": "#2C2F32",
        "card2": "#212427",
        "card_border": "rgba(255,255,255,18)",
        "shadow": 34,
        "mic1": "#4B5055",
        "mic2": "#34383C",
        "glyph": "#F3F4F5",
        "label": "#ECEDEF",
        "label_muted": "#A5AAB0",
        "button1": "#3A3E42",
        "button2": "#313539",
        "button_text": "#ECEDEF",
        "close1": "#3A3E42",
        "close2": "#2B2E31",
        "close_glyph": "#F3F4F5",
        "hover": "rgba(255,255,255,20)",
        "switch_on": "#6E747A",
        "switch_off": "#3A3E42",
        "knob": "#F2F3F4",
        "segment_bg": "#313539",
        "segment_border": "rgba(255,255,255,16)",
        "segment_text": "#B8BDC2",
        "segment_checked": "#555B61",
        "segment_checked_text": "#FFFFFF",
        "groove": "#3A3E42",
        "slider_fill": "#A9AFB5",
        "slider_handle": "#F2F3F4",
        "footer": "#7F858A",
        "error": "#FF9E9E",
    },
}

THEME = dict(PALETTES["teal"])
THEME_NAME = "teal"
VOXA_VERSION = "0.7.1"

MARGIN = 4
PILL_MARGIN_X = 6
PILL_MARGIN_TOP = 11
PILL_MARGIN_BOTTOM = 9
PILL_W = 217
PILL_H = 33
CARD_W = 342
CARD_H = 596


def set_theme(name: str) -> str:
    """Switch the module palette used by every custom-painted widget."""
    global THEME, THEME_NAME
    key = name if name in PALETTES else "teal"
    THEME = dict(PALETTES[key])
    THEME_NAME = key
    return key


_RGBA = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)",
    re.IGNORECASE,
)


def c(key: str) -> QColor:
    """Return a QColor for a palette entry, including CSS rgba() strings.

    QColor('rgba(...)') is invalid in Qt and silently paints black; the
    close-button hover used to hit exactly that bug.
    """
    value = THEME[key]
    if isinstance(value, QColor):
        return QColor(value)
    text = str(value).strip()
    match = _RGBA.fullmatch(text)
    if match:
        rgb = [int(match.group(i)) for i in (1, 2, 3)]
        alpha_text = match.group(4)
        if alpha_text is None:
            alpha = 255
        else:
            alpha_value = float(alpha_text)
            alpha = round(alpha_value * 255) if alpha_value <= 1 else round(alpha_value)
        return QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, alpha)))
    return QColor(text)


def _mic_glyph(
    p: QPainter,
    cx: float,
    cy: float,
    color: QColor,
    scale: float = 1.0,
    filled: bool = True,
) -> None:
    """Small microphone: capsule + U-shaped cradle + stem."""
    capsule = QRectF(
        cx - 4.0 * scale,
        cy - 10.0 * scale,
        8.0 * scale,
        15.0 * scale,
    )
    if filled:
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(capsule, 4.0 * scale, 4.0 * scale)
    else:
        p.setPen(QPen(color, 2.0 * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(capsule, 4.0 * scale, 4.0 * scale)
    pen = QPen(color, 2.0 * scale, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    path = QPainterPath()
    path.moveTo(cx - 7.0 * scale, cy - 2.0 * scale)
    path.quadTo(cx - 7.0 * scale, cy + 5.0 * scale, cx, cy + 5.0 * scale)
    path.quadTo(cx + 7.0 * scale, cy + 5.0 * scale, cx + 7.0 * scale, cy - 2.0 * scale)
    p.drawPath(path)
    p.drawLine(QPointF(cx, cy + 5.0 * scale), QPointF(cx, cy + 9.0 * scale))
    p.drawLine(QPointF(cx - 3.0 * scale, cy + 9.0 * scale), QPointF(cx + 3.0 * scale, cy + 9.0 * scale))


class MicButton(QAbstractButton):
    """Mic icon at rest; a live, level-driven waveform while recording."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(29, 29)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.mode = "idle"
        self._phase = 0.0
        self._hover = False
        self._level = 0.0
        self._display = 0.0
        self._history: deque[float] = deque([0.0] * 5, maxlen=5)
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._tick)

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        if mode in ("recording", "loading", "finishing"):
            self._timer.start()
        else:
            self._timer.stop()
            self._level = 0.0
            self._display = 0.0
            self._history = deque([0.0] * 5, maxlen=5)
            self._phase = 0.0
        self.update()

    def set_level(self, level: float) -> None:
        value = max(0.0, min(1.0, float(level)))
        # Make normal speech visible without clipping loud syllables.
        value = min(1.0, value * 1.7)
        self._level = value
        if self.mode == "recording":
            self._history.append(value)
        self.update()

    def _tick(self) -> None:
        self._phase = (self._phase + 0.22) % (2 * math.pi)
        self._display += (self._level - self._display) * 0.35
        self.update()

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, 28, 28)
        gradient = QRadialGradient(QPointF(9, 8), 28)
        gradient.setColorAt(0.0, c("mic1"))
        gradient.setColorAt(1.0, c("mic2"))
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.setBrush(gradient)
        p.drawEllipse(rect)
        if self._hover and self.isEnabled():
            p.setPen(Qt.NoPen)
            p.setBrush(c("hover"))
            p.drawEllipse(rect.adjusted(1, 1, -1, -1))

        cx, cy = rect.center().x(), rect.center().y()
        glyph = c("glyph")
        if self.mode == "paused":
            p.setPen(Qt.NoPen)
            p.setBrush(glyph)
            path = QPainterPath()
            path.moveTo(cx - 3.2, cy - 6.4)
            path.lineTo(cx + 6.2, cy)
            path.lineTo(cx - 3.2, cy + 6.4)
            path.closeSubpath()
            p.drawPath(path)
        elif self.mode in ("loading", "finishing"):
            pen = QPen(glyph, 2.0, Qt.SolidLine, Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawArc(rect.adjusted(8, 8, -8, -8), int(self._phase * 57.3) % 5760, 120 * 16)
        elif self.mode == "recording" and self.isEnabled():
            p.setPen(Qt.NoPen)
            p.setBrush(glyph)
            shape = (0.48, 0.78, 1.0, 0.78, 0.48)
            heights = []
            for i, sample in enumerate(self._history):
                wave = 0.72 + 0.28 * abs(math.sin(self._phase * 1.7 + i * 1.2))
                energy = max(sample, self._display * 0.55)
                heights.append((5.8 + energy * 9.6) * shape[i] * wave)
            for i, height in enumerate(heights):
                x = cx - 8.0 + i * 4.0
                h = max(2.1, min(13.0, height))
                p.drawRoundedRect(QRectF(x - 1.15, cy - h / 2, 2.3, h), 1.15, 1.15)
        else:
            color = QColor(glyph)
            if not self.isEnabled() or self.mode == "disabled":
                color.setAlpha(105)
            _mic_glyph(p, cx, cy, color, 0.76, filled=False)


class Switch(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(44, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._hover = False

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        track = QRectF(0, 0, 44, 24)
        if not self.isEnabled():
            color = QColor(THEME["switch_off"])
            color.setAlpha(105)
        elif self.isChecked():
            color = c("switch_on")
            if self._hover:
                color = color.lighter(112)
        else:
            color = c("switch_off")
            if self._hover:
                color = color.lighter(118)
        p.setPen(QPen(QColor(0, 0, 0, 24), 0.8))
        p.setBrush(color)
        p.drawRoundedRect(track.adjusted(0.4, 0.4, -0.4, -0.4), 12, 12)

        knob = 19.0
        x = 44 - knob - 2.5 if self.isChecked() else 2.5
        y = (24 - knob) / 2
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 35))
        p.drawEllipse(QRectF(x + 0.6, y + 1.0, knob, knob))
        p.setBrush(c("knob"))
        p.drawEllipse(QRectF(x, y, knob, knob))


class SettingsButton(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(47, 23)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._hover = False

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, 46, 22)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, c("button1"))
        gradient.setColorAt(1.0, c("button2"))
        p.setPen(QPen(c("segment_border"), 0.8))
        p.setBrush(gradient)
        p.drawRoundedRect(rect, 11, 11)
        p.setFont(QFont("Microsoft YaHei UI", 8))
        p.setPen(c("button_text"))
        p.drawText(rect, Qt.AlignCenter, "设置")


class CloseButton(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._hover = False

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0.5, 0.5, 27, 27)
        gradient = QRadialGradient(QPointF(14, 14), 16)
        gradient.setColorAt(0.0, c("close1"))
        gradient.setColorAt(1.0, c("close2"))
        p.setPen(QPen(c("pill_border"), 0.8))
        p.setBrush(gradient)
        p.drawEllipse(rect)
        if self._hover:
            p.setPen(Qt.NoPen)
            p.setBrush(c("hover"))
            p.drawEllipse(rect)
        p.setPen(QPen(c("close_glyph"), 1.55, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(9.6, 9.6), QPointF(18.4, 18.4))
        p.drawLine(QPointF(9.6, 18.4), QPointF(18.4, 9.6))


class BackButton(QAbstractButton):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self._hover = False

    def enterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        if self._hover:
            p.setPen(Qt.NoPen)
            p.setBrush(c("hover"))
            p.drawEllipse(QRectF(0, 0, 28, 28))
        p.setPen(QPen(c("label"), 1.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawLine(QPointF(16.4, 9.2), QPointF(9.4, 16.2))
        p.drawLine(QPointF(9.4, 16.2), QPointF(16.4, 23.2))


class PillWindow(QWidget):
    mic_clicked = Signal()
    close_clicked = Signal()
    settings_clicked = Signal()

    def __init__(self, hotkey_label: str = "Win+H") -> None:
        super().__init__()
        self.hotkey_label = hotkey_label
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(
            PILL_W + PILL_MARGIN_X * 2,
            PILL_MARGIN_TOP + PILL_H + PILL_MARGIN_BOTTOM,
        )

        self._state = "idle"
        self._full_text = ""
        self._timer_text = "0:00"
        self._dragging = False
        self._drag_offset = None
        self._has_position = False

        left = PILL_MARGIN_X
        top = PILL_MARGIN_TOP
        self.mic = MicButton(self)
        self.mic.setGeometry(left + 2, top + 2, 29, 29)
        self.mic.clicked.connect(lambda: self.mic_clicked.emit())

        self.text_label = QLabel(self)
        self.text_label.setGeometry(left + 37, top + 4, 68, 25)
        self.text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.text_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.text_label.setFont(QFont("Microsoft YaHei UI", 8))

        self.timer_label = QLabel("0:00", self)
        self.timer_label.setGeometry(left + 112, top + 7, 23, 18)
        self.timer_label.setAlignment(Qt.AlignCenter)
        self.timer_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.timer_label.setFont(QFont("Consolas", 7))

        self.settings_btn = SettingsButton(self)
        self.settings_btn.setGeometry(left + 138, top + 5, 47, 23)
        self.settings_btn.clicked.connect(lambda: self.settings_clicked.emit())

        self.close_btn = CloseButton(self)
        self.close_btn.setGeometry(left + 186, top + 2, 28, 28)
        self.close_btn.clicked.connect(lambda: self.close_clicked.emit())
        self.apply_theme()

    def apply_theme(self) -> None:
        self.text_label.setStyleSheet(
            f'color: {THEME["text"]}; font-family: "Microsoft YaHei UI"; '
            "font-size: 8pt; background: transparent;"
        )
        self.timer_label.setStyleSheet(
            f'color: {THEME["muted"]}; font-family: Consolas; '
            "font-size: 7pt; background: transparent;"
        )
        for widget in (self.mic, self.settings_btn, self.close_btn):
            widget.update()
        self.update()

    # ---- state ----------------------------------------------------------
    @property
    def state(self) -> str:
        return self._state

    def set_state(self, state: str, text: str | None = None) -> None:
        self._state = state
        if text is not None:
            self._full_text = text
        if state == "recording":
            self.mic.set_mode("recording")
        elif state == "paused":
            self.mic.set_mode("paused")
        elif state in ("loading", "finishing"):
            self.mic.set_mode("loading")
        else:
            self.mic.set_mode("disabled")
        self._refresh_text()
        self.update()

    def set_text(self, text: str) -> None:
        self._full_text = text
        self._refresh_text()

    def set_timer(self, seconds: float) -> None:
        total = max(0, int(seconds))
        self._timer_text = f"{total // 60}:{total % 60:02d}"
        self.timer_label.setText(self._timer_text)

    def set_mic_enabled(self, enabled: bool) -> None:
        self.mic.setEnabled(enabled)

    def set_level(self, level: float) -> None:
        self.mic.set_level(level)

    def _refresh_text(self) -> None:
        if self._state == "loading":
            display = "正在唤醒…"
        elif self._state == "finishing":
            display = "正在生成…"
        elif self._state == "error":
            display = self._full_text or "出错了"
        elif self._full_text:
            display = self._full_text
        elif self._state == "paused":
            display = "已暂停 · 点击继续"
        elif self._state == "recording":
            display = "正在聆听…"
        else:
            display = f"按 {self.hotkey_label} 说话"
        metrics = QFontMetrics(self.text_label.font())
        elided = metrics.elidedText(display, Qt.ElideLeft, self.text_label.width() - 2)
        self.text_label.setText(elided)
        self.setToolTip(self._full_text or display)

    # ---- geometry / dragging -------------------------------------------
    def show_pill(self) -> None:
        if not self._has_position:
            screen = QGuiApplication.screenAt(QGuiApplication.primaryScreen().geometry().center())
            screen = screen or QGuiApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                self.move(geo.center().x() - self.width() // 2, geo.bottom() - self.height() - 30)
                self._has_position = True
        self.show()
        self.raise_()

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        if self.isVisible():
            self._has_position = True

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None or child in (self.text_label, self.timer_label):
                self._dragging = True
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # ---- painting ------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        content = QRectF(PILL_MARGIN_X, PILL_MARGIN_TOP, PILL_W, PILL_H)

        for i in (4, 3, 2, 1):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, int(THEME["shadow"])))
            p.drawRoundedRect(content.adjusted(-i, -i + 2, i, i + 2), 16 + i, 16 + i)

        gradient = QLinearGradient(content.topLeft(), content.bottomLeft())
        gradient.setColorAt(0.0, c("pill1"))
        gradient.setColorAt(1.0, c("pill2"))
        p.setBrush(gradient)
        p.setPen(QPen(c("pill_border"), 0.8))
        p.drawRoundedRect(content, 16.5, 16.5)

        p.setPen(QPen(c("divider"), 1))
        p.drawLine(
            QPointF(content.left() + 108.5, content.top() + 2.5),
            QPointF(content.left() + 108.5, content.bottom() - 2.5),
        )


class SettingsPanel(QWidget):
    back_clicked = Signal()
    live_preview_toggled = Signal(bool)
    auto_paste_toggled = Signal(bool)
    high_accuracy_toggled = Signal(bool)
    language_selected = Signal(str)
    auto_punctuation_toggled = Signal(bool)
    auto_stop_toggled = Signal(bool)
    silence_changed = Signal(int)
    device_selected = Signal(str)
    theme_selected = Signal(str)
    autostart_toggled = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setFixedSize(CARD_W + MARGIN * 2, CARD_H + MARGIN * 2)
        self._dragging = False
        self._drag_offset = None
        self._silence_timer = QTimer(self)
        self._silence_timer.setSingleShot(True)
        self._silence_timer.setInterval(220)
        self._silence_timer.timeout.connect(self._emit_silence)
        self._gpu_available = False
        self._current_device = "CPU"
        self._build()
        self.apply_theme()

    # ---- construction ---------------------------------------------------
    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(MARGIN + 18, MARGIN + 14, MARGIN + 18, MARGIN + 14)
        root.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(8)
        brand_box = QVBoxLayout()
        brand_box.setSpacing(0)
        self.brand_label = QLabel("VOXA")
        self.brand_label.setObjectName("brand")
        self.brand_sub = QLabel(f"详细设置 · 本地语音输入 · v{VOXA_VERSION}")
        self.brand_sub.setObjectName("brandSub")
        brand_box.addWidget(self.brand_label)
        brand_box.addWidget(self.brand_sub)
        header.addLayout(brand_box)
        header.addStretch(1)
        self.back_btn = BackButton(self)
        self.back_btn.clicked.connect(lambda: self.back_clicked.emit())
        header.addWidget(self.back_btn, 0, Qt.AlignTop)
        root.addLayout(header)
        root.addSpacing(2)

        root.addWidget(self._section("输入"))
        self.auto_punct_switch = Switch(self)
        self.auto_punct_switch.toggled.connect(self.auto_punctuation_toggled.emit)
        root.addWidget(self._row("自动标点", "让识别结果带逗号、句号", self.auto_punct_switch))

        self.live_switch = Switch(self)
        self.live_switch.toggled.connect(self.live_preview_toggled.emit)
        root.addWidget(self._row("实时预览", "边说边输入到当前输入框", self.live_switch))

        self.auto_switch = Switch(self)
        self.auto_switch.toggled.connect(self.auto_paste_toggled.emit)
        root.addWidget(self._row("自动上屏", "结束后用最终结果校正文字", self.auto_switch))

        root.addWidget(self._separator())
        root.addWidget(self._section("识别"))
        self.high_switch = Switch(self)
        self.high_switch.toggled.connect(self.high_accuracy_toggled.emit)
        self.high_label = QLabel("高精度模型")
        self.high_label.setObjectName("rowLabel")
        self.high_hint = QLabel("OpenAI large-v3-turbo · 更慢")
        self.high_hint.setObjectName("rowHint")
        high_text = QVBoxLayout()
        high_text.setSpacing(0)
        high_text.addWidget(self.high_label)
        high_text.addWidget(self.high_hint)
        high_row = QWidget()
        high_layout = QHBoxLayout(high_row)
        high_layout.setContentsMargins(0, 0, 0, 0)
        high_layout.addLayout(high_text)
        high_layout.addStretch(1)
        high_layout.addWidget(self.high_switch)
        root.addWidget(high_row)

        self.device_group = QButtonGroup(self)
        self.device_group.setExclusive(True)
        self.device_buttons: dict[str, QPushButton] = {}
        for key, text in (("CPU", "CPU"), ("GPU", "GPU")):
            btn = self._segment(text, checkable=True)
            btn.clicked.connect(lambda checked=False, k=key: self._choose_device(k))
            self.device_group.addButton(btn)
            self.device_buttons[key] = btn
        root.addWidget(self._seg_row("计算设备", self.device_buttons, "CPU", "GPU"))

        self.language_group = QButtonGroup(self)
        self.language_group.setExclusive(True)
        self.lang_buttons: dict[str, QPushButton] = {}
        for key, text in (("zh", "中文"), ("en", "EN"), ("auto", "自动")):
            btn = self._segment(text, checkable=True)
            btn.clicked.connect(lambda checked=False, k=key: self._choose_language(k))
            self.language_group.addButton(btn)
            self.lang_buttons[key] = btn
        root.addWidget(self._seg_row("识别语言", self.lang_buttons, "中文", "EN", "自动"))

        root.addWidget(self._separator())
        root.addWidget(self._section("结束"))
        self.auto_stop_switch = Switch(self)
        self.auto_stop_switch.toggled.connect(self._on_auto_stop_toggled)
        root.addWidget(self._row("停止说话自动结束", "不需要再按确认键", self.auto_stop_switch))

        silence_box = QWidget()
        silence_layout = QVBoxLayout(silence_box)
        silence_layout.setContentsMargins(0, 0, 0, 2)
        silence_layout.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(6)
        self.silence_title = QLabel("静音判定")
        self.silence_title.setObjectName("rowLabel")
        self.silence_value = QLabel("1.8 秒")
        self.silence_value.setObjectName("value")
        top.addWidget(self.silence_title)
        top.addStretch(1)
        top.addWidget(self.silence_value)
        silence_layout.addLayout(top)
        self.silence_slider = QSlider(Qt.Horizontal)
        self.silence_slider.setRange(800, 4000)
        self.silence_slider.setSingleStep(100)
        self.silence_slider.setPageStep(200)
        self.silence_slider.setTickInterval(400)
        self.silence_slider.setFixedHeight(22)
        self.silence_slider.valueChanged.connect(self._on_silence_value)
        silence_layout.addWidget(self.silence_slider)
        root.addWidget(silence_box)

        root.addWidget(self._separator())
        root.addWidget(self._section("外观"))
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_buttons: dict[str, QPushButton] = {}
        for key, text in (("teal", "青色"), ("light", "浅色"), ("dark", "深色")):
            btn = self._segment(text, checkable=True)
            btn.clicked.connect(lambda checked=False, k=key: self._choose_theme(k))
            self.theme_group.addButton(btn)
            self.theme_buttons[key] = btn
        root.addWidget(self._seg_row("主题", self.theme_buttons, "青色", "浅色", "深色"))

        self.autostart_switch = Switch(self)
        self.autostart_switch.toggled.connect(self.autostart_toggled.emit)
        root.addWidget(self._row("开机自启动", "登录后静默运行在托盘", self.autostart_switch))

        root.addStretch(1)
        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.footer_label = QLabel("设置自动保存")
        self.footer_label.setObjectName("footer")
        footer.addWidget(self.footer_label)
        footer.addStretch(1)
        self.done_btn = QPushButton("完成")
        self.done_btn.setObjectName("done")
        self.done_btn.setCursor(Qt.PointingHandCursor)
        self.done_btn.setFocusPolicy(Qt.NoFocus)
        self.done_btn.setFixedSize(68, 28)
        self.done_btn.clicked.connect(lambda: self.back_clicked.emit())
        footer.addWidget(self.done_btn)
        root.addLayout(footer)

    def _section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def _separator(self) -> QWidget:
        line = QWidget()
        line.setObjectName("separator")
        line.setFixedHeight(1)
        return line

    def _segment(self, text: str, checkable: bool = False) -> QPushButton:
        btn = QPushButton(text)
        btn.setObjectName("segment")
        btn.setCheckable(checkable)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setFixedHeight(25)
        return btn

    def _row(self, title: str, hint: str, switch: Switch) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        text = QVBoxLayout()
        text.setSpacing(0)
        title_label = QLabel(title)
        title_label.setObjectName("rowLabel")
        hint_label = QLabel(hint)
        hint_label.setObjectName("rowHint")
        text.addWidget(title_label)
        text.addWidget(hint_label)
        layout.addLayout(text)
        layout.addStretch(1)
        layout.addWidget(switch)
        return row

    def _seg_row(
        self,
        title: str,
        buttons: dict[str, QPushButton],
        *labels: str,
    ) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(5)
        title_label = QLabel(title)
        title_label.setObjectName("rowLabel")
        layout.addWidget(title_label)
        layout.addStretch(1)
        for key, label in zip(buttons.keys(), labels):
            buttons[key].setText(label)
            layout.addWidget(buttons[key])
        return row

    # ---- state ----------------------------------------------------------
    def _choose_language(self, key: str) -> None:
        self.lang_buttons[key].setChecked(True)
        self.language_selected.emit(key)

    def _choose_device(self, key: str) -> None:
        if key == "GPU" and not self._gpu_available:
            self.device_buttons[self._current_device].setChecked(True)
            return
        self.device_buttons[key].setChecked(True)
        self.device_selected.emit(key)

    def _choose_theme(self, key: str) -> None:
        self.theme_buttons[key].setChecked(True)
        self.theme_selected.emit(key)

    def _on_auto_stop_toggled(self, enabled: bool) -> None:
        self.silence_slider.setEnabled(enabled)
        self.auto_stop_toggled.emit(enabled)

    def _on_silence_value(self, value: int) -> None:
        self.silence_value.setText(f"{value / 1000:.1f} 秒")
        self._silence_timer.start()

    def _emit_silence(self) -> None:
        self.silence_changed.emit(int(self.silence_slider.value()))

    def set_high_available(self, available: bool) -> None:
        self.high_switch.setEnabled(available)
        self.high_hint.setText(
            "OpenAI large-v3-turbo · 更慢" if available else "未安装 large 模型"
        )
        self.high_hint.setToolTip(
            "更准，但更慢"
            if available
            else "安装时未选择 OpenAI large-v3-turbo 模型；需要性能强劲的电脑"
        )
        if not available:
            self.high_switch.blockSignals(True)
            self.high_switch.setChecked(False)
            self.high_switch.blockSignals(False)

    def set_gpu_available(self, available: bool) -> None:
        self._gpu_available = available
        gpu = self.device_buttons.get("GPU")
        if gpu is not None:
            gpu.setEnabled(available)
            gpu.setToolTip(
                "使用 OpenVINO GPU。核显可能比 CPU 更慢。"
                if available
                else "未检测到 OpenVINO GPU 设备"
            )

    def set_values(
        self,
        live_preview: bool,
        auto_paste: bool,
        high_accuracy: bool,
        language: str,
        auto_punctuation: bool = True,
        theme: str = "teal",
        auto_stop: bool = True,
        silence_ms: int = 1800,
        device: str = "CPU",
        autostart: bool = True,
    ) -> None:
        for switch, value in (
            (self.live_switch, live_preview),
            (self.auto_switch, auto_paste),
            (self.high_switch, high_accuracy and self.high_switch.isEnabled()),
            (self.auto_punct_switch, auto_punctuation),
            (self.auto_stop_switch, auto_stop),
            (self.autostart_switch, autostart),
        ):
            switch.blockSignals(True)
            switch.setChecked(value)
            switch.blockSignals(False)
        self.silence_slider.blockSignals(True)
        self.silence_slider.setValue(max(800, min(4000, int(silence_ms))))
        self.silence_slider.blockSignals(False)
        self.silence_value.setText(f"{self.silence_slider.value() / 1000:.1f} 秒")
        self.silence_slider.setEnabled(auto_stop)

        key = language if language in self.lang_buttons else "zh"
        for k, btn in self.lang_buttons.items():
            btn.setChecked(k == key)
        self._current_device = device if device in self.device_buttons else "CPU"
        for k, btn in self.device_buttons.items():
            btn.setChecked(k == self._current_device)
        theme_key = theme if theme in self.theme_buttons else "teal"
        for k, btn in self.theme_buttons.items():
            btn.setChecked(k == theme_key)

    # ---- theme / placement ---------------------------------------------
    def apply_theme(self) -> None:
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {THEME["label"]};
                background: transparent;
                font-family: "Microsoft YaHei UI";
                font-size: 9pt;
            }}
            QLabel#brand {{
                color: {THEME["text"]};
                font-family: "Segoe UI Semibold", "Microsoft YaHei UI";
                font-size: 19pt;
                font-weight: 700;
                letter-spacing: 2px;
            }}
            QLabel#brandSub {{
                color: {THEME["label_muted"]};
                font-size: 7.5pt;
            }}
            QLabel#sectionLabel {{
                color: {THEME["label_muted"]};
                font-size: 7.5pt;
                font-weight: 700;
                letter-spacing: 1px;
                padding-top: 1px;
            }}
            QLabel#rowLabel {{
                color: {THEME["label"]};
                font-size: 9pt;
            }}
            QLabel#rowHint {{
                color: {THEME["label_muted"]};
                font-size: 7pt;
            }}
            QLabel#value {{
                color: {THEME["text"]};
                font-family: "Consolas", "Microsoft YaHei UI";
                font-size: 9pt;
                font-weight: 600;
            }}
            QLabel#footer {{
                color: {THEME["footer"]};
                font-size: 7pt;
            }}
            QWidget#separator {{
                background: {THEME["divider"]};
                min-height: 1px;
                max-height: 1px;
                margin-top: 2px;
                margin-bottom: 2px;
            }}
            QPushButton#segment {{
                color: {THEME["segment_text"]};
                background: {THEME["segment_bg"]};
                border: 1px solid {THEME["segment_border"]};
                border-radius: 7px;
                font-family: "Microsoft YaHei UI";
                font-size: 7.5pt;
                padding: 0 10px;
            }}
            QPushButton#segment:hover {{
                border: 1px solid {THEME["accent"]};
            }}
            QPushButton#segment:checked {{
                color: {THEME["segment_checked_text"]};
                background: {THEME["segment_checked"]};
                border: 1px solid {THEME["segment_checked"]};
            }}
            QPushButton#segment:disabled {{
                color: {THEME["footer"]};
                background: transparent;
            }}
            QPushButton#done {{
                color: {THEME["segment_checked_text"]};
                background: {THEME["segment_checked"]};
                border: none;
                border-radius: 9px;
                font-family: "Microsoft YaHei UI";
                font-size: 8.5pt;
                font-weight: 600;
            }}
            QPushButton#done:hover {{
                background: {THEME["accent"]};
            }}
            QSlider::groove:horizontal {{
                height: 4px;
                background: {THEME["groove"]};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                height: 4px;
                background: {THEME["slider_fill"]};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
                background: {THEME["slider_handle"]};
                border: 2px solid {THEME["accent"]};
            }}
            QSlider::handle:horizontal:disabled {{
                background: {THEME["switch_off"]};
                border: 2px solid {THEME["switch_off"]};
            }}
            QSlider::groove:horizontal:disabled {{
                background: {THEME["divider"]};
            }}
            """
        )
        for widget in (
            self.back_btn,
            self.auto_punct_switch,
            self.live_switch,
            self.auto_switch,
            self.high_switch,
            self.auto_stop_switch,
            self.autostart_switch,
            self.silence_slider,
        ):
            widget.update()
        self.update()

    def show_near(self, pill_rect) -> None:
        screen = QGuiApplication.screenAt(pill_rect.center()) or QGuiApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = pill_rect.right() + 8
            if x + self.width() > geo.right() - 8:
                x = pill_rect.left() - self.width() - 8
            y = pill_rect.top()
            if y + self.height() > geo.bottom() - 8:
                y = geo.bottom() - self.height() - 8
            y = max(geo.top() + 8, min(y, geo.bottom() - self.height() - 8))
            x = max(geo.left() + 8, min(x, geo.right() - self.width() - 8))
            self.move(x, y)
        self.show()
        self.raise_()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            child = self.childAt(event.position().toPoint())
            if child is None or isinstance(child, QLabel):
                self._dragging = True
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._dragging and self._drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        self._dragging = False
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        card = QRectF(MARGIN, MARGIN, CARD_W, CARD_H)

        for i in (5, 4, 3, 2, 1):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, int(THEME["shadow"])))
            p.drawRoundedRect(card.adjusted(-i, -i + 3, i, i + 3), 12 + i, 12 + i)

        gradient = QLinearGradient(card.topLeft(), card.bottomLeft())
        gradient.setColorAt(0.0, c("card1"))
        gradient.setColorAt(1.0, c("card2"))
        p.setBrush(gradient)
        p.setPen(QPen(c("card_border"), 0.8))
        p.drawRoundedRect(card, 14, 14)


def make_icon(color: str = "#F7FDFF", accent: str = "#0097A7") -> QIcon:
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(accent))
    p.drawRoundedRect(QRectF(2, 2, 60, 60), 16, 16)
    _mic_glyph(p, 32, 30, QColor(color), 1.55)
    p.end()
    return QIcon(pm)


class TrayIcon(QSystemTrayIcon):
    def __init__(
        self,
        parent: QWidget | None,
        on_quit,
        on_open_logs,
        on_show=None,
        on_settings=None,
        on_toggle_hotkey=None,
        on_toggle_autostart=None,
        autostart_enabled: bool = False,
        on_toggle_auto_stop=None,
        auto_stop_enabled: bool = True,
        hotkey_label: str = "Win+H",
        on_activate=None,
    ) -> None:
        super().__init__(make_icon(), parent)
        self.hotkey_label = hotkey_label
        self.setToolTip(f"Voxa · {hotkey_label} 语音输入")
        menu = QMenu()
        self.status_action = menu.addAction("正在加载模型…")
        self.status_action.setEnabled(False)
        menu.addSeparator()
        if on_show:
            show_action = menu.addAction("显示浮窗")
            show_action.triggered.connect(on_show)
        if on_settings:
            settings_action = menu.addAction("打开设置")
            settings_action.triggered.connect(on_settings)
        self.autostart_action = menu.addAction("开机自启动")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(autostart_enabled)
        if on_toggle_autostart:
            self.autostart_action.toggled.connect(on_toggle_autostart)
        self.auto_stop_action = menu.addAction("停止说话自动结束")
        self.auto_stop_action.setCheckable(True)
        self.auto_stop_action.setChecked(auto_stop_enabled)
        if on_toggle_auto_stop:
            self.auto_stop_action.toggled.connect(on_toggle_auto_stop)
        self.hotkey_action = menu.addAction("暂停热键（恢复应用快捷键）")
        self.hotkey_action.setCheckable(True)
        if on_toggle_hotkey:
            self.hotkey_action.toggled.connect(on_toggle_hotkey)
        logs = menu.addAction("打开日志文件夹")
        logs.triggered.connect(on_open_logs)
        quit_action = menu.addAction("退出 Voxa")
        quit_action.triggered.connect(on_quit)
        self.setContextMenu(menu)
        self._menu = menu
        self._on_activate = on_activate
        self._last_activate = 0.0
        if on_activate:
            self.activated.connect(self._activated)

    def _activated(self, reason) -> None:
        if reason != QSystemTrayIcon.Trigger:
            return
        now = time.monotonic()
        if now - self._last_activate < 0.45:
            return
        self._last_activate = now
        self._on_activate()

    def set_status(self, text: str) -> None:
        self.status_action.setText(text)
        self.setToolTip(f"Voxa · {text}")

    def set_autostart_checked(self, checked: bool) -> None:
        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(checked)
        self.autostart_action.blockSignals(False)

    def set_auto_stop_checked(self, checked: bool) -> None:
        self.auto_stop_action.blockSignals(True)
        self.auto_stop_action.setChecked(checked)
        self.auto_stop_action.blockSignals(False)
