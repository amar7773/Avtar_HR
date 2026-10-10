import os
import logging
from typing import Optional, Dict, Any
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("LiveAvatarService")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)


class LiveAvatarService:
    """
    Service wrapper for the official HeyGen LiveAvatar API (v1).
    Documentation: https://docs.liveavatar.com
    
    Handles:
    - Secure server-side authentication using API_LIVE
    - Temporary session token creation for the frontend Web SDK
    - Session initiation, termination, and keep-alive
    - Error normalization without leaking sensitive credentials to the client
    """

    DEFAULT_BASE_URL = "https://api.liveavatar.com/v1"

    def __init__(
        self,
        api_key: Optional[str] = None,
        avatar_id: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = (
            api_key
            or os.getenv("API_LIVE")
            or os.getenv("HEYGEN_API_KEY")
            or ""
        ).strip()
        self.default_avatar_id = (
            avatar_id
            or os.getenv("Avtar_ID")
            or os.getenv("HEYGEN_AVATAR_ID")
            or ""
        ).strip()
        self.base_url = (base_url or os.getenv("HEYGEN_API_BASE") or self.DEFAULT_BASE_URL).rstrip("/")

        if not self.api_key:
            logger.warning("[LIVE-AVATAR] Warning: API_LIVE is not set in environment or .env.")

    @property
    def is_configured(self) -> bool:
        """Returns True if the required API key is present."""
        return bool(self.api_key)

    def get_default_avatar_id(self) -> str:
        """Returns the default avatar ID configured in .env."""
        return self.default_avatar_id

    def create_session_token(
        self,
        avatar_id: Optional[str] = None,
        mode: str = "LITE",
        is_sandbox: bool = False,
        quality: str = "medium",
        language: str = "en",
        voice_id: Optional[str] = None,
        context_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Request a temporary session token from LiveAvatar.
        Endpoint: POST https://api.liveavatar.com/v1/sessions/token
        Headers: X-API-KEY: <API_LIVE>
        
        Returns:
            {
                "session_id": str,
                "session_token": str
            }
        """
        if not self.is_configured:
            raise ValueError("LiveAvatar API key (API_LIVE) is not configured in .env.")

        target_avatar_id = (avatar_id or self.default_avatar_id).strip()
        if not target_avatar_id:
            raise ValueError("LiveAvatar avatar ID (Avtar_ID) is required.")

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload: Dict[str, Any] = {
            "mode": mode.upper(),
            "avatar_id": target_avatar_id,
        }

        if is_sandbox:
            payload["is_sandbox"] = True

        if quality:
            payload["video_settings"] = {
                "quality": quality,
                "encoding": "H264",
            }

        persona: Dict[str, Any] = {}
        if voice_id:
            persona["voice_id"] = voice_id.strip()
        if context_id:
            persona["context_id"] = context_id.strip()
        if language:
            persona["language"] = language.strip()

        # HeyGen FULL mode requires avatar_persona (or voice_agent)
        if mode.upper() == "FULL":
            payload["avatar_persona"] = persona
        elif persona:
            payload["avatar_persona"] = persona

        try:
            url = f"{self.base_url}/sessions/token"
            logger.info(f"[LIVE-AVATAR] Creating session token (avatar_id={target_avatar_id}, mode={mode})...")
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code != 200:
                err_msg = response.text
                try:
                    err_json = response.json()
                    err_msg = err_json.get("message") or err_json.get("detail") or response.text
                except Exception:
                    pass
                logger.error(f"[LIVE-AVATAR] Session token creation failed ({response.status_code}): {err_msg}")
                raise RuntimeError(f"LiveAvatar session creation failed: {err_msg}")

            data = response.json()
            # LiveAvatar responses use standard envelope: {"code": 1000, "data": {...}, "message": "..."}
            resp_code = data.get("code")
            if resp_code not in (1000, 200, None):
                msg = data.get("message") or f"Error code {resp_code}"
                raise RuntimeError(f"LiveAvatar returned error: {msg}")

            session_data = data.get("data") or data
            session_id = session_data.get("session_id")
            session_token = session_data.get("session_token")

            if not session_token:
                raise RuntimeError("LiveAvatar response did not include a valid session_token.")

            return {
                "session_id": session_id,
                "session_token": session_token,
                "avatar_id": target_avatar_id,
                "mode": mode,
            }
        except requests.RequestException as exc:
            logger.error(f"[LIVE-AVATAR] Network error connecting to LiveAvatar: {exc}")
            raise RuntimeError(f"Could not reach LiveAvatar service: {exc}") from exc

    def start_session(self, session_token: str) -> Dict[str, Any]:
        """
        Optionally start session on the server side using the session_token.
        Endpoint: POST https://api.liveavatar.com/v1/sessions/start
        Headers: Authorization: Bearer <session_token>
        """
        if not session_token:
            raise ValueError("session_token is required to start LiveAvatar session.")

        headers = {
            "Authorization": f"Bearer {session_token.strip()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            url = f"{self.base_url}/sessions/start"
            response = requests.post(url, headers=headers, json={}, timeout=30)
            if response.status_code != 200:
                raise RuntimeError(f"Failed to start LiveAvatar session ({response.status_code}): {response.text}")

            data = response.json()
            if data.get("code") not in (1000, 200, None):
                raise RuntimeError(data.get("message") or "Failed to start LiveAvatar session.")
            return data.get("data") or data
        except requests.RequestException as exc:
            raise RuntimeError(f"LiveAvatar start_session request error: {exc}") from exc

    def stop_session(self, session_token: str) -> bool:
        """
        Terminate an active LiveAvatar session.
        Endpoint: POST https://api.liveavatar.com/v1/sessions/stop
        Headers: Authorization: Bearer <session_token>
        """
        if not session_token:
            return False

        headers = {
            "Authorization": f"Bearer {session_token.strip()}",
            "Content-Type": "application/json",
        }

        try:
            url = f"{self.base_url}/sessions/stop"
            response = requests.post(url, headers=headers, json={}, timeout=15)
            return response.status_code == 200
        except Exception as exc:
            logger.warning(f"[LIVE-AVATAR] Failed to stop session: {exc}")
            return False

    def keep_alive(self, session_token: str) -> bool:
        """
        Send a keep-alive ping for an active LiveAvatar session.
        Endpoint: POST https://api.liveavatar.com/v1/sessions/keep-alive
        Headers: Authorization: Bearer <session_token>
        """
        if not session_token:
            return False

        headers = {
            "Authorization": f"Bearer {session_token.strip()}",
            "Content-Type": "application/json",
        }

        try:
            url = f"{self.base_url}/sessions/keep-alive"
            response = requests.post(url, headers=headers, json={}, timeout=15)
            return response.status_code == 200
        except Exception:
            return False
