import { store as localFilesStore } from "/plugins/_windows_host_bridge/webui/local-files-store.js";

export default async function registerLocalFilesSurface(canvas) {
  canvas.registerSurface({
    id: "local-files",
    title: "Local Files",
    icon: "folder_open",
    order: 25,
    modalPath: "/plugins/_windows_host_bridge/webui/main.html",
    async open() {
      await localFilesStore.refreshStatus?.();
    },
  });
}
