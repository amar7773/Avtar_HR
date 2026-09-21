import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [loggedIn, setLoggedIn] = useState(
    Boolean(localStorage.getItem("employee_id")),
  );

  const [employee, setEmployee] = useState(() => {
    try {
      const saved = localStorage.getItem("employee");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [loginId, setLoginId] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  const [activePage, setActivePage] = useState("assistant");

  const [message, setMessage] = useState("");

  const [messages, setMessages] = useState(() => {
    const id = localStorage.getItem("employee_id");

    if (!id) return [];

    try {
      const saved = localStorage.getItem(`chat_${id}`);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [loading, setLoading] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceLoading, setVoiceLoading] = useState(false);

  const [mediaRecorder, setMediaRecorder] = useState(null);
  const [audioUrl, setAudioUrl] = useState(null);

  const [serverOnline, setServerOnline] = useState(false);

  const messagesEndRef = useRef(null);

  /* =====================================================
     SERVER HEALTH
  ===================================================== */

  useEffect(() => {
    checkServer();
  }, []);

  const checkServer = async () => {
    try {
      const response = await fetch(`${API_URL}/`, {
        method: "GET",
      });

      setServerOnline(response.ok);
    } catch {
      setServerOnline(false);
    }
  };

  /* =====================================================
     SAVE CHAT
  ===================================================== */

  useEffect(() => {
    const id = localStorage.getItem("employee_id");

    if (!id) return;

    localStorage.setItem(`chat_${id}`, JSON.stringify(messages));
  }, [messages]);

  /* =====================================================
     AUTO SCROLL
  ===================================================== */

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  /* =====================================================
     LOGIN
  ===================================================== */

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
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          employee_id: id,
        }),
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

      const saved = localStorage.getItem(`chat_${data.employee.employee_id}`);

      try {
        setMessages(saved ? JSON.parse(saved) : []);
      } catch {
        setMessages([]);
      }

      setServerOnline(true);
    } catch (error) {
      console.error(error);

      setLoginError("Unable to connect with FastAPI. Start the backend first.");
    } finally {
      setLoginLoading(false);
    }
  };

  /* =====================================================
     LOGOUT
  ===================================================== */

  const logout = () => {
    localStorage.removeItem("employee_id");
    localStorage.removeItem("employee");

    setLoggedIn(false);
    setEmployee(null);
    setMessages([]);
    setMessage("");
    setAudioUrl(null);
    setActivePage("assistant");
  };

  /* =====================================================
     CHAT
  ===================================================== */

  const sendMessage = async (text = message) => {
    if (!text.trim() || loading || !employee) return;

    const userText = text.trim();

    const userMsg = {
      id: Date.now(),
      role: "user",
      content: userText,
      time: new Date().toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      }),
    };

    setMessages((prev) => [...prev, userMsg]);
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
          employee_id: Number(employee.employee_id),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Chat API failed");
      }

      const assistantMsg = {
        id: Date.now() + 1,
        role: "assistant",
        content:
          data.response || data.answer || "I couldn't generate a response.",
        time: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (error) {
      console.error(error);

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          role: "assistant",
          content:
            "I couldn't connect to the AI server. Please check that FastAPI is running.",
          error: true,
        },
      ]);

      setServerOnline(false);
    } finally {
      setLoading(false);
    }
  };

  /* =====================================================
     STT
  ===================================================== */

  const startSTT = async () => {
    if (recording || loading || voiceLoading) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      const recorder = new MediaRecorder(stream);
      const chunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());

        const blob = new Blob(chunks, {
          type: "audio/webm",
        });

        await sendAudioToSTT(blob);
      };

      recorder.start();

      setMediaRecorder(recorder);
      setRecording(true);
    } catch (error) {
      console.error(error);
      alert("Please allow microphone permission.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }

    setRecording(false);
    setMediaRecorder(null);
  };

  const sendAudioToSTT = async (audioBlob) => {
    setLoading(true);

    try {
      const formData = new FormData();

      formData.append("audio", audioBlob, "employee_voice.webm");

      const response = await fetch(`${API_URL}/stt`, {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error("STT failed");
      }

      setMessage(data.text || "");
    } catch (error) {
      console.error(error);

      alert("Speech recognition failed.");
    } finally {
      setLoading(false);
    }
  };

  /* =====================================================
     TTS
  ===================================================== */

  const generateSpeech = async (text) => {
    if (!text?.trim() || voiceLoading) return;

    try {
      setVoiceLoading(true);

      const response = await fetch(`${API_URL}/tts`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          text,
        }),
      });

      if (!response.ok) {
        throw new Error("TTS failed");
      }

      const blob = await response.blob();

      const url = URL.createObjectURL(blob);

      setAudioUrl(url);

      const audio = new Audio(url);

      /*
        Slow playback slightly.
        Backend voice itself should also be configured
        with a suitable speaking speed.
      */
      audio.playbackRate = 0.9;

      await audio.play();
    } catch (error) {
      console.error(error);
      alert("Text-to-Speech failed.");
    } finally {
      setVoiceLoading(false);
    }
  };

  /* =====================================================
     FULL VOICE AI
  ===================================================== */

  const startVoiceAI = async () => {
    if (recording || voiceLoading) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      const recorder = new MediaRecorder(stream);
      const chunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunks.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());

        const blob = new Blob(chunks, {
          type: "audio/webm",
        });

        await sendVoiceToAI(blob);
      };

      recorder.start();

      setMediaRecorder(recorder);
      setRecording(true);
    } catch (error) {
      console.error(error);
      alert("Microphone permission required.");
    }
  };

  const sendVoiceToAI = async (audioBlob) => {
    setVoiceLoading(true);

    try {
      const formData = new FormData();

      formData.append("audio", audioBlob, "employee_voice.webm");

      formData.append("employee_id", String(employee.employee_id));

      const response = await fetch(`${API_URL}/voice`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Voice API failed");
      }

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
  };

  /* =====================================================
     CLEAR CHAT
  ===================================================== */

  const clearChat = () => {
    if (!employee) return;

    if (!window.confirm("Clear your complete chat history?")) {
      return;
    }

    localStorage.removeItem(`chat_${employee.employee_id}`);

    setMessages([]);
    setMessage("");
  };

  /* =====================================================
     COPY
  ===================================================== */

  const copyMessage = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch (error) {
      console.error(error);
    }
  };

  /* =====================================================
     QUICK QUESTIONS
  ===================================================== */

  const quickQuestions = [
    {
      icon: "₹",
      title: "Salary",
      description: "Check your salary",
      query: "Show my salary details",
    },
    {
      icon: "◷",
      title: "Attendance",
      description: "View attendance",
      query: "Show my attendance",
    },
    {
      icon: "◆",
      title: "Projects",
      description: "View your projects",
      query: "Show my projects",
    },
    {
      icon: "◎",
      title: "Experience",
      description: "View work experience",
      query: "Show my experience",
    },
  ];

  /* =====================================================
     LOGIN SCREEN
  ===================================================== */

  if (!loggedIn) {
    return (
      <div className="login-page">
        <div className="login-glow glow-one"></div>
        <div className="login-glow glow-two"></div>

        <div className="login-box">
          <div className="login-brand">
            <div className="logo-orb">✦</div>

            <div>
              <h1>Employee AI</h1>
              <p>Intelligent Workplace Assistant</p>
            </div>
          </div>

          <div className="login-card">
            <div className="login-ai">
              <span>AI</span>
            </div>

            <h2>Welcome back</h2>

            <p className="login-subtitle">Sign in with your employee ID</p>

            <label>Employee ID</label>

            <div className="login-input">
              <span>#</span>

              <input
                type="number"
                value={loginId}
                onChange={(e) => {
                  setLoginId(e.target.value);
                  setLoginError("");
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleLogin();
                  }
                }}
                placeholder="e.g. 1010"
              />
            </div>

            {loginError && <div className="login-error">⚠ {loginError}</div>}

            <button
              className="login-submit"
              onClick={handleLogin}
              disabled={loginLoading}
            >
              {loginLoading ? "Connecting..." : "Enter Employee AI →"}
            </button>

            <div className="login-status">
              <span className={serverOnline ? "online" : "offline"}></span>

              {serverOnline ? "AI server connected" : "Waiting for AI server"}
            </div>
          </div>

          <p className="login-footer">NLP • LLM • RAG • Voice AI</p>
        </div>
      </div>
    );
  }

  const employeeName = employee?.name || "Employee";

  const initial = employeeName.charAt(0).toUpperCase();

  /* =====================================================
     DASHBOARD
  ===================================================== */

  const Dashboard = () => (
    <div className="dashboard">
      <div className="page-heading">
        <div>
          <span className="eyebrow">EMPLOYEE OVERVIEW</span>

          <h2>Welcome, {employeeName}</h2>

          <p>Your personal AI workplace command center.</p>
        </div>

        <div className="server-pill">
          <span className={serverOnline ? "online" : "offline"}></span>

          {serverOnline ? "Systems operational" : "Server offline"}
        </div>
      </div>

      <div className="profile-hero">
        <div className="big-avatar">{initial}</div>

        <div className="profile-main">
          <h3>{employeeName}</h3>

          <p>
            {employee.designation || "Employee"} •{" "}
            {employee.department || "Organization"}
          </p>

          <span>Employee ID #{employee.employee_id}</span>
        </div>

        <div className="profile-chip">
          <span></span>
          Active Employee
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat-card purple">
          <div className="stat-icon">₹</div>

          <span>Salary</span>

          <strong>Ask AI</strong>

          <small>Get latest salary details</small>
        </div>

        <div className="stat-card blue">
          <div className="stat-icon">◷</div>

          <span>Attendance</span>

          <strong>Ask AI</strong>

          <small>Check attendance records</small>
        </div>

        <div className="stat-card green">
          <div className="stat-icon">◆</div>

          <span>Projects</span>

          <strong>Ask AI</strong>

          <small>Explore assigned projects</small>
        </div>

        <div className="stat-card orange">
          <div className="stat-icon">◎</div>

          <span>Experience</span>

          <strong>Ask AI</strong>

          <small>View your experience</small>
        </div>
      </div>

      <div className="dashboard-grid">
        <div className="panel">
          <div className="panel-header">
            <div>
              <span>AI TOOLS</span>
              <h3>Ask your assistant</h3>
            </div>

            <span className="panel-icon">✦</span>
          </div>

          <div className="tool-list">
            {quickQuestions.map((item) => (
              <button
                key={item.title}
                onClick={() => {
                  setActivePage("assistant");
                  setTimeout(() => {
                    sendMessage(item.query);
                  }, 50);
                }}
                className="tool-item"
              >
                <div>{item.icon}</div>

                <span>
                  <strong>{item.title}</strong>
                  <small>{item.description}</small>
                </span>

                <b>→</b>
              </button>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <div>
              <span>CAPABILITIES</span>
              <h3>AI Services</h3>
            </div>

            <span className="panel-icon">⚡</span>
          </div>

          <div className="capability-list">
            <div>
              <span className="cap-dot green"></span>
              <strong>NLP</strong>
              <small>Intent understanding</small>
            </div>

            <div>
              <span className="cap-dot purple"></span>
              <strong>LLM</strong>
              <small>Natural responses</small>
            </div>

            <div>
              <span className="cap-dot blue"></span>
              <strong>RAG</strong>
              <small>Knowledge retrieval</small>
            </div>

            <div>
              <span className="cap-dot orange"></span>
              <strong>Voice AI</strong>
              <small>Speech interaction</small>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  /* =====================================================
     PROFILE
  ===================================================== */

  const Profile = () => (
    <div className="dashboard">
      <div className="page-heading">
        <div>
          <span className="eyebrow">MY PROFILE</span>

          <h2>Employee Profile</h2>

          <p>Your employee information.</p>
        </div>
      </div>

      <div className="profile-detail">
        <div className="profile-detail-avatar">{initial}</div>

        <div className="profile-fields">
          <div>
            <span>Name</span>
            <strong>{employee.name || "—"}</strong>
          </div>

          <div>
            <span>Employee ID</span>
            <strong>#{employee.employee_id}</strong>
          </div>

          <div>
            <span>Department</span>
            <strong>{employee.department || "—"}</strong>
          </div>

          <div>
            <span>Designation</span>
            <strong>{employee.designation || "—"}</strong>
          </div>

          <div>
            <span>Joining Date</span>
            <strong>{employee.joining_date || "—"}</strong>
          </div>
        </div>
      </div>
    </div>
  );

  /* =====================================================
     SETTINGS
  ===================================================== */

  const Settings = () => (
    <div className="dashboard">
      <div className="page-heading">
        <div>
          <span className="eyebrow">SETTINGS</span>

          <h2>Assistant Settings</h2>

          <p>Manage your local assistant experience.</p>
        </div>
      </div>

      <div className="settings-panel">
        <div className="setting-row">
          <div>
            <strong>Chat History</strong>
            <span>Conversations are saved locally for this employee.</span>
          </div>

          <button onClick={clearChat} className="danger-button">
            Clear history
          </button>
        </div>

        <div className="setting-row">
          <div>
            <strong>AI Server</strong>
            <span>FastAPI backend connection status.</span>
          </div>

          <span className="setting-status">
            <i className={serverOnline ? "online" : "offline"}></i>

            {serverOnline ? "Connected" : "Disconnected"}
          </span>
        </div>

        <div className="setting-row">
          <div>
            <strong>Voice AI</strong>
            <span>Speech-to-text, text-to-speech and voice-to-voice.</span>
          </div>

          <span className="setting-status active">Enabled</span>
        </div>
      </div>
    </div>
  );

  /* =====================================================
     MAIN UI
  ===================================================== */

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">✦</div>

          <div>
            <strong>Employee AI</strong>
            <span>Workplace Assistant</span>
          </div>
        </div>

        <div className="workspace-label">WORKSPACE</div>

        <button
          className={activePage === "assistant" ? "nav active" : "nav"}
          onClick={() => setActivePage("assistant")}
        >
          <span>✦</span>
          AI Assistant
        </button>

        <button
          className={activePage === "dashboard" ? "nav active" : "nav"}
          onClick={() => setActivePage("dashboard")}
        >
          <span>▦</span>
          Dashboard
        </button>

        <button
          className={activePage === "profile" ? "nav active" : "nav"}
          onClick={() => setActivePage("profile")}
        >
          <span>◎</span>
          My Profile
        </button>

        <button
          className={activePage === "settings" ? "nav active" : "nav"}
          onClick={() => setActivePage("settings")}
        >
          <span>⚙</span>
          Settings
        </button>

        <div className="sidebar-ai-card">
          <div>✦</div>

          <strong>AI Assistant</strong>

          <span>Ask about salary, attendance & more.</span>
        </div>

        <div className="sidebar-bottom">
          <div className="employee-mini">
            <div className="mini-avatar">{initial}</div>

            <div>
              <strong>{employeeName}</strong>

              <span>ID #{employee.employee_id}</span>
            </div>

            <i></i>
          </div>

          <button className="logout" onClick={logout}>
            ↪ Logout
          </button>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div className="mobile-brand">✦</div>

          <div>
            <h1>
              {activePage === "assistant"
                ? "AI Assistant"
                : activePage === "dashboard"
                  ? "Dashboard"
                  : activePage === "profile"
                    ? "My Profile"
                    : "Settings"}
            </h1>

            <div className="connection">
              <span className={serverOnline ? "online" : "offline"}></span>

              {serverOnline ? "AI system online" : "AI server offline"}
            </div>
          </div>

          <div className="top-user">
            <div className="top-avatar">{initial}</div>

            <div>
              <strong>{employeeName}</strong>
              <span>#{employee.employee_id}</span>
            </div>
          </div>
        </header>

        {activePage === "dashboard" && <Dashboard />}

        {activePage === "profile" && <Profile />}

        {activePage === "settings" && <Settings />}

        {activePage === "assistant" && (
          <>
            <section className="chat-area">
              {messages.length === 0 ? (
                <div className="assistant-home">
                  <div className="hero-orb">
                    <div>✦</div>
                  </div>

                  <div className="ready">
                    <span></span>
                    AI ASSISTANT READY
                  </div>

                  <h2>
                    What can I help you
                    <br />
                    <em>{employeeName}?</em>
                  </h2>

                  <p>
                    Ask questions about your employee information or use your
                    voice.
                  </p>

                  <div className="quick-grid">
                    {quickQuestions.map((item) => (
                      <button
                        key={item.title}
                        onClick={() => sendMessage(item.query)}
                      >
                        <div className="quick-symbol">{item.icon}</div>

                        <div>
                          <strong>{item.title}</strong>

                          <span>{item.description}</span>
                        </div>

                        <b>→</b>
                      </button>
                    ))}
                  </div>

                  <div className="ai-stack">
                    <span>NLP</span>
                    <span>LLM</span>
                    <span>RAG</span>
                    <span>STT</span>
                    <span>TTS</span>
                    <span>VOICE AI</span>
                  </div>
                </div>
              ) : (
                <div className="messages">
                  <div className="conversation-title">
                    <span></span>
                    Your conversation
                  </div>

                  {messages.map((item) => (
                    <div
                      key={item.id}
                      className={
                        item.role === "user"
                          ? "message user-message"
                          : "message ai-message"
                      }
                    >
                      {item.role === "assistant" && (
                        <div className="message-avatar">✦</div>
                      )}

                      <div className="message-body">
                        <small>
                          {item.role === "user" ? employeeName : "Employee AI"}
                        </small>

                        <div className={item.error ? "bubble error" : "bubble"}>
                          {item.content}
                        </div>

                        <div className="message-actions">
                          {item.role === "assistant" && (
                            <>
                              <button
                                onClick={() => generateSpeech(item.content)}
                              >
                                🔊 Listen
                              </button>

                              <button onClick={() => copyMessage(item.content)}>
                                ⧉ Copy
                              </button>
                            </>
                          )}

                          <span>{item.time}</span>
                        </div>
                      </div>

                      {item.role === "user" && (
                        <div className="user-avatar">{initial}</div>
                      )}
                    </div>
                  ))}

                  {loading && (
                    <div className="message ai-message">
                      <div className="message-avatar">✦</div>

                      <div className="message-body">
                        <small>Employee AI</small>

                        <div className="bubble">
                          <div className="thinking">
                            <i></i>
                            <i></i>
                            <i></i>
                            <span>Thinking...</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef}></div>
                </div>
              )}
            </section>

            {audioUrl && (
              <div className="audio-bar">
                <span>🔊</span>

                <div>
                  <strong>AI Voice</strong>

                  <small>Audio response ready</small>
                </div>

                <audio controls src={audioUrl} />

                <button onClick={() => setAudioUrl(null)}>×</button>
              </div>
            )}

            <section className="composer">
              <div
                className={
                  recording ? "composer-box recording" : "composer-box"
                }
              >
                <textarea
                  value={message}
                  onChange={(e) => setMessage(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder={
                    recording
                      ? "Listening to you..."
                      : "Ask anything about your employee data..."
                  }
                  disabled={recording}
                />

                <div className="composer-actions">
                  <button
                    className={recording ? "mic active" : "mic"}
                    onClick={recording ? stopRecording : startSTT}
                    title="Speech to Text"
                  >
                    {recording ? "■" : "🎙"}
                  </button>

                  <button
                    className={
                      voiceLoading ? "voice-button active" : "voice-button"
                    }
                    onClick={recording ? stopRecording : startVoiceAI}
                    disabled={voiceLoading}
                    title="Voice to Voice"
                  >
                    {voiceLoading ? "..." : "✦"}
                  </button>

                  <button
                    className="send"
                    onClick={() => sendMessage()}
                    disabled={!message.trim() || loading || recording}
                  >
                    ↑
                  </button>
                </div>
              </div>

              <div className="composer-hint">
                <span>
                  <b>Enter</b> send
                </span>

                <span>🎙 Speech to Text</span>

                <span>✦ Voice to Voice</span>

                <span>🔊 Text to Speech</span>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}

export default App;
