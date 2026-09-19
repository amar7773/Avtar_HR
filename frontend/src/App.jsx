import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  // =========================
  // LOGIN
  // =========================

  const [loggedIn, setLoggedIn] = useState(() => {
    return Boolean(localStorage.getItem("employee_id"));
  });

  const [employee, setEmployee] = useState(() => {
    const saved = localStorage.getItem("employee");
    return saved ? JSON.parse(saved) : null;
  });

  const [loginId, setLoginId] = useState("");
  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  // =========================
  // CHAT
  // =========================

  const [message, setMessage] = useState("");

  const [messages, setMessages] = useState(() => {
    const id = localStorage.getItem("employee_id");

    if (!id) return [];

    const saved = localStorage.getItem(`chat_${id}`);

    try {
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  const [loading, setLoading] = useState(false);

  // =========================
  // VOICE
  // =========================

  const [recording, setRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);

  const [audioUrl, setAudioUrl] = useState(null);
  const [voiceLoading, setVoiceLoading] = useState(false);

  const messagesEndRef = useRef(null);

  // =========================
  // SAVE CHAT
  // =========================

  useEffect(() => {
    const id = localStorage.getItem("employee_id");

    if (!id) return;

    localStorage.setItem(`chat_${id}`, JSON.stringify(messages));
  }, [messages]);

  // =========================
  // AUTO SCROLL
  // =========================

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  // =========================
  // LOGIN
  // =========================

  const handleLogin = async () => {
    if (!loginId.trim()) {
      setLoginError("Please enter your Employee ID.");
      return;
    }

    const id = Number(loginId);

    if (!Number.isInteger(id) || id <= 0) {
      setLoginError("Please enter a valid Employee ID.");
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
        setLoginError(data.message || "Employee ID not found.");
        return;
      }

      localStorage.setItem("employee_id", String(data.employee.employee_id));

      localStorage.setItem("employee", JSON.stringify(data.employee));

      setEmployee(data.employee);
      setLoggedIn(true);

      const savedChat = localStorage.getItem(
        `chat_${data.employee.employee_id}`,
      );

      try {
        setMessages(savedChat ? JSON.parse(savedChat) : []);
      } catch {
        setMessages([]);
      }
    } catch (error) {
      console.error(error);
      setLoginError("Unable to connect to server. Please start FastAPI.");
    } finally {
      setLoginLoading(false);
    }
  };

  // =========================
  // LOGOUT
  // =========================

  const logout = () => {
    localStorage.removeItem("employee_id");
    localStorage.removeItem("employee");

    setLoggedIn(false);
    setEmployee(null);
    setMessages([]);
    setMessage("");
    setAudioUrl(null);
  };

  // =========================
  // QUICK ACTIONS
  // =========================

  const quickActions = [
    {
      icon: "₹",
      title: "Salary",
      text: "Show my salary details",
      description: "View your salary information",
    },
    {
      icon: "◷",
      title: "Attendance",
      text: "Show my attendance",
      description: "Check your attendance",
    },
    {
      icon: "◆",
      title: "Projects",
      text: "Show my projects",
      description: "View project information",
    },
    {
      icon: "◎",
      title: "Experience",
      text: "Show my experience",
      description: "View your work experience",
    },
  ];

  // =========================
  // CHAT API
  // =========================

  const sendMessage = async (text = message) => {
    if (!text.trim() || loading || !employee) return;

    const userMessage = text.trim();

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: userMessage,
        time: new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
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
          user_query: userMessage,
          employee_id: Number(employee.employee_id),
        }),
      });

      if (!response.ok) {
        throw new Error("Chat API failed");
      }

      const data = await response.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.response || "I could not generate a response.",
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
          role: "assistant",
          content:
            "I couldn't connect to the AI server. Please make sure FastAPI is running.",
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // STT
  // =========================

  const startRecording = async () => {
    if (recording || voiceLoading) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      const recorder = new MediaRecorder(stream);
      const audioChunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, {
          type: "audio/webm",
        });

        stream.getTracks().forEach((track) => {
          track.stop();
        });

        await sendAudioToSTT(audioBlob);
      };

      recorder.start();

      setMediaRecorder(recorder);
      setRecording(true);
    } catch (error) {
      console.error(error);

      alert("Microphone permission required. Please allow microphone access.");
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

      formData.append("audio", audioBlob, "user_voice.webm");

      const response = await fetch(`${API_URL}/stt`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("STT API failed");
      }

      const data = await response.json();

      setMessage(data.text || "");
    } catch (error) {
      console.error(error);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Speech recognition failed. Please try again.",
          error: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // =========================
  // TTS
  // =========================

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
        throw new Error("TTS API failed");
      }

      const blob = await response.blob();

      const url = URL.createObjectURL(blob);

      setAudioUrl(url);

      const audio = new Audio(url);

      await audio.play();
    } catch (error) {
      console.error(error);

      alert("Text-to-Speech failed. Please check ElevenLabs/API.");
    } finally {
      setVoiceLoading(false);
    }
  };

  // =========================
  // FULL VOICE AI
  // =========================

  const startFullVoice = async () => {
    if (recording || voiceLoading) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      const recorder = new MediaRecorder(stream);
      const audioChunks = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data);
        }
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, {
          type: "audio/webm",
        });

        stream.getTracks().forEach((track) => {
          track.stop();
        });

        await sendVoiceToAI(audioBlob);
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

      formData.append("audio", audioBlob, "user_voice.webm");

      formData.append("employee_id", Number(employee.employee_id));

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

      await audio.play();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Voice response generated successfully.",
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
          role: "assistant",
          content:
            "Voice assistant failed. Please check FastAPI and AI services.",
          error: true,
        },
      ]);
    } finally {
      setVoiceLoading(false);
      setRecording(false);
      setMediaRecorder(null);
    }
  };

  // =========================
  // CLEAR CHAT
  // =========================

  const clearChat = () => {
    if (!employee) return;

    const confirmClear = window.confirm("Clear this employee's chat history?");

    if (!confirmClear) return;

    localStorage.removeItem(`chat_${employee.employee_id}`);

    setMessages([]);
    setMessage("");
    setAudioUrl(null);
  };

  // =========================
  // KEYBOARD
  // =========================

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();

      sendMessage();
    }
  };

  // =========================
  // LOGIN SCREEN
  // =========================

  if (!loggedIn) {
    return (
      <div className="login-page">
        <div className="login-background-orb orb-one"></div>
        <div className="login-background-orb orb-two"></div>

        <div className="login-container">
          <div className="login-brand">
            <div className="brand-logo">✦</div>

            <div>
              <h1>Employee AI</h1>
              <p>Intelligent workplace assistant</p>
            </div>
          </div>

          <div className="login-card">
            <div className="login-icon">
              <span>AI</span>
            </div>

            <div className="login-heading">
              <h2>Welcome back</h2>

              <p>Enter your Employee ID to continue</p>
            </div>

            <div className="login-field">
              <label>Employee ID</label>

              <div className="login-input-wrapper">
                <span className="input-symbol">#</span>

                <input
                  type="number"
                  value={loginId}
                  onChange={(event) => {
                    setLoginId(event.target.value);
                    setLoginError("");
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      handleLogin();
                    }
                  }}
                  placeholder="Enter your employee ID"
                  autoFocus
                />
              </div>
            </div>

            {loginError && (
              <div className="login-error">
                <span>!</span>
                {loginError}
              </div>
            )}

            <button
              className="login-button"
              onClick={handleLogin}
              disabled={loginLoading}
            >
              {loginLoading ? (
                <>
                  <span className="button-spinner"></span>
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <span>→</span>
                </>
              )}
            </button>

            <div className="login-security">
              <span>●</span>
              Secure employee access
            </div>
          </div>

          <p className="login-footer">
            AI Employee Assistant • NLP • LLM • RAG • Voice AI
          </p>
        </div>
      </div>
    );
  }

  // =========================
  // MAIN APPLICATION
  // =========================

  const employeeName = employee?.name || "Employee";

  const employeeInitial = employeeName.charAt(0).toUpperCase();

  return (
    <div className="app">
      {/* ================= SIDEBAR ================= */}

      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">✦</div>

          <div>
            <h2>Employee AI</h2>
            <span>Assistant</span>
          </div>
        </div>

        <div className="sidebar-divider"></div>

        <div className="menu-title">WORKSPACE</div>

        <button className="side-menu active">
          <span>✦</span>
          AI Assistant
        </button>

        <button className="side-menu">
          <span>◫</span>
          Dashboard
        </button>

        <button className="side-menu">
          <span>◎</span>
          My Profile
        </button>

        <button className="side-menu">
          <span>⚙</span>
          Settings
        </button>

        <div className="sidebar-info">
          <div className="sidebar-info-icon">✨</div>

          <div>
            <strong>AI Assistant</strong>

            <span>Ask about your work</span>
          </div>
        </div>

        <div className="sidebar-bottom">
          <div className="employee-card">
            <div className="employee-avatar">{employeeInitial}</div>

            <div className="employee-info">
              <strong>{employeeName}</strong>

              <span>ID: {employee.employee_id}</span>
            </div>

            <div className="online-dot"></div>
          </div>

          <button className="logout-button" onClick={logout}>
            <span>↪</span>
            Logout
          </button>
        </div>
      </aside>

      {/* ================= MAIN ================= */}

      <main className="main">
        {/* TOPBAR */}

        <header className="topbar">
          <div className="topbar-left">
            <div className="mobile-logo">✦</div>

            <div>
              <h1>AI Employee Assistant</h1>

              <div className="status">
                <span className="status-dot"></span>
                AI system online
              </div>
            </div>
          </div>

          <div className="topbar-right">
            <div className="employee-top-info">
              <div className="top-avatar">{employeeInitial}</div>

              <div className="top-employee-name">
                <strong>{employeeName}</strong>

                <span>{employee.department || "Employee"}</span>
              </div>
            </div>

            <button className="clear-button" onClick={clearChat}>
              <span>⌫</span>
              Clear chat
            </button>
          </div>
        </header>

        {/* CHAT AREA */}

        <section className="chat-area">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-glow"></div>

              <div className="ai-orb">
                <div className="orb-ring"></div>

                <div className="orb-inner">✦</div>
              </div>

              <div className="welcome-badge">
                <span></span>
                AI Assistant Ready
              </div>

              <h2>
                How can I help you,
                <br />
                <span>{employeeName}?</span>
              </h2>

              <p>
                Ask me about your salary, attendance, projects, experience or
                company policies.
              </p>

              <div className="quick-actions">
                {quickActions.map((action, index) => (
                  <button
                    key={index}
                    className="quick-card"
                    onClick={() => sendMessage(action.text)}
                  >
                    <div className="quick-icon">{action.icon}</div>

                    <div className="quick-content">
                      <strong>{action.title}</strong>

                      <span>{action.description}</span>
                    </div>

                    <span className="arrow">→</span>
                  </button>
                ))}
              </div>

              <div className="feature-row">
                <span>
                  <b>●</b> NLP
                </span>

                <span>
                  <b>●</b> LLM
                </span>

                <span>
                  <b>●</b> RAG
                </span>

                <span>
                  <b>●</b> Voice AI
                </span>
              </div>
            </div>
          ) : (
            <div className="messages">
              <div className="conversation-label">
                <span></span>
                Conversation
              </div>

              {messages.map((item, index) => (
                <div
                  key={index}
                  className={`message-row ${
                    item.role === "user" ? "user-row" : "assistant-row"
                  }`}
                >
                  {item.role === "assistant" && (
                    <div className="message-avatar">✦</div>
                  )}

                  <div className="message-content">
                    <div
                      className={`message-name ${
                        item.role === "user" ? "user-name" : ""
                      }`}
                    >
                      {item.role === "user" ? employeeName : "AI Assistant"}
                    </div>

                    <div
                      className={`message-bubble ${
                        item.role === "user"
                          ? "user-bubble"
                          : "assistant-bubble"
                      } ${item.error ? "error-bubble" : ""}`}
                    >
                      {item.content}
                    </div>

                    {item.role === "assistant" && (
                      <div className="message-tools">
                        <button
                          onClick={() => generateSpeech(item.content)}
                          disabled={voiceLoading}
                          title="Listen"
                        >
                          {voiceLoading ? "..." : "🔊"}
                        </button>

                        {item.time && <span>{item.time}</span>}
                      </div>
                    )}

                    {item.role === "user" && item.time && (
                      <div className="user-time">{item.time}</div>
                    )}
                  </div>

                  {item.role === "user" && (
                    <div className="user-message-avatar">{employeeInitial}</div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="message-row assistant-row">
                  <div className="message-avatar">✦</div>

                  <div className="message-content">
                    <div className="message-name">AI Assistant</div>

                    <div className="message-bubble assistant-bubble">
                      <div className="typing">
                        <span></span>
                        <span></span>
                        <span></span>

                        <small>Thinking...</small>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef}></div>
            </div>
          )}
        </section>

        {/* AUDIO PLAYER */}

        {audioUrl && (
          <div className="audio-panel">
            <div className="audio-icon">🔊</div>

            <div className="audio-info">
              <strong>AI Voice Response</strong>

              <span>Audio generated successfully</span>
            </div>

            <audio controls src={audioUrl} />

            <button className="close-audio" onClick={() => setAudioUrl(null)}>
              ×
            </button>
          </div>
        )}

        {/* INPUT */}

        <section className="input-section">
          <div
            className={`input-wrapper ${recording ? "input-recording" : ""}`}
          >
            <textarea
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                recording ? "Listening..." : "Ask your AI assistant anything..."
              }
              rows="1"
              disabled={recording}
            />

            <div className="input-actions">
              {/* STT */}

              <button
                className={`icon-button ${recording ? "recording" : ""}`}
                onClick={recording ? stopRecording : startRecording}
                title={recording ? "Stop recording" : "Speech to Text"}
              >
                {recording ? "■" : "🎙"}
              </button>

              {/* FULL VOICE */}

              <button
                className={`voice-ai-button ${recording ? "recording" : ""}`}
                onClick={recording ? stopRecording : startFullVoice}
                disabled={voiceLoading}
                title="Speech to Speech"
              >
                {voiceLoading ? "..." : "✦"}
              </button>

              {/* SEND */}

              <button
                className="send-button"
                onClick={() => sendMessage()}
                disabled={!message.trim() || loading || recording}
                title="Send message"
              >
                ↑
              </button>
            </div>
          </div>

          <div className="input-hint">
            <span>
              <b>Enter</b> to send
            </span>

            <span>🎙 Speech to Text</span>

            <span>✦ Voice AI</span>

            <span>🔊 Text to Speech</span>
          </div>
        </section>

        <footer>
          AI Employee Assistant
          <span>•</span>
          NLP
          <span>•</span>
          LLM
          <span>•</span>
          RAG
          <span>•</span>
          Voice AI
        </footer>
      </main>
    </div>
  );
}

export default App;
