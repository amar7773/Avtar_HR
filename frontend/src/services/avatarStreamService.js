// D-ID Persistent WebRTC Avatar Stream Service
// Manages real-time WebRTC peer connection, remote media stream, and Janus DataChannel events.

class AvatarStreamService {
  constructor() {
    this.streamId = null;
    this.sessionId = null;
    this.peerConnection = null;
    this.pcDataChannel = null;
    this.remoteStream = null;
    this.connectionState = "disconnected";
    this.isStreamReady = false;
    this.apiUrl = null;
    this.listeners = {
      streamReady: new Set(),
      streamEvent: new Set(),
      stateChange: new Set(),
    };
    this.connectPromise = null;
    this.reconnectTimeout = null;
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
          console.warn(`[AVATAR-STREAM] Listener error for ${event}:`, err);
        }
      });
    }
  }

  setConnectionState(state) {
    if (this.connectionState !== state) {
      this.connectionState = state;
      console.log(`[AVATAR-STREAM] State changed to: ${state}`);
      this.emit("stateChange", state);
    }
  }

  isConnected() {
    return (
      Boolean(this.streamId) &&
      Boolean(this.sessionId) &&
      this.peerConnection &&
      (this.peerConnection.connectionState === "connected" ||
        this.peerConnection.iceConnectionState === "connected")
    );
  }

  getStreamId() {
    return this.streamId;
  }

  getSessionId() {
    return this.sessionId;
  }

  getRemoteStream() {
    return this.remoteStream;
  }

  async connect(apiUrl) {
    this.apiUrl = apiUrl || this.apiUrl;
    if (this.isConnected()) {
      console.log("[AVATAR-STREAM] Already connected, reusing persistent stream:", this.streamId);
      return { streamId: this.streamId, sessionId: this.sessionId };
    }

    if (this.connectPromise) {
      return this.connectPromise;
    }

    this.connectPromise = this._initConnection();
    try {
      const res = await this.connectPromise;
      return res;
    } finally {
      this.connectPromise = null;
    }
  }

  async _initConnection() {
    this.setConnectionState("connecting");
    this._cleanupPeerConnection();

    try {
      console.log("[AVATAR-STREAM] Requesting new WebRTC stream from backend...");
      const res = await fetch(`${this.apiUrl}/avatar/stream/new`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!res.ok) {
        throw new Error(`Failed to request stream: HTTP ${res.status}`);
      }

      const data = await res.json();
      if (!data.stream_id || !data.offer) {
        throw new Error(data.error || "Backend did not return valid stream offer.");
      }

      this.streamId = data.stream_id;
      this.sessionId = data.session_id;
      const iceServers = data.ice_servers || [];

      console.log("[AVATAR-STREAM] Stream created. Setting up RTCPeerConnection...", {
        streamId: this.streamId,
        sessionId: this.sessionId,
      });

      const pc = new (window.RTCPeerConnection ||
        window.webkitRTCPeerConnection ||
        window.mozRTCPeerConnection)({
        iceServers,
      });
      this.peerConnection = pc;

      // Create data channel for D-ID events (stream/started, stream/done, stream/ready)
      try {
        const dc = pc.createDataChannel("JanusDataChannel");
        this.pcDataChannel = dc;
        dc.onopen = () => console.log("[AVATAR-STREAM] DataChannel open.");
        dc.onmessage = (event) => this._handleDataChannelMessage(event);
        dc.onerror = (err) => console.warn("[AVATAR-STREAM] DataChannel error:", err);
      } catch (dcErr) {
        console.warn("[AVATAR-STREAM] Could not create JanusDataChannel:", dcErr);
      }

      // Handle ICE candidates trickling to D-ID
      pc.onicecandidate = (event) => {
        if (event.candidate) {
          const { candidate, sdpMid, sdpMLineIndex } = event.candidate;
          fetch(`${this.apiUrl}/avatar/stream/ice`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              stream_id: this.streamId,
              session_id: this.sessionId,
              candidate,
              sdp_mid: sdpMid,
              sdp_mline_index: sdpMLineIndex,
            }),
          }).catch((err) => console.warn("[AVATAR-STREAM] ICE submit warning:", err));
        }
      };

      // Handle connection states
      pc.onconnectionstatechange = () => {
        console.log("[AVATAR-STREAM] PeerConnection state:", pc.connectionState);
        if (pc.connectionState === "connected") {
          this.setConnectionState("connected");
        } else if (
          pc.connectionState === "failed" ||
          pc.connectionState === "closed"
        ) {
          this.setConnectionState("disconnected");
        }
      };

      pc.oniceconnectionstatechange = () => {
        console.log("[AVATAR-STREAM] ICE connection state:", pc.iceConnectionState);
        if (pc.iceConnectionState === "connected" || pc.iceConnectionState === "completed") {
          this.setConnectionState("connected");
        } else if (pc.iceConnectionState === "failed") {
          this.setConnectionState("disconnected");
        }
      };

      // Remote media stream arrived (video + audio)
      pc.ontrack = (event) => {
        console.log("[AVATAR-STREAM] Remote track received:", event.track?.kind);
        if (event.streams && event.streams[0]) {
          this.remoteStream = event.streams[0];
          this.emit("streamReady", this.remoteStream);
        }
      };

      // Set remote offer from D-ID
      await pc.setRemoteDescription(new RTCSessionDescription(data.offer));

      // Create client answer and set local description
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);

      // Send answer to D-ID
      const sdpRes = await fetch(`${this.apiUrl}/avatar/stream/sdp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          stream_id: this.streamId,
          session_id: this.sessionId,
          answer: {
            type: answer.type,
            sdp: answer.sdp,
          },
        }),
      });

      if (!sdpRes.ok) {
        throw new Error(`SDP exchange failed with HTTP ${sdpRes.status}`);
      }

      console.log("[AVATAR-STREAM] SDP answer accepted. WebRTC negotiation completed.");
      return { streamId: this.streamId, sessionId: this.sessionId };
    } catch (error) {
      console.error("[AVATAR-STREAM] Connection setup failed:", error);
      this.setConnectionState("error");
      this._cleanupPeerConnection();
      throw error;
    }
  }

  _handleDataChannelMessage(msgEvent) {
    if (!msgEvent || !msgEvent.data) return;
    const raw = String(msgEvent.data);
    const [eventName, extra] = raw.split(":");
    console.log(`[AVATAR-STREAM] DataChannel event: ${eventName}`, extra || "");

    switch (eventName) {
      case "stream/started":
        this.emit("streamEvent", "started", extra);
        break;
      case "stream/done":
        this.emit("streamEvent", "done", extra);
        break;
      case "stream/ready":
        this.isStreamReady = true;
        this.emit("streamEvent", "ready", extra);
        break;
      case "stream/error":
        this.emit("streamEvent", "error", extra);
        break;
      default:
        this.emit("streamEvent", eventName, extra);
        break;
    }
  }

  attachVideo(videoElement) {
    if (!videoElement) return false;
    if (this.remoteStream) {
      if (videoElement.srcObject !== this.remoteStream) {
        videoElement.srcObject = this.remoteStream;
      }
      videoElement.play().catch((err) => {
        console.warn("[AVATAR-STREAM] Video play autoplay warning:", err);
      });
      return true;
    }
    return false;
  }

  _cleanupPeerConnection() {
    if (this.pcDataChannel) {
      try {
        this.pcDataChannel.close();
      } catch {}
      this.pcDataChannel = null;
    }
    if (this.peerConnection) {
      try {
        this.peerConnection.close();
      } catch {}
      this.peerConnection = null;
    }
  }

  async disconnect() {
    const sId = this.streamId;
    const sessId = this.sessionId;
    const api = this.apiUrl;

    this.streamId = null;
    this.sessionId = null;
    this.remoteStream = null;
    this.isStreamReady = false;
    this._cleanupPeerConnection();
    this.setConnectionState("disconnected");

    if (sId && api) {
      try {
        await fetch(`${api}/avatar/stream/${sId}`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessId || "" }),
        });
        console.log(`[AVATAR-STREAM] Stream ${sId} deleted from server.`);
      } catch (err) {
        console.warn("[AVATAR-STREAM] Error closing stream on server:", err);
      }
    }
  }

  async reconnect(apiUrl) {
    await this.disconnect();
    return this.connect(apiUrl);
  }
}

export const avatarStreamService = new AvatarStreamService();
export default avatarStreamService;
