import { createStore } from "/js/AlpineStore.js";
import { getNamespacedClient } from "/js/websocket.js";
import { ttsService } from "/js/tts-service.js";
import { sendMessage, updateChatInput } from "/index.js";

const Status = {
  IDLE: "idle",
  STARTING: "starting",
  LISTENING: "listening",
  RECORDING: "recording",
  THINKING: "thinking",
  SPEAKING: "speaking",
  ERROR: "error",
};

const TARGET_SAMPLE_RATE = 16000;
const FRAME_SAMPLES = 320;
const FAST_TTS_CHUNK_LENGTH = 64;
const RESPONSE_TARGET_MS = 2000;
const RESPONSE_TIMEOUT_MS = 45000;
const DUPLICATE_TRANSCRIPT_WINDOW_MS = 8000;
const VOICE_HANDLER = "plugins/_vini_voice/ws_voice";
const BACKCHANNEL_TRANSCRIPTS = new Set([
  "yeah",
  "yes",
  "yep",
  "ok",
  "okay",
  "right",
  "hmm",
  "hm",
  "uh huh",
  "mm hmm",
]);

const voiceSocket = getNamespacedClient("/ws");
voiceSocket.addHandlers([VOICE_HANDLER]);

function firstResult(response) {
  const result = response?.results?.find((item) => item?.ok !== false);
  return result?.data || null;
}

function firstError(response) {
  const result = response?.results?.find((item) => item?.ok === false);
  return result?.error?.error || result?.error?.message || "";
}

function appendFloat32(left, right) {
  if (!left?.length) return new Float32Array(right);
  const merged = new Float32Array(left.length + right.length);
  merged.set(left, 0);
  merged.set(right, left.length);
  return merged;
}

function appendInt16(left, right) {
  if (!left?.length) return new Int16Array(right);
  const merged = new Int16Array(left.length + right.length);
  merged.set(left, 0);
  merged.set(right, left.length);
  return merged;
}

function int16ToBase64(samples) {
  const bytes = new Uint8Array(samples.buffer, samples.byteOffset, samples.byteLength);
  let binary = "";
  const chunk = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunk) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunk));
  }
  return btoa(binary);
}

const model = {
  isOpen: false,
  status: Status.IDLE,
  error: "",
  audioLevel: 0,
  userText: "",
  assistantText: "",
  vadLabel: "Standby",
  runtimeStatus: null,
  stream: null,
  audioContext: null,
  mediaStreamSource: null,
  processorNode: null,
  resampleRemainder: new Float32Array(0),
  pcmRemainder: new Int16Array(0),
  logsListener: null,
  ttsListener: null,
  voiceEventListener: null,
  canvasFrame: null,
  particles: [],
  lastSpokenKey: "",
  activeVoiceResponseId: "",
  interruptedVoiceResponseId: "",
  lastSpeakableText: "",
  awaitingAgentResponse: false,
  responseWaitTimer: null,
  responseTargetTimer: null,
  isStreamingAudio: false,
  lastSubmittedTranscript: "",
  lastSubmittedAt: 0,
  suppressedTranscriptCount: 0,
  ttsProviderReadyPromise: null,

  async init() {
    if (!this.logsListener) {
      this.logsListener = (event) => {
        if (!this.isOpen) return;
        if (globalThis.Alpine?.store?.("preferences")?.speech) return;
        this.speakLatestLog(event?.detail?.logs || []);
      };
      window.addEventListener("vini:agent-logs", this.logsListener);
    }

    if (!this.ttsListener) {
      this.ttsListener = (event) => {
        if (!this.isOpen) return;
        if (event?.detail?.isSpeaking) {
          this.status = Status.SPEAKING;
          this.vadLabel = "Vini AI is speaking";
        } else if (this.status === Status.SPEAKING) {
          this.resumeListeningIfReady();
        }
      };
      ttsService.addEventListener("statechange", this.ttsListener);
    }

    if (!this.voiceEventListener) {
      this.voiceEventListener = (envelope) => {
        this.handleVoiceEvent(envelope?.data || {});
      };
      await voiceSocket.on("vini_voice_event", this.voiceEventListener);
    }

    void this.ensureTtsProvider();
  },

  async open() {
    await this.init();
    this.isOpen = true;
    this.error = "";
    this.userText = "";
    this.assistantText = "";
    document.body.classList.add("voice-conversation-open");
    requestAnimationFrame(() => this.startOrb());
    await this.start();
  },

  close() {
    this.isOpen = false;
    document.body.classList.remove("voice-conversation-open");
    this.stop();
  },

  async start() {
    if (this.stream || this.status === Status.STARTING) return;
    this.status = Status.STARTING;
    this.vadLabel = "Starting voice runtime";
    this.error = "";

    try {
      globalThis.Alpine?.store?.("whisperStt")?.stop?.();
      await voiceSocket.connect();
      await this.ensureTtsProvider();
      const startResponse = await voiceSocket.request("vini_voice_start", {}, { timeoutMs: 60000 });
      const startError = firstError(startResponse);
      if (startError) throw new Error(startError);
      this.runtimeStatus = firstResult(startResponse)?.runtime || null;

      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });

      await this.setupAudioPipeline(this.stream);
      this.isStreamingAudio = true;
      this.status = Status.LISTENING;
      this.vadLabel = "Listening";
    } catch (error) {
      this.status = Status.ERROR;
      this.error = error instanceof Error ? error.message : String(error);
      this.vadLabel = "Voice unavailable";
      this.stopMedia();
    }
  },

  stop() {
    this.awaitingAgentResponse = false;
    clearTimeout(this.responseWaitTimer);
    clearTimeout(this.responseTargetTimer);
    this.responseWaitTimer = null;
    this.responseTargetTimer = null;
    this.isStreamingAudio = false;
    this.stopAudio();
    this.stopMedia();
    void voiceSocket.emit("vini_voice_stop", {}).catch(() => {});
    this.status = Status.IDLE;
    this.vadLabel = "Standby";
    this.audioLevel = 0;
  },

  stopAudio() {
    ttsService.stop();
  },

  async setupAudioPipeline(stream) {
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    await this.audioContext.resume();
    this.mediaStreamSource = this.audioContext.createMediaStreamSource(stream);

    this.processorNode = this.audioContext.createScriptProcessor(2048, 1, 1);
    this.processorNode.onaudioprocess = (event) => this.processAudio(event);

    this.mediaStreamSource.connect(this.processorNode);
    this.processorNode.connect(this.audioContext.destination);
  },

  processAudio(event) {
    if (!this.isOpen || !this.isStreamingAudio || !voiceSocket.isConnected()) return;
    const input = event.inputBuffer.getChannelData(0);
    event.outputBuffer.getChannelData(0).fill(0);
    const rms = this.calculateRms(input);
    this.audioLevel = Math.max(0, Math.min(1, rms * 8));

    if (this.shouldPauseSttStream()) {
      this.resampleRemainder = new Float32Array(0);
      this.pcmRemainder = new Int16Array(0);
      return;
    }

    const downsampled = this.downsampleToTarget(input, this.audioContext.sampleRate);
    if (!downsampled.length) return;

    const pcm = this.floatToInt16(downsampled);
    this.pcmRemainder = appendInt16(this.pcmRemainder, pcm);

    while (this.pcmRemainder.length >= FRAME_SAMPLES) {
      const frame = this.pcmRemainder.slice(0, FRAME_SAMPLES);
      this.pcmRemainder = this.pcmRemainder.slice(FRAME_SAMPLES);
      void voiceSocket.emit("vini_voice_audio", { pcm: int16ToBase64(frame) }).catch((error) => {
        this.status = Status.ERROR;
        this.error = error instanceof Error ? error.message : String(error);
      });
    }
  },

  downsampleToTarget(input, sampleRate) {
    const source = appendFloat32(this.resampleRemainder, input);
    if (sampleRate === TARGET_SAMPLE_RATE) {
      this.resampleRemainder = new Float32Array(0);
      return source;
    }

    const ratio = sampleRate / TARGET_SAMPLE_RATE;
    const outputLength = Math.max(0, Math.floor((source.length - 1) / ratio));
    if (outputLength <= 0) {
      this.resampleRemainder = source;
      return new Float32Array(0);
    }

    const output = new Float32Array(outputLength);
    for (let index = 0; index < outputLength; index += 1) {
      const position = index * ratio;
      const left = Math.floor(position);
      const right = Math.min(source.length - 1, left + 1);
      const amount = position - left;
      output[index] = source[left] * (1 - amount) + source[right] * amount;
    }

    const consumed = Math.floor(outputLength * ratio);
    this.resampleRemainder = source.slice(consumed);
    return output;
  },

  floatToInt16(input) {
    const output = new Int16Array(input.length);
    for (let index = 0; index < input.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, input[index]));
      output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
    return output;
  },

  calculateRms(samples) {
    let sum = 0;
    for (let index = 0; index < samples.length; index += 1) {
      sum += samples[index] * samples[index];
    }
    return Math.sqrt(sum / Math.max(1, samples.length));
  },

  async handleVoiceEvent(event) {
    if (!event?.type || !this.isOpen) return;

    if (event.type === "ready") {
      this.runtimeStatus = event.status || this.runtimeStatus;
      this.vadLabel = "Listening";
      return;
    }

    if (event.type === "speech_start") {
      if (ttsService.isSpeaking()) ttsService.stop();
      if (this.activeVoiceResponseId) {
        this.interruptedVoiceResponseId = this.activeVoiceResponseId;
      }
      this.awaitingAgentResponse = false;
      clearTimeout(this.responseWaitTimer);
      clearTimeout(this.responseTargetTimer);
      this.responseWaitTimer = null;
      this.responseTargetTimer = null;
      this.status = Status.RECORDING;
      this.vadLabel = "Listening to you";
      return;
    }

    if (event.type === "speech_end") {
      this.status = Status.THINKING;
      this.vadLabel = "Preparing reply";
      return;
    }

    if (event.type === "transcribing") {
      this.status = Status.THINKING;
      this.vadLabel = "Transcribing";
      return;
    }

    if (event.type === "no_speech") {
      this.resumeListeningIfReady();
      return;
    }

    if (event.type === "transcript") {
      const text = String(event.text || "").trim();
      if (!text) {
        this.resumeListeningIfReady();
        return;
      }
      await this.sendTranscript(text);
      return;
    }

    if (event.type === "error") {
      this.status = Status.ERROR;
      this.error = String(event.error || "Voice runtime error");
      this.vadLabel = "Voice error";
    }
  },

  async sendTranscript(text) {
    const normalized = this.normalizeTranscript(text);
    const now = Date.now();
    const isDuplicate =
      normalized &&
      normalized === this.lastSubmittedTranscript &&
      now - this.lastSubmittedAt < DUPLICATE_TRANSCRIPT_WINDOW_MS;
    const isBackchannel = BACKCHANNEL_TRANSCRIPTS.has(normalized);

    if (!normalized || isDuplicate) {
      this.suppressedTranscriptCount += 1;
      this.resumeListeningIfReady();
      return;
    }

    if (this.awaitingAgentResponse || this.isAgentBusy()) {
      this.suppressedTranscriptCount += 1;
      console.info("[vini_voice] suppressed transcript while agent is busy", {
        text,
        normalized,
        isBackchannel,
        count: this.suppressedTranscriptCount,
      });
      this.vadLabel = isBackchannel ? "Waiting for Vini AI" : "Hold on";
      this.resumeListeningIfReady();
      return;
    }

    this.lastSubmittedTranscript = normalized;
    this.lastSubmittedAt = now;
    this.userText = text;
    this.status = Status.THINKING;
    this.vadLabel = "Sending to Vini AI";
    this.awaitingAgentResponse = true;
    this.activeVoiceResponseId = "";
    this.lastSpeakableText = "";
    this.lastSpokenKey = "";
    this.startResponseWaitTimer();
    this.startResponseTargetTimer();
    updateChatInput(text);
    await sendMessage({ voiceMode: true });
    if (this.stream && this.status !== Status.ERROR) {
      this.status = Status.THINKING;
      this.vadLabel = "Listening for reply";
    }
  },

  speakLatestLog(logs) {
    if (!Array.isArray(logs) || !logs.length) return;
    if (this.status === Status.RECORDING) return;

    for (let index = logs.length - 1; index >= 0; index -= 1) {
      const log = logs[index];
      if (log?.type !== "response" || !String(log.content || "").trim()) continue;

      const cleanText = this.stripText(this.extractVoiceResponseText(log.content));
      if (!this.isSpeakableResponse(cleanText)) return;
      const responseId = `voice-${log.no}`;
      if (this.interruptedVoiceResponseId === responseId) return;
      const finished = !!log.kvps?.finished;
      const speakableText = this.extractSpeakableText(cleanText, finished);
      if (!speakableText) return;

      const key = `response:${log.no}:${finished ? "done" : "partial"}:${speakableText}`;
      if (this.lastSpokenKey === key) return;
      this.lastSpokenKey = key;
      this.activeVoiceResponseId = responseId;
      this.lastSpeakableText = speakableText;
      this.assistantText = cleanText;
      this.awaitingAgentResponse = false;
      clearTimeout(this.responseWaitTimer);
      clearTimeout(this.responseTargetTimer);
      this.responseWaitTimer = null;
      this.responseTargetTimer = null;
      console.info("[vini_voice] speaking response", {
        responseId,
        finished,
        length: speakableText.length,
        providerReady: ttsService.hasProvider(),
      });
      void this.ensureTtsProvider()
        .then(() =>
          ttsService.speakStream(responseId, speakableText, finished, {
            allowPartial: true,
            fast: true,
            maxChunkLength: FAST_TTS_CHUNK_LENGTH,
          }),
        )
        .catch((error) => {
          console.error("[vini_voice] TTS playback failed", error);
          this.error = error instanceof Error ? error.message : String(error);
        })
        .finally(() => this.resumeListeningIfReady());
      return;
    }
  },

  startResponseWaitTimer() {
    clearTimeout(this.responseWaitTimer);
    this.responseWaitTimer = setTimeout(() => {
      this.awaitingAgentResponse = false;
      this.responseWaitTimer = null;
      this.resumeListeningIfReady();
    }, RESPONSE_TIMEOUT_MS);
  },

  startResponseTargetTimer() {
    clearTimeout(this.responseTargetTimer);
    this.responseTargetTimer = setTimeout(() => {
      this.responseTargetTimer = null;
      if (!this.awaitingAgentResponse || ttsService.isSpeaking()) return;
      this.vadLabel = "Generating first sentence";
    }, RESPONSE_TARGET_MS);
  },

  resumeListeningIfReady() {
    if (!this.stream || this.status === Status.ERROR) {
      this.status = this.status === Status.ERROR ? Status.ERROR : Status.IDLE;
      this.vadLabel = this.status === Status.ERROR ? this.vadLabel : "Standby";
      return;
    }

    if (this.awaitingAgentResponse || this.isAgentBusy() || ttsService.isSpeaking()) {
      this.status = Status.THINKING;
      this.vadLabel = "Waiting for Vini AI";
      return;
    }

    this.status = Status.LISTENING;
    this.vadLabel = "Listening";
  },

  isAgentBusy() {
    const chatsStore = globalThis.Alpine?.store?.("chats");
    const messageQueueStore = globalThis.Alpine?.store?.("messageQueue");
    return !!chatsStore?.selectedContext?.running || !!messageQueueStore?.hasQueue;
  },

  shouldPauseSttStream() {
    if (this.status === Status.RECORDING) return false;
    if (ttsService.isSpeaking() || this.status === Status.SPEAKING) return false;
    return this.awaitingAgentResponse || this.isAgentBusy();
  },

  ensureTtsProvider() {
    if (ttsService.hasProvider()) return Promise.resolve();
    if (this.ttsProviderReadyPromise) return this.ttsProviderReadyPromise;

    this.ttsProviderReadyPromise = import("/plugins/_kokoro_tts/webui/kokoro-tts-store.js")
      .then((module) => module?.store?.initRuntime?.())
      .catch((error) => {
        console.warn("[vini_voice] TTS provider init failed", error);
      })
      .finally(() => {
        this.ttsProviderReadyPromise = null;
      });

    return this.ttsProviderReadyPromise;
  },

  normalizeTranscript(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]/gu, " ")
      .replace(/\s+/g, " ")
      .trim();
  },

  isSpeakableResponse(value) {
    const text = String(value || "").trim();
    if (!text) return false;
    if (text.startsWith("{") || text.startsWith("[")) return false;
    return true;
  },

  extractVoiceResponseText(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";

    try {
      const parsed = JSON.parse(raw);
      const toolText = parsed?.tool_args?.text;
      if (typeof toolText === "string" && toolText.trim()) return toolText;
    } catch (_error) {
      // Streaming Agent Zero JSON is often incomplete until the final chunk.
    }

    const toolArgsIndex = raw.indexOf('"tool_args"');
    const searchFrom = toolArgsIndex >= 0 ? raw.slice(toolArgsIndex) : raw;
    const textMatch = searchFrom.match(/"text"\s*:\s*"((?:\\.|[^"\\])*)"?/s);
    if (textMatch?.[1]) {
      return this.decodeJsonStringFragment(textMatch[1]);
    }

    return raw;
  },

  decodeJsonStringFragment(value) {
    const text = String(value || "");
    try {
      return JSON.parse(`"${text.replace(/\\?$/, "")}"`);
    } catch (_error) {
      return text
        .replace(/\\"/g, '"')
        .replace(/\\n/g, " ")
        .replace(/\\r/g, " ")
        .replace(/\\t/g, " ")
        .replace(/\\\\/g, "\\");
    }
  },

  extractSpeakableText(value, finished = false) {
    const text = String(value || "").trim();
    if (!text) return "";
    if (finished) return text;

    let lastBoundary = -1;
    for (let index = 0; index < text.length; index += 1) {
      const character = text[index];
      if (character !== "." && character !== "!" && character !== "?") continue;
      const next = text[index + 1] || "";
      if (!next || /\s|["')\]]/.test(next)) {
        lastBoundary = index;
      }
    }

    if (lastBoundary < 0) return "";
    const candidate = text.slice(0, lastBoundary + 1).trim();
    return candidate.length >= 8 ? candidate : "";
  },

  stripText(value) {
    return String(value || "")
      .replace(/<[^>]*>/g, " ")
      .replace(/\s+/g, " ")
      .trim();
  },

  stopMedia() {
    this.processorNode?.disconnect?.();
    this.processorNode = null;
    this.mediaStreamSource?.disconnect?.();
    this.mediaStreamSource = null;
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    this.audioContext?.close?.().catch?.(() => {});
    this.audioContext = null;
    this.resampleRemainder = new Float32Array(0);
    this.pcmRemainder = new Int16Array(0);
  },

  startOrb() {
    const canvas = document.getElementById("voice-orb-canvas");
    if (!canvas || !this.isOpen) return;
    const context = canvas.getContext("2d");
    if (!context) return;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      context.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    if (!this.particles.length) {
      this.particles = Array.from({ length: 900 }, (_, index) => ({
        index,
        offset: Math.random() * Math.PI * 2,
        radius: 18 + Math.random() * 140,
        speed: 0.002 + Math.random() * 0.005,
        size: 0.45 + Math.random() * 1.5,
      }));
    }

    const draw = (time) => {
      if (!this.isOpen) return;
      const rect = canvas.getBoundingClientRect();
      if (canvas.width !== Math.floor(rect.width * (window.devicePixelRatio || 1))) {
        resize();
      }

      const width = rect.width;
      const height = rect.height;
      const cx = width / 2;
      const cy = height / 2;
      const activity = Math.max(this.audioLevel, ttsService.isSpeaking() ? 0.56 : 0);

      context.clearRect(0, 0, width, height);

      const halo = context.createRadialGradient(cx, cy, 12, cx, cy, 190 + activity * 80);
      halo.addColorStop(0, `rgba(132, 145, 255, ${0.26 + activity * 0.18})`);
      halo.addColorStop(0.42, `rgba(30, 184, 255, ${0.12 + activity * 0.2})`);
      halo.addColorStop(1, "rgba(0, 0, 0, 0)");
      context.fillStyle = halo;
      context.fillRect(0, 0, width, height);

      for (const particle of this.particles) {
        const theta = particle.offset + time * particle.speed + particle.index * 0.018;
        const spiral = particle.radius + Math.sin(theta * 2.0 + time * 0.001) * (10 + activity * 42);
        const x = cx + Math.cos(theta) * spiral * (0.9 + activity * 0.2);
        const y = cy + Math.sin(theta * 1.14) * spiral * 0.62;
        const alpha = 0.16 + activity * 0.54 + Math.sin(theta) * 0.08;
        context.fillStyle = `rgba(${150 + activity * 80}, ${170 + activity * 60}, 255, ${Math.max(0.06, alpha)})`;
        context.beginPath();
        context.arc(x, y, particle.size + activity * 1.6, 0, Math.PI * 2);
        context.fill();
      }

      context.strokeStyle = `rgba(255,255,255,${0.18 + activity * 0.24})`;
      context.lineWidth = 1.5 + activity * 1.8;
      context.beginPath();
      for (let index = 0; index < 220; index += 1) {
        const t = index / 18;
        const r = 5 + index * (0.62 + activity * 0.42);
        const x = cx + Math.cos(t + time * 0.0028) * r;
        const y = cy + Math.sin(t + time * 0.0028) * r * 0.58;
        if (index === 0) context.moveTo(x, y);
        else context.lineTo(x, y);
      }
      context.stroke();

      this.canvasFrame = requestAnimationFrame(draw);
    };

    if (this.canvasFrame) cancelAnimationFrame(this.canvasFrame);
    this.canvasFrame = requestAnimationFrame(draw);
  },

  get statusText() {
    if (this.error) return this.error;
    if (this.status === Status.STARTING) return "Starting real-time voice";
    if (this.status === Status.RECORDING) return "Listening to your voice";
    if (this.status === Status.THINKING) return "Vini AI is thinking";
    if (this.status === Status.SPEAKING) return "Vini AI is speaking";
    if (this.status === Status.LISTENING) return "Listening. Start talking anytime.";
    return "Voice conversation ready";
  },
};

export const store = createStore("voiceConversation", model);
