"""End-to-end ASREngine test on the bundled TTS fixtures."""

from __future__ import annotations

import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from asr import ASREngine  # noqa: E402

MODEL_ROOT = Path(os.environ.get("VOXA_MODEL_ROOT", str(ROOT / "models")))
MODEL_DIR = sys.argv[1] if len(sys.argv) > 1 else str(
    MODEL_ROOT / "faster-whisper-large-v3-turbo"
)
PREVIEW_DIR = sys.argv[2] if len(sys.argv) > 2 else str(
    MODEL_ROOT / "faster-whisper-small"
)


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as f:
        assert f.getnchannels() == 1 and f.getsampwidth() == 2
        audio = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
    return audio.astype(np.float32) / 32768.0


def main() -> int:
    engine = ASREngine(MODEL_DIR, language="zh", num_threads=4, preview_model_dir=PREVIEW_DIR)
    t0 = time.perf_counter()
    engine.load()
    print(f"load: {time.perf_counter() - t0:.1f}s")

    ok = True
    for name, language, keys in [
        ("zh_test.wav", "zh-CN", ["你好", "语音", "测试", "天气"]),
        ("en_test.wav", "en-US", ["hello", "speech", "test", "weather"]),
    ]:
        engine.language = language
        audio = read_wav(ROOT / "tests" / "fixtures" / name)
        t0 = time.perf_counter()
        text = engine.transcribe(audio)
        elapsed = time.perf_counter() - t0
        print(f"{name} [{language}] {len(audio) / 16000:.2f}s -> {text!r} ({elapsed:.2f}s)")
        missing = [k for k in keys if k.lower() not in text.lower()]
        if missing:
            print("  missing keywords:", missing)
            ok = False

    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
