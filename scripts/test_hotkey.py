"""Verify push-to-talk Ctrl+H (press/release) and Win+H passthrough."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from hotkey import (  # noqa: E402
    KEYEVENTF_KEYUP,
    VK_H,
    VK_LCONTROL,
    VK_LWIN,
    HotkeyManager,
    user32,
)

downs = 0
ups = 0


def press_ctrl_h() -> None:
    user32.keybd_event(VK_LCONTROL, 0, 0, 0)
    user32.keybd_event(VK_H, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(VK_H, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LCONTROL, 0, KEYEVENTF_KEYUP, 0)


def press_ctrl_h_release_ctrl_first() -> None:
    user32.keybd_event(VK_LCONTROL, 0, 0, 0)
    user32.keybd_event(VK_H, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(VK_LCONTROL, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.03)
    user32.keybd_event(VK_H, 0, KEYEVENTF_KEYUP, 0)


def press_win_h() -> None:
    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(VK_H, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(VK_H, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)


def main() -> int:
    global downs, ups

    def on_down() -> None:
        global downs
        downs += 1
        print(f"DOWN #{downs}", flush=True)

    def on_up() -> None:
        global ups
        ups += 1
        print(f"UP #{ups}", flush=True)

    mgr = HotkeyManager(
        on_hotkey=on_down,
        on_hotkey_release=on_up,
        on_escape=lambda: print("ESC", flush=True),
        hotkey="ctrl+h",
    )
    mgr.start()
    time.sleep(0.3)

    press_ctrl_h()
    time.sleep(0.4)
    press_ctrl_h()
    time.sleep(0.4)
    press_ctrl_h_release_ctrl_first()
    time.sleep(0.5)
    print("after 3 presses: down=", downs, "up=", ups)

    before = (downs, ups)
    press_win_h()
    time.sleep(0.8)
    print("win+h delta:", downs - before[0], ups - before[1])
    user32.keybd_event(0x1B, 0, 0, 0)
    user32.keybd_event(0x1B, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.3)

    mgr.set_enabled(False)
    before = (downs, ups)
    press_ctrl_h()
    time.sleep(0.4)
    paused_delta = (downs - before[0], ups - before[1])
    mgr.set_enabled(True)
    print("paused delta:", paused_delta)

    mgr.stop()

    win_down = 0
    win_up = 0

    def on_win_down() -> None:
        nonlocal win_down
        win_down += 1
        print(f"WIN DOWN #{win_down}", flush=True)

    def on_win_up() -> None:
        nonlocal win_up
        win_up += 1
        print(f"WIN UP #{win_up}", flush=True)

    mgr_win = HotkeyManager(
        on_hotkey=on_win_down,
        on_hotkey_release=on_win_up,
        on_escape=lambda: None,
        hotkey="win+h",
    )
    mgr_win.start()
    time.sleep(0.3)
    press_win_h()
    time.sleep(0.8)
    mgr_win.stop()
    print("win+h mode down/up:", win_down, win_up)

    ok = (
        downs == 3
        and ups == 3
        and paused_delta == (0, 0)
        and win_down == 1
        and win_up == 1
    )
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
