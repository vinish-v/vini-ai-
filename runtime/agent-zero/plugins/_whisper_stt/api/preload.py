from helpers.api import ApiHandler, Request, Response
from plugins._whisper_stt.helpers import runtime


class Preload(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if not runtime.is_globally_enabled():
            return Response(status=409, response="Whisper STT plugin is disabled")

        config = runtime.get_config()
        model_name = str(input.get("model_size") or config["model_size"])

        try:
            await runtime.preload(model_name)
            return {
                "success": True,
                "model_size": model_name,
                "ready": await runtime.is_downloaded(),
                "loaded_model": runtime.get_loaded_model_name(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
