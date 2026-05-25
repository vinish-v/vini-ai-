from helpers.api import ApiHandler, Request, Response
from plugins._kokoro_tts.helpers import runtime


class Preload(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        if not runtime.is_globally_enabled():
            return Response(status=409, response="Kokoro TTS plugin is disabled")

        try:
            await runtime.preload()
            return {
                "success": True,
                "ready": await runtime.is_downloaded(),
                "runtime": runtime.get_runtime_status(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
