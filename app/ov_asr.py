"""OpenVINO GenAI ASR pipelines (Intel CPU/iGPU) for Whisper models."""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

log = logging.getLogger("voxa.openvino")

try:
    import openvino_genai
except Exception:  # pragma: no cover - optional dependency
    openvino_genai = None

_VAD_OPTIONS = None


def available() -> bool:
    return openvino_genai is not None


def available_devices() -> list[str]:
    try:
        import openvino as ov

        return [str(device).upper() for device in ov.Core().available_devices]
    except Exception:
        log.exception("读取 OpenVINO 设备失败")
        return ["CPU"]


def has_speech(audio: np.ndarray) -> bool:
    """Energy gate + Silero VAD; prevents hallucinations on room noise."""
    global _VAD_OPTIONS
    audio = np.asarray(audio, dtype=np.float32)
    if len(audio) == 0:
        return False
    rms = float(np.sqrt(np.mean(np.square(audio.astype(np.float64)))))
    if rms < 0.012:
        # Room noise / keyboard clicks on this machine sit around 0.006.
        return False
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        if _VAD_OPTIONS is None:
            _VAD_OPTIONS = VadOptions(min_silence_duration_ms=300, speech_pad_ms=100)
        return bool(get_speech_timestamps(audio, _VAD_OPTIONS, sampling_rate=16000))
    except Exception:
        log.exception("VAD 检测失败，按有语音处理")
        return True


class OVPipeline:
    def __init__(self, model_dir: str, device: str = "CPU") -> None:
        if openvino_genai is None:
            raise RuntimeError("openvino-genai 未安装")
        path = Path(model_dir)
        if not path.exists():
            raise FileNotFoundError(f"OpenVINO 模型目录不存在: {model_dir}")
        self.model_dir = str(path)
        self.device = device
        started = time.perf_counter()
        kwargs = {"PERFORMANCE_HINT": "LATENCY"}
        if device == "CPU":
            kwargs["INFERENCE_NUM_THREADS"] = 4
        else:
            cache = Path(__file__).resolve().parents[1] / "ov_cache"
            cache.mkdir(exist_ok=True)
            kwargs["CACHE_DIR"] = str(cache)
        self.pipe = openvino_genai.ASRPipeline(self.model_dir, device, **kwargs)
        self.load_seconds = time.perf_counter() - started
        log.info("OpenVINO 模型就绪 (%s, %.1fs): %s", device, self.load_seconds, path.name)

    def transcribe(self, audio: np.ndarray, language: str | None, prompt: str | None) -> tuple[str, float]:
        config = self.pipe.get_generation_config()
        config.task = "transcribe"
        config.return_timestamps = False
        if language:
            config.language = f"<|{language}|>"
        if prompt:
            config.initial_prompt = prompt
        started = time.perf_counter()
        result = self.pipe.generate(np.asarray(audio, dtype=np.float32).tolist(), config)
        elapsed = time.perf_counter() - started
        return str(result).strip(), elapsed
