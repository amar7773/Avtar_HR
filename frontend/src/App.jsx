import { useEffect, useRef, useState } from "react";
import "./App.css";
import avatarStreamService from "./services/avatarStreamService";

const API_URL =
  import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

const QUICK_ACTIONS = [
  {
    icon: "◎",
    title: "My Profile",
    desc: "View your employee details",
    query: "Show my complete profile details",
  },
  {
    icon: "◷",
    title: "Attendance",
    desc: "Check your attendance",
    query: "Show my attendance",
  },
  {
    icon: "◆",
    title: "Leave",
    desc: "Check your leave information",
    query: "What leaves are available?",
  },
  {
    icon: "▣",
    title: "Holidays",
    desc: "View company holidays",
    query: "What are the company holidays in 2026?",
  },
];

function formatIndiaTimestamps(text) {
  const isoTimestamp =
    /\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b/g;
  const utcTime =
    /\b(\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\b/g;

  const formattedDates = text.replace(isoTimestamp, (value) => {
    const dateOnlyTimestamp =
      /^(\d{4}-\d{2}-\d{2})T00:00:00(?:\.0+)?(?:Z|\+00:00)$/.exec(value);

    if (dateOnlyTimestamp) {
      const date = new Date(`${dateOnlyTimestamp[1]}T00:00:00Z`);

      return new Intl.DateTimeFormat("en-IN", {
        timeZone: "UTC",
        day: "2-digit",
        month: "short",
        year: "numeric",
      }).format(date);
    }

    const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value);
    const date = new Date(hasTimezone ? value : `${value}Z`);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    const timeZone = hasTimezone ? "Asia/Kolkata" : "UTC";

    return (
      new Intl.DateTimeFormat("en-IN", {
        timeZone,
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      }).format(date) + " IST"
    );
  });

  return formattedDates.replace(utcTime, (value) => {
    const date = new Date(`1970-01-01T${value}`);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return (
      new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true,
      }).format(date) + " IST"
    );
  });
}

function FormattedMessage({ content }) {
  const formattedContent = formatIndiaTimestamps(String(content || ""));
  const lines = formattedContent.split("\n");

  return (
    <div className="formatted-message">
      {lines.map((line, index) => {
        const trimmed = line.trim();
        if (!trimmed) {
          return <div className="formatted-gap" key={`gap-${index}`} />;
        }

        const isHeading = trimmed.startsWith("### ") || trimmed.startsWith("## ");
        const isBullet = trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("• ");

        let text = trimmed;
        if (isHeading) {
          text = trimmed.replace(/^#{2,3}\s+/, "");
        } else if (isBullet) {
          text = trimmed.replace(/^[-*•]\s+/, "");
        }

        const parts = text.split(/(\*\*[^*]+\*\*)/g);
        const rendered = parts.map((part, partIndex) => {
          if (part.startsWith("**") && part.endsWith("**")) {
            return (
              <strong key={partIndex}>
                {part.slice(2, -2)}
              </strong>
            );
          }
          return <span key={partIndex}>{part}</span>;
        });

        if (isHeading) {
          return (
            <div className="formatted-heading" key={`${index}-${line}`}>
              {rendered}
            </div>
          );
        }

        if (isBullet) {
          return (
            <div className="formatted-bullet" key={`${index}-${line}`}>
              <span className="bullet-point">•</span>
              <span className="bullet-content">{rendered}</span>
            </div>
          );
        }

        return (
          <div className="formatted-line" key={`${index}-${line}`}>
            {rendered}
          </div>
        );
      })}
    </div>
  );
}

function App() {
  const [loggedIn, setLoggedIn] = useState(() => {
    return Boolean(localStorage.getItem("employee_id"));
  });

  const [employee, setEmployee] = useState(() => {
    try {
      return JSON.parse(
        localStorage.getItem("employee") || "null"
      );
    } catch {
      return null;
    }
  });

  const [loginId, setLoginId] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [serverOnline, setServerOnline] = useState(false);

  const [activePage, setActivePage] = useState("assistant");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const [message, setMessage] = useState("");

  const [messages, setMessages] = useState(() => {
    const id = localStorage.getItem("employee_id");

    if (!id) {
      return [];
    }

    try {
      return JSON.parse(
        localStorage.getItem(`chat_${id}`) || "[]"
      );
    } catch {
      return [];
    }
  });

  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [isMicMuted, setIsMicMuted] = useState(false);
  const mediaRecorderRef = useRef(null);
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const vadTimerRef = useRef(null);
  const animFrameRef = useRef(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [userAudioUrl, setUserAudioUrl] = useState(null);
  const [avatarVideoUrl, setAvatarVideoUrl] = useState(null);
  const [avatarImageUrl, setAvatarImageUrl] = useState(
    `${API_URL}/avatar-files/avtar_img.jpg`
  );
  const [avatarState, setAvatarState] = useState("idle");
  const [hasStreamVideo, setHasStreamVideo] = useState(false);
  const speechFallbackTimeoutRef = useRef(null);
  const [latestUserText, setLatestUserText] = useState("");
  const [latestAiResponse, setLatestAiResponse] = useState("");
  const activeAudioRef = useRef(null);
  const pollIntervalRef = useRef(null);
  const pendingDidTalkIdRef = useRef(null);

  const activePageRef = useRef(activePage);
  const isSubmittingVoiceRef = useRef(false);
  const voiceAbortControllerRef = useRef(null);
  const ttsAbortControllerRef = useRef(null);
  const greetingAbortControllerRef = useRef(null);
  const sttAbortControllerRef = useRef(null);
  const ttsAudioRef = useRef(null);
  const currentAudioRequestIdRef = useRef(0);
  const shouldDiscardRecordingRef = useRef(false);
  const isGreetingActiveRef = useRef(false);
  const isVoiceConversationActiveRef = useRef(false);
  const [quickOptions, setQuickOptions] = useState([
    { label: "📅 My attendance", query: "Show my attendance" },
    { label: "🌴 My leave balance", query: "What is my leave balance?" },
    { label: "👤 My profile", query: "Show my complete employee profile details" },
  ]);
  const [floatingAvatarOpen, setFloatingAvatarOpen] = useState(() => {
    return sessionStorage.getItem("floating_avatar_open") !== "false";
  });
  const floatingAvatarOpenRef = useRef(floatingAvatarOpen);
  const [floatingPanelInput, setFloatingPanelInput] = useState("");
  const [floatingMessages, setFloatingMessages] = useState(() => {
    const id = localStorage.getItem("employee_id");
    if (!id) {
      return [];
    }
    try {
      return JSON.parse(
        localStorage.getItem(`floating_avatar_chat_${id}`) || "[]"
      );
    } catch {
      return [];
    }
  });
  const [voiceCompact, setVoiceCompact] = useState(false);
  const [toast, setToast] = useState("");

  useEffect(() => {
    activePageRef.current = activePage;
  }, [activePage]);

  useEffect(() => {
    floatingAvatarOpenRef.current = floatingAvatarOpen;
    sessionStorage.setItem("floating_avatar_open", String(floatingAvatarOpen));
  }, [floatingAvatarOpen]);

  useEffect(() => {
    const id = localStorage.getItem("employee_id");
    if (id) {
      localStorage.setItem(
        `floating_avatar_chat_${id}`,
        JSON.stringify(floatingMessages)
      );
    }
  }, [floatingMessages]);

  // Fetch initial avatar image and custom status
  useEffect(() => {
    fetch(`${API_URL}/avatar/custom-info`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.browser_url) {
          const full = data.browser_url.startsWith("http")
            ? data.browser_url
            : `${API_URL}${data.browser_url}`;
          setAvatarImageUrl(full);
        }
      })
      .catch(() => {});
  }, []);

  // Persistent D-ID WebRTC Stream Lifecycle Management
  useEffect(() => {
    const isAvatarActive = activePage === "avtar" || floatingAvatarOpen;
    if (isAvatarActive) {
      avatarStreamService.connect(API_URL).catch((err) => {
        console.warn("[AVATAR] WebRTC connection notice (MP4 fallback is ready if needed):", err);
      });
    }

    const unsubReady = avatarStreamService.on("streamReady", () => {
      setHasStreamVideo(true);
    });

    const unsubEvent = avatarStreamService.on("streamEvent", (event) => {
      if (event === "started") {
        setAvatarState("speaking");
      } else if (event === "done") {
        setAvatarState("idle");
        setVoiceLoading(false);
      }
    });

    const unsubState = avatarStreamService.on("stateChange", (state) => {
      if (state === "disconnected" || state === "error") {
        setHasStreamVideo(false);
      } else if (state === "connected") {
        setHasStreamVideo(true);
      }
    });

    return () => {
      unsubReady();
      unsubEvent();
      unsubState();
    };
  }, [activePage, floatingAvatarOpen]);

  const messagesEndRef = useRef(null);

  const employeeName = employee?.name || "Employee";
  const initial = employeeName.charAt(0).toUpperCase();

  async function checkServer() {
    try {
      const response = await fetch(`${API_URL}/`, {
        method: "GET",
      });

      setServerOnline(response.ok);
    } catch {
      setServerOnline(false);
    }
  }

  useEffect(() => {
    // Health status is synchronized with the API when the shell mounts.
    // oxlint-disable-next-line react(set-state-in-effect)
    checkServer();

    const timer = setInterval(checkServer, 15000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const id = localStorage.getItem("employee_id");

    if (id) {
      localStorage.setItem(`chat_${id}`, JSON.stringify(messages));
    }
  }, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timer = setTimeout(() => {
      setToast("");
    }, 2500);

    return () => clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    return () => {
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }
    };
  }, [audioUrl]);

  useEffect(() => {
    return () => {
      if (userAudioUrl) {
        URL.revokeObjectURL(userAudioUrl);
      }
    };
  }, [userAudioUrl]);


  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearTimeout(pollIntervalRef.current);
      }
      if (activeAudioRef.current) {
        activeAudioRef.current.pause();
      }
      if (vadTimerRef.current) {
        clearTimeout(vadTimerRef.current);
      }
      if (animFrameRef.current) {
        cancelAnimationFrame(animFrameRef.current);
      }
      if (audioContextRef.current) {
        try {
          audioContextRef.current.close();
        } catch {}
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  const notify = (text) => {
    setToast(text);
  };

  const handleLogin = async () => {
    const id = loginId.trim();

    if (!id) {
      setLoginError("Please enter your Employee ID.");
      return;
    }

    try {
      setLoginLoading(true);
      setLoginError("");

      const response = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          employee_id: id,
        }),
      });

      let data;

      try {
        data = await response.json();
      } catch {
        throw new Error(
          "Server returned an invalid response."
        );
      }

      if (!response.ok) {
        setLoginError(
          data?.detail ||
            data?.message ||
            "Login request failed."
        );
        return;
      }

      if (!data?.success || !data?.employee) {
        setLoginError(
          data?.message || "Employee ID not found."
        );
        return;
      }

      const loggedEmployee = data.employee;

      localStorage.setItem(
        "employee_id",
        String(loggedEmployee.employee_id)
      );

      localStorage.setItem(
        "employee",
        JSON.stringify(loggedEmployee)
      );

      setEmployee(loggedEmployee);
      setLoggedIn(true);
      setActivePage("assistant");
      setSidebarOpen(false);
      setLoginId("");
      setServerOnline(true);

      try {
        const oldMessages = JSON.parse(
          localStorage.getItem(
            `chat_${loggedEmployee.employee_id}`
          ) || "[]"
        );

        setMessages(
          Array.isArray(oldMessages) ? oldMessages : []
        );
      } catch {
        setMessages([]);
      }

      try {
        const oldFloating = JSON.parse(
          localStorage.getItem(
            `floating_avatar_chat_${loggedEmployee.employee_id}`
          ) || "[]"
        );

        setFloatingMessages(
          Array.isArray(oldFloating) ? oldFloating : []
        );
      } catch {
        setFloatingMessages([]);
      }
    } catch (error) {
      console.error("Login error:", error);

      setServerOnline(false);

      setLoginError(
        "Unable to connect to the server. Please make sure FastAPI is running."
      );
    } finally {
      setLoginLoading(false);
    }
  };

  const logout = () => {
    stopAllAudio({ resetUI: true });
    localStorage.removeItem("employee_id");
    localStorage.removeItem("employee");

    setLoggedIn(false);
    setEmployee(null);
    setMessages([]);
    setFloatingMessages([]);
    setFloatingAvatarOpen(false);
    floatingAvatarOpenRef.current = false;
    sessionStorage.removeItem("floating_avatar_open");
    setMessage("");
    setLoginId("");
    setLoginError("");
    setAudioUrl(null);
    setAvatarVideoUrl(null);
    setAvatarState("idle");
    setLatestUserText("");
    setLatestAiResponse("");
    setActivePage("assistant");
    setSidebarOpen(false);
  };

  const sendMessage = async (text = message) => {
    if (!text?.trim() || loading || !employee) {
      return;
    }

    if (activeAudioRef.current || ttsAudioRef.current) {
      stopAllAudio({ resetUI: false });
    }

    const userText = text.trim();

    const now = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: "user",
        content: userText,
        time: now,
      },
    ]);

    setMessage("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_query: userText,
          employee_id: String(
            employee.employee_id
          ),
        }),
      });

      let data;

      try {
        data = await response.json();
      } catch {
        throw new Error(
          "Invalid response from server."
        );
      }

      if (!response.ok) {
        throw new Error(
          data?.detail || "Chat API failed"
        );
      }

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content:
            data?.response ||
            data?.answer ||
            "I couldn't generate a response.",
          time: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);

      setServerOnline(true);
    } catch (error) {
      console.error("Chat error:", error);

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          role: "assistant",
          error: true,
          content:
            "Sorry, I couldn't process your request right now. Please try again.",
          time: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);

      setServerOnline(false);
    } finally {
      setLoading(false);
    }
  };

  const sendFloatingMessage = async (text = floatingPanelInput) => {
    const query = String(text || "").trim();
    if (!query || voiceLoading || loading || !employee) return;
    setFloatingPanelInput("");

    // Text / chip interaction is not a voice conversational loop
    isVoiceConversationActiveRef.current = false;
    isGreetingActiveRef.current = false;

    // Interrupt any playing audio, video, or speech immediately
    if (activeAudioRef.current || ttsAudioRef.current) {
      stopAllAudio({ resetUI: false });
    }

    const reqId = ++currentAudioRequestIdRef.current;
    const now = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

    setLatestUserText(query);
    setLatestAiResponse("");
    setAvatarState("thinking");
    setVoiceLoading(true);

    setFloatingMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", content: query, time: now, voice: false },
    ]);

    try {
      const streamId = avatarStreamService.getStreamId();
      const sessionId = avatarStreamService.getSessionId();

      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_query: query,
          employee_id: String(employee.employee_id),
          mode: "avatar_mode",
          stream_id: streamId,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.detail || "Chat request failed.");
      }

      const data = await response.json();
      if (reqId !== currentAudioRequestIdRef.current) return;

      const aiResponse = data.response || "I processed your request.";

      if (data.stream_talk) {
        setAvatarState("speaking");
        setLatestAiResponse(aiResponse);
        setFloatingMessages((prev) => [
          ...prev,
          { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: false },
        ]);
        const estSec = Math.max(3, Math.min(45, Math.ceil(aiResponse.length / 10)));
        if (speechFallbackTimeoutRef.current) clearTimeout(speechFallbackTimeoutRef.current);
        speechFallbackTimeoutRef.current = setTimeout(() => {
          if (currentAudioRequestIdRef.current === reqId) {
            setAvatarState((curr) => (curr === "speaking" ? "idle" : curr));
            setVoiceLoading(false);
          }
        }, estSec * 1000 + 4000);
      } else {
        const talkId = data.avatar_talk_id || data?.avatar?.talk_id;
        if (talkId && typeof talkId === "string" && talkId.startsWith("tlk_")) {
          setAvatarVideoUrl(null);
          setAvatarState("preparing");
          setLatestAiResponse(aiResponse);
          setFloatingMessages((prev) => [
            ...prev,
            { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: false },
          ]);
          pollAvatarVideo(talkId, reqId);
        } else if (data.audio_url) {
          const fullAudio = data.audio_url.startsWith("http") ? data.audio_url : `${API_URL}${data.audio_url}`;
          const audio = new Audio(fullAudio);
          activeAudioRef.current = audio;

          // Continuous lip-sync facial movement loop during speech
          setAvatarVideoUrl(`${API_URL}/avatar-files/response_avatar.mp4?t=${Date.now()}`);

          let messageRendered = false;
          const syncStartSpeaking = () => {
            if (!messageRendered && currentAudioRequestIdRef.current === reqId) {
              messageRendered = true;
              setAvatarState("speaking");
              setLatestAiResponse(aiResponse);
              setFloatingMessages((prev) => [
                ...prev,
                { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: false },
              ]);
            }
          };

          audio.onplay = syncStartSpeaking;

          const cleanupAudio = () => {
            audio.onended = null;
            audio.onerror = null;
            audio.onplay = null;
            syncStartSpeaking();
            if (activeAudioRef.current === audio) activeAudioRef.current = null;
            setAvatarVideoUrl(null);
            setAvatarState("idle");
            setVoiceLoading(false);
          };
          audio.onended = cleanupAudio;
          audio.onerror = cleanupAudio;
          audio.play().then(syncStartSpeaking).catch(cleanupAudio);
        } else {
          setAvatarState("idle");
          setVoiceLoading(false);
          setLatestAiResponse(aiResponse);
          setFloatingMessages((prev) => [
            ...prev,
            { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: false },
          ]);
        }
        if (data.avatar_error || data?.avatar?.error) {
          notify(`Avatar: ${data.avatar_error || data?.avatar?.error}`);
        }
      }
    } catch (err) {
      if (reqId !== currentAudioRequestIdRef.current) return;
      console.warn("Avatar text error:", err);
      notify(`Message failed: ${err.message}`);
      setAvatarState("error");
      setFloatingMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          error: true,
          content: "Sorry, I couldn't process your request. Please try again.",
          time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
      setTimeout(() => {
        setAvatarState((curr) => (curr === "error" ? "idle" : curr));
      }, 4000);
    } finally {
      if (reqId === currentAudioRequestIdRef.current) {
        setVoiceLoading(false);
      }
    }
  };

  const stopRecording = () => {
    if (vadTimerRef.current) {
      clearTimeout(vadTimerRef.current);
      vadTimerRef.current = null;
    }
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (streamRef.current) {
      try {
        streamRef.current.getTracks().forEach((track) => {
          track.stop();
          track.enabled = false;
        });
      } catch (err) {
        console.warn("Stop stream tracks error:", err);
      }
      streamRef.current = null;
    }
    if (audioContextRef.current) {
      try {
        audioContextRef.current.close();
      } catch {}
      audioContextRef.current = null;
    }
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state !== "inactive"
    ) {
      try {
        mediaRecorderRef.current.stop();
      } catch (err) {
        console.warn("Stop recorder error:", err);
      }
    }
    setRecording(false);
    setAudioLevel(0);
    setIsMicMuted(false);
  };

  const toggleMicMute = () => {
    setIsMicMuted((prev) => {
      const next = !prev;
      if (streamRef.current) {
        try {
          streamRef.current.getAudioTracks().forEach((track) => {
            track.enabled = !next;
          });
        } catch (err) {
          console.warn("Mic track mute toggle error:", err);
        }
      }
      return next;
    });
  };

  const stopAllAudio = (options = { resetUI: true }) => {
    // Invalidate all pending asynchronous audio/voice callbacks
    currentAudioRequestIdRef.current += 1;
    shouldDiscardRecordingRef.current = true;
    isSubmittingVoiceRef.current = false;

    // 1. Abort any active in-flight fetch requests
    if (voiceAbortControllerRef.current) {
      try {
        voiceAbortControllerRef.current.abort();
      } catch {}
      voiceAbortControllerRef.current = null;
    }
    if (ttsAbortControllerRef.current) {
      try {
        ttsAbortControllerRef.current.abort();
      } catch {}
      ttsAbortControllerRef.current = null;
    }
    if (greetingAbortControllerRef.current) {
      try {
        greetingAbortControllerRef.current.abort();
      } catch {}
      greetingAbortControllerRef.current = null;
    }
    if (sttAbortControllerRef.current) {
      try {
        sttAbortControllerRef.current.abort();
      } catch {}
      sttAbortControllerRef.current = null;
    }

    // 2. Halt active Audio instance (speech-to-speech, greeting, avatar voice)
    if (activeAudioRef.current) {
      try {
        activeAudioRef.current.onended = null;
        activeAudioRef.current.onplay = null;
        activeAudioRef.current.onpause = null;
        activeAudioRef.current.onerror = null;
        activeAudioRef.current.pause();
        activeAudioRef.current.currentTime = 0;
        activeAudioRef.current.src = "";
      } catch {}
      activeAudioRef.current = null;
    }

    // 3. Halt TTS Audio instance
    if (ttsAudioRef.current) {
      try {
        ttsAudioRef.current.onended = null;
        ttsAudioRef.current.onplay = null;
        ttsAudioRef.current.onpause = null;
        ttsAudioRef.current.onerror = null;
        ttsAudioRef.current.pause();
        ttsAudioRef.current.currentTime = 0;
        ttsAudioRef.current.src = "";
      } catch {}
      ttsAudioRef.current = null;
    }

    // 4. Halt any HTML5 <audio> elements in the DOM
    try {
      document.querySelectorAll("audio").forEach((el) => {
        try {
          el.pause();
          el.currentTime = 0;
        } catch {}
      });
    } catch {}

    // 5. Halt D-ID video playback and polling
    if (pollIntervalRef.current) {
      clearTimeout(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
    pendingDidTalkIdRef.current = null;

    if (options?.resetUI) {
      setAvatarVideoUrl(null);
    }

    // 6. Stop microphone tracks and recorder
    stopRecording();

    // 7. Clear VAD timer
    if (vadTimerRef.current) {
      clearTimeout(vadTimerRef.current);
      vadTimerRef.current = null;
    }

    // 8. Reset UI states
    setVoiceLoading(false);
    if (options?.resetUI) {
      setAvatarState("idle");
    }
  };

  const stopAllAvatarActivity = () => {
    stopAllAudio({ resetUI: true });
    currentAudioRequestIdRef.current += 1;
    if (speechFallbackTimeoutRef.current) {
      clearTimeout(speechFallbackTimeoutRef.current);
      speechFallbackTimeoutRef.current = null;
    }
    if (!hasStreamVideo) {
      setAvatarVideoUrl(null);
    }
    setAvatarState("idle");
    setRecording(false);
    setVoiceLoading(false);
  };

  const handleOpenFloatingAvatar = () => {
    setFloatingAvatarOpen(true);
    floatingAvatarOpenRef.current = true;
    isVoiceConversationActiveRef.current = false;
    if (!avatarVideoUrl && avatarState === "idle") {
      triggerGreeting();
    }
  };

  const handleCloseFloatingAvatar = () => {
    setFloatingAvatarOpen(false);
    floatingAvatarOpenRef.current = false;
    stopAllAvatarActivity();
  };

  const handleToggleFloatingAvatar = () => {
    if (floatingAvatarOpen) {
      handleCloseFloatingAvatar();
    } else {
      handleOpenFloatingAvatar();
    }
  };

  const handleRefreshAvatarSession = () => {
    stopAllAudio({ resetUI: false });
    if (speechFallbackTimeoutRef.current) {
      clearTimeout(speechFallbackTimeoutRef.current);
      speechFallbackTimeoutRef.current = null;
    }
    isGreetingActiveRef.current = true;
    isVoiceConversationActiveRef.current = false;
    setRecording(false);
    setVoiceLoading(false);
    clearFloatingChat();
    triggerGreeting();
  };

  const clearFloatingChat = () => {
    const id = localStorage.getItem("employee_id");
    if (id) {
      localStorage.removeItem(`floating_avatar_chat_${id}`);
    }
    setFloatingMessages([]);
    setLatestUserText("");
    setLatestAiResponse("");
    notify("Avatar conversation cleared.");
  };

  const startRecorder = async (onBlob, onBlobMode = "avatar_mode") => {
    shouldDiscardRecordingRef.current = false;
    if (recording || loading || voiceLoading || isSubmittingVoiceRef.current) {
      console.log("[VOICE-MIC] Recorder or submission already active, skipping start.");
      return;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.error("[VOICE-MIC] navigator.mediaDevices.getUserMedia not supported.");
      notify("Microphone is not supported in this browser.");
      return;
    }

    try {
      console.log("[VOICE-MIC] Requesting microphone permission...");
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });
      } catch (micErr) {
        console.warn("[VOICE-MIC] Enhanced audio constraints failed, using standard audio:", micErr);
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      streamRef.current = stream;
      console.log("[VOICE-MIC] Microphone stream acquired successfully:", stream.getAudioTracks().map((t) => t.label).join(", "));

      // Real-time audio level analyser for live visualizer wave & VAD
      try {
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (AudioContextClass) {
          const audioCtx = new AudioContextClass();
          audioContextRef.current = audioCtx;
          if (audioCtx.state === "suspended") {
            await audioCtx.resume();
          }
          console.log("[VOICE-MIC] AudioContext active, state:", audioCtx.state);
          const source = audioCtx.createMediaStreamSource(stream);
          const analyser = audioCtx.createAnalyser();
          analyser.fftSize = 256;
          analyser.smoothingTimeConstant = 0.3;
          source.connect(analyser);

          const pcmData = new Uint8Array(analyser.frequencyBinCount);

          // Voice Activity Detection (VAD) for natural sentence capture
          let hasSpoken = false;
          let firstSpeechTime = null;
          let lastSpeechTime = null;
          const SPEECH_THRESHOLD = 3;  // 3% audio volume sensitivity (catches quiet microphones)
          const SILENCE_MS = 2500;     // 2.5s silence after speaking before auto-submitting
          const MIN_SPEECH_MS = 800;   // At least 0.8s of speech before silence detection can trigger

          const checkLevel = () => {
            if (!streamRef.current) return;
            analyser.getByteFrequencyData(pcmData);
            let sum = 0;
            for (let i = 0; i < pcmData.length; i++) {
              sum += pcmData[i];
            }
            const avg = sum / pcmData.length;
            const volumePercent = Math.min(100, Math.round((avg / 128) * 100));
            setAudioLevel(volumePercent);

            const now = Date.now();
            if (volumePercent >= SPEECH_THRESHOLD) {
              if (!hasSpoken) {
                hasSpoken = true;
                firstSpeechTime = now;
                console.log(`[VOICE-VAD] Speech detected (volume: ${volumePercent}%). Listening to user question...`);
              }
              lastSpeechTime = now;
            } else if (hasSpoken && firstSpeechTime && (now - firstSpeechTime > MIN_SPEECH_MS)) {
              if (lastSpeechTime && (now - lastSpeechTime > SILENCE_MS)) {
                console.log(`[VOICE-VAD] Sentence complete (${Math.round(now - lastSpeechTime)}ms pause after speaking). Submitting question...`);
                stopRecording();
                return;
              }
            }

            animFrameRef.current = requestAnimationFrame(checkLevel);
          };
          animFrameRef.current = requestAnimationFrame(checkLevel);
        }
      } catch (audioCtxErr) {
        console.warn("[VOICE-MIC] AudioContext meter error:", audioCtxErr);
      }

      // Max safety duration: 45 seconds
      vadTimerRef.current = setTimeout(() => {
        console.log("[VOICE-VAD] Maximum speech duration reached (45s). Stopping recording...");
        stopRecording();
      }, 45000);

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";
      const recorder = new MediaRecorder(stream, {
        mimeType,
        audioBitsPerSecond: 128000,
      });
      mediaRecorderRef.current = recorder;
      const chunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      recorder.onerror = (event) => {
        console.error("[VOICE-MIC] Recorder error:", event);
        stopRecording();
        notify("Microphone recording failed.");
      };

      recorder.onstop = async () => {
        console.log("[VOICE-MIC] MediaRecorder stopped. Processing audio chunks...");
        if (vadTimerRef.current) {
          clearTimeout(vadTimerRef.current);
          vadTimerRef.current = null;
        }
        if (animFrameRef.current) {
          cancelAnimationFrame(animFrameRef.current);
          animFrameRef.current = null;
        }
        if (audioContextRef.current) {
          try {
            audioContextRef.current.close();
          } catch {}
          audioContextRef.current = null;
        }
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((track) => {
            track.stop();
            track.enabled = false;
          });
          streamRef.current = null;
        }

        setRecording(false);
        setAudioLevel(0);

        if (shouldDiscardRecordingRef.current) {
          console.log("[VOICE-MIC] Discarding recording because user cancelled.");
          return;
        }

        if (isSubmittingVoiceRef.current) {
          console.log("[VOICE-MIC] Submission already running, skipping duplicate blob.");
          return;
        }

        const blob = new Blob(chunks, {
          type: mimeType,
        });
        console.log(`[VOICE-MIC] Audio recorded: ${blob.size} bytes (${mimeType}, mode: ${onBlobMode}).`);

        if (blob.size < 200) {
          console.log("[VOICE-MIC] Recorded audio too small or empty. Returning to idle.");
          setVoiceLoading(false);
          setAvatarState("idle");
          return;
        }

        isSubmittingVoiceRef.current = true;
        try {
          await onBlob(blob);
        } catch (error) {
          console.error("[VOICE-API] Error submitting audio blob:", error);
        } finally {
          isSubmittingVoiceRef.current = false;
        }
      };

      recorder.start(250);
      console.log("[VOICE-MIC] MediaRecorder started listening.");
      setRecording(true);
    } catch (error) {
      console.error("[VOICE-MIC] Microphone permission/init error:", error);
      stopRecording();
      notify("Please allow microphone access from your browser.");
    }
  };


  const startSTT = () =>
    startRecorder(async (audioBlob) => {
      setLoading(true);
      const reqId = ++currentAudioRequestIdRef.current;
      sttAbortControllerRef.current = new AbortController();

      try {
        const formData = new FormData();
        formData.append(
          "audio",
          audioBlob,
          "employee_voice.webm"
        );

        const response = await fetch(
          `${API_URL}/stt`,
          {
            method: "POST",
            body: formData,
            signal: sttAbortControllerRef.current.signal,
          }
        );

        if (reqId !== currentAudioRequestIdRef.current) {
          return;
        }

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data?.detail || "Speech recognition failed."
          );
        }

        if (reqId !== currentAudioRequestIdRef.current) {
          return;
        }

        setMessage(data?.text || "");

        if (data?.text) {
          notify(
            "Your speech has been converted to text."
          );
        } else {
          notify(
            "No speech was detected."
          );
        }
      } catch (error) {
        if (error.name === "AbortError") {
          return;
        }
        console.error("STT error:", error);

        notify(
          "Sorry, speech recognition failed."
        );
      } finally {
        if (reqId === currentAudioRequestIdRef.current) {
          setLoading(false);
        }
      }
    }, "stt_mode");

  const generateSpeech = async (text) => {
    if (!text?.trim()) {
      return;
    }

    // Stop previous audio immediately
    stopAllAudio({ resetUI: false });

    const reqId = ++currentAudioRequestIdRef.current;
    ttsAbortControllerRef.current = new AbortController();

    try {
      setVoiceLoading(true);

      const response = await fetch(
        `${API_URL}/tts`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            text,
          }),
          signal: ttsAbortControllerRef.current.signal,
        }
      );

      if (!response.ok) {
        throw new Error("Voice generation failed.");
      }

      if (reqId !== currentAudioRequestIdRef.current || document.hidden) {
        return;
      }

      const blob = await response.blob();

      if (reqId !== currentAudioRequestIdRef.current || document.hidden) {
        return;
      }

      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }

      const url = URL.createObjectURL(blob);
      setAudioUrl(url);

      const audio = new Audio(url);
      audio.playbackRate = 1.0;
      activeAudioRef.current = audio;
      ttsAudioRef.current = audio;

      const cleanupTtsAudio = () => {
        audio.onended = null;
        audio.onerror = null;
        audio.onpause = null;
        if (activeAudioRef.current === audio) {
          activeAudioRef.current = null;
        }
        if (ttsAudioRef.current === audio) {
          ttsAudioRef.current = null;
        }
        setVoiceLoading(false);
      };

      audio.onended = cleanupTtsAudio;
      audio.onerror = cleanupTtsAudio;

      await audio.play();
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      console.error("TTS error:", error);

      notify(
        "Sorry, voice playback failed."
      );
    } finally {
      if (reqId === currentAudioRequestIdRef.current) {
        setVoiceLoading(false);
      }
    }
  };

  const pollAvatarVideo = (talkId, boundReqId) => {
    const cleanId = String(talkId || "").trim();
    if (!cleanId.startsWith("tlk_")) {
      notify("Avatar response did not include a D-ID talk ID.");
      setAvatarState("idle");
      return;
    }
    if (pollIntervalRef.current) {
      clearTimeout(pollIntervalRef.current);
    }

    const targetReqId = boundReqId || currentAudioRequestIdRef.current;
    pendingDidTalkIdRef.current = cleanId;
    let attempts = 0;
    const maxAttempts = 120;
    const pollDelayMs = 1200;

    const poll = async () => {
      // Abort only if superseded by a newer request or left avatar session
      if (
        pendingDidTalkIdRef.current !== cleanId ||
        targetReqId !== currentAudioRequestIdRef.current ||
        (activePageRef.current !== "avtar" && !floatingAvatarOpenRef.current)
      ) {
        clearTimeout(pollIntervalRef.current);
        pollIntervalRef.current = null;
        return;
      }

      attempts += 1;
      try {
        const response = await fetch(`${API_URL}/avatar/status/${encodeURIComponent(cleanId)}`);
        if (!response.ok) {
          const errorBody = await response.json().catch(() => ({}));
          throw new Error(errorBody.detail || "Failed to check avatar status.");
        }
        const statusData = await response.json();
        if (statusData.talk_id !== cleanId) {
          throw new Error("D-ID returned status for a different talk ID.");
        }

        if (statusData.status === "done" && statusData.video_url) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
          pendingDidTalkIdRef.current = null;

          const fullVideoUrl = statusData.video_url.startsWith("http")
            ? statusData.video_url
            : `${API_URL}${statusData.video_url}`;

          if (
            targetReqId !== currentAudioRequestIdRef.current ||
            (activePageRef.current !== "avtar" && !floatingAvatarOpenRef.current)
          ) {
            return;
          }

          if (activeAudioRef.current) {
            activeAudioRef.current.pause();
            activeAudioRef.current = null;
          }
          setAvatarVideoUrl(fullVideoUrl);
          setAvatarState("speaking");
        } else if (statusData.status === "error") {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
          pendingDidTalkIdRef.current = null;
          const errDetail = statusData.error || "Avatar video generation failed.";
          console.warn("Avatar video status error or credit limit:", errDetail);
          notify(`Avatar video failed: ${errDetail}`);
          setAvatarVideoUrl(null);
          setAvatarState("idle");
        } else if (attempts >= maxAttempts) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
          pendingDidTalkIdRef.current = null;
          console.warn("Avatar video timed out after 240 seconds");
          notify("Avatar video generation timed out.");
          setAvatarVideoUrl(null);
          setAvatarState("idle");
        }
      } catch (err) {
        console.warn("Avatar status check error:", err);
        if (attempts >= maxAttempts) {
          clearTimeout(pollIntervalRef.current);
          pollIntervalRef.current = null;
          pendingDidTalkIdRef.current = null;
          notify(`Avatar status check failed: ${err.message}`);
          setAvatarVideoUrl(null);
          setAvatarState("idle");
          return;
        }
      }
      if (pendingDidTalkIdRef.current === cleanId) {
        pollIntervalRef.current = setTimeout(poll, pollDelayMs);
      }
    };

    pollIntervalRef.current = setTimeout(poll, 0);
  };

  const handleAvatarVideoEnded = () => {
    console.log("[VOICE-AVATAR] Avatar video finished.");
    // If audio is actively playing in parallel, let audio.onended handle the completion
    if (activeAudioRef.current && !activeAudioRef.current.paused && !activeAudioRef.current.ended) {
      return;
    }
    setAvatarVideoUrl(null);
    setAvatarState("idle");
    isGreetingActiveRef.current = false;
    isVoiceConversationActiveRef.current = false;
  };

  const triggerGreeting = async () => {
    stopAllAudio({ resetUI: false });
    const reqId = ++currentAudioRequestIdRef.current;
    if (greetingAbortControllerRef.current) {
      greetingAbortControllerRef.current.abort();
    }
    const controller = new AbortController();
    greetingAbortControllerRef.current = controller;
    isGreetingActiveRef.current = true;
    isVoiceConversationActiveRef.current = false;

    try {
      setAvatarState("greeting");
      const res = await fetch(`${API_URL}/avatar/greeting?t=${Date.now()}`, { signal: controller.signal });
      if (!res.ok) {
        const errorBody = await res.json().catch(() => ({}));
        throw new Error(errorBody.detail || "Greeting request failed.");
      }
      const data = await res.json();

      if (
        reqId !== currentAudioRequestIdRef.current ||
        (activePageRef.current !== "avtar" && !floatingAvatarOpenRef.current)
      ) {
        return;
      }

      if (Array.isArray(data.quick_options) && data.quick_options.length > 0) {
        setQuickOptions(data.quick_options);
      }

      const greetingText =
        data.text ||
        "Hi, I am your AI employee assistant. How can I help you today?";
      setLatestAiResponse(greetingText);
      setLatestUserText("");

      if (data.video_url) {
        const fullVideo = data.video_url.startsWith("http")
          ? data.video_url
          : `${API_URL}${data.video_url}`;
        setAvatarVideoUrl(fullVideo);
        setAvatarState("greeting");
      } else if (typeof data.talk_id === "string" && data.talk_id.startsWith("tlk_")) {
        setAvatarVideoUrl(null);
        setAvatarState("preparing");
        pollAvatarVideo(data.talk_id, reqId);
      } else {
        setAvatarVideoUrl(null);
        setAvatarState("idle");
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        console.warn("Avatar greeting error:", err);
      }
      if (reqId === currentAudioRequestIdRef.current) {
        setAvatarState("idle");
      }
    }
  };

  // Initial load: automatically play greeting for the avatar
  const initialGreetingDoneRef = useRef(false);
  useEffect(() => {
    if (!initialGreetingDoneRef.current) {
      initialGreetingDoneRef.current = true;
      console.log("[LIFECYCLE] Initial mount — automatically triggering avatar greeting.");
      triggerGreeting();
    }
  }, []);

  // 1. Completely stop voice detection, audio & mic when user leaves any screen
  useEffect(() => {
    activePageRef.current = activePage;
    if (activePage === "avtar") {
      console.log("[LIFECYCLE] Entered Talking Avatar page — triggering greeting & avatar setup.");
      triggerGreeting();
    } else if (!floatingAvatarOpenRef.current) {
      console.log("[LIFECYCLE] Left Talking Avatar page — stopping voice detection & mic completely.");
      stopAllAvatarActivity();
    }
  }, [activePage]);

  // 2. Pause audio/video when tab is hidden, resume cleanly when tab becomes visible
  useEffect(() => {
    const handleVisibility = () => {
      if (document.hidden) {
        console.log("[LIFECYCLE] Browser tab hidden — pausing playing media.");
        if (activeAudioRef.current) {
          try { activeAudioRef.current.pause(); } catch {}
        }
        stopRecording();
      }
    };

    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, []);


  const startVoiceAI = (explicitMode = null) => {
    const rawMode = typeof explicitMode === "string" ? explicitMode : null;
    const mode = rawMode || (activePageRef.current === "avtar" || floatingAvatarOpenRef.current ? "avatar_mode" : "voice_mode");
    if (mode === "avatar_mode" && activePageRef.current !== "avtar" && !floatingAvatarOpenRef.current) {
      console.log("[VOICE-LIFECYCLE] Not on avtar page or floating panel, ignoring avatar voice start.");
      return;
    }
    if (isSubmittingVoiceRef.current) {
      console.log("[VOICE-MIC] Voice submission already in progress.");
      return;
    }

    // Interrupt any ongoing audio/video and start capturing speech
    stopAllAudio({ resetUI: false });
    const reqId = ++currentAudioRequestIdRef.current;
    if (activeAudioRef.current) {
      try { activeAudioRef.current.pause(); activeAudioRef.current.src = ""; } catch {}
      activeAudioRef.current = null;
    }

    if (mode === "avatar_mode") {
      isVoiceConversationActiveRef.current = true;
      isGreetingActiveRef.current = false;
      if (!hasStreamVideo) {
        setAvatarVideoUrl(null);
      }
      setAvatarState("listening");
    }

    return startRecorder(async (audioBlob) => {
      if (
        reqId !== currentAudioRequestIdRef.current ||
        shouldDiscardRecordingRef.current ||
        (mode === "avatar_mode" && activePageRef.current !== "avtar" && !floatingAvatarOpenRef.current)
      ) {
        console.log("[VOICE-API] Discarding recording because state changed or request was superseded.");
        return;
      }

      console.log(`[VOICE-API] Submitting audio to backend (${audioBlob.size} bytes, mode: ${mode})...`);
      setVoiceLoading(true);
      if (mode === "avatar_mode") {
        setAvatarState("thinking");
      }
      setVoiceCompact(false);

      try {
        if (userAudioUrl) {
          URL.revokeObjectURL(userAudioUrl);
        }

        const blobUrl = URL.createObjectURL(audioBlob);
        setUserAudioUrl(blobUrl);

        const formData = new FormData();
        formData.append("audio", audioBlob, "employee_voice.webm");
        formData.append("employee_id", String(employee.employee_id));
        formData.append("mode", mode);
        if (mode === "avatar_mode") {
          const sId = avatarStreamService.getStreamId();
          const sessId = avatarStreamService.getSessionId();
          if (sId && sessId) {
            formData.append("stream_id", sId);
            formData.append("session_id", sessId);
          }
        }

        voiceAbortControllerRef.current = new AbortController();

        const response = await fetch(`${API_URL}/voice`, {
          method: "POST",
          body: formData,
          signal: voiceAbortControllerRef.current.signal,
        });

        if (!response.ok) {
          const errorBody = await response.json().catch(() => ({}));
          throw new Error(
            errorBody.detail ||
              `Voice assistant request failed with status ${response.status}`
          );
        }

        const data = await response.json();

        // If request superseded or left avatar session, discard response
        if (
          reqId !== currentAudioRequestIdRef.current ||
          shouldDiscardRecordingRef.current ||
          (mode === "avatar_mode" && activePageRef.current !== "avtar" && !floatingAvatarOpenRef.current)
        ) {
          console.log("[VOICE-API] Discarding voice response because state changed.");
          return;
        }

        console.log("[VOICE-API] Assistant response received:", {
          user_text: data?.user_text,
          response: data?.response?.slice(0, 80),
          audio_url: data?.audio_url,
          stream_talk: data?.stream_talk,
          talk_id: data?.avatar_talk_id || data?.avatar?.talk_id,
        });

        if (mode !== "avatar_mode" && !data?.audio_url) {
          throw new Error("Voice response did not include audio.");
        }

        const userText = data.user_text || "Voice message";
        const aiResponse = data.response || "Your voice request has been processed.";
        const now = new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        });

        if (mode === "avatar_mode") {
          const didTalkId = data?.avatar_talk_id || data?.avatar?.talk_id;
          setLatestUserText(userText);

          setFloatingMessages((prev) => [
            ...prev,
            { id: Date.now(), role: "user", content: userText, time: now, voice: true },
          ]);

          if (
            reqId !== currentAudioRequestIdRef.current ||
            (activePageRef.current !== "avtar" && !floatingAvatarOpenRef.current)
          ) {
            return;
          }

          if (data?.stream_talk) {
            setAvatarState("speaking");
            setLatestAiResponse(aiResponse);
            setFloatingMessages((prev) => [
              ...prev,
              { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: true },
            ]);
            const estSec = Math.max(3, Math.min(45, Math.ceil(aiResponse.length / 10)));
            if (speechFallbackTimeoutRef.current) clearTimeout(speechFallbackTimeoutRef.current);
            speechFallbackTimeoutRef.current = setTimeout(() => {
              if (currentAudioRequestIdRef.current === reqId) {
                setAvatarState((curr) => (curr === "speaking" ? "idle" : curr));
                setVoiceLoading(false);
                isVoiceConversationActiveRef.current = false;
              }
            }, estSec * 1000 + 4000);
          } else if (typeof didTalkId === "string" && didTalkId.startsWith("tlk_")) {
            setAvatarVideoUrl(null);
            setAvatarState("preparing");
            setLatestAiResponse(aiResponse);
            setFloatingMessages((prev) => [
              ...prev,
              { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: true },
            ]);
            pollAvatarVideo(didTalkId, reqId);
          } else {
            if (data?.audio_url) {
              const fullAudio = data.audio_url.startsWith("http") ? data.audio_url : `${API_URL}${data.audio_url}`;
              const audio = new Audio(fullAudio);
              activeAudioRef.current = audio;

              // Real-time visible lip-sync & facial movement loop during speech
              setAvatarVideoUrl(`${API_URL}/avatar-files/response_avatar.mp4?t=${Date.now()}`);

              let msgRendered = false;
              const syncStartSpeaking = () => {
                if (!msgRendered && currentAudioRequestIdRef.current === reqId) {
                  msgRendered = true;
                  setAvatarState("speaking");
                  setLatestAiResponse(aiResponse);
                  setFloatingMessages((prev) => [
                    ...prev,
                    { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: true },
                  ]);
                }
              };

              audio.onplay = syncStartSpeaking;

              const cleanupVoiceAudio = () => {
                audio.onended = null;
                audio.onerror = null;
                audio.onplay = null;
                syncStartSpeaking();
                if (activeAudioRef.current === audio) activeAudioRef.current = null;
                setAvatarVideoUrl(null);
                setAvatarState("idle");
                isVoiceConversationActiveRef.current = false;
              };
              audio.onended = cleanupVoiceAudio;
              audio.onerror = cleanupVoiceAudio;
              audio.play().then(syncStartSpeaking).catch(cleanupVoiceAudio);
            } else {
              setAvatarVideoUrl(null);
              setAvatarState("idle");
              setLatestAiResponse(aiResponse);
              setFloatingMessages((prev) => [
                ...prev,
                { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: true },
              ]);
            }
            if (data?.avatar_error || data?.avatar?.error) {
              notify(`Avatar: ${data.avatar_error || data?.avatar?.error}`);
            }
          }
        } else {
          // --- VOICE MODE (Assistant tab) ---
          setLatestUserText(userText);
          setLatestAiResponse(aiResponse);
          const url = `${API_URL}${data.audio_url}`;
          setAudioUrl(url);

          setMessages((prev) => [
            ...prev,
            { id: Date.now(), role: "user", content: userText, time: now, voice: true },
            { id: Date.now() + 1, role: "assistant", content: aiResponse, time: now, voice: true },
          ]);

          if (
            reqId !== currentAudioRequestIdRef.current ||
            document.hidden
          ) {
            return;
          }

          const audio = new Audio(url);
          activeAudioRef.current = audio;
          audio.playbackRate = 1.0;

          const cleanupVoiceAudio = () => {
            audio.onended = null;
            audio.onerror = null;
            if (activeAudioRef.current === audio) {
              activeAudioRef.current = null;
            }
          };

          audio.onended = cleanupVoiceAudio;
          audio.onerror = cleanupVoiceAudio;

          audio.play().catch((e) => {
            console.warn("Audio autoplay blocked:", e);
            cleanupVoiceAudio();
          });
          setVoiceCompact(true);
        }
      } catch (error) {
        if (error.name === "AbortError") {
          console.log("[VOICE-API] Voice request aborted cleanly by user navigation.");
          return;
        }
        if (reqId !== currentAudioRequestIdRef.current) return;
        console.error("[VOICE-API] Voice assistant error:", error);
        setAvatarState("error");
        setTimeout(() => {
          setAvatarState((curr) => (curr === "error" ? "idle" : curr));
        }, 4000);

        if (mode !== "avatar_mode") {
          setMessages((prev) => [
            ...prev,
            {
              id: Date.now(),
              role: "assistant",
              error: true,
              content: "Sorry, I couldn't process your voice request.",
              time: new Date().toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              }),
            },
          ]);
        } else {
          setFloatingMessages((prev) => [
            ...prev,
            {
              id: Date.now(),
              role: "assistant",
              error: true,
              content: "Sorry, I couldn't process your voice request. Tap mic to try again.",
              time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
            },
          ]);
          notify(error.message || "Could not process your voice. Please try speaking again.");
        }
      } finally {
        setVoiceLoading(false);
      }
    });
  };




  const clearChat = () => {
    if (!employee) {
      return;
    }

    if (
      !window.confirm(
        "Clear your complete chat history?"
      )
    ) {
      return;
    }

    stopAllAudio({ resetUI: true });

    localStorage.removeItem(
      `chat_${employee.employee_id}`
    );
    setMessages([]);
    setMessage("");
    if (userAudioUrl) {
      URL.revokeObjectURL(userAudioUrl);
    }
    if (audioUrl?.startsWith("blob:")) {
      URL.revokeObjectURL(audioUrl);
    }
    setUserAudioUrl(null);
    setAudioUrl(null);
    setVoiceCompact(false);

    notify("Chat history cleared.");
  };


  const copyMessage = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      notify("Copied to clipboard.");
    } catch {
      notify("Copy failed.");
    }
  };

  const openPage = (page) => {
    setActivePage(page);
    setSidebarOpen(false);
  };

  if (!loggedIn || !employee) {
    return (
      <LoginScreen
        loginId={loginId}
        setLoginId={setLoginId}
        loginLoading={loginLoading}
        loginError={loginError}
        serverOnline={serverOnline}
        handleLogin={handleLogin}
      />
    );
  }

  return (
    <div className="app-shell">
      <div
        className={`mobile-overlay ${
          sidebarOpen ? "show" : ""
        }`}
        onClick={() => setSidebarOpen(false)}
      />

      <aside
        className={`sidebar ${
          sidebarOpen ? "open" : ""
        }`}
      >
        <div className="brand">
          <CompanyLogo className="brand-mark" />

          <div>
            <strong>Employee AI</strong>
            <small>
              Your workplace assistant
            </small>
          </div>
        </div>

        <div className="workspace-label">
          WORKSPACE
        </div>

        <NavButton
          active={
            activePage === "assistant"
          }
          icon="✦"
          label="Assistant"
          onClick={() =>
            openPage("assistant")
          }
        />

        <NavButton
          active={
            activePage === "dashboard"
          }
          icon="▦"
          label="Dashboard"
          onClick={() =>
            openPage("dashboard")
          }
        />

        <NavButton
          active={
            activePage === "profile"
          }
          icon="◎"
          label="My Profile"
          onClick={() =>
            openPage("profile")
          }
        />

        <NavButton
          active={activePage === "avtar"}
          icon={
            <img
              src={avatarImageUrl || `${API_URL}/avatar-files/avtar_img.jpg`}
              alt="Avatar"
              className="nav-avatar-img"
              onError={(e) => {
                if (!e.currentTarget.src.endsWith("/avtar_img.jpg")) {
                  e.currentTarget.src = `${API_URL}/avatar-files/avtar_img.jpg`;
                }
              }}
            />
          }
          label="Talk with Avtar"
          onClick={() => openPage("avtar")}
        />

        <NavButton
          active={
            activePage === "settings"
          }
          icon="⚙"
          label="Settings"
          onClick={() =>
            openPage("settings")
          }
        />

        <div className="sidebar-feature">
          <div className="feature-icon">
            ✦
          </div>

          <strong>
            Everything in one place
          </strong>

          <span>
            Ask questions, check your
            information and get quick
            workplace answers.
          </span>
        </div>

        <div className="sidebar-bottom">
          <div className="employee-mini">
            <Avatar
              initial={initial}
              size="small"
            />

            <div>
              <strong>
                {employeeName}
              </strong>

              <span>
                {employee.employee_id}
              </span>
            </div>

            <i
              className={
                serverOnline
                  ? "status-dot online"
                  : "status-dot"
              }
            />
          </div>

          <button
            className="logout-button"
            onClick={logout}
          >
            ↪
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <button
            className="mobile-menu"
            onClick={() =>
              setSidebarOpen(true)
            }
          >
            ☰
          </button>

          <div>
            <div className="top-title">
              {pageTitle(activePage)}
            </div>

            <div className="connection">
              <span
                className={`status-dot ${
                  serverOnline
                    ? "online"
                    : ""
                }`}
              />

              {serverOnline
                ? "Connected"
                : "Offline"}
            </div>
          </div>

          <div className="top-actions">
            {activePage === "assistant" &&
              messages.length > 0 && (
                <button
                  className="ghost-button"
                  onClick={clearChat}
                >
                  ⌫ Clear
                </button>
              )}

            <div className="top-user">
              <Avatar initial={initial} />

              <div>
                <strong>
                  {employeeName}
                </strong>

                <span>
                  {employee.employee_id}
                </span>
              </div>
            </div>
          </div>
        </header>

        {activePage === "dashboard" && (
          <Dashboard
            employee={employee}
            employeeName={employeeName}
            initial={initial}
            openAssistant={() =>
              openPage("assistant")
            }
            sendMessage={sendMessage}
          />
        )}

        {activePage === "profile" && (
          <Profile
            employee={employee}
            initial={initial}
          />
        )}

        {activePage === "avtar" && (
          <AvtarPage
            avatarImageUrl={avatarImageUrl}
            setAvatarImageUrl={setAvatarImageUrl}
            avatarVideoUrl={avatarVideoUrl}
            avatarState={avatarState}
            setAvatarState={setAvatarState}
            setAvatarVideoUrl={setAvatarVideoUrl}
            hasStreamVideo={hasStreamVideo}
            recording={recording}
            voiceLoading={voiceLoading}
            audioLevel={audioLevel}
            startVoiceAI={() => startVoiceAI("avatar_mode")}
            stopRecording={stopRecording}
            latestUserText={latestUserText}
            latestAiResponse={latestAiResponse}
            onSendMessage={sendFloatingMessage}
            quickOptions={quickOptions}
            onVideoEnded={handleAvatarVideoEnded}
            onReplayGreeting={triggerGreeting}
            notify={notify}
            API_URL={API_URL}
          />
        )}


        {activePage === "settings" && (
          <Settings
            clearChat={clearChat}
          />
        )}

        {activePage === "assistant" && (
          <AssistantView
            employeeName={employeeName}
            initial={initial}
            messages={messages}
            message={message}
            setMessage={setMessage}
            sendMessage={sendMessage}
            loading={loading}
            recording={recording}
            voiceLoading={voiceLoading}
            startSTT={startSTT}
            startVoiceAI={() => startVoiceAI("voice_mode")}
            stopRecording={stopRecording}
            generateSpeech={generateSpeech}
            copyMessage={copyMessage}
            messagesEndRef={messagesEndRef}
            audioUrl={audioUrl}
            userAudioUrl={userAudioUrl}
            voiceCompact={voiceCompact}
            quickActions={QUICK_ACTIONS}
          />
        )}
      </main>

      {/* ── Floating Talk with Avatar ─────────────────────────────────────
          1. Floating button on current page -> opens compact floating panel.
          2. Compact floating panel stays on current page until closed.
          3. Sidebar Talk with Avatar -> remains full-size page.            */}
      {activePage !== "avtar" && !floatingAvatarOpen && (
        <button
          type="button"
          className="floating-avatar-btn"
          onClick={handleOpenFloatingAvatar}
          title="Talk with Avatar"
          aria-label="Open Talk with Avatar"
          id="floating-avatar-shortcut"
        >
          <img
            className="floating-avatar-img"
            src={avatarImageUrl || `${API_URL}/avatar-files/avtar_img.jpg`}
            alt="Talk with Avatar"
            onError={(e) => {
              if (!e.currentTarget.src.endsWith("/avtar_img.jpg")) {
                e.currentTarget.src = `${API_URL}/avatar-files/avtar_img.jpg`;
              }
            }}
          />
          <span className="floating-avatar-status-dot" title="Avatar Active" />
          <span className="floating-avatar-tooltip">Talk with Avatar</span>
        </button>
      )}

      {activePage !== "avtar" && floatingAvatarOpen && (
        <FloatingAvatarPanel
          avatarImageUrl={avatarImageUrl}
          avatarVideoUrl={avatarVideoUrl}
          avatarState={avatarState}
          hasStreamVideo={hasStreamVideo}
          recording={recording}
          voiceLoading={voiceLoading}
          audioLevel={audioLevel}
          messages={floatingMessages}
          inputText={floatingPanelInput}
          setInputText={setFloatingPanelInput}
          onSendText={sendFloatingMessage}
          onStopSpeaking={stopAllAvatarActivity}
          isMicMuted={isMicMuted}
          onToggleMicMute={toggleMicMute}
          onMicClick={() => {
            if (recording) {
              stopRecording();
            } else if (avatarState === "speaking" || activeAudioRef.current) {
              // Interruption: immediately stop avatar speaking and capture user's new voice
              stopAllAvatarActivity();
              startVoiceAI("avatar_mode");
            } else if (!voiceLoading) {
              startVoiceAI("avatar_mode");
            }
          }}
          onClose={handleCloseFloatingAvatar}
          onClearChat={clearFloatingChat}
          onRefresh={handleRefreshAvatarSession}
          onVideoEnded={handleAvatarVideoEnded}
          quickOptions={quickOptions}
          API_URL={API_URL}
        />
      )}

      {toast && (
        <div className="toast">
          {toast}
        </div>
      )}
    </div>
  );
}

function pageTitle(page) {
  return {
    assistant: "Assistant",
    dashboard: "Dashboard",
    profile: "My Profile",
    avtar: "Talk with Avtar",
    settings: "Settings",
  }[page];
}

function NavButton({
  active,
  icon,
  label,
  onClick,
}) {
  return (
    <button
      className={`nav-button ${
        active ? "active" : ""
      }`}
      onClick={onClick}
    >
      <span className="nav-icon">
        {icon}
      </span>

      <span>{label}</span>

      {active && <b>•</b>}
    </button>
  );
}

function Avatar({
  initial,
  size = "normal",
}) {
  return (
    <div
      className={`avatar ${size}`}
    >
      {initial}
    </div>
  );
}

function CompanyLogo({ className = "" }) {
  return (
    <div className={`company-logo-frame ${className}`}>
      <img
        className="company-logo-image"
        src="/company-logo.png"
        alt="Company logo"
        onError={(event) => {
          event.currentTarget.hidden = true;
        }}
      />
    </div>
  );
}

function AvtarPage({
  avatarImageUrl,
  setAvatarImageUrl,
  avatarVideoUrl,
  avatarState = "idle",
  setAvatarVideoUrl,
  setAvatarState,
  hasStreamVideo = false,
  recording = false,
  voiceLoading = false,
  audioLevel = 0,
  startVoiceAI,
  stopRecording,
  latestUserText = "",
  latestAiResponse = "",
  onSendMessage,
  quickOptions = [],
  onVideoEnded,
  onReplayGreeting,
  notify,
  API_URL,
}) {
  const videoRef = useRef(null);
  const fileInputRef = useRef(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [pageInput, setPageInput] = useState("");

  const isCustomAvatar = Boolean(
    avatarImageUrl &&
      (avatarImageUrl.includes("custom_avatar") ||
        avatarImageUrl.includes("custom-avatar"))
  );

  useEffect(() => {
    if (videoRef.current) {
      avatarStreamService.attachVideo(videoRef.current);
    }
  }, [hasStreamVideo]);

  const handleAvatarFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith("image/")) {
      notify?.("Please select a valid image file (JPG, PNG, WebP).");
      return;
    }

    setUploadingAvatar(true);
    try {
      const formData = new FormData();
      formData.append("image", file);

      const res = await fetch(`${API_URL}/avatar/upload`, {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const errJson = await res.json().catch(() => ({}));
        throw new Error(errJson.detail || "Avatar upload failed.");
      }

      const data = await res.json();
      const updatedUrl = data.browser_url.startsWith("http")
        ? data.browser_url
        : `${API_URL}${data.browser_url}?t=${Date.now()}`;

      setAvatarImageUrl?.(updatedUrl);
      notify?.("Custom avatar updated successfully!");
      // Cleanly reconnect persistent WebRTC stream with new avatar
      avatarStreamService.reconnect(API_URL).catch(() => {});
      if (onReplayGreeting) {
        setTimeout(() => {
          onReplayGreeting();
        }, 350);
      }
    } catch (err) {
      console.error("[AVATAR] Upload error:", err);
      notify?.(err.message || "Failed to upload custom avatar.");
    } finally {
      setUploadingAvatar(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const handleResetAvatar = async () => {
    setUploadingAvatar(true);
    try {
      const res = await fetch(`${API_URL}/avatar/reset`, { method: "POST" });
      if (!res.ok) throw new Error("Reset failed.");
      setAvatarImageUrl?.(`${API_URL}/avatar-files/avtar_img.jpg`);
      notify?.("Avatar reset to default.");
      // Cleanly reconnect persistent WebRTC stream with default avatar
      avatarStreamService.reconnect(API_URL).catch(() => {});
      if (onReplayGreeting) {
        setTimeout(() => {
          onReplayGreeting();
        }, 350);
      }
    } catch (err) {
      console.error("[AVATAR] Reset error:", err);
      notify?.("Failed to reset avatar.");
    } finally {
      setUploadingAvatar(false);
    }
  };

  useEffect(() => {
    if (avatarVideoUrl && videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.volume = 1.0;
      const isLoopLipSync = typeof avatarVideoUrl === "string" && avatarVideoUrl.includes("response_avatar.mp4");
      videoRef.current.muted = isLoopLipSync;
      videoRef.current.loop = isLoopLipSync;
      setIsMuted(isLoopLipSync);
      const playPromise = videoRef.current.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          console.warn("Avatar video autoplay restricted:", err);
          if (videoRef.current) {
            videoRef.current.muted = true;
            setIsMuted(true);
            videoRef.current.play().catch((playError) => {
              console.error("Avatar video playback failed:", playError);
            });
          }
        });
      }
    } else if (!avatarVideoUrl && videoRef.current && hasStreamVideo) {
      avatarStreamService.attachVideo(videoRef.current);
    }
  }, [avatarVideoUrl, hasStreamVideo, notify]);

  const handleMicClick = () => {
    if (recording) {
      stopRecording?.();
    } else if (!voiceLoading) {
      startVoiceAI?.();
    }
  };

  const handleVideoEnded = () => {
    if (onVideoEnded) {
      onVideoEnded();
    } else {
      setAvatarVideoUrl?.(null);
      setAvatarState?.("idle");
    }
  };

  const getStatusConfig = () => {
    if (recording || avatarState === "listening") {
      return {
        label: "Listening...",
        className: "listening",
        icon: "🎙️",
      };
    }
    if (voiceLoading || avatarState === "thinking") {
      return {
        label: "Thinking...",
        className: "thinking",
        icon: "✨",
      };
    }
    if (avatarState === "greeting") {
      return {
        label: "Greeting...",
        className: "greeting",
        icon: "👋",
      };
    }
    if (avatarVideoUrl || avatarState === "speaking") {
      return {
        label: "Speaking...",
        className: "speaking",
        icon: "🔊",
      };
    }
    if (avatarState === "preparing") {
      return {
        label: "Processing Voice & Avatar...",
        className: "preparing",
        icon: "⏳",
      };
    }
    return {
      label: "Ready to Talk",
      className: "idle",
      icon: "🟢",
    };
  };

  const status = getStatusConfig();

  return (
    <section className="page avtar-page">
      <div className="avtar-card">
        {/* Header */}
        <div className="avatar-header-row">
          <CompanyLogo className="avtar-logo-compact" />
          <div className="avatar-title-wrap">
            <span className="eyebrow">AI EMPLOYEE ASSISTANT</span>
            <h1>Talk with Avtar</h1>
          </div>
          <div className="avatar-header-actions">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp,image/jpg"
              style={{ display: "none" }}
              onChange={handleAvatarFileSelect}
            />
            {isCustomAvatar ? (
              <div className="avatar-custom-chip-group">
                <span className="avatar-custom-badge" title="Custom avatar active">
                  ✨ Custom
                </span>
                <button
                  type="button"
                  className="avatar-header-chip"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploadingAvatar || recording || voiceLoading}
                  title="Change custom photo"
                >
                  {uploadingAvatar ? "..." : "Change"}
                </button>
                <button
                  type="button"
                  className="avatar-header-chip"
                  onClick={handleResetAvatar}
                  disabled={uploadingAvatar || recording || voiceLoading}
                  title="Reset to default avatar"
                >
                  ↺ Default
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="avatar-header-chip avatar-upload-chip"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadingAvatar || recording || voiceLoading}
                title="Upload custom face / photo for avatar"
              >
                <span>📷</span> {uploadingAvatar ? "Uploading..." : "Custom Avatar"}
              </button>
            )}

            {onReplayGreeting && (
              <button
                type="button"
                className="avatar-replay-chip"
                onClick={onReplayGreeting}
                title="Replay greeting"
                disabled={recording || voiceLoading}
              >
                <span>👋</span> Replay
              </button>
            )}
            <div className={`avatar-status-pill ${status.className}`}>
              <span className="status-pill-icon">{status.icon}</span>
              <span className="status-pill-text">{status.label}</span>
            </div>
          </div>
        </div>

        {/* Two-column body */}
        <div className="avatar-body-row">

          {/* LEFT: Avatar stage */}
          <div
            className={`avatar-stage ${status.className} ${
              (hasStreamVideo || avatarVideoUrl) ? "has-video" : ""
            }`}
            onClick={() => {
              if (videoRef.current) {
                videoRef.current.muted = false;
                videoRef.current.volume = 1.0;
                setIsMuted(false);
                if (videoRef.current.paused) {
                  videoRef.current.play().catch(() => {});
                }
              }
            }}
            title={avatarVideoUrl ? "Click to unmute" : ""}
          >
            <div className="avatar-ambient-halo" />

            {/* Baseline Image Layer - Always rendered behind video to guarantee continuous avatar */}
            {!hasStreamVideo && (
              <img
                className="avatar-image"
                src={avatarImageUrl || `${API_URL}/avatar-files/avtar_img.jpg`}
                alt="Avtar - AI Employee Assistant"
                style={{
                  position: "absolute",
                  inset: 0,
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  objectPosition: "center top",
                  zIndex: 1,
                }}
                onError={(e) => {
                  if (!e.currentTarget.src.endsWith("/avtar_img.jpg")) {
                    e.currentTarget.src = `${API_URL}/avatar-files/avtar_img.jpg`;
                  }
                }}
              />
            )}

            <video
              ref={videoRef}
              className={`avatar-video ${(hasStreamVideo || avatarVideoUrl) ? "has-video" : "video-hidden"}`}
              src={avatarVideoUrl || undefined}
              poster={avatarImageUrl || `${API_URL}/avatar-files/avtar_img.jpg`}
              autoPlay
              playsInline
              muted={isMuted || (typeof avatarVideoUrl === "string" && avatarVideoUrl.includes("response_avatar.mp4"))}
              loop={Boolean(avatarVideoUrl && typeof avatarVideoUrl === "string" && avatarVideoUrl.includes("response_avatar.mp4"))}
              onEnded={handleVideoEnded}
              style={{
                position: "relative",
                zIndex: 2,
                display: (hasStreamVideo || avatarVideoUrl) ? "block" : "none",
                width: "100%",
                height: "100%",
                objectFit: "cover",
                objectPosition: "center top",
              }}
            />
            {isMuted && avatarVideoUrl && !avatarVideoUrl.includes("response_avatar.mp4") && (
              <button
                type="button"
                className="avatar-unmute-overlay-btn"
                style={{ zIndex: 3 }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (videoRef.current) {
                    videoRef.current.muted = false;
                    setIsMuted(false);
                    videoRef.current.play().catch(() => {});
                  }
                }}
              >
                🔊 Unmute
              </button>
            )}

            {status.className === "listening" && (
              <div className="avatar-live-indicator listening">
                <div className="radar-ring ring-1" />
                <div className="radar-ring ring-2" />
                <span className="indicator-chip">Listening...</span>
              </div>
            )}
            {status.className === "thinking" && (
              <div className="avatar-live-indicator thinking">
                <span className="spinner-orbit" />
                <span className="indicator-chip">Processing...</span>
              </div>
            )}
            {status.className === "preparing" && (
              <div className="avatar-live-indicator thinking">
                <span className="spinner-orbit" />
                <span className="indicator-chip">Generating Lip-sync...</span>
              </div>
            )}
            {status.className === "greeting" && (
              <div className="avatar-live-indicator greeting">
                <span className="sparkle-icon">✦</span>
                <span className="indicator-chip">Greeting</span>
              </div>
            )}
            {status.className === "speaking" && (
              <div className="avatar-live-indicator speaking">
                <div className="soundwave-equalizer">
                  <span className="bar bar-1" />
                  <span className="bar bar-2" />
                  <span className="bar bar-3" />
                  <span className="bar bar-4" />
                  <span className="bar bar-5" />
                </div>
                <span className="indicator-chip">Speaking</span>
              </div>
            )}
          </div>

          {/* RIGHT: Transcript + Mic */}
          <div className="avatar-controls-panel">

            {recording && (
              <div className="avatar-live-visualizer">
                <div className="visualizer-bars">
                  {[14, 30, 50, 80, 100, 65, 45, 25, 12].map((h, i) => {
                    const sc = Math.max(6, Math.min(28, Math.round((h * (audioLevel + 15)) / 100)));
                    return (
                      <span
                        key={i}
                        className="live-wave-bar"
                        style={{ height: `${sc}px` }}
                      />
                    );
                  })}
                </div>
                <span className="visualizer-caption">
                  {audioLevel > 10 ? "Speaking detected..." : "Speak now..."}
                </span>
              </div>
            )}

            {(latestUserText || latestAiResponse) ? (
              <div className="avatar-transcript-panel">
                {latestUserText && (
                  <div className="transcript-row you-row">
                    <span className="transcript-badge you-badge">You</span>
                    <span className="transcript-text">{latestUserText}</span>
                  </div>
                )}
                {latestAiResponse && (
                  <div className="transcript-row avtar-row">
                    <span className="transcript-badge avtar-badge">Avtar</span>
                    <div className="transcript-text">
                      <FormattedMessage content={latestAiResponse} />
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="avatar-transcript-empty">
                <span className="transcript-empty-icon">💬</span>
                <p>Your conversation appears here.</p>
                <small>Tap mic and start speaking.</small>
              </div>
            )}

            {/* What Can I Ask? Help Panel */}
            {showHelp && (
              <div className="avatar-help-panel">
                <div className="help-panel-header">
                  <span className="help-panel-icon">💡</span>
                  <strong>What Can I Ask?</strong>
                  <button
                    type="button"
                    className="help-close-btn"
                    onClick={() => setShowHelp(false)}
                    title="Close help"
                  >
                    ✕
                  </button>
                </div>
                <div className="help-panel-grid">
                  <div className="help-category">
                    <span className="help-cat-label">📅 Attendance</span>
                    <ul>
                      <li>"Show my attendance"</li>
                      <li>"Was I present yesterday?"</li>
                      <li>"Meri September ki attendance batao"</li>
                      <li>"Aaj main present tha?"</li>
                    </ul>
                  </div>
                  <div className="help-category">
                    <span className="help-cat-label">🌴 Leave</span>
                    <ul>
                      <li>"How many leaves do I have?"</li>
                      <li>"Meri leave balance kya hai?"</li>
                      <li>"Show my approved leaves"</li>
                      <li>"Leaves kaise apply karte hain?"</li>
                    </ul>
                  </div>
                  <div className="help-category">
                    <span className="help-cat-label">👤 Profile & Shift</span>
                    <ul>
                      <li>"Show my profile"</li>
                      <li>"What is my shift?"</li>
                      <li>"Meri designation kya hai?"</li>
                      <li>"Which branch am I in?"</li>
                    </ul>
                  </div>
                  <div className="help-category">
                    <span className="help-cat-label">🎉 Holidays</span>
                    <ul>
                      <li>"What are company holidays?"</li>
                      <li>"2026 mein holidays kab hain?"</li>
                      <li>"Is October mein holiday hai?"</li>
                    </ul>
                  </div>
                </div>
                <p className="help-panel-footer">Hindi, English ya Hinglish — kisi bhi language mein poochein! 🇮🇳</p>
              </div>
            )}

            <div className="avatar-action-deck">
              <button
                type="button"
                className={`avatar-mic-trigger ${status.className}`}
                onClick={handleMicClick}
                disabled={voiceLoading || avatarState === "preparing"}
                title={recording ? "Click to finish" : avatarState === "preparing" ? "Generating avatar video..." : "Click to speak"}
              >
                <span className="mic-trigger-icon">
                  {recording ? "⏹" : voiceLoading || avatarState === "preparing" ? "⏳" : "🎙"}
                </span>
                <span className="mic-trigger-text">
                  {recording
                    ? "Finish Speaking"
                    : voiceLoading
                    ? "Thinking..."
                    : avatarState === "preparing"
                    ? "Generating Video..."
                    : avatarVideoUrl || avatarState === "speaking"
                    ? "Ask Another Question"
                    : "Tap to Speak"}
                </span>
              </button>
              <button
                type="button"
                className={`avatar-help-toggle ${showHelp ? "active" : ""}`}
                onClick={() => setShowHelp((prev) => !prev)}
                title="What can I ask?"
              >
                <span>💡</span>
                <span>What Can I Ask?</span>
              </button>
              <span className="avatar-hint-caption">
                {recording
                  ? "Tap Finish Speaking when done."
                  : voiceLoading
                  ? "Generating ElevenLabs voice..."
                  : avatarState === "preparing"
                  ? "Rendering lip-synced avatar video..."
                  : "Hindi, English or Hinglish — any language."}
              </span>
            </div>

            {/* Quick Option Chips */}
            {onSendMessage && quickOptions && quickOptions.length > 0 && (
              <div className="avtar-page-quick-chips">
                {quickOptions.map((opt, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="floating-quick-chip"
                    onClick={() => onSendMessage(opt.query)}
                    disabled={voiceLoading || avatarState === "preparing" || avatarState === "speaking"}
                    title={`Ask: ${opt.query}`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            )}

            {/* Chat text message input */}
            {onSendMessage && (
              <form
                className="avtar-page-text-controls"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (pageInput.trim()) {
                    onSendMessage(pageInput.trim());
                    setPageInput("");
                  }
                }}
              >
                <input
                  type="text"
                  className="floating-input-field"
                  placeholder="Type a message or ask a question..."
                  value={pageInput}
                  onChange={(e) => setPageInput(e.target.value)}
                  disabled={voiceLoading}
                  id="avtar-page-text-input"
                />
                <button
                  type="submit"
                  className="floating-ctrl-btn floating-send-btn"
                  disabled={!pageInput.trim() || voiceLoading || avatarState === "preparing"}
                  title="Send message"
                  aria-label="Send"
                  id="avtar-page-send-btn"
                >
                  ➤
                </button>
              </form>
            )}

          </div>
        </div>
      </div>
    </section>
  );
}

function FloatingAvatarPanel({
  avatarImageUrl,
  avatarVideoUrl,
  avatarState = "idle",
  hasStreamVideo = false,
  recording = false,
  voiceLoading = false,
  audioLevel = 0,
  messages = [],
  inputText = "",
  setInputText,
  onSendText,
  onStopSpeaking,
  isMicMuted = false,
  onToggleMicMute,
  onMicClick,
  onClose,
  onClearChat,
  onRefresh,
  onVideoEnded,
  quickOptions = [],
  API_URL,
}) {
  const videoRef = useRef(null);
  const chatEndRef = useRef(null);
  const panelRef = useRef(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ mouseX: 0, mouseY: 0, startX: 0, startY: 0 });

  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);

  useEffect(() => {
    if (avatarVideoUrl && videoRef.current) {
      videoRef.current.currentTime = 0;
      videoRef.current.volume = 1.0;
      const isLoopLipSync = typeof avatarVideoUrl === "string" && avatarVideoUrl.includes("response_avatar.mp4");
      videoRef.current.muted = isLoopLipSync;
      videoRef.current.loop = isLoopLipSync;
      setIsMuted(isLoopLipSync);

      const p = videoRef.current.play();
      if (p !== undefined) {
        p.catch((err) => {
          console.warn("Floating avatar video autoplay restricted:", err);
          if (videoRef.current) {
            videoRef.current.muted = true;
            setIsMuted(true);
            videoRef.current.play().catch(() => {});
          }
        });
      }
    } else if (!avatarVideoUrl && videoRef.current && hasStreamVideo) {
      avatarStreamService.attachVideo(videoRef.current);
    }
  }, [avatarVideoUrl, hasStreamVideo, avatarState]);

  // First user interaction automatically unmutes greeting video if browser restricted audio autoplay
  useEffect(() => {
    const handleFirstUserInteraction = () => {
      if (videoRef.current && avatarState === "greeting" && isMuted) {
        videoRef.current.muted = false;
        videoRef.current.volume = 1.0;
        setIsMuted(false);
        if (videoRef.current.paused) {
          videoRef.current.play().catch(() => {});
        }
      }
    };
    window.addEventListener("pointerdown", handleFirstUserInteraction, { once: true });
    window.addEventListener("keydown", handleFirstUserInteraction, { once: true });
    return () => {
      window.removeEventListener("pointerdown", handleFirstUserInteraction);
      window.removeEventListener("keydown", handleFirstUserInteraction);
    };
  }, [avatarState, isMuted]);

  // Clamped dragging handlers
  const handleHeaderPointerDown = (e) => {
    if (e.button !== 0 || e.target.closest("button")) {
      return;
    }
    if (window.innerWidth <= 600) return; // touch-safe on small devices

    isDraggingRef.current = true;
    dragStartRef.current = {
      mouseX: e.clientX,
      mouseY: e.clientY,
      startX: dragOffset.x,
      startY: dragOffset.y,
    };

    const handlePointerMove = (moveEvt) => {
      if (!isDraggingRef.current) return;
      const dx = moveEvt.clientX - dragStartRef.current.mouseX;
      const dy = moveEvt.clientY - dragStartRef.current.mouseY;

      let newX = dragStartRef.current.startX + dx;
      let newY = dragStartRef.current.startY + dy;

      if (panelRef.current) {
        const rect = panelRef.current.getBoundingClientRect();
        const minX = -rect.left + 16;
        const maxX = window.innerWidth - rect.right - 16;
        const minY = -rect.top + 16;
        const maxY = window.innerHeight - rect.bottom - 16;

        newX = Math.min(Math.max(newX, minX), maxX);
        newY = Math.min(Math.max(newY, minY), maxY);
      }

      setDragOffset({ x: newX, y: newY });
    };

    const handlePointerUp = () => {
      isDraggingRef.current = false;
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  };

  const handleHeaderDoubleClick = () => {
    setDragOffset({ x: 0, y: 0 });
  };

  const getStatusConfig = () => {
    if (avatarState === "error") {
      return { className: "error" };
    }
    if (recording || avatarState === "listening") {
      return { className: isMicMuted ? "muted" : "listening" };
    }
    if (voiceLoading || avatarState === "thinking") {
      return { className: "thinking" };
    }
    if (avatarState === "preparing") {
      return { className: "preparing" };
    }
    if (avatarState === "greeting") {
      return { className: "greeting" };
    }
    if (avatarVideoUrl || avatarState === "speaking") {
      return { className: "speaking" };
    }
    return { className: "idle" };
  };

  const status = getStatusConfig();

  const defaultQuickOptions = [
    { label: "📅 My attendance", query: "Show my attendance" },
    { label: "🌴 My leave balance", query: "What is my leave balance?" },
    { label: "👤 My profile", query: "Show my complete employee profile details" },
  ];
  const activeChips = quickOptions && quickOptions.length > 0 ? quickOptions : defaultQuickOptions;
  const isSpeakingNow = avatarState === "speaking" || avatarState === "greeting" || Boolean(avatarVideoUrl);

  return (
    <aside
      ref={panelRef}
      className={`floating-avatar-panel ${isMinimized ? "is-minimized" : ""} ${isMaximized ? "is-maximized" : ""}`}
      style={{
        transform: dragOffset.x || dragOffset.y ? `translate(${dragOffset.x}px, ${dragOffset.y}px)` : undefined,
      }}
      aria-label="Floating Talk with Avatar Panel"
      id="compact-floating-avatar-panel"
    >
      {/* 1. Header with Avatar Thumbnail, Title, Drag handle, Actions */}
      <div
        className="floating-panel-header"
        onPointerDown={handleHeaderPointerDown}
        onDoubleClick={handleHeaderDoubleClick}
        title="Drag header to move • Double-click to reset position"
      >
        <div
          className="floating-panel-title-group"
          onClick={() => {
            if (isMinimized) setIsMinimized(false);
          }}
        >
          <CompanyLogo className="floating-panel-logo" />
          <span className="floating-panel-title">Smart HR Avatar</span>
        </div>

        <div className="floating-panel-actions">
          {/* Refresh Session */}
          {!isMinimized && onRefresh && (
            <button
              type="button"
              className="floating-panel-action-btn refresh-btn"
              onClick={onRefresh}
              title="Start fresh conversation"
              aria-label="Refresh conversation"
              id="refresh-floating-avatar-btn"
            >
              🔄
            </button>
          )}

          {/* Minimize / Expand Toggle */}
          <button
            type="button"
            className="floating-panel-action-btn minimize-btn"
            onClick={() => {
              setIsMinimized((prev) => !prev);
              if (isMaximized) setIsMaximized(false);
            }}
            title={isMinimized ? "Restore full widget" : "Minimize to mini bar"}
            aria-label={isMinimized ? "Restore" : "Minimize"}
            id="minimize-floating-avatar-btn"
          >
            {isMinimized ? "🗖" : "🗕"}
          </button>

          {/* Maximize / Normal Toggle (only when not minimized) */}
          {!isMinimized && (
            <button
              type="button"
              className="floating-panel-action-btn maximize-btn"
              onClick={() => setIsMaximized((prev) => !prev)}
              title={isMaximized ? "Restore compact widget" : "Maximize widget"}
              aria-label={isMaximized ? "Restore" : "Maximize"}
              id="maximize-floating-avatar-btn"
            >
              {isMaximized ? "🗗" : "⛶"}
            </button>
          )}

          {/* Clear Chat */}
          {!isMinimized && messages && messages.length > 0 && onClearChat && (
            <button
              type="button"
              className="floating-panel-action-btn"
              onClick={onClearChat}
              title="Clear chat history"
              aria-label="Clear chat"
            >
              🗑️
            </button>
          )}

          {/* Close Panel */}
          <button
            type="button"
            className="floating-panel-action-btn close-btn"
            onClick={onClose}
            title="Close Talk with Avatar"
            aria-label="Close"
            id="close-floating-avatar-btn"
          >
            ✕
          </button>
        </div>
      </div>

      {!isMinimized && (
        <>
          {/* 2. Avatar Stage (WebRTC live stream, response video, or neutral idle avatar image) */}
          <div className="floating-avatar-stage-wrap">
            <div
              className={`avatar-stage ${status.className} ${(hasStreamVideo || avatarVideoUrl) ? "has-video" : ""}`}
              onClick={() => {
                if (videoRef.current && avatarState === "greeting") {
                  videoRef.current.muted = false;
                  videoRef.current.volume = 1.0;
                  setIsMuted(false);
                  if (videoRef.current.paused) {
                    videoRef.current.play().catch(() => {});
                  }
                }
              }}
              title={avatarVideoUrl ? "Click to unmute greeting or replay" : ""}
            >
              <div className="avatar-ambient-halo" />

              {/* Baseline Image Layer - Always rendered behind video to guarantee continuous avatar */}
              {!hasStreamVideo && (
                <img
                  className="avatar-image"
                  src={avatarImageUrl || `${API_URL}/avatar-files/avtar_img.jpg`}
                  alt="Avtar - AI Employee Assistant"
                  style={{
                    position: "absolute",
                    inset: 0,
                    width: "100%",
                    height: "100%",
                    objectFit: "cover",
                    objectPosition: "center top",
                    zIndex: 1,
                  }}
                  onError={(e) => {
                    if (!e.currentTarget.src.endsWith("/avtar_img.jpg")) {
                      e.currentTarget.src = `${API_URL}/avatar-files/avtar_img.jpg`;
                    }
                  }}
                />
              )}

              <video
                ref={videoRef}
                className={`avatar-video ${(hasStreamVideo || avatarVideoUrl) ? "has-video" : "video-hidden"}`}
                src={avatarVideoUrl || undefined}
                poster={avatarImageUrl || `${API_URL}/avatar-files/avtar_img.jpg`}
                autoPlay
                playsInline
                muted={isMuted || (typeof avatarVideoUrl === "string" && avatarVideoUrl.includes("response_avatar.mp4"))}
                loop={Boolean(avatarVideoUrl && typeof avatarVideoUrl === "string" && avatarVideoUrl.includes("response_avatar.mp4"))}
                onEnded={onVideoEnded}
                style={{
                  position: "relative",
                  zIndex: 2,
                  display: (hasStreamVideo || avatarVideoUrl) ? "block" : "none",
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  objectPosition: "center top",
                }}
              />
              {isMuted && (avatarState === "greeting" || (typeof avatarVideoUrl === "string" && !avatarVideoUrl.includes("response_avatar.mp4"))) && (
                <button
                  type="button"
                  className="avatar-unmute-overlay-btn"
                  style={{ zIndex: 3 }}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (videoRef.current) {
                      videoRef.current.muted = false;
                      videoRef.current.currentTime = 0;
                      videoRef.current.play().catch(() => {});
                      setIsMuted(false);
                    }
                  }}
                >
                  🔊 Unmute
                </button>
              )}

              {status.className === "listening" && (
                <div className="avatar-live-indicator listening">
                  <div className="radar-ring ring-1" />
                  <div className="radar-ring ring-2" />
                  <span className="indicator-chip">{isMicMuted ? "Muted 🔇" : "Listening..."}</span>
                </div>
              )}
              {status.className === "thinking" && (
                <div className="avatar-live-indicator thinking">
                  <span className="spinner-orbit" />
                  <span className="indicator-chip">Thinking...</span>
                </div>
              )}
              {status.className === "preparing" && (
                <div className="avatar-live-indicator preparing">
                  <span className="spinner-orbit" />
                  <span className="indicator-chip">Processing Voice & Avatar...</span>
                </div>
              )}
              {status.className === "greeting" && (
                <div className="avatar-live-indicator greeting">
                  <span className="sparkle-icon">✦</span>
                  <span className="indicator-chip">Greeting</span>
                </div>
              )}
              {status.className === "speaking" && (
                <div className="avatar-live-indicator speaking">
                  <div className="soundwave-equalizer">
                    <span className="bar bar-1" />
                    <span className="bar bar-2" />
                    <span className="bar bar-3" />
                    <span className="bar bar-4" />
                    <span className="bar bar-5" />
                  </div>
                  <span className="indicator-chip">Speaking</span>
                </div>
              )}
              {status.className === "error" && (
                <div className="avatar-live-indicator error">
                  <span className="error-icon">⚠️</span>
                  <span className="indicator-chip">Connection issue</span>
                </div>
              )}
            </div>
          </div>

          {/* 3. Real-time visualizer when mic is recording */}
          {recording && (
            <div className="avatar-live-visualizer compact-visualizer">
              <div className="visualizer-bars">
                {[14, 30, 50, 80, 100, 65, 45, 25, 12].map((h, i) => {
                  const sc = isMicMuted ? 4 : Math.max(6, Math.min(22, Math.round((h * (audioLevel + 15)) / 100)));
                  return (
                    <span
                      key={i}
                      className="live-wave-bar"
                      style={{ height: `${sc}px`, opacity: isMicMuted ? 0.35 : 1 }}
                    />
                  );
                })}
              </div>
              <span className="visualizer-caption">
                {isMicMuted ? "Mic is muted" : audioLevel > 10 ? "Speaking detected..." : "Speak now..."}
              </span>
            </div>
          )}

          {/* 4. Chat Messages Transcript (Isolated Floating Avatar Chat history) */}
          <div className="floating-avatar-chat">
            {messages && messages.length > 0 ? (
              <div className="floating-chat-scroll">
                {messages.map((m) => (
                  <div key={m.id} className={`floating-chat-bubble ${m.role} ${m.error ? "error" : ""}`}>
                    <div className="bubble-header">
                      <strong className="bubble-label">
                        {m.role === "user" ? "You" : "Smart HR Avatar"}
                      </strong>
                      {m.time && <span className="bubble-time">{m.time}</span>}
                    </div>
                    <div className="bubble-body">
                      {m.role === "assistant" ? (
                        <FormattedMessage content={m.content} />
                      ) : (
                        <span>{m.content}</span>
                      )}
                    </div>
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
            ) : (
              <div className="floating-chat-empty">
                <div className="empty-avatar-icon">💬</div>
                <strong>Talk with Smart HR Avatar</strong>
                <p>Ask anything about leaves, attendance, shifts, or policies via voice or text.</p>
              </div>
            )}
          </div>

          {/* 5. Quick conversation option chips */}
          <div className="floating-quick-chips">
            {activeChips.map((opt, idx) => (
              <button
                key={idx}
                type="button"
                className="floating-quick-chip"
                onClick={() => onSendText(opt.query)}
                disabled={voiceLoading || avatarState === "preparing" || avatarState === "speaking"}
                title={`Ask: ${opt.query}`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          {/* 6. Controls Deck: Text Input + Stop / Interruption + Mute + Microphone + Send */}
          <form
            className="floating-avatar-controls"
            onSubmit={(e) => {
              e.preventDefault();
              if (inputText.trim()) {
                onSendText(inputText);
              }
            }}
          >
            <input
              type="text"
              className="floating-input-field"
              placeholder="Type message or ask a question..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={voiceLoading}
              id="floating-avatar-text-input"
            />

            {/* Stop / Interruption Control (available when speaking or playing video) */}
            {isSpeakingNow && onStopSpeaking && (
              <button
                type="button"
                className="floating-ctrl-btn floating-stop-btn"
                onClick={onStopSpeaking}
                title="Interrupt / Stop avatar speaking"
                aria-label="Stop avatar"
                id="floating-avatar-stop-btn"
              >
                ⏹ Stop
              </button>
            )}

            {/* Mic Mute / Unmute Toggle (available when recording) */}
            {recording && onToggleMicMute && (
              <button
                type="button"
                className={`floating-ctrl-btn floating-mute-btn ${isMicMuted ? "muted" : ""}`}
                onClick={onToggleMicMute}
                title={isMicMuted ? "Unmute microphone" : "Mute microphone"}
                aria-label={isMicMuted ? "Unmute" : "Mute"}
                id="floating-avatar-mute-btn"
              >
                {isMicMuted ? "🔇" : "🔈"}
              </button>
            )}

            {/* Mic / STT trigger */}
            <button
              type="button"
              className={`floating-ctrl-btn floating-mic-btn ${recording ? "active" : ""}`}
              onClick={onMicClick}
              disabled={voiceLoading || avatarState === "preparing"}
              title={recording ? "Finish speaking" : "Speak with microphone"}
              aria-label={recording ? "Finish speaking" : "Start microphone"}
              id="floating-avatar-mic-btn"
            >
              {recording ? "⏹" : "🎤"}
            </button>

            {/* Send button */}
            <button
              type="submit"
              className="floating-ctrl-btn floating-send-btn"
              disabled={!inputText.trim() || voiceLoading || avatarState === "preparing"}
              title="Send message"
              aria-label="Send"
              id="floating-avatar-send-btn"
            >
              ➤
            </button>
          </form>
        </>
      )}
    </aside>
  );
}



function LoginScreen({
  loginId,
  setLoginId,
  loginLoading,
  loginError,
  serverOnline,
  handleLogin,
}) {
  return (
    <div className="login-page">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <div className="grid-overlay" />

      <div className="login-wrap">
        <div className="login-brand">
          <img
            className="company-logo company-logo-large"
            src="/company-logo.png"
            alt="Company logo"
            onError={(event) => {
              event.currentTarget.hidden = true;
            }}
          />

          <div>
            <strong>Employee AI</strong>

            <span>
              Your workplace assistant
            </span>
          </div>
        </div>

        <div className="login-card">
          <div className="login-orb">
            <img
              className="company-logo company-logo-card"
              src="/company-logo.png"
              alt=""
              onError={(event) => {
                event.currentTarget.hidden = true;
              }}
            />
          </div>

          <div className="eyebrow centered">
            EMPLOYEE PORTAL
          </div>

          <h1>
            Welcome back
          </h1>

          <p className="login-subtitle">
            Sign in to access your workplace
            assistant and employee information.
          </p>

          <label htmlFor="employee-id">
            Employee ID
          </label>

          <div
            className={`login-input ${
              loginError
                ? "input-error"
                : ""
            }`}
          >
            <span>#</span>

            <input
              id="employee-id"
              type="text"
              value={loginId}
              onChange={(e) => {
                setLoginId(
                  e.target.value
                );

                if (loginError) {
                  setLoginError("");
                }
              }}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  !loginLoading
                ) {
                  handleLogin();
                }
              }}
              placeholder="Enter Employee ID"
              autoComplete="username"
              autoFocus
              disabled={loginLoading}
            />
          </div>

          {loginError && (
            <div className="error-box">
              <span>!</span>
              <div>{loginError}</div>
            </div>
          )}

          <button
            className="primary-button login-submit"
            onClick={handleLogin}
            disabled={
              loginLoading ||
              !loginId.trim()
            }
          >
            {loginLoading ? (
              <>
                <span className="button-spinner" />
                Signing in...
              </>
            ) : (
              <>
                Continue
                <span>→</span>
              </>
            )}
          </button>

          <div className="login-status">
            <span
              className={`status-dot ${
                serverOnline
                  ? "online"
                  : ""
              }`}
            />

            {serverOnline
              ? "Server connected"
              : "Connecting to server..."}
          </div>
        </div>

        <div className="login-footer">
          <span>
            Secure employee access
          </span>

          <span>•</span>

          <span>
            Workplace Assistant
          </span>
        </div>
      </div>
    </div>
  );
}

function AssistantView({
  employeeName,
  initial,
  messages,
  message,
  setMessage,
  sendMessage,
  loading,
  recording,
  voiceLoading,
  startSTT,
  startVoiceAI,
  stopRecording,
  generateSpeech,
  copyMessage,
  messagesEndRef,
  audioUrl,
  userAudioUrl,
  voiceCompact,
  quickActions,
}) {
  const empty = messages.length === 0;

  return (
    <section className="assistant-page">
      <div
        className={`assistant-content ${
          empty ? "empty" : ""
        }`}
      >
        {empty ? (
          <div className="assistant-home">
            <div className="assistant-welcome">
              <CompanyLogo className="welcome-icon" />

              <span className="welcome-badge">
                <i className="status-dot online" />
                Ready to help
              </span>

              <h1>
                How can I help you,
                <em>
                  {" "}
                  {employeeName}
                </em>
                ?
              </h1>

              <p>
                Ask me about your employee
                information, attendance,
                leaves, holidays and more.
              </p>
            </div>

            <div className="quick-section">
              <div className="section-label">
                QUICK ACTIONS
              </div>

              <div className="quick-grid">
                {quickActions.map(
                  (item) => (
                    <button
                      key={item.title}
                      className="quick-card"
                      onClick={() =>
                        sendMessage(
                          item.query
                        )
                      }
                    >
                      <span className="quick-icon">
                        {item.icon}
                      </span>

                      <span className="quick-copy">
                        <strong>
                          {item.title}
                        </strong>

                        <small>
                          {item.desc}
                        </small>
                      </span>

                      <b>→</b>
                    </button>
                  )
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="conversation">
            <div className="conversation-head">
              <div>
                <span className="eyebrow">
                  CHAT
                </span>

                <h2>
                  Your conversation
                </h2>
              </div>

              <span className="session-badge">
                <i />
                Active
              </span>
            </div>

            {messages.map((item) => (
              <div
                className={`message-row ${
                  item.role === "user"
                    ? "user"
                    : "assistant"
                }`}
                key={item.id}
              >
                {item.role ===
                  "assistant" && (
                  <Avatar
                    initial="✦"
                    size="message"
                  />
                )}

                <div className="message-group">
                  <div className="message-meta">
                    {item.role === "user"
                      ? employeeName
                      : "Employee AI"}

                    {item.time && (
                      <span>
                        {item.time}
                      </span>
                    )}
                  </div>

                  <div
                    className={`message-bubble ${
                      item.error
                        ? "error"
                        : ""
                    }`}
                  >
                    <FormattedMessage content={item.content} />
                  </div>

                  {item.role ===
                    "assistant" &&
                    !item.error && (
                      <div className="message-actions">
                        <button
                          onClick={() =>
                            generateSpeech(
                              item.content
                            )
                          }
                        >
                          🔊 Listen
                        </button>

                        <button
                          onClick={() =>
                            copyMessage(
                              item.content
                            )
                          }
                        >
                          ⧉ Copy
                        </button>
                      </div>
                    )}
                </div>

                {item.role === "user" && (
                  <Avatar
                    initial={initial}
                    size="message"
                  />
                )}
              </div>
            ))}

            {loading && (
              <div className="message-row assistant">
                <Avatar
                  initial="✦"
                  size="message"
                />

                <div className="message-group">
                  <div className="message-meta">
                    Employee AI
                  </div>

                  <div className="message-bubble thinking-bubble">
                    <span />
                    <span />
                    <span />
                    Thinking...
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {(audioUrl || userAudioUrl) && (
        <div
          className={`voice-results ${
            voiceCompact ? "compact" : ""
          }`}
        >
          {userAudioUrl && (
            <div className="audio-preview user-audio">
              <div className="audio-icon">🎙</div>
              <div className="audio-copy">
                <strong>Your voice</strong>
                <span>Recorded question</span>
              </div>
              <audio controls src={userAudioUrl} />
            </div>
          )}

          <div className="audio-preview assistant-audio">
            <div className="audio-icon">♪</div>
            <div className="audio-copy">
              <strong>AI response</strong>
              <span>Assistant voice</span>
            </div>
            <audio controls src={audioUrl} />
          </div>
        </div>
      )}

      <div className="composer-shell">
        <div className="composer-mode">
          <span
            className={`mode-dot ${
              recording ||
              voiceLoading
                ? "active"
                : ""
            }`}
          />

          {recording
            ? "Listening..."
            : voiceLoading
              ? "Preparing voice..."
              : "Ready"}
        </div>

        <div className="composer">
          <button
            className={`voice-button ${
              recording
                ? "recording"
                : ""
            }`}
            onClick={
              recording
                ? stopRecording
                : () => startVoiceAI("voice_mode")
            }
            disabled={
              loading ||
              voiceLoading
            }
            title="Voice assistant"
          >
            {recording ? "■" : "●"}
          </button>

          <textarea
            value={message}
            onChange={(e) =>
              setMessage(
                e.target.value
              )
            }
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey
              ) {
                e.preventDefault();

                if (
                  message.trim() &&
                  !loading &&
                  !voiceLoading
                ) {
                  sendMessage();
                }
              }
            }}
            placeholder="Message Employee AI..."
            rows={1}
            disabled={
              loading ||
              voiceLoading
            }
          />

          <button
            className="mini-mic"
            onClick={
              recording
                ? stopRecording
                : startSTT
            }
            disabled={
              loading ||
              voiceLoading
            }
            title="Speak to type"
          >
            🎙
          </button>

          <button
            className="send-button"
            onClick={() =>
              sendMessage()
            }
            disabled={
              !message.trim() ||
              loading ||
              voiceLoading
            }
            title="Send message"
          >
            ↑
          </button>
        </div>

        <div className="composer-hint">
          <span>
            Enter to send
          </span>

          <span>•</span>

          <span>
            🎙 Speak to type
          </span>

          <span>•</span>

          <span>
            ● Voice assistant
          </span>
        </div>
      </div>
    </section>
  );
}

function Dashboard({
  employee,
  employeeName,
  initial,
  openAssistant,
  sendMessage,
}) {
  const quickDashboardActions = [
    [
      "◎",
      "My Profile",
      "View",
      "Employee information",
      "Show my complete profile details",
    ],
    [
      "◷",
      "Attendance",
      "Check",
      "Attendance records",
      "Show my attendance",
    ],
    [
      "◆",
      "Leave",
      "View",
      "Leave information",
      "What leaves are available?",
    ],
    [
      "▣",
      "Holidays",
      "View",
      "Company holidays",
      "What are the company holidays in 2026?",
    ],
  ];

  const askAssistant = (query) => {
    openAssistant();

    setTimeout(() => {
      sendMessage(query);
    }, 100);
  };

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            OVERVIEW
          </span>

          <h1>
            Welcome, {employeeName}
          </h1>

          <p>
            Your workplace information,
            all in one place.
          </p>
        </div>
      </div>

      <div className="employee-hero">
        <div className="hero-avatar">
          <Avatar
            initial={initial}
            size="large"
          />
        </div>

        <div className="employee-hero-info">
          <span className="eyebrow">
            EMPLOYEE
          </span>

          <h2>{employeeName}</h2>

          <p>
            {employee.designation ||
              "Employee"}
          </p>

          <small>
            {employee.employee_id}
          </small>
        </div>

        <div className="active-chip">
          <i />
          {employee.status ||
            "Active"}
        </div>
      </div>

      <div className="stats-grid">
        {quickDashboardActions.map(
          ([
            icon,
            title,
            value,
            desc,
            query,
          ]) => (
            <button
              key={title}
              className="stat-card"
              onClick={() =>
                askAssistant(query)
              }
            >
              <span className="stat-icon">
                {icon}
              </span>

              <span className="stat-label">
                {title}
              </span>

              <strong>
                {value}
              </strong>

              <small>
                {desc}
              </small>

              <span className="stat-arrow">
                →
              </span>
            </button>
          )
        )}
      </div>

      <div className="dashboard-columns">
        <section className="panel-card">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">
                QUICK ACCESS
              </span>

              <h2>
                Ask your assistant
              </h2>
            </div>

            <span className="panel-symbol">
              ✦
            </span>
          </div>

          <div className="tool-list">
            {QUICK_ACTIONS.map(
              (item) => (
                <button
                  key={item.title}
                  className="tool-row"
                  onClick={() =>
                    askAssistant(
                      item.query
                    )
                  }
                >
                  <span className="tool-icon">
                    {item.icon}
                  </span>

                  <span>
                    <strong>
                      {item.title}
                    </strong>

                    <small>
                      {item.desc}
                    </small>
                  </span>

                  <b>→</b>
                </button>
              )
            )}
          </div>
        </section>

        <section className="panel-card">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">
                YOUR INFORMATION
              </span>

              <h2>
                Employee details
              </h2>
            </div>

            <span className="panel-symbol">
              ◎
            </span>
          </div>

          <div className="dashboard-details">
            <DetailItem
              label="Designation"
              value={
                employee.designation
              }
            />

            <DetailItem
              label="Branch"
              value={
                employee.branch?.name ||
                employee.branch_name
              }
            />

            <DetailItem
              label="Shift"
              value={
                employee.shift?.name ||
                employee.shift_name
              }
            />

            <DetailItem
              label="Joining Date"
              value={formatDate(
                employee.joining_date
              )}
            />
          </div>
        </section>
      </div>
    </div>
  );
}

function DetailItem({
  label,
  value,
}) {
  return (
    <div className="detail-item">
      <span>{label}</span>

      <strong>
        {value || "Not available"}
      </strong>
    </div>
  );
}

function Profile({
  employee,
  initial,
}) {
  const branchName =
    employee.branch?.name ||
    employee.branch_name;

  const branchCode =
    employee.branch?.code ||
    employee.branch_code;

  const branchAddress =
    employee.branch?.address ||
    employee.branch_address;

  const shiftName =
    employee.shift?.name ||
    employee.shift_name;

  const shiftStart =
    employee.shift?.start_time ||
    employee.shift_start;

  const shiftEnd =
    employee.shift?.end_time ||
    employee.shift_end;

  const shiftTiming =
    shiftStart && shiftEnd
      ? `${shiftStart} - ${shiftEnd}`
      : null;

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            MY PROFILE
          </span>

          <h1>
            Employee information
          </h1>

          <p>
            Your current employee details.
          </p>
        </div>
      </div>

      <section className="profile-card">
        <div className="profile-cover">
          <div className="profile-big-avatar">
            <Avatar
              initial={initial}
              size="xlarge"
            />
          </div>

          <div className="profile-cover-copy">
            <span>
              EMPLOYEE
            </span>

            <h2>
              {employee.name ||
                "Employee"}
            </h2>

            <p>
              {employee.designation ||
                "Not available"}
            </p>

            <small>
              {employee.employee_id}
            </small>
          </div>

          <div className="profile-online">
            <i className="status-dot online" />
            {employee.status ||
              "Active"}
          </div>
        </div>

        <div className="profile-section-title">
          Personal & employment details
        </div>

        <div className="profile-fields">
          <ProfileField
            label="Employee ID"
            value={
              employee.employee_id
            }
          />

          <ProfileField
            label="Full Name"
            value={employee.name}
          />

          <ProfileField
            label="First Name"
            value={
              employee.first_name
            }
          />

          <ProfileField
            label="Last Name"
            value={
              employee.last_name
            }
          />

          <ProfileField
            label="Designation"
            value={
              employee.designation
            }
          />

          <ProfileField
            label="Department ID"
            value={
              employee.department_id
            }
          />

          <ProfileField
            label="Joining Date"
            value={formatDate(
              employee.joining_date
            )}
          />

          <ProfileField
            label="Employment Status"
            value={
              employee.employment_status
            }
          />

          <ProfileField
            label="Status"
            value={employee.status}
          />

          <ProfileField
            label="Job Type"
            value={employee.job_type}
          />

          <ProfileField
            label="Management Level"
            value={
              employee.management_level
            }
          />
        </div>

        <div className="profile-section-title">
          Workplace details
        </div>

        <div className="profile-fields">
          <ProfileField
            label="Branch"
            value={branchName}
          />

          <ProfileField
            label="Branch Code"
            value={branchCode}
          />

          <ProfileField
            label="Branch Address"
            value={branchAddress}
          />

          <ProfileField
            label="Shift"
            value={shiftName}
          />

          <ProfileField
            label="Shift Timing"
            value={shiftTiming}
          />

          <ProfileField
            label="Shift Grace"
            value={
              employee.shift?.grace_minutes != null
                ? `${employee.shift.grace_minutes} minutes`
                : employee.shift_grace_minutes != null
                  ? `${employee.shift_grace_minutes} minutes`
                  : null
            }
          />
        </div>
      </section>
    </div>
  );
}

function ProfileField({
  label,
  value,
}) {
  return (
    <div className="profile-field">
      <span>{label}</span>

      <strong>
        {value !== undefined &&
        value !== null &&
        String(value).trim() !== ""
          ? String(value)
          : "Not available"}
      </strong>
    </div>
  );
}

function Settings({ clearChat }) {
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [voiceMode, setVoiceMode] = useState(true);

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">SETTINGS</span>
          <h1>Preferences</h1>
          <p>Customize your assistant experience.</p>
        </div>
      </div>

      <div className="settings-card">
        <SettingRow title="Voice assistant" desc="Allow voice conversations with your assistant.">
          <Toggle value={voiceMode} onChange={setVoiceMode} />
        </SettingRow>

        <SettingRow title="Automatic voice replies" desc="Play voice responses automatically when available.">
          <Toggle value={autoSpeak} onChange={setAutoSpeak} />
        </SettingRow>

        <SettingRow title="Conversation history" desc="Clear conversations stored on this device.">
          <button className="danger-button" onClick={clearChat}>
            Clear history
          </button>
        </SettingRow>
      </div>
    </div>
  );
}

function SettingRow({
  title,
  desc,
  children,
}) {
  return (
    <div className="setting-row">
      <div>
        <strong>{title}</strong>

        <span>{desc}</span>
      </div>

      {children}
    </div>
  );
}

function Toggle({
  value,
  onChange,
}) {
  return (
    <button
      className={`toggle ${
        value ? "on" : ""
      }`}
      onClick={() =>
        onChange(!value)
      }
      aria-label="Toggle setting"
    >
      <span />
    </button>
  );
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      year: "numeric",
    }
  );
}

export default App;