import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

const QUICK_ACTIONS = [
  {
    icon: "₹",
    title: "Salary",
    desc: "View salary details",
    query: "Show my salary details",
  },
  {
    icon: "◷",
    title: "Attendance",
    desc: "Check attendance",
    query: "Show my attendance",
  },
  {
    icon: "◆",
    title: "Projects",
    desc: "Explore your projects",
    query: "Show my projects",
  },
  {
    icon: "◎",
    title: "Experience",
    desc: "View experience",
    query: "Show my experience",
  },
];

function App() {
  const [loggedIn, setLoggedIn] = useState(
    Boolean(localStorage.getItem("employee_id")),
  );
  const [employee, setEmployee] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("employee") || "null");
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
    if (!id) return [];
    try {
      return JSON.parse(localStorage.getItem(`chat_${id}`) || "[]");
    } catch {
      return [];
    }
  });

  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceLoading, setVoiceLoading] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);
  const [toast, setToast] = useState("");

  const messagesEndRef = useRef(null);

  const employeeName = employee?.name || "Employee";
  const initial = employeeName.charAt(0).toUpperCase();

  useEffect(() => {
    checkServer();
    const timer = setInterval(checkServer, 15000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    const id = localStorage.getItem("employee_id");
    if (id) localStorage.setItem(`chat_${id}`, JSON.stringify(messages));
  }, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 2500);
    return () => clearTimeout(timer);
  }, [toast]);

  const checkServer = async () => {
    try {
      const response = await fetch(`${API_URL}/`, { method: "GET" });
      setServerOnline(response.ok);
    } catch {
      setServerOnline(false);
    }
  };

  const notify = (text) => setToast(text);

  const handleLogin = async () => {
    if (!loginId.trim()) {
      setLoginError("Enter your Employee ID.");
      return;
    }

    const id = Number(loginId);
    if (!Number.isInteger(id) || id <= 0) {
      setLoginError("Enter a valid Employee ID.");
      return;
    }

    try {
      setLoginLoading(true);
      setLoginError("");

      const response = await fetch(`${API_URL}/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ employee_id: id }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        setLoginError(data.message || "Employee not found.");
        return;
      }

      localStorage.setItem("employee_id", String(data.employee.employee_id));
      localStorage.setItem("employee", JSON.stringify(data.employee));

      setEmployee(data.employee);
      setLoggedIn(true);
      setActivePage("assistant");
      setSidebarOpen(false);
      setServerOnline(true);

      try {
        setMessages(
          JSON.parse(
            localStorage.getItem(`chat_${data.employee.employee_id}`) || "[]",
          ),
        );
      } catch {
        setMessages([]);
      }
    } catch (error) {
      console.error(error);
      setLoginError("Unable to connect with FastAPI. Start the backend first.");
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
    setAudioUrl(null);
    setActivePage("assistant");
    setSidebarOpen(false);
  };

  const sendMessage = async (text = message) => {
    if (!text.trim() || loading || !employee) return;

    const userText = text.trim();
    const now = new Date().toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    setMessages((prev) => [
      ...prev,
      { id: Date.now(), role: "user", content: userText, time: now },
    ]);
    setMessage("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_query: userText,
          employee_id: Number(employee.employee_id),
        }),
      });

      const data = await response.json();

      if (!response.ok) throw new Error(data.detail || "Chat API failed");

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          role: "assistant",
          content:
            data.response || data.answer || "I couldn't generate a response.",
          time: new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          }),
        },
      ]);
      setServerOnline(true);
    } catch (error) {
      console.error(error);
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          role: "assistant",
          error: true,
          content:
            "I couldn't connect to the AI server. Please check that FastAPI is running.",
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
    if (recording || loading || voiceLoading) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        await onBlob(blob);
      };

      recorder.start();
      setMediaRecorder(recorder);
      setRecording(true);
    } catch (error) {
      console.error(error);
      notify("Microphone permission is required.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive")
      mediaRecorder.stop();
    setRecording(false);
    setMediaRecorder(null);
  };

  const startSTT = () =>
    startRecorder(async (audioBlob) => {
      setLoading(true);
      try {
        const formData = new FormData();
        formData.append("audio", audioBlob, "employee_voice.webm");

        const response = await fetch(`${API_URL}/stt`, {
          method: "POST",
          body: formData,
        });

        const data = await response.json();
        if (!response.ok) throw new Error("STT failed");

        setMessage(data.text || "");
        notify("Speech converted to text.");
      } catch (error) {
        console.error(error);
        notify("Speech recognition failed.");
      } finally {
        setLoading(false);
      }
    });

  const generateSpeech = async (text) => {
    if (!text?.trim() || voiceLoading) return;

    try {
      setVoiceLoading(true);

      const response = await fetch(`${API_URL}/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });

      if (!response.ok) throw new Error("TTS failed");

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setAudioUrl(url);

      const audio = new Audio(url);
      audio.playbackRate = 0.9;
      await audio.play();
    } catch (error) {
      console.error(error);
      notify("Text-to-Speech failed.");
    } finally {
      setVoiceLoading(false);
    }
  };

  const startVoiceAI = () =>
    startRecorder(async (audioBlob) => {
      setVoiceLoading(true);

      try {
        const formData = new FormData();
        formData.append("audio", audioBlob, "employee_voice.webm");
        formData.append("employee_id", String(employee.employee_id));

        const response = await fetch(`${API_URL}/voice`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) throw new Error("Voice API failed");

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        setAudioUrl(url);

        const audio = new Audio(url);
        audio.playbackRate = 0.9;
        await audio.play();

        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            content: "Voice response generated.",
            time: new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            }),
          },
        ]);
      } catch (error) {
        console.error(error);
        setMessages((prev) => [
          ...prev,
          {
            id: Date.now(),
            role: "assistant",
            error: true,
            content:
              "Voice AI failed. Please check FastAPI and your AI voice services.",
          },
        ]);
      } finally {
        setVoiceLoading(false);
        setRecording(false);
        setMediaRecorder(null);
      }
    });

  const clearChat = () => {
    if (!employee) return;
    if (!window.confirm("Clear your complete chat history?")) return;

    localStorage.removeItem(`chat_${employee.employee_id}`);
    setMessages([]);
    setMessage("");
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

  if (!loggedIn) {
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
        className={`mobile-overlay ${sidebarOpen ? "show" : ""}`}
        onClick={() => setSidebarOpen(false)}
      />

      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <span>✦</span>
          </div>
          <div>
            <strong>Employee AI</strong>
            <small>Workplace Intelligence</small>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <NavButton
          active={activePage === "assistant"}
          icon="✦"
          label="AI Assistant"
          onClick={() => openPage("assistant")}
        />
        <NavButton
          active={activePage === "dashboard"}
          icon="▦"
          label="Dashboard"
          onClick={() => openPage("dashboard")}
        />
        <NavButton
          active={activePage === "profile"}
          icon="◎"
          label="My Profile"
          onClick={() => openPage("profile")}
        />
        <NavButton
          active={activePage === "settings"}
          icon="⚙"
          label="Settings"
          onClick={() => openPage("settings")}
        />

        <div className="sidebar-feature">
          <div className="feature-icon">AI</div>
          <strong>Built for conversation</strong>
          <span>Chat, voice, RAG and future avatar interaction.</span>
          <div className="feature-tags">
            <span>NLP</span>
            <span>LLM</span>
            <span>RAG</span>
            <span>VOICE</span>
          </div>
        </div>

        <div className="sidebar-bottom">
          <div className="employee-mini">
            <Avatar initial={initial} size="small" />
            <div>
              <strong>{employeeName}</strong>
              <span>ID #{employee.employee_id}</span>
            </div>
            <i className={serverOnline ? "status-dot online" : "status-dot"} />
          </div>
          <button className="logout-button" onClick={logout}>
            ↪ <span>Logout</span>
          </button>
        </div>
      </aside>

      <main className="main-shell">
        <header className="topbar">
          <button className="mobile-menu" onClick={() => setSidebarOpen(true)}>
            ☰
          </button>

          <div>
            <div className="top-title">{pageTitle(activePage)}</div>
            <div className="connection">
              <span className={`status-dot ${serverOnline ? "online" : ""}`} />
              {serverOnline ? "AI system online" : "AI server offline"}
            </div>
          </div>

          <div className="top-actions">
            {activePage === "assistant" && messages.length > 0 && (
              <button className="ghost-button" onClick={clearChat}>
                ⌫ Clear
              </button>
            )}
            <div className="top-user">
              <Avatar initial={initial} />
              <div>
                <strong>{employeeName}</strong>
                <span>#{employee.employee_id}</span>
              </div>
            </div>
          </div>
        </header>

        {activePage === "dashboard" && (
          <Dashboard
            employee={employee}
            employeeName={employeeName}
            initial={initial}
            serverOnline={serverOnline}
            openAssistant={() => openPage("assistant")}
            sendMessage={sendMessage}
          />
        )}

        {activePage === "profile" && (
          <Profile
            employee={employee}
            initial={initial}
            serverOnline={serverOnline}
          />
        )}

        {activePage === "settings" && (
          <Settings
            serverOnline={serverOnline}
            clearChat={clearChat}
            voiceEnabled
            onRefresh={checkServer}
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
            quickActions={QUICK_ACTIONS}
          />
        )}
      </main>

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function pageTitle(page) {
  return {
    assistant: "AI Assistant",
    dashboard: "Dashboard",
    profile: "My Profile",
    settings: "Settings",
  }[page];
}

function NavButton({ active, icon, label, onClick }) {
  return (
    <button
      className={`nav-button ${active ? "active" : ""}`}
      onClick={onClick}
    >
      <span className="nav-icon">{icon}</span>
      <span>{label}</span>
      {active && <b>•</b>}
    </button>
  );
}

function Avatar({ initial, size = "normal" }) {
  return <div className={`avatar ${size}`}>{initial}</div>;
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
          <div className="brand-mark large">
            <span>✦</span>
          </div>
          <div>
            <strong>Employee AI</strong>
            <span>Workplace Intelligence</span>
          </div>
        </div>

        <div className="login-card">
          <div className="login-orb">
            <div className="orb-core">AI</div>
          </div>

          <div className="eyebrow centered">SECURE EMPLOYEE ACCESS</div>
          <h1>Welcome back</h1>
          <p className="login-subtitle">
            Sign in to your personal AI workplace assistant.
          </p>

          <label htmlFor="employee-id">Employee ID</label>
          <div className="login-input">
            <span>#</span>
            <input
              id="employee-id"
              type="number"
              value={loginId}
              onChange={(e) => setLoginId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleLogin()}
              placeholder="Enter employee ID"
              autoFocus
            />
          </div>

          {loginError && <div className="error-box">⚠ {loginError}</div>}

          <button
            className="primary-button login-submit"
            onClick={handleLogin}
            disabled={loginLoading}
          >
            {loginLoading ? (
              "Connecting..."
            ) : (
              <>
                Continue to Employee AI <span>→</span>
              </>
            )}
          </button>

          <div className="login-status">
            <span className={`status-dot ${serverOnline ? "online" : ""}`} />
            {serverOnline ? "FastAPI connected" : "Waiting for AI server"}
          </div>
        </div>

        <div className="login-capabilities">
          <span>✦ NLP</span>
          <span>◈ LLM</span>
          <span>◌ RAG</span>
          <span>◉ VOICE AI</span>
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
  quickActions,
}) {
  const empty = messages.length === 0;

  return (
    <section className="assistant-page">
      <div className={`assistant-content ${empty ? "empty" : ""}`}>
        {empty ? (
          <div className="assistant-home">
            <div className="assistant-hero">
              <div className="avatar-column">
                <div className="avatar-label">
                  <span className="status-dot online" /> LIVE AI AVATAR
                </div>
                <div className="ai-avatar-stage">
                  <div className="ai-ring ring-one" />
                  <div className="ai-ring ring-two" />
                  <div className="ai-face">
                    <span>✦</span>
                  </div>
                  <div className="listening-orbit">AI</div>
                </div>
                <div className="avatar-state">Ready to listen</div>
                <div className="avatar-tools">
                  <span>STT</span>
                  <span>TTS</span>
                  <span>VOICE</span>
                  <span>RAG</span>
                </div>
              </div>

              <div className="hero-panel">
                <div className="ready-pill">
                  <span className="status-dot online" /> AI ASSISTANT READY
                </div>
                <h1>
                  How can I help you, <em>{employeeName}?</em>
                </h1>
                <p className="hero-copy">
                  Your employee assistant for workplace information. Type a
                  question, speak naturally, or use the quick actions below.
                </p>

                <div className="quick-grid">
                  {quickActions.map((item) => (
                    <button
                      key={item.title}
                      className="quick-card"
                      onClick={() => sendMessage(item.query)}
                    >
                      <span className="quick-icon">{item.icon}</span>
                      <span className="quick-copy">
                        <strong>{item.title}</strong>
                        <small>{item.desc}</small>
                      </span>
                      <b>→</b>
                    </button>
                  ))}
                </div>

                <div className="capability-strip">
                  <span>
                    <b>TEXT</b> Ask anything
                  </span>
                  <span>
                    <b>STT</b> Speak to type
                  </span>
                  <span>
                    <b>TTS</b> Listen to reply
                  </span>
                  <span>
                    <b>VOICE</b> Talk to AI
                  </span>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="conversation">
            <div className="conversation-head">
              <div>
                <span className="eyebrow">LIVE CONVERSATION</span>
                <h2>Your AI session</h2>
              </div>
              <span className="session-badge">
                <i /> Active
              </span>
            </div>

            {messages.map((item) => (
              <div
                className={`message-row ${item.role === "user" ? "user" : "assistant"}`}
                key={item.id}
              >
                {item.role === "assistant" && (
                  <Avatar initial="✦" size="message" />
                )}

                <div className="message-group">
                  <div className="message-meta">
                    {item.role === "user" ? employeeName : "Employee AI"}{" "}
                    <span>{item.time}</span>
                  </div>
                  <div
                    className={`message-bubble ${item.error ? "error" : ""}`}
                  >
                    {item.content}
                  </div>

                  {item.role === "assistant" && !item.error && (
                    <div className="message-actions">
                      <button onClick={() => generateSpeech(item.content)}>
                        🔊 Listen
                      </button>
                      <button onClick={() => copyMessage(item.content)}>
                        ⧉ Copy
                      </button>
                    </div>
                  )}
                </div>

                {item.role === "user" && (
                  <Avatar initial={initial} size="message" />
                )}
              </div>
            ))}

            {loading && (
              <div className="message-row assistant">
                <Avatar initial="✦" size="message" />
                <div className="message-group">
                  <div className="message-meta">Employee AI</div>
                  <div className="message-bubble thinking-bubble">
                    <span />
                    <span />
                    <span /> Thinking
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {audioUrl && (
        <div className="audio-preview">
          <div className="audio-icon">♪</div>
          <div>
            <strong>AI Voice Response</strong>
            <span>Generated audio is ready</span>
          </div>
          <audio controls src={audioUrl} />
        </div>
      )}

      <div className="composer-shell">
        <div className="composer-mode">
          <span className="mode-dot" />
          {recording
            ? "Listening..."
            : voiceLoading
              ? "AI is speaking..."
              : "Ready for your request"}
        </div>

        <div className="composer">
          <button
            className={`voice-button ${recording ? "recording" : ""}`}
            onClick={recording ? stopRecording : startVoiceAI}
            disabled={loading || voiceLoading}
            title="Voice AI"
          >
            {recording ? "■" : "●"}
          </button>

          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask your AI assistant anything..."
            rows={1}
            disabled={loading || voiceLoading}
          />

          <button
            className="mini-mic"
            onClick={recording ? stopRecording : startSTT}
            disabled={loading || voiceLoading}
          >
            🎙
          </button>

          <button
            className="send-button"
            onClick={() => sendMessage()}
            disabled={!message.trim() || loading || voiceLoading}
          >
            ↑
          </button>
        </div>

        <div className="composer-hint">
          <span>Enter to send</span>
          <span>•</span>
          <span>🎙 Speech-to-text</span>
          <span>•</span>
          <span>● Voice-to-voice</span>
        </div>
      </div>
    </section>
  );
}

function Dashboard({
  employee,
  employeeName,
  initial,
  serverOnline,
  openAssistant,
  sendMessage,
}) {
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">EMPLOYEE OVERVIEW</span>
          <h1>Good to see you, {employeeName}</h1>
          <p>Your personal AI workplace command center.</p>
        </div>
        <div className="system-pill">
          <span className={`status-dot ${serverOnline ? "online" : ""}`} />{" "}
          {serverOnline ? "Systems operational" : "Server offline"}
        </div>
      </div>

      <div className="employee-hero">
        <div className="hero-avatar">
          <Avatar initial={initial} size="large" />
        </div>
        <div className="employee-hero-info">
          <span className="eyebrow">EMPLOYEE</span>
          <h2>{employeeName}</h2>
          <p>
            {employee.designation || "Employee"} <i>•</i>{" "}
            {employee.department || "Organization"}
          </p>
          <small>Employee ID #{employee.employee_id}</small>
        </div>
        <div className="active-chip">
          <i /> Active employee
        </div>
      </div>

      <div className="stats-grid">
        {[
          ["₹", "Salary", "Ask AI", "Latest salary information"],
          ["◷", "Attendance", "Ask AI", "Attendance records"],
          ["◆", "Projects", "Ask AI", "Assigned projects"],
          ["◎", "Experience", "Ask AI", "Work experience"],
        ].map(([icon, title, value, desc]) => (
          <button
            key={title}
            className="stat-card"
            onClick={() => {
              openAssistant();
              setTimeout(
                () => sendMessage(`Show my ${title.toLowerCase()} details`),
                50,
              );
            }}
          >
            <span className="stat-icon">{icon}</span>
            <span className="stat-label">{title}</span>
            <strong>{value}</strong>
            <small>{desc}</small>
          </button>
        ))}
      </div>

      <div className="dashboard-columns">
        <section className="panel-card">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">AI TOOLS</span>
              <h2>Ask your assistant</h2>
            </div>
            <span className="panel-symbol">✦</span>
          </div>
          <div className="tool-list">
            {QUICK_ACTIONS.map((item) => (
              <button
                key={item.title}
                className="tool-row"
                onClick={() => {
                  openAssistant();
                  setTimeout(() => sendMessage(item.query), 50);
                }}
              >
                <span className="tool-icon">{item.icon}</span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.desc}</small>
                </span>
                <b>→</b>
              </button>
            ))}
          </div>
        </section>

        <section className="panel-card">
          <div className="panel-heading">
            <div>
              <span className="eyebrow">AI STACK</span>
              <h2>Built for the future</h2>
            </div>
            <span className="panel-symbol">⚡</span>
          </div>
          <div className="capability-grid">
            {[
              ["NLP", "Intent understanding", "✓"],
              ["LLM", "Natural responses", "✓"],
              ["RAG", "Knowledge retrieval", "✓"],
              ["VOICE", "STT • TTS • Voice", "✓"],
              ["AVATAR", "Talking AI layer", "Soon"],
              ["TOOLS", "Employee data", "✓"],
            ].map(([name, desc, status]) => (
              <div className="capability" key={name}>
                <span className="cap-dot" />
                <div>
                  <strong>{name}</strong>
                  <small>{desc}</small>
                </div>
                <em>{status}</em>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function Profile({ employee, initial, serverOnline }) {
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">MY PROFILE</span>
          <h1>Employee profile</h1>
          <p>Your organization information in one place.</p>
        </div>
      </div>

      <section className="profile-card">
        <div className="profile-cover">
          <div className="profile-big-avatar">
            <Avatar initial={initial} size="xlarge" />
          </div>
          <div className="profile-cover-copy">
            <span>ACTIVE EMPLOYEE</span>
            <h2>{employee.name || "Employee"}</h2>
            <p>
              {employee.designation || "Employee"} •{" "}
              {employee.department || "Organization"}
            </p>
          </div>
          <div className="profile-online">
            <i className={`status-dot ${serverOnline ? "online" : ""}`} /> AI
            connected
          </div>
        </div>

        <div className="profile-fields">
          {[
            ["Employee ID", `#${employee.employee_id}`],
            ["Department", employee.department],
            ["Designation", employee.designation],
            ["Joining Date", employee.joining_date],
          ].map(([label, value]) => (
            <div className="profile-field" key={label}>
              <span>{label}</span>
              <strong>{value || "—"}</strong>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Settings({ serverOnline, clearChat, voiceEnabled, onRefresh }) {
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [voiceMode, setVoiceMode] = useState(true);

  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PREFERENCES</span>
          <h1>Assistant settings</h1>
          <p>
            Control your AI experience. Avatar controls can be added here later.
          </p>
        </div>
      </div>

      <div className="settings-card">
        <SettingRow title="AI server" desc="FastAPI backend connection status.">
          <div className="setting-status">
            <i className={`status-dot ${serverOnline ? "online" : ""}`} />{" "}
            {serverOnline ? "Connected" : "Disconnected"}
          </div>
        </SettingRow>

        <SettingRow
          title="Voice AI"
          desc="Speech-to-text, text-to-speech and voice-to-voice."
        >
          <Toggle value={voiceMode} onChange={setVoiceMode} />
        </SettingRow>

        <SettingRow
          title="Auto speak responses"
          desc="Automatically play AI responses when audio is available."
        >
          <Toggle value={autoSpeak} onChange={setAutoSpeak} />
        </SettingRow>

        <SettingRow
          title="Chat history"
          desc="Conversation history is stored locally for this employee."
        >
          <button className="danger-button" onClick={clearChat}>
            Clear history
          </button>
        </SettingRow>

        <SettingRow
          title="Backend health"
          desc="Check the FastAPI server again."
        >
          <button className="outline-button" onClick={onRefresh}>
            Refresh status
          </button>
        </SettingRow>

        <SettingRow
          title="Future avatar"
          desc="Talking avatar, facial reactions and lip-sync will plug into this layer."
        >
          <span className="coming-soon">COMING SOON</span>
        </SettingRow>
      </div>
    </div>
  );
}

function SettingRow({ title, desc, children }) {
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

function Toggle({ value, onChange }) {
  return (
    <button
      className={`toggle ${value ? "on" : ""}`}
      onClick={() => onChange(!value)}
      aria-label="Toggle setting"
    >
      <span />
    </button>
  );
}

export default App;
