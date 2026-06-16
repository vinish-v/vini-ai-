export type RuntimeBlocker = {
  severity: "info" | "warning" | "error";
  code: string;
  message: string;
};

export type DockerStatus = {
  available: boolean;
  daemonAvailable: boolean;
  version?: string;
  error?: string;
};

export type ContainerStatus = {
  name: string;
  exists: boolean;
  running: boolean;
  status?: string;
  image?: string;
  imageId?: string;
  id?: string;
  startedAt?: string;
  exitCode?: number;
  ports?: string;
  hostBridgeConfigured?: boolean;
  error?: string;
};

export type HostBridgeStatus = {
  enabled: boolean;
  url: string;
  dockerUrl: string;
  tokenFingerprint?: string;
  configPath: string;
};

export type HealthStatus = {
  ok: boolean;
  url: string;
  apiUrl: string;
  statusCode?: number;
  error?: string;
  gitinfo?: unknown;
};

export type ProviderStatus = {
  state: "configured" | "not_configured" | "unknown";
  evidence: string;
};

export type RecentEntry = {
  name: string;
  path: string;
  kind: "file" | "directory";
  modifiedAt: string;
  contextId?: string;
  contextName?: string;
  openUrl?: string;
};

export type RuntimePaths = {
  runtimeDir: string;
  dataDir: string;
  usrDir: string;
  settingsPath: string;
  envPath: string;
};

export type RuntimeStatus = {
  checkedAt: string;
  url: string;
  containerName: string;
  image: string;
  hostPort: number;
  docker: DockerStatus;
  container: ContainerStatus;
  health: HealthStatus;
  provider: ProviderStatus;
  hostBridge?: HostBridgeStatus;
  paths: RuntimePaths;
  recentEntries: RecentEntry[];
  blockers: RuntimeBlocker[];
};

export type RuntimeLogResult = {
  ok: boolean;
  logs: string;
  error?: string;
};

export type RuntimeActionResult = {
  ok: boolean;
  message: string;
  status?: RuntimeStatus;
};
