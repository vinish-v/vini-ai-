from __future__ import annotations

import asyncio
import base64
import io
import os
import shutil
import warnings
from typing import Any

import soundfile as sf

from helpers import files, plugins
from helpers.notification import (
    NotificationManager,
    NotificationPriority,
    NotificationType,
)
from helpers.print_style import PrintStyle
from plugins._kokoro_tts.helpers import migration


warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)


PLUGIN_NAME = "_kokoro_tts"
DEFAULT_CONFIG = {
    "engine": "supertonic",
    "voice": "am_puck,am_onyx",
    "speed": 1.16,
    "supertonic_voice": "F1",
    "supertonic_steps": 6,
    "supertonic_language": "en",
}
NO_AUDIO_ERROR = "No audio generated"

_pipeline = None
_supertonic_tts = None
_supertonic_style = None
is_updating_model = False
supertonic_last_error = ""


def normalize_config(config: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(DEFAULT_CONFIG)
    if not isinstance(config, dict):
        return normalized

    voice = str(config.get("voice", normalized["voice"]) or "").strip()
    if voice:
        normalized["voice"] = voice

    engine = str(config.get("engine", normalized["engine"]) or "").strip().lower()
    if engine in {"supertonic", "kokoro"}:
        normalized["engine"] = engine

    supertonic_voice = str(
        config.get("supertonic_voice", normalized["supertonic_voice"]) or ""
    ).strip()
    if supertonic_voice:
        normalized["supertonic_voice"] = supertonic_voice

    supertonic_language = str(
        config.get("supertonic_language", normalized["supertonic_language"]) or ""
    ).strip()
    if supertonic_language:
        normalized["supertonic_language"] = supertonic_language

    try:
        speed = float(config.get("speed", normalized["speed"]))
        if speed > 0:
            normalized["speed"] = speed
    except (TypeError, ValueError):
        pass

    try:
        steps = int(config.get("supertonic_steps", normalized["supertonic_steps"]))
        if 4 <= steps <= 12:
            normalized["supertonic_steps"] = steps
    except (TypeError, ValueError):
        pass

    return normalized


def get_config() -> dict[str, Any]:
    config = plugins.get_plugin_config(PLUGIN_NAME) or {}
    return normalize_config(config)


def is_globally_enabled() -> bool:
    migration.ensure_migrated()
    return plugins.determined_toggle_from_paths(
        True, reversed(plugins.get_plugin_roots(PLUGIN_NAME))
    )


async def preload(config: dict[str, Any] | None = None):
    cfg = normalize_config(config or get_config())
    if cfg["engine"] == "supertonic":
        try:
            return await _preload_supertonic(str(cfg["supertonic_voice"]))
        except Exception as e:
            PrintStyle.error(f"Supertonic TTS preload failed, falling back to Kokoro: {e}")
    return await _preload()


async def _preload():
    global _pipeline, is_updating_model

    while is_updating_model:
        await asyncio.sleep(0.1)

    try:
        is_updating_model = True
        if not _pipeline:
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Loading Kokoro TTS model...",
                display_time=99,
                group="kokoro-preload",
            )
            PrintStyle.standard("Loading Kokoro TTS model...")
            from kokoro import KPipeline

            _pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Kokoro TTS model loaded.",
                display_time=2,
                group="kokoro-preload",
            )
    finally:
        is_updating_model = False


async def is_downloading() -> bool:
    return is_updating_model


async def is_downloaded() -> bool:
    return _pipeline is not None or _supertonic_tts is not None


def supertonic_available() -> bool:
    try:
        import supertonic  # noqa: F401

        return True
    except Exception:
        return False


def get_runtime_status() -> dict[str, Any]:
    version = ""
    error = ""
    try:
        import importlib.metadata

        version = importlib.metadata.version("supertonic")
    except Exception as e:
        error = str(e)

    return {
        "engine": "supertonic" if _supertonic_tts is not None else "kokoro",
        "supertonic": {
            "available": supertonic_available(),
            "ready": _supertonic_tts is not None,
            "version": version,
            "error": error or supertonic_last_error,
        },
        "kokoro": {
            "ready": _pipeline is not None,
        },
    }


async def synthesize_sentences(
    sentences: list[str], config: dict[str, Any] | None = None, *, fast: bool = False
) -> str:
    cfg = normalize_config(config or get_config())
    if fast:
        cfg["speed"] = max(float(cfg["speed"]), 1.2)
        cfg["supertonic_steps"] = min(int(cfg["supertonic_steps"]), 4)
    clean_sentences = _clean_sentences(sentences)
    if not clean_sentences:
        raise ValueError("No text to synthesize")

    if cfg["engine"] == "supertonic":
        try:
            return await _synthesize_sentences_supertonic(
                clean_sentences,
                voice=str(cfg["supertonic_voice"]),
                speed=float(cfg["speed"]),
                steps=int(cfg["supertonic_steps"]),
                lang=str(cfg["supertonic_language"]),
            )
        except Exception as e:
            PrintStyle.error(f"Supertonic TTS synthesis failed, falling back to Kokoro: {e}")

    return await _synthesize_sentences(
        clean_sentences,
        voice=str(cfg["voice"]),
        speed=float(cfg["speed"]),
    )


async def _preload_supertonic(voice: str):
    global _supertonic_tts, _supertonic_style, is_updating_model, supertonic_last_error

    while is_updating_model:
        await asyncio.sleep(0.1)

    try:
        is_updating_model = True
        if not _supertonic_tts:
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Loading Supertonic TTS model...",
                display_time=99,
                group="supertonic-preload",
            )
            PrintStyle.standard("Loading Supertonic TTS model...")
            from supertonic import TTS

            model_dir = files.get_abs_path("usr/models/supertonic")
            expected_config = os.path.join(model_dir, "onnx", "tts.json")
            if os.path.isdir(model_dir) and not os.path.isfile(expected_config):
                shutil.rmtree(model_dir, ignore_errors=True)

            _supertonic_tts = TTS(
                auto_download=True,
                model_dir=model_dir,
            )
            NotificationManager.send_notification(
                NotificationType.INFO,
                NotificationPriority.NORMAL,
                "Supertonic TTS model loaded.",
                display_time=2,
                group="supertonic-preload",
            )

        if not _supertonic_style:
            _supertonic_style = _supertonic_tts.get_voice_style(voice)
        supertonic_last_error = ""
    except Exception as e:
        supertonic_last_error = str(e)
        raise
    finally:
        is_updating_model = False


async def _synthesize_sentences_supertonic(
    sentences: list[str], *, voice: str, speed: float, steps: int, lang: str
) -> str:
    global _supertonic_style

    await _preload_supertonic(voice)

    combined_audio: list[float] = []
    sample_rate = int(getattr(_supertonic_tts, "sample_rate", 24000))
    style = _supertonic_style or _supertonic_tts.get_voice_style(voice)

    for sentence in sentences:
        text = sentence.strip()
        if len(text) < 2 or not any(character.isalnum() for character in text):
            continue
        wav, _duration = _supertonic_tts.synthesize(
            text=text,
            voice_style=style,
            total_steps=steps,
            speed=speed,
            max_chunk_length=120,
            silence_duration=0.08,
            lang=lang or "en",
            verbose=False,
        )
        try:
            if getattr(wav, "numel", lambda: 1)() == 0:
                continue
            audio = wav.squeeze().tolist()
        except Exception:
            audio = list(wav)
        combined_audio.extend(audio)

    if not combined_audio:
        raise ValueError(NO_AUDIO_ERROR)

    buffer = io.BytesIO()
    sf.write(buffer, combined_audio, sample_rate, format="WAV")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def _synthesize_sentences(
    sentences: list[str], *, voice: str, speed: float
) -> str:
    await _preload()

    combined_audio: list[float] = []

    try:
        for sentence in sentences:
            segments = _pipeline(sentence.strip(), voice=voice, speed=speed)  # type: ignore[misc]
            for segment in list(segments):
                audio_tensor = segment.audio
                if getattr(audio_tensor, "numel", lambda: 1)() == 0:
                    continue
                audio_numpy = audio_tensor.detach().cpu().numpy()  # type: ignore[union-attr]
                combined_audio.extend(audio_numpy.tolist())

        if not combined_audio:
            raise ValueError(NO_AUDIO_ERROR)

        buffer = io.BytesIO()
        sf.write(buffer, combined_audio, 24000, format="WAV")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        PrintStyle.error(f"Error in Kokoro TTS synthesis: {e}")
        raise


def _clean_sentences(sentences: list[str]) -> list[str]:
    cleaned: list[str] = []
    for sentence in sentences:
        text = " ".join(str(sentence or "").split())
        if text and any(character.isalnum() for character in text):
            cleaned.append(text)
    return cleaned
