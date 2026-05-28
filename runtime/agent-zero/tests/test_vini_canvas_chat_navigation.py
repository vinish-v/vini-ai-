from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_chat_selection_returns_from_canvas_workspace():
    source = (PROJECT_ROOT / "webui" / "components" / "sidebar" / "chats" / "chats-store.js").read_text(encoding="utf-8")

    assert "function openAgentWorkspace()" in source
    assert "globalThis.Alpine?.store?.(\"viniWorkspace\")?.openAgent?.()" in source
    assert "async selectChat(id) {\n    openAgentWorkspace();" in source
    assert "if (id === currentContext) {\n      this.setSelected(id);\n      return;\n    }" in source
