"""Configuration for Voxa — private, local voice input for Windows."""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import shutil
import sys
from pathlib import Path
from typing import Any

FROZEN = bool(getattr(sys, "frozen", False))
if FROZEN:
    APP_DIR = Path(sys.executable).resolve().parent
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "Voxa"
    LEGACY_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", str(APP_DIR))) / "VoiceIn"
else:
    APP_DIR = Path(__file__).resolve().parents[1]
    DATA_DIR = APP_DIR
    LEGACY_DATA_DIR = None
CONFIG_PATH = DATA_DIR / "config.json"
LOG_DIR = DATA_DIR / "logs"

if FROZEN:
    MODEL_ROOT = APP_DIR / "models"
    DEFAULTS: dict[str, Any] = {
        "model_dir": "",
        "preview_model_dir": "",
        "fast_model_dir": "",
        "use_openvino": True,
        "ov_device": "CPU",
        "ov_model_dir": str(MODEL_ROOT / "whisper-large-v3-turbo-int4-ov"),
        "ov_fast_model_dir": str(MODEL_ROOT / "whisper-small-int4-ov"),
        "ov_preview_model_dir": str(MODEL_ROOT / "whisper-base-int4-ov"),
        "high_accuracy": False,
        "language": "zh",
        "hotkey": "win+h",
        "input_device": None,
        "num_threads": 4,
        "compute_type": "int8",
        "live_preview": True,
        "auto_stop": True,
        "auto_stop_silence_ms": 1800,
        "auto_speech_level": 0.08,
        "auto_min_speech_ms": 250,
        "autostart": True,
        "preview_interval_ms": 800,
        "auto_paste": True,
        "auto_punctuation": True,
        "theme": "teal",
        "max_record_seconds": 60,
        "min_record_seconds": 0.35,
        "insert_mode": "paste",
        "restore_clipboard": True,
        "native_fallback_hotkey_enabled": False,
    }
else:
    # Source checkouts keep models under ./models by default. Set
    # VOXA_MODEL_ROOT to use a shared model directory.
    MODEL_ROOT = Path(os.environ.get("VOXA_MODEL_ROOT", str(APP_DIR / "models")))
    DEFAULTS: dict[str, Any] = {
        "model_dir": str(MODEL_ROOT / "faster-whisper-large-v3-turbo"),
        "preview_model_dir": str(MODEL_ROOT / "faster-whisper-base"),
        "fast_model_dir": str(MODEL_ROOT / "faster-whisper-small"),
        "use_openvino": True,
        "ov_device": "CPU",
        "ov_model_dir": str(MODEL_ROOT / "whisper-large-v3-turbo-int4-ov"),
        "ov_fast_model_dir": str(MODEL_ROOT / "whisper-small-int4-ov"),
        "ov_preview_model_dir": str(MODEL_ROOT / "whisper-base-int4-ov"),
        "high_accuracy": False,
        "language": "zh",
        "hotkey": "win+h",
        "input_device": None,
        "num_threads": 4,
        "compute_type": "int8",
        "live_preview": True,
        "auto_stop": True,
        "auto_stop_silence_ms": 1800,
        "auto_speech_level": 0.08,
        "auto_min_speech_ms": 250,
        "autostart": True,
        "preview_interval_ms": 800,
        "auto_paste": True,
        "auto_punctuation": True,
        "theme": "teal",
        "max_record_seconds": 60,
        "min_record_seconds": 0.35,
        "insert_mode": "paste",
        "restore_clipboard": True,
        "native_fallback_hotkey_enabled": False,
    }


def _migrate_legacy_config() -> None:
    """Carry settings over from the pre-rename VoiceIn install once."""
    if not FROZEN or LEGACY_DATA_DIR is None:
        return
    if CONFIG_PATH.exists():
        return
    legacy = LEGACY_DATA_DIR / "config.json"
    if not legacy.exists():
        return
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, CONFIG_PATH)
        logging.getLogger("voxa").info("已迁移旧版配置: %s", legacy)
    except Exception:
        logging.getLogger("voxa").exception("迁移旧版配置失败")


def _normalize_bundled_models(cfg: dict[str, Any]) -> None:
    """Always prefer the models shipped next to the installed executable.

    Older builds could leave absolute paths pointing at a developer's dist/
    folder. Those paths may still exist after an upgrade, so merely checking
    Path.exists() is not enough.
    """
    if not FROZEN:
        return
    known = {
        "whisper-large-v3-turbo-int4-ov",
        "whisper-small-int4-ov",
        "whisper-base-int4-ov",
    }
    for key in ("ov_model_dir", "ov_fast_model_dir", "ov_preview_model_dir"):
        current = str(cfg.get(key) or "")
        name = Path(current).name
        bundled = MODEL_ROOT / name
        if name in known:
            cfg[key] = str(bundled)


def load_config() -> dict[str, Any]:
    _migrate_legacy_config()
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            logging.getLogger("voxa").exception("config.json 读取失败，使用默认配置")
    _normalize_bundled_models(cfg)
    return cfg


def save_config(cfg: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("voxa")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(threadName)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    # pythonw has no console: sys.stderr is None and StreamHandler would fail.
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(fmt)
        logger.addHandler(console)
    return logger
