import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";

function currentContextId() {
  try {
    return globalThis.getContext?.() || "";
  } catch {
    return "";
  }
}

function basename(path = "") {
  return String(path || "").replace(/[\\\/]+$/, "").split(/[\\\/]/).filter(Boolean).pop() || path || "";
}

async function callLocalFiles(action, payload = {}) {
  return await callJsonApi("/plugins/_windows_host_bridge/local_files", {
    action,
    ctxid: currentContextId(),
    ...payload,
  });
}

const model = {
  status: null,
  currentPath: "",
  entries: [],
  selected: null,
  loading: false,
  error: "",
  message: "",

  async init() {
    await this.refreshStatus();
  },

  async refreshStatus() {
    this.loading = true;
    this.error = "";
    try {
      const status = await callLocalFiles("status");
      this.status = status || {};
      const scopes = Array.isArray(status?.scopes) ? status.scopes : [];
      if (!this.currentPath && scopes.length) {
        this.currentPath = scopes[0]?.path || "";
        await this.list(this.currentPath);
      }
    } catch (error) {
      this.error = error?.message || String(error);
    } finally {
      this.loading = false;
    }
  },

  async list(path = this.currentPath) {
    const target = String(path || "").trim();
    if (!target) return;
    this.loading = true;
    this.error = "";
    try {
      const result = await callLocalFiles("list", { path: target });
      if (result?.ok === false) throw new Error(result.error || "Could not list folder.");
      this.currentPath = result.path || target;
      this.entries = Array.isArray(result.entries) ? result.entries : [];
      this.selected = null;
    } catch (error) {
      this.error = error?.message || String(error);
    } finally {
      this.loading = false;
    }
  },

  async openEntry(entry = null) {
    const item = entry || this.selected;
    if (!item) return;
    if (item.kind === "directory") {
      await this.list(item.path);
      return;
    }
    this.selected = item;
  },

  async importSelected(openInDesktop = false) {
    if (!this.selected?.path) return;
    this.loading = true;
    this.error = "";
    try {
      const result = await callLocalFiles("import", {
        host_path: this.selected.path,
        register_office: true,
        open_in_desktop: Boolean(openInDesktop),
      });
      if (result?.ok === false) throw new Error(result.error || "Import failed.");
      this.message = `Imported ${basename(this.selected.path)}`;
      if (openInDesktop && result?.desktop?.available) {
        await globalThis.Alpine?.store("rightCanvas")?.open?.("desktop", { source: "local-files" });
      }
    } catch (error) {
      this.error = error?.message || String(error);
    } finally {
      this.loading = false;
    }
  },

  async openDefaultApp() {
    if (!this.selected?.path) return;
    this.loading = true;
    this.error = "";
    try {
      const result = await callLocalFiles("open", { path: this.selected.path });
      if (result?.ok === false) throw new Error(result.error || "Open failed.");
      this.message = "Windows app launch approved";
    } catch (error) {
      this.error = error?.message || String(error);
    } finally {
      this.loading = false;
    }
  },

  async openNativeOffice(app = "") {
    if (!this.selected?.path) return;
    this.loading = true;
    this.error = "";
    try {
      const result = await callLocalFiles("office_open", { path: this.selected.path, app });
      if (result?.ok === false) throw new Error(result.error || "Microsoft Office open failed.");
      this.message = "Microsoft Office launch approved";
    } catch (error) {
      this.error = error?.message || String(error);
    } finally {
      this.loading = false;
    }
  },

  scopePaths() {
    return Array.isArray(this.status?.scopes) ? this.status.scopes.map((scope) => scope.path).filter(Boolean) : [];
  },

  officeInstalled() {
    return Boolean(this.status?.microsoft_office_installed);
  },

  providerState() {
    if (this.status?.ok) return "Bridge attached";
    if (this.status?.enabled === false) return "Bridge disabled";
    return "Bridge unavailable";
  },
};

export const store = createStore("localFiles", model);
