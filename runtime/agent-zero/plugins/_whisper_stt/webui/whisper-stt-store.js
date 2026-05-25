import { createStore } from "/js/AlpineStore.js";
import { toastFrontendError } from "/components/notifications/notification-store.js";
import { callJsonApi } from "/js/api.js";
import { sttService } from "/js/stt-service.js";
import { ttsService } from "/js/tts-service.js";
import { sendMessage, updateChatInput } from "/index.js";

const PLUGIN_NAME = "_whisper_stt";

const Status = {
  INACTIVE: "inactive",
  ACTIVATING: "activating",
  LISTENING: "listening",
  RECORDING: "recording",
  WAITING: "waiting",
  PROCESSING: "processing",
};

const MicButtonClasses = [
  "mic-disabled",
  "mic-inactive",
  "mic-activating",
  "mic-listening",
  "mic-recording",
  "mic-waiting",
  "mic-processing",
];

const MicStatusLabels = {
  disabled: "Whisper STT disabled",
  inactive: "Microphone standby",
  activating: "Microphone activating",
  listening: "Listening for speech",
  recording: "Recording voice",
  waiting: "Waiting for final silence",
  processing: "Transcribing voice",
};

const MIN_AUDIO_BYTES = 1400;
const TARGET_SAMPLE_RATE = 16000;
const FAST_SILENCE_DURATION_MS = 420;
const FAST_WAITING_TIMEOUT_MS = 120;
const FAST_RECORDING_SLICE_MS = 100;
const PRE_ROLL_MS = 240;
const SCRIPT_PROCESSOR_BUFFER_SIZE = 2048;

function clearMicrophoneTooltip(element) {
  const tooltip = globalThis.bootstrap?.Tooltip?.getInstance?.(element);
  tooltip?.dispose?.();
  element.removeAttribute("title");
  element.removeAttribute("data-bs-original-title");
  element.removeAttribute("data-bs-toggle");
  element.removeAttribute("data-bs-trigger");
  element.removeAttribute("data-bs-tooltip-initialized");
}

const model = {
  runtimeInitialized: false,
  statusLoaded: false,
  loading: false,
  error: "",
  enabled: false,
  config: {
    engine: "parakeet",
    model_size: "base",
    language: "en",
    message_mode: "send",
    silence_threshold: 0.3,
    silence_duration: 1000,
    waiting_timeout: 2000,
  },
  modelReady: false,
  modelLoading: false,
  loadedEngine: "",
  loadedModel: "",
  packageVersion: "",
  providerCleanup: null,
  microphoneInput: null,
  isProcessingClick: false,
  devices: [],
  selectedDevice: "",
  requestingPermission: false,
  _ttsListener: null,
  _deviceChangeListenerBound: false,

  async initRuntime() {
    if (this.runtimeInitialized) return;

    this.runtimeInitialized = true;
    await this.loadDevices();
    await this.refreshStatus({ suppressError: true });

    if (!this._deviceChangeListenerBound) {
      navigator.mediaDevices?.addEventListener?.("devicechange", () => {
        void this.loadDevices();
      });
      this._deviceChangeListenerBound = true;
    }

    if (!this._ttsListener) {
      this._ttsListener = () => this.updateMicrophoneButtonUI();
      ttsService.addEventListener("statechange", this._ttsListener);
    }
  },

  async ensureStatusLoaded({ force = false, suppressError = true } = {}) {
    if ((!this.statusLoaded || force) && !this.loading) {
      await this.refreshStatus({ suppressError });
    }
  },

  async refreshStatus({ suppressError = false } = {}) {
    this.loading = true;
    this.error = "";

    try {
      const status = await callJsonApi(`/plugins/${PLUGIN_NAME}/status`, {});
      this.statusLoaded = true;
      this.enabled = !!status?.enabled;
      this.config = {
        engine:
          status?.config?.engine === "whisper" ? "whisper" : "parakeet",
        model_size: status?.config?.model_size || "base",
        language: status?.config?.language || "en",
        message_mode:
          status?.config?.message_mode === "draft" ? "draft" : "send",
        silence_threshold: Number(status?.config?.silence_threshold ?? 0.3),
        silence_duration: Math.min(
          Number(status?.config?.silence_duration ?? FAST_SILENCE_DURATION_MS),
          FAST_SILENCE_DURATION_MS,
        ),
        waiting_timeout: Math.min(
          Number(status?.config?.waiting_timeout ?? FAST_WAITING_TIMEOUT_MS),
          FAST_WAITING_TIMEOUT_MS,
        ),
      };
      this.modelReady = !!status?.model?.ready;
      this.modelLoading = !!status?.model?.loading;
      this.loadedEngine = status?.model?.loaded_engine || "";
      this.loadedModel = status?.model?.loaded_model || "";
      this.packageVersion =
        this.config.engine === "parakeet"
          ? status?.package?.onnx_asr_version || ""
          : status?.package?.whisper_version || status?.package?.version || "";

      if (this.enabled) {
        this.registerProvider();
      } else {
        this.unregisterProvider();
      }
    } catch (error) {
      this.error = error instanceof Error ? error.message : String(error);
      this.unregisterProvider();
      if (!suppressError) {
        void toastFrontendError(this.error, "Whisper STT");
      }
    } finally {
      this.loading = false;
      this.updateMicrophoneButtonUI();
    }
  },

  registerProvider() {
    if (this.providerCleanup || !this.enabled) return;

    this.providerCleanup = sttService.registerProvider(PLUGIN_NAME, {
      handleMicrophoneClick: async () => await this.handleMicrophoneClick(),
      requestMicrophonePermission: async () =>
        await this.requestMicrophonePermission(),
      updateMicrophoneButtonUI: () => this.updateMicrophoneButtonUI(),
      stop: () => this.stop(),
      getStatus: () => this.micStatus,
    });

    sttService.emitStatusChange(this.micStatus);
    this.updateMicrophoneButtonUI();
  },

  unregisterProvider() {
    if (!this.providerCleanup) return;

    this.stop();
    this.providerCleanup();
    this.providerCleanup = null;
  },

  async openConfig() {
    const { store } = await import("/components/plugins/plugin-settings-store.js");
    await store.openConfig(PLUGIN_NAME);
  },

  openPanel() {
    window.openModal?.(`/plugins/${PLUGIN_NAME}/webui/main.html`);
  },

  updateMicrophoneButtonUI() {
    const microphoneButton = document.getElementById("microphone-button");
    if (!microphoneButton) return;

    const status = this.enabled ? this.micStatus : "disabled";
    const label = MicStatusLabels[status] || "Microphone";
    clearMicrophoneTooltip(microphoneButton);
    microphoneButton.classList.remove(...MicButtonClasses);
    microphoneButton.classList.add(`mic-${status}`);
    microphoneButton.setAttribute("data-status", status);
    microphoneButton.setAttribute("aria-label", label);
    microphoneButton.setAttribute(
      "aria-pressed",
      String(
        status !== "disabled" &&
          status !== Status.INACTIVE &&
          status !== Status.ACTIVATING,
      ),
    );
  },

  async loadDevices() {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      this.devices = devices.filter(
        (device) => device.kind === "audioinput" && device.deviceId,
      );

      const saved = localStorage.getItem("whisperSttSelectedDevice") || "";
      const savedStillExists = this.devices.some(
        (device) => device.deviceId === saved,
      );

      if (savedStillExists) {
        this.selectedDevice = saved;
        return;
      }

      const defaultDevice =
        this.devices.find((device) => device.deviceId === "default") ||
        this.devices[0];
      this.selectedDevice = defaultDevice?.deviceId || "";
    } catch (error) {
      console.error("[Whisper STT] Failed to enumerate audio devices", error);
      this.devices = [];
      this.selectedDevice = "";
    }
  },

  async selectDevice(deviceId) {
    this.selectedDevice = deviceId || "";
    localStorage.setItem("whisperSttSelectedDevice", this.selectedDevice);

    if (this.microphoneInput?.selectedDeviceId !== this.selectedDevice) {
      this.stop();
      this.microphoneInput = null;
    }
  },

  getSelectedDevice() {
    let device = this.devices.find(
      (candidate) => candidate.deviceId === this.selectedDevice,
    );

    if (!device && this.devices.length > 0) {
      device =
        this.devices.find((candidate) => candidate.deviceId === "default") ||
        this.devices[0];
    }

    return device || null;
  },

  async requestMicrophonePermission() {
    this.requestingPermission = true;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      await this.loadDevices();
      return true;
    } catch (error) {
      console.error("[Whisper STT] Microphone permission denied", error);
      globalThis.toast?.(
        "Microphone access denied. Please enable microphone access in your browser settings.",
        "error",
      );
      return false;
    } finally {
      this.requestingPermission = false;
    }
  },

  async handleMicrophoneClick() {
    if (this.isProcessingClick) return;

    this.isProcessingClick = true;
    try {
      await this.ensureStatusLoaded({ force: true, suppressError: false });
      if (!this.enabled) {
        globalThis.justToast?.("Whisper STT is disabled.", "info");
        return;
      }

      ttsService.stop();

      const selectedDevice = this.getSelectedDevice();
      if (
        this.microphoneInput &&
        this.microphoneInput.selectedDeviceId !== (selectedDevice?.deviceId || "")
      ) {
        this.stop();
        this.microphoneInput = null;
      }

      if (!this.microphoneInput) {
        await this.initMicrophone();
      }

      if (this.microphoneInput) {
        await this.microphoneInput.toggle();
      }
    } finally {
      setTimeout(() => {
        this.isProcessingClick = false;
      }, 300);
    }
  },

  async initMicrophone() {
    if (this.microphoneInput) return this.microphoneInput;

    const input = new MicrophoneInput(this, async (text, isFinal) => {
      if (isFinal) {
        await this.sendVoiceMessage(text);
      }
    });

    const initialized = await input.initialize();
    this.microphoneInput = initialized ? input : null;
    return this.microphoneInput;
  },

  async sendVoiceMessage(text) {
    const message = String(text || "").trim();
    if (!message) return;

    updateChatInput(message);

    if (!this.sendsImmediately) {
      this.stop();
      return;
    }

    if (!this.microphoneInput?.messageSent) {
      this.microphoneInput.messageSent = true;
      await sendMessage();
    }
  },

  notifyStatusChange() {
    this.updateMicrophoneButtonUI();
    sttService.emitStatusChange(this.micStatus);
  },

  stop() {
    if (this.microphoneInput) {
      this.microphoneInput.status = Status.INACTIVE;
      this.microphoneInput.dispose();
      this.microphoneInput = null;
    }

    this.notifyStatusChange();
  },

  get micStatus() {
    return this.microphoneInput?.status || Status.INACTIVE;
  },

  get sendsImmediately() {
    return this.config.message_mode !== "draft";
  },

  get messageModeLabel() {
    return this.sendsImmediately ? "Send immediately" : "Draft in composer";
  },

  get statusText() {
    if (!this.enabled) return "Disabled";
    if (this.modelLoading) return "Loading";
    if (this.modelReady) return "Ready";
    return "Idle";
  },

  get statusClass() {
    if (!this.enabled) return "warn";
    if (this.modelLoading) return "warn";
    if (this.modelReady) return "ok";
    return "warn";
  },

  get selectedDeviceLabel() {
    const device = this.getSelectedDevice();
    if (!device) return "System default";
    return device.label || "System default";
  },
};

class MicrophoneInput {
  constructor(owner, updateCallback) {
    this.owner = owner;
    this.updateCallback = updateCallback;
    this.mediaStream = null;
    this.mediaRecorder = null;
    this.audioContext = null;
    this.mediaStreamSource = null;
    this.analyserNode = null;
    this.processorNode = null;
    this.silentGainNode = null;
    this.audioChunks = [];
    this.pcmAudioChunks = [];
    this.preRollAudioChunks = [];
    this.lastChunk = null;
    this.messageSent = false;
    this.lastAudioTime = null;
    this.waitingTimer = null;
    this.silenceStartTime = null;
    this.hasStartedRecording = false;
    this.analysisFrame = null;
    this.selectedDeviceId = "";
    this.inputSampleRate = TARGET_SAMPLE_RATE;
    this.preRollSampleCount = 0;
    this.speechFrameCount = 0;
    this.noiseFloor = 0.006;
    this.lastRms = 0;
    this._status = Status.INACTIVE;
  }

  get status() {
    return this._status;
  }

  set status(nextStatus) {
    if (this._status === nextStatus) return;

    const previousStatus = this._status;
    this._status = nextStatus;
    this.handleStatusChange(previousStatus, nextStatus);
    this.owner.notifyStatusChange();
  }

  async initialize() {
    this.status = Status.ACTIVATING;

    try {
      const selectedDevice = this.owner.getSelectedDevice();
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId:
            selectedDevice?.deviceId
              ? { exact: selectedDevice.deviceId }
              : undefined,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      });

      this.selectedDeviceId = selectedDevice?.deviceId || "";
      this.mediaStream = stream;
      this.initMediaRecorderFallback(stream);

      this.setupAudioAnalysis(stream);
      return true;
    } catch (error) {
      console.error("[Whisper STT] Microphone initialization failed", error);
      globalThis.toast?.(
        "Failed to access the microphone. Please check browser permissions.",
        "error",
      );
      this.status = Status.INACTIVE;
      this.dispose();
      return false;
    }
  }

  handleStatusChange(previousStatus, nextStatus) {
    if (nextStatus !== Status.RECORDING) {
      this.lastChunk = null;
    }

    switch (nextStatus) {
      case Status.INACTIVE:
        this.handleInactiveState();
        break;
      case Status.LISTENING:
        this.handleListeningState();
        break;
      case Status.RECORDING:
        this.handleRecordingState();
        break;
      case Status.WAITING:
        this.handleWaitingState();
        break;
      case Status.PROCESSING:
        this.handleProcessingState();
        break;
    }
  }

  handleInactiveState() {
    this.stopRecording();
    this.stopAudioAnalysis();
    clearTimeout(this.waitingTimer);
    this.waitingTimer = null;
  }

  handleListeningState() {
    this.stopRecording();
    this.audioChunks = [];
    this.pcmAudioChunks = [];
    this.preRollAudioChunks = [];
    this.preRollSampleCount = 0;
    this.hasStartedRecording = false;
    this.silenceStartTime = null;
    this.lastAudioTime = null;
    this.messageSent = false;
    this.speechFrameCount = 0;
    this.startAudioAnalysis();
  }

  handleRecordingState() {
    if (!this.hasStartedRecording) {
      this.hasStartedRecording = true;
      if (this.preRollAudioChunks.length > 0) {
        this.pcmAudioChunks.push(...this.preRollAudioChunks);
        this.preRollAudioChunks = [];
        this.preRollSampleCount = 0;
      }
      if (this.mediaRecorder?.state === "inactive") {
        this.mediaRecorder.start(FAST_RECORDING_SLICE_MS);
      }
    }

    clearTimeout(this.waitingTimer);
    this.waitingTimer = null;
  }

  handleWaitingState() {
    clearTimeout(this.waitingTimer);
    this.waitingTimer = setTimeout(() => {
      if (this.status === Status.WAITING) {
        this.status = Status.PROCESSING;
      }
    }, this.owner.config.waiting_timeout);
  }

  handleProcessingState() {
    this.stopRecording();
    void this.process();
  }

  setupAudioAnalysis(stream) {
    this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
    this.inputSampleRate = this.audioContext.sampleRate || TARGET_SAMPLE_RATE;
    this.mediaStreamSource = this.audioContext.createMediaStreamSource(stream);
    this.analyserNode = this.audioContext.createAnalyser();
    this.analyserNode.fftSize = 2048;
    this.analyserNode.minDecibels = -90;
    this.analyserNode.maxDecibels = -10;
    this.analyserNode.smoothingTimeConstant = 0.85;
    this.mediaStreamSource.connect(this.analyserNode);

    if (this.audioContext.createScriptProcessor) {
      this.processorNode = this.audioContext.createScriptProcessor(
        SCRIPT_PROCESSOR_BUFFER_SIZE,
        1,
        1,
      );
      this.silentGainNode = this.audioContext.createGain();
      this.silentGainNode.gain.value = 0;
      this.processorNode.onaudioprocess = (event) => {
        this.capturePcmFrame(event.inputBuffer.getChannelData(0));
      };
      this.mediaStreamSource.connect(this.processorNode);
      this.processorNode.connect(this.silentGainNode);
      this.silentGainNode.connect(this.audioContext.destination);
    }
  }

  startAudioAnalysis() {
    const analyzeFrame = () => {
      if (this.status === Status.INACTIVE || !this.analyserNode) return;

      const dataArray = new Uint8Array(this.analyserNode.fftSize);
      this.analyserNode.getByteTimeDomainData(dataArray);

      let sum = 0;
      for (let index = 0; index < dataArray.length; index += 1) {
        const amplitude = (dataArray[index] - 128) / 128;
        sum += amplitude * amplitude;
      }

      const rms = Math.sqrt(sum / dataArray.length);
      const now = Date.now();
      this.lastRms = rms;
      if (this.status === Status.LISTENING && rms < 0.025) {
        this.noiseFloor = this.noiseFloor * 0.92 + rms * 0.08;
      }
      const silenceThreshold = Math.max(
        0.012,
        this.noiseFloor * 2.8,
        this.densify(this.owner.config.silence_threshold) * 0.55,
      );
      const speechDetected = rms > silenceThreshold;

      if (speechDetected) {
        this.lastAudioTime = now;
        this.silenceStartTime = null;
        this.speechFrameCount += 1;

        if (ttsService.isSpeaking() && this.speechFrameCount >= 2) {
          ttsService.stop();
        }

        if (
          (this.status === Status.LISTENING || this.status === Status.WAITING) &&
          (this.speechFrameCount >= 2 || rms > silenceThreshold * 1.45)
        ) {
          this.status = Status.RECORDING;
        }
      } else if (this.status === Status.RECORDING) {
        this.speechFrameCount = 0;
        if (!this.silenceStartTime) {
          this.silenceStartTime = now;
        }

        const silenceDuration = now - this.silenceStartTime;
        if (silenceDuration >= this.owner.config.silence_duration) {
          this.status = Status.WAITING;
        }
      } else {
        this.speechFrameCount = 0;
      }

      this.analysisFrame = requestAnimationFrame(analyzeFrame);
    };

    this.stopAudioAnalysis();
    this.analysisFrame = requestAnimationFrame(analyzeFrame);
  }

  stopAudioAnalysis() {
    if (this.analysisFrame) {
      cancelAnimationFrame(this.analysisFrame);
      this.analysisFrame = null;
    }
  }

  stopRecording() {
    if (this.mediaRecorder?.state === "recording") {
      this.mediaRecorder.stop();
    }
    this.hasStartedRecording = false;
  }

  densify(value) {
    return Math.exp(-5 * (1 - value));
  }

  async process() {
    const payload = await this.buildAudioPayload();
    if (!payload) {
      if (this.status === Status.PROCESSING) {
        this.status = Status.LISTENING;
      }
      return;
    }

    try {
      const result = await callJsonApi(`/plugins/${PLUGIN_NAME}/transcribe`, {
        audio: payload.audio,
        mime_type: payload.mimeType,
      });
      if (result?.success === false && result?.code !== "no_speech") {
        throw new Error(result?.error || "Transcription failed");
      }
      const text = this.filterResult(result?.text || "");
      if (text) {
        await this.updateCallback(text, true);
      }
    } catch (error) {
      console.error("[Whisper STT] Transcription failed", error);
      window.toastFetchError?.("Transcription error", error);
    } finally {
      this.audioChunks = [];
      this.pcmAudioChunks = [];
      this.preRollAudioChunks = [];
      this.preRollSampleCount = 0;
      if (this.status === Status.PROCESSING) {
        this.status = Status.LISTENING;
      }
    }
  }

  convertBlobToBase64(audioBlob) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        const result = String(reader.result || "");
        resolve(result.split(",")[1] || "");
      };
      reader.onerror = (error) => reject(error);
      reader.readAsDataURL(audioBlob);
    });
  }

  initMediaRecorderFallback(stream) {
    if (!window.MediaRecorder) return;

    try {
      const options = MediaRecorder.isTypeSupported?.("audio/webm;codecs=opus")
        ? { mimeType: "audio/webm;codecs=opus" }
        : undefined;
      this.mediaRecorder = new MediaRecorder(stream, options);
      this.mediaRecorder.ondataavailable = (event) => {
        if (
          event.data.size > 0 &&
          (this.status === Status.RECORDING || this.status === Status.WAITING)
        ) {
          if (this.lastChunk) {
            this.audioChunks.push(this.lastChunk);
            this.lastChunk = null;
          }
          this.audioChunks.push(event.data);
        } else if (this.status === Status.LISTENING) {
          this.lastChunk = event.data;
        }
      };
    } catch (error) {
      console.warn("[Whisper STT] MediaRecorder fallback unavailable", error);
      this.mediaRecorder = null;
    }
  }

  capturePcmFrame(input) {
    if (
      this.status !== Status.LISTENING &&
      this.status !== Status.RECORDING &&
      this.status !== Status.WAITING
    ) {
      return;
    }

    const frame = new Float32Array(input.length);
    frame.set(input);

    if (this.status === Status.RECORDING || this.status === Status.WAITING) {
      this.pcmAudioChunks.push(frame);
      return;
    }

    this.preRollAudioChunks.push(frame);
    this.preRollSampleCount += frame.length;

    const maxPreRollSamples = Math.ceil((this.inputSampleRate * PRE_ROLL_MS) / 1000);
    while (
      this.preRollSampleCount > maxPreRollSamples &&
      this.preRollAudioChunks.length > 1
    ) {
      const dropped = this.preRollAudioChunks.shift();
      this.preRollSampleCount -= dropped?.length || 0;
    }
  }

  async buildAudioPayload() {
    if (this.pcmAudioChunks.length > 0) {
      const wavBlob = this.createWavBlob(this.pcmAudioChunks);
      if (wavBlob.size >= MIN_AUDIO_BYTES) {
        const audio = await this.convertBlobToBase64(wavBlob);
        if (audio && audio.length >= MIN_AUDIO_BYTES) {
          return { audio, mimeType: "audio/wav" };
        }
      }
    }

    if (this.audioChunks.length === 0) {
      return null;
    }

    const mimeType = this.mediaRecorder?.mimeType || "audio/webm";
    const audioBlob = new Blob(this.audioChunks, { type: mimeType });
    if (audioBlob.size < MIN_AUDIO_BYTES) {
      return null;
    }

    const audio = await this.convertBlobToBase64(audioBlob);
    if (!audio || audio.length < MIN_AUDIO_BYTES) {
      return null;
    }

    return { audio, mimeType };
  }

  createWavBlob(chunks) {
    const source = this.flattenChunks(chunks);
    const resampled = this.resampleToTarget(source, this.inputSampleRate);
    const pcm = this.floatTo16BitPcm(resampled);
    const buffer = new ArrayBuffer(44 + pcm.byteLength);
    const view = new DataView(buffer);

    this.writeAscii(view, 0, "RIFF");
    view.setUint32(4, 36 + pcm.byteLength, true);
    this.writeAscii(view, 8, "WAVE");
    this.writeAscii(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, TARGET_SAMPLE_RATE, true);
    view.setUint32(28, TARGET_SAMPLE_RATE * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    this.writeAscii(view, 36, "data");
    view.setUint32(40, pcm.byteLength, true);

    const output = new Uint8Array(buffer, 44);
    output.set(new Uint8Array(pcm.buffer));
    return new Blob([buffer], { type: "audio/wav" });
  }

  flattenChunks(chunks) {
    const totalLength = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    const output = new Float32Array(totalLength);
    let offset = 0;
    for (const chunk of chunks) {
      output.set(chunk, offset);
      offset += chunk.length;
    }
    return output;
  }

  resampleToTarget(input, sourceRate) {
    if (!input.length || sourceRate === TARGET_SAMPLE_RATE) {
      return input;
    }

    const ratio = sourceRate / TARGET_SAMPLE_RATE;
    const outputLength = Math.max(1, Math.floor(input.length / ratio));
    const output = new Float32Array(outputLength);

    for (let index = 0; index < outputLength; index += 1) {
      const sourceIndex = index * ratio;
      const left = Math.floor(sourceIndex);
      const right = Math.min(left + 1, input.length - 1);
      const weight = sourceIndex - left;
      output[index] = input[left] * (1 - weight) + input[right] * weight;
    }

    return output;
  }

  floatTo16BitPcm(input) {
    const output = new Int16Array(input.length);
    for (let index = 0; index < input.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, input[index]));
      output[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
    }
    return output;
  }

  writeAscii(view, offset, value) {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(offset + index, value.charCodeAt(index));
    }
  }

  filterResult(text) {
    const normalized = String(text || "").trim();
    if (!normalized) return "";

    const wrapped =
      (normalized.startsWith("{") && normalized.endsWith("}")) ||
      (normalized.startsWith("(") && normalized.endsWith(")")) ||
      (normalized.startsWith("[") && normalized.endsWith("]"));

    if (wrapped) {
      console.log(`[Whisper STT] Discarding transcription: ${normalized}`);
      return "";
    }

    return normalized;
  }

  async toggle() {
    const hasPermission = await this.requestPermission();
    if (!hasPermission) return;

    if (
      this.status === Status.INACTIVE ||
      this.status === Status.ACTIVATING
    ) {
      this.status = Status.LISTENING;
    } else {
      this.owner.stop();
    }
  }

  async requestPermission() {
    return await this.owner.requestMicrophonePermission();
  }

  dispose() {
    clearTimeout(this.waitingTimer);
    this.waitingTimer = null;
    this.stopAudioAnalysis();

    try {
      this.mediaRecorder?.stream?.getTracks?.().forEach((track) => track.stop());
    } catch (_error) {
      // Ignore media cleanup failures.
    }

    try {
      this.mediaStream?.getTracks?.().forEach((track) => track.stop());
    } catch (_error) {
      // Ignore media cleanup failures.
    }

    try {
      this.processorNode?.disconnect?.();
      this.silentGainNode?.disconnect?.();
      this.mediaStreamSource?.disconnect?.();
      this.analyserNode?.disconnect?.();
    } catch (_error) {
      // Ignore audio graph cleanup failures.
    }

    try {
      this.audioContext?.close?.();
    } catch (_error) {
      // Ignore audio context cleanup failures.
    }

    this.mediaStream = null;
    this.mediaRecorder = null;
    this.mediaStreamSource = null;
    this.analyserNode = null;
    this.processorNode = null;
    this.silentGainNode = null;
    this.audioContext = null;
    this.audioChunks = [];
    this.pcmAudioChunks = [];
    this.preRollAudioChunks = [];
    this.lastChunk = null;
    this.hasStartedRecording = false;
  }
}

export const store = createStore("whisperStt", model);
