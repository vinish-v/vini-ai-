from __future__ import annotations


def install_route_hooks() -> None:
    from helpers.ui_server import UiServerRuntime

    if getattr(UiServerRuntime, "_vini_app_builder_route_hooks_installed", False):
        return

    original_register_http_routes = UiServerRuntime.register_http_routes

    def register_http_routes(self):
        result = original_register_http_routes(self)
        from plugins._vini_app_builder.helpers.routes import register_routes

        register_routes(self.webapp)
        return result

    UiServerRuntime.register_http_routes = register_http_routes
    UiServerRuntime._vini_app_builder_route_hooks_installed = True
