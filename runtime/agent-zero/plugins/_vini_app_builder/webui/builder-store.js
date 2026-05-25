import { createStore } from "/js/AlpineStore.js";
import { callJsonApi } from "/js/api.js";
import { open as openSurface } from "/js/surfaces.js";
import { store as chatInputStore } from "/components/chat/input/input-store.js";

const API_PATH = "/plugins/_vini_app_builder/projects";

function firstLine(value = "") {
  return String(value || "").trim().split(/\r?\n/)[0] || "";
}

function normalizeError(error) {
  if (!error) return "Unknown builder error.";
  if (typeof error === "string") return error;
  return error.message || String(error);
}

function projectName(project = {}) {
  return project.name || project.project_id || "Untitled project";
}

export const store = createStore("viniAppBuilder", {
  projects: [],
  activeProjectId: "",
  activeProject: null,
  files: [],
  log: "",
  prompt: "",
  newProjectName: "",
  loading: false,
  actionLabel: "",
  error: "",
  message: "",
  previewBust: Date.now(),

  async api(action, payload = {}) {
    const result = await callJsonApi(API_PATH, { action, ...payload });
    if (result && result.ok === false) {
      throw new Error(result.error || `Vini app builder action failed: ${action}`);
    }
    return result || {};
  },

  async onOpen(payload = {}) {
    await this.refresh();
    const projectId = payload.projectId || payload.project_id || "";
    if (projectId) await this.selectProject(projectId);
  },

  cleanup() {},

  async refresh() {
    await this.withLoading("Refreshing projects", async () => {
      const result = await this.api("list");
      this.projects = result.projects || [];
      if (!this.activeProjectId && this.projects.length) {
        this.activeProjectId = this.projects[0].project_id || "";
      }
      if (this.activeProjectId) {
        await this.loadProject(this.activeProjectId);
      } else {
        this.activeProject = null;
        this.files = [];
        this.log = "";
      }
    });
  },

  async selectProject(projectId) {
    if (!projectId) return;
    this.activeProjectId = projectId;
    await this.loadProject(projectId);
  },

  async loadProject(projectId = this.activeProjectId) {
    if (!projectId) return;
    const status = await this.api("status", { project_id: projectId });
    this.activeProject = status.project || null;
    this.log = status.log || "";
    const files = await this.api("files", { project_id: projectId });
    this.files = files.files || [];
    this.previewBust = Date.now();
  },

  async createProject() {
    const prompt = this.prompt.trim();
    if (!prompt) {
      this.error = "Enter a website prompt first.";
      return;
    }
    await this.withLoading("Creating project", async () => {
      const result = await this.api("create", {
        name: this.newProjectName.trim(),
        prompt,
      });
      const project = result.project || {};
      this.projects = [project, ...this.projects.filter((item) => item.project_id !== project.project_id)];
      this.activeProjectId = project.project_id || "";
      await this.loadProject(this.activeProjectId);
      this.message = `Created ${projectName(project)}.`;
    });
  },

  async sendToVini() {
    const prompt = this.prompt.trim();
    if (!prompt) {
      this.error = "Enter a website prompt first.";
      return;
    }
    chatInputStore.message = [
      "Build this as a real website inside Vini Computer using the vini_app_builder tool.",
      "Create files under /a0/usr/projects, run real install/build/typecheck/dev-server commands, open and verify the preview, then report the manifest/proof.",
      "",
      prompt,
    ].join("\n");
    await chatInputStore.sendMessage();
    await openSurface("build");
  },

  async runBuild() {
    if (!this.activeProjectId) return;
    await this.withLoading("Running install/build/typecheck", async () => {
      await this.api("build_all", { project_id: this.activeProjectId, install: true });
      await this.loadProject(this.activeProjectId);
      this.message = "Build commands completed. Check proof log for exit codes.";
    });
  },

  async startPreview() {
    if (!this.activeProjectId) return;
    await this.withLoading("Starting preview", async () => {
      await this.api("preview", { project_id: this.activeProjectId, verify: true });
      await this.loadProject(this.activeProjectId);
      this.message = "Preview started and verification was recorded.";
    });
  },

  async exportProject() {
    if (!this.activeProjectId) return;
    await this.withLoading("Exporting ZIP", async () => {
      const result = await this.api("export", { project_id: this.activeProjectId });
      await this.loadProject(this.activeProjectId);
      const url = result.export_url || this.activeProject?.export_url || "";
      if (url) window.open(url, "_blank", "noopener");
      this.message = "Export ZIP created.";
    });
  },

  async withLoading(label, fn) {
    if (this.loading) return;
    this.loading = true;
    this.actionLabel = label;
    this.error = "";
    this.message = "";
    try {
      await fn();
    } catch (error) {
      this.error = normalizeError(error);
    } finally {
      this.loading = false;
      this.actionLabel = "";
    }
  },

  statusClass(project = this.activeProject) {
    const status = String(project?.status || "").toLowerCase();
    if (status.includes("failed") || status.includes("error")) return "is-error";
    if (status.includes("verified") || status.includes("preview") || status.includes("export")) return "is-ok";
    if (status.includes("running") || status.includes("install") || status.includes("build")) return "is-busy";
    return "";
  },

  previewUrl(project = this.activeProject) {
    const url = project?.preview_url || "";
    if (!url) return "";
    const separator = url.includes("?") ? "&" : "?";
    return `${url}${separator}v=${this.previewBust}`;
  },

  activeTitle() {
    return projectName(this.activeProject || {});
  },

  shortLogLine() {
    return firstLine(this.log.split(/\r?\n/).reverse().find(Boolean) || "");
  },
});
