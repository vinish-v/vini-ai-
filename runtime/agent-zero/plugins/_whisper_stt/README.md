# Whisper STT

Built-in speech-to-text plugin backed by Whisper.

## Responsibilities

- Registers Whisper as the active STT provider when the plugin is enabled.
- Owns the microphone runtime, device selector UI, message delivery mode, and plugin APIs.
- Keeps dependency installation and model bootstrap on the Docker/bootstrap path.

## Config

- `model_size`: Whisper model name
- `language`: language hint or `auto`
- `message_mode`: `send` to send final transcriptions immediately, or `draft` to leave them in the composer
- `silence_threshold`: frontend threshold before recording starts
- `silence_duration`: silence window before waiting state
- `waiting_timeout`: delay before transcription dispatch

The browser microphone path targets sub-2-second local turn latency by sending
16 kHz PCM WAV to the runtime when Web Audio capture is available. WebM remains
as a compatibility fallback for browsers that cannot provide the PCM capture
path.

## API

- `POST /api/plugins/_whisper_stt/transcribe`
- `POST /api/plugins/_whisper_stt/status`
