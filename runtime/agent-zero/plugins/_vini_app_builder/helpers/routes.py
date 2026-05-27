from __future__ import annotations

from flask import Flask
from helpers.api import requires_auth


def register_routes(app: Flask) -> None:
    if getattr(app, "_vini_app_builder_routes_registered", False):
        return

    from plugins._vini_app_builder.helpers import builder
    preview_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]

    @requires_auth
    async def preview_root(project_id: str):
        return builder.proxy_preview(project_id, "")

    @requires_auth
    async def preview_path(project_id: str, subpath: str):
        return builder.proxy_preview(project_id, subpath)

    @requires_auth
    async def export_project(project_id: str):
        return builder.download_export(project_id)

    @requires_auth
    async def qa_artifact(project_id: str, subpath: str):
        return builder.serve_qa_artifact(project_id, subpath)

    app.add_url_rule(
        "/vini-preview/<project_id>/",
        "vini_app_builder_preview_root",
        preview_root,
        methods=preview_methods,
    )
    app.add_url_rule(
        "/vini-preview/<project_id>/<path:subpath>",
        "vini_app_builder_preview_path",
        preview_path,
        methods=preview_methods,
    )
    app.add_url_rule(
        "/vini-builder/export/<project_id>",
        "vini_app_builder_export",
        export_project,
        methods=["GET"],
    )
    app.add_url_rule(
        "/vini-builder/qa/<project_id>/<path:subpath>",
        "vini_app_builder_qa_artifact",
        qa_artifact,
        methods=["GET"],
    )
    app._vini_app_builder_routes_registered = True
