from __future__ import annotations

import json
import zipfile

from plugins._vini_app_builder.helpers import builder


def configure_tmp_builder(monkeypatch, tmp_path):
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


def test_create_project_writes_real_vite_files_and_manifest(monkeypatch, tmp_path):
    configure_tmp_builder(monkeypatch, tmp_path)

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
    assert (project_dir / "src" / "main.tsx").is_file()
    assert "vite" in (project_dir / "package.json").read_text(encoding="utf-8")


def test_write_file_is_project_scoped_and_export_skips_runtime_artifacts(monkeypatch, tmp_path):
    configure_tmp_builder(monkeypatch, tmp_path)
    project = builder.create_project(name="Export Site", prompt="Export proof")["project"]
    project_id = project["project_id"]

    write_result = builder.write_file(project_id, "src/extra.ts", "export const proof = true;\n")
    assert write_result["ok"] is True

    blocked = builder.write_file(project_id, "../escape.txt", "bad")
    assert blocked["ok"] is False

    project_dir = tmp_path / "projects" / project_id
    (project_dir / "node_modules").mkdir()
    (project_dir / "node_modules" / "ignored.txt").write_text("ignored", encoding="utf-8")
    export_result = builder.export_project(project_id)
    assert export_result["ok"] is True

    with zipfile.ZipFile(export_result["export_path"]) as archive:
        names = set(archive.namelist())

    assert "src/extra.ts" in names
    assert builder.MANIFEST_NAME in names
    assert "node_modules/ignored.txt" not in names
    assert builder.LOG_NAME not in names
