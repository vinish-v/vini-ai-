import { open as openSurface } from "/js/surfaces.js";

const AUTO_OPEN_WINDOW_MS = 10 * 60 * 1000;
const openedResults = new Set();

export default async function syncBuilderResultsIntoCanvas(context) {
  if (!context?.results?.length || context.historyEmpty) return;

  for (const { args } of context.results) {
    const payload = getToolResultPayload(args);
    if (getToolName(payload) !== "vini_app_builder") continue;
    if (!isFresh(args.timestamp, payload.last_modified)) continue;

    const result = parseMaybeJson(payload.tool_result) || parseMaybeJson(args.content) || {};
    const projectId = getProjectId(payload, result);
    const key = [args?.id || "", projectId || "", payload.action || ""].join(":");
    const persistedKey = `vini.builder.opened.${key}`;
    if (hasOpened(key, persistedKey)) continue;

    requestAnimationFrame(async () => {
      await openSurface("build", { projectId, source: "vini-app-builder-tool-result" });
    });
  }
}

function getToolResultPayload(args = {}) {
  const contentPayload = parseMaybeJson(args.content);
  const kvpsPayload = parseMaybeJson(args.kvps);
  return {
    ...(pickPayloadFields(args) || {}),
    ...(contentPayload || {}),
    ...(kvpsPayload || {}),
  };
}

function pickPayloadFields(args = {}) {
  const payload = {};
  for (const key of [
    "_tool_name",
    "tool_name",
    "tool_result",
    "action",
    "project_id",
    "projectId",
    "last_modified",
  ]) {
    if (args[key] != null && args[key] !== "") payload[key] = args[key];
  }
  return payload;
}

function getToolName(payload = {}) {
  return String(payload._tool_name || payload.tool_name || "").trim();
}

function getProjectId(payload = {}, result = {}) {
  return (
    result.project_id
    || result.project?.project_id
    || payload.project_id
    || payload.projectId
    || ""
  );
}

function parseMaybeJson(value) {
  if (!value) return null;
  if (typeof value === "object") return value;
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (!trimmed.startsWith("{")) return null;
  try {
    const parsed = JSON.parse(trimmed);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
}

function isFresh(timestamp, fallbackTimestamp) {
  const messageMs = toMs(timestamp) || toMs(fallbackTimestamp);
  if (!messageMs) return true;
  return Math.abs(Date.now() - messageMs) <= AUTO_OPEN_WINDOW_MS;
}

function toMs(value) {
  if (value == null || value === "") return 0;
  const numeric = Number(value);
  if (Number.isFinite(numeric) && numeric > 0) {
    return numeric > 10_000_000_000 ? numeric : numeric * 1000;
  }
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : 0;
}

function hasOpened(key, persistedKey) {
  if (openedResults.has(key)) return true;
  openedResults.add(key);
  try {
    if (sessionStorage.getItem(persistedKey)) return true;
    sessionStorage.setItem(persistedKey, "1");
  } catch {
    // In-memory tracking still prevents repeated surface opens.
  }
  return false;
}
