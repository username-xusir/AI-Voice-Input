"""ASR engines for Voxa.

Preferred: OpenVINO GenAI int4 Whisper pipelines on CPU (Intel Iris Xe is
slower than CPU for this workload).  Fallback: faster-whisper / CTranslate2.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from pathlib import Path

import numpy as np

from ov_asr import OVPipeline, available as ov_available, has_speech

log = logging.getLogger("voxa.asr")

_LANG_TAG = re.compile(r"<[a-z]{2,3}-[A-Z]{2,3}>")
_LOOP = re.compile(r"(.{2,20}?)\1{3,}")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_KANA = re.compile(r"[\u3040-\u30ff]")
_PUNCT = re.compile(r"[\uff0c\u3002\uff01\uff1f\uff1b\uff1a\u3001,.!?;:'\"\u2026\u2014\u2013\uff08\uff09()\u300a\u300b\u3008\u3009\u3010\u3011\[\]{}\u201c\u201d\u2018\u2019\u00b7]+")

try:
    from opencc import OpenCC

    _OPENCC = OpenCC("t2s")
except Exception:  # pragma: no cover - optional dependency
    _OPENCC = None

_WHISPER_LANG = {
    "zh": "zh",
    "zh-cn": "zh",
    "zh-tw": "zh",
    "en": "en",
    "en-us": "en",
    "ja": "ja",
    "ko": "ko",
    "fr": "fr",
    "de": "de",
    "es": "es",
    "ru": "ru",
}


def _clean_text(text: str) -> str:
    """Strip language tags and collapse Whisper repetition loops."""
    text = _LANG_TAG.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    previous = None
    while previous != text:
        previous = text
        text = _LOOP.sub(r"\1", text)
    return text.strip()


def _strip_punctuation(text: str) -> str:
    """Remove punctuation while keeping a word gap for Latin text."""

    def replace(match: re.Match[str]) -> str:
        before = text[match.start() - 1] if match.start() else ""
        after = text[match.end()] if match.end() < len(text) else ""
        if before.isascii() and before.isalnum() and after.isascii() and after.isalnum():
            return " "
        return ""

    text = _PUNCT.sub(replace, text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def _finish_text(text: str, language_key: str, auto_punctuation: bool = True) -> str:
    """Clean text and convert traditional Chinese to simplified when relevant."""
    text = _clean_text(text)
    if _OPENCC is not None:
        key = str(language_key).lower()
        if not key.startswith("ja") and (
            key.startswith("zh") or (key == "auto" and _CJK.search(text) and not _KANA.search(text))
        ):
            text = _OPENCC.convert(text)
    if not auto_punctuation:
        text = _strip_punctuation(text)
    return text


def resolve_whisper_dir(path: str) -> Path:
    """Accept either a snapshot dir or the HF hub model dir."""
    p = Path(path)
    if (p / "model.bin").exists():
        return p
    snapshots = p / "snapshots"
    if snapshots.is_dir():
        for candidate in sorted(snapshots.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if (candidate / "model.bin").exists():
                return candidate
    raise FileNotFoundError(f"找不到 faster-whisper 模型 (model.bin): {path}")


class ASREngine:
    def __init__(
        self,
        model_dir: str,
        language: str = "zh",
        num_threads: int = 4,
        compute_type: str = "int8",
        preview_model_dir: str | None = None,
        fast_model_dir: str | None = None,
        use_high_accuracy: bool = True,
        ov_model_dir: str | None = None,
        ov_preview_model_dir: str | None = None,
        ov_fast_model_dir: str | None = None,
        ov_device: str = "CPU",
        use_openvino: bool = True,
    ) -> None:
        self.model_dir = model_dir
        self.preview_model_dir = preview_model_dir
        self.fast_model_dir = fast_model_dir
        self.use_high_accuracy = use_high_accuracy
        self.language = language
        self.num_threads = max(1, int(num_threads))
        self.compute_type = compute_type
        self.ov_model_dir = ov_model_dir
        self.ov_preview_model_dir = ov_preview_model_dir
        self.ov_fast_model_dir = ov_fast_model_dir
        self.ov_device = ov_device
        self.use_openvino = use_openvino
        self.auto_punctuation = True
        self._lock = threading.Lock()

        self.whisper = None
        self.fast_whisper = None
        self.preview_whisper = None
        self.ov_large: OVPipeline | None = None
        self.ov_small: OVPipeline | None = None
        self.ov_base: OVPipeline | None = None
        self._loaded = False
        self.load_seconds = 0.0

    # ---- loading --------------------------------------------------------
    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def preview_loaded(self) -> bool:
        return self.ov_base is not None or self.preview_whisper is not None

    def load(self) -> None:
        if self._loaded:
            return
        started = time.perf_counter()
        if self.use_openvino and ov_available():
            self._load_openvino()
        else:
            log.info("OpenVINO 不可用，使用 faster-whisper")

        if self.ov_large is None and self.ov_small is None and self.whisper is None:
            self._load_whisper_final()
        if self.ov_base is None and self.preview_whisper is None:
            self._load_preview()
        if self.ov_small is None and self.fast_whisper is None and self.fast_model_dir:
            self._load_fast()

        self._loaded = bool(self.ov_large or self.ov_small or self.whisper)
        self.load_seconds = time.perf_counter() - started
        log.info(
            "全部模型加载完成: %.1fs (openvino=%s, ov_device=%s)",
            self.load_seconds,
            bool(self.ov_large or self.ov_small or self.ov_base),
            self.ov_device,
        )

    def close(self) -> None:
        """Release pipelines/models before swapping engines."""
        self.whisper = None
        self.fast_whisper = None
        self.preview_whisper = None
        self.ov_large = None
        self.ov_small = None
        self.ov_base = None
        self._loaded = False
        self.load_seconds = 0.0

    def _load_openvino(self) -> None:
        if self.use_high_accuracy and self.ov_model_dir:
            self._load_ov_large()
        specs = (
            ("快速最终", self.ov_fast_model_dir, "ov_small"),
            ("预览", self.ov_preview_model_dir, "ov_base"),
        )
        for label, path, attr in specs:
            if not path or not Path(path).exists():
                log.info("未找到 OpenVINO %s模型: %s", label, path)
                continue
            try:
                setattr(self, attr, OVPipeline(path, self.ov_device))
            except Exception:
                log.exception("OpenVINO %s模型加载失败，回退 faster-whisper", label)

    def _load_ov_large(self) -> None:
        if not self.ov_model_dir or not Path(self.ov_model_dir).exists():
            return
        try:
            self.ov_large = OVPipeline(self.ov_model_dir, self.ov_device)
        except Exception:
            log.exception("OpenVINO 高精度模型加载失败，回退 faster-whisper")
            self.ov_large = None

    def _load_whisper_final(self) -> None:
        from faster_whisper import WhisperModel

        t0 = time.perf_counter()
        try:
            whisper_dir = resolve_whisper_dir(self.model_dir)
            log.info("加载 faster-whisper 最终模型: %s", whisper_dir)
            self.whisper = WhisperModel(
                str(whisper_dir),
                device="cpu",
                compute_type=self.compute_type,
                cpu_threads=self.num_threads,
                num_workers=1,
                local_files_only=True,
            )
            log.info(
                "faster-whisper 最终模型就绪: %.1fs (compute=%s, threads=%s)",
                time.perf_counter() - t0,
                self.compute_type,
                self.num_threads,
            )
        except Exception:
            log.exception("faster-whisper 最终模型加载失败")
            self.whisper = None

    def _load_fast(self) -> None:
        from faster_whisper import WhisperModel

        t0 = time.perf_counter()
        try:
            fast_dir = resolve_whisper_dir(self.fast_model_dir or "")
            log.info("加载快速最终模型: %s", fast_dir)
            self.fast_whisper = WhisperModel(
                str(fast_dir),
                device="cpu",
                compute_type=self.compute_type,
                cpu_threads=self.num_threads,
                num_workers=1,
                local_files_only=True,
            )
            log.info("快速最终模型就绪: %.1fs", time.perf_counter() - t0)
        except Exception:
            log.exception("快速最终模型加载失败，将回退到预览模型")
            self.fast_whisper = None

    def _load_preview(self) -> None:
        from faster_whisper import WhisperModel

        t0 = time.perf_counter()
        try:
            preview_dir = resolve_whisper_dir(self.preview_model_dir or "")
            log.info("加载预览模型: %s", preview_dir)
            self.preview_whisper = WhisperModel(
                str(preview_dir),
                device="cpu",
                compute_type=self.compute_type,
                cpu_threads=self.num_threads,
                num_workers=1,
                local_files_only=True,
            )
            log.info("预览模型就绪: %.1fs", time.perf_counter() - t0)
        except Exception:
            log.exception("预览模型加载失败，实时预览将不可用")
            self.preview_whisper = None

    # ---- final transcription -------------------------------------------
    def transcribe_final(self, audio: np.ndarray) -> str:
        audio = np.asarray(audio, dtype=np.float32)
        if len(audio) == 0:
            return ""
        language = self._whisper_language()
        prompt = None
        duration = len(audio) / 16000

        if (
            self.use_high_accuracy
            and self.ov_large is None
            and self.use_openvino
            and ov_available()
        ):
            self._load_ov_large()
        ov_pipe = self.ov_large if self.use_high_accuracy else self.ov_small
        if ov_pipe is None and self.use_high_accuracy:
            ov_pipe = self.ov_small
        if ov_pipe is not None:
            if not has_speech(audio):
                log.info("最终识别：VAD 未检测到语音")
                return ""
            label = "ov-large" if ov_pipe is self.ov_large else "ov-small"
            try:
                with self._lock:
                    text, elapsed = ov_pipe.transcribe(audio, language, prompt)
            except Exception:
                log.exception("OpenVINO 最终识别失败，回退 faster-whisper")
            else:
                text = _finish_text(text, self.language, self.auto_punctuation)
                log.info(
                    "Whisper 最终完成 (%s): %.2fs 音频 / %.2fs 推理 (RTF %.2f) | %r",
                    label,
                    duration,
                    elapsed,
                    elapsed / duration if duration else 0.0,
                    text,
                )
                return text

        # Fallback: faster-whisper.
        if self.use_high_accuracy:
            if self.whisper is None:
                self._load_whisper_final()
            model = self.whisper or self.fast_whisper or self.preview_whisper
        else:
            model = self.fast_whisper or self.preview_whisper or self.whisper
        if model is None:
            raise RuntimeError("最终模型尚未加载")
        if not has_speech(audio):
            log.info("最终识别：VAD 未检测到语音")
            return ""

        with self._lock:
            t0 = time.perf_counter()
            segments, _info = model.transcribe(
                audio,
                language=language,
                beam_size=1,
                best_of=1,
                without_timestamps=True,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                temperature=0.0,
                initial_prompt=prompt,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300, "speech_pad_ms": 100},
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
            elapsed = time.perf_counter() - t0

        text = _finish_text(text, self.language, self.auto_punctuation)
        log.info(
            "Whisper 最终完成 (%s): %.2fs 音频 / %.2fs 推理 (RTF %.2f) | %r",
            "high" if model is self.whisper else "fast",
            duration,
            elapsed,
            elapsed / duration if duration else 0.0,
            text,
        )
        return text

    def transcribe(self, audio: np.ndarray) -> str:
        return self.transcribe_final(audio)

    # ---- live preview ---------------------------------------------------
    def transcribe_preview(self, audio: np.ndarray) -> str:
        audio = np.asarray(audio, dtype=np.float32)
        if len(audio) == 0:
            return ""
        # Use the whole utterance (up to the 60s recording cap).  A sliding
        # 8s window would omit the earlier prefix, which would make live
        # typing backspace and retype everything on every update.
        max_samples = 60 * 16000
        if len(audio) > max_samples:
            audio = audio[-max_samples:]
        language = self._whisper_language()
        prompt = None
        duration = len(audio) / 16000

        if self.ov_base is not None:
            if not has_speech(audio):
                return ""
            try:
                with self._lock:
                    text, elapsed = self.ov_base.transcribe(audio, language, prompt)
            except Exception:
                log.exception("OpenVINO 预览失败，回退 faster-whisper")
            else:
                text = _finish_text(text, self.language, self.auto_punctuation)
                log.info(
                    "Whisper 预览完成: %.2fs 音频 / %.2fs 推理 (RTF %.2f)",
                    duration,
                    elapsed,
                    elapsed / duration if duration else 0.0,
                )
                return text

        if self.preview_whisper is None:
            return ""
        if not has_speech(audio):
            return ""
        t0 = time.perf_counter()
        with self._lock:
            segments, _info = self.preview_whisper.transcribe(
                audio,
                language=language,
                beam_size=1,
                best_of=1,
                without_timestamps=True,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                temperature=0.0,
                initial_prompt=prompt,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300, "speech_pad_ms": 100},
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        elapsed = time.perf_counter() - t0
        text = _finish_text(text, self.language, self.auto_punctuation)
        log.info(
            "Whisper 预览完成: %.2fs 音频 / %.2fs 推理 (RTF %.2f)",
            duration,
            elapsed,
            elapsed / duration if duration else 0.0,
        )
        return text

    # ---- language mapping ----------------------------------------------
    def _whisper_language(self) -> str | None:
        key = str(self.language).lower()
        if key == "auto":
            return None
        return _WHISPER_LANG.get(key, key.split("-")[0] or None)
