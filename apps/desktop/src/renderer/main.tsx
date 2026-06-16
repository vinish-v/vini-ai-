import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Database,
  ExternalLink,
  FolderOpen,
  HardDrive,
  Play,
  RefreshCw,
  Square,
  Terminal,
  XCircle
} from "lucide-react";
import type { RuntimeActionResult, RuntimeBlocker, RuntimeLogResult, RuntimeStatus } from "../main/types.js";
import "./styles.css";

type ActionName = "start" | "stop" | "restart" | "refresh" | "logs";

function formatDate(value?: string): string {
  if (!value) {
    return "Not available";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function statusText(status: RuntimeStatus | null): string {
  if (!status) {
    return "Checking";
  }
  if (!status.docker.available) {
    return "Docker missing";
  }
  if (!status.docker.daemonAvailable) {
    return "Docker stopped";
  }
  if (!status.container.exists) {
    return "Not created";
  }
  if (!status.container.running) {
    return "Stopped";
  }
  if (!status.health.ok) {
    return "Starting";
  }
  return "Runtime online";
}

function blockerIcon(blocker: RuntimeBlocker) {
  if (blocker.severity === "error") {
    return <XCircle size={17} />;
  }
  if (blocker.severity === "warning") {
    return <AlertTriangle size={17} />;
  }
  return <CheckCircle2 size={17} />;
}

function Metric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "good" | "warn" | "bad" | "neutral" }) {
  return (
    <div className={`metric metric-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ToolbarButton({
  icon,
  children,
  onClick,
  disabled
}: {
  icon: React.ReactNode;
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button className="toolbar-button" onClick={onClick} disabled={disabled}>
      {icon}
      <span>{children}</span>
    </button>
  );
}

function App() {
  const [status, setStatus] = useState<RuntimeStatus | null>(null);
  const [logs, setLogs] = useState<RuntimeLogResult | null>(null);
  const [message, setMessage] = useState<string>("Waiting for first status check.");
  const [busyAction, setBusyAction] = useState<ActionName | null>(null);

  const refresh = async () => {
    setBusyAction((current) => current ?? "refresh");
    try {
      const next = await window.vini.runtime.getStatus();
      setStatus(next);
      setMessage(`Status checked at ${formatDate(next.checkedAt)}.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyAction((current) => (current === "refresh" ? null : current));
    }
  };

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => {
      void window.vini.runtime.getStatus().then(setStatus).catch(() => undefined);
    }, 8000);
    return () => window.clearInterval(timer);
  }, []);

  const runAction = async (action: ActionName, fn: () => Promise<RuntimeActionResult | RuntimeLogResult | void>) => {
    setBusyAction(action);
    try {
      const result = await fn();
      if (result && "status" in result && result.status) {
        setStatus(result.status);
      }
      if (result && "logs" in result) {
        setLogs(result);
        setMessage(result.ok ? "Docker logs loaded from the real runtime container." : result.error || "Unable to load logs.");
      } else if (result && "message" in result) {
        setMessage(result.message);
      }
      if (!result) {
        setMessage("Command completed.");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyAction(null);
    }
  };

  const openRecentEntry = async (entry: RuntimeStatus["recentEntries"][number]) => {
    if (!entry.contextId) {
      setMessage("This recent item is not a saved chat or task session yet.");
      return;
    }
    await runAction("refresh", () => window.vini.runtime.openContext(entry.contextId!));
  };

  const primaryTone = useMemo(() => {
    if (!status) {
      return "neutral";
    }
    if (!status.docker.available || !status.docker.daemonAvailable || (status.container.exists && !status.container.running)) {
      return "bad";
    }
    if (!status.container.exists || !status.health.ok || status.provider.state === "not_configured") {
      return "warn";
    }
    return "good";
  }, [status]);

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <img src="/vini-ai-mark.png" alt="" />
          </div>
          <div>
            <h1>Vini AI</h1>
            <p>Agent runtime control</p>
          </div>
        </div>

        <nav className="nav-stack" aria-label="Vini AI sections">
          <a className="nav-item active" href="#runtime">
            <Activity size={18} />
            Runtime
          </a>
          <a className="nav-item" href="#storage">
            <Database size={18} />
            Storage
          </a>
          <a className="nav-item" href="#logs">
            <Terminal size={18} />
            Logs
          </a>
        </nav>

        <div className="side-note">
          <strong>No mock state</strong>
          <span>All status cards are read from Docker, HTTP health probes, or local Vini AI runtime files.</span>
        </div>
      </aside>

      <section className="content">
        <header className="topbar">
          <div>
            <p className="overline">Windows desktop shell</p>
            <h2>Vini AI controls the local Vini AI runtime</h2>
          </div>
          <div className={`status-chip status-${primaryTone}`}>
            <span />
            {statusText(status)}
          </div>
        </header>

        <section className="hero-panel" id="runtime">
          <div className="hero-copy">
            <p className="overline">Runtime endpoint</p>
            <h3>{status?.url || "http://127.0.0.1:50080"}</h3>
            <p>{message}</p>
          </div>
          <div className="toolbar">
            <ToolbarButton icon={<Play size={16} />} onClick={() => runAction("start", window.vini.runtime.start)} disabled={Boolean(busyAction)}>
              Start
            </ToolbarButton>
            <ToolbarButton icon={<Square size={16} />} onClick={() => runAction("stop", window.vini.runtime.stop)} disabled={Boolean(busyAction)}>
              Stop
            </ToolbarButton>
            <ToolbarButton icon={<RefreshCw size={16} />} onClick={() => runAction("restart", window.vini.runtime.restart)} disabled={Boolean(busyAction)}>
              Restart
            </ToolbarButton>
            <ToolbarButton icon={<ExternalLink size={16} />} onClick={() => runAction("refresh", window.vini.runtime.open)} disabled={!status?.health.ok}>
              Open
            </ToolbarButton>
          </div>
        </section>

        <section className="metric-grid" aria-label="Runtime checks">
          <Metric label="Docker CLI" value={status?.docker.version || status?.docker.error || "Checking"} tone={status?.docker.available ? "good" : "bad"} />
          <Metric
            label="Docker daemon"
            value={status?.docker.daemonAvailable ? "Responding" : status?.docker.error || "Checking"}
            tone={status?.docker.daemonAvailable ? "good" : "bad"}
          />
          <Metric
            label="Container"
            value={status?.container.exists ? `${status.container.status || "unknown"} ${status.container.id ? `(${status.container.id})` : ""}` : "Not created"}
            tone={status?.container.running ? "good" : status?.container.exists ? "bad" : "warn"}
          />
          <Metric
            label="Health"
            value={status?.health.ok ? `HTTP ${status.health.statusCode}` : status?.health.error || "Unavailable"}
            tone={status?.health.ok ? "good" : "warn"}
          />
          <Metric label="Provider" value={status?.provider.state.replace("_", " ") || "Checking"} tone={status?.provider.state === "configured" ? "good" : "warn"} />
          <Metric label="Image" value={status?.image || "vini-ai/agent-runtime:local"} />
        </section>

        <section className="two-column">
          <div className="panel">
            <div className="panel-title">
              <AlertTriangle size={18} />
              <h3>Current blockers</h3>
            </div>
            <div className="blocker-list">
              {(status?.blockers || []).map((blocker) => (
                <div className={`blocker blocker-${blocker.severity}`} key={blocker.code}>
                  {blockerIcon(blocker)}
                  <div>
                    <strong>{blocker.code}</strong>
                    <span>{blocker.message}</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="fine-print">{status?.provider.evidence || "Provider state has not been checked yet."}</p>
          </div>

          <div className="panel" id="storage">
            <div className="panel-title">
              <HardDrive size={18} />
              <h3>Runtime storage</h3>
            </div>
            <dl className="path-list">
              <div>
                <dt>Vini AI runtime source</dt>
                <dd>{status?.paths.runtimeDir || "Checking"}</dd>
              </div>
              <div>
                <dt>User data mount</dt>
                <dd>{status?.paths.usrDir || "Checking"}</dd>
              </div>
              <div>
                <dt>Settings file</dt>
                <dd>{status?.paths.settingsPath || "Checking"}</dd>
              </div>
            </dl>
            <div className="inline-actions">
              <button onClick={() => runAction("refresh", window.vini.runtime.openDataDir)}>
                <FolderOpen size={15} />
                Open data
              </button>
              <button onClick={() => runAction("refresh", window.vini.runtime.openRuntimeDir)}>
                <FolderOpen size={15} />
                Open runtime
              </button>
            </div>
          </div>
        </section>

        <section className="two-column bottom-grid">
          <div className="panel">
            <div className="panel-title">
              <Database size={18} />
              <h3>Recent workspace activity</h3>
            </div>
            <div className="activity-list">
              {status?.recentEntries.length ? (
                status.recentEntries.map((entry) => {
                  const rowContent = (
                    <>
                      <span>{entry.contextId ? "session" : entry.kind}</span>
                      <strong title={entry.path}>{entry.contextName || entry.name}</strong>
                      <time>{formatDate(entry.modifiedAt)}</time>
                    </>
                  );

                  return entry.contextId ? (
                    <button className="activity-row activity-button" key={entry.path} onClick={() => void openRecentEntry(entry)} title={`Open ${entry.contextName || entry.name}`}>
                      {rowContent}
                    </button>
                  ) : (
                    <div className="activity-row" key={entry.path}>
                      {rowContent}
                    </div>
                  );
                })
              ) : (
                <p className="empty-state">No Vini AI runtime user files have been created in the data mount yet.</p>
              )}
            </div>
          </div>

          <div className="panel" id="logs">
            <div className="panel-title">
              <Terminal size={18} />
              <h3>Container logs</h3>
              <button className="small-button" onClick={() => runAction("logs", window.vini.runtime.logs)} disabled={Boolean(busyAction)}>
                Load logs
              </button>
            </div>
            <pre className="log-view">{logs?.ok ? logs.logs || "No logs returned." : logs?.error || "Load logs to inspect the real Docker container output."}</pre>
          </div>
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
