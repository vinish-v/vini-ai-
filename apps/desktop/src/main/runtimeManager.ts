import { app, shell } from "electron";
import { execFile } from "node:child_process";
import { existsSync } from "node:fs";
import { promises as fs } from "node:fs";
import http from "node:http";
import path from "node:path";
import { fileURLToPath } from "node:url";
import type {
  ContainerStatus,
  DockerStatus,
  HealthStatus,
  HostBridgeStatus,
  ProviderStatus,
  RecentEntry,
  RuntimeActionResult,
  RuntimeBlocker,
  RuntimeLogResult,
  RuntimePaths,
  RuntimeStatus
} from "./types.js";
import type { HostBridge } from "./hostBridge.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const CONTAINER_NAME = "vini-ai-agent-zero";
const IMAGE = "vini-ai/agent-runtime:local";
const BASE_IMAGE = "agent0ai/agent-zero:latest";
const HOST_PORT = 50080;
const RUNTIME_URL = `http://127.0.0.1:${HOST_PORT}`;
const HEALTH_URL = `${RUNTIME_URL}/api/health`;

type CommandResult = {
  stdout: string;
  stderr: string;
};

function run(command: string, args: string[], timeoutMs = 20000): Promise<CommandResult> {
  return new Promise((resolve, reject) => {
    execFile(command, args, { windowsHide: true, timeout: timeoutMs }, (error, stdout, stderr) => {
      if (error) {
        const err = error as Error & { code?: string | number; stdout?: string; stderr?: string };
        err.stdout = stdout;
        err.stderr = stderr;
        reject(err);
        return;
      }
      resolve({ stdout: String(stdout || ""), stderr: String(stderr || "") });
    });
  });
}

function commandError(error: unknown): string {
  if (error instanceof Error) {
    const enriched = error as Error & { stderr?: string; stdout?: string; code?: string | number };
    const detail = [enriched.stderr, enriched.stdout].filter(Boolean).join("\n").trim();
    return detail || enriched.message;
  }
  return String(error);
}

async function pathExists(target: string): Promise<boolean> {
  try {
    await fs.access(target);
    return true;
  } catch {
    return false;
  }
}

async function readJsonFile(target: string): Promise<Record<string, unknown> | null> {
  try {
    const raw = await fs.readFile(target, "utf8");
    return JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return null;
  }
}

async function readEnvKeys(target: string): Promise<string[]> {
  try {
    const raw = await fs.readFile(target, "utf8");
    return raw
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => /^API_KEY_[A-Z0-9_]+=.+/.test(line))
      .map((line) => line.split("=")[0]);
  } catch {
    return [];
  }
}

function providerFromSettings(settings: Record<string, unknown> | null, envKeys: string[], settingsExists: boolean): ProviderStatus {
  const configuredProviders: string[] = [];
  const apiKeys = settings?.api_keys;

  if (apiKeys && typeof apiKeys === "object" && !Array.isArray(apiKeys)) {
    for (const [provider, value] of Object.entries(apiKeys as Record<string, unknown>)) {
      if (typeof value === "string" && value.trim() && value !== "************" && value !== "****PSWD****") {
        configuredProviders.push(provider);
      }
    }
  }

  if (envKeys.length > 0) {
    configuredProviders.push(...envKeys.map((key) => key.replace(/^API_KEY_/, "").toLowerCase()));
  }

  const uniqueProviders = Array.from(new Set(configuredProviders));
  if (uniqueProviders.length > 0) {
    return {
      state: "configured",
      evidence: `Detected provider key entries for ${uniqueProviders.join(", ")} in Vini AI runtime data.`
    };
  }

  if (settingsExists || envKeys.length === 0) {
    return {
      state: "not_configured",
      evidence: "No provider API key entries were found in the mounted Vini AI settings or .env files."
    };
  }

  return {
    state: "unknown",
    evidence: "Provider state is managed by Vini AI and could not be read from local data."
  };
}

function requestHealth(url: string): Promise<HealthStatus> {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: 5000 }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => {
        let parsed: Record<string, unknown> | undefined;
        try {
          parsed = JSON.parse(body) as Record<string, unknown>;
        } catch {
          parsed = undefined;
        }
        resolve({
          ok: Boolean(res.statusCode && res.statusCode >= 200 && res.statusCode < 400),
          url: RUNTIME_URL,
          apiUrl: url,
          statusCode: res.statusCode,
          gitinfo: parsed?.gitinfo
        });
      });
    });

    req.on("timeout", () => {
      req.destroy(new Error("Health probe timed out."));
    });

    req.on("error", (error) => {
      resolve({
        ok: false,
        url: RUNTIME_URL,
        apiUrl: url,
        error: error.message
      });
    });
  });
}

async function listRecentEntries(paths: RuntimePaths): Promise<RecentEntry[]> {
  const candidates = [
    paths.usrDir,
    path.join(paths.usrDir, "workdir"),
    path.join(paths.usrDir, "projects"),
    path.join(paths.usrDir, "chats"),
    path.join(paths.usrDir, "memory")
  ];

  const entries: RecentEntry[] = [];
  for (const candidate of candidates) {
    if (!(await pathExists(candidate))) {
      continue;
    }
    try {
      const children = await fs.readdir(candidate, { withFileTypes: true });
      for (const child of children) {
        const fullPath = path.join(candidate, child.name);
        const stats = await fs.stat(fullPath);
        entries.push({
          name: child.name,
          path: fullPath,
          kind: child.isDirectory() ? "directory" : "file",
          modifiedAt: stats.mtime.toISOString()
        });
      }
    } catch {
      continue;
    }
  }

  return entries.sort((a, b) => Date.parse(b.modifiedAt) - Date.parse(a.modifiedAt)).slice(0, 8);
}

export class RuntimeManager {
  constructor(private readonly hostBridge?: HostBridge) {}

  resolveRuntimeDir(): string {
    const candidates = [
      process.env.VINI_AI_AGENT_ZERO_DIR,
      path.resolve(app.getAppPath(), "../../runtime/agent-zero"),
      path.resolve(app.getAppPath(), "../../../runtime/agent-zero"),
      path.resolve(app.getAppPath(), "../../../../runtime/agent-zero"),
      path.resolve(process.cwd(), "runtime/agent-zero"),
      path.resolve(process.cwd(), "../../runtime/agent-zero"),
      path.resolve(__dirname, "../../../../runtime/agent-zero"),
      path.join(process.resourcesPath || "", "runtime/agent-zero")
    ].filter(Boolean) as string[];

    const found = candidates.find((candidate) => existsSync(path.join(candidate, "README.md")));
    return found || candidates[0];
  }

  getPaths(): RuntimePaths {
    const appData = app.getPath("userData");
    const runtimeDir = this.resolveRuntimeDir();
    const dataDir = path.join(appData, "agent-zero");
    const usrDir = path.join(dataDir, "usr");

    return {
      runtimeDir,
      dataDir,
      usrDir,
      settingsPath: path.join(usrDir, "settings.json"),
      envPath: path.join(dataDir, ".env")
    };
  }

  async ensureDataDirs(): Promise<RuntimePaths> {
    const paths = this.getPaths();
    await fs.mkdir(paths.usrDir, { recursive: true });
    return paths;
  }

  async getDockerStatus(): Promise<DockerStatus> {
    try {
      const version = (await run("docker", ["--version"], 10000)).stdout.trim();
      try {
        await run("docker", ["info", "--format", "{{json .ServerVersion}}"], 10000);
        return { available: true, daemonAvailable: true, version };
      } catch (daemonError) {
        return {
          available: true,
          daemonAvailable: false,
          version,
          error: commandError(daemonError)
        };
      }
    } catch (error) {
      return {
        available: false,
        daemonAvailable: false,
        error: commandError(error)
      };
    }
  }

  async getContainerStatus(): Promise<ContainerStatus> {
    try {
      const result = await run(
        "docker",
        [
          "inspect",
          CONTAINER_NAME,
          "--format",
          "{{json .}}"
        ],
        10000
      );
      const info = JSON.parse(result.stdout) as {
        Id?: string;
        Image?: string;
        Config?: { Image?: string; Env?: string[] };
        State?: { Running?: boolean; Status?: string; StartedAt?: string; ExitCode?: number };
        NetworkSettings?: { Ports?: Record<string, Array<{ HostIp?: string; HostPort?: string }> | null> };
      };

      const mappedPorts = Object.entries(info.NetworkSettings?.Ports || {})
        .flatMap(([containerPort, hostBindings]) =>
          (hostBindings || []).map((binding) => `${binding.HostIp || "0.0.0.0"}:${binding.HostPort}->${containerPort}`)
        )
        .join(", ");

      return {
        name: CONTAINER_NAME,
        exists: true,
        running: Boolean(info.State?.Running),
        status: info.State?.Status,
        image: info.Config?.Image,
        imageId: info.Image,
        id: info.Id?.slice(0, 12),
        startedAt: info.State?.StartedAt,
        exitCode: info.State?.ExitCode,
        ports: mappedPorts,
        hostBridgeConfigured: Boolean(
          info.Config?.Env?.some((entry) => entry.startsWith("VINI_HOST_BRIDGE_URL=")) &&
          info.Config?.Env?.some((entry) => entry.startsWith("VINI_HOST_BRIDGE_TOKEN="))
        )
      };
    } catch (error) {
      return {
        name: CONTAINER_NAME,
        exists: false,
        running: false,
        error: commandError(error)
      };
    }
  }

  async hasRuntimeImage(): Promise<boolean> {
    try {
      await run("docker", ["image", "inspect", IMAGE], 10000);
      return true;
    } catch {
      return false;
    }
  }

  async getRuntimeImageId(): Promise<string | undefined> {
    try {
      return (await run("docker", ["image", "inspect", IMAGE, "--format", "{{.Id}}"], 10000)).stdout.trim();
    } catch {
      return undefined;
    }
  }

  async buildRuntimeImage(): Promise<void> {
    const runtimeRoot = path.dirname(this.getPaths().runtimeDir);
    await run(
      "docker",
      [
        "build",
        "-f",
        path.join(runtimeRoot, "Dockerfile.vini-ai"),
        "-t",
        IMAGE,
        runtimeRoot
      ],
      15 * 60 * 1000
    );
  }

  async getStatus(): Promise<RuntimeStatus> {
    const paths = await this.ensureDataDirs();
    const [docker, container, health, recentEntries, settingsExists, envKeys, runtimeImageExists] = await Promise.all([
      this.getDockerStatus(),
      this.getContainerStatus(),
      requestHealth(HEALTH_URL),
      listRecentEntries(paths),
      pathExists(paths.settingsPath),
      readEnvKeys(paths.envPath),
      this.hasRuntimeImage()
    ]);
    const settings = settingsExists ? await readJsonFile(paths.settingsPath) : null;
    const provider = providerFromSettings(settings, envKeys, settingsExists);
    const blockers = this.deriveBlockers(docker, container, health, provider, runtimeImageExists);

    return {
      checkedAt: new Date().toISOString(),
      url: RUNTIME_URL,
      containerName: CONTAINER_NAME,
      image: runtimeImageExists ? IMAGE : `${IMAGE} (not built yet; base ${BASE_IMAGE})`,
      hostPort: HOST_PORT,
      docker,
      container,
      health,
      provider,
      hostBridge: this.getHostBridgeStatus(),
      paths,
      recentEntries,
      blockers
    };
  }

  getHostBridgeStatus(): HostBridgeStatus | undefined {
    if (!this.hostBridge) {
      return undefined;
    }
    return {
      enabled: true,
      url: this.hostBridge.getUrl(),
      dockerUrl: this.hostBridge.getDockerUrl(),
      tokenFingerprint: this.hostBridge.tokenFingerprint(),
      configPath: this.hostBridge.getConfigPath()
    };
  }

  deriveBlockers(
    docker: DockerStatus,
    container: ContainerStatus,
    health: HealthStatus,
    provider: ProviderStatus,
    runtimeImageExists = true
  ): RuntimeBlocker[] {
    const blockers: RuntimeBlocker[] = [];

    if (!docker.available) {
      blockers.push({
        severity: "error",
        code: "docker_missing",
        message: "Docker CLI was not found. Install Docker Desktop before starting the Vini AI runtime."
      });
      return blockers;
    }

    if (!docker.daemonAvailable) {
      blockers.push({
        severity: "error",
        code: "docker_daemon_unavailable",
        message: "Docker is installed, but the daemon is not responding. Start Docker Desktop and retry."
      });
      return blockers;
    }

    if (!runtimeImageExists) {
      blockers.push({
        severity: "warning",
        code: "runtime_image_not_built",
        message: "The local Vini AI runtime image has not been built yet. Start will build it from the rebranded local runtime source."
      });
    }

    if (!container.exists) {
      blockers.push({
        severity: "warning",
        code: "container_not_created",
        message: "The Vini AI runtime container has not been created yet."
      });
    } else if (!container.running) {
      blockers.push({
        severity: "error",
        code: "container_not_running",
        message: `The runtime container exists but is not running. Docker reports status: ${container.status || "unknown"}.`
      });
    }

    if (container.running && !health.ok) {
      blockers.push({
        severity: "error",
        code: "runtime_unavailable",
        message: `The container is running, but the Vini AI health endpoint is unavailable: ${health.error || health.statusCode || "unknown error"}.`
      });
    }

    if (container.exists && container.running && container.hostBridgeConfigured === false) {
      blockers.push({
        severity: "warning",
        code: "host_bridge_not_attached",
        message: "The runtime container is running without the Windows host bridge environment. Restart Vini AI to attach scoped host access."
      });
    }

    if (provider.state === "not_configured") {
      blockers.push({
        severity: "warning",
        code: "provider_not_configured",
        message: "No provider key was detected in Vini AI local data. Configure models inside Vini AI before running real tasks."
      });
    }

    if (blockers.length === 0) {
      blockers.push({
        severity: "info",
        code: "ready",
        message: "Docker, container, and Vini AI health checks are passing."
      });
    }

    return blockers;
  }

  async start(): Promise<RuntimeActionResult> {
    const paths = await this.ensureDataDirs();
    const docker = await this.getDockerStatus();
    if (!docker.available || !docker.daemonAvailable) {
      return {
        ok: false,
        message: docker.error || "Docker is not ready.",
        status: await this.getStatus()
      };
    }

    const container = await this.getContainerStatus();
    try {
      if (!(await this.hasRuntimeImage())) {
        await this.buildRuntimeImage();
      }

      const runtimeImageId = await this.getRuntimeImageId();
      if (container.exists && (container.image !== IMAGE || (runtimeImageId && container.imageId !== runtimeImageId))) {
        if (container.running) {
          await run("docker", ["stop", CONTAINER_NAME], 30000);
        }
        await run("docker", ["rm", CONTAINER_NAME], 30000);
      }

      const currentContainer = await this.getContainerStatus();

      if (currentContainer.exists) {
        if (!currentContainer.hostBridgeConfigured) {
          if (currentContainer.running) {
            await run("docker", ["stop", CONTAINER_NAME], 30000);
          }
          await run("docker", ["rm", CONTAINER_NAME], 30000);
          return this.start();
        }
        if (currentContainer.running) {
          return {
            ok: true,
            message: "Vini AI runtime is already running.",
            status: await this.getStatus()
          };
        }
        await run("docker", ["start", CONTAINER_NAME], 30000);
      } else {
        await run(
          "docker",
          [
            "run",
            "-d",
            "--name",
            CONTAINER_NAME,
            "--restart",
            "unless-stopped",
            "-p",
            `${HOST_PORT}:80`,
            "-e",
            `VINI_HOST_BRIDGE_URL=${this.hostBridge?.getDockerUrl() || ""}`,
            "-e",
            `VINI_HOST_BRIDGE_TOKEN=${this.hostBridge?.getToken() || ""}`,
            "-v",
            `${paths.usrDir}:/a0/usr`,
            IMAGE
          ],
          120000
        );
      }

      return {
        ok: true,
        message: "Vini AI runtime start command completed.",
        status: await this.getStatus()
      };
    } catch (error) {
      return {
        ok: false,
        message: commandError(error),
        status: await this.getStatus()
      };
    }
  }

  async stop(): Promise<RuntimeActionResult> {
    const container = await this.getContainerStatus();
    if (!container.exists) {
      return {
        ok: true,
        message: "Vini AI runtime container does not exist.",
        status: await this.getStatus()
      };
    }

    if (!container.running) {
      return {
        ok: true,
        message: "Vini AI runtime container is already stopped.",
        status: await this.getStatus()
      };
    }

    try {
      await run("docker", ["stop", CONTAINER_NAME], 30000);
      return {
        ok: true,
        message: "Vini AI runtime stopped.",
        status: await this.getStatus()
      };
    } catch (error) {
      return {
        ok: false,
        message: commandError(error),
        status: await this.getStatus()
      };
    }
  }

  async restart(): Promise<RuntimeActionResult> {
    const container = await this.getContainerStatus();
    if (!container.exists) {
      return this.start();
    }

    try {
      await run("docker", ["restart", CONTAINER_NAME], 60000);
      return {
        ok: true,
        message: "Vini AI runtime restarted.",
        status: await this.getStatus()
      };
    } catch (error) {
      return {
        ok: false,
        message: commandError(error),
        status: await this.getStatus()
      };
    }
  }

  async logs(): Promise<RuntimeLogResult> {
    try {
      const result = await run("docker", ["logs", "--tail", "160", CONTAINER_NAME], 20000);
      return {
        ok: true,
        logs: [result.stdout, result.stderr].filter(Boolean).join("\n").trim()
      };
    } catch (error) {
      return {
        ok: false,
        logs: "",
        error: commandError(error)
      };
    }
  }

  async openRuntime(): Promise<void> {
    await shell.openExternal(RUNTIME_URL);
  }

  async openDataDir(): Promise<void> {
    const paths = await this.ensureDataDirs();
    await shell.openPath(paths.dataDir);
  }

  async openRuntimeDir(): Promise<void> {
    await shell.openPath(this.getPaths().runtimeDir);
  }
}
