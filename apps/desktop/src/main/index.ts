import { app, BrowserWindow, ipcMain, Menu, shell } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { HostBridge } from "./hostBridge.js";
import { RuntimeManager } from "./runtimeManager.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const hostBridge = new HostBridge();
const runtimeManager = new RuntimeManager(hostBridge);

app.setName("Vini AI");

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function loadingPage(message: string, detail = ""): string {
  return `data:text/html;charset=utf-8,${encodeURIComponent(`<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Vini AI</title>
  <style>
    :root { color-scheme: dark; font-family: Inter, Segoe UI, system-ui, sans-serif; background: #050505; color: #f5f5f5; }
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #050505; }
    main { width: min(560px, calc(100vw - 48px)); border: 1px solid #262626; border-radius: 10px; padding: 28px; background: #0d0d0d; }
    .mark { width: 48px; height: 48px; border-radius: 10px; display: grid; place-items: center; background: #f5f5f5; color: #050505; font-weight: 900; font-size: 25px; margin-bottom: 18px; }
    h1 { margin: 0 0 10px; font-size: 26px; line-height: 1.15; }
    p { margin: 0; color: #b8b8be; line-height: 1.55; }
    pre { margin: 18px 0 0; white-space: pre-wrap; color: #fca5a5; background: #120808; border: 1px solid #3f1717; border-radius: 8px; padding: 12px; font-size: 12px; }
  </style>
</head>
<body>
  <main>
    <div class="mark">V</div>
    <h1>${escapeHtml(message)}</h1>
    <p>Vini AI is starting the local runtime and will open the app UI here when it is ready.</p>
    ${detail ? `<pre>${escapeHtml(detail)}</pre>` : ""}
  </main>
</body>
</html>`)}`
}

function createWindow(): BrowserWindow {
  const mainWindow = new BrowserWindow({
    width: 1260,
    height: 820,
    minWidth: 980,
    minHeight: 680,
    title: "Vini AI",
    backgroundColor: "#050505",
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("http://127.0.0.1:50080") || url.startsWith("http://localhost:50080")) {
      return { action: "allow" };
    }
    if (isSafeExternalUrl(url)) {
      void shell.openExternal(url).catch((error) => dialogSafeLog(`Could not open external URL: ${url}`, error));
    }
    return { action: "deny" };
  });

  void mainWindow.loadURL(loadingPage("Starting Vini AI"));
  void bootRuntimeInto(mainWindow);

  return mainWindow;
}

function isSafeExternalUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return ["http:", "https:", "mailto:"].includes(url.protocol);
  } catch {
    return false;
  }
}

function requireSafeExternalUrl(value: unknown): string {
  const url = String(value || "").trim();
  if (!isSafeExternalUrl(url)) {
    throw new Error("Only http, https, and mailto URLs can be opened externally.");
  }
  return url;
}

function registerIpcHandlers(): void {
  ipcMain.handle("runtime:getStatus", () => runtimeManager.getStatus());
  ipcMain.handle("runtime:start", () => runtimeManager.start());
  ipcMain.handle("runtime:stop", () => runtimeManager.stop());
  ipcMain.handle("runtime:restart", () => runtimeManager.restart());
  ipcMain.handle("runtime:logs", () => runtimeManager.logs());
  ipcMain.handle("runtime:open", () => runtimeManager.openRuntime());
  ipcMain.handle("runtime:openDataDir", () => runtimeManager.openDataDir());
  ipcMain.handle("runtime:openRuntimeDir", () => runtimeManager.openRuntimeDir());
  ipcMain.handle("app:openExternal", async (_event, url) => {
    await shell.openExternal(requireSafeExternalUrl(url));
  });
}

async function bootRuntimeInto(window: BrowserWindow): Promise<void> {
  const startResult = await runtimeManager.start();
  if (!startResult.ok) {
    await window.loadURL(loadingPage("Vini AI runtime could not start", startResult.message));
    return;
  }

  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    const status = await runtimeManager.getStatus();
    if (status.health.ok) {
      await window.loadURL(status.url);
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }

  const status = await runtimeManager.getStatus();
  await window.loadURL(loadingPage("Vini AI runtime did not become healthy in time", status.health.error || `HTTP ${status.health.statusCode || "unavailable"}`));
}

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null);
  registerIpcHandlers();
  await hostBridge.start().catch((error) => {
    dialogSafeLog("Windows host bridge could not start", error);
  });
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

function dialogSafeLog(message: string, error: unknown): void {
  console.error(message, error);
}

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    void hostBridge.stop();
    app.quit();
  }
});
