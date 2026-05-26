from __future__ import annotations

import shutil
import subprocess

from helpers.api import ApiHandler, Request, Response


def _read_tool_version(executable: str) -> tuple[str | None, str | None]:
    path = shutil.which(executable)
    if not path:
        return None, None

    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except Exception:
        return path, None

    version = (result.stdout or result.stderr or "").strip().splitlines()
    return path, version[0].strip() if version else None


class Status(ApiHandler):
    async def process(self, input: dict, request: Request) -> dict | Response:
        node_path, node_version = _read_tool_version("node")
        pnpm_path, pnpm_version = _read_tool_version("pnpm")

        return {
            "node": {
                "path": node_path,
                "version": node_version,
            },
            "pnpm": {
                "path": pnpm_path,
                "version": pnpm_version,
            },
        }
