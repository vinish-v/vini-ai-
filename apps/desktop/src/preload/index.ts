import { contextBridge, ipcRenderer } from "electron";
import type { RuntimeActionResult, RuntimeLogResult, RuntimeStatus } from "../main/types.js";

const api = {
  runtime: {
    getStatus: (): Promise<RuntimeStatus> => ipcRenderer.invoke("runtime:getStatus"),
    start: (): Promise<RuntimeActionResult> => ipcRenderer.invoke("runtime:start"),
    stop: (): Promise<RuntimeActionResult> => ipcRenderer.invoke("runtime:stop"),
    restart: (): Promise<RuntimeActionResult> => ipcRenderer.invoke("runtime:restart"),
    logs: (): Promise<RuntimeLogResult> => ipcRenderer.invoke("runtime:logs"),
    open: (): Promise<void> => ipcRenderer.invoke("runtime:open"),
    openContext: (contextId: string): Promise<void> => ipcRenderer.invoke("runtime:openContext", contextId),
    openDataDir: (): Promise<void> => ipcRenderer.invoke("runtime:openDataDir"),
    openRuntimeDir: (): Promise<void> => ipcRenderer.invoke("runtime:openRuntimeDir")
  },
  app: {
    openExternal: (url: string): Promise<void> => ipcRenderer.invoke("app:openExternal", url)
  }
};

contextBridge.exposeInMainWorld("vini", api);

export type ViniApi = typeof api;

