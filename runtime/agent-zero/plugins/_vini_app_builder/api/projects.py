from __future__ import annotations

from helpers.api import ApiHandler, Request, Response
from plugins._vini_app_builder.helpers.builder import handle_action


class Projects(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        return handle_action(input or {})
