from __future__ import annotations

import threading
from typing import Any

from helpers.extension import Extension
from helpers.print_style import PrintStyle
from helpers import virtual_desktop_routes
from plugins._desktop import hooks
from plugins._desktop.helpers import desktop_session


_startup_preparation_thread: threading.Thread | None = None


class DesktopStartup(Extension):
    def execute(self, **kwargs):
        virtual_desktop_routes.install_route_hooks()
        _start_background_runtime_preparation()


def _start_background_runtime_preparation() -> threading.Thread:
    global _startup_preparation_thread

    if _startup_preparation_thread and _startup_preparation_thread.is_alive():
        return _startup_preparation_thread

    _startup_preparation_thread = threading.Thread(
        target=_prepare_runtime_safely,
        name="a0-desktop-runtime-preparation",
        daemon=True,
    )
    _startup_preparation_thread.start()
    return _startup_preparation_thread


def _prepare_runtime_safely() -> None:
    try:
        _log_runtime_preparation_result(hooks.cleanup_stale_runtime_state())
    except Exception as exc:
        PrintStyle.warning("Desktop runtime preparation failed:", exc)
        return
    try:
        _start_desktop_session_safely()
    except Exception as exc:
        PrintStyle.warning("Vini AI Computer startup failed:", exc)


def _log_runtime_preparation_result(result: dict[str, Any]) -> None:
    if result.get("errors"):
        PrintStyle.warning("Desktop runtime preparation reported errors:", result["errors"])
    elif result.get("warnings"):
        PrintStyle.warning("Desktop runtime preparation reported warnings:", result["warnings"])
    elif result.get("installed") or result.get("removed") or result.get("migrated"):
        PrintStyle.info("Desktop runtime prepared:", result)


def _start_desktop_session_safely() -> None:
    desktop = desktop_session.get_manager().ensure_system_desktop()
    if not desktop.get("available"):
        PrintStyle.warning(
            "Vini AI Computer startup reported unavailable desktop:",
            desktop.get("error") or desktop.get("status") or desktop,
        )
        return
    PrintStyle.info(
        "Vini AI Computer started:",
        {
            "session_id": desktop.get("session_id"),
            "url": desktop.get("url"),
            "display": desktop.get("display"),
        },
    )
