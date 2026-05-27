from __future__ import annotations

import asyncio
import base64
import binascii
import io
import os
import tempfile
import warnings
import wave
from typing import Any

import numpy as np
import whisper

from helpers import files, plugins
from helpers.notification import (
    NotificationManager,
    NotificationPriority,
    NotificationType,
)
from helpers.print_style import PrintStyle
from plugins._whisper_stt.helpers import migration


warnings.filterwarnings("ignore", category=FutureWarning)


PLUGIN_NAME = "_whisper_stt"
PARAKEET_MODEL_DIR = "usr/models/parakeet-tdt-0.6b-v3-int8"
PARAKEET_MODEL_NAME = "nemo-parakeet-tdt-0.6b-v3"
DEFAULT_CONFIG = {
    "engine": "whisper",
    "model_size": "tiny",
    "language": "en",
    "message_mode": "send",
    "silence_threshold": 0.3,
    "silence_duration": 420,
    "waiting_timeout": 120,
}
VALID_ENGINES = {"parakeet", "whisper"}
VALID_MODEL_SIZES = {"tiny", "base", "small", "medium", "large", "turbo"}
VALID_MESSAGE_MODES = {"send", "draft"}
NO_SPEECH_ERROR = "No speech detected"
MIN_AUDIO_BYTES = 1400
MIN_AUDIO_SAMPLES = 1600
MIN_AUDIO_PEAK = 0.006
MIN_AUDIO_RMS = 0.0012

_whisper_model = None
_whisper_model_name = ""
_faster_whisper_model = None
_faster_whisper_model_name = ""
_faster_whisper_error = ""
_parakeet_model = None
_parakeet_loaded = False
_parakeet_error = ""
is_updating_model = False


def normalize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        return normalized

    engine = str(config.get("engine", normalized["engine"]) or "").strip().lower()
    if engine in VALID_ENGINES:
        normalized["engine"] = engine

    model_size = str(config.get("model_size", normalized["model_size"]) or "").strip()
    if model_size in VALID_MODEL_SIZES:
        normalized["model_size"] = model_size

    language = str(config.get("language", normalized["language"]) or "").strip()
    if language:
        normalized["language"] = language

    message_mode = (
        str(config.get("message_mode", normalized["message_mode"]) or "")
        .strip()
        .lower()
    )
    if message_mode in VALID_MESSAGE_MODES:
        normalized["message_mode"] = message_mode

    try:
        silence_threshold = float(
            config.get("silence_threshold", normalized["silence_threshold"])
        )
        normalized["silence_threshold"] = min(max(silence_threshold, 0.0), 1.0)
    except (TypeError, ValueError):
        pass

    try:
        silence_duration = int(
            config.get("silence_duration", normalized["silence_duration"])
        )
        if silence_duration > 0:
            normalized["silence_duration"] = silence_duration
    except (TypeError, ValueError):
        pass

    try:
        waiting_timeout = int(config.get("waiting_timeout", normalized["waiting_timeout"]))
        if waiting_timeout > 0:
            normalized["waiting_timeout"] = waiting_timeout
    except (TypeError, ValueError):
        pass

    return normalized


def get_config() -> dict[str, Any]:
    migration.ensure_config_seeded()
    config = migration.read_saved_config()
    return normalize_config(config)


def get_loaded_model_name() -> str:
    if _parakeet_loaded:
        return PARAKEET_MODEL_NAME
    if _faster_whisper_model is not None:
        return _faster_whisper_model_name
    return _whisper_model_name


def get_loaded_engine() -> str:
    if _parakeet_loaded:
        return "parakeet"
    if _faster_whisper_model is not None:
        return "faster-whisper"
    if _whisper_model is not None:
        return "whisper"
    return ""


def get_parakeet_model_path() -> str:
    return files.get_abs_path(PARAKEET_MODEL_DIR)


def is_parakeet_available() -> bool:
    model_path = get_parakeet_model_path()
    return all(
        files.exists(os.path.join(model_path, filename))
        for filename in (
            "config.json",
            "decoder_joint-model.int8.onnx",
            "encoder-model.int8.onnx",
            "nemo128.onnx",
            "vocab.txt",
        )
    )


def get_parakeet_status() -> dict[str, Any]:
    return {
        "available": is_parakeet_available(),
        "loaded": _parakeet_loaded,
        "model": PARAKEET_MODEL_NAME,
        "path": get_parakeet_model_path(),
        "error": _parakeet_error,
    }


def faster_whisper_available() -> bool:
    try:
        import faster_whisper  # noqa: F401

        return True
    except Exception:
        return False


def get_faster_whisper_status() -> dict[str, Any]:
    return {
        "available": faster_whisper_available(),
        "loaded": _faster_whisper_model is not None,
        "model": _faster_whisper_model_name,
        "error": _faster_whisper_error,
    }


def is_globally_enabled() -> bool:
    return plugins.determined_toggle_from_paths(
        True, reversed(plugins.get_plugin_roots(PLUGIN_NAME))
    )


async def preload(model_name: str | None = None, engine: str | None = None):
    cfg = get_config()
    resolved_engine = str(engine or cfg["engine"]).strip().lower()
    if resolved_engine == "parakeet":
        if is_parakeet_available():
            return await _preload_parakeet()
        PrintStyle.warning("Parakeet v3 model not found; falling back to Whisper STT preload.")

    resolved_model = str(model_name or cfg["model_size"])
    if faster_whisper_available():
        try:
            return await _preload_faster_whisper(resolved_model)
        except Exception as e:
            PrintStyle.warning(f"faster-whisper preload failed; falling back to Whisper: {e}")
    return await _preload_whisper(resolved_model)


async def _preload_parakeet():
    global _parakeet_model, _parakeet_loaded, _parakeet_error, is_updating_model

    while is_updating_model:
        await asyncio.sleep(0.1)

    try:
        is_updating_model = True
        if not _parakeet_model:
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Loading Parakeet v3 speech model...",
                display_time=99,
                group="stt-preload",
            )
            PrintStyle.standard(f"Loading Parakeet v3 model: {get_parakeet_model_path()}")
            try:
                import onnx_asr

                _parakeet_model = onnx_asr.load_model(
                    PARAKEET_MODEL_NAME,
                    path=get_parakeet_model_path(),
                    quantization="int8",
                )
                _parakeet_loaded = True
                _parakeet_error = ""
            except Exception as e:
                _parakeet_model = None
                _parakeet_loaded = False
                _parakeet_error = str(e)
                raise
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Parakeet v3 speech model loaded.",
                display_time=2,
                group="stt-preload",
            )
    finally:
        is_updating_model = False


async def _preload_whisper(model_name: str):
    global _whisper_model, _whisper_model_name, is_updating_model

    while is_updating_model:
        await asyncio.sleep(0.1)

    try:
        is_updating_model = True
        if not _whisper_model or _whisper_model_name != model_name:
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Loading Whisper model...",
                display_time=99,
                group="stt-preload",
            )
            PrintStyle.standard(f"Loading Whisper model: {model_name}")
            _whisper_model = whisper.load_model(
                name=model_name,
                download_root=files.get_abs_path("usr/models/whisper"),
            )
            _whisper_model_name = model_name
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Whisper model loaded.",
                display_time=2,
                group="stt-preload",
            )
    finally:
        is_updating_model = False


async def _preload_faster_whisper(model_name: str):
    global _faster_whisper_model, _faster_whisper_model_name, _faster_whisper_error, is_updating_model

    while is_updating_model:
        await asyncio.sleep(0.1)

    try:
        is_updating_model = True
        if not _faster_whisper_model or _faster_whisper_model_name != model_name:
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Loading faster-whisper model...",
                display_time=99,
                group="stt-preload",
            )
            PrintStyle.standard(f"Loading faster-whisper model: {model_name}")
            try:
                from faster_whisper import WhisperModel

                _faster_whisper_model = WhisperModel(
                    model_name,
                    device="cpu",
                    compute_type="int8",
                    download_root=files.get_abs_path("usr/models/faster-whisper"),
                )
                _faster_whisper_model_name = model_name
                _faster_whisper_error = ""
            except Exception as e:
                _faster_whisper_model = None
                _faster_whisper_model_name = ""
                _faster_whisper_error = str(e)
                raise
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "faster-whisper model loaded.",
                display_time=2,
                group="stt-preload",
            )
    finally:
        is_updating_model = False


async def is_downloading() -> bool:
    return is_updating_model


async def is_downloaded() -> bool:
    return (
        _parakeet_model is not None
        or _faster_whisper_model is not None
        or _whisper_model is not None
    )


async def transcribe(
    audio_bytes_b64: str,
    config: dict[str, Any] | None = None,
    *,
    mime_type: str = "audio/webm",
) -> dict[str, Any]:
    cfg = normalize_config(config or get_config())
    engine = str(cfg["engine"])
    language = _resolve_language(str(cfg["language"]))

    if engine == "parakeet" and is_parakeet_available():
        try:
            return await _transcribe_parakeet(audio_bytes_b64, mime_type=mime_type)
        except ValueError as e:
            if str(e) == NO_SPEECH_ERROR:
                raise
            PrintStyle.warning(f"Parakeet v3 STT rejected audio; falling back to Whisper: {e}")
        except Exception as e:
            PrintStyle.warning(f"Parakeet v3 STT failed; falling back to Whisper: {e}")

    model_size = str(cfg["model_size"])
    if faster_whisper_available():
        try:
            return await _transcribe_faster_whisper(
                model_size,
                audio_bytes_b64,
                language=language,
                mime_type=mime_type,
            )
        except ValueError:
            raise
        except Exception as e:
            PrintStyle.warning(f"faster-whisper STT failed; falling back to Whisper: {e}")

    return await _transcribe_whisper(
        model_size,
        audio_bytes_b64,
        language=language,
        mime_type=mime_type,
    )


async def _transcribe_parakeet(
    audio_bytes_b64: str,
    *,
    mime_type: str = "audio/webm",
) -> dict[str, Any]:
    audio_bytes, temp_path = _write_temp_audio(audio_bytes_b64, mime_type)

    try:
        decoded_audio = _load_audio(temp_path, mime_type, audio_bytes)
        if getattr(decoded_audio, "size", 0) < MIN_AUDIO_SAMPLES:
            raise ValueError(NO_SPEECH_ERROR)
        if _is_effectively_silent(decoded_audio):
            raise ValueError(NO_SPEECH_ERROR)

        await _preload_parakeet()
        result = _parakeet_model.recognize(decoded_audio, sample_rate=16000)  # type: ignore[union-attr]
        text = _normalize_parakeet_result(result)
        if not text.strip():
            raise ValueError(NO_SPEECH_ERROR)
        return {
            "text": text,
            "language": "auto",
            "segments": [],
            "engine": "parakeet",
            "model": PARAKEET_MODEL_NAME,
        }
    finally:
        _remove_temp_file(temp_path)


async def _transcribe_whisper(
    model_name: str,
    audio_bytes_b64: str,
    *,
    language: str | None = None,
    mime_type: str = "audio/webm",
) -> dict[str, Any]:
    audio_bytes, temp_path = _write_temp_audio(audio_bytes_b64, mime_type)

    try:
        decoded_audio = _load_audio(temp_path, mime_type, audio_bytes)
        if getattr(decoded_audio, "size", 0) < MIN_AUDIO_SAMPLES:
            raise ValueError(NO_SPEECH_ERROR)
        if _is_effectively_silent(decoded_audio):
            raise ValueError(NO_SPEECH_ERROR)

        await _preload_whisper(model_name)

        kwargs: dict[str, Any] = {"fp16": False}
        if language:
            kwargs["language"] = language

        result = _whisper_model.transcribe(temp_path, **kwargs)  # type: ignore[union-attr]
        if isinstance(result, dict):
            result["engine"] = "whisper"
            result["model"] = model_name
            return result
        return {}
    finally:
        _remove_temp_file(temp_path)


async def _transcribe_faster_whisper(
    model_name: str,
    audio_bytes_b64: str,
    *,
    language: str | None = None,
    mime_type: str = "audio/webm",
) -> dict[str, Any]:
    audio_bytes, temp_path = _write_temp_audio(audio_bytes_b64, mime_type)

    try:
        decoded_audio = _load_audio(temp_path, mime_type, audio_bytes)
        if getattr(decoded_audio, "size", 0) < MIN_AUDIO_SAMPLES:
            raise ValueError(NO_SPEECH_ERROR)
        if _is_effectively_silent(decoded_audio):
            raise ValueError(NO_SPEECH_ERROR)

        await _preload_faster_whisper(model_name)

        segments, info = _faster_whisper_model.transcribe(  # type: ignore[union-attr]
            temp_path,
            beam_size=1,
            language=language,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        normalized_segments = [
            {
                "start": float(getattr(segment, "start", 0.0)),
                "end": float(getattr(segment, "end", 0.0)),
                "text": str(getattr(segment, "text", "") or "").strip(),
            }
            for segment in segments
        ]
        text = " ".join(segment["text"] for segment in normalized_segments).strip()
        if not text:
            raise ValueError(NO_SPEECH_ERROR)
        return {
            "text": text,
            "language": str(getattr(info, "language", "") or "").strip(),
            "segments": normalized_segments,
            "engine": "faster-whisper",
            "model": model_name,
        }
    finally:
        _remove_temp_file(temp_path)


def _write_temp_audio(audio_bytes_b64: str, mime_type: str) -> tuple[bytes, str]:
    try:
        audio_bytes = base64.b64decode(audio_bytes_b64, validate=True)
    except binascii.Error as e:
        raise ValueError("Invalid audio payload") from e

    if len(audio_bytes) < MIN_AUDIO_BYTES:
        raise ValueError(NO_SPEECH_ERROR)

    suffix = _suffix_for_mime_type(mime_type)
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
        audio_file.write(audio_bytes)
        return audio_bytes, audio_file.name


def _remove_temp_file(temp_path: str):
    try:
        os.remove(temp_path)
    except Exception:
        pass


def _load_audio(temp_path: str, mime_type: str, audio_bytes: bytes):
    if _suffix_for_mime_type(mime_type) == ".wav":
        try:
            return _load_pcm_wav(audio_bytes)
        except Exception as e:
            PrintStyle.warning(f"Fast WAV decode failed; using ffmpeg audio decode: {e}")
    return whisper.load_audio(temp_path)


def _load_pcm_wav(audio_bytes: bytes):
    with wave.open(io.BytesIO(audio_bytes), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        frame_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if sample_width != 2:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    if frame_rate != 16000:
        raise ValueError(f"Unsupported WAV sample rate for fast path: {frame_rate}")

    return audio


def _normalize_parakeet_result(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        return str(result.get("text") or result.get("transcript") or "").strip()
    text = getattr(result, "text", None)
    if text is not None:
        return str(text).strip()
    return str(result or "").strip()


def _is_effectively_silent(decoded_audio: Any) -> bool:
    try:
        if getattr(decoded_audio, "size", 0) < MIN_AUDIO_SAMPLES:
            return True
        peak = float(abs(decoded_audio).max())
        rms = float((decoded_audio * decoded_audio).mean() ** 0.5)
        return peak < MIN_AUDIO_PEAK and rms < MIN_AUDIO_RMS
    except Exception:
        return False


def _resolve_language(language: str) -> str | None:
    value = language.strip().lower()
    if not value or value == "auto":
        return None
    return value


def _suffix_for_mime_type(mime_type: str) -> str:
    normalized = mime_type.split(";", 1)[0].strip().lower()
    if normalized == "audio/webm":
        return ".webm"
    if normalized == "audio/ogg":
        return ".ogg"
    if normalized in {"audio/wav", "audio/wave", "audio/x-wav"}:
        return ".wav"
    if normalized == "audio/mp4":
        return ".m4a"
    return ".webm"
