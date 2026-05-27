import { createStore } from "/js/AlpineStore.js";

export const store = createStore("viniWorkspace", {
  active: "agent",
  previousSidebarOpen: null,

  isAgent() {
    return this.active !== "canvas";
  },

  isCanvas() {
    return this.active === "canvas";
  },

  openAgent() {
    this.active = "agent";
    document.body.classList.remove("vini-canvas-active");
    this.resetWorkspaceDisplay();
    const sidebar = globalThis.Alpine?.store("sidebar");
    if (sidebar && this.previousSidebarOpen !== null) {
      sidebar.isOpen = this.previousSidebarOpen;
      this.previousSidebarOpen = null;
    }
  },

  openCanvas() {
    this.active = "canvas";
    document.body.classList.add("vini-canvas-active");
    document.body.classList.remove("right-canvas-open");
    globalThis.Alpine?.store("rightCanvas")?.close?.();
    this.resetWorkspaceDisplay();
  },

  toggleCanvas() {
    if (this.isCanvas()) {
      this.openAgent();
      return;
    }
    this.openCanvas();
  },

  resetWorkspaceDisplay() {
    for (const id of ["vini-agent-workspace", "vini-agent-input-host", "vini-canvas-workspace-host"]) {
      document.getElementById(id)?.style.removeProperty("display");
    }
  },
});
