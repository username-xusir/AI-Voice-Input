"""Voxa — private, local voice input for Windows.

A compact Win+H pill records, previews, auto-stops on silence, and types the
final transcript into the focused input box.
"""

from __future__ import annotations

import ctypes
import logging
import os
import queue
import subprocess
import sys
from pathlib import Path
import threading
import time
import traceback

import numpy as np
from PySide6.QtCore import QObject, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from asr import ASREngine
from autostart import ensure as ensure_autostart
from autostart import is_enabled as is_autostart_enabled
from config import LOG_DIR, load_config, save_config, setup_logging
from hotkey import HotkeyManager
from injector import (
    copy_text,
    force_foreground,
    foreground_window,
    insert_text,
    send_text_edit,
    text_delta,
)
from ov_asr import available_devices
from recorder import Recorder
from ui import PillWindow, QuickSettingsPanel, SettingsPanel, TrayIcon, set_theme

log = logging.getLogger("voxa")

MUTEX_NAME = "Local\\Voxa_SingleInstance"
ACTIVATE_EVENT_NAME = "Local\\Voxa_ShowSettings"
ERROR_ALREADY_EXISTS = 183
EVENT_MODIFY_STATE = 0x0002
WAIT_OBJECT_0 = 0


def hotkey_label_for(mode: str) -> str:
    mode = mode.lower()
    if mode.startswith("shift"):
        return "Shift+H"
    if mode.startswith("ctrl"):
        return "Ctrl+H"
    return "Win+H"


class Bridge(QObject):
    model_loaded = Signal()
    model_failed = Signal(str)
    preview_text = Signal(str, int)
    final_text = Signal(str, int)
    final_failed = Signal(str, int)
    engine_ready = Signal(object)
    engine_failed = Signal(str, str)


class VoxaApp(QObject):
    def __init__(
        self,
        app: QApplication,
        config: dict,
        silent: bool = False,
        activation_event: int | None = None,
    ) -> None:
        super().__init__()
        self.app = app
        self.config = config
        self.silent = silent
        self.activation_event = activation_event
        self.open_settings_on_start = not silent
        self.state = "loading"
        self.events: queue.Queue[str] = queue.Queue()
        self.bridge = Bridge()
        self.bridge.model_loaded.connect(self._on_model_loaded)
        self.bridge.model_failed.connect(self._on_model_failed)
        self.bridge.preview_text.connect(self._on_preview_text)
        self.bridge.final_text.connect(self._on_final_text)
        self.bridge.final_failed.connect(self._on_final_failed)
        self.bridge.engine_ready.connect(self._on_engine_ready)
        self.bridge.engine_failed.connect(self._on_engine_failed)

        hotkey_mode = str(config.get("hotkey", "win+h"))
        self.hotkey_label = hotkey_label_for(hotkey_mode)
        self.language = str(config.get("language", "zh"))
        self.live_preview_enabled = bool(config.get("live_preview", True))
        self.auto_stop_enabled = bool(config.get("auto_stop", True))
        self.auto_paste = bool(config.get("auto_paste", True))
        self.auto_punctuation = bool(config.get("auto_punctuation", True))
        self.high_accuracy = bool(config.get("high_accuracy", False))
        self.theme = set_theme(str(config.get("theme", "teal")))

        self.pill = PillWindow(hotkey_label=self.hotkey_label)
        self.settings = SettingsPanel()
        self.quick = QuickSettingsPanel()
        self.pill.mic_clicked.connect(self._on_mic_clicked)
        self.pill.close_clicked.connect(self._on_close_clicked)
        self.pill.settings_clicked.connect(self._on_settings_clicked)
        self.settings.back_clicked.connect(self._on_settings_back)
        self.settings.live_preview_toggled.connect(self._on_live_preview_toggled)
        self.settings.auto_paste_toggled.connect(self._on_auto_paste_toggled)
        self.settings.high_accuracy_toggled.connect(self._on_high_accuracy_toggled)
        self.settings.language_selected.connect(self._on_language_selected)
        self.settings.auto_punctuation_toggled.connect(self._on_auto_punctuation_toggled)
        self.settings.auto_stop_toggled.connect(self._on_auto_stop_toggled)
        self.settings.silence_changed.connect(self._on_silence_changed)
        self.settings.device_selected.connect(self._on_device_selected)
        self.settings.theme_selected.connect(self._on_theme_selected)
        self.settings.autostart_toggled.connect(self._on_toggle_autostart)
        self.quick.back_clicked.connect(self._on_quick_back)
        self.quick.live_preview_toggled.connect(self._on_live_preview_toggled)
        self.quick.auto_paste_toggled.connect(self._on_auto_paste_toggled)
        self.quick.auto_punctuation_toggled.connect(self._on_auto_punctuation_toggled)
        self.quick.auto_stop_toggled.connect(self._on_auto_stop_toggled)
        self.quick.theme_selected.connect(self._on_theme_selected)

        self.recorder = Recorder(config.get("input_device"))
        self.engine = self._create_engine()
        self.high_model_available = bool(self.engine.ov_model_dir) and Path(
            self.engine.ov_model_dir
        ).exists()
        if not self.high_model_available:
            self.high_accuracy = False
            self.config["high_accuracy"] = False
            self.engine.use_high_accuracy = False
        self.settings.set_high_available(self.high_model_available)
        self.gpu_available = False
        try:
            devices = available_devices()
            self.gpu_available = any(d.startswith("GPU") for d in devices)
        except Exception:
            log.exception("检测 OpenVINO GPU 失败")
        self.settings.set_gpu_available(self.gpu_available)
        if not self.gpu_available and str(self.config.get("ov_device", "CPU")).upper() == "GPU":
            self.config["ov_device"] = "CPU"
            self.engine.ov_device = "CPU"
        self.settings.set_values(
            self.live_preview_enabled,
            self.auto_paste,
            self.high_accuracy,
            self.language,
            auto_punctuation=self.auto_punctuation,
            theme=self.theme,
            auto_stop=self.auto_stop_enabled,
            silence_ms=int(self.config.get("auto_stop_silence_ms", 1800)),
            device=str(self.config.get("ov_device", "CPU")).upper(),
            autostart=bool(self.config.get("autostart", True)),
        )
        self.quick.set_values(
            self.live_preview_enabled,
            self.auto_paste,
            self.auto_punctuation,
            self.auto_stop_enabled,
            self.theme,
        )
        self.hotkey = HotkeyManager(
            on_hotkey=lambda: self.events.put("hotkey"),
            on_hotkey_release=lambda: self.events.put("hotkey_up"),
            on_escape=lambda: self.events.put("escape"),
            on_native_fallback=lambda: self.events.put("native"),
            native_fallback_enabled=config.get("native_fallback_hotkey_enabled", False),
            hotkey=hotkey_mode,
        )

        self.tray = TrayIcon(
            self.pill,
            on_quit=self.quit,
            on_open_logs=lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(LOG_DIR))),
            on_show=self._show_pill_from_tray,
            on_settings=self._open_settings_from_tray,
            on_toggle_hotkey=self._on_toggle_hotkey,
            on_toggle_autostart=self._on_toggle_autostart,
            autostart_enabled=is_autostart_enabled(),
            on_toggle_auto_stop=self._on_toggle_auto_stop,
            auto_stop_enabled=self.auto_stop_enabled,
            hotkey_label=self.hotkey_label,
            on_activate=self._open_settings_from_tray,
        )
        self.tray.show()

        self.session_id = 0
        self.finish_id = 0
        self.preview_busy = False
        self.preview_text = ""
        self.live_typed_text = ""
        self.live_type_failures = 0
        self.pending_live_text = ""
        self._auto_voice_started = 0.0
        self._auto_last_voice = 0.0
        self._auto_voice_ticks = 0
        self.last_preview_samples = 0
        self.pill_visible = False
        self.settings_visible = False
        self.quick_visible = False
        self.target_hwnd = 0
        self.session_started = 0.0
        self.paused_accum = 0.0
        self.pause_started = 0.0
        self.last_elapsed = 0.0
        self.toast_token = 0

        self._tick = QTimer(self)
        self._tick.setInterval(100)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start()

        self._live_timer = QTimer(self)
        self._live_timer.setInterval(int(config.get("preview_interval_ms", 800)))
        self._live_timer.timeout.connect(self._on_preview_tick)

        if self.activation_event:
            self._activation_timer = QTimer(self)
            self._activation_timer.setInterval(140)
            self._activation_timer.timeout.connect(self._check_activation)
            self._activation_timer.start()

    def _create_engine(self, device: str | None = None) -> ASREngine:
        engine = ASREngine(
            self.config.get("model_dir", ""),
            language=self.language,
            num_threads=self.config.get("num_threads", 4),
            compute_type=self.config.get("compute_type", "int8"),
            preview_model_dir=self.config.get("preview_model_dir"),
            fast_model_dir=self.config.get("fast_model_dir"),
            use_high_accuracy=self.high_accuracy,
            ov_model_dir=self.config.get("ov_model_dir"),
            ov_preview_model_dir=self.config.get("ov_preview_model_dir"),
            ov_fast_model_dir=self.config.get("ov_fast_model_dir"),
            ov_device=str(device or self.config.get("ov_device", "CPU")),
            use_openvino=bool(self.config.get("use_openvino", True)),
        )
        engine.auto_punctuation = self.auto_punctuation
        return engine

    # ---- startup --------------------------------------------------------
    def start(self) -> None:
        log.info(
            "Voxa 启动，OpenVINO=%s (%s)，OV 高精度=%s，OV 快速=%s，OV 预览=%s，语言=%s",
            self.config.get("use_openvino"),
            self.config.get("ov_device"),
            self.config.get("ov_model_dir"),
            self.config.get("ov_fast_model_dir"),
            self.config.get("ov_preview_model_dir"),
            self.language,
        )
        close_legacy_app()
        wanted_autostart = bool(self.config.get("autostart", True))
        if not ensure_autostart(wanted_autostart):
            log.warning("开机自启动设置失败（可稍后在托盘菜单重试）")
        self.tray.set_autostart_checked(is_autostart_enabled())
        try:
            self.hotkey.start()
        except Exception as exc:
            log.exception("全局热键安装失败")
            if not self.silent:
                QMessageBox.critical(
                    None,
                    "Voxa 启动失败",
                    f"无法安装 {self.hotkey_label} 全局热键：\n{exc}\n\n"
                    "如果另一个 Voxa 实例已经在运行，请先退出它。",
                )
            self.app.quit()
            return

        self.tray.set_status("正在加载模型…")
        threading.Thread(target=self._load_model, name="ModelLoader", daemon=True).start()

    def _load_model(self) -> None:
        try:
            self.engine.load()
            self.bridge.model_loaded.emit()
        except Exception as exc:
            log.exception("模型加载失败")
            self.bridge.model_failed.emit(str(exc))

    # ---- event loop -----------------------------------------------------
    def _on_tick(self) -> None:
        for _ in range(12):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            self._handle_event(event)

        if self.pill_visible:
            elapsed = self._elapsed()
            if self.state in ("recording", "paused"):
                self.pill.set_timer(elapsed)
            if self.state == "recording":
                self.pill.set_level(self.recorder.level)
            elif self.state == "paused":
                self.pill.set_level(0.0)
            if self.state == "recording" and elapsed >= float(
                self.config.get("max_record_seconds", 60)
            ):
                log.info("达到最长录音时间，自动结束")
                self._finish_and_close()
        if self.state == "recording" and self.auto_stop_enabled:
            self._update_auto_stop()

    def _elapsed(self) -> float:
        if self.state == "recording":
            return max(0.0, time.monotonic() - self.session_started - self.paused_accum)
        if self.state == "paused":
            return max(0.0, self.pause_started - self.session_started - self.paused_accum)
        return self.last_elapsed

    def _handle_event(self, event: str) -> None:
        if event == "hotkey":
            if self.state == "loading":
                self._show_loading_toast()
            elif self.state in ("recording", "paused"):
                log.info("用户再按 %s 停止录音", self.hotkey_label)
                self._finish_and_close()
            elif self.state == "finishing":
                log.info("正在生成文字，忽略热键")
            else:
                self._start_session()
        elif event == "hotkey_up":
            pass  # Ctrl+H is a toggle handled on key-down
        elif event == "escape":
            if self.state in ("recording", "paused"):
                log.info("用户按 Esc 停止录音并关闭")
                self._finish_and_close()
            elif self.state == "finishing":
                log.info("用户按 Esc 取消生成并关闭")
                self.finish_id += 1
                self._hide_all()
            elif self.pill_visible:
                log.info("用户按 Esc 关闭弹窗")
                self._hide_all()
        elif event == "native":
            log.info("用户触发 Ctrl+Alt+H，已调用 Windows 原生语音输入")

    # ---- session flow ---------------------------------------------------
    def _start_session(self) -> None:
        if not self.engine.loaded:
            self._show_locked("模型不可用，请查看日志")
            return
        if self.state in ("recording", "paused", "finishing"):
            return

        current = foreground_window()
        own_ids = (
            int(self.pill.winId()),
            int(self.settings.winId()),
            int(self.quick.winId()),
        )
        if current and current not in own_ids:
            self.target_hwnd = current
        self.toast_token += 1
        self._on_settings_back()
        self._on_quick_back()
        self.session_id += 1
        self.preview_text = ""
        self.live_typed_text = ""
        self.live_type_failures = 0
        self.pending_live_text = ""
        self._auto_voice_started = 0.0
        self._auto_last_voice = 0.0
        self._auto_voice_ticks = 0
        self.preview_busy = False
        self.last_preview_samples = 0
        self.last_elapsed = 0.0
        self.paused_accum = 0.0
        self.close_after_finish = False
        try:
            self.recorder.start()
        except Exception as exc:
            log.exception("麦克风启动失败")
            self._show_locked(str(exc))
            return

        self.state = "recording"
        self.session_started = time.monotonic()
        self.pill.set_timer(0)
        self.pill.set_mic_enabled(True)
        self.pill.set_text("")
        self.pill.set_state("recording")
        self.pill.show_pill()
        self.pill_visible = True
        self.hotkey.set_escape_armed(True)
        self._live_timer.start()
        self.tray.set_status("正在录音…")
        log.info("会话开始 sid=%s target=%s", self.session_id, self.target_hwnd)
        QTimer.singleShot(80, self._restore_target_focus)

    def _pause_recording(self) -> None:
        if self.state != "recording":
            return
        self.state = "paused"
        self.pause_started = time.monotonic()
        self.last_elapsed = self._elapsed()
        self.recorder.pause()
        self._live_timer.stop()
        self.pill.set_state("paused")
        if self.preview_text:
            self.pill.set_text(self.preview_text)
        self.tray.set_status("已暂停 · 点击麦克风继续")

    def _resume_recording(self) -> None:
        if self.state != "paused":
            return
        self.paused_accum += time.monotonic() - self.pause_started
        self.state = "recording"
        self.recorder.resume()
        self._auto_voice_ticks = 0
        self._auto_voice_started = 0.0
        self._auto_last_voice = 0.0
        self.pill.set_state("recording")
        if self.preview_text:
            self.pill.set_text(self.preview_text)
        self._live_timer.start()
        self.tray.set_status("正在录音…")
        QTimer.singleShot(80, self._restore_target_focus)

    def _update_auto_stop(self) -> None:
        level = float(self.recorder.level)
        now = time.monotonic()
        threshold = float(self.config.get("auto_speech_level", 0.03))
        if level >= threshold:
            if not self._auto_voice_ticks:
                self._auto_voice_started = now
            self._auto_voice_ticks += 1
            self._auto_last_voice = now
            return
        if not self._auto_voice_ticks:
            return
        min_speech = float(self.config.get("auto_min_speech_ms", 250)) / 1000.0
        if now - self._auto_voice_started < min_speech:
            return
        silence = float(self.config.get("auto_stop_silence_ms", 1800)) / 1000.0
        if now - self._auto_last_voice < silence:
            return
        log.info(
            "检测到停止说话（静音 %.2fs），自动结束并生成",
            now - self._auto_last_voice,
        )
        self._finish_and_close()

    def _restore_target_focus(self) -> None:
        if self.state == "recording" and self.target_hwnd:
            force_foreground(self.target_hwnd)

    def _on_mic_clicked(self) -> None:
        log.info("麦克风按钮点击 (state=%s)", self.state)
        if self.state == "recording":
            self._pause_recording()
        elif self.state == "paused":
            self._resume_recording()
        elif self.state == "ready":
            self._start_session()
        elif self.state == "finishing":
            log.info("正在生成文字，忽略麦克风点击")

    def _finish_and_close(self) -> None:
        if self.state == "finishing":
            # Second stop / X while final ASR is running: cancel and close.
            log.info("最终校正中再次请求结束，取消本次校正")
            self.finish_id += 1
            self._hide_all()
            return
        if self.state not in ("recording", "paused"):
            self._hide_all()
            return

        self._live_timer.stop()
        self.state = "finishing"
        self.last_elapsed = self._elapsed()
        audio, _rate = self.recorder.stop()
        duration = len(audio) / 16000
        log.info("会话结束 sid=%s %.2fs", self.session_id, duration)
        self.pill.set_mic_enabled(False)
        self.pill.set_state("finishing", "正在生成文字…")
        self.pill.set_timer(self.last_elapsed)
        self.tray.set_status("正在生成文字…")

        if duration < float(self.config.get("min_record_seconds", 0.35)):
            self._show_toast("说话时间太短", 1300)
            return
        peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
        if peak < 0.0008:
            self._show_toast("没有检测到声音", 1300)
            return

        self.finish_id += 1
        fid = self.finish_id
        log.info("最终识别开始 fid=%s %.2fs", fid, duration)
        threading.Thread(
            target=self._run_final,
            args=(audio, fid),
            name="WhisperFinal",
            daemon=True,
        ).start()

    def _run_final(self, audio: np.ndarray, fid: int) -> None:
        try:
            text = self.engine.transcribe_final(audio)
            self.bridge.final_text.emit(text, fid)
        except Exception as exc:
            log.exception("最终识别失败")
            self.bridge.final_failed.emit(str(exc), fid)

    # ---- preview --------------------------------------------------------
    def _on_preview_tick(self) -> None:
        if (
            self.state != "recording"
            or not self.live_preview_enabled
            or not self.engine.preview_loaded
            or self.preview_busy
        ):
            return
        audio = self.recorder.snapshot()
        if len(audio) < int(0.8 * 16000):
            return
        if len(audio) <= self.last_preview_samples + int(0.25 * 16000):
            return
        if float(np.max(np.abs(audio))) < 0.001:
            # Pure digital silence: do not let Whisper hallucinate into the
            # input box while the user is not speaking.
            return
        self.preview_busy = True
        self.last_preview_samples = len(audio)
        sid = self.session_id
        log.info("预览开始 sid=%s %.2fs", sid, len(audio) / 16000)
        threading.Thread(
            target=self._run_preview,
            args=(audio, sid),
            name="PreviewASR",
            daemon=True,
        ).start()

    def _run_preview(self, audio: np.ndarray, sid: int) -> None:
        try:
            text = self.engine.transcribe_preview(audio)
        except Exception:
            log.exception("实时预览失败")
            text = ""
        self.bridge.preview_text.emit(text, sid)

    def _on_preview_text(self, text: str, sid: int) -> None:
        self.preview_busy = False
        if sid != self.session_id or self.state not in ("recording", "paused"):
            return
        if not text:
            return
        self.preview_text = text
        self.pill.set_text(text)
        log.info("预览 sid=%s: %r", sid, text)
        if self.state == "recording":
            self._apply_live_text(text)

    def _apply_live_text(self, text: str) -> None:
        """Type the preview into the target input box, keeping earlier text."""
        if (
            not self.live_preview_enabled
            or self.state != "recording"
            or self.settings_visible
            or self.quick_visible
        ):
            return
        new = (text or "").strip("\r\n")
        if not new or new == self.live_typed_text:
            return
        if not self.target_hwnd:
            return
        delete_count, insert = text_delta(self.live_typed_text, new)
        if delete_count + len(insert) > 120:
            # A single preview should not rewrite hundreds of characters.
            # Wait for the next preview; if it repeats, accept it.
            if new != self.pending_live_text:
                self.pending_live_text = new
                log.info("预览变化 %s 字，等待下一次确认", delete_count + len(insert))
                return
        self.pending_live_text = ""
        current = foreground_window()
        own_windows = (
            int(self.pill.winId()),
            int(self.settings.winId()),
            int(self.quick.winId()),
        )
        if current and current != self.target_hwnd and current not in own_windows:
            # The user switched to another app; don't steal focus every
            # preview. The final pass will still try to correct the text.
            log.info("前台不是目标窗口 (current=%s)，暂停实时输入", current)
            return
        allow_activate = current in own_windows
        try:
            ok = send_text_edit(
                self.live_typed_text,
                new,
                self.target_hwnd,
                allow_activate=allow_activate,
            )
        except Exception:
            log.exception("实时输入失败")
            ok = False
        if ok:
            self.live_typed_text = new
        else:
            self.live_type_failures += 1
            log.warning(
                "实时输入未生效 (第 %s 次)，保留预览文字，停止时再校正",
                self.live_type_failures,
            )

    # ---- results --------------------------------------------------------
    def _on_model_loaded(self) -> None:
        self.state = "ready"
        self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")
        if self.pill_visible and self.pill._state == "loading":
            self._hide_all()
        log.info("模型加载完成，等待按 %s", self.hotkey_label)
        if self.open_settings_on_start:
            self.open_settings_on_start = False
            QTimer.singleShot(150, self._open_settings_from_tray)

    def _on_model_failed(self, message: str) -> None:
        self.state = "error"
        self.tray.set_status("模型加载失败")
        self._show_locked(message)
        log.error("模型加载失败: %s", message)

    def _on_final_text(self, text: str, fid: int) -> None:
        if fid != self.finish_id or self.state != "finishing":
            log.info("忽略过期/已取消的最终结果 fid=%s current=%s", fid, self.finish_id)
            return
        self.state = "ready"
        text = (text or "").strip() or self.preview_text.strip()
        if not text:
            self._show_toast("没听清，请再说一次", 1300)
            return
        try:
            if self.auto_paste:
                if self.live_typed_text:
                    # Live preview already typed the text; only fix the
                    # changed suffix so the final pass is fast and non-destructive.
                    ok = send_text_edit(self.live_typed_text, text, self.target_hwnd)
                    if not ok:
                        copy_text(text)
                        log.warning("最终校正失败，最终文字已复制到剪贴板")
                        self.tray.set_status("最终文字已复制，请手动粘贴")
                elif not self.target_hwnd or foreground_window() == self.target_hwnd:
                    insert_text(
                        text,
                        target_hwnd=self.target_hwnd,
                        mode=self.config.get("insert_mode", "paste"),
                        restore_clipboard=self.config.get("restore_clipboard", True),
                    )
                else:
                    copy_text(text)
                    log.warning("目标窗口已不在前台，最终文字已复制到剪贴板")
                    self.tray.set_status("最终文字已复制，请手动粘贴")
            else:
                copy_text(text)
                log.info("自动校正已关闭，最终文字已复制到剪贴板")
        except Exception as exc:
            log.exception("文字输入失败")
            self.state = "ready"
            if getattr(self, "close_after_finish", False):
                self.close_after_finish = False
                self._hide_all()
                self.tray.set_status("文字输入失败")
                return
            self.pill.set_mic_enabled(True)
            self.pill.set_state("error", f"文字输入失败：{exc}")
            self.tray.set_status("文字输入失败")
            return
        self.live_typed_text = ""
        self.state = "ready"
        if getattr(self, "close_after_finish", False):
            self.close_after_finish = False
            self._hide_all()
            self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")
            return
        self.pill.set_mic_enabled(True)
        self.pill.set_state("ready", text)
        self.pill.show_pill()
        self.pill_visible = True
        self.hotkey.set_escape_armed(True)
        self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")

    def _on_final_failed(self, message: str, fid: int) -> None:
        if fid != self.finish_id or self.state != "finishing":
            return
        self.state = "ready"
        self.tray.set_status("识别失败")
        if getattr(self, "close_after_finish", False):
            self.close_after_finish = False
            self._hide_all()
            log.error("最终识别失败: %s", message)
            return
        self.pill.set_mic_enabled(True)
        self.pill.set_state("error", message)
        log.error("最终识别失败: %s", message)

    # ---- settings / tray ------------------------------------------------
    def _on_settings_clicked(self) -> None:
        """Small, quick settings card opened from the floating pill."""
        if self.quick_visible:
            self._on_quick_back()
            return
        if self.settings_visible:
            self._on_settings_back()
        if not self.pill_visible:
            self.pill.show_pill()
            self.pill_visible = True
            self.hotkey.set_escape_armed(True)
        self.quick.set_values(
            self.live_preview_enabled,
            self.auto_paste,
            self.auto_punctuation,
            self.auto_stop_enabled,
            self.theme,
        )
        self.quick.apply_theme()
        self.quick.show_near(self.pill.frameGeometry())
        self.quick_visible = True

    def _on_quick_back(self) -> None:
        self.quick.hide()
        self.quick_visible = False
        if self.state == "recording":
            QTimer.singleShot(60, self._restore_target_focus)

    def _on_settings_back(self) -> None:
        self.settings.hide()
        self.settings_visible = False
        if self.state == "recording":
            QTimer.singleShot(60, self._restore_target_focus)

    def _open_settings_from_tray(self) -> None:
        """Detailed settings, opened by the desktop shortcut / tray.

        This path deliberately does not create or show the voice pill.
        """
        if self.quick_visible:
            self._on_quick_back()
        if self.settings_visible:
            self.settings.raise_()
            self.settings.activateWindow()
            return
        # Desktop/tray settings must not bring up the voice pill.
        if self.pill_visible and self.state in ("ready", "error"):
            self.pill.hide()
            self.pill_visible = False
            self.hotkey.set_escape_armed(False)
        self.settings.set_values(
            self.live_preview_enabled,
            self.auto_paste,
            self.high_accuracy,
            self.language,
            auto_punctuation=self.auto_punctuation,
            theme=self.theme,
            auto_stop=self.auto_stop_enabled,
            silence_ms=int(self.config.get("auto_stop_silence_ms", 1800)),
            device=str(self.config.get("ov_device", "CPU")).upper(),
            autostart=bool(self.config.get("autostart", True)),
        )
        self.settings.apply_theme()
        self.settings.show_centered()
        self.settings_visible = True

    def _show_pill_from_tray(self) -> None:
        if self.state not in ("ready", "error"):
            return
        if not self.pill_visible:
            self.target_hwnd = foreground_window()
            self.pill.set_state("paused", f"按 {self.hotkey_label} 开始说话")
            self.pill.show_pill()
            self.pill_visible = True
            self.hotkey.set_escape_armed(True)

    def _on_live_preview_toggled(self, enabled: bool) -> None:
        self.live_preview_enabled = enabled
        self.config["live_preview"] = enabled
        save_config(self.config)
        if not enabled:
            self.preview_text = ""
            self.pill.set_text("")
        log.info("实时预览: %s", enabled)

    def _on_auto_paste_toggled(self, enabled: bool) -> None:
        self.auto_paste = enabled
        self.config["auto_paste"] = enabled
        save_config(self.config)
        log.info("自动粘贴: %s", enabled)

    def _on_high_accuracy_toggled(self, enabled: bool) -> None:
        self.high_accuracy = enabled
        self.config["high_accuracy"] = enabled
        self.engine.use_high_accuracy = enabled
        save_config(self.config)
        log.info("高精度最终模型: %s", enabled)

    def _on_language_selected(self, language: str) -> None:
        self.language = language
        self.config["language"] = language
        self.engine.language = language
        save_config(self.config)
        log.info("语言: %s", language)

    def _on_auto_punctuation_toggled(self, enabled: bool) -> None:
        self.auto_punctuation = enabled
        self.config["auto_punctuation"] = enabled
        self.engine.auto_punctuation = enabled
        save_config(self.config)
        log.info("自动标点: %s", enabled)

    def _on_auto_stop_toggled(self, enabled: bool) -> None:
        self.auto_stop_enabled = enabled
        self.config["auto_stop"] = enabled
        save_config(self.config)
        self.tray.set_auto_stop_checked(enabled)
        self.settings.auto_stop_switch.blockSignals(True)
        self.settings.auto_stop_switch.setChecked(enabled)
        self.settings.auto_stop_switch.blockSignals(False)
        self.settings.silence_slider.setEnabled(enabled)
        self.quick.auto_stop_switch.blockSignals(True)
        self.quick.auto_stop_switch.setChecked(enabled)
        self.quick.auto_stop_switch.blockSignals(False)
        log.info("停止说话自动结束: %s", enabled)

    def _on_silence_changed(self, milliseconds: int) -> None:
        value = max(800, min(4000, int(milliseconds)))
        self.config["auto_stop_silence_ms"] = value
        save_config(self.config)
        log.info("静音结束阈值: %s ms", value)

    def _on_theme_selected(self, name: str) -> None:
        self.theme = set_theme(name)
        self.config["theme"] = self.theme
        save_config(self.config)
        self.pill.apply_theme()
        self.settings.apply_theme()
        self.quick.apply_theme()
        log.info("主题: %s", self.theme)

    def _on_device_selected(self, device: str) -> None:
        device = device.upper()
        current = str(self.config.get("ov_device", "CPU")).upper()
        if self.state not in ("ready", "error"):
            self.settings.set_values(
                self.live_preview_enabled,
                self.auto_paste,
                self.high_accuracy,
                self.language,
                auto_punctuation=self.auto_punctuation,
                theme=self.theme,
                auto_stop=self.auto_stop_enabled,
                silence_ms=int(self.config.get("auto_stop_silence_ms", 1800)),
                device=current,
                autostart=bool(self.config.get("autostart", True)),
            )
            self.settings.footer_label.setText("识别中，暂不能切换设备")
            QTimer.singleShot(
                1800, lambda: self.settings.footer_label.setText("设置自动保存")
            )
            log.info("当前状态 %s，忽略设备切换", self.state)
            return
        if device == current:
            return
        if device == "GPU" and not self.gpu_available:
            return
        self._previous_device = current
        self.config["ov_device"] = device
        save_config(self.config)
        self.state = "loading"
        self.tray.set_status(f"正在切换到 {device}…")
        log.info("切换计算设备: %s -> %s", current, device)
        threading.Thread(
            target=self._reload_engine,
            args=(device,),
            name="EngineReload",
            daemon=True,
        ).start()

    def _reload_engine(self, device: str) -> None:
        try:
            engine = self._create_engine(device)
            engine.load()
            self.bridge.engine_ready.emit(engine)
        except Exception as exc:
            log.exception("切换计算设备失败")
            self.bridge.engine_failed.emit(device, str(exc))

    def _on_engine_ready(self, engine: ASREngine) -> None:
        old = self.engine
        self.engine = engine
        try:
            old.close()
        except Exception:
            log.exception("释放旧引擎失败")
        self.high_model_available = bool(engine.ov_model_dir) and Path(
            engine.ov_model_dir
        ).exists()
        if not self.high_model_available:
            self.high_accuracy = False
            self.config["high_accuracy"] = False
            engine.use_high_accuracy = False
        self.settings.set_high_available(self.high_model_available)
        self.settings.set_gpu_available(self.gpu_available)
        self.state = "ready"
        self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")
        self._show_toast(f"已切换到 {engine.ov_device} 推理", 1700)
        log.info(
            "计算设备切换完成: %s (%.1fs)",
            engine.ov_device,
            engine.load_seconds,
        )

    def _on_engine_failed(self, device: str, message: str) -> None:
        previous = getattr(self, "_previous_device", "CPU")
        self.config["ov_device"] = previous
        save_config(self.config)
        self.state = "ready"
        self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")
        self.settings.set_values(
            self.live_preview_enabled,
            self.auto_paste,
            self.high_accuracy,
            self.language,
            auto_punctuation=self.auto_punctuation,
            theme=self.theme,
            auto_stop=self.auto_stop_enabled,
            silence_ms=int(self.config.get("auto_stop_silence_ms", 1800)),
            device=previous,
            autostart=bool(self.config.get("autostart", True)),
        )
        self._show_toast(f"{device} 切换失败，已保留 {previous}", 2300)
        log.error("计算设备 %s 切换失败: %s", device, message)

    def _on_toggle_autostart(self, enabled: bool) -> None:
        if not ensure_autostart(enabled):
            self.tray.set_autostart_checked(not enabled)
            self.settings.autostart_switch.blockSignals(True)
            self.settings.autostart_switch.setChecked(not enabled)
            self.settings.autostart_switch.blockSignals(False)
            self.tray.set_status("开机自启动设置失败")
            return
        self.config["autostart"] = enabled
        save_config(self.config)
        self.tray.set_autostart_checked(enabled)
        self.settings.autostart_switch.blockSignals(True)
        self.settings.autostart_switch.setChecked(enabled)
        self.settings.autostart_switch.blockSignals(False)
        log.info("开机自启动: %s", enabled)
        self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")

    def _on_toggle_auto_stop(self, enabled: bool) -> None:
        self._on_auto_stop_toggled(enabled)
        self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")

    def _on_toggle_hotkey(self, paused: bool) -> None:
        if paused and self.state == "recording":
            self._pause_recording()
        self.hotkey.set_enabled(not paused)
        if paused:
            self.tray.set_status("热键已暂停")
        else:
            self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")

    # ---- helpers --------------------------------------------------------
    def _check_activation(self) -> None:
        """A second launch (desktop shortcut / Start menu) opens settings."""
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            kernel32.WaitForSingleObject.restype = ctypes.c_uint32
            if kernel32.WaitForSingleObject(self.activation_event, 0) == WAIT_OBJECT_0:
                log.info("收到再次启动请求，打开设置")
                self._open_settings_from_tray()
        except Exception:
            log.exception("处理启动激活事件失败")

    def _show_loading_toast(self) -> None:
        self.toast_token += 1
        token = self.toast_token
        self.pill.set_state("loading", "正在加载模型…")
        self.pill.show_pill()
        self.pill_visible = True
        self.hotkey.set_escape_armed(True)
        QTimer.singleShot(1600, lambda: self._hide_loading_toast(token))

    def _hide_loading_toast(self, token: int) -> None:
        if token == self.toast_token and self.state == "loading" and self.pill.state == "loading":
            self._hide_all()

    def _show_toast(self, text: str, ms: int) -> None:
        self.state = "ready"
        self.pill.set_mic_enabled(False)
        self.pill.set_state("error", text)
        if not self.pill_visible:
            self.pill.show_pill()
            self.pill_visible = True
            self.hotkey.set_escape_armed(True)
        self.toast_token += 1
        token = self.toast_token
        QTimer.singleShot(ms, lambda: self._hide_toast(token))

    def _hide_toast(self, token: int) -> None:
        if token == self.toast_token and self.state == "ready" and self.pill.state == "error":
            self._hide_all()

    def _show_locked(self, text: str) -> None:
        self.pill.set_state("error", text)
        self.pill.show_pill()
        self.pill_visible = True
        self.hotkey.set_escape_armed(True)

    def _hide_all(self) -> None:
        self.toast_token += 1
        self._live_timer.stop()
        self.settings.hide()
        self.settings_visible = False
        self.quick.hide()
        self.quick_visible = False
        self.close_after_finish = False
        self.pill.hide()
        self.pill_visible = False
        self.live_typed_text = ""
        self.pending_live_text = ""
        self.hotkey.set_escape_armed(False)
        if self.state not in ("loading", "error"):
            self.state = "ready"
            self.tray.set_status(f"就绪 · 按 {self.hotkey_label} 说话")

    def _on_close_clicked(self) -> None:
        log.info("关闭按钮点击 (state=%s)", self.state)
        if self.state in ("recording", "paused", "finishing"):
            self.close_after_finish = True
            self._finish_and_close()
        else:
            self._hide_all()

    def quit(self) -> None:
        log.info("Voxa 退出")
        try:
            self.recorder.cancel()
            self.hotkey.stop()
        finally:
            self.pill.hide()
            self.settings.hide()
            self.quick.hide()
            self.tray.hide()
            self.app.quit()


def acquire_single_instance():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    handle = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not handle:
        return None
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        return None
    return handle


def close_legacy_app() -> None:
    """A stale pre-rename VoiceIn build would otherwise keep its old UI and
    Win+H hook alive next to Voxa."""
    if not getattr(sys, "frozen", False):
        return
    try:
        result = subprocess.run(
            ["taskkill", "/IM", "VoiceIn.exe", "/F"],
            capture_output=True,
            timeout=3,
            creationflags=0x08000000,
        )
        if result.returncode == 0:
            log.info("已关闭遗留的 VoiceIn 进程")
    except Exception:
        log.exception("关闭遗留 VoiceIn 失败")


def create_activation_event():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateEventW.restype = ctypes.c_void_p
    return kernel32.CreateEventW(None, False, False, ACTIVATE_EVENT_NAME)


def signal_existing_instance() -> bool:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenEventW.restype = ctypes.c_void_p
    handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, ACTIVATE_EVENT_NAME)
    if not handle:
        return False
    kernel32.SetEvent.argtypes = [ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel32.SetEvent(handle)
    kernel32.CloseHandle(handle)
    return True


def main() -> int:
    setup_logging()
    silent = "--silent" in sys.argv
    if silent:
        sys.argv.remove("--silent")
    try:
        if os.environ.get("VOICEIN_DEBUG_STACKS"):
            import faulthandler

            trace_file = open(LOG_DIR / "traceback.log", "a", encoding="utf-8")  # noqa: SIM115
            faulthandler.dump_traceback_later(30, repeat=True, file=trace_file)
    except Exception:
        pass
    log.info("=" * 60)
    log.info("进程启动 pid=%s", os.getpid())

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Voxa.Voice")
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setApplicationName("Voxa")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Microsoft YaHei UI", 9))

    config = load_config()
    hotkey_mode = str(config.get("hotkey", "win+h"))
    hotkey_label = hotkey_label_for(hotkey_mode)

    mutex = acquire_single_instance()
    if mutex is None:
        if silent:
            log.info("静默启动：已有实例在运行，直接退出")
        elif signal_existing_instance():
            log.info("已有实例在运行，已请求它打开设置")
        else:
            QMessageBox.information(
                None, "Voxa", f"Voxa 已经在运行了。\n按 {hotkey_label} 即可开始语音输入。"
            )
        # QApplication was created before the mutex check; returning normally
        # can leave a tiny Qt process alive. Exit the secondary process now.
        app.quit()
        os._exit(0)

    activation_event = create_activation_event()

    def excepthook(exc_type, exc, tb):
        log.error("未捕获异常:\n%s", "".join(traceback.format_exception(exc_type, exc, tb)))

    sys.excepthook = excepthook

    voxa = VoxaApp(app, config, silent=silent, activation_event=activation_event)
    voxa.start()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
