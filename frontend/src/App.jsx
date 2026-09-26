import { useEffect, useRef, useState } from "react";
import "./App.css";

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
        const heading = line.startsWith("### ");
        const text = heading ? line.slice(4) : line;
        const parts = text.split(/(\*\*[^*]+\*\*)/g);

        return (
          <div
            className={heading ? "formatted-heading" : ""}
            key={`${index}-${line}`}
          >
            {parts.map((part, partIndex) => {
              if (part.startsWith("**") && part.endsWith("**")) {
                return (
                  <strong key={partIndex}>
                    {part.slice(2, -2)}
                  </strong>
                );
              }

              return <span key={partIndex}>{part}</span>;
            })}
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
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [userAudioUrl, setUserAudioUrl] = useState(null);
  const [voiceCompact, setVoiceCompact] = useState(false);
  const [toast, setToast] = useState("");

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
    localStorage.removeItem("employee_id");
    localStorage.removeItem("employee");

    setLoggedIn(false);
    setEmployee(null);
    setMessages([]);
    setMessage("");
    setLoginId("");
    setLoginError("");
    setAudioUrl(null);
    setActivePage("assistant");
    setSidebarOpen(false);
  };

  const sendMessage = async (text = message) => {
    if (!text?.trim() || loading || !employee) {
      return;
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
      const requestStartedAt = Date.now();
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

      const minimumThinkingTime = 800;
      const elapsed = Date.now() - requestStartedAt;
      if (elapsed < minimumThinkingTime) {
        await new Promise((resolve) => {
          setTimeout(resolve, minimumThinkingTime - elapsed);
        });
      }

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

  const startRecorder = async (onBlob) => {
    if (
      recording ||
      loading ||
      voiceLoading
    ) {
      return;
    }

    if (
      !navigator.mediaDevices ||
      !navigator.mediaDevices.getUserMedia
    ) {
      notify(
        "Microphone is not supported in this browser."
      );
      return;
    }

    try {
      const stream =
        await navigator.mediaDevices.getUserMedia({
          audio: true,
        });

      const recorder = new MediaRecorder(stream);
      const chunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      recorder.onerror = (event) => {
        console.error(
          "Recorder error:",
          event
        );

        stream
          .getTracks()
          .forEach((track) => track.stop());

        setRecording(false);
        setMediaRecorder(null);

        notify("Microphone recording failed.");
      };

      recorder.onstop = async () => {
        stream
          .getTracks()
          .forEach((track) => track.stop());

        const blob = new Blob(chunks, {
          type: "audio/webm",
        });

        try {
          await onBlob(blob);
        } catch (error) {
          console.error(error);
        }
      };

      recorder.start();

      setMediaRecorder(recorder);
      setRecording(true);
    } catch (error) {
      console.error(
        "Microphone permission error:",
        error
      );

      notify(
        "Please allow microphone access from your browser."
      );
    }
  };

  const stopRecording = () => {
    if (
      mediaRecorder &&
      mediaRecorder.state !== "inactive"
    ) {
      mediaRecorder.stop();
    }

    setRecording(false);
    setMediaRecorder(null);
  };

  const startSTT = () =>
    startRecorder(async (audioBlob) => {
      setLoading(true);

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
          }
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(
            data?.detail || "Speech recognition failed."
          );
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
        console.error("STT error:", error);

        notify(
          "Sorry, speech recognition failed."
        );
      } finally {
        setLoading(false);
      }
    });

  const generateSpeech = async (text) => {
    if (!text?.trim() || voiceLoading) {
      return;
    }

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
        }
      );

      if (!response.ok) {
        throw new Error("Voice generation failed.");
      }

      const blob = await response.blob();

      if (audioUrl) {
        URL.revokeObjectURL(audioUrl);
      }

      const url = URL.createObjectURL(blob);

      setAudioUrl(url);

      const audio = new Audio(url);

      audio.playbackRate = 0.9;

      await audio.play();
    } catch (error) {
      console.error("TTS error:", error);

      notify(
        "Sorry, voice playback failed."
      );
    } finally {
      setVoiceLoading(false);
    }
  };

  const startVoiceAI = () =>
    startRecorder(async (audioBlob) => {
      setVoiceLoading(true);
      setVoiceCompact(false);

      try {
        if (userAudioUrl) {
          URL.revokeObjectURL(userAudioUrl);
        }

        setUserAudioUrl(URL.createObjectURL(audioBlob));

        const formData = new FormData();

        formData.append(
          "audio",
          audioBlob,
          "employee_voice.webm"
        );

        formData.append(
          "employee_id",
          String(employee.employee_id)
        );

        const response = await fetch(
          `${API_URL}/voice`,
          {
            method: "POST",
            body: formData,
          }
        );

        if (!response.ok) {
          throw new Error(
            "Voice assistant request failed."
          );
        }

        const data = await response.json();
        if (!data?.audio_url) {
          throw new Error("Voice response did not include audio.");
        }

        const url = `${API_URL}${data.audio_url}`;

        setAudioUrl(url);

        const audio = new Audio(url);

        audio.playbackRate = 0.9;

        await audio.play();
        setVoiceCompact(true);

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "user",
            content:
              data.user_text ||
              "Voice message",
            time: new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            voice: true,
          },
          {
            id: Date.now() + 1,
            role: "assistant",
            content:
              data.response ||
              "Your voice request has been processed.",
            time: new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
            voice: true,
          },
        ]);
      } catch (error) {
        console.error(
          "Voice assistant error:",
          error
        );

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            error: true,
            content:
              "Sorry, I couldn't process your voice request.",
            time: new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
          },
        ]);
      } finally {
        setVoiceLoading(false);
        setRecording(false);
        setMediaRecorder(null);
      }
    });

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
          icon="◉"
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

        {activePage === "avtar" && <AvtarPage />}

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
            startVoiceAI={startVoiceAI}
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

function AvtarPage() {
  return (
    <section className="page avtar-page">
      <div className="avtar-card">
        <CompanyLogo className="avtar-logo" />
        <span className="eyebrow">AVTAR EXPERIENCE</span>
        <h1>Talk with Avtar</h1>
        <p>
          Your Avtar conversation experience will appear here. This frontend
          section is ready for the Avtar integration.
        </p>
        <button className="primary-button avtar-button" type="button" disabled>
          Avtar integration coming soon
        </button>
      </div>
    </section>
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
                : startVoiceAI
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

function Settings({
  clearChat,
}) {
  const [autoSpeak, setAutoSpeak] =
    useState(false);

  const [voiceMode, setVoiceMode] =
    useState(true);

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            SETTINGS
          </span>

          <h1>
            Preferences
          </h1>

          <p>
            Customize your assistant
            experience.
          </p>
        </div>
      </div>

      <div className="settings-card">
        <SettingRow
          title="Voice assistant"
          desc="Allow voice conversations with your assistant."
        >
          <Toggle
            value={voiceMode}
            onChange={setVoiceMode}
          />
        </SettingRow>

        <SettingRow
          title="Automatic voice replies"
          desc="Play voice responses automatically when available."
        >
          <Toggle
            value={autoSpeak}
            onChange={setAutoSpeak}
          />
        </SettingRow>

        <SettingRow
          title="Conversation history"
          desc="Clear conversations stored on this device."
        >
          <button
            className="danger-button"
            onClick={clearChat}
          >
            Clear history
          </button>
        </SettingRow>

        <SettingRow
          title="Talking avatar"
          desc="The visual assistant experience will be added in a future update."
        >
          <span className="coming-soon">
            COMING SOON
          </span>
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