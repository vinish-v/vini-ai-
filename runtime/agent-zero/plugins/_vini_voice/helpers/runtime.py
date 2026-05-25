from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
import time
import wave
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from helpers import files, plugins
from helpers.print_style import PrintStyle
from plugins._kokoro_tts.helpers import runtime as tts_runtime
from plugins._whisper_stt.helpers import runtime as stt_runtime


PLUGIN_NAME = "_vini_voice"
CONFIG_PATH = "usr/plugins/_vini_voice/config.json"
SAMPLE_RATE = 16000
FRAME_MS = 20
FRAME_BYTES = int(SAMPLE_RATE * FRAME_MS / 1000) * 2

DEFAULT_CONFIG = {
    "vad_aggressiveness": 2,
    "min_voiced_ms": 100,
    "end_silence_ms": 360,
    "max_utterance_ms": 12000,
    "pre_roll_ms": 220,
}

_vad = None
_vad_error = ""
_preload_task: asyncio.Task | None = None


@dataclass
class VoiceSession:
    sid: str
    active: bool = False
    transcribing: bool = False
    voiced_ms: int = 0
    silence_ms: int = 0
    utterance_index: int = 0
    pre_roll: deque[bytes] = field(default_factory=deque)
    frames: list[bytes] = field(default_factory=list)
    started_at: float = field(default_factory=time.perf_counter)
    last_audio_at: float = field(default_factory=time.perf_counter)

    def reset_utterance(self) -> None:
        self.active = False
        self.voiced_ms = 0
        self.silence_ms = 0
        self.frames = []
        self.started_at = time.perf_counter()


def normalize_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    source = dict(DEFAULT_CONFIG)
    if isinstance(config, dict):
        source.update(config)

    normalized = dict(DEFAULT_CONFIG)
    for key in DEFAULT_CONFIG:
        try:
            normalized[key] = int(source.get(key, DEFAULT_CONFIG[key]))
        except (TypeError, ValueError):
            normalized[key] = DEFAULT_CONFIG[key]

    normalized["vad_aggressiveness"] = min(max(normalized["vad_aggressiveness"], 0), 3)
    normalized["min_voiced_ms"] = min(max(normalized["min_voiced_ms"], 40), 800)
    normalized["end_silence_ms"] = min(max(normalized["end_silence_ms"], 120), 1600)
    normalized["max_utterance_ms"] = min(max(normalized["max_utterance_ms"], 1500), 30000)
    normalized["pre_roll_ms"] = min(max(normalized["pre_roll_ms"], 0), 600)
    return normalized


def get_config() -> dict[str, Any]:
    try:
        config_path = files.get_abs_path(CONFIG_PATH)
        if files.exists(config_path):
            return normalize_config(json.loads(files.read_file(config_path)))
    except Exception:
        pass
    return normalize_config({})


def is_globally_enabled() -> bool:
    return plugins.determined_toggle_from_paths(
        True, reversed(plugins.get_plugin_roots(PLUGIN_NAME))
    )


def get_vad():
    global _vad, _vad_error

    if _vad is not None:
        return _vad

    try:
        import webrtcvad

        _vad = webrtcvad.Vad(int(get_config()["vad_aggressiveness"]))
        _vad_error = ""
        return _vad
    except Exception as exc:
        _vad_error = str(exc)
        raise RuntimeError(
            "Vini Voice VAD is unavailable. Install the webrtcvad-wheels package in the runtime image."
        ) from exc


def status() -> dict[str, Any]:
    vad_available = False
    vad_error = _vad_error
    try:
        get_vad()
        vad_available = True
        vad_error = ""
    except Exception as exc:
        vad_error = str(exc)

    return {
        "enabled": is_globally_enabled(),
        "sample_rate": SAMPLE_RATE,
        "frame_ms": FRAME_MS,
        "frame_bytes": FRAME_BYTES,
        "vad": {
            "provider": "webrtcvad",
            "available": vad_available,
            "error": vad_error,
        },
        "stt": {
            "enabled": stt_runtime.is_globally_enabled(),
            "loaded_model": stt_runtime.get_loaded_model_name(),
        },
        "tts": tts_runtime.get_runtime_status(),
        "config": get_config(),
    }


async def preload() -> dict[str, Any]:
    start_preload_background()
    await _preload_task
    return status()


def start_preload_background() -> dict[str, Any]:
    global _preload_task

    get_vad()

    if _preload_task is None or _preload_task.done():
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return status()
        _preload_task = loop.create_task(_preload_speech_models())
    return status()


async def _preload_speech_models() -> None:
    stt_cfg = stt_runtime.get_config()
    results = await asyncio.gather(
        stt_runtime.preload(str(stt_cfg["model_size"])),
        tts_runtime.preload(),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            PrintStyle.error(f"[vini_voice] preload failed: {result}")


def decode_pcm_frame(frame_b64: str) -> list[bytes]:
    try:
        payload = base64.b64decode(str(frame_b64 or ""), validate=True)
    except binascii.Error as exc:
        raise ValueError("Invalid PCM frame payload") from exc

    if not payload:
        return []

    frames = []
    for offset in range(0, len(payload), FRAME_BYTES):
        frame = payload[offset : offset + FRAME_BYTES]
        if len(frame) == FRAME_BYTES:
            frames.append(frame)
    return frames


def analyze_frame(session: VoiceSession, frame: bytes) -> dict[str, Any] | None:
    cfg = get_config()
    vad = get_vad()
    vad.set_mode(int(cfg["vad_aggressiveness"]))

    is_speech = bool(vad.is_speech(frame, SAMPLE_RATE))
    session.last_audio_at = time.perf_counter()

    max_pre_roll_frames = max(0, int(cfg["pre_roll_ms"] / FRAME_MS))
    if not session.active:
        if max_pre_roll_frames:
            session.pre_roll.append(frame)
            while len(session.pre_roll) > max_pre_roll_frames:
                session.pre_roll.popleft()

        if not is_speech:
            return {"type": "silence", "speech": False}

        session.active = True
        session.started_at = time.perf_counter()
        session.frames = list(session.pre_roll)
        session.pre_roll.clear()
        session.frames.append(frame)
        session.voiced_ms = FRAME_MS
        session.silence_ms = 0
        return {"type": "speech_start", "speech": True}

    session.frames.append(frame)
    if is_speech:
        session.voiced_ms += FRAME_MS
        session.silence_ms = 0
    else:
        session.silence_ms += FRAME_MS

    elapsed_ms = int((time.perf_counter() - session.started_at) * 1000)
    if (
        session.silence_ms >= int(cfg["end_silence_ms"])
        and session.voiced_ms >= int(cfg["min_voiced_ms"])
    ):
        return {"type": "speech_end", "speech": False, "elapsed_ms": elapsed_ms}

    if elapsed_ms >= int(cfg["max_utterance_ms"]):
        return {"type": "speech_end", "speech": False, "elapsed_ms": elapsed_ms, "reason": "max_utterance"}

    return {
        "type": "speech" if is_speech else "silence",
        "speech": is_speech,
        "elapsed_ms": elapsed_ms,
    }


def consume_utterance(session: VoiceSession) -> tuple[int, str]:
    session.utterance_index += 1
    utterance_id = session.utterance_index
    frames = list(session.frames)
    session.reset_utterance()
    return utterance_id, pcm_to_wav_b64(frames)


def pcm_to_wav_b64(frames: list[bytes]) -> str:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(frames))
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


async def transcribe_utterance(wav_b64: str) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        result = await stt_runtime.transcribe(wav_b64, mime_type="audio/wav")
    except ValueError as exc:
        if str(exc) != stt_runtime.NO_SPEECH_ERROR:
            raise
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        PrintStyle.info(f"[vini_voice] STT finished in {elapsed_ms}ms text='' reason=no_speech")
        return {
            "text": "",
            "language": "",
            "elapsed_ms": elapsed_ms,
        }

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    text = str(result.get("text") or "").strip()
    PrintStyle.info(f"[vini_voice] STT finished in {elapsed_ms}ms text={text!r}")
    return {
        "text": text,
        "language": str(result.get("language") or "").strip(),
        "elapsed_ms": elapsed_ms,
    }
