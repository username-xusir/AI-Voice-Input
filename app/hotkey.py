"""Global hotkey hook for the local voice-input app.

Default hotkey is Ctrl+H: the hook swallows Ctrl+H and notifies the app.
Windows' native Win+H is left untouched. Shift+H and Win+H modes are kept for
compatibility/experimentation. Ctrl+Alt+H can optionally forward a synthetic
Win+H to Microsoft's voice typing.
"""

from __future__ import annotations

import ctypes
import logging
import threading
import time
from ctypes import wintypes
from typing import Callable

log = logging.getLogger("voxa.hotkey")

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_SHIFT = 0x10
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_MENU = 0x12
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_H = 0x48
VK_ESCAPE = 0x1B

KEYEVENTF_KEYUP = 0x0002

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int,
    HOOKPROC,
    wintypes.HINSTANCE,
    wintypes.DWORD,
]
user32.SetWindowsHookExW.restype = wintypes.HANDLE
user32.CallNextHookEx.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT,
]
user32.GetMessageW.restype = ctypes.c_int
user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM,
]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.keybd_event.argtypes = [
    wintypes.BYTE,
    wintypes.BYTE,
    wintypes.DWORD,
    ctypes.c_size_t,
]
user32.keybd_event.restype = None
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD


class HotkeyManager:
    """Installs a WH_KEYBOARD_LL hook in its own message-loop thread."""

    def __init__(
        self,
        on_hotkey: Callable[[], None],
        on_escape: Callable[[], None],
        on_native_fallback: Callable[[], None] | None = None,
        on_hotkey_release: Callable[[], None] | None = None,
        native_fallback_enabled: bool = True,
        hotkey: str = "ctrl+h",
    ) -> None:
        self.on_hotkey = on_hotkey
        self.on_hotkey_release = on_hotkey_release
        self.on_escape = on_escape
        self.on_native_fallback = on_native_fallback
        self.native_fallback_enabled = native_fallback_enabled
        mode = hotkey.lower()
        if mode.startswith("shift"):
            self.hotkey_mode = "shift+h"
        elif mode.startswith("ctrl"):
            self.hotkey_mode = "ctrl+h"
        else:
            self.hotkey_mode = "win+h"
        self._enabled = True

        self._esc_armed = False
        self._thread: threading.Thread | None = None
        self._thread_id: int = 0
        self._hook = None
        self._ready = threading.Event()
        self._error: BaseException | None = None
        self._proc_ref = HOOKPROC(self._proc)

        self._win_down = False
        self._shift_down = False
        self._ctrl_down = False
        self._alt_down = False
        self._hotkey_held = False
        self._suppress_h_up = False
        self._swallow_win_up = False
        self._bypass_until = 0.0

    # ---- public API -----------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, name="WinKeyHook", daemon=True)
        self._thread.start()
        if not self._ready.wait(4.0):
            raise RuntimeError("键盘钩子启动超时")
        if self._error:
            raise RuntimeError(f"键盘钩子安装失败: {self._error}")

    def stop(self) -> None:
        if self._thread_id:
            user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2.0)

    def set_escape_armed(self, armed: bool) -> None:
        self._esc_armed = armed

    def set_enabled(self, enabled: bool) -> None:
        """Pause the hotkey so Ctrl+H (or the configured combo) reaches the app."""
        self._enabled = enabled
        if not enabled:
            if self._hotkey_held:
                self._hotkey_held = False
                self._suppress_h_up = True
                self._safe_call(self.on_hotkey_release)
            else:
                self._hotkey_held = False
        log.info("热键已%s (%s)", "启用" if enabled else "暂停", self.hotkey_mode)

    # ---- hook thread ----------------------------------------------------
    def _run(self) -> None:
        self._thread_id = kernel32.GetCurrentThreadId()
        hmod = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc_ref, hmod, 0)
        if not self._hook:
            self._error = ctypes.WinError(ctypes.get_last_error())
            self._ready.set()
            return
        self._ready.set()
        log.info("键盘钩子已安装 (thread=%s, hotkey=%s)", self._thread_id, self.hotkey_mode)

        msg = wintypes.MSG()
        try:
            while True:
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret == 0 or ret == -1:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            if self._hook:
                user32.UnhookWindowsHookEx(self._hook)
                self._hook = None
            log.info("键盘钩子已卸载")

    def _call_next(self, n_code: int, w_param: int, l_param: int) -> int:
        return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

    def _proc(self, n_code: int, w_param: int, l_param: int) -> int:
        if n_code < 0:
            return self._call_next(n_code, w_param, l_param)
        try:
            if time.monotonic() < self._bypass_until:
                return self._call_next(n_code, w_param, l_param)

            kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = kb.vkCode
            is_down = w_param in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up = w_param in (WM_KEYUP, WM_SYSKEYUP)

            if vk in (VK_LWIN, VK_RWIN):
                if is_down:
                    self._win_down = True
                elif is_up:
                    self._win_down = False
                    self._swallow_win_up = False
                    if self._hotkey_held and self.hotkey_mode == "win+h":
                        self._hotkey_held = False
                        self._suppress_h_up = True
                        self._safe_call(self.on_hotkey_release)
                return self._call_next(n_code, w_param, l_param)

            if vk in (VK_SHIFT, VK_LSHIFT, VK_RSHIFT):
                if is_up and self._hotkey_held and self.hotkey_mode == "shift+h":
                    self._hotkey_held = False
                    self._suppress_h_up = True
                    self._safe_call(self.on_hotkey_release)
                self._shift_down = is_down
                return self._call_next(n_code, w_param, l_param)
            if vk in (VK_CONTROL, VK_LCONTROL, VK_RCONTROL):
                if is_up and self._hotkey_held and self.hotkey_mode == "ctrl+h":
                    self._hotkey_held = False
                    self._suppress_h_up = True
                    self._safe_call(self.on_hotkey_release)
                self._ctrl_down = is_down
                return self._call_next(n_code, w_param, l_param)
            if vk in (VK_MENU, VK_LMENU, VK_RMENU):
                self._alt_down = is_down
                return self._call_next(n_code, w_param, l_param)

            if vk == VK_H:
                # Keyboard auto-repeat while the combo is held must not leak
                # to the shell; otherwise Win+H long-press opens Microsoft's
                # native voice typing.
                if is_down and self._hotkey_held:
                    return 1
                if (
                    is_down
                    and self.hotkey_mode == "win+h"
                    and self._win_down
                    and self._enabled
                    and not (self._ctrl_down or self._alt_down or self._shift_down)
                ):
                    if not self._hotkey_held:
                        self._hotkey_held = True
                        self._suppress_h_up = True
                        self._swallow_win_up = True
                        self._tap_start_menu_guard()
                        self._safe_call(self.on_hotkey)
                    return 1
                if is_down and not self._hotkey_held and self._enabled:
                    if self.hotkey_mode == "shift+h":
                        if self._shift_down and not (
                            self._ctrl_down or self._alt_down or self._win_down
                        ):
                            self._hotkey_held = True
                            self._suppress_h_up = True
                            self._safe_call(self.on_hotkey)
                            return 1
                    elif self.hotkey_mode == "ctrl+h":
                        if self._ctrl_down and not (
                            self._shift_down or self._alt_down or self._win_down
                        ):
                            self._hotkey_held = True
                            self._suppress_h_up = True
                            self._safe_call(self.on_hotkey)
                            return 1
                    elif self._win_down and not (
                        self._ctrl_down or self._alt_down or self._shift_down
                    ):
                        self._hotkey_held = True
                        self._suppress_h_up = True
                        self._swallow_win_up = True
                        # Only used if the user explicitly configures win+h.
                        self._tap_start_menu_guard()
                        self._safe_call(self.on_hotkey)
                        return 1

                if (
                    is_down
                    and self._ctrl_down
                    and self._alt_down
                    and not self._win_down
                    and not self._shift_down
                ):
                    if self.native_fallback_enabled:
                        self._safe_call(self.on_native_fallback)
                        self._send_native_win_h()
                        return 1

                if is_up:
                    was_held = self._hotkey_held
                    suppress = self._suppress_h_up
                    self._hotkey_held = False
                    self._suppress_h_up = False
                    if was_held:
                        self._safe_call(self.on_hotkey_release)
                        return 1
                    if suppress:
                        return 1
                return self._call_next(n_code, w_param, l_param)

            if vk == VK_ESCAPE and is_down and self._esc_armed:
                self._safe_call(self.on_escape)
                return 1

        except Exception:
            log.exception("键盘钩子回调异常")
        return self._call_next(n_code, w_param, l_param)

    # ---- helpers --------------------------------------------------------
    @staticmethod
    def _tap_start_menu_guard() -> None:
        # Tapping a harmless modifier while Win is held tells the shell
        # "Win was used with another key", so releasing Win does not open the
        # Start menu.  F24 caused a visible full-screen flash on this Intel
        # iGPU; Ctrl does not and has no Win+Ctrl-only shell action.
        vk_ctrl = 0x11
        user32.keybd_event(vk_ctrl, 0, 0, 0)
        user32.keybd_event(vk_ctrl, 0, KEYEVENTF_KEYUP, 0)

    @staticmethod
    def _safe_call(fn: Callable[[], None] | None) -> None:
        if fn is None:
            return
        try:
            fn()
        except Exception:
            log.exception("热键回调异常")

    def _send_native_win_h(self) -> None:
        """Synthesize Win+H while bypassing our own hook."""
        self._bypass_until = time.monotonic() + 0.7
        user32.keybd_event(VK_LWIN, 0, 0, 0)
        user32.keybd_event(VK_H, 0, 0, 0)
        user32.keybd_event(VK_H, 0, KEYEVENTF_KEYUP, 0)
        user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
        log.info("已转发原生 Win+H（Ctrl+Alt+H）")
