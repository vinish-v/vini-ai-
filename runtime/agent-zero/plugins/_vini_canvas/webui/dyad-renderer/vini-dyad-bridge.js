(function () {
  if (window.electron?.ipcRenderer) return;

  const MODEL_API_BASE = "/api/plugins/_model_config";
  const CANVAS_API_BASE = "/api/plugins/_vini_canvas";

  const PROVIDER_ENV = {
    openai: "OPENAI_API_KEY",
    anthropic: "ANTHROPIC_API_KEY",
    google: "GEMINI_API_KEY",
    openrouter: "OPENROUTER_API_KEY",
    azure: "AZURE_API_KEY",
    xai: "XAI_API_KEY",
    bedrock: "AWS_BEARER_TOKEN_BEDROCK",
    minimax: "MINIMAX_API_KEY",
  };

  const PROVIDER_NAMES = {
    auto: "Dyad",
    openai: "OpenAI",
    anthropic: "Anthropic",
    google: "Google",
    vertex: "Google Vertex AI",
    openrouter: "OpenRouter",
    azure: "Azure OpenAI",
    xai: "xAI",
    bedrock: "AWS Bedrock",
    minimax: "MiniMax",
    ollama: "Ollama",
    lmstudio: "LM Studio",
    lm_studio: "LM Studio",
  };

  const PROVIDER_TYPE = {
    ollama: "local",
    lmstudio: "local",
    lm_studio: "local",
  };

  const CLOUD_PROVIDERS = new Set([
    "openai",
    "anthropic",
    "google",
    "vertex",
    "auto",
    "openrouter",
    "azure",
    "xai",
    "bedrock",
    "minimax",
  ]);

  let csrfToken = null;
  let statePromise = null;
  let savedSettings = null;
  const listeners = new Map();

  async function getCsrfToken() {
    if (csrfToken) return csrfToken;
    const response = await fetch("/api/csrf_token", { credentials: "same-origin" });
    const data = await response.json();
    if (!response.ok || !data.ok || !data.token) {
      throw new Error(data.error || "Unable to read Vini runtime CSRF token");
    }
    csrfToken = data.token;
    if (data.runtime_id) {
      const secureFlag = window.location.protocol === "https:" ? "; Secure" : "";
      document.cookie = `csrf_token_${data.runtime_id}=${csrfToken}; SameSite=Lax; Path=/${secureFlag}`;
    }
    return csrfToken;
  }

  async function postJson(url, body) {
    const token = await getCsrfToken();
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": token,
      },
      body: JSON.stringify(body || {}),
    });
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `Vini runtime API failed: ${response.status}`);
    }
    return await response.json();
  }

  async function canvasBackend(action, payload = {}) {
    const result = await postJson(`${CANVAS_API_BASE}/backend`, {
      action,
      ...payload,
    });
    if (!result?.ok) {
      throw new Error(result?.error || `Vini Canvas backend action failed: ${action}`);
    }
    return result;
  }

  function emit(channel, payload) {
    const channelListeners = listeners.get(channel);
    if (!channelListeners) return;
    for (const listener of channelListeners) {
      try {
        listener(payload);
      } catch (error) {
        console.error(`Vini Canvas listener failed for ${channel}`, error);
      }
    }
  }

  function normalizeProviderId(provider) {
    const value = String(provider || "").trim().toLowerCase();
    if (value === "lm_studio") return "lmstudio";
    return value;
  }

  function toDyadModelName(provider, name) {
    const cleanName = String(name || "").trim();
    if (!cleanName) return provider === "openrouter" ? "openrouter/free" : "auto";
    if (provider === "openrouter" && cleanName.startsWith("openrouter/")) {
      return cleanName.slice("openrouter/".length);
    }
    return cleanName;
  }

  function toDyadProvider(provider) {
    const id = normalizeProviderId(provider);
    return id || "openrouter";
  }

  function providerToRecord(provider, apiKeyStatus) {
    const id = normalizeProviderId(provider.value || provider.id);
    if (!id) return null;
    const type = PROVIDER_TYPE[id] || (CLOUD_PROVIDERS.has(id) ? "cloud" : "custom");
    return {
      id,
      name: provider.label || provider.name || PROVIDER_NAMES[id] || id,
      type,
      hasFreeTier: id === "google" || id === "openrouter" || type === "local",
      envVarName: PROVIDER_ENV[id],
      apiBaseUrl: provider.api_base || undefined,
      isCustom: type === "custom",
      secondary: ["vertex", "azure", "bedrock", "xai", "minimax"].includes(id),
      _viniHasKey: Boolean(apiKeyStatus?.[id]),
    };
  }

  function settingsFromConfig(configData) {
    const config = configData.config || {};
    const chat = config.chat_model || {};
    const provider = toDyadProvider(chat.provider || "openrouter");
    const modelName = toDyadModelName(provider, chat.name);
    const providerSettings = {};

    for (const [providerId, hasKey] of Object.entries(configData.api_key_status || {})) {
      const dyadProviderId = normalizeProviderId(providerId);
      if (hasKey && dyadProviderId) {
        providerSettings[dyadProviderId] = {
          apiKey: {
            value: "configured-in-vini",
            encryptionType: "plaintext",
          },
        };
      }
    }

    return {
      selectedModel: {
        name: modelName,
        provider,
      },
      providerSettings,
      telemetryConsent: "opted_out",
      hasRunBefore: true,
      experiments: {},
      selectedChatMode: "build",
      defaultChatMode: "build",
      selectedTemplateId: "react",
      selectedThemeId: "default",
      enableAutoUpdate: false,
      releaseChannel: "stable",
      enableAutoFixProblems: false,
      enableAppBlueprint: true,
      enableNativeGit: true,
      enableSandboxScriptExecution: true,
      autoExpandPreviewPanel: true,
      enableContextCompaction: true,
      enablePnpmMinimumReleaseAgeWarning: false,
      previewIdleTimeoutPolicy: "default",
      runtimeMode2: "docker",
      ...savedSettings,
    };
  }

  async function loadViniState() {
    if (statePromise) return statePromise;
    statePromise = (async () => {
      const configData = await postJson(`${MODEL_API_BASE}/model_config_get`, {});
      const providers = [];
      const seen = new Set();
      for (const provider of [
        ...(configData.chat_providers || []),
        ...(configData.embedding_providers || []),
      ]) {
        const record = providerToRecord(provider, configData.api_key_status || {});
        if (!record || seen.has(record.id)) continue;
        seen.add(record.id);
        providers.push(record);
      }
      return {
        configData,
        providers,
        settings: settingsFromConfig(configData),
      };
    })();
    try {
      return await statePromise;
    } catch (error) {
      statePromise = null;
      throw error;
    }
  }

  async function getNodeStatus() {
    const status = await postJson(`${CANVAS_API_BASE}/status`, {});
    return {
      nodeVersion: status?.node?.version || null,
      pnpmVersion: status?.pnpm?.version || null,
      nodeDownloadUrl: "https://nodejs.org/en/download",
    };
  }

  async function getModelsForProvider(providerId) {
    const state = await loadViniState();
    const provider = normalizeProviderId(providerId);
    const config = state.configData.config || {};
    const chat = config.chat_model || {};
    const currentProvider = toDyadProvider(chat.provider);
    const currentName = toDyadModelName(currentProvider, chat.name);

    const models = [];
    if (provider === currentProvider && currentName) {
      models.push({
        apiName: currentName,
        displayName: currentName,
        description: "Active Vini AI model",
        type: PROVIDER_TYPE[provider] || "cloud",
      });
    }

    if (provider === "auto") {
      models.push({
        apiName: "auto",
        displayName: "Auto",
        description: "Use Vini AI provider routing",
        type: "cloud",
      });
    }

    if (provider === "openrouter" && !models.some((model) => model.apiName === "openrouter/free")) {
      models.push({
        apiName: "openrouter/free",
        displayName: "Free (OpenRouter)",
        description: "OpenRouter free model route",
        type: "cloud",
      });
    }

    return models;
  }

  async function getEnvVars() {
    const state = await loadViniState();
    const envVars = {};
    for (const provider of state.providers) {
      const envName = PROVIDER_ENV[provider.id] || provider.envVarName;
      if (envName && provider._viniHasKey) {
        envVars[envName] = "configured-in-vini";
      }
    }
    return envVars;
  }

  function fallbackForUnhandledChannel(channel) {
    console.warn(`Vini Canvas optional Dyad IPC channel is not active in-shell: ${channel}`);
    if (
      channel.startsWith("list-") ||
      channel.includes(":list-") ||
      channel.endsWith(":list") ||
      channel === "search-chats" ||
      channel === "search-app-files" ||
      channel === "check-problems" ||
      channel === "get-context-paths" ||
      channel === "mcp:list-tools"
    ) {
      return [];
    }
    if (
      channel.startsWith("get-") ||
      channel.includes(":get-") ||
      channel === "check-ai-rules" ||
      channel === "get-latest-security-review"
    ) {
      return null;
    }
    if (
      channel.startsWith("check-") ||
      channel.startsWith("is-") ||
      channel.startsWith("does-")
    ) {
      return false;
    }
    return undefined;
  }

  function isMutationChannel(channel) {
    return /^(add|apply|approve|cancel|change|checkout|cleanup|clear|copy|create|delete|discard|edit|execute|generate|git:|github:|import|install|migration:|move|neon:|open-|portal:|pro:|reject|rename|reset|respond|revert|save|select-|set-|supabase:|sync|update|upload|vercel:)/.test(channel);
  }

  async function invoke(channel, input) {
    switch (channel) {
      case "get-user-settings": {
        const state = await loadViniState();
        return state.settings;
      }
      case "set-user-settings": {
        const state = await loadViniState();
        savedSettings = { ...(savedSettings || {}), ...(input || {}) };
        state.settings = { ...state.settings, ...savedSettings };
        return state.settings;
      }
      case "get-env-vars":
        return await getEnvVars();
      case "get-language-model-providers": {
        const state = await loadViniState();
        return state.providers.map(({ _viniHasKey, ...provider }) => provider);
      }
      case "get-language-models":
        return await getModelsForProvider(input?.providerId || input);
      case "get-language-models-by-providers": {
        const state = await loadViniState();
        const result = {};
        for (const provider of state.providers) {
          result[provider.id] = await getModelsForProvider(provider.id);
        }
        return result;
      }
      case "nodejs-status":
        return await getNodeStatus();
      case "get-node-path":
        return (await postJson(`${CANVAS_API_BASE}/status`, {}))?.node?.path || null;
      case "get-system-platform":
        return "linux";
      case "get-app-version":
        return { version: "vini-canvas" };
      case "get-user-budget":
        return null;
      case "list-apps": {
        const result = await canvasBackend("list_apps");
        return { apps: result.apps || [] };
      }
      case "check-app-name": {
        const result = await canvasBackend("check_app_name", input || {});
        return { exists: Boolean(result.exists), message: result.message || "" };
      }
      case "create-app": {
        const result = await canvasBackend("create_app", input || {});
        return { app: result.app, chatId: result.chatId };
      }
      case "get-app": {
        const result = await canvasBackend("get_app", { appId: input });
        return result.app;
      }
      case "get-templates":
        return [
          {
            id: "react",
            title: "React",
            description: "Vini Canvas default Vite React app template",
            imageUrl: "",
            isOfficial: true,
            isExperimental: false,
            requiresNeon: false,
          },
        ];
      case "apply-app-template": {
        const result = await canvasBackend("apply_app_template", input || {});
        return {
          applied: Boolean(result.applied),
          needsRestart: Boolean(result.needsRestart),
        };
      }
      case "set-app-theme":
        await canvasBackend("set_app_theme", input || {});
        return undefined;
      case "get-app-theme": {
        const result = await canvasBackend("get_app_theme", input || {});
        return result.themeId || null;
      }
      case "list-versions": {
        const result = await canvasBackend("list_versions", input || {});
        return result.versions || [];
      }
      case "get-current-branch": {
        const result = await canvasBackend("get_current_branch", input || {});
        return { branch: result.branch || "no-git" };
      }
      case "get-proposal": {
        const result = await canvasBackend("get_proposal", input || {});
        return result.proposal || null;
      }
      case "approve-proposal":
        return {
          success: false,
          error: "Vini Canvas does not use Dyad proposal approval in the Vini AI shell yet.",
          extraFiles: [],
          warningMessages: [],
        };
      case "reject-proposal":
        return undefined;
      case "delete-app":
        await canvasBackend("delete_app", input || {});
        return undefined;
      case "get-chats": {
        const result = await canvasBackend("get_chats", { appId: input });
        return result.chats || [];
      }
      case "get-chat": {
        const result = await canvasBackend("get_chat", { chatId: input });
        return result.chat;
      }
      case "get-chat-metadata": {
        const result = await canvasBackend("get_chat_metadata", { chatId: input });
        return result.chat;
      }
      case "create-chat": {
        const payload = typeof input === "number" ? { appId: input } : input || {};
        const result = await canvasBackend("create_chat", payload);
        return result.chatId;
      }
      case "update-chat":
        await canvasBackend("update_chat", input || {});
        return undefined;
      case "delete-chat":
        await canvasBackend("delete_chat", { chatId: input });
        return undefined;
      case "delete-messages":
        await canvasBackend("delete_messages", { chatId: input });
        return undefined;
      case "read-app-file": {
        const result = await canvasBackend("read_app_file", input || {});
        return result.content || "";
      }
      case "edit-app-file": {
        const result = await canvasBackend("edit_app_file", input || {});
        return result.warning ? { warning: result.warning } : {};
      }
      case "search-app": {
        const result = await canvasBackend("search_apps", { query: input || "" });
        return result.results || [];
      }
      case "chat:count-tokens": {
        const result = await canvasBackend("count_tokens", input || {});
        return result.tokens;
      }
      case "chat:response:ack":
        return undefined;
      case "chat:cancel":
        return false;
      case "chat:stream": {
        const params = input || {};
        const chatId = Number(params.chatId);
        emit("chat:stream:start", { chatId });
        const result = await canvasBackend("generate_app", params);
        emit("chat:response:chunk", {
          chatId,
          messages: result.chat?.messages || [],
          effectiveChatMode: params.requestedChatMode || "build",
        });
        const previewUrl = result.preview?.preview_url;
        const originalUrl = result.preview?.internal_preview_url || previewUrl;
        const appId = result.chat?.appId;
        if (previewUrl && appId) {
          emit("app:output", {
            type: "stdout",
            message: `[dyad-proxy-server]started=[${previewUrl}] original=[${originalUrl}] mode=[host]`,
            appId,
            timestamp: Date.now(),
          });
        }
        emit("chat:response:end", {
          chatId,
          updatedFiles: Boolean(result.updatedFiles),
          extraFiles: result.files || [],
          warningMessages: result.warningMessages || [],
          totalTokens: result.chat?.messages?.at?.(-1)?.totalTokens || undefined,
          chatSummary: result.chat?.title || undefined,
        });
        emit("chat:stream:end", { chatId });
        return undefined;
      }
      case "run-app": {
        const appId = Number(input?.appId);
        emit("app:output", {
          type: "info",
          message: "Starting Vini Canvas preview...",
          appId,
          timestamp: Date.now(),
        });
        const result = await canvasBackend("run_app", input || {});
        const previewUrl = result.preview?.preview_url;
        const originalUrl = result.preview?.internal_preview_url || previewUrl;
        if (previewUrl) {
          emit("app:output", {
            type: "stdout",
            message: `[dyad-proxy-server]started=[${previewUrl}] original=[${originalUrl}] mode=[host]`,
            appId,
            timestamp: Date.now(),
          });
        }
        return undefined;
      }
      case "stop-app":
        await canvasBackend("stop_app", input || {});
        return undefined;
      case "restart-app": {
        const appId = Number(input?.appId);
        emit("app:output", {
          type: "info",
          message: "Restarting Vini Canvas preview...",
          appId,
          timestamp: Date.now(),
        });
        const result = await canvasBackend("restart_app", input || {});
        const previewUrl = result.preview?.preview_url;
        const originalUrl = result.preview?.internal_preview_url || previewUrl;
        if (previewUrl) {
          emit("app:output", {
            type: "stdout",
            message: `[dyad-proxy-server]started=[${previewUrl}] original=[${originalUrl}] mode=[host]`,
            appId,
            timestamp: Date.now(),
          });
        }
        return undefined;
      }
      case "select-app-for-preview":
        return undefined;
      case "update-app-commands":
        throw new Error("Vini Canvas has not connected custom app command editing yet.");
      case "get-cloud-sandbox-status":
        return null;
      case "app:get-current-commit-hash":
        return { commitHash: null };
      case "app:list-screenshots":
        return { screenshots: [] };
      case "app:list-thumbnails":
        return { thumbnails: [] };
      case "get-themes":
      case "get-custom-themes":
      case "mcp:list-servers":
      case "mcp:get-tool-consents":
      case "prompts:list":
        return [];
      case "reload-env-path":
      case "renderer:error-toast-ready":
      case "take-screenshot":
      case "window:focus":
      case "window:minimize":
      case "window:maximize":
      case "window:close":
        return undefined;
      case "open-external-url":
      case "open-file-path":
      case "show-item-in-folder":
        if (typeof input === "string" && input) window.open(input, "_blank", "noopener,noreferrer");
        return undefined;
      default:
        if (isMutationChannel(channel)) {
          throw new Error(`Vini Canvas does not support Dyad IPC action "${channel}" in the Vini AI shell yet.`);
        }
        return fallbackForUnhandledChannel(channel);
    }
  }

  window.electron = {
    ipcRenderer: {
      invoke,
      on(channel, listener) {
        if (!listeners.has(channel)) listeners.set(channel, new Set());
        listeners.get(channel).add(listener);
        return () => listeners.get(channel)?.delete(listener);
      },
      removeListener(channel, listener) {
        listeners.get(channel)?.delete(listener);
      },
      removeAllListeners(channel) {
        if (channel) listeners.delete(channel);
        else listeners.clear();
      },
      send() {},
    },
    webFrame: {
      setZoomFactor() {},
    },
  };
})();
