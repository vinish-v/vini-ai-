class VoiceCaptureProcessor extends AudioWorkletProcessor {
  process(inputs) {
    const input = inputs[0];
    const channel = input?.[0];
    if (channel?.length) {
      this.port.postMessage(channel.slice(0));
    }
    return true;
  }
}

registerProcessor("voice-capture-processor", VoiceCaptureProcessor);
