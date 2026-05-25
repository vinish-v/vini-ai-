import importlib.metadata

from helpers.api import ApiHandler, Request, Response
from plugins._whisper_stt.helpers import migration, runtime


class Status(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        migration.ensure_config_seeded()

        whisper_package_version = ""
        whisper_package_error = ""
        faster_whisper_package_version = ""
        faster_whisper_package_error = ""
        onnx_asr_package_version = ""
        onnx_asr_package_error = ""
        try:
            whisper_package_version = importlib.metadata.version("openai-whisper")
        except Exception as e:
            whisper_package_error = str(e)
        try:
            faster_whisper_package_version = importlib.metadata.version("faster-whisper")
        except Exception as e:
            faster_whisper_package_error = str(e)
        try:
            onnx_asr_package_version = importlib.metadata.version("onnx-asr")
        except Exception as e:
            onnx_asr_package_error = str(e)

        return {
            "plugin": "_whisper_stt",
            "enabled": runtime.is_globally_enabled(),
            "config": runtime.get_config(),
            "model": {
                "ready": await runtime.is_downloaded(),
                "loading": await runtime.is_downloading(),
                "loaded_engine": runtime.get_loaded_engine(),
                "loaded_model": runtime.get_loaded_model_name(),
                "parakeet": runtime.get_parakeet_status(),
                "faster_whisper": runtime.get_faster_whisper_status(),
            },
            "package": {
                "version": faster_whisper_package_version or whisper_package_version,
                "error": faster_whisper_package_error or whisper_package_error,
                "whisper_version": whisper_package_version,
                "whisper_error": whisper_package_error,
                "faster_whisper_version": faster_whisper_package_version,
                "faster_whisper_error": faster_whisper_package_error,
                "onnx_asr_version": onnx_asr_package_version,
                "onnx_asr_error": onnx_asr_package_error,
            },
        }
