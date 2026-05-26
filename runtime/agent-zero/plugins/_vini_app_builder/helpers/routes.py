from __future__ import annotations

from flask import Flask
from helpers.api import requires_auth


def register_routes(app: Flask) -> None:
    if getattr(app, "_vini_app_builder_routes_registered", False):
        return

    from plugins._vini_app_builder.helpers import builder

    @requires_auth
    async def preview_root(project_id: str):
        return builder.proxy_preview(project_id, "")

    @requires_auth
    async def preview_path(project_id: str, subpath: str):
        return builder.proxy_preview(project_id, subpath)

    @requires_auth
    async def export_project(project_id: str):
        return builder.download_export(project_id)

    app.add_url_rule(
        "/vini-preview/<project_id>/",
        "vini_app_builder_preview_root",
        preview_root,
        methods=["GET"],
    )
    app.add_url_rule(
        "/vini-preview/<project_id>/<path:subpath>",
        "vini_app_builder_preview_path",
        preview_path,
        methods=["GET"],
    )
    app.add_url_rule(
        "/vini-builder/export/<project_id>",
        "vini_app_builder_export",
        export_project,
        methods=["GET"],
    )
    app._vini_app_builder_routes_registered = True
