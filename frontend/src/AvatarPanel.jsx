import { useEffect, useRef, useState } from "react";
import * as sdk from "@d-id/client-sdk";

const AGENT_ID = "v2_agt_hbTqX-Fg";
const CLIENT_KEY = "ck_VPFNyH1Iih6NHXtXUzsvJ";

function AvatarPanel() {
  const videoRef = useRef(null);
  const agentRef = useRef(null);

  const [status, setStatus] = useState("Connecting...");
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;

    const initializeAvatar = async () => {
      try {
        const auth = {
          type: "key",
          clientKey: CLIENT_KEY,
        };

        const callbacks = {
          onSrcObjectReady(value) {
            if (videoRef.current) {
              videoRef.current.srcObject = value;
            }
          },

          onConnectionStateChange(state) {
            console.log("Avatar connection:", state);

            if (mounted) {
              setStatus(state);

              if (state === "connected") {
                setStatus("Avatar Connected");
              }
            }
          },

          onVideoStateChange(state) {
            console.log("Avatar video:", state);
          },

          onError(error, errorData) {
            console.error("D-ID Error:", error, errorData);

            if (mounted) {
              setError("Avatar connection failed.");
            }
          },
        };

        const streamOptions = {
          compatibilityMode: "auto",
          streamWarmup: true,
        };

        const agent = await sdk.createAgentManager(AGENT_ID, {
          auth,
          callbacks,
          streamOptions,
        });

        agentRef.current = agent;

        await agent.connect();

        if (mounted) {
          setStatus("Avatar Connected");
        }
      } catch (error) {
        console.error("Avatar initialization error:", error);

        if (mounted) {
          setError(error.message || "Failed to initialize avatar.");
          setStatus("Disconnected");
        }
      }
    };

    initializeAvatar();

    return () => {
      mounted = false;

      if (agentRef.current) {
        agentRef.current.disconnect();
      }
    };
  }, []);

  const testSpeak = async () => {
    try {
      if (!agentRef.current) {
        return;
      }

      setStatus("Avatar Speaking...");

      await agentRef.current.speak({
        type: "text",
        input: "Hello! I am your AI employee assistant.",
      });

      setStatus("Avatar Connected");
    } catch (error) {
      console.error("Speak error:", error);
      setError("Avatar could not speak.");
    }
  };

  return (
    <div className="avatar-panel">
      <div className="avatar-header">
        <div>
          <h3>AI Assistant</h3>
          <span>{status}</span>
        </div>
      </div>

      <div className="avatar-video-container">
        <video ref={videoRef} autoPlay playsInline controls={false} />

        {error && <div className="avatar-error">{error}</div>}
      </div>

      <button className="avatar-test-button" onClick={testSpeak}>
        Test Avatar
      </button>
    </div>
  );
}

export default AvatarPanel;
