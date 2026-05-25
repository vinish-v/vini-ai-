import { createStore } from "/js/AlpineStore.js";
import { callJsExtensions } from "/js/extensions.js";
import {
  SURFACE_MODE_DOCKED,
  SURFACE_MODE_FLOATING,
  closeSurfaceGroupModals,
  getRegisteredSurfaces,
  migratePersistedSurfaceState,
  normalizeSurfaceId,
  normalizeSurfaceMode,
  registerSurface as registerSurfaceDefinition,
} from "/js/surfaces.js";

const STORAGE_KEY = "a0.rightCanvas";
const DEFAULT_WIDTH = 640;
const MIN_WIDTH = 420;
const DESKTOP_BREAKPOINT = 1024;
const MOBILE_BREAKPOINT = 768;

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function viewportWidth() {
  return Math.max(document.documentElement.clientWidth || 0, globalThis.innerWidth || 0);
}

function normalizeWidth(value, fallback = DEFAULT_WIDTH) {
  if (value === null || value === undefined || value === "") return fallback;
  const width = Number(value);
  return Number.isFinite(width) ? Math.max(MIN_WIDTH, Math.round(width)) : fallback;
}

const model = {
  surfaces: [],
  activeSurfaceId: "",
  surfaceModes: {},
  mountedSurfaces: {},
  isOpen: false,
  width: DEFAULT_WIDTH,
  isOverlayMode: false,
  isMobileMode: false,
  osAppWindows: {},
  osActiveAppId: "",
  _initialized: false,
  _registering: false,
  _registered: false,
  _registrationPromise: null,
  _rootElement: null,
  _resizeCleanup: null,
  _lastPayloadBySurface: {},

  async init(element = null) {
    if (element) this._rootElement = element;
    if (this._initialized) {
      this.applyLayoutState();
      return;
    }

    this._initialized = true;
    this.restore();
    this.updateLayoutMode();
    this.applyLayoutState();
    globalThis.addEventListener("resize", () => {
      this.updateLayoutMode();
      this.setWidth(this.width, { persist: false });
      this.applyLayoutState();
    });

    await this.ensureRegistered();
  },

  async ensureRegistered() {
    if (this._registered) return;
    if (this._registrationPromise) {
      await this._registrationPromise;
      return;
    }

    this._registering = true;
    this._registrationPromise = (async () => {
      await callJsExtensions("surfaces_register", this);
      await callJsExtensions("right_canvas_register_surfaces", this);
      this._registered = true;
      this.ensureActiveSurface();
    })();

    try {
      await this._registrationPromise;
    } finally {
      this._registering = false;
      this._registrationPromise = null;
    }
  },

  registerSurface(surface) {
    if (!surface?.id) return;
    const surfaceId = normalizeSurfaceId(surface.id);
    const normalized = {
      title: surface.id,
      icon: "web_asset",
      image: "",
      order: 100,
      canOpen: () => true,
      open: () => {},
      close: () => {},
      modalPath: "",
      actionOnly: false,
      ...surface,
      id: surfaceId,
    };

    const index = this.surfaces.findIndex((item) => item.id === normalized.id);
    if (index >= 0) {
      this.surfaces.splice(index, 1, normalized);
    } else {
      this.surfaces.push(normalized);
    }
    if (!this.surfaceModes[normalized.id]) {
      this.surfaceModes[normalized.id] = SURFACE_MODE_DOCKED;
    }
    registerSurfaceDefinition(normalized);
    this.surfaces.sort((a, b) => (a.order ?? 100) - (b.order ?? 100));
    if (!this._registering) {
      this.ensureActiveSurface();
    }
  },

  ensureActiveSurface() {
    const panelSurfaces = this.panelSurfaces;
    if (!panelSurfaces.length) {
      this.activeSurfaceId = "";
      return;
    }
    if (this.isComputerAppSurface(this.activeSurfaceId) || !panelSurfaces.some((surface) => surface.id === this.activeSurfaceId)) {
      this.activeSurfaceId = this.defaultSurfaceId();
    }
  },

  async open(surfaceId = "", payload = {}) {
    await this.ensureRegistered();
    const targetId = normalizeSurfaceId(surfaceId || this.activeSurfaceId || this.defaultSurfaceId() || "");
    const surface = this.getSurface(targetId);
    if (!surface) {
      return false;
    }
    if (this.isComputerAppSurface(targetId)) {
      return await this.openOsApp(targetId, payload);
    }
    if (this.isMobileMode && !surface.actionOnly) {
      return false;
    }
    if (typeof surface.canOpen === "function" && surface.canOpen(payload) === false) {
      return false;
    }

    if (surface.actionOnly) {
      try {
        await surface.open?.(payload || {});
      } catch (error) {
        console.error(`Vini AI Computer action ${targetId} failed`, error);
      }
      return true;
    }

    this.activeSurfaceId = targetId;
    this.markSurfaceMounted(targetId);
    this.isOpen = true;
    this.setWidth(this.width, { persist: false });
    this.recordSurfaceMode(targetId, SURFACE_MODE_DOCKED, { persist: false });
    this._lastPayloadBySurface[targetId] = payload || {};
    this.persist();
    this.applyLayoutState();

    try {
      await surface.open?.(payload || {});
    } catch (error) {
      console.error(`Vini AI Computer surface ${targetId} failed to open`, error);
    }
    return true;
  },

  defaultSurfaceId() {
    return this.panelSurfaces.find((surface) => surface.id === "desktop")?.id
      || this.panelSurfaces[0]?.id
      || "";
  },

  isComputerAppSurface(surfaceId = "") {
    return ["browser", "editor", "build"].includes(normalizeSurfaceId(surfaceId));
  },

  isOsAppOpen(surfaceId = "") {
    return Boolean(this.osAppWindows[normalizeSurfaceId(surfaceId)]);
  },

  isOsAppActive(surfaceId = "") {
    const targetId = normalizeSurfaceId(surfaceId);
    return Boolean(targetId && this.osActiveAppId === targetId && this.isOsAppOpen(targetId));
  },

  async openOsApp(surfaceId = "", payload = {}) {
    await this.ensureRegistered();
    const targetId = normalizeSurfaceId(surfaceId);
    const appSurface = this.getSurface(targetId);
    const desktopSurface = this.getSurface("desktop");
    if (!appSurface || !desktopSurface) return false;

    this.isOpen = true;
    this.activeSurfaceId = "desktop";
    this.markSurfaceMounted("desktop");
    this.markSurfaceMounted(targetId);
    this.osAppWindows = {
      ...this.osAppWindows,
      [targetId]: true,
    };
    this.osActiveAppId = targetId;
    this.recordSurfaceMode("desktop", SURFACE_MODE_DOCKED, { persist: false });
    this.recordSurfaceMode(targetId, SURFACE_MODE_DOCKED, { persist: false });
    this._lastPayloadBySurface.desktop = this._lastPayloadBySurface.desktop || { source: "vini-os" };
    this._lastPayloadBySurface[targetId] = payload || {};
    this.persist();
    this.applyLayoutState();

    try {
      await desktopSurface.open?.({ source: payload?.source || "vini-os" });
    } catch (error) {
      console.error("Vini OS desktop failed to open", error);
    }
    try {
      await appSurface.open?.(payload || {});
    } catch (error) {
      console.error(`Vini OS app ${targetId} failed to open`, error);
    }
    return true;
  },

  async closeOsApp(surfaceId = "") {
    const targetId = normalizeSurfaceId(surfaceId);
    if (!this.isComputerAppSurface(targetId)) return false;
    const surface = this.getSurface(targetId);
    try {
      await surface?.close?.({ source: "vini-os" });
    } catch (error) {
      console.error(`Vini OS app ${targetId} failed to close`, error);
    }
    const nextWindows = { ...this.osAppWindows };
    delete nextWindows[targetId];
    this.osAppWindows = nextWindows;
    this.markSurfaceUnmounted(targetId);
    if (this.osActiveAppId === targetId) {
      this.osActiveAppId = Object.keys(this.osAppWindows).find((id) => this.osAppWindows[id]) || "";
    }
    this.activeSurfaceId = "desktop";
    this.persist();
    this.applyLayoutState();
    return true;
  },

  markSurfaceMounted(surfaceId) {
    const targetId = normalizeSurfaceId(surfaceId);
    if (!targetId) return;
    this.mountedSurfaces = {
      ...this.mountedSurfaces,
      [targetId]: true,
    };
  },

  markSurfaceUnmounted(surfaceId) {
    const targetId = normalizeSurfaceId(surfaceId);
    if (!targetId || !this.mountedSurfaces[targetId]) return;
    const next = { ...this.mountedSurfaces };
    delete next[targetId];
    this.mountedSurfaces = next;
  },

  mountedSurfaceIds() {
    return Object.entries(this.mountedSurfaces)
      .filter(([, mounted]) => mounted)
      .map(([surfaceId]) => surfaceId);
  },

  isSurfaceMounted(id) {
    return Boolean(this.mountedSurfaces[normalizeSurfaceId(id)]);
  },

  isSurfaceRendered(id) {
    return Boolean(this.isOpen && this.isSurfaceMounted(id));
  },

  isSurfaceVisible(id) {
    const targetId = normalizeSurfaceId(id);
    return Boolean(this.isOpen && this.activeSurfaceId === targetId && this.isSurfaceMounted(targetId));
  },

  recordSurfaceMode(surfaceId, mode = SURFACE_MODE_DOCKED, options = {}) {
    const targetId = normalizeSurfaceId(surfaceId);
    if (!targetId) return;
    this.surfaceModes = {
      ...this.surfaceModes,
      [targetId]: normalizeSurfaceMode(mode),
    };
    if (options.persist !== false) this.persist();
  },

  latestSurfaceMode(surfaceId) {
    const targetId = normalizeSurfaceId(surfaceId);
    return normalizeSurfaceMode(this.surfaceModes[targetId]);
  },

  async openLatest(surfaceId = "", payload = {}) {
    await this.ensureRegistered();
    const targetId = normalizeSurfaceId(surfaceId || this.activeSurfaceId || this.defaultSurfaceId() || "");
    if (!targetId) return false;
    if (this.latestSurfaceMode(targetId) === SURFACE_MODE_FLOATING) {
      return await this.openModalSurface(targetId, payload);
    }
    return await this.open(targetId, payload);
  },

  async close() {
    this.isOpen = false;
    this.persist();
    this.applyLayoutState();
    return true;
  },

  async dockSurface(surfaceId, payload = {}) {
    surfaceId = normalizeSurfaceId(surfaceId);
    if (this.isMobileMode) {
      return false;
    }
    const surface = this.getSurface(surfaceId);
    if (!surface) {
      return false;
    }
    const modalPath = payload.modalPath || surface.modalPath || "";
    let handoffStarted = false;
    try {
      await surface.beginDockHandoff?.(payload);
      handoffStarted = true;

      const closed = await this.closeDockSourceModal(payload, modalPath);
      if (closed === false) {
        await surface.cancelDockHandoff?.(payload);
        return false;
      }

      const openPayload = { ...payload, source: "modal" };
      delete openPayload.closeSourceModal;
      const opened = await this.open(surfaceId, openPayload);
      await surface.finishDockHandoff?.({ ...openPayload, opened });
      return opened;
    } catch (error) {
      if (handoffStarted) {
        await surface.cancelDockHandoff?.(payload);
      }
      console.error(`Vini AI Computer surface ${surfaceId} failed to dock`, error);
      return false;
    }
  },

  async closeDockSourceModal(payload = {}, modalPath = "") {
    if (typeof payload.closeSourceModal === "function") {
      return (await payload.closeSourceModal()) !== false;
    }

    const sourceModalPath = payload.sourceModalPath || modalPath;
    if (sourceModalPath || modalPath) {
      const closed = await closeSurfaceGroupModals();
      if (closed === false) return false;
      if (!sourceModalPath || !globalThis.isModalOpen?.(sourceModalPath)) return true;
    }
    if (sourceModalPath && globalThis.isModalOpen?.(sourceModalPath)) {
      return (await globalThis.closeModal?.(sourceModalPath)) !== false;
    }
    if (modalPath && modalPath !== sourceModalPath && globalThis.isModalOpen?.(modalPath)) {
      return (await globalThis.closeModal?.(modalPath)) !== false;
    }
    return true;
  },

  async undockSurface(surfaceId = "", payload = {}) {
    const targetId = normalizeSurfaceId(surfaceId || this.activeSurfaceId);
    const surface = this.getSurface(targetId);
    const modalPath = payload.modalPath || surface?.modalPath || "";
    if (!surface || !modalPath) return false;
    const openModal = globalThis.ensureModalOpen || globalThis.openModal;
    if (!openModal) return false;
    if (this.activeSurfaceId === targetId) {
      this.isOpen = false;
      this.persist();
      this.applyLayoutState();
    }
    this.recordSurfaceMode(targetId, SURFACE_MODE_FLOATING);
    const modalPromise = openModal(modalPath);
    if (modalPromise?.catch) {
      modalPromise.catch((error) => console.error(`Vini AI Computer surface ${targetId} failed to undock`, error));
    }
    return true;
  },

  async openModalSurface(surfaceId = "", payload = {}) {
    const targetId = normalizeSurfaceId(surfaceId || this.activeSurfaceId);
    const surface = this.getSurface(targetId);
    const modalPath = payload.modalPath || surface?.modalPath || "";
    if (!surface || !modalPath) return false;
    const openModal = globalThis.ensureModalOpen || globalThis.openModal;
    if (!openModal) return false;

    if (this.isOpen && this.activeSurfaceId === targetId) {
      this.isOpen = false;
      this.persist();
      this.applyLayoutState();
    }

    this.recordSurfaceMode(targetId, SURFACE_MODE_FLOATING);
    const modalPromise = openModal(modalPath);
    if (modalPromise?.catch) {
      modalPromise.catch((error) => console.error(`Vini AI Computer surface ${targetId} failed to open as modal`, error));
    }
    return true;
  },

  async undockActiveSurface() {
    return await this.undockSurface(this.activeSurfaceId);
  },

  currentSurfaceCanUndock() {
    return Boolean(this.currentSurface()?.modalPath);
  },

  async toggle(surfaceId = "", payload = {}) {
    await this.ensureRegistered();
    const targetId = normalizeSurfaceId(surfaceId || this.activeSurfaceId || this.panelSurfaces[0]?.id || "");
    if (this.isOpen && targetId === this.activeSurfaceId) {
      await this.close();
      return false;
    }
    return await this.open(targetId, payload);
  },

  async toggleCanvas() {
    await this.ensureRegistered();
    if (this.isMobileMode) {
      return false;
    }
    if (this.isOpen) {
      await this.close();
      return false;
    }
    return await this.open(this.activeSurfaceId || this.defaultSurfaceId() || "");
  },

  setWidth(px, options = {}) {
    const { persist = true } = options;
    const next = clamp(normalizeWidth(px), MIN_WIDTH, this.maxWidth());
    this.width = next;
    this.applyLayoutState();
    if (persist) this.persist();
  },

  maxWidth() {
    if (this.isOverlayMode) {
      return Math.max(MIN_WIDTH, viewportWidth() - 44);
    }

    const container = this._rootElement?.closest(".container");
    const rightPanel = document.getElementById("right-panel");
    const containerRight = container?.getBoundingClientRect().right ?? viewportWidth();
    const panelLeft = rightPanel?.getBoundingClientRect().left ?? 0;
    const reservedChatWidth = Math.min(620, Math.max(520, Math.floor(viewportWidth() * 0.42)));
    return Math.max(MIN_WIDTH, Math.floor(containerRight - panelLeft - reservedChatWidth));
  },

  defaultWidth() {
    return Math.min(DEFAULT_WIDTH, Math.floor(viewportWidth() * 0.45));
  },

  startResize(event) {
    if (this.isOverlayMode || this.isMobileMode || !this.isOpen) return;
    if (event.button !== 0) return;
    event.preventDefault();
    this.dispatchResizeEvent("right-canvas-resize-start");

    const onPointerMove = (moveEvent) => {
      const nextWidth = viewportWidth() - moveEvent.clientX;
      this.setWidth(nextWidth);
    };
    const onPointerUp = () => {
      globalThis.removeEventListener("pointermove", onPointerMove);
      globalThis.removeEventListener("pointerup", onPointerUp);
      globalThis.removeEventListener("pointercancel", onPointerUp);
      document.body.classList.remove("right-canvas-resizing");
      this.persist();
      this.dispatchResizeEvent("right-canvas-resize-end");
    };

    document.body.classList.add("right-canvas-resizing");
    globalThis.addEventListener("pointermove", onPointerMove);
    globalThis.addEventListener("pointerup", onPointerUp);
    globalThis.addEventListener("pointercancel", onPointerUp);
  },

  dispatchResizeEvent(name) {
    try {
      globalThis.dispatchEvent(new CustomEvent(name, {
        detail: {
          width: this.width,
          activeSurfaceId: this.activeSurfaceId,
        },
      }));
    } catch {
      // Resize events are an optimization hook for embedded surfaces.
    }
  },

  persist() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          isOpen: this.isOpen,
          activeSurfaceId: this.activeSurfaceId,
          surfaceModes: this.surfaceModes,
          width: this.width,
        }),
      );
    } catch (error) {
      console.warn("Could not persist right canvas state", error);
    }
  },

  restore() {
    this.width = this.defaultWidth();
    try {
      const saved = migratePersistedSurfaceState(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
      this.isOpen = false;
      this.activeSurfaceId = String(saved.activeSurfaceId || "");
      if (this.isComputerAppSurface(this.activeSurfaceId)) this.activeSurfaceId = "desktop";
      this.surfaceModes = Object.fromEntries(
        Object.entries(saved.surfaceModes || {}).map(([surfaceId, mode]) => [
          surfaceId,
          normalizeSurfaceMode(mode),
        ]),
      );
      if (Number.isFinite(Number(saved.width))) this.width = Number(saved.width);
    } catch (error) {
      console.warn("Could not restore right canvas state", error);
    }
    this.setWidth(this.width, { persist: false });
  },

  updateLayoutMode() {
    const width = viewportWidth();
    const wasMobileMode = this.isMobileMode;
    this.isOverlayMode = width < DESKTOP_BREAKPOINT;
    this.isMobileMode = width <= MOBILE_BREAKPOINT;
    if (this.isMobileMode) {
      const wasOpen = this.isOpen;
      const mountedIds = this.mountedSurfaceIds();
      this.isOpen = false;
      this.mountedSurfaces = {};
      if ((wasOpen || mountedIds.length > 0) && mountedIds.length > 0) {
        globalThis.setTimeout?.(() => {
          for (const surfaceId of mountedIds) {
            const surface = this.getSurface(surfaceId);
            const payload = this._lastPayloadBySurface[surfaceId] || {};
            surface?.close?.({ ...payload, reason: "mobile" });
          }
        }, 0);
      }
    } else if (wasMobileMode && this.width < MIN_WIDTH) {
      this.width = this.defaultWidth();
    }
  },

  applyLayoutState() {
    this.updateLayoutMode();
    document.documentElement.style.setProperty("--right-canvas-width", `${this.width}px`);
    document.body.classList.toggle("right-canvas-open", this.isOpen && !this.isMobileMode);
    document.body.classList.toggle("right-canvas-overlay-mode", this.isOverlayMode);
    document.body.classList.toggle("right-canvas-mobile-mode", this.isMobileMode);
  },

  widthStyle() {
    if (this.isMobileMode) return "";
    if (!this.isOpen) return "width: 0;";
    if (this.isOverlayMode) {
      return `width: min(${this.width}px, calc(100vw - 44px));`;
    }
    return `width: ${this.width}px;`;
  },

  getSurface(id) {
    const targetId = normalizeSurfaceId(id);
    return this.surfaces.find((surface) => surface.id === targetId)
      || getRegisteredSurfaces().find((surface) => surface.id === targetId)
      || null;
  },

  get railSurfaces() {
    return this.surfaces;
  },

  get panelSurfaces() {
    return this.surfaces.filter((surface) => !surface.actionOnly);
  },

  currentSurface() {
    return this.getSurface(this.activeSurfaceId);
  },

  isSurfaceActive(id) {
    return this.activeSurfaceId === normalizeSurfaceId(id);
  },

  activeTitle() {
    return this.currentSurface()?.title || "Vini AI Computer";
  },

  shouldRender() {
    return !this.isMobileMode;
  },
};

export const store = createStore("rightCanvas", model);
globalThis.ViniRightCanvas = store;
if (typeof window !== "undefined") {
  window.ViniRightCanvas = store;
}
