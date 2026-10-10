// HeyGen LiveAvatar Web SDK Integration Service
// Manages real-time WebRTC sessions via LiveKit using @heygen/liveavatar-web-sdk.
// Supports ONE SHARED SESSION simultaneously powering both Main Talk with Avatar and Floating Talk with Avatar.
// Audio-driven synchronization using 16-bit 24kHz mono PCM in Lite Mode with event-driven speaking lifecycle.

import {
  LiveAvatarSession,
  SessionEvent,
  AgentEventsEnum,
  SessionState,
} from "@heygen/liveavatar-web-sdk";

export function cleanTextForSpeech(text) {
  if (!text) return "";
  let s = String(text).trim();
  // Remove markdown links [text](url) -> text
  s = s.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
  // Remove bold / italics
  s = s.replace(/\*\*([^*]+)\*\*/g, "$1");
  s = s.replace(/\*([^*]+)\*/g, "$1");
  s = s.replace(/__([^_]+)__/g, "$1");
  s = s.replace(/_([^_]+)_/g, "$1");
  // Remove markdown headers #, ##
  s = s.replace(/^#{1,6}\s*/gm, "");
  // Remove code blocks
  s = s.replace(/```[a-zA-Z]*\n?([\s\S]*?)```/g, "$1");
  s = s.replace(/`([^`]+)`/g, "$1");
  // Bullet points
  s = s.replace(/^\s*[-*•]\s+/gm, "");
  // Emojis that TTS shouldn't read
  s = s.replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, "");
  // Normalize whitespace
  s = s.replace(/\n+/g, ". ");
  s = s.replace(/\s+/g, " ").trim();
  return s;
}

/**
 * Splits raw 16-bit 24kHz mono PCM buffer into 20ms sample-aligned chunks:
 * 24,000 samples/sec * 2 bytes/sample * 0.02s = 960 bytes per chunk (480 samples).
 * Each 960-byte slice is converted to a base64 string matching the official
 * HeyGen LiveAvatar Lite Mode audio frame ingestion specification.
 */
export function chunkPcm24kToBase64(pcmBuffer, chunkMs = 20) {
  const bytes = pcmBuffer instanceof Uint8Array ? pcmBuffer : new Uint8Array(pcmBuffer);
  const chunks = [];
  if (bytes.length === 0) return chunks;

  // 960 bytes = exactly 20ms at 24kHz mono 16-bit PCM
  const bytesPerChunk = Math.max(960, Math.round((24000 * 2 * chunkMs) / 1000));
  const alignedChunkSize = bytesPerChunk - (bytesPerChunk % 2); // strictly 2-byte sample aligned

  let offset = 0;
  while (offset < bytes.length) {
    const end = Math.min(offset + alignedChunkSize, bytes.length);
    const slice = bytes.subarray(offset, end);
    offset = end;

    let binary = "";
    const len = slice.length;
    for (let i = 0; i < len; i += 8192) {
      const sub = slice.subarray(i, Math.min(i + 8192, len));
      binary += String.fromCharCode.apply(null, sub);
    }
    chunks.push(btoa(binary));
  }
  return chunks;
}

/**
 * Decode arbitrary browser audio (MP3/WAV) to 16-bit 24kHz mono PCM using Web Audio API.
 * Provides resilient browser-side fallback if server-converted PCM is unavailable.
 */
export async function decodeAudioUrlToPcm24k(audioUrl) {
  const res = await fetch(audioUrl);
  if (!res.ok) throw new Error(`Audio fetch failed (${res.status})`);
  const arrayBuffer = await res.arrayBuffer();

  const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtxClass) {
    throw new Error("Web Audio API not supported in this browser");
  }
  const audioCtx = new AudioCtxClass();
  try {
    const decoded = await audioCtx.decodeAudioData(arrayBuffer.slice(0));
    const OfflineCtxClass = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    const offlineCtx = new OfflineCtxClass(
      1,
      Math.ceil(decoded.duration * 24000),
      24000
    );
    const source = offlineCtx.createBufferSource();
    source.buffer = decoded;
    source.connect(offlineCtx.destination);
    source.start(0);
    const rendered = await offlineCtx.startRendering();

    const channelData = rendered.getChannelData(0);
    const pcm16 = new Int16Array(channelData.length);
    for (let i = 0; i < channelData.length; i++) {
      const s = Math.max(-1, Math.min(1, channelData[i]));
      pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return pcm16.buffer;
  } finally {
    audioCtx.close().catch(() => {});
  }
}

let globalAudioCtx = null;

/**
 * Proactively initializes/resumes a shared Web Audio AudioContext on user interaction.
 * Ensures zero-latency audio hardware playback without browser autoplay policy blockage.
 */
export async function unlockBrowserAudio() {
  try {
    const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtxClass) return false;
    if (!globalAudioCtx || globalAudioCtx.state === "closed") {
      globalAudioCtx = new AudioCtxClass({ latencyHint: "interactive" });
    }
    if (globalAudioCtx.state === "suspended") {
      await globalAudioCtx.resume();
    }
    const buf = globalAudioCtx.createBuffer(1, 1, 24000);
    const src = globalAudioCtx.createBufferSource();
    src.buffer = buf;
    src.connect(globalAudioCtx.destination);
    src.start(0);
    return true;
  } catch (err) {
    console.warn("[AUDIO_UNLOCK] Browser audio unlock notice:", err);
    return false;
  }
}

export function logMediaDiagnostics(prefix, videoElement) {
  if (!videoElement) return;
  const stream = videoElement.srcObject;
  const vTracks = stream && stream.getVideoTracks ? stream.getVideoTracks() : [];
  const aTracks = stream && stream.getAudioTracks ? stream.getAudioTracks() : [];
  console.log(`${prefix} Video diagnostics:`, {
    srcObject: stream,
    readyState: videoElement.readyState,
    videoWidth: videoElement.videoWidth,
    videoHeight: videoElement.videoHeight,
    videoTracks: vTracks.map((t) => ({ id: t.id, kind: t.kind, enabled: t.enabled, readyState: t.readyState, muted: t.muted })),
    audioTracks: aTracks.map((t) => ({ id: t.id, kind: t.kind, enabled: t.enabled, readyState: t.readyState, muted: t.muted })),
  });
}

export class LiveAvatarController {
  constructor(name = "shared") {
    this.name = name;
    this.session = null;
    this.sessionId = null;
    this.sessionToken = null;
    this.attachedElements = new Map(); // Map<HTMLVideoElement, { role: "main" | "floating" }>
    this.activeAudioRole = "main"; // "main" or "floating" — which element is currently unmuted
    this.isStreamReady = false;
    this.isSessionStarted = false;
    this.isFullyReady = false;
    this.connectionState = "inactive"; // "inactive" | "connecting" | "connected" | "disconnected" | "expired" | "error"
    this.isSpeaking = false;
    this.activeRequestId = null;
    this.currentSpeechEventId = null;
    this.listeners = {
      streamReady: new Set(),
      stateChange: new Set(),
      speakStarted: new Set(),
      speakEnded: new Set(),
      error: new Set(),
      disconnected: new Set(),
      expired: new Set(),
    };
    this.connectPromise = null;
    this.keepAliveTimer = null;
    this.sessionExpiryTimer = null;
    this.sessionStartTime = null;
    this.isManualStop = false;
    this.lastApiUrl = null;
    this.lastOptions = null;
    this.speechEndSafetyTimer = null;
    this.speechStartTime = null;
    this.isAudioUnlocked = false;
  }

  async ensureAudioUnlocked() {
    try {
      await unlockBrowserAudio();
      if (this.session?.room?.startAudio) {
        await this.session.room.startAudio();
      }
      this.syncAudioMuting();
      this.isAudioUnlocked = true;
      return true;
    } catch (err) {
      console.warn(`[LIVE-AVATAR] Audio playback unlock notice:`, err);
      this.isAudioUnlocked = false;
      return false;
    }
  }

  setActiveAudioRole(role) {
    if (this.activeAudioRole !== role) {
      this.activeAudioRole = role;
      console.log(`[LIVE-AVATAR] Active audio role switched to: ${role}`);
      this.syncAudioMuting();
    }
  }

  syncAudioMuting() {
    this.attachedElements.forEach((meta, el) => {
      if (!el) return;
      const shouldBeAudible = meta.role === this.activeAudioRole;
      el.muted = !shouldBeAudible;
      el.volume = shouldBeAudible ? 1.0 : 0.0;
      if (el.paused && el.srcObject) {
        el.play().catch(() => {});
      }
    });
  }

  async waitForStreamReadyAndDecoded(videoEl, timeoutMs = 8000) {
    const el = videoEl || Array.from(this.attachedElements.keys())[0];
    const start = performance.now();
    console.log(`[LIVE-AVATAR] Awaiting active video/audio decoding and playback (timeout: ${timeoutMs}ms)...`);
    while (performance.now() - start < timeoutMs) {
      const wsReady = this.session?._sessionEventSocket?.readyState === WebSocket.OPEN;
      const streamReady = this.isStreamReady;
      const vTracks = el?.srcObject?.getVideoTracks?.() || [];
      const aTracks = el?.srcObject?.getAudioTracks?.() || [];
      const hasLiveVideo = vTracks.some((t) => t.readyState === "live" && t.enabled);
      const hasLiveAudio = aTracks.some((t) => t.readyState === "live" && t.enabled);
      const isDecoded = Boolean(el && el.readyState >= 2);
      const isPlaying = Boolean(el && !el.paused);

      if (wsReady && streamReady && hasLiveVideo && hasLiveAudio && isDecoded && isPlaying) {
        console.log(`[LIVE-AVATAR] Stream verified fully ready, decoded & playing in ${(performance.now() - start).toFixed(1)}ms`);
        return true;
      }

      // Nudge play if paused
      if (el && el.srcObject && el.paused) {
        try { await el.play(); } catch {}
      }

      await new Promise((r) => setTimeout(r, 60));
    }
    return false;
  }

  on(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event].add(callback);
    }
    return () => this.off(event, callback);
  }

  off(event, callback) {
    if (this.listeners[event]) {
      this.listeners[event].delete(callback);
    }
  }

  emit(event, ...args) {
    if (this.listeners[event]) {
      this.listeners[event].forEach((cb) => {
        try {
          cb(...args);
        } catch (err) {
          console.warn(`[LIVE-AVATAR] Listener error for ${event}:`, err);
        }
      });
    }
  }

  setConnectionState(state) {
    if (this.connectionState !== state) {
      this.connectionState = state;
      console.log(`[LIVE-AVATAR] Connection state changed to: ${state}`);
      this.emit("stateChange", state);
    }
  }

  isConnected() {
    return (
      Boolean(this.session) &&
      (this.session.state === SessionState.CONNECTED || this.isStreamReady)
    );
  }

  getSessionId() {
    return this.sessionId;
  }

  attachVideo(videoElement, { role = "main" } = {}) {
    if (!videoElement) return false;

    this.attachedElements.set(videoElement, { role });
    videoElement.autoplay = true;
    videoElement.playsInline = true;

    // Apply audio muting policy to prevent echo between main & floating views
    const shouldBeAudible = role === this.activeAudioRole;
    videoElement.muted = !shouldBeAudible;
    videoElement.volume = shouldBeAudible ? 1.0 : 0.0;

    if (!this.session || !this.isStreamReady) {
      return false;
    }

    // If element already has active live WebRTC tracks from this session, preserve them
    if (videoElement.srcObject) {
      const activeTracks = videoElement.srcObject.getVideoTracks?.() || [];
      if (activeTracks.some((t) => t.readyState === "live")) {
        if (videoElement.paused) {
          videoElement.play().catch(() => {});
        }
        return true;
      }
    }

    try {
      console.log(`[LIVE-AVATAR] Attaching shared WebRTC tracks to ${role} video element.`);
      this.session.attach(videoElement);

      this.syncAudioMuting();

      if (!videoElement._liveAvatarAutoResume) {
        videoElement._liveAvatarAutoResume = true;
        videoElement.addEventListener("pause", () => {
          if (this.isConnected() && !this.isManualStop && videoElement.srcObject) {
            videoElement.play().catch(() => {});
          }
        });
      }

      videoElement.play().catch(() => {});
      return true;
    } catch (err) {
      console.warn(`[LIVE-AVATAR] Video attach warning:`, err);
      return false;
    }
  }

  detachVideo(videoElement) {
    if (!videoElement) return;
    this.attachedElements.delete(videoElement);
    try {
      if (this.session) {
        if (this.session._remoteVideoTrack?.detach) {
          this.session._remoteVideoTrack.detach(videoElement);
        }
        if (this.session._remoteAudioTrack?.detach) {
          this.session._remoteAudioTrack.detach(videoElement);
        }
      }
      videoElement.srcObject = null;
    } catch (e) {
      console.warn("[LIVE-AVATAR] Detach video element notice:", e);
    }
  }

  async startSession(apiUrl, { avatarId, quality = "medium" } = {}) {
    this.lastApiUrl = apiUrl;
    this.lastOptions = { avatarId, quality };
    this.isManualStop = false;

    if (this.isConnected()) {
      console.log(`[LIVE-AVATAR] Reusing active shared session:`, this.sessionId);
      this.attachedElements.forEach((_, el) => {
        if (el && this.isStreamReady) {
          this.attachVideo(el, this.attachedElements.get(el));
        }
      });
      return { sessionId: this.sessionId };
    }

    if (this.connectPromise) {
      return this.connectPromise;
    }

    this.connectPromise = this._initSession(apiUrl, { avatarId, quality });
    try {
      const res = await this.connectPromise;
      return res;
    } finally {
      this.connectPromise = null;
    }
  }

  async _initSession(apiUrl, { avatarId, quality }) {
    this.setConnectionState("connecting");
    await this.stopSession({ isReconnecting: true });

    try {
      console.log(`[LIVE-AVATAR] Requesting session token (mode: LITE) from ${apiUrl}/avatar/live/session...`);
      const tokenRes = await fetch(`${apiUrl}/avatar/live/session`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          avatar_id: avatarId || undefined,
          mode: "LITE",
          quality: quality || "medium",
        }),
      });

      if (!tokenRes.ok) {
        const errJson = await tokenRes.json().catch(() => ({}));
        throw new Error(errJson.detail || `Session token request failed (${tokenRes.status})`);
      }

      const tokenData = await tokenRes.json();
      if (!tokenData.success || !tokenData.session_token) {
        throw new Error(tokenData.detail || "Invalid session token received from server.");
      }

      this.sessionId = tokenData.session_id;
      this.sessionToken = tokenData.session_token;
      this.sessionStartTime = Date.now();
      console.log(`[LIVE-AVATAR] Session token acquired (sessionId: ${this.sessionId}). Initializing LiveKit room...`);

      const sessionConfig = {
        autoKeepAlive: true,
        voiceChat: false, // Application manages local VAD and microphone pipeline
      };

      const session = new LiveAvatarSession(this.sessionToken, sessionConfig);
      this.session = session;

      // Bind WebRTC Media Stream events
      session.on(SessionEvent.SESSION_STREAM_READY, () => {
        console.log(`[LIVE-AVATAR] WebRTC media stream ready at ${performance.now().toFixed(2)}ms`);
        this.isStreamReady = true;

        // Attach all currently registered video elements (both main and floating)
        this.attachedElements.forEach((meta, el) => {
          if (el) {
            this.attachVideo(el, meta);
          }
        });
        this._checkAndEmitReady();
      });

      session.on(SessionEvent.SESSION_STATE_CHANGED, (state) => {
        console.log(`[LIVE-AVATAR] Session state changed:`, state);
        if (state === SessionState.CONNECTED) {
          this.setConnectionState("connected");
        } else if (state === SessionState.DISCONNECTED) {
          this.setConnectionState("disconnected");
        }
      });

      session.on(SessionEvent.SESSION_DISCONNECTED, (reason) => {
        console.log(`[LIVE-AVATAR] Session disconnected:`, reason);
        this.isStreamReady = false;
        this.isFullyReady = false;
        this.setConnectionState("expired");
        this.emit("expired", reason);
        this.emit("disconnected", reason);
      });

      // Bind Speaking lifecycle events
      session.on(AgentEventsEnum.AVATAR_SPEAK_STARTED, (data) => {
        const tSpeak = performance.now();
        console.log(`[TIMING] [LIVE-AVATAR] Speech playback started (AVATAR_SPEAK_STARTED) at ${tSpeak.toFixed(2)}ms, eventId=${data?.event_id}`);
        this.isSpeaking = true;
        this.syncAudioMuting();
        this.emit("speakStarted", { ...data, requestId: this.activeRequestId });
      });

      session.on(AgentEventsEnum.AVATAR_SPEAK_ENDED, (data) => {
        const tEnd = performance.now();
        console.log(`[TIMING] [LIVE-AVATAR] Speech playback ended (AVATAR_SPEAK_ENDED) at ${tEnd.toFixed(2)}ms, eventId=${data?.event_id}`);
        if (this.speechEndSafetyTimer) {
          clearTimeout(this.speechEndSafetyTimer);
          this.speechEndSafetyTimer = null;
        }
        this.isSpeaking = false;
        this.currentSpeechEventId = null;
        this.emit("speakEnded", { ...data, requestId: this.activeRequestId });
      });

      await session.start();
      this.isSessionStarted = true;
      this.setConnectionState("connected");
      this._startKeepAlive();
      this._startSessionExpiryTimer();

      // Ensure socket onopen listener triggers check
      if (session._sessionEventSocket) {
        const existingOpen = session._sessionEventSocket.onopen;
        session._sessionEventSocket.onopen = (evt) => {
          if (existingOpen) existingOpen.call(session._sessionEventSocket, evt);
          this._checkAndEmitReady();
        };
      }
      this._checkAndEmitReady();

      return { sessionId: this.sessionId };
    } catch (err) {
      console.error(`[LIVE-AVATAR] Session start failed:`, err);
      this.setConnectionState("error");
      this.emit("error", err);
      await this.stopSession({ isReconnecting: false });
      throw err;
    }
  }

  _checkAndEmitReady() {
    const wsReady = this.session?._sessionEventSocket?.readyState === WebSocket.OPEN;
    if (this.isStreamReady && wsReady) {
      if (!this.isFullyReady) {
        this.isFullyReady = true;
        console.log(`[LIVE-AVATAR] Stream & WebSocket fully ready.`);
        this.emit("streamReady");
      }
    }
  }

  _startKeepAlive() {
    this._stopKeepAlive();
    this.keepAliveTimer = setInterval(async () => {
      if (this.session && this.isConnected()) {
        try {
          await this.session.keepAlive();
        } catch (err) {
          console.warn(`[LIVE-AVATAR] Keepalive ping notice:`, err);
        }
      }
    }, 45000);
  }

  _stopKeepAlive() {
    if (this.keepAliveTimer) {
      clearInterval(this.keepAliveTimer);
      this.keepAliveTimer = null;
    }
  }

  _startSessionExpiryTimer() {
    this._stopSessionExpiryTimer();
    // Enforce 120-second (2 minute) free tier lifetime guard
    const maxDurationSec = this.session?.maxSessionDuration || 120;
    const expiryMs = maxDurationSec * 1000;
    console.log(`[LIVE-AVATAR] Session limit configured for ${maxDurationSec} seconds.`);

    this.sessionExpiryTimer = setTimeout(() => {
      console.log(`[LIVE-AVATAR] 2-minute plan limit reached. Safely concluding session.`);
      this.isStreamReady = false;
      this.isFullyReady = false;
      this.setConnectionState("expired");
      this.emit("expired", "MAX_DURATION_EXCEEDED");
      this.stopSession({ isReconnecting: false });
    }, expiryMs);
  }

  _stopSessionExpiryTimer() {
    if (this.sessionExpiryTimer) {
      clearTimeout(this.sessionExpiryTimer);
      this.sessionExpiryTimer = null;
    }
  }

  async speakUtterance({ text, pcmData, pcmBase64, pcmUrl, audioUrl, requestId } = {}) {
    if (!this.session) {
      console.warn(`[LIVE-AVATAR] Cannot speak: no active session.`);
      return false;
    }

    if (!this.isFullyReady) {
      console.log(`[LIVE-AVATAR] Awaiting readiness before delivering speech...`);
      const deadline = Date.now() + 4000;
      while (!this.isFullyReady && Date.now() < deadline) {
        await new Promise((r) => setTimeout(r, 40));
      }
    }

    this.interrupt();
    this.activeRequestId = requestId || (crypto.randomUUID ? crypto.randomUUID() : Date.now());
    const currentReq = this.activeRequestId;

    // 1. Obtain 24kHz mono 16-bit PCM buffer
    let pcmBuffer = pcmData;

    // Direct memory decode of pcmBase64 (<1ms)
    if (!pcmBuffer && pcmBase64 && typeof pcmBase64 === "string") {
      try {
        const binStr = atob(pcmBase64);
        const len = binStr.length;
        const u8 = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
          u8[i] = binStr.charCodeAt(i);
        }
        pcmBuffer = u8.buffer;
      } catch (err) {
        console.warn(`[LIVE-AVATAR] Could not decode pcmBase64:`, err);
      }
    }

    if (!pcmBuffer && pcmUrl) {
      try {
        const res = await fetch(pcmUrl);
        if (res.ok) {
          pcmBuffer = await res.arrayBuffer();
        }
      } catch (err) {
        console.warn(`[LIVE-AVATAR] Could not fetch pcmUrl:`, err);
      }
    }

    if (!pcmBuffer && audioUrl) {
      try {
        pcmBuffer = await decodeAudioUrlToPcm24k(audioUrl);
      } catch (err) {
        console.warn(`[LIVE-AVATAR] Web Audio decode failed:`, err);
      }
    }

    // Race condition check: If another utterance started while loading audio, abort
    if (this.activeRequestId !== currentReq) {
      return false;
    }

    const eventId = crypto.randomUUID ? crypto.randomUUID() : `evt-${Date.now()}`;
    this.currentSpeechEventId = eventId;

    await this.ensureAudioUnlocked();

    // In Lite Mode: Inject audio chunks over HeyGen WebSocket
    const wsWaitStart = Date.now();
    while (
      (!this.session?._sessionEventSocket || this.session._sessionEventSocket.readyState !== WebSocket.OPEN) &&
      Date.now() - wsWaitStart < 4000
    ) {
      await new Promise((r) => setTimeout(r, 40));
    }

    const ws = this.session?._sessionEventSocket;

    if (ws && ws.readyState === WebSocket.OPEN && pcmBuffer && pcmBuffer.byteLength > 0) {
      // 20ms audio frame chunking (960 bytes aligned to 16-bit mono 24kHz)
      const chunks = chunkPcm24kToBase64(pcmBuffer, 20);
      console.log(`[TIMING] [LIVE-AVATAR] Streaming ${chunks.length} x 20ms audio frames over WebSocket (eventId=${eventId}).`);

      for (const chunk of chunks) {
        ws.send(JSON.stringify({
          type: "agent.speak",
          event_id: eventId,
          audio: chunk,
        }));
      }
      ws.send(JSON.stringify({
        type: "agent.speak_end",
        event_id: eventId,
      }));

      // Safety timeout in case WebSocket drop prevents agent.speak_ended
      if (this.speechEndSafetyTimer) clearTimeout(this.speechEndSafetyTimer);
      const durSec = pcmBuffer.byteLength / 48000;
      const safetyMs = Math.max(2000, Math.round(durSec * 1000) + 1500);
      this.speechEndSafetyTimer = setTimeout(() => {
        if (this.isSpeaking && this.currentSpeechEventId === eventId) {
          console.log(`[LIVE-AVATAR] Speech end safety fallback triggered.`);
          this.isSpeaking = false;
          this.currentSpeechEventId = null;
          this.speechEndSafetyTimer = null;
          this.emit("speakEnded", { event_id: eventId, isSafetyFallback: true, requestId: currentReq });
        }
      }, safetyMs);

      return true;
    }

    // Fallback text repeat if PCM or WebSocket unavailable
    const raw = String(text || "").trim();
    if (raw) {
      const cleaned = cleanTextForSpeech(raw) || raw;
      try {
        this.session.repeat(cleaned);
        return true;
      } catch (err) {
        console.error(`[LIVE-AVATAR] repeat(text) failed:`, err);
      }
    }

    return false;
  }

  speak(text) {
    return this.speakUtterance({ text });
  }

  interrupt() {
    if (this.speechEndSafetyTimer) {
      clearTimeout(this.speechEndSafetyTimer);
      this.speechEndSafetyTimer = null;
    }
    if (this.session && this.isConnected() && this.isSpeaking) {
      try {
        console.log(`[LIVE-AVATAR] Interrupting avatar speech...`);
        this.session.interrupt();
        this.isSpeaking = false;
        this.currentSpeechEventId = null;
        this.emit("speakEnded", { isInterrupted: true });
        return true;
      } catch (err) {
        console.warn(`[LIVE-AVATAR] Interrupt error:`, err);
      }
    }
    return false;
  }

  async stopSession({ isReconnecting = false } = {}) {
    this._stopKeepAlive();
    this._stopSessionExpiryTimer();
    if (this.speechEndSafetyTimer) {
      clearTimeout(this.speechEndSafetyTimer);
      this.speechEndSafetyTimer = null;
    }

    if (!isReconnecting) {
      this.isManualStop = true;
    }

    const activeSession = this.session;
    this.session = null;
    this.sessionId = null;
    this.sessionToken = null;
    this.isStreamReady = false;
    this.isSessionStarted = false;
    this.isFullyReady = false;
    this.isSpeaking = false;
    this.activeRequestId = null;
    this.currentSpeechEventId = null;

    if (activeSession) {
      try {
        console.log(`[LIVE-AVATAR] Stopping session on server...`);
        await activeSession.stop();
      } catch (err) {
        console.warn(`[LIVE-AVATAR] Error stopping session:`, err);
      }
    }

    if (!isReconnecting) {
      this.attachedElements.forEach((_, el) => {
        if (el) el.srcObject = null;
      });
      this.setConnectionState("inactive");
    }
  }
}

// Single application-level shared instance powering both Main and Floating avatar views
export const sharedLiveAvatarService = new LiveAvatarController("shared");
