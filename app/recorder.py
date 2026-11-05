"""Microphone capture with pause/resume and live snapshots."""

from __future__ import annotations

import logging
import os
import threading
import time
import wave

import numpy as np
import sounddevice as sd

log = logging.getLogger("voxa.recorder")

TARGET_RATE = 16000
TEST_WAV = os.environ.get("VOICEIN_TEST_WAV")


class Recorder:
    def __init__(self, device: str | int | None = None) -> None:
        self.device = device
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._level = 0.0
        self._samplerate = TARGET_RATE
        self._paused = False
        self._test_audio: np.ndarray | None = None
        self._test_started = 0.0

    # ---- state ----------------------------------------------------------
    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def active(self) -> bool:
        return self._stream is not None or self._test_audio is not None

    @property
    def level(self) -> float:
        if self._paused:
            return 0.0
        if self._test_audio is not None:
            import math

            t = time.monotonic() - self._test_started
            return 0.18 + 0.12 * abs(math.sin(t * 5.0))
        return self._level

    @property
    def duration(self) -> float:
        if self._test_audio is not None:
            return min(
                time.monotonic() - self._test_started,
                len(self._test_audio) / TARGET_RATE,
            )
        with self._lock:
            frames = sum(len(c) for c in self._chunks)
        return frames / self._samplerate if self._samplerate else 0.0

    # ---- lifecycle ------------------------------------------------------
    def start(self) -> None:
        if self.active:
            return
        self._paused = False
        self._chunks = []
        self._level = 0.0

        if TEST_WAV:
            with wave.open(TEST_WAV, "rb") as f:
                if f.getnchannels() != 1 or f.getsampwidth() != 2:
                    raise RuntimeError("测试 WAV 必须是 16-bit 单声道")
                audio = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
            self._test_audio = audio.astype(np.float32) / 32768.0
            self._test_started = time.monotonic()
            self._samplerate = TARGET_RATE
            log.warning("测试模式：使用 WAV 代替麦克风 (%s)", TEST_WAV)
            return

        device_info = self._resolve_device()
        native_rate = int(device_info["default_samplerate"])
        errors: list[str] = []
        for rate in (TARGET_RATE, native_rate):
            if rate <= 0:
                continue
            try:
                stream = sd.InputStream(
                    samplerate=rate,
                    channels=1,
                    dtype="float32",
                    blocksize=max(160, int(rate * 0.05)),
                    device=self.device,
                    callback=self._callback,
                )
                stream.start()
            except Exception as exc:  # PortAudioError and friends
                errors.append(f"{rate} Hz: {exc}")
                continue
            self._stream = stream
            self._samplerate = rate
            log.info(
                "录音开始: device=%r rate=%s name=%s",
                self.device,
                rate,
                device_info.get("name"),
            )
            return
        raise RuntimeError("无法打开麦克风。\n" + "\n".join(errors))

    def pause(self) -> None:
        if self.active:
            self._paused = True
            self._level = 0.0
            log.info("录音暂停")

    def resume(self) -> None:
        if self.active:
            self._paused = False
            log.info("录音继续")

    def snapshot(self) -> np.ndarray:
        """Return recorded audio so far, resampled to 16 kHz."""
        if self._test_audio is not None:
            return self._test_audio.copy()
        with self._lock:
            chunks = list(self._chunks)
            rate = self._samplerate
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(chunks).astype(np.float32, copy=False)
        if rate != TARGET_RATE and len(audio):
            import soxr

            audio = soxr.resample(audio, rate, TARGET_RATE, quality="HQ").astype(np.float32)
        return audio

    def stop(self) -> tuple[np.ndarray, int]:
        if self._test_audio is not None:
            audio = self._test_audio
            self._test_audio = None
            self._paused = False
            log.info("测试模式录音结束: %.2fs", len(audio) / TARGET_RATE)
            return audio, TARGET_RATE

        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()

        audio = self.snapshot()
        self._paused = False
        with self._lock:
            self._chunks = []
        log.info("录音结束: %.2fs", len(audio) / TARGET_RATE)
        return audio, TARGET_RATE

    def cancel(self) -> None:
        self._test_audio = None
        stream = self._stream
        self._stream = None
        if stream is not None:
            try:
                stream.stop()
            finally:
                stream.close()
        with self._lock:
            self._chunks = []
        self._level = 0.0
        self._paused = False

    # ---- internals ------------------------------------------------------
    def _callback(self, indata, frames, time_info, status) -> None:
        if status:
            log.debug("录音状态: %s", status)
        if self._paused:
            self._level = 0.0
            return
        data = indata[:, 0].copy()
        rms = float(np.sqrt(np.mean(data * data))) if len(data) else 0.0
        with self._lock:
            self._chunks.append(data)
            self._level = 0.75 * self._level + 0.25 * min(1.0, rms * 14.0)

    def _resolve_device(self) -> dict:
        try:
            if self.device is not None:
                return sd.query_devices(self.device, "input")
            return sd.query_devices(kind="input")
        except Exception:
            for idx, info in enumerate(sd.query_devices()):
                if info["max_input_channels"] > 0:
                    self.device = idx
                    return info
            raise RuntimeError("系统里没有可用的麦克风输入设备")
