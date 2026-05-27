import { app, BrowserWindow, dialog, shell } from "electron";
import { execFile, spawn } from "node:child_process";
import crypto from "node:crypto";
import { existsSync } from "node:fs";
import { promises as fs } from "node:fs";
import http from "node:http";
import os from "node:os";
import path from "node:path";

const DEFAULT_PORT = 50180;
const MAX_BODY_BYTES = 96 * 1024 * 1024;
const MAX_TEXT_READ_BYTES = 1024 * 1024;
const MAX_BINARY_READ_BYTES = 64 * 1024 * 1024;
const MAX_COMMAND_OUTPUT_BYTES = 256 * 1024;

type HostBridgeConfig = {
  version: 1;
  enabled: boolean;
  port: number;
  allowedRoots: string[];
  approvals: {
    command: boolean;
    write: boolean;
    delete: boolean;
    mkdir: boolean;
    open: boolean;
  };
  command: {
    timeoutMs: number;
    maxOutputBytes: number;
  };
};

type JsonValue = string | number | boolean | null | JsonValue[] | { [key: string]: JsonValue };

type BridgeResult = Record<string, JsonValue | undefined>;

function normalizeForCompare(target: string): string {
  return path.resolve(target).replace(/[\\/]+$/, "").toLowerCase();
}

function truncate(value: string, maxBytes: number): string {
  const buffer = Buffer.from(value, "utf8");
  if (buffer.byteLength <= maxBytes) {
    return value;
  }
  return `${buffer.subarray(0, maxBytes).toString("utf8")}\n...[truncated ${buffer.byteLength - maxBytes} bytes]`;
}

function jsonResponse(res: http.ServerResponse, statusCode: number, payload: BridgeResult): void {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store"
  });
  res.end(body);
}

function isJsonObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function commandError(error: unknown): string {
  if (error instanceof Error) {
    const enriched = error as Error & { stderr?: string; stdout?: string; code?: string | number };
    return [enriched.stderr, enriched.stdout, enriched.message].filter(Boolean).join("\n").trim();
  }
  return String(error);
}

export class HostBridge {
  private server: http.Server | null = null;
  private config: HostBridgeConfig | null = null;
  private token = "";

  getConfigPath(): string {
    return path.join(app.getPath("userData"), "host-bridge.json");
  }

  getTokenPath(): string {
    return path.join(app.getPath("userData"), "host-bridge-token");
  }

  getUrl(): string {
    return `http://127.0.0.1:${this.config?.port || DEFAULT_PORT}`;
  }

  getDockerUrl(): string {
    return `http://host.docker.internal:${this.config?.port || DEFAULT_PORT}`;
  }

  getToken(): string {
    return this.token;
  }

  tokenFingerprint(): string {
    return crypto.createHash("sha256").update(this.token).digest("hex").slice(0, 12);
  }

  async start(): Promise<void> {
    this.config = await this.loadConfig();
    this.token = await this.loadToken();

    if (!this.config.enabled) {
      return;
    }

    if (this.server) {
      return;
    }

    await new Promise<void>((resolve, reject) => {
      const server = http.createServer((req, res) => {
        void this.handleRequest(req, res).catch((error) => {
          jsonResponse(res, 500, { ok: false, error: commandError(error) });
        });
      });
      server.on("error", reject);
      server.listen(this.config?.port || DEFAULT_PORT, "127.0.0.1", () => {
        this.server = server;
        resolve();
      });
    });
  }

  async stop(): Promise<void> {
    if (!this.server) {
      return;
    }
    await new Promise<void>((resolve) => this.server?.close(() => resolve()));
    this.server = null;
  }

  private defaultConfig(): HostBridgeConfig {
    const userData = app.getPath("userData");
    const roots = [
      app.getPath("documents"),
      app.getPath("desktop"),
      app.getPath("downloads"),
      path.join(userData, "agent-zero", "usr", "workdir"),
      path.join(userData, "agent-zero", "usr", "projects")
    ];

    return {
      version: 1,
      enabled: true,
      port: DEFAULT_PORT,
      allowedRoots: Array.from(new Set(roots.map((root) => path.resolve(root)))),
      approvals: {
        command: true,
        write: true,
        delete: true,
        mkdir: true,
        open: true
      },
      command: {
        timeoutMs: 30000,
        maxOutputBytes: MAX_COMMAND_OUTPUT_BYTES
      }
    };
  }

  private async loadConfig(): Promise<HostBridgeConfig> {
    const configPath = this.getConfigPath();
    if (!existsSync(configPath)) {
      const config = this.defaultConfig();
      await fs.writeFile(configPath, `${JSON.stringify(config, null, 2)}\n`, "utf8");
      return config;
    }

    const raw = JSON.parse(await fs.readFile(configPath, "utf8")) as Partial<HostBridgeConfig>;
    const fallback = this.defaultConfig();
    return {
      ...fallback,
      ...raw,
      port: Number(raw.port || fallback.port),
      allowedRoots: Array.isArray(raw.allowedRoots) && raw.allowedRoots.length > 0
        ? raw.allowedRoots.map((root) => path.resolve(String(root)))
        : fallback.allowedRoots,
      approvals: {
        ...fallback.approvals,
        ...(isJsonObject(raw.approvals) ? raw.approvals : {})
      },
      command: {
        ...fallback.command,
        ...(isJsonObject(raw.command) ? raw.command : {})
      }
    };
  }

  private async loadToken(): Promise<string> {
    const tokenPath = this.getTokenPath();
    try {
      const existing = (await fs.readFile(tokenPath, "utf8")).trim();
      if (existing.length >= 32) {
        return existing;
      }
    } catch {
      // Generate a token below.
    }
    const token = crypto.randomBytes(32).toString("hex");
    await fs.writeFile(tokenPath, token, { encoding: "utf8", mode: 0o600 });
    return token;
  }

  private async handleRequest(req: http.IncomingMessage, res: http.ServerResponse): Promise<void> {
    const pathname = new URL(req.url || "/", "http://127.0.0.1").pathname;

    if (pathname === "/health" && req.method === "GET") {
      jsonResponse(res, 200, {
        ok: true,
        service: "vini-windows-host-bridge",
        port: this.config?.port || DEFAULT_PORT,
        scopes: this.safeScopes(),
        tokenFingerprint: this.tokenFingerprint()
      });
      return;
    }

    if (!this.isAuthorized(req)) {
      jsonResponse(res, 401, { ok: false, error: "Unauthorized host bridge request." });
      return;
    }

    if (pathname === "/scopes" && req.method === "GET") {
      jsonResponse(res, 200, { ok: true, scopes: this.safeScopes() });
      return;
    }

    const body = await this.readBody(req);
    if (pathname === "/file/list" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileList(body));
      return;
    }
    if (pathname === "/file/read" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileRead(body));
      return;
    }
    if (pathname === "/file/stat" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileStat(body));
      return;
    }
    if (pathname === "/file/exists" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileExists(body));
      return;
    }
    if (pathname === "/file/read-binary" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileReadBinary(body));
      return;
    }
    if (pathname === "/file/write" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileWrite(body));
      return;
    }
    if (pathname === "/file/write-binary" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileWriteBinary(body));
      return;
    }
    if (pathname === "/file/mkdir" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileMkdir(body));
      return;
    }
    if (pathname === "/file/delete" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileDelete(body));
      return;
    }
    if (pathname === "/command/run" && req.method === "POST") {
      jsonResponse(res, 200, await this.commandRun(body));
      return;
    }
    if (pathname === "/file/open" && req.method === "POST") {
      jsonResponse(res, 200, await this.fileOpen(body));
      return;
    }
    if (pathname === "/office/status" && req.method === "POST") {
      jsonResponse(res, 200, await this.officeStatus());
      return;
    }
    if (pathname === "/office/open" && req.method === "POST") {
      jsonResponse(res, 200, await this.officeOpen(body));
      return;
    }

    jsonResponse(res, 404, { ok: false, error: `Unknown endpoint: ${req.method || "GET"} ${pathname}` });
  }

  private isAuthorized(req: http.IncomingMessage): boolean {
    const token = req.headers["x-vini-host-bridge-token"];
    if (typeof token !== "string") {
      return false;
    }
    const received = Buffer.from(token);
    const expected = Buffer.from(this.token);
    return received.byteLength === expected.byteLength && crypto.timingSafeEqual(received, expected);
  }

  private safeScopes(): JsonValue[] {
    return (this.config?.allowedRoots || []).map((root) => ({ path: root }));
  }

  private async readBody(req: http.IncomingMessage): Promise<Record<string, unknown>> {
    const chunks: Buffer[] = [];
    let size = 0;
    for await (const chunk of req) {
      const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(String(chunk));
      size += buffer.byteLength;
      if (size > MAX_BODY_BYTES) {
        throw new Error("Request body is too large.");
      }
      chunks.push(buffer);
    }
    if (chunks.length === 0) {
      return {};
    }
    const parsed = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    if (!isJsonObject(parsed)) {
      throw new Error("JSON object body is required.");
    }
    return parsed;
  }

  private resolveScoped(input: unknown): string {
    if (typeof input !== "string" || !input.trim()) {
      throw new Error("path is required.");
    }
    const homeExpanded = input.replace(/^~(?=$|[\\/])/, os.homedir());
    const target = path.resolve(homeExpanded);
    const normalizedTarget = normalizeForCompare(target);
    const roots = this.config?.allowedRoots || [];
    const matched = roots.some((root) => {
      const normalizedRoot = normalizeForCompare(root);
      return normalizedTarget === normalizedRoot || normalizedTarget.startsWith(`${normalizedRoot}${path.sep}`);
    });
    if (!matched) {
      throw new Error(`Path is outside Vini AI host bridge scopes: ${target}`);
    }
    return target;
  }

  private async requireApproval(kind: keyof HostBridgeConfig["approvals"], detail: string): Promise<void> {
    if (!this.config?.approvals[kind]) {
      return;
    }
    const parent = BrowserWindow.getFocusedWindow() || BrowserWindow.getAllWindows()[0];
    const result = await dialog.showMessageBox(parent, {
      type: "warning",
      title: "Vini AI host approval",
      message: `Allow Vini AI to ${kind} on this Windows computer?`,
      detail,
      buttons: ["Allow once", "Deny"],
      defaultId: 1,
      cancelId: 1,
      noLink: true
    });
    if (result.response !== 0) {
      throw new Error("User denied the host bridge request.");
    }
  }

  private async fileList(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    const children = await fs.readdir(target, { withFileTypes: true });
    const entries = await Promise.all(children.map(async (child) => {
      const fullPath = path.join(target, child.name);
      const stat = await fs.stat(fullPath);
      return {
        name: child.name,
        path: fullPath,
        kind: child.isDirectory() ? "directory" : "file",
        size: stat.size,
        modifiedAt: stat.mtime.toISOString()
      };
    }));
    return { ok: true, path: target, entries };
  }

  private async fileRead(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    const stat = await fs.stat(target);
    if (!stat.isFile()) {
      throw new Error("Path is not a file.");
    }
    if (stat.size > MAX_TEXT_READ_BYTES) {
      throw new Error(`File is too large to read through the host bridge (${stat.size} bytes).`);
    }
    const content = await fs.readFile(target, "utf8");
    return { ok: true, path: target, size: stat.size, modifiedAt: stat.mtime.toISOString(), content };
  }

  private async fileStat(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    const stat = await fs.stat(target);
    return {
      ok: true,
      exists: true,
      path: target,
      name: path.basename(target),
      extension: path.extname(target).replace(/^\./, "").toLowerCase(),
      kind: stat.isDirectory() ? "directory" : "file",
      size: stat.size,
      modifiedAt: stat.mtime.toISOString(),
      createdAt: stat.birthtime.toISOString()
    };
  }

  private async fileExists(body: Record<string, unknown>): Promise<BridgeResult> {
    try {
      return await this.fileStat(body);
    } catch (error) {
      const message = commandError(error);
      if (message.includes("ENOENT") || message.includes("no such file")) {
        return { ok: true, exists: false, path: String(body.path || "") };
      }
      throw error;
    }
  }

  private async fileReadBinary(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    const stat = await fs.stat(target);
    if (!stat.isFile()) {
      throw new Error("Path is not a file.");
    }
    if (stat.size > MAX_BINARY_READ_BYTES) {
      throw new Error(`File is too large to import through the host bridge (${stat.size} bytes).`);
    }
    const contentBase64 = (await fs.readFile(target)).toString("base64");
    return {
      ok: true,
      path: target,
      name: path.basename(target),
      extension: path.extname(target).replace(/^\./, "").toLowerCase(),
      size: stat.size,
      modifiedAt: stat.mtime.toISOString(),
      contentBase64
    };
  }

  private async fileWrite(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    const content = typeof body.content === "string" ? body.content : "";
    const mode = body.mode === "append" ? "append" : "overwrite";
    await this.requireApproval("write", `${mode} ${target}\n\n${truncate(content, 800)}`);
    if (body.createDirs !== false) {
      await fs.mkdir(path.dirname(target), { recursive: true });
    }
    if (mode === "append") {
      await fs.appendFile(target, content, "utf8");
    } else {
      await fs.writeFile(target, content, "utf8");
    }
    const stat = await fs.stat(target);
    return { ok: true, path: target, size: stat.size, modifiedAt: stat.mtime.toISOString(), mode };
  }

  private async fileWriteBinary(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    const raw = String(body.contentBase64 || "");
    if (!raw) {
      throw new Error("contentBase64 is required.");
    }
    const data = Buffer.from(raw, "base64");
    if (data.byteLength > MAX_BINARY_READ_BYTES) {
      throw new Error(`Binary write exceeds host bridge limit (${data.byteLength} bytes).`);
    }
    await this.requireApproval("write", `Write binary file:\n${target}\n\nSize: ${data.byteLength} bytes`);
    if (body.createDirs !== false) {
      await fs.mkdir(path.dirname(target), { recursive: true });
    }
    await fs.writeFile(target, data);
    const stat = await fs.stat(target);
    return { ok: true, path: target, size: stat.size, modifiedAt: stat.mtime.toISOString(), mode: "binary" };
  }

  private async fileMkdir(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    await this.requireApproval("mkdir", `Create folder:\n${target}`);
    await fs.mkdir(target, { recursive: body.recursive !== false });
    return { ok: true, path: target };
  }

  private async fileDelete(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    const recursive = Boolean(body.recursive);
    await this.requireApproval("delete", `Delete ${recursive ? "recursively" : ""}:\n${target}`);
    await fs.rm(target, { recursive, force: false });
    return { ok: true, path: target, recursive };
  }

  private async commandRun(body: Record<string, unknown>): Promise<BridgeResult> {
    const command = String(body.command || "").trim();
    if (!command) {
      throw new Error("command is required.");
    }
    const cwd = body.cwd ? this.resolveScoped(body.cwd) : this.resolveScoped(this.config?.allowedRoots[0]);
    const timeoutMs = Math.min(Number(body.timeoutMs || this.config?.command.timeoutMs || 30000), 120000);
    await this.requireApproval(
      "command",
      `Working directory:\n${cwd}\n\nCommand:\n${command}\n\nCommand execution is approval-gated and starts in a scoped folder, but the Windows shell itself is not a filesystem sandbox.`
    );
    const result = await new Promise<{ stdout: string; stderr: string; code: number | string | null }>((resolve) => {
      execFile(
        "powershell.exe",
        ["-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        { cwd, windowsHide: true, timeout: timeoutMs, maxBuffer: MAX_COMMAND_OUTPUT_BYTES },
        (error, stdout, stderr) => {
          const enriched = error as Error & { code?: number | string | null } | null;
          resolve({
            stdout: String(stdout || ""),
            stderr: String(stderr || ""),
            code: enriched?.code ?? 0
          });
        }
      );
    });
    const maxOutput = Number(this.config?.command.maxOutputBytes || MAX_COMMAND_OUTPUT_BYTES);
    return {
      ok: result.code === 0,
      cwd,
      code: result.code,
      stdout: truncate(result.stdout, maxOutput),
      stderr: truncate(result.stderr, maxOutput),
      warning: "Command execution is approval-gated and scoped by cwd, but not OS-sandboxed."
    };
  }

  private async fileOpen(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    await this.requireApproval("open", `Open with the Windows default application:\n${target}`);
    const error = await shell.openPath(target);
    if (error) {
      throw new Error(error);
    }
    return { ok: true, path: target, opened: true, app: "default" };
  }

  private async officeStatus(): Promise<BridgeResult> {
    const [word, excel, powerpoint] = await Promise.all([
      this.findOfficeExecutable("WINWORD.EXE"),
      this.findOfficeExecutable("EXCEL.EXE"),
      this.findOfficeExecutable("POWERPNT.EXE")
    ]);
    return {
      ok: true,
      microsoft_office_installed: Boolean(word || excel || powerpoint),
      apps: {
        word: { installed: Boolean(word), path: word || "" },
        excel: { installed: Boolean(excel), path: excel || "" },
        powerpoint: { installed: Boolean(powerpoint), path: powerpoint || "" }
      }
    };
  }

  private async officeOpen(body: Record<string, unknown>): Promise<BridgeResult> {
    const target = this.resolveScoped(body.path);
    const appName = String(body.app || "").trim().toLowerCase();
    const exeName = appName === "excel"
      ? "EXCEL.EXE"
      : appName === "powerpoint" || appName === "ppt" || appName === "pptx"
        ? "POWERPNT.EXE"
        : appName === "word" || appName === "doc" || appName === "docx"
          ? "WINWORD.EXE"
          : "";
    if (!exeName) {
      throw new Error("app must be one of word, excel, or powerpoint.");
    }
    const executable = await this.findOfficeExecutable(exeName);
    if (!executable) {
      throw new Error(`Microsoft ${appName || exeName} is not installed or not discoverable on this Windows computer.`);
    }
    await this.requireApproval("open", `Open in Microsoft Office:\n${target}\n\nApplication:\n${executable}`);
    const child = spawn(executable, [target], { detached: true, stdio: "ignore", windowsHide: false });
    await new Promise<void>((resolve, reject) => {
      child.once("error", reject);
      child.once("spawn", resolve);
    });
    child.unref();
    return { ok: true, path: target, opened: true, app: appName || exeName, executable };
  }

  private async findOfficeExecutable(exeName: string): Promise<string> {
    const normalized = exeName.toUpperCase();
    try {
      const found = await this.execSimple("where.exe", [normalized]);
      const first = found.split(/\r?\n/).map((line) => line.trim()).find(Boolean);
      if (first) {
        return first;
      }
    } catch {
      // Registry lookup below covers common Click-to-Run installs.
    }

    const keys = [
      `HKCU\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\${normalized}`,
      `HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths\\${normalized}`,
      `HKLM\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\App Paths\\${normalized}`
    ];
    for (const key of keys) {
      try {
        const output = await this.execSimple("reg.exe", ["query", key, "/ve"]);
        const match = output.match(/REG_SZ\s+(.+)\s*$/im);
        if (match?.[1]?.trim()) {
          return match[1].trim().replace(/^"|"$/g, "");
        }
      } catch {
        continue;
      }
    }
    return "";
  }

  private async execSimple(command: string, args: string[]): Promise<string> {
    return await new Promise<string>((resolve, reject) => {
      execFile(command, args, { windowsHide: true, timeout: 8000, maxBuffer: 128 * 1024 }, (error, stdout, stderr) => {
        if (error) {
          reject(error);
          return;
        }
        resolve(String(stdout || stderr || ""));
      });
    });
  }
}
