from __future__ import annotations

import base64
from pathlib import Path

import pytest

from plugins._windows_host_bridge.helpers import bridge_client


def test_import_host_file_copies_binary_into_vini_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge_client, "DEFAULT_IMPORT_DIR", tmp_path / "imports")
    monkeypatch.setattr(bridge_client.files, "get_base_dir", lambda: str(tmp_path))
    monkeypatch.setattr(bridge_client.files, "normalize_a0_path", lambda value: "/a0/" + str(Path(value).relative_to(tmp_path)).replace("\\", "/"))
    monkeypatch.setattr(bridge_client, "config", lambda agent=None: {"enabled": True})

    def fake_request(cfg, method, path, payload=None):
        assert path == "/file/read-binary"
        return {
            "ok": True,
            "path": r"C:\Users\HP\Documents\Book.xlsx",
            "name": "Book.xlsx",
            "contentBase64": base64.b64encode(b"xlsx-bytes").decode("ascii"),
        }

    monkeypatch.setattr(bridge_client, "request", fake_request)

    result = bridge_client.import_host_file(r"C:\Users\HP\Documents\Book.xlsx", register_office=False)

    assert result["ok"] is True
    assert result["local_path"] == "/a0/imports/Book.xlsx"
    assert (tmp_path / "imports" / "Book.xlsx").read_bytes() == b"xlsx-bytes"


def test_export_host_file_uses_binary_write_endpoint(tmp_path, monkeypatch):
    source = tmp_path / "documents" / "Deck.pptx"
    source.parent.mkdir()
    source.write_bytes(b"pptx-bytes")
    calls = []

    monkeypatch.setattr(bridge_client.files, "get_base_dir", lambda: str(tmp_path))
    monkeypatch.setattr(bridge_client.files, "normalize_a0_path", lambda value: "/a0/" + str(Path(value).relative_to(tmp_path)).replace("\\", "/"))
    monkeypatch.setattr(bridge_client, "config", lambda agent=None: {"enabled": True})

    def fake_request(cfg, method, path, payload=None):
        calls.append((method, path, payload))
        return {"ok": True, "path": r"C:\Users\HP\Desktop\Deck.pptx", "size": len(b"pptx-bytes")}

    monkeypatch.setattr(bridge_client, "request", fake_request)

    result = bridge_client.export_host_file(str(source), r"C:\Users\HP\Desktop\Deck.pptx")

    assert result["ok"] is True
    assert result["host_path"] == r"C:\Users\HP\Desktop\Deck.pptx"
    assert calls[0][1] == "/file/write-binary"
    assert base64.b64decode(calls[0][2]["contentBase64"]) == b"pptx-bytes"


def test_local_path_rejects_paths_outside_vini_workspace(tmp_path, monkeypatch):
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("no", encoding="utf-8")
    monkeypatch.setattr(bridge_client.files, "get_base_dir", lambda: str(tmp_path))

    with pytest.raises(PermissionError):
        bridge_client.export_host_file(str(outside), r"C:\Users\HP\Desktop\outside.txt")


def test_local_files_surface_declares_honest_boundaries():
    panel = Path("plugins/_windows_host_bridge/webui/local-files-panel.html")
    content = (Path(__file__).resolve().parents[1] / panel).read_text(encoding="utf-8")

    assert "Host writes and app launches require Windows approval." in content
    assert "Microsoft Office detected" in content
    assert "scoped folders" in content
