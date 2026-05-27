from __future__ import annotations

import json
import importlib
import sys
import types
import zipfile
from pathlib import Path


import pytest


def install_builder_import_stubs(monkeypatch):
    flask_stub = types.ModuleType("flask")
    flask_stub.Response = object
    flask_stub.request = types.SimpleNamespace(query_string=b"", method="GET")
    monkeypatch.setitem(sys.modules, "flask", flask_stub)

    helpers_stub = types.ModuleType("helpers")
    files_stub = types.ModuleType("helpers.files")
    plugins_stub = types.ModuleType("helpers.plugins")
    files_stub.get_abs_path = lambda *parts: str(Path.cwd().joinpath(*parts))
    plugins_stub.get_plugin_config = lambda *_args, **_kwargs: {}
    helpers_stub.files = files_stub
    helpers_stub.plugins = plugins_stub
    monkeypatch.setitem(sys.modules, "helpers", helpers_stub)
    monkeypatch.setitem(sys.modules, "helpers.files", files_stub)
    monkeypatch.setitem(sys.modules, "helpers.plugins", plugins_stub)


@pytest.fixture()
def builder_module(monkeypatch):
    try:
        return importlib.import_module("plugins._vini_app_builder.helpers.builder")
    except ModuleNotFoundError as exc:
        if exc.name not in {"flask", "simpleeval"}:
            raise
        install_builder_import_stubs(monkeypatch)
        for name in [
            "plugins._vini_app_builder.helpers",
            "plugins._vini_app_builder.helpers.builder",
        ]:
            sys.modules.pop(name, None)
        return importlib.import_module("plugins._vini_app_builder.helpers.builder")


def configure_tmp_builder(builder, monkeypatch, tmp_path):
    config = {
        "enabled": True,
        "projects_root": str(tmp_path / "projects"),
        "exports_root": str(tmp_path / "exports"),
        "preview_port_start": 43100,
        "preview_port_end": 43109,
        "command_timeout_seconds": 20,
        "max_response_chars": 20000,
    }
    monkeypatch.setattr(builder, "_config", lambda: config)
    return config


def test_create_project_writes_real_vite_files_and_manifest(builder_module, monkeypatch, tmp_path):
    builder = builder_module
    configure_tmp_builder(builder, monkeypatch, tmp_path)

    result = builder.create_project(
        name="Revenue Ops Dashboard",
        prompt="Build a dashboard landing page with metrics and proof sections.",
    )

    assert result["ok"] is True
    project = result["project"]
    project_dir = tmp_path / "projects" / project["project_id"]
    manifest = json.loads((project_dir / builder.MANIFEST_NAME).read_text(encoding="utf-8"))

    assert manifest["framework"] == "vite-react-ts"
    assert manifest["status"] == "created"
    assert (project_dir / "package.json").is_file()
    assert (project_dir / "server.mjs").is_file()
    assert (project_dir / "src" / "main.tsx").is_file()
    package_json = json.loads((project_dir / "package.json").read_text(encoding="utf-8"))
    assert "vite" in package_json["dependencies"]
    assert "express" in package_json["dependencies"]
    assert "framer-motion" in package_json["dependencies"]
    assert "three" in package_json["dependencies"]
    assert package_json["scripts"]["dev"] == "node server.mjs"


def test_write_file_is_project_scoped_and_export_skips_runtime_artifacts(builder_module, monkeypatch, tmp_path):
    builder = builder_module
    configure_tmp_builder(builder, monkeypatch, tmp_path)
    project = builder.create_project(name="Export Site", prompt="Export proof")["project"]
    project_id = project["project_id"]

    write_result = builder.write_file(project_id, "src/extra.ts", "export const proof = true;\n")
    assert write_result["ok"] is True

    blocked = builder.write_file(project_id, "../escape.txt", "bad")
    assert blocked["ok"] is False

    project_dir = tmp_path / "projects" / project_id
    (project_dir / "node_modules").mkdir()
    (project_dir / "node_modules" / "ignored.txt").write_text("ignored", encoding="utf-8")
    (project_dir / ".vini-data").mkdir()
    (project_dir / ".vini-data" / "reservations.json").write_text("[]", encoding="utf-8")
    export_result = builder.export_project(project_id)
    assert export_result["ok"] is True

    with zipfile.ZipFile(export_result["export_path"]) as archive:
        names = set(archive.namelist())

    assert f"{project_id}/src/extra.ts" in names
    assert f"{project_id}/{builder.MANIFEST_NAME}" in names
    assert "node_modules/ignored.txt" not in names
    assert f"{project_id}/.vini-data/reservations.json" not in names
    assert builder.LOG_NAME not in names
