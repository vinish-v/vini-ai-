from __future__ import annotations

import asyncio
from typing import Any, ClassVar

from helpers.print_style import PrintStyle
from helpers.ws import WsHandler
from helpers.ws_manager import WsResult
from plugins._vini_voice.helpers import runtime


class WsVoice(WsHandler):
    _sessions: ClassVar[dict[str, runtime.VoiceSession]] = {}
    _tasks: ClassVar[dict[tuple[str, int], asyncio.Task[None]]] = {}

    @classmethod
    def requires_auth(cls) -> bool:
        return True

    @classmethod
    def requires_csrf(cls) -> bool:
        return False

    async def on_connect(self, sid: str) -> None:
        self._sessions[sid] = runtime.VoiceSession(sid=sid)
        PrintStyle.debug(f"[vini_voice] connected: {sid}")

    async def on_disconnect(self, sid: str) -> None:
        self._sessions.pop(sid, None)
        for key, task in list(self._tasks.items()):
            if key[0] == sid:
                task.cancel()
                self._tasks.pop(key, None)
        PrintStyle.debug(f"[vini_voice] disconnected: {sid}")

    async def process(
        self,
        event: str,
        data: dict[str, Any],
        sid: str,
    ) -> dict[str, Any] | WsResult | None:
        if event == "vini_voice_status":
            return runtime.status()

        if event == "vini_voice_start":
            return await self._handle_start(sid)

        if event == "vini_voice_stop":
            self._sessions[sid] = runtime.VoiceSession(sid=sid)
            return {"status": "stopped"}

        if event == "vini_voice_audio":
            await self._handle_audio(data, sid)
            return None

        return None

    async def _handle_start(self, sid: str) -> dict[str, Any] | WsResult:
        if not runtime.is_globally_enabled():
            return WsResult.error(code="DISABLED", message="Vini Voice plugin is disabled")

        self._sessions[sid] = runtime.VoiceSession(sid=sid)
        try:
            status = runtime.start_preload_background()
        except Exception as exc:
            return WsResult.error(code="VOICE_PRELOAD_FAILED", message=str(exc))

        await self.emit_to(
            sid,
            "vini_voice_event",
            {
                "type": "ready",
                "status": status,
            },
        )
        return {"status": "ready", "runtime": status}

    async def _handle_audio(self, data: dict[str, Any], sid: str) -> None:
        session = self._sessions.get(sid)
        if session is None or session.transcribing:
            return

        try:
            frames = runtime.decode_pcm_frame(str(data.get("pcm") or ""))
        except Exception as exc:
            await self.emit_to(
                sid,
                "vini_voice_event",
                {"type": "error", "error": str(exc)},
            )
            return

        for frame in frames:
            result = runtime.analyze_frame(session, frame)
            if not result:
                continue

            if result["type"] == "speech_start":
                await self.emit_to(
                    sid,
                    "vini_voice_event",
                    {"type": "speech_start"},
                )

            if result["type"] == "speech_end":
                utterance_id, wav_b64 = runtime.consume_utterance(session)
                await self.emit_to(
                    sid,
                    "vini_voice_event",
                    {
                        "type": "speech_end",
                        "utterance_id": utterance_id,
                        "elapsed_ms": result.get("elapsed_ms"),
                        "reason": result.get("reason") or "silence",
                    },
                )
                task = asyncio.create_task(
                    self._transcribe_and_emit(sid, utterance_id, wav_b64)
                )
                self._tasks[(sid, utterance_id)] = task

    async def _transcribe_and_emit(self, sid: str, utterance_id: int, wav_b64: str) -> None:
        session = self._sessions.get(sid)
        if session:
            session.transcribing = True

        try:
            await self.emit_to(
                sid,
                "vini_voice_event",
                {"type": "transcribing", "utterance_id": utterance_id},
            )
            result = await runtime.transcribe_utterance(wav_b64)
            text = result["text"]
            if not text:
                await self.emit_to(
                    sid,
                    "vini_voice_event",
                    {
                        "type": "no_speech",
                        "utterance_id": utterance_id,
                        "elapsed_ms": result["elapsed_ms"],
                    },
                )
                return

            await self.emit_to(
                sid,
                "vini_voice_event",
                {
                    "type": "transcript",
                    "utterance_id": utterance_id,
                    "text": text,
                    "language": result["language"],
                    "elapsed_ms": result["elapsed_ms"],
                },
            )
        except Exception as exc:
            PrintStyle.error(f"[vini_voice] transcription failed: {exc}")
            await self.emit_to(
                sid,
                "vini_voice_event",
                {
                    "type": "error",
                    "utterance_id": utterance_id,
                    "error": str(exc),
                },
            )
        finally:
            if session:
                session.transcribing = False
            self._tasks.pop((sid, utterance_id), None)
