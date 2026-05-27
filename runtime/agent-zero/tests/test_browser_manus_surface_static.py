from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_repo_file(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_browser_surface_exposes_live_proof_controls() -> None:
    panel = read_repo_file("plugins/_browser/webui/browser-panel.html")
    store = read_repo_file("plugins/_browser/webui/browser-store.js")

    assert "browser-live-action-trail" in panel
    assert "actionPathSegments()" in panel
    assert "frameCleanupText()" in panel
    assert "actionFeedMeta(action)" in panel
    assert "STREAM_TARGET_FPS = 12" in store
    assert "frameCleanupStats" in store
    assert "URL.revokeObjectURL" in store


def test_browser_tool_messages_render_proof_cards() -> None:
    messages = read_repo_file("webui/js/messages.js")
    css = read_repo_file("webui/css/messages.css")

    assert 'kvps._tool_name === "browser"' in messages
    assert 'kvps._tool_name === "scripted_browser_task"' in messages
    assert "drawMessageBrowserTool" in messages
    assert "drawMessageScriptedBrowserTask" in messages
    assert "browser-proof-step" in css
    assert "browser-proof-content" in css
