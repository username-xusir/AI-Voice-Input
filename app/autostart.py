"""Windows login autostart via HKCU\\...\\Run (no admin required)."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("voxa.autostart")

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "Voxa"
LEGACY_VALUE_NAME = "VoiceIn"


def _remove_legacy() -> None:
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, LEGACY_VALUE_NAME)
    except FileNotFoundError:
        pass
    except OSError:
        log.exception("清理旧版开机自启动失败")


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([sys.executable, "--silent"])
    root = Path(__file__).resolve().parents[1]
    pythonw = root / ".venv" / "Scripts" / "pythonw.exe"
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    main_py = root / "app" / "main.py"
    return subprocess.list2cmdline([str(pythonw), str(main_py), "--silent"])


def is_enabled() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _kind = winreg.QueryValueEx(key, VALUE_NAME)
        return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        log.exception("读取开机自启动设置失败")
        return False


def enable() -> bool:
    try:
        import winreg

        _remove_legacy()
        command = _launch_command()
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)
        log.info("开机自启动已开启: %s", command)
        return True
    except OSError:
        log.exception("写入开机自启动失败")
        return False


def disable() -> bool:
    _remove_legacy()
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, VALUE_NAME)
        log.info("开机自启动已关闭")
        return True
    except FileNotFoundError:
        return True
    except OSError:
        log.exception("关闭开机自启动失败")
        return False


def ensure(enabled: bool) -> bool:
    return enable() if enabled else disable()
