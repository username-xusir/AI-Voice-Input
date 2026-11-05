"""Insert recognized text into the foreground application.

Default path is clipboard + Ctrl+V because it handles Chinese reliably in most
apps. A Unicode SendInput path is available as a fallback for apps where paste
is not supported.
"""

from __future__ import annotations

import ctypes
import logging
import struct
import time
from ctypes import wintypes

from PySide6.QtCore import QMimeData, QTimer
from PySide6.QtGui import QGuiApplication

log = logging.getLogger("voxa.injector")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

VK_CONTROL = 0x11
VK_BACK = 0x08
VK_V = 0x56
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
SW_RESTORE = 9
INPUT_KEYBOARD = 1

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ULONG_PTR),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUTUNION)]


user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
user32.SendInput.restype = wintypes.UINT
user32.keybd_event.argtypes = [
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.DWORD,
    ctypes.c_size_t,
]
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
user32.AttachThreadInput.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.BringWindowToTop.argtypes = [wintypes.HWND]
user32.BringWindowToTop.restype = wintypes.BOOL


def foreground_window() -> int:
    return int(user32.GetForegroundWindow() or 0)


def force_foreground(hwnd: int) -> None:
    if not hwnd:
        return
    current = user32.GetForegroundWindow()
    if current and int(current) == hwnd:
        return
    try:
        tid = int(kernel32.GetCurrentThreadId())
        tid_fg = int(user32.GetWindowThreadProcessId(current, None)) if current else 0
        attached = False
        if tid_fg and tid_fg != tid:
            attached = bool(user32.AttachThreadInput(tid, tid_fg, True))
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if attached:
            user32.AttachThreadInput(tid, tid_fg, False)
    except Exception:
        log.exception("切换前台窗口失败")


def _send_ctrl_v() -> None:
    user32.keybd_event(VK_CONTROL, 0, 0, 0)
    user32.keybd_event(VK_V, 0, 0, 0)
    user32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def _send_unicode(text: str) -> bool:
    data = text.encode("utf-16-le")
    units = [struct.unpack("<H", data[i : i + 2])[0] for i in range(0, len(data), 2)]
    inputs: list[INPUT] = []
    for unit in units:
        for flags in (KEYEVENTF_UNICODE, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP):
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.ki = KEYBDINPUT(0, unit, flags, 0, 0)
            inputs.append(inp)
    if not inputs:
        return True
    array = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), array, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        log.warning("SendInput 只发送了 %s/%s 个事件", sent, len(inputs))
        return False
    return True


def _send_backspace() -> None:
    user32.keybd_event(VK_BACK, 0, 0, 0)
    user32.keybd_event(VK_BACK, 0, KEYEVENTF_KEYUP, 0)


def text_delta(old: str, new: str) -> tuple[int, str]:
    """Return (backspaces, text) needed to turn `old` into `new`."""
    if old == new:
        return 0, ""
    limit = min(len(old), len(new))
    i = 0
    while i < limit and old[i] == new[i]:
        i += 1
    return len(old) - i, new[i:]


def _ensure_target(target_hwnd: int, allow_activate: bool = True) -> bool:
    if not target_hwnd:
        return True
    current = foreground_window()
    if current == target_hwnd:
        return True
    if not allow_activate:
        log.info("目标窗口不在前台 (target=%s current=%s)，本次不输入", target_hwnd, current)
        return False
    force_foreground(target_hwnd)
    time.sleep(0.03)
    current = foreground_window()
    if current != target_hwnd:
        log.warning("目标窗口不在前台 (target=%s current=%s)，取消输入", target_hwnd, current)
        return False
    return True


def send_text_edit(
    old: str,
    new: str,
    target_hwnd: int = 0,
    allow_activate: bool = False,
) -> bool:
    """Incrementally turn the text we typed (`old`) into `new`.

    Used for live preview: only backspaces the changed suffix and types the
    new suffix, so already-committed words stay in the target input box.
    By default it will not steal focus from another app.
    """
    delete_count, insert = text_delta(old, new)
    if not delete_count and not insert:
        return True
    if not _ensure_target(target_hwnd, allow_activate):
        return False
    if delete_count:
        for _ in range(delete_count):
            _send_backspace()
            time.sleep(0.001)
    if insert and not _send_unicode(insert):
        return False
    log.info("实时输入: 退格 %s，新增 %s 字", delete_count, len(insert))
    return True


def delete_chars(count: int, target_hwnd: int = 0) -> bool:
    if count <= 0:
        return True
    if not _ensure_target(target_hwnd):
        return False
    for _ in range(count):
        _send_backspace()
        time.sleep(0.001)
    log.info("已退格 %s 字", count)
    return True


def _snapshot_clipboard() -> QMimeData | None:
    try:
        source = QGuiApplication.clipboard().mimeData()
        if source is None:
            return None
        clone = QMimeData()
        for fmt in source.formats():
            clone.setData(fmt, source.data(fmt))
        return clone
    except Exception:
        log.exception("读取剪贴板失败")
        return None


def _restore_clipboard(later: QMimeData | None, expected_text: str, delay_ms: int = 800) -> None:
    if later is None:
        return

    def restore() -> None:
        try:
            clipboard = QGuiApplication.clipboard()
            if clipboard.text() == expected_text:
                clipboard.setMimeData(later)
        except Exception:
            log.exception("恢复剪贴板失败")

    QTimer.singleShot(delay_ms, restore)


def copy_text(text: str) -> None:
    if not text:
        return
    QGuiApplication.clipboard().setText(text)
    log.info("已复制 %s 字到剪贴板", len(text))


def insert_text(
    text: str,
    target_hwnd: int = 0,
    mode: str = "paste",
    restore_clipboard: bool = True,
) -> bool:
    if not text:
        return False

    force_foreground(target_hwnd)
    time.sleep(0.04)

    if mode == "type":
        _send_unicode(text)
        log.info("已用 Unicode 方式输入 %s 字", len(text))
        return True

    clipboard = QGuiApplication.clipboard()
    previous = _snapshot_clipboard() if restore_clipboard else None
    try:
        clipboard.setText(text)
    except Exception:
        log.exception("写入剪贴板失败，改用 Unicode 输入")
        _send_unicode(text)
        return True

    time.sleep(0.03)
    _send_ctrl_v()
    if restore_clipboard:
        _restore_clipboard(previous, text)
    log.info("已用粘贴方式输入 %s 字", len(text))
    return True
