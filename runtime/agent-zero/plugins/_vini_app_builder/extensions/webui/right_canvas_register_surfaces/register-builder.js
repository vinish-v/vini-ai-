import { store as builderStore } from "/plugins/_vini_app_builder/webui/builder-store.js";

function waitForElement(selector, timeoutMs = 3000) {
  const found = document.querySelector(selector);
  if (found) return Promise.resolve(found);
  return new Promise((resolve) => {
    const timeout = globalThis.setTimeout(() => {
      observer.disconnect();
      resolve(null);
    }, timeoutMs);
    const observer = new MutationObserver(() => {
      const element = document.querySelector(selector);
      if (!element) return;
      globalThis.clearTimeout(timeout);
      observer.disconnect();
      resolve(element);
    });
    observer.observe(document.body, { childList: true, subtree: true });
  });
}

export default async function registerBuilderSurface(canvas) {
  canvas.registerSurface({
    id: "build",
    title: "Build",
    icon: "code_blocks",
    order: 15,
    modalPath: "/plugins/_vini_app_builder/webui/main.html",
    async open(payload = {}) {
      await waitForElement('[data-surface-id="build"] .vini-builder-panel');
      await builderStore.onOpen?.(payload || {});
    },
    async close() {
      await builderStore.cleanup?.();
    },
  });
}
